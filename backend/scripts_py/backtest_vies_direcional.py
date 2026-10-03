"""
Nome do script : backtest_vies_direcional.py
Descricao      : Backtest do motor vies_direcional.py contra a serie
                  historica completa da MTF — responde a pergunta do
                  usuario "voce analisou a serie historica dos indicadores
                  pra chegar nessa conclusao?": nao, o vies_direcional.py
                  em producao so olha o valor MAIS RECENTE de cada
                  indicador (e assim que ele tem que rodar ao vivo). Este
                  script aqui e o oposto: anda a serie historica INTEIRA,
                  reproduz o mesmo calculo de voto/combinacao de TF/peso de
                  correlacao em CADA dia do passado, e compara com o que
                  Indice/Dolar realmente fizeram no dia seguinte, pra medir se
                  a regra teria acertado a direcao.

                  Limitacao assumida, documentada de proposito: usa a
                  correlacao ATUAL (pesoMercadoD1.parquet — um snapshot de
                  hoje) FIXA pro periodo inteiro do backtest, porque
                  correl.py so guarda o ultimo ponto da correlacao rolante,
                  nao a serie historica dela. Ou seja: isto testa "a regra
                  de voto por ativo + combinacao de TF teria funcionado,
                  assumindo os pesos de correlacao de hoje" — nao "o
                  sistema inteiro, incluindo a correlacao mudando dia a
                  dia, teria funcionado". Pra testar isso ultimo seria
                  preciso o correl.py guardar a serie rolante inteira, nao
                  so o ultimo ponto — mudanca maior, fora do escopo de
                  hoje.

                  Avaliacao: uma vez por dia, na data de cada candle D1 de
                  Indice (linha do tempo de referencia). Vies avaliado com o
                  indicador mais recente disponivel (as-of, sem espiar o
                  futuro) de cada TF (H1/H4/D1) de cada ativo do universo
                  naquela data — mesmo voto/combinacao/formula do
                  vies_direcional.py (reaproveitado por import, pra nao
                  duplicar/divergir regra). Retorno seguinte: fechamento
                  D1 do dia seguinte vs fechamento do dia da avaliacao, pra
                  Indice e Dolar separadamente. Acerto = sinal do retorno
                  bateu com o vies (alta->retorno positivo,
                  baixa->retorno negativo); dias com vies neutro ficam de
                  fora da taxa de acerto (o sistema nao apostou nada).
Autor          : Julio Cesar Silvio Campanhola
Criado em      : 2026-09-21
Ultima edicao  : 2026-09-21
Versao         : 1.0.1
Projeto        : dashboard
Historico      : scripts_py/versoes/backtest_vies_direcional.md
"""

import importlib
import os

try:
    pd = importlib.import_module("pandas")
except ImportError as exc:
    raise ImportError(
        "A dependencia pandas nao esta instalada. "
        "Instale-a com: pip install pandas pyarrow"
    ) from exc
try:
    np = importlib.import_module("numpy")
except ImportError as exc:
    raise ImportError(
        "A dependencia numpy nao esta instalada. "
        "Instale-a com: pip install numpy"
    ) from exc

from vies_direcional import (
    MotorViesDirecional,
    TIMEFRAMES_VIES,
    TF_PESOS,
    LIMIAR_NEUTRO,
    SYMBOL_INDICE,
    SYMBOL_DOLAR,
)


