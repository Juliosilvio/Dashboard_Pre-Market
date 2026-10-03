"""
Nome do script : flat_mtf.py
Descricao      : Deriva historico_d1.parquet e historico_m5.parquet (o
                  formato "achatado", uma tabela so com broker/symbol/
                  timeframe/time/OHLCV) a partir da pasta de estudo MTF —
                  em vez de coletar de novo do MT5.

                  Motivo de existir (consolidacao pedida pelo usuario
                  2026-09-21: "isso e o que precisamos: serie historica em
                  MTF e preco em tempo real, de forma centralizada, pra nao
                  errar mais"). Antes desta mudanca, o projeto tinha DOIS
                  pipelines de coleta independentes buscando D1/M5 do MESMO
                  MT5, pros MESMOS ativos: nac.py/nac_m5.py (corretora nacional) e
                  int.py/int_m5.py (corretora internacional) alimentavam
                  historico_d1.parquet/historico_m5.parquet; historico.py
                  buscava tudo de novo (D1/M5 inclusive) pra dentro da MTF.
                  Isso ja causou uma divergencia real: a correcao do
                  alinhar_d1.py so tinha sido aplicada numa das duas copias
                  (ver changelog dele, 2.0.0). Solucao: historico.py vira a
                  UNICA coleta (MTF), e este script (flat_mtf.py) DERIVA o
                  formato achatado a partir dela — retorno.py e
                  taxa_usatb.py (os dois unicos consumidores diretos de
                  historico_d1/m5.parquet) continuam lendo o MESMO caminho,
                  MESMO formato, sem nenhuma mudanca — so quem produz o
                  arquivo que muda.

                  Usa historico.ColetorHistoricoMTF.montar_alvos() (a MESMA
                  lista de alvos que o historico.py usa pra coletar) pra
                  saber, de cada ativo/vencimento: qual broker, qual ticker
                  bruto do MT5 (ex: IndiceOct26, nao so "Indice") e em qual
                  pasta da MTF estao os parquets dele. Pra cada alvo, le
                  d1.parquet e m5.parquet (se existirem), marca com
                  broker/symbol=ticker/timeframe e empilha tudo — reproduz
                  exatamente o schema que nac.py/int.py geravam
                  (broker, symbol, timeframe, time, open, high, low, close,
                  tick_volume, spread, real_volume), simbolo = ticker bruto
                  (nao a raiz) pra manter o mesmo comportamento de sempre
                  tratar cada vencimento como uma serie separada (evita
                  misturar nivel de preco de contratos diferentes na hora
                  da rolagem — mesma logica que ja existia).

                  Roda DEPOIS de historico.py e alinhar_d1.py (que corrige o
                  D1 da corretora internacional DENTRO da MTF antes deste script ler) —
                  ver main.py.
Autor          : Julio Cesar Silvio Campanhola
Criado em      : 2026-09-21
Ultima edicao  : 2026-09-21
Versao         : 1.0.0
Projeto        : dashboard
Historico      : scripts_py/versoes/flat_mtf.md
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

from historico import ColetorHistoricoMTF

TIMEFRAMES_FLAT = ["d1", "m5"]  # nomes de arquivo na MTF, minusculo


class DerivadorFlatMTF:
    """Deriva historico_d1.parquet/historico_m5.parquet (formato achatado,
    broker+symbol+timeframe+time+OHLCV) a partir dos parquets ja coletados
    na pasta de estudo MTF — nao conecta no MT5."""

    def __init__(self, base_dir=None):
        self.coletor = ColetorHistoricoMTF(base_dir=base_dir)
        self.mtf_dir = self.coletor.mtf_dir
        historicos_dir = os.path.dirname(self.mtf_dir)
        self.saida = {
            "d1": os.path.join(historicos_dir, "historico_d1.parquet"),
            "m5": os.path.join(historicos_dir, "historico_m5.parquet"),
        }

    def _ler_alvo(self, alvo, tf_nome):
        pasta = os.path.join(self.mtf_dir, *alvo["pasta_rel"].split("/"))
        caminho = os.path.join(pasta, f"{tf_nome}.parquet")
        if not os.path.exists(caminho):
            return None
        df = pd.read_parquet(caminho)
        if df.empty:
            return None
        df = df.copy()
        df["broker"] = alvo["broker"]
        df["symbol"] = alvo["ticker"]
        df["timeframe"] = tf_nome.upper()
        return df

    def derivar(self, tf_nome, alvos):
        partes = []
        for alvo in alvos:
            df = self._ler_alvo(alvo, tf_nome)
            if df is not None:
                partes.append(df)

        if not partes:
            return pd.DataFrame(columns=["broker", "symbol", "timeframe", "time",
                                          "open", "high", "low", "close",
                                          "tick_volume", "spread", "real_volume"])

        df_final = pd.concat(partes, ignore_index=True)
        colunas = ["broker", "symbol", "timeframe", "time", "open", "high", "low",
                   "close", "tick_volume", "spread", "real_volume"]
        colunas = [c for c in colunas if c in df_final.columns]
        df_final = df_final[colunas].sort_values(["broker", "symbol", "time"]).reset_index(drop=True)
        return df_final

    def executar(self):
        self.coletor.carregar_config()
        alvos = self.coletor.montar_alvos()

        for tf_nome in TIMEFRAMES_FLAT:
            df = self.derivar(tf_nome, alvos)
            df.to_parquet(self.saida[tf_nome], index=False)
            print(f"[flat_mtf] {tf_nome.upper()}: {os.path.abspath(self.saida[tf_nome])} "
                  f"({len(df)} candles, {df['symbol'].nunique() if not df.empty else 0} simbolos)")


if __name__ == "__main__":
    DerivadorFlatMTF().executar()
