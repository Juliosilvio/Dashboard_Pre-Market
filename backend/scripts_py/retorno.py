"""
Nome do script : retorno.py
Descricao      : Calcula o retorno LOGARITMICO (LN, natural — ln(close /
                  close_anterior), nao mais percentual simples) entre o
                  candle atual e o imediatamente anterior, por ativo, a
                  partir dos historicos D1 e M5 salvos em
                  parquet/historicos/, e salva em
                  parquet/calculos/retornoD1.parquet e retornoM5.parquet.
                  O calculo interno sempre roda em ordem cronologica
                  crescente (cada candle comparado so com o que veio
                  imediatamente antes, nunca com um dado antigo qualquer);
                  a gravacao final sai com o mais recente primeiro, por
                  ativo. Base pra qualquer correlacao/descorrelacao futura —
                  sempre em cima de retorno, nunca de preco bruto.

                  Correcao do usuario (2026-09-21): trocado de retorno
                  percentual simples (pct_change) pra retorno logaritmico —
                  padrao em analise quantitativa pra correlacao entre
                  series financeiras (aditivo no tempo, mais simetrico
                  entre alta/baixa, aproxima melhor de normalidade). Todo
                  consumidor (correl.py, descorrel.py, e por consequencia
                  pesoMercadoD1/M5.parquet e o vies_direcional.py) passa a
                  herdar retorno LN automaticamente, sem mudanca propria —
                  eles so leem a coluna "retorno" pronta.
Autor          : Julio Cesar Silvio Campanhola
Criado em      : 2026-09-13
Ultima edicao  : 2026-09-21
Versao         : 2.0.0
Projeto        : dashboard
Historico      : scripts_py/versoes/retorno.md
"""

import importlib
import os

try:
    np = importlib.import_module("numpy")
except ImportError as exc:
    raise ImportError(
        "A dependencia numpy nao esta instalada. "
        "Instale-a com: pip install numpy"
    ) from exc
try:
    pd = importlib.import_module("pandas")
except ImportError as exc:
    raise ImportError(
        "A dependencia pandas nao esta instalada. "
        "Instale-a com: pip install pandas pyarrow"
    ) from exc


class CalculadorRetorno:
    """Calcula o retorno percentual por ativo a partir de um historico D1 ou M5."""

    def __init__(self, historico_path, saida_path):
        self.historico_path = historico_path
        self.saida_path = saida_path
        os.makedirs(os.path.dirname(self.saida_path), exist_ok=True)

    def calcular(self):
        """Le o historico, calcula o retorno LOGARITMICO do close
        (ln(close / close_anterior)) e devolve com o mais recente
        primeiro."""
        df = pd.read_parquet(
            self.historico_path,
            columns=["broker", "symbol", "timeframe", "time", "close"],
        )
        # ordem crescente so pro calculo — cada candle comparado com o
        # imediatamente anterior no tempo, nunca com um dado antigo qualquer
        df = df.sort_values(["broker", "symbol", "time"]).reset_index(drop=True)
        close_anterior = df.groupby(["broker", "symbol"])["close"].shift(1)
        df["retorno"] = np.log(df["close"] / close_anterior)
        # primeira linha de cada ativo nao tem candle anterior pra comparar
        df = df.dropna(subset=["retorno"]).reset_index(drop=True)
        # gravacao final: mais recente primeiro, por ativo
        df = df.sort_values(["broker", "symbol", "time"], ascending=[True, True, False]).reset_index(drop=True)
        return df

    def executar(self):
        df = self.calcular()
        df.to_parquet(self.saida_path, index=False)
        print(f"Salvo: {os.path.abspath(self.saida_path)} "
              f"({len(df)} retornos, {df['symbol'].nunique()} ativos)")
        return df


if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.abspath(__file__))
    historicos = os.path.join(base_dir, "..", "parquet", "historicos")
    calculos = os.path.join(base_dir, "..", "parquet", "calculos")

    CalculadorRetorno(
        os.path.join(historicos, "historico_d1.parquet"),
        os.path.join(calculos, "retornoD1.parquet"),
    ).executar()

    CalculadorRetorno(
        os.path.join(historicos, "historico_m5.parquet"),
        os.path.join(calculos, "retornoM5.parquet"),
    ).executar()
