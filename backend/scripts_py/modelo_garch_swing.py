"""
Nome do script : modelo_garch_swing.py
Descricao      : Primeiro modelo de "quando e a que preco" um proximo
                  topo/fundo intradiario deve ocorrer, por ativo, SOB
                  DEMANDA (nao continuo, nao entra no main.py) - consumido
                  pelo endpoint GET /api/modelo-swing/{raiz} do
                  api_server.py, chamado toda vez que o usuario troca o
                  ativo no seletor do card (ModeloSwingCard.jsx no
                  frontend).

                  Combina tres leituras, sem recalcular o que ja existe:
                  1) QUANDO: horario historicamente mais provavel de topo
                     e de fundo (marginal_topo/marginal_fundo), ja
                     calculado por diag_sazonalidade_swings.py e salvo em
                     json/diag_sazonalidade_swings.json - so LE, nunca
                     recalcula.
                  2) VIES: sinal do MACD M15 (>0 alta, <0 baixa) e estado
                     do IFR M5 (<=30 sobrevendido, >=70 sobrecomprado) do
                     candle mais recente - lidos de
                     parquet/historicos/MTF/<raiz>/indicadores/, mesmos
                     arquivos que indicadores_mtf.py ja mantem (nada
                     recalculado aqui tambem).
                  3) A QUE PRECO: faixa de oscilacao esperada pro proximo
                     candle M15, via GARCH(1,1) (biblioteca `arch`) sobre
                     o retorno logaritmico do fechamento M15 - PRIMEIRO
                     modelo estatistico do projeto pra essa pergunta
                     (fila: regressao/ARIMA family, XGBoost/LightGBM/
                     CatBoost, todos ainda por fazer). Faixa = preco atual
                     x exp(+-1 sigma), sigma = desvio-padrao do retorno
                     previsto 1 passo a frente pelo GARCH. E uma faixa de
                     OSCILACAO GERAL (nao diferencia se o proximo extremo
                     vai ser topo ou fundo - isso quem sinaliza e o vies
                     do item 2) - simplificacao deliberada de primeira
                     versao, documentada aqui pra nao ser lida como mais
                     precisa do que e.

                  Dependencia NOVA, ainda nao instalada no venv do
                  Windows (`backend/scripts_py/venv`) - confirmado
                  2026-09-27 olhando o site-packages direto, sem rodar
                  nada no Windows (pandas/numpy/fastapi/MetaTrader5/
                  pyarrow ja estavam la, `arch` nao): rodar, uma vez,
                  dentro do venv do projeto:
                      pip install arch

                  Reaproveita _carregar_concatenado()/montar_universo() de
                  diag_sazonalidade_swings.py (mesma logica de concatenar
                  subpasta de vencimento MM-AAAA + dedup por time) - nao
                  duplica a funcao aqui.
Autor          : Julio Cesar Silvio Campanhola
Criado em      : 2026-09-27
Ultima edicao  : 2026-09-27
Versao         : 1.0.0
Projeto        : dashboard
Historico      : scripts_py/versoes/modelo_garch_swing.md
"""

import importlib
import json
import os

import numpy as np

from diag_sazonalidade_swings import _carregar_concatenado, montar_universo

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIAG_SAZONALIDADE_JSON = os.path.join(BASE_DIR, "json", "diag_sazonalidade_swings.json")

RSI_SOBRECOMPRADO = 70
RSI_SOBREVENDIDO = 30
AMOSTRA_MINIMA_GARCH = 200


