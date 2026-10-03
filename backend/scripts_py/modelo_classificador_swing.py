"""
Nome do script : modelo_classificador_swing.py
Descricao      : Segunda peca de modelagem da fila descrita em
                  diag_sazonalidade_swings.py (v2.0.0) e no documento de
                  arquitetura ("Terceira leitura" / "Quarto passo") - a
                  primeira foi o GARCH (modelo_garch_swing.py, faixa de
                  oscilacao). Esta treina um CLASSIFICADOR (LightGBM) que
                  tenta prever, a partir do estado MACD/IFR/ATR (M15) e IFR
                  (M5) de CADA candle M15 do universo (nao so dos pontos de
                  swing ja confirmados), a probabilidade daquele candle ser
                  um topo ou um fundo - tentando bater a leitura crua ja
                  registrada em diag_sazonalidade_swings.py (10,7% dos
                  fundos e 10,0% dos topos confirmados por "macd E ifr_m5"
                  simultaneos, olhando SO os pontos que ja eram swing).

                  Diferenca importante em relacao ao dataset que ja existia
                  (sazonalidade_swings_universo.parquet): aquele parquet so
                  tem os PONTOS DE SWING (positivos) - nao da pra treinar
                  um classificador com ele sozinho, porque falta o negativo
                  (candle que NAO virou swing). Este script reconstroi a
                  serie COMPLETA de cada ativo (todos os candles M15 dentro
                  da janela em que o fractal N=2 consegue decidir, ou seja,
                  excluindo as N_SWING pontas de cada serie) e rotula 1/0
                  se aquele candle e um topo/fundo confirmado pelo mesmo
                  `detectar_swings()` de diag_sazonalidade_swings.py -
                  reaproveitado por import, nada recalculado feature por
                  feature aqui.

                  Dois classificadores binarios (topo, fundo), LightGBM,
                  POOLED no universo inteiro (nao um modelo por ativo -
                  129 modelos seria dado demais fragmentado e a "jogada"
                  do usuario e sobre o ESTADO do indicador, nao sobre uma
                  peculiaridade do ativo especifico). Classe extremamente
                  desbalanceada (swing e raro) - compensado via
                  `scale_pos_weight` do LightGBM, nao oversampling.

                  Validacao walk-forward (NUNCA split aleatorio, mesma
                  regra usada em toda a fila do projeto): cada ativo tem
                  profundidade historica diferente (uns poucos meses, tudo
                  M15), entao o corte usa QUANTIS de tempo por ativo (nao
                  uma data de calendario fixa, que deixaria ativo novo
                  inteiro de um lado so) - 3 janelas expansivas (25/50/75%
                  treino -> proximo quarto de teste), metrica final e a
                  MEDIA das 3 dobras. Compara, em cada dobra: prevalencia
                  crua de swing no teste, precisao da regra crua (macd e
                  ifr_m5 nos extremos) no teste, e precisao do modelo
                  tomando o MESMO percentual de candles (top-K score) que a
                  regra crua teria disparado - pra comparar peras com
                  peras (nao adianta o modelo disparar em 50% dos candles
                  e "ganhar" da regra que so dispara em 5%).

                  Saida:
                  - json/modelo_classificador_swing.json: metricas por
                    dobra + agregado, importancia de feature.
                  - modelos/classificador_swing_topo.joblib e
                    modelos/classificador_swing_fundo.joblib: modelo final
                    (treinado com TODO o dado disponivel, apos a validacao
                    walk-forward ja ter medido o desempenho fora da
                    amostra) - pendente de wiring num endpoint tipo
                    modelo_garch_swing.py, nao feito aqui ainda (pedido do
                    usuario foi "escolher e treinar", nao integrar no
                    frontend).

                  Ainda standalone (nao registrado no main.py) - roda sob
                  demanda com `python modelo_classificador_swing.py`.
                  Dependencia nova no venv do projeto: `lightgbm`,
                  `scikit-learn` (nem uma nem outra estava instalada antes
                  desta versao - ver `versoes/modelo_classificador_swing.md`
                  pra confirmacao).
Autor          : Julio Cesar Silvio Campanhola
Criado em      : 2026-09-27
Ultima edicao  : 2026-09-27
Versao         : 1.0.0
Projeto        : dashboard
Historico      : scripts_py/versoes/modelo_classificador_swing.md
"""

import json
import os

import joblib
import numpy as np
import pandas as pd
from lightgbm import LGBMClassifier
from sklearn.metrics import average_precision_score, roc_auc_score

