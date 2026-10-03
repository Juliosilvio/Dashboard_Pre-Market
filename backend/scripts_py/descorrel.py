"""
Nome do script : descorrel.py
Descricao      : Calcula a correlacao rolante (janela deslizante) do retorno
                  de cada ativo do universo contra o retorno de referencia do
                  Indice e do Dolar (contrato corrente, corretora nacional), a
                  partir de parquet/calculos/retornoD1.parquet e
                  retornoM5.parquet. Pra cada ativo, pega o valor mais recente
                  da correlacao rolante contra INDICE e contra DOLAR e mantem so
                  quem bateu o limiar NEGATIVO (-LIMIAR_CORRELACAO) em pelo
                  menos uma das duas — candidatos a "andar contra" INDICE/DOLAR
                  (decorrelacao). Correlacao positiva fica no correl.py.
                  Ativos INDICE/DOLAR (qualquer variante) ficam de fora do
                  universo analisado — sao o alvo, nao candidato a driver.
                  Salva em parquet/calculos/descorrelacaoD1.parquet e
                  descorrelacaoM5.parquet.
Autor          : Julio Cesar Silvio Campanhola
Criado em      : 2026-09-13
Ultima edicao  : 2026-09-20
Versao         : 1.1.0
Projeto        : dashboard
Historico      : scripts_py/versoes/descorrel.md
"""

import importlib
import json
import os

try:
    pd = importlib.import_module("pandas")
except ImportError as exc:
    raise ImportError(
        "A dependencia pandas nao esta instalada. "
        "Instale-a com: pip install pandas pyarrow"
    ) from exc


BROKER_REF = "corretora nacional"
SYMBOL_INDICE = "Indice"
SYMBOL_DOLAR = "Dolar"
LIMIAR_CORRELACAO = 0.6


class AnalisadorDescorrelacao:
    """Correlacao rolante do retorno de cada ativo contra Indice e Dolar — mantem so a negativa."""

    def __init__(self, retorno_path, saida_path, janela):
        self.retorno_path = retorno_path
        self.saida_path = saida_path
        self.janela = janela
        os.makedirs(os.path.dirname(self.saida_path), exist_ok=True)

    def _serie_referencia(self, df, symbol, rotulo):
        """Serie de retorno de um simbolo de referencia (Indice ou Dolar), pronta pra merge por time."""
        ref = df[(df["broker"] == BROKER_REF) & (df["symbol"] == symbol)][["time", "retorno"]]
        return ref.rename(columns={"retorno": rotulo}).sort_values("time")

    def calcular(self):
        """Correlacao rolante no ultimo ponto disponivel de cada ativo — um valor por ativo."""
        df = pd.read_parquet(self.retorno_path, columns=["broker", "symbol", "time", "retorno"])

        ref_indice = self._serie_referencia(df, SYMBOL_INDICE, "ret_indice")
        ref_dolar = self._serie_referencia(df, SYMBOL_DOLAR, "ret_dolar")

        # INDICE/DOLAR sao o alvo, nao entram como candidato a driver de si mesmos
        universo = df[~df["symbol"].str.upper().str.match(r"^(INDICE|DOLAR)")]

        linhas = []
        for (broker, symbol), grupo in universo.groupby(["broker", "symbol"]):
            # obs: nao precisa mais corrigir fuso aqui - historico_d1/m5.parquet
            # ja nascem com o horario correto (corrigido na coleta, ver
            # scripts_py/fuso_horario.py)
            base = grupo[["time", "retorno"]].sort_values("time").copy()
            base = base.merge(ref_indice, on="time", how="inner").merge(ref_dolar, on="time", how="inner")
            if len(base) < self.janela:
                continue

            base["correlacao_indice"] = base["retorno"].rolling(self.janela).corr(base["ret_indice"])
            base["correlacao_dolar"] = base["retorno"].rolling(self.janela).corr(base["ret_dolar"])
            ultimo = base.dropna(subset=["correlacao_indice", "correlacao_dolar"], how="all").tail(1)
            if ultimo.empty:
                continue

            linhas.append({
                "broker": broker,
                "symbol": symbol,
                "time": ultimo["time"].iloc[0],
                "correlacao_indice": ultimo["correlacao_indice"].iloc[0],
                "correlacao_dolar": ultimo["correlacao_dolar"].iloc[0],
                "n_pontos": len(base),
            })

        saida = pd.DataFrame(linhas)
        if saida.empty:
            return saida

        negativos = saida[
            (saida["correlacao_indice"] <= -LIMIAR_CORRELACAO)
            | (saida["correlacao_dolar"] <= -LIMIAR_CORRELACAO)
        ].copy()
        negativos["forca"] = negativos[["correlacao_indice", "correlacao_dolar"]].min(axis=1)
        negativos = negativos.sort_values("forca", ascending=True).drop(columns="forca").reset_index(drop=True)
        return negativos

    def executar(self):
        df = self.calcular()
        df.to_parquet(self.saida_path, index=False)
        print(f"Salvo: {os.path.abspath(self.saida_path)} "
              f"({len(df)} ativos descorrelacionados, janela={self.janela})")
        return df


if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.abspath(__file__))
    calculos = os.path.join(base_dir, "..", "parquet", "calculos")

    AnalisadorDescorrelacao(
        os.path.join(calculos, "retornoD1.parquet"),
        os.path.join(calculos, "descorrelacaoD1.parquet"),
        janela=20,
    ).executar()

    AnalisadorDescorrelacao(
        os.path.join(calculos, "retornoM5.parquet"),
        os.path.join(calculos, "descorrelacaoM5.parquet"),
        janela=100,
    ).executar()
