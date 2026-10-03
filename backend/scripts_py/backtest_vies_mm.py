"""
Nome do script : backtest_vies_mm.py
Descricao      : Experimento pedido pelo usuario 2026-09-21, EM CIMA do
                  backtest_vies_direcional.py (nao mexe em producao) — testa
                  duas mudancas na regra do vies direcional antes de decidir
                  se valem a pena:

                  1) Troca o voto por ativo/TF: em vez do sinal do
                     histograma MACD, usa o CRUZAMENTO DE MEDIAS MOVEIS
                     longas (SMA50 x SMA200 do PRECO, mesmos periodos em
                     todo TF — H1/H4/D1): preco/MA rapida ACIMA da MA lenta
                     = voto de alta; abaixo = voto de baixa. Decisao
                     tecnica registrada em texto (nao no codigo): rejeitei
                     a opcao de projetar a inclinacao das duas medias pra
                     "prever" um preco/data de cruzamento futuro — isso e
                     extrapolacao linear de indicador defasado, sem
                     embasamento estatistico solido, e o backtest anterior
                     ja mostrou que a regra mais simples (MACD) nao tem
                     vantagem nenhuma; empilhar uma projecao mais fraca em
                     cima so pioraria. Fica so o ESTADO do cruzamento
                     (acima/abaixo), com o IFR confirmando exatamente como
                     no MACD (peso cheio se concorda, metade se discorda).

                  2) Restringe o universo aos TOP_N ativos de maior
                     correlacao ABSOLUTA (indice ou dolar) em vez dos ~28
                     inteiros — motivo do usuario: ativo fraco (0,05-0,15)
                     dilui o placar dos ativos que realmente importam.

                  Mesma metodologia do backtest_vies_direcional.py
                  (avaliacao diaria na data D1 de Indice, retorno
                  close-to-close do dia seguinte, mesma limitacao de usar a
                  correlacao ATUAL fixa pro periodo inteiro — ver docstring
                  de la pro raciocinio completo).
Autor          : Julio Cesar Silvio Campanhola
Criado em      : 2026-09-21
Ultima edicao  : 2026-09-21
Versao         : 1.0.0
Projeto        : dashboard
Historico      : scripts_py/versoes/backtest_vies_mm.md
"""

import importlib
import os

try:
    pd = importlib.import_module("pandas")
except ImportError as exc:
    raise ImportError("A dependencia pandas nao esta instalada.") from exc
try:
    np = importlib.import_module("numpy")
except ImportError as exc:
    raise ImportError("A dependencia numpy nao esta instalada.") from exc

from vies_direcional import MotorViesDirecional, TIMEFRAMES_VIES, TF_PESOS, LIMIAR_NEUTRO, SYMBOL_INDICE, SYMBOL_DOLAR

PERIODO_RAPIDA = 50
PERIODO_LENTA = 200
TOP_N = 10


