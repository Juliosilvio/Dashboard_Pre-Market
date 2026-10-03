"""
Nome do script : cenario_final_swing.py
Descricao      : "Quinto passo" da fila de modelagem - junta as duas pecas
                  ja treinadas (modelo_garch_swing.py e
                  modelo_classificador_swing.py) num UNICO cenario por
                  ativo com direcao sugerida, faixa-alvo e preco de
                  entrada - pedido explicito do usuario (2026-09-27):
                  "com os numeros gerados por essa fase do sistema
                  precisamos de recomendacao de onde o preco pode ir e
                  qual e a entrada".

                  Ate aqui cada peca falava sozinha: `modelo_garch_swing.py`
                  da o VIES (MACD/IFR) e a FAIXA de oscilacao (GARCH);
                  `modelo_classificador_swing.py` da a PROBABILIDADE
                  calibrada de o candle atual ser um topo ou um fundo. Este
                  script SO combina os dois (nao recalcula nada de novo):

                  1) Roda `ModeloGarchSwing.analisar(raiz)` -> preco atual,
                     vies MACD/IFR, faixa esperada (GARCH).
                  2) Carrega os dois modelos ja treinados
                     (`modelos/classificador_swing_topo.joblib` e
                     `_fundo.joblib`) e pontua o candle MTF mais recente do
                     ativo (mesmas features do treino: macd/macd_sinal/
                     macd_hist/ifr M15, atr M15, ifr M5, minutos do dia).
                  3) Sinal = "topo" se p(topo) >= p(fundo) E acima do
                     limiar calibrado (`json/limiares_classificador_swing.json`
                     - percentil do score que bate a MESMA taxa de disparo
                     media que a regra crua MACD/IFR tinha na validacao,
                     nao um "0.5" arbitrario que nao faz sentido pra uma
                     classe rara ~15%); espelhado pra "fundo". Sem os dois
                     acima do limiar -> "indefinido" (sem sinal, disparar
                     recomendacao errada e pior que nao dar recomendacao).
                  4) Direcao: sinal "topo" (mercado deve reverter pra
                     baixo) -> VENDA; sinal "fundo" -> COMPRA.
                  5) Alvo: ponta da faixa GARCH na direcao esperada (venda
                     -> faixa_esperada_min; compra -> faixa_esperada_max).
                  6) Confianca: "alta" quando a regra crua MACD/IFR TAMBEM
                     concorda com o sinal do modelo (dois metodos
                     independentes bateram); "moderada" quando so o
                     modelo aponta.
                  7) Entrada - pedido do usuario foi as DUAS opcoes, nao
                     uma so:
                     - `entrada_a_mercado`: preco atual, reage na hora.
                     - `entrada_zona_pullback`: ponto medio entre o preco
                       atual e a ponta OPOSTA da faixa GARCH (ex.: sinal de
                       venda espera o preco subir mais um pouco antes de
                       reverter - entrada mais vantajosa, vendendo mais
                       caro; sinal de compra e o espelho, comprando mais
                       barato). So e uma referencia geometrica dentro da
                       faixa esperada, nao um nivel tecnico (suporte/
                       resistencia real) - simplificacao de primeira
                       versao, documentada aqui.

                  NAO calcula stop (fora do pedido desta versao - "1 e 2"
                  nas opcoes de entrada, sem a opcao de stop tecnico).

                  Igual as pecas anteriores da fila: leitura de modelo
                  estatistico, nao e recomendacao de investimento - ver
                  campo "aviso" na saida. Ainda standalone (nao registrado
                  no main.py, nao tem endpoint proprio no api_server.py
                  ainda) - roda sob demanda com
                  `python cenario_final_swing.py`.

                  Reaproveita ModeloGarchSwing (modelo_garch_swing.py) e
                  carregar_precos/carregar_indicadores/montar_universo/
                  minutos_do_dia/COLUNAS_INDICADOR_* (diag_sazonalidade_
                  swings.py) - nada recalculado aqui alem da combinacao.
                  1.1.0 (2026-09-27, mesmo dia): saida passa a ser um
                  SUPERSET do dict de ModeloGarchSwing.analisar() (mantem
                  preco_atual, vies_macd_m15, macd_m15, ifr_m5,
                  ifr_m5_estado, sigma_garch_1passo_pct,
                  candles_m15_amostra - todos ja consumidos pelo
                  ModeloSwingCard.jsx) em vez de um dict novo so com os
                  campos do cenario - permitiu trocar direto a chamada do
                  endpoint GET /api/modelo-swing/{raiz} em api_server.py
                  (1.18.0) de ModeloGarchSwing pra CenarioFinalSwing sem
                  quebrar nada que ja lia a resposta antiga.
Autor          : Julio Cesar Silvio Campanhola
Criado em      : 2026-09-27
Ultima edicao  : 2026-09-27
Versao         : 1.1.0
Projeto        : dashboard
Historico      : scripts_py/versoes/cenario_final_swing.md
"""

