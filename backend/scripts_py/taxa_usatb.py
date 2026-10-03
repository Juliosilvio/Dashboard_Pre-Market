"""
Nome do script : taxa_usatb.py
Descricao      : Script exclusivo do UsaTB (T-Bill futures, corretora internacional,
                  familia vencimento_americano — mesmo esqueminha de
                  vigencia do Gasol/Dolar/Indice/Brent/UsaVix/UsaRus).
                  Converte o preco cotado (estilo indice IMM: preco = 100 -
                  taxa, mesma convencao de Eurodollar/SOFR/Fed Funds
                  futures) na taxa de juros implicita anualizada (%), a
                  partir dos historicos D1 e M5 salvos em
                  parquet/historicos/. Le qualquer contrato cujo symbol
                  comece com "UsaTB" (ex: UsaTBDec26), entao sobrevive a
                  virada de vencimento sem precisar de ajuste. High/low se
                  invertem na conversao (preco alto = taxa baixa): a
                  taxa_high vem do low do preco, a taxa_low vem do high.
                  Salva em parquet/calculos/taxaUsaTBD1.parquet e
                  taxaUsaTBM5.parquet — pedido do usuario 2026-09-19, pra
                  usar como lado "juros EUA" no comparativo de inflacao
                  BR x EUA (gasolina), ja que o projeto so tinha curva de
                  juros do lado brasileiro (DI1/DAP/FRC/DDI).
Autor          : Julio Cesar Silvio Campanhola
Criado em      : 2026-09-19
Ultima edicao  : 2026-09-19
Versao         : 1.0.0
Projeto        : dashboard
Historico      : scripts_py/versoes/taxa_usatb.md
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

RAIZ = "UsaTB"
NOME_BROKER = "corretora internacional"


class ConversorTaxaUsaTB:
    """Converte o preco do(s) contrato(s) UsaTB pra taxa de juros implicita (%), D1 ou M5."""

    def __init__(self, historico_path, saida_path):
        self.historico_path = historico_path
        self.saida_path = saida_path
        os.makedirs(os.path.dirname(self.saida_path), exist_ok=True)

    def calcular(self):
        """Le o historico, filtra so o(s) contrato(s) UsaTB (qualquer mes/ano
        de vencimento — symbol comecando com RAIZ) e converte preco -> taxa:
        taxa = 100 - preco. High e low se invertem na conversao (preco alto
        = taxa baixa): taxa_high vem do low do preco, taxa_low vem do high.
        Mantem as colunas de preco originais (open/high/low/close) junto das
        novas colunas de taxa, pra auditoria/conferencia."""
        df = pd.read_parquet(
            self.historico_path,
            columns=["broker", "symbol", "timeframe", "time", "open", "high", "low", "close"],
        )
        df = df[(df["broker"] == NOME_BROKER) & (df["symbol"].str.startswith(RAIZ))].copy()
        if df.empty:
            return df

        df["taxa_open"] = 100 - df["open"]
        df["taxa_high"] = 100 - df["low"]
        df["taxa_low"] = 100 - df["high"]
        df["taxa_close"] = 100 - df["close"]

        # gravacao final: mais recente primeiro, por contrato (mesma
        # convencao de retorno.py)
        df = df.sort_values(["symbol", "time"], ascending=[True, False]).reset_index(drop=True)
        return df

    def executar(self):
        df = self.calcular()
        if df.empty:
            print(f"[{RAIZ}] nenhum candle encontrado em {os.path.basename(self.historico_path)} — nada a converter")
            return df
        df.to_parquet(self.saida_path, index=False)
        contratos = sorted(df["symbol"].unique())
        print(f"[{RAIZ}] salvo: {os.path.abspath(self.saida_path)} "
              f"({len(df)} candles, contrato(s): {contratos})")
        return df


if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.abspath(__file__))
    historicos = os.path.join(base_dir, "..", "parquet", "historicos")
    calculos = os.path.join(base_dir, "..", "parquet", "calculos")

    ConversorTaxaUsaTB(
        os.path.join(historicos, "historico_d1.parquet"),
        os.path.join(calculos, "taxaUsaTBD1.parquet"),
    ).executar()

    ConversorTaxaUsaTB(
        os.path.join(historicos, "historico_m5.parquet"),
        os.path.join(calculos, "taxaUsaTBM5.parquet"),
    ).executar()