class BacktestViesMM:
    def __init__(self, base_dir=None, top_n=TOP_N):
        self.motor = MotorViesDirecional(base_dir)
        self.mtf_dir = self.motor.mtf_dir
        self.top_n = top_n

    def _universo_top_n(self):
        universo = self.motor._montar_universo()
        peso_lookup = self.motor._ler_peso()
        candidatos = []
        for alvo in universo:
            row = peso_lookup.get((alvo["broker"], alvo["ticker"]))
            if row is None:
                continue
            cw = row["correlacao_indice"]
            cd = row["correlacao_dolar"]
            peso_max = max(abs(cw) if pd.notna(cw) else 0.0, abs(cd) if pd.notna(cd) else 0.0)
            candidatos.append((peso_max, alvo, row))
        candidatos.sort(key=lambda x: x[0], reverse=True)
        selecionados = candidatos[: self.top_n]
        print(f"[backtest-mm] top {len(selecionados)} ativos por correlacao absoluta:")
        for peso_max, alvo, row in selecionados:
            print(f"    {alvo['raiz']:10s} {alvo['ticker']:14s} peso={peso_max:.3f} "
                  f"corr_indice={row['correlacao_indice']:.3f} corr_dolar={row['correlacao_dolar']:.3f}")
        return [(alvo, row) for _, alvo, row in selecionados]

    def _padronizar_time(self, serie_ou_df, coluna="time"):
        if isinstance(serie_ou_df, pd.DataFrame):
            serie_ou_df = serie_ou_df.copy()
            serie_ou_df[coluna] = pd.to_datetime(serie_ou_df[coluna], utc=True).astype("datetime64[ns, UTC]")
            return serie_ou_df
        return pd.to_datetime(serie_ou_df, utc=True).astype("datetime64[ns, UTC]")

    def _serie_voto_mm_tf(self, alvo, timeframe, timeline):
        """Voto por cruzamento de SMA50/SMA200 do preco, confirmado pelo
        IFR do mesmo TF (mesma logica de peso cheio/metade do MACD)."""
        caminho_preco = os.path.join(self.mtf_dir, *alvo["pasta_rel"].split("/"), f"{timeframe}.parquet")
        if not os.path.exists(caminho_preco):
            return pd.Series(np.nan, index=timeline)

        dfp = pd.read_parquet(caminho_preco, columns=["time", "close"]).sort_values("time").reset_index(drop=True)
        if len(dfp) < PERIODO_LENTA:
            return pd.Series(np.nan, index=timeline)

        dfp["ma_rapida"] = dfp["close"].rolling(PERIODO_RAPIDA).mean()
        dfp["ma_lenta"] = dfp["close"].rolling(PERIODO_LENTA).mean()
        dfp = dfp.dropna(subset=["ma_rapida", "ma_lenta"]).reset_index(drop=True)
        if dfp.empty:
            return pd.Series(np.nan, index=timeline)

        dfp["sinal"] = np.where(dfp["ma_rapida"] > dfp["ma_lenta"], 1.0, -1.0)

        caminho_ind = self.motor._caminho_indicador(alvo, timeframe)
        if os.path.exists(caminho_ind):
            dfi = pd.read_parquet(caminho_ind, columns=["time", "ifr"]).sort_values("time")
            dfi = self._padronizar_time(dfi)
        else:
            dfi = pd.DataFrame({"time": pd.Series(dtype="datetime64[ns, UTC]"), "ifr": pd.Series(dtype=float)})

        dfp = self._padronizar_time(dfp)
        combinado = pd.merge_asof(dfp[["time", "sinal"]], dfi, on="time", direction="backward")

        concorda = ((combinado["sinal"] > 0) & (combinado["ifr"] > 50)) | (
            (combinado["sinal"] < 0) & (combinado["ifr"] < 50)
        )
        # sem IFR ainda calculado pra essa data: nao penaliza (peso 1.0), so pesa
        # metade quando o IFR existe E discorda
        peso_confirmacao = np.where(combinado["ifr"].isna(), 1.0, np.where(concorda, 1.0, 0.5))
        combinado["voto"] = combinado["sinal"] * peso_confirmacao

        esquerda = pd.DataFrame({"time": self._padronizar_time(timeline)})
        alinhado = pd.merge_asof(esquerda, combinado[["time", "voto"]], on="time", direction="backward")
        return pd.Series(alinhado["voto"].to_numpy(), index=timeline)

    def _serie_voto_ativo(self, alvo, timeline):
        soma = pd.Series(0.0, index=timeline)
        soma_pesos = pd.Series(0.0, index=timeline)
        for timeframe in TIMEFRAMES_VIES:
            serie = self._serie_voto_mm_tf(alvo, timeframe, timeline)
            peso_tf = TF_PESOS[timeframe]
            disponivel = serie.notna()
            soma = soma + serie.fillna(0.0) * peso_tf * disponivel
            soma_pesos = soma_pesos + peso_tf * disponivel
        with np.errstate(invalid="ignore", divide="ignore"):
            resultado = soma / soma_pesos
        resultado[soma_pesos == 0] = np.nan
        return resultado

    def calcular_placar_historico(self):
        selecionados = self._universo_top_n()

        preco_indice = pd.read_parquet(os.path.join(self.mtf_dir, "Indice", "d1.parquet"), columns=["time"])
        timeline = preco_indice.sort_values("time")["time"].reset_index(drop=True)

        soma_indice, peso_indice = pd.Series(0.0, index=timeline), pd.Series(0.0, index=timeline)
        soma_dolar, peso_dolar = pd.Series(0.0, index=timeline), pd.Series(0.0, index=timeline)

        for alvo, row in selecionados:
            voto_serie = self._serie_voto_ativo(alvo, timeline)
            if voto_serie.isna().all():
                continue
            disponivel = voto_serie.notna()
            corr_indice, corr_dolar = row["correlacao_indice"], row["correlacao_dolar"]
            if pd.notna(corr_indice):
                soma_indice = soma_indice + voto_serie.fillna(0.0) * corr_indice * disponivel
                peso_indice = peso_indice + abs(corr_indice) * disponivel
            if pd.notna(corr_dolar):
                soma_dolar = soma_dolar + voto_serie.fillna(0.0) * corr_dolar * disponivel
                peso_dolar = peso_dolar + abs(corr_dolar) * disponivel

        with np.errstate(invalid="ignore", divide="ignore"):
            score_indice = (soma_indice / peso_indice).where(peso_indice > 0, np.nan)
            score_dolar = (soma_dolar / peso_dolar).where(peso_dolar > 0, np.nan)

        def classificar(score):
            return np.select([score > LIMIAR_NEUTRO, score < -LIMIAR_NEUTRO], ["alta", "baixa"], default="neutro")

        return pd.DataFrame({
            "time": timeline,
            "score_indice": score_indice.to_numpy(),
            "vies_indice": np.where(score_indice.isna(), None, classificar(score_indice.fillna(0))),
            "score_dolar": score_dolar.to_numpy(),
            "vies_dolar": np.where(score_dolar.isna(), None, classificar(score_dolar.fillna(0))),
        })

    def _retorno_seguinte(self, symbol):
        caminho = os.path.join(self.mtf_dir, symbol, "d1.parquet")
        df = pd.read_parquet(caminho, columns=["time", "close"]).sort_values("time").reset_index(drop=True)
        df["retorno_seguinte"] = df["close"].shift(-1) / df["close"] - 1.0
        return df[["time", "retorno_seguinte"]]

    def rodar(self):
        placar = self.calcular_placar_historico()
        ret_indice = self._retorno_seguinte(SYMBOL_INDICE).rename(columns={"retorno_seguinte": "retorno_indice"})
        ret_dolar = self._retorno_seguinte(SYMBOL_DOLAR).rename(columns={"retorno_seguinte": "retorno_dolar"})
        completo = placar.merge(ret_indice, on="time", how="left").merge(ret_dolar, on="time", how="left")
        completo = completo.dropna(subset=["retorno_indice", "retorno_dolar"])

        relatorio = {}
        for ativo, col_vies, col_ret in [("Indice", "vies_indice", "retorno_indice"), ("Dolar", "vies_dolar", "retorno_dolar")]:
            sub = completo[completo[col_vies].isin(["alta", "baixa"])].copy()
            sub["acertou"] = ((sub[col_vies] == "alta") & (sub[col_ret] > 0)) | (
                (sub[col_vies] == "baixa") & (sub[col_ret] < 0)
            )
            n_total = len(sub)
            n_alta = int((sub[col_vies] == "alta").sum())
            n_baixa = int((sub[col_vies] == "baixa").sum())
            relatorio[ativo] = {
                "dias_totais": len(completo),
                "dias_neutro": int((completo[col_vies] == "neutro").sum()),
                "dias_com_vies": n_total,
                "acertos": int(sub["acertou"].sum()),
                "taxa_acerto_geral": sub["acertou"].mean() if n_total else float("nan"),
                "dias_alta": n_alta,
                "taxa_acerto_alta": sub.loc[sub[col_vies] == "alta", "acertou"].mean() if n_alta else float("nan"),
                "dias_baixa": n_baixa,
                "taxa_acerto_baixa": sub.loc[sub[col_vies] == "baixa", "acertou"].mean() if n_baixa else float("nan"),
            }
        return relatorio, completo


if __name__ == "__main__":
    relatorio, completo = BacktestViesMM().rodar()
    for ativo, stats in relatorio.items():
        print(f"\n=== {ativo} ===")
        for chave, valor in stats.items():
            print(f"  {chave}: {valor}")