from diag_sazonalidade_swings import (
    COLUNAS_INDICADOR_M15,
    COLUNAS_INDICADOR_M5,
    N_SWING,
    carregar_indicadores,
    carregar_precos,
    detectar_swings,
    minutos_do_dia,
    montar_universo,
)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAIDA_JSON_PATH = os.path.join(BASE_DIR, "json", "modelo_classificador_swing.json")
SAIDA_LIMIARES_PATH = os.path.join(BASE_DIR, "json", "limiares_classificador_swing.json")
MODELOS_DIR = os.path.join(BASE_DIR, "modelos")

FEATURES = ["macd_m15", "macd_sinal_m15", "macd_hist_m15", "ifr_m15", "atr_m15", "ifr_m5", "minutos_do_dia"]
ALVOS = ["label_topo", "label_fundo"]
N_DOBRAS = 3  # janelas expansivas: treina 1/4,2/4,3/4 -> testa o quarto seguinte, media das 3


class ModeloClassificadorSwing:
    def __init__(self):
        self.universo = montar_universo()

    def montar_dataset_completo(self):
        """Reconstroi a serie M15 COMPLETA (nao so os pontos de swing) de
        cada ativo do universo, rotulada 1/0 se aquele candle e um topo ou
        fundo confirmado por detectar_swings() (mesmo fractal N=2 de
        diag_sazonalidade_swings.py, reaproveitado por import)."""
        datasets = []
        for raiz in self.universo:
            df_precos = carregar_precos(raiz)
            if df_precos is None or len(df_precos) < (2 * N_SWING + 1) * 4:
                # precisa de pelo menos ~4x a janela minima pra formar as
                # N_DOBRAS janelas expansivas com algum dado em cada uma
                continue

            pontos = detectar_swings(df_precos, N_SWING)
            tempos_topo = {p["time"] for p in pontos if p["tipo"] == "topo"}
            tempos_fundo = {p["time"] for p in pontos if p["tipo"] == "fundo"}

            # so os candles onde o fractal CONSEGUE decidir (exclui as
            # N_SWING pontas de cada serie, mesma janela usada em
            # detectar_swings) - fora disso o rotulo "nao e swing" nao e
            # confiavel (podia ser swing e o fractal so nao teve candle
            # suficiente pra confirmar)
            df = df_precos.iloc[N_SWING: len(df_precos) - N_SWING].copy()
            df["label_topo"] = df["time"].isin(tempos_topo).astype(int)
            df["label_fundo"] = df["time"].isin(tempos_fundo).astype(int)

            ind_m15 = carregar_indicadores(raiz, "m15", COLUNAS_INDICADOR_M15)
            ind_m5 = carregar_indicadores(raiz, "m5", COLUNAS_INDICADOR_M5)
            if ind_m15 is None:
                continue

            df = df.merge(
                ind_m15.rename(columns={"ifr": "ifr_m15", "atr": "atr_m15", "macd": "macd_m15",
                                         "macd_sinal": "macd_sinal_m15", "macd_hist": "macd_hist_m15"}),
                on="time", how="left",
            )
            if ind_m5 is not None:
                ind_m5_renom = ind_m5.rename(columns={"ifr": "ifr_m5"}).sort_values("time")
                df = pd.merge_asof(df.sort_values("time"), ind_m5_renom, on="time", direction="backward")
            else:
                df["ifr_m5"] = np.nan

            df["minutos_do_dia"] = df["time"].apply(minutos_do_dia)
            df.insert(0, "raiz", raiz)
            datasets.append(df)

        if not datasets:
            return pd.DataFrame()

        completo = pd.concat(datasets, ignore_index=True)
        completo = completo.dropna(subset=FEATURES).reset_index(drop=True)
        return completo

    @staticmethod
    def _fatia_dobra(df_raiz, dobra):
        """Corte por QUANTIL de tempo dentro do proprio ativo (nao data de
        calendario fixa - ativos tem profundidade historica bem diferente).
        dobra 0 -> treina no 1o quarto, testa no 2o; dobra 1 -> treina nos
        2 primeiros quartos, testa no 3o; dobra 2 -> treina nos 3 primeiros,
        testa no 4o (janela expansiva, nunca encolhe o treino)."""
        n = len(df_raiz)
        cortes = [int(n * f) for f in (0.25, 0.50, 0.75, 1.00)]
        fim_treino = cortes[dobra]
        fim_teste = cortes[dobra + 1]
        return df_raiz.iloc[:fim_treino], df_raiz.iloc[fim_treino:fim_teste]

    def _dividir_dobra(self, df, dobra):
        treinos, testes = [], []
        for _, df_raiz in df.groupby("raiz", sort=False):
            df_raiz = df_raiz.sort_values("time")
            if len(df_raiz) < 8:  # precisa de pelo menos 2 candles por quarto
                continue
            tr, te = self._fatia_dobra(df_raiz, dobra)
            if len(tr) == 0 or len(te) == 0:
                continue
            treinos.append(tr)
            testes.append(te)
        if not treinos:
            return None, None
        return pd.concat(treinos, ignore_index=True), pd.concat(testes, ignore_index=True)

    @staticmethod
    def _regra_crua(df_teste, alvo):
        if alvo == "label_topo":
            return (df_teste["macd_m15"] > 0) & (df_teste["ifr_m5"] >= 70)
        return (df_teste["macd_m15"] < 0) & (df_teste["ifr_m5"] <= 30)

    def _treinar_e_avaliar_dobra(self, df_treino, df_teste, alvo):
        X_treino, y_treino = df_treino[FEATURES], df_treino[alvo]
        X_teste, y_teste = df_teste[FEATURES], df_teste[alvo]

        n_pos = int(y_treino.sum())
        if n_pos < 5 or n_pos == len(y_treino):
            return None  # dobra sem exemplo positivo suficiente pra treinar

        scale_pos_weight = (len(y_treino) - n_pos) / n_pos
        modelo = LGBMClassifier(
            n_estimators=300, learning_rate=0.05, max_depth=6, num_leaves=31,
            scale_pos_weight=scale_pos_weight, random_state=42, verbosity=-1,
        )
        modelo.fit(X_treino, y_treino)
        proba_teste = modelo.predict_proba(X_teste)[:, 1]

        if y_teste.sum() == 0 or y_teste.sum() == len(y_teste):
            return None  # AUC/AP indefinido sem as duas classes no teste

        auc = roc_auc_score(y_teste, proba_teste)
        ap = average_precision_score(y_teste, proba_teste)
        prevalencia = float(y_teste.mean())

        regra = self._regra_crua(df_teste, alvo)
        taxa_disparo_regra = float(regra.mean())
        precisao_regra = float(y_teste[regra].mean()) if regra.sum() else None

        precisao_modelo_mesmo_k = None
        if 0 < taxa_disparo_regra < 1:
            limite = np.quantile(proba_teste, 1 - taxa_disparo_regra)
            mascara_modelo = proba_teste >= limite
            if mascara_modelo.sum():
                precisao_modelo_mesmo_k = float(y_teste[mascara_modelo].mean())

        return {
            "n_treino": len(df_treino), "n_teste": len(df_teste),
            "n_positivos_treino": n_pos, "n_positivos_teste": int(y_teste.sum()),
            "prevalencia_teste_pct": round(prevalencia * 100, 3),
            "auc_roc": round(float(auc), 4), "average_precision": round(float(ap), 4),
            "regra_crua_taxa_disparo_pct": round(taxa_disparo_regra * 100, 2),
            "regra_crua_precisao_pct": round(precisao_regra * 100, 2) if precisao_regra is not None else None,
            "modelo_precisao_mesmo_k_pct": (
                round(precisao_modelo_mesmo_k * 100, 2) if precisao_modelo_mesmo_k is not None else None
            ),
        }, modelo

    def executar(self):
        print("[modelo_classificador_swing] montando dataset completo (todos os candles M15, nao so swings)...")
        df = self.montar_dataset_completo()
        print(f"[modelo_classificador_swing] dataset: {len(df)} candles, {df['raiz'].nunique()} ativos")

        relatorio = {"alvos": {}}
        limiares_finais = {}
        for alvo in ALVOS:
            print(f"\n[modelo_classificador_swing] alvo={alvo} - {N_DOBRAS} dobras walk-forward")
            dobras_resultado = []
            for dobra in range(N_DOBRAS):
                df_treino, df_teste = self._dividir_dobra(df, dobra)
                if df_treino is None:
                    print(f"  dobra {dobra}: sem dado suficiente, pulando")
                    continue
                resultado = self._treinar_e_avaliar_dobra(df_treino, df_teste, alvo)
                if resultado is None:
                    print(f"  dobra {dobra}: sem positivo suficiente no treino/teste, pulando")
                    continue
                metricas, _ = resultado
                dobras_resultado.append(metricas)
                print(
                    f"  dobra {dobra}: prevalencia={metricas['prevalencia_teste_pct']}% "
                    f"| regra crua: disparo={metricas['regra_crua_taxa_disparo_pct']}% "
                    f"precisao={metricas['regra_crua_precisao_pct']}% "
                    f"| modelo: AUC={metricas['auc_roc']} AP={metricas['average_precision']} "
                    f"precisao_mesmo_k={metricas['modelo_precisao_mesmo_k_pct']}%"
                )

            agregado = None
            if dobras_resultado:
                agregado = {
                    "auc_roc_medio": round(float(np.mean([d["auc_roc"] for d in dobras_resultado])), 4),
                    "average_precision_medio": round(
                        float(np.mean([d["average_precision"] for d in dobras_resultado])), 4
                    ),
                    "regra_crua_precisao_media_pct": round(
                        float(np.mean([d["regra_crua_precisao_pct"] for d in dobras_resultado
                                       if d["regra_crua_precisao_pct"] is not None])), 2
                    ),
                    "modelo_precisao_mesmo_k_media_pct": round(
                        float(np.mean([d["modelo_precisao_mesmo_k_pct"] for d in dobras_resultado
                                       if d["modelo_precisao_mesmo_k_pct"] is not None])), 2
                    ),
                }
                print(f"  AGREGADO {alvo}: AUC medio={agregado['auc_roc_medio']} "
                      f"| precisao regra crua media={agregado['regra_crua_precisao_media_pct']}% "
                      f"| precisao modelo (mesmo K) media={agregado['modelo_precisao_mesmo_k_media_pct']}%")

            relatorio["alvos"][alvo] = {"dobras": dobras_resultado, "agregado": agregado}

            # taxa de disparo media da regra crua nas dobras - usada so pra
            # calibrar o limiar de score do modelo final (ver abaixo),
            # nunca pra decidir a validacao em si (essa ja fechou acima)
            taxa_disparo_media = None
            if dobras_resultado:
                taxas = [d["regra_crua_taxa_disparo_pct"] for d in dobras_resultado]
                taxa_disparo_media = float(np.mean(taxas)) / 100.0

            # modelo FINAL: treina com TODO o dado (a validacao acima ja
            # mediu o desempenho fora da amostra nas 3 dobras) - e o que
            # fica salvo pra uso futuro (cenario_final_swing.py)
            X_completo, y_completo = df[FEATURES], df[alvo]
            n_pos_completo = int(y_completo.sum())
            if n_pos_completo >= 5:
                scale_pos_weight = (len(y_completo) - n_pos_completo) / n_pos_completo
                modelo_final = LGBMClassifier(
                    n_estimators=300, learning_rate=0.05, max_depth=6, num_leaves=31,
                    scale_pos_weight=scale_pos_weight, random_state=42, verbosity=-1,
                )
                modelo_final.fit(X_completo, y_completo)
                os.makedirs(MODELOS_DIR, exist_ok=True)
                caminho_modelo = os.path.join(MODELOS_DIR, f"classificador_swing_{alvo.replace('label_', '')}.joblib")
                joblib.dump(modelo_final, caminho_modelo)
                importancias = dict(zip(FEATURES, [round(float(x), 1) for x in modelo_final.feature_importances_]))
                relatorio["alvos"][alvo]["importancia_feature_modelo_final"] = importancias
                relatorio["alvos"][alvo]["modelo_final_salvo_em"] = caminho_modelo
                print(f"  modelo final ({alvo}) salvo em {caminho_modelo}")
                print(f"  importancia de feature: {importancias}")

                # limiar de score sugerido: em vez de um "prob >= 0.5" que
                # nao bate com uma classe rara (~15% de prevalencia), pega
                # o percentil do score do modelo final que corresponde a
                # MESMA taxa de disparo media que a regra crua ja tinha
                # (a mesma logica de "mesmo K" usada na validacao acima,
                # agora fixada pra uso em producao por cenario_final_swing.py)
                if taxa_disparo_media and 0 < taxa_disparo_media < 1:
                    scores_completo = modelo_final.predict_proba(X_completo)[:, 1]
                    limiar_sugerido = float(np.quantile(scores_completo, 1 - taxa_disparo_media))
                    relatorio["alvos"][alvo]["limiar_score_sugerido"] = round(limiar_sugerido, 4)
                    relatorio["alvos"][alvo]["limiar_score_taxa_disparo_alvo_pct"] = round(
                        taxa_disparo_media * 100, 2
                    )
                    limiares_finais[alvo.replace("label_", "")] = round(limiar_sugerido, 4)
                    print(f"  limiar de score sugerido ({alvo}): {round(limiar_sugerido, 4)} "
                          f"(dispara em ~{round(taxa_disparo_media * 100, 2)}% dos candles, mesma "
                          f"frequencia media da regra crua nas dobras)")

        os.makedirs(os.path.dirname(SAIDA_JSON_PATH), exist_ok=True)
        with open(SAIDA_JSON_PATH, "w", encoding="utf-8") as f:
            json.dump(relatorio, f, ensure_ascii=False, indent=2)
        print(f"\n[modelo_classificador_swing] relatorio salvo em {SAIDA_JSON_PATH}")

        if limiares_finais:
            with open(SAIDA_LIMIARES_PATH, "w", encoding="utf-8") as f:
                json.dump(limiares_finais, f, ensure_ascii=False, indent=2)
            print(f"[modelo_classificador_swing] limiares salvos em {SAIDA_LIMIARES_PATH} "
                  f"(consumido por cenario_final_swing.py)")

        return relatorio


if __name__ == "__main__":
    ModeloClassificadorSwing().executar()