import json
import os

import joblib
import numpy as np
import pandas as pd

from diag_sazonalidade_swings import (
    COLUNAS_INDICADOR_M15,
    COLUNAS_INDICADOR_M5,
    carregar_indicadores,
    minutos_do_dia,
)
from modelo_classificador_swing import FEATURES, MODELOS_DIR
from modelo_garch_swing import ModeloGarchSwing

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIMIARES_PATH = os.path.join(BASE_DIR, "json", "limiares_classificador_swing.json")

AVISO_PADRAO = (
    "Leitura combinada de modelos estatisticos (GARCH + classificador LightGBM) "
    "- nao e recomendacao de investimento, e apoio de decisao. Faixa/alvo sao "
    "estimativas de oscilacao (nao garantia de preco); entrada de zona/pullback "
    "e so uma referencia geometrica dentro da faixa esperada, nao suporte/"
    "resistencia tecnica real. Decisao final e sempre do usuario."
)


class CenarioFinalSwing:
    """Combina ModeloGarchSwing (vies + faixa) com os dois classificadores
    ja treinados (probabilidade de topo/fundo) num cenario unico por
    ativo: direcao sugerida, alvo e duas opcoes de entrada."""

    def __init__(self):
        self._garch = ModeloGarchSwing()
        self._modelo_topo = None
        self._modelo_fundo = None
        self._limiares = None

    def _carregar_modelos(self):
        if self._modelo_topo is None or self._modelo_fundo is None:
            caminho_topo = os.path.join(MODELOS_DIR, "classificador_swing_topo.joblib")
            caminho_fundo = os.path.join(MODELOS_DIR, "classificador_swing_fundo.joblib")
            if not (os.path.exists(caminho_topo) and os.path.exists(caminho_fundo)):
                raise FileNotFoundError(
                    "modelos do classificador nao encontrados em "
                    f"{MODELOS_DIR} - rode modelo_classificador_swing.py primeiro"
                )
            self._modelo_topo = joblib.load(caminho_topo)
            self._modelo_fundo = joblib.load(caminho_fundo)
        return self._modelo_topo, self._modelo_fundo

    def _carregar_limiares(self):
        if self._limiares is None:
            if not os.path.exists(LIMIARES_PATH):
                raise FileNotFoundError(
                    f"{LIMIARES_PATH} nao encontrado - rode modelo_classificador_swing.py primeiro"
                )
            with open(LIMIARES_PATH, encoding="utf-8") as f:
                self._limiares = json.load(f)
        return self._limiares

    @staticmethod
    def _features_candle_atual(raiz):
        """Ultimo candle M15 com indicador ja calculado (mesmas 7 features
        do treino) - NAO usa merge_asof aqui porque so precisamos do
        instante mais recente, nao da serie inteira."""
        ind_m15 = carregar_indicadores(raiz, "m15", COLUNAS_INDICADOR_M15)
        if ind_m15 is None or len(ind_m15) == 0:
            raise ValueError(f"sem indicadores M15 pra {raiz!r}")
        ind_m5 = carregar_indicadores(raiz, "m5", COLUNAS_INDICADOR_M5)
        ifr_m5_atual = float(ind_m5["ifr"].iloc[-1]) if ind_m5 is not None and len(ind_m5) else np.nan

        ultimo = ind_m15.iloc[-1]
        linha = pd.DataFrame([{
            "macd_m15": ultimo["macd"], "macd_sinal_m15": ultimo["macd_sinal"],
            "macd_hist_m15": ultimo["macd_hist"], "ifr_m15": ultimo["ifr"],
            "atr_m15": ultimo["atr"], "ifr_m5": ifr_m5_atual,
            "minutos_do_dia": minutos_do_dia(ultimo["time"]),
        }])
        return linha

    def analisar(self, raiz):
        garch = self._garch.analisar(raiz)  # ja levanta ValueError/ImportError se faltar amostra/dependencia
        modelo_topo, modelo_fundo = self._carregar_modelos()
        limiares = self._carregar_limiares()

        linha = self._features_candle_atual(raiz)
        if linha[FEATURES].isna().any(axis=None):
            raise ValueError(f"feature incompleta pro candle atual de {raiz!r} (indicador ainda nao calculado)")

        p_topo = float(modelo_topo.predict_proba(linha[FEATURES])[0, 1])
        p_fundo = float(modelo_fundo.predict_proba(linha[FEATURES])[0, 1])
        limiar_topo = limiares.get("topo", 1.0)
        limiar_fundo = limiares.get("fundo", 1.0)

        if p_topo >= p_fundo and p_topo >= limiar_topo:
            sinal, direcao = "topo", "venda"
        elif p_fundo > p_topo and p_fundo >= limiar_fundo:
            sinal, direcao = "fundo", "compra"
        else:
            sinal, direcao = "indefinido", "sem sinal"

        macd_atual, ifr_m5_atual = garch["macd_m15"], garch["ifr_m5"]
        regra_concorda = None
        if sinal == "topo":
            regra_concorda = bool(macd_atual is not None and macd_atual > 0
                                   and ifr_m5_atual is not None and ifr_m5_atual >= 70)
        elif sinal == "fundo":
            regra_concorda = bool(macd_atual is not None and macd_atual < 0
                                   and ifr_m5_atual is not None and ifr_m5_atual <= 30)

        if sinal == "indefinido":
            confianca = "sem sinal"
        elif regra_concorda:
            confianca = "alta (modelo e regra MACD/IFR concordam)"
        else:
            confianca = "moderada (so o modelo aponta, regra MACD/IFR nao confirma)"

        preco_atual = garch["preco_atual"]
        faixa_min, faixa_max = garch["faixa_esperada_min"], garch["faixa_esperada_max"]

        alvo_sugerido = entrada_zona = None
        if direcao == "venda":
            alvo_sugerido = faixa_min
            entrada_zona = round((preco_atual + faixa_max) / 2, 5)
        elif direcao == "compra":
            alvo_sugerido = faixa_max
            entrada_zona = round((preco_atual + faixa_min) / 2, 5)

        # superset do dict do ModeloGarchSwing (preco_atual, vies_macd_m15,
        # macd_m15, ifr_m5, ifr_m5_estado, horario_mais_provavel_topo/fundo,
        # sigma_garch_1passo_pct, faixa_esperada_min/max,
        # candles_m15_amostra) - o card do frontend ja consome esses campos
        # direto do endpoint GARCH, entao mantemos todos e so ACRESCENTAMOS
        # os novos, pra nao quebrar quem ja le a resposta antiga.
        resultado = dict(garch)
        resultado.update({
            "sinal": sinal,
            "direcao_sugerida": direcao,
            "confianca": confianca,
            "probabilidade_topo_pct": round(p_topo * 100, 1),
            "probabilidade_fundo_pct": round(p_fundo * 100, 1),
            "limiar_topo_pct": round(limiar_topo * 100, 1),
            "limiar_fundo_pct": round(limiar_fundo * 100, 1),
            "alvo_sugerido": alvo_sugerido,
            "entrada_a_mercado": preco_atual,
            "entrada_zona_pullback": entrada_zona,
            "aviso": AVISO_PADRAO,
        })
        return resultado


if __name__ == "__main__":
    cenario = CenarioFinalSwing()
    for raiz_teste in ["Indice", "Dolar", "EURUSD", "AAPL", "GOLD"]:
        try:
            print(json.dumps(cenario.analisar(raiz_teste), ensure_ascii=False, indent=2))
        except Exception as exc:
            print(f"AVISO: falha em {raiz_teste}: {exc}")