class BacktestViesDirecional:
    def __init__(self, base_dir=None):
        self.motor = MotorViesDirecional(base_dir)
        self.mtf_dir = self.motor.mtf_dir

    # ---------- serie de voto vetorizada por ativo/TF ----------

    def _serie_voto_tf(self, alvo, timeframe, timeline):
        """Le a serie historica INTEIRA de ifr/macd_hist de um ativo num TF,
        calcula o voto candle a candle (vetorizado) e alinha (as-of, sem
        espiar o futuro) na linha do tempo de avaliacao (datas D1 de
        Indice)."""
        caminho = self.motor._caminho_indicador(alvo, timeframe)
        if not os.path.exists(caminho):
            return pd.Series(np.nan, index=timeline)

        df = pd.read_parquet(caminho, columns=["time", "ifr", "macd_hist"]).sort_values("time")
        df = df.dropna(subset=["ifr", "macd_hist"])
        if df.empty:
            return pd.Series(np.nan, index=timeline)

        sinal = np.sign(df["macd_hist"].to_numpy())
        ifr = df["ifr"].to_numpy()
        concorda = ((sinal > 0) & (ifr > 50)) | ((sinal < 0) & (ifr < 50))
        peso_confirmacao = np.where(concorda, 1.0, 0.5)
        df = df.assign(voto=sinal * peso_confirmacao)

        # merge_asof exige o MESMO dtype exato nas duas colunas de merge -
        # parquets de ativos/TFs diferentes podem ter vindo do MT5 com unit
        # de datetime64 diferente (us/s/ns) dependendo da origem/momento da
        # coleta. Normaliza os dois lados pra ns antes de comparar (mesmo
        # fix ja aplicado no curva_juros.py pro mesmo tipo de erro).
        timeline_ns = pd.to_datetime(timeline, utc=True).astype("datetime64[ns, UTC]")
        df_time_ns = pd.to_datetime(df["time"], utc=True).astype("datetime64[ns, UTC]")
        alinhado = pd.merge_asof(
            pd.DataFrame({"time": timeline_ns}).sort_values("time"),
            df[["voto"]].assign(time=df_time_ns.to_numpy())[["time", "voto"]],
            on="time",
            direction="backward",  # so pega indicador ja fechado ate aquela data, nunca do futuro
        )
        return pd.Series(alinhado["voto"].to_numpy(), index=timeline)

    def _serie_voto_ativo(self, alvo, timeline):
        """Combina H1/H4/D1 do ativo (media ponderada D1>H4>H1) em cada
        data da linha do tempo — mesmos pesos do vies_direcional.py ao
        vivo. NaN nas datas em que nenhum TF tinha indicador ainda."""
        soma = pd.Series(0.0, index=timeline)
        soma_pesos = pd.Series(0.0, index=timeline)
        for timeframe in TIMEFRAMES_VIES:
            serie = self._serie_voto_tf(alvo, timeframe, timeline)
            peso_tf = TF_PESOS[timeframe]
            disponivel = serie.notna()
            soma = soma + serie.fillna(0.0) * peso_tf * disponivel
            soma_pesos = soma_pesos + peso_tf * disponivel
        with np.errstate(invalid="ignore", divide="ignore"):
            resultado = soma / soma_pesos
        resultado[soma_pesos == 0] = np.nan
        return resultado

    # ---------- placar historico (INDICE e DOLAR) ----------

    def calcular_placar_historico(self):
        """Devolve um DataFrame indexado pela data (D1 de Indice) com
        colunas score_indice, vies_indice, score_dolar, vies_dolar — o placar que o
        vies_direcional.py teria mostrado NAQUELE dia, se ja existisse."""
        universo = self.motor._montar_universo()
        peso_lookup = self.motor._ler_peso()

        preco_indice = pd.read_parquet(os.path.join(self.mtf_dir, "Indice", "d1.parquet"), columns=["time", "close"])
        timeline = preco_indice.sort_values("time")["time"].reset_index(drop=True)

        soma_indice = pd.Series(0.0, index=timeline)
        peso_indice = pd.Series(0.0, index=timeline)
        soma_dolar = pd.Series(0.0, index=timeline)
        peso_dolar = pd.Series(0.0, index=timeline)

        ativos_usados = 0
        for alvo in universo:
            peso_row = peso_lookup.get((alvo["broker"], alvo["ticker"]))
            if peso_row is None:
                continue
            corr_indice = peso_row["correlacao_indice"]
            corr_dolar = peso_row["correlacao_dolar"]
            if pd.isna(corr_indice) and pd.isna(corr_dolar):
                continue

            voto_serie = self._serie_voto_ativo(alvo, timeline)
            if voto_serie.isna().all():
                continue
            ativos_usados += 1

            disponivel = voto_serie.notna()
            if pd.notna(corr_indice):
                soma_indice = soma_indice + voto_serie.fillna(0.0) * corr_indice * disponivel
                peso_indice = peso_indice + abs(corr_indice) * disponivel
            if pd.notna(corr_dolar):
                soma_dolar = soma_dolar + voto_serie.fillna(0.0) * corr_dolar * disponivel
                peso_dolar = peso_dolar + abs(corr_dolar) * disponivel

        with np.errstate(invalid="ignore", divide="ignore"):
            score_indice = (soma_indice / peso_indice).where(peso_indice > 0, np.nan)
            score_dolar = (soma_dolar / peso_dolar).where(peso_dolar > 0, np.nan)

        def classificar_serie(score):
            return np.select(
                [score > LIMIAR_NEUTRO, score < -LIMIAR_NEUTRO],
                ["alta", "baixa"],
                default="neutro",
            )

        placar = pd.DataFrame({
            "time": timeline,
            "score_indice": score_indice.to_numpy(),
            "vies_indice": np.where(score_indice.isna(), None, classificar_serie(score_indice.fillna(0))),
            "score_dolar": score_dolar.to_numpy(),
            "vies_dolar": np.where(score_dolar.isna(), None, classificar_serie(score_dolar.fillna(0))),
        })
        print(f"[backtest] {ativos_usados}/{len(universo)} ativos do universo contribuiram em pelo menos uma data")
        return placar

    # ---------- comparacao com o retorno real ----------

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
        completo = completo.dropna(subset=["retorno_indice", "retorno_dolar"])  # ultimo dia nao tem "dia seguinte"

        relatorio = {}
        for ativo, col_vies, col_ret in [("Indice", "vies_indice", "retorno_indice"), ("Dolar", "vies_dolar", "retorno_dolar")]:
            sub = completo[completo[col_vies].isin(["alta", "baixa"])].copy()
            sub["acertou"] = (
                ((sub[col_vies] == "alta") & (sub[col_ret] > 0))
                | ((sub[col_vies] == "baixa") & (sub[col_ret] < 0))
            )
            n_total = len(sub)
            n_acertos = int(sub["acertou"].sum())
            taxa = n_acertos / n_total if n_total else float("nan")

            n_alta = int((sub[col_vies] == "alta").sum())
            n_baixa = int((sub[col_vies] == "baixa").sum())
            taxa_alta = sub.loc[sub[col_vies] == "alta", "acertou"].mean() if n_alta else float("nan")
            taxa_baixa = sub.loc[sub[col_vies] == "baixa", "acertou"].mean() if n_baixa else float("nan")

            n_neutro = int((completo[col_vies] == "neutro").sum())

            relatorio[ativo] = {
                "dias_totais": len(completo),
                "dias_neutro": n_neutro,
                "dias_com_vies": n_total,
                "acertos": n_acertos,
                "taxa_acerto_geral": taxa,
                "dias_alta": n_alta,
                "taxa_acerto_alta": taxa_alta,
                "dias_baixa": n_baixa,
                "taxa_acerto_baixa": taxa_baixa,
            }

        return relatorio, completo


if __name__ == "__main__":
    relatorio, completo = BacktestViesDirecional().rodar()
    for ativo, stats in relatorio.items():
        print(f"\n=== {ativo} ===")
        for chave, valor in stats.items():
            print(f"  {chave}: {valor}")