class ModeloGarchSwing:
    """Analisa um ativo sob demanda: le preco (M15) + indicadores ja
    calculados (M15/M5), ajusta um GARCH(1,1) no retorno do fechamento M15
    e devolve um dict pronto pra virar resposta de API."""

    def __init__(self):
        self._diag_cache = None  # json de diag_sazonalidade_swings.py, lido uma vez por processo

    def _carregar_diag(self):
        if self._diag_cache is None:
            if os.path.exists(DIAG_SAZONALIDADE_JSON):
                with open(DIAG_SAZONALIDADE_JSON, encoding="utf-8") as f:
                    self._diag_cache = json.load(f)
            else:
                self._diag_cache = {}
        return self._diag_cache

    @staticmethod
    def _horario_mais_provavel(dicionario):
        # marginal_topo/marginal_fundo ja saem ordenados desc por contagem
        # (ver analisar_raiz() em diag_sazonalidade_swings.py) - o primeiro
        # item e o horario mais frequente.
        if not dicionario:
            return None
        return next(iter(dicionario))

    @staticmethod
    def _calcular_sigma_garch(precos_close):
        try:
            arch_model = importlib.import_module("arch").arch_model
        except ImportError as exc:
            raise ImportError(
                "A dependencia 'arch' nao esta instalada neste Python. Instale com: pip install arch"
            ) from exc

        retornos_pct = np.log(precos_close).diff().dropna() * 100
        if len(retornos_pct) < AMOSTRA_MINIMA_GARCH:
            raise ValueError(
                f"amostra insuficiente pro GARCH ({len(retornos_pct)} retornos, "
                f"minimo {AMOSTRA_MINIMA_GARCH})"
            )

        modelo = arch_model(retornos_pct, vol="Garch", p=1, q=1, dist="normal", rescale=False)
        resultado = modelo.fit(disp="off", show_warning=False)
        previsao = resultado.forecast(horizon=1, reindex=False)
        variancia_pct = float(previsao.variance.values[-1, 0])
        return (variancia_pct ** 0.5) / 100  # volta da escala de retorno em % pra decimal

    def analisar(self, raiz):
        df_precos = _carregar_concatenado(raiz, None, "m15.parquet", ["time", "close"])
        if df_precos is None or len(df_precos) < AMOSTRA_MINIMA_GARCH:
            n = 0 if df_precos is None else len(df_precos)
            raise ValueError(f"sem candles M15 suficientes pra {raiz!r} ({n} candles)")

        ind_m15 = _carregar_concatenado(raiz, "indicadores", "m15.parquet", ["time", "macd", "ifr"])
        ind_m5 = _carregar_concatenado(raiz, "indicadores", "m5.parquet", ["time", "ifr"])

        preco_atual = float(df_precos["close"].iloc[-1])
        sigma = self._calcular_sigma_garch(df_precos["close"])

        macd_atual = float(ind_m15["macd"].iloc[-1]) if ind_m15 is not None and len(ind_m15) else None
        ifr_m5_atual = float(ind_m5["ifr"].iloc[-1]) if ind_m5 is not None and len(ind_m5) else None

        if macd_atual is None:
            vies = "indisponivel"
        elif macd_atual > 0:
            vies = "alta"
        elif macd_atual < 0:
            vies = "baixa"
        else:
            vies = "neutro"

        if ifr_m5_atual is None:
            estado_ifr = "indisponivel"
        elif ifr_m5_atual >= RSI_SOBRECOMPRADO:
            estado_ifr = "sobrecomprado"
        elif ifr_m5_atual <= RSI_SOBREVENDIDO:
            estado_ifr = "sobrevendido"
        else:
            estado_ifr = "neutro"

        diag_raiz = self._carregar_diag().get(raiz, {})

        return {
            "raiz": raiz,
            "preco_atual": preco_atual,
            "vies_macd_m15": vies,
            "macd_m15": macd_atual,
            "ifr_m5": ifr_m5_atual,
            "ifr_m5_estado": estado_ifr,
            "horario_mais_provavel_topo": self._horario_mais_provavel(diag_raiz.get("marginal_topo")),
            "horario_mais_provavel_fundo": self._horario_mais_provavel(diag_raiz.get("marginal_fundo")),
            "sigma_garch_1passo_pct": round(sigma * 100, 3),
            # 5 casas (nao 2) porque o universo inclui pares de forex com
            # preco < 2 (ex.: EURUSD ~1.14) - 2 casas arredondava a faixa
            # inteira pro mesmo numero, escondendo a variacao esperada.
            "faixa_esperada_min": round(preco_atual * float(np.exp(-sigma)), 5),
            "faixa_esperada_max": round(preco_atual * float(np.exp(sigma)), 5),
            "candles_m15_amostra": len(df_precos),
        }


if __name__ == "__main__":
    modelo = ModeloGarchSwing()
    for raiz_teste in ["Indice", "Dolar", "EURUSD", "AAPL", "GOLD"]:
        try:
            print(json.dumps(modelo.analisar(raiz_teste), ensure_ascii=False, indent=2))
        except Exception as exc:
            print(f"AVISO: falha em {raiz_teste}: {exc}")

    print(f"\nuniverso completo disponivel pro seletor do frontend: {len(montar_universo())} ativos")
