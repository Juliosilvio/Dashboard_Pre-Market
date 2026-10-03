"""
Nome do script : magnificas.py
Descricao      : Cotacao "atual" + variacao intradiaria das Sete Magnificas
                  (Apple, Microsoft, Alphabet, Amazon, Nvidia, Meta, Tesla)
                  pra grade de cotacoes do frontend — pedido do usuario
                  2026-09-26 ("coloque as 7 magnificas na grade de cotacao
                  tambem, e sua variacao intradiaria"), depois de resolver
                  o mt5stock (ver ExportadorMt5Stock.mq5/historico.py 1.3.0):
                  agora as 100 acoes do Nasdaq-100 (incluindo as 7
                  magnificas) sao coletadas via mt5stock em
                  parquet/historicos/MTF/<raiz>/<tf>.parquet.

                  IMPORTANTE - por que NAO e um "last_magnificas.py" como
                  last_nac.py/last_int.py (conexao MT5 direta, tick a
                  tick): o terminal mt5stock tem um bug de conta/Market
                  Watch que faz symbol_select()/copy_rates_range() falharem
                  via API Python externa (ver docstring do
                  ExportadorMt5Stock.mq5 — descoberto e corrigido nesta
                  mesma sessao). A solucao ja em producao pra esse
                  terminal e o Service MQL5 nativo exportando CSV, que o
                  historico.py 1.3.0 ja funde no parquet de MTF. Reabrir
                  uma conexao Python pro mt5stock so pra "ultimo preco"
                  reintroduziria o mesmo risco resolvido a duras penas —
                  em vez disso, este script LE o parquet que ja esta
                  sendo alimentado (MESMA fonte de amplitude.py/dp.py),
                  sem conexao MT5 nenhuma.

                  Formato de saida IDENTICO ao last_int.py/last_nac.py
                  (lista de {"broker", "symbol", "time", "last",
                  "session_close"}) pra poder ser concatenado direto na
                  mesma lista `cotacoes` que a QuotesTable.jsx ja consome
                  (ver App.jsx) — variacao intradiaria = (last -
                  session_close) / session_close * 100, calculada no
                  FRONTEND, exatamente como ja acontece pros ativos da
                  corretora internacional/corretora nacional.

                  Por simbolo:
                  - "last" = fechamento do ULTIMO candle M1 (mais granular
                    coletado do mt5stock) — proxy de "preco corrente", tao
                    fresco quanto a ultima passada do
                    ExportadorMt5Stock.mq5 (ate ~15-20min de atraso, ver
                    docstring do .mq5 sobre o tempo de uma volta completa;
                    NAO e tick a tick como last_int.py/last_nac.py).
                  - "session_close" = fechamento do PENULTIMO candle D1
                    (o ULTIMO D1 e o dia de hoje, ainda se formando
                    intraday — igual ao "fechamento_anterior" que
                    amplitude.py usa pra avanco/declinio). Fechamento
                    OFICIAL da sessao anterior, mesma semantica do
                    session_close que last_int.py le de symbol_info().

                  Le direto dos parquets de preco em MTF (mesma fonte de
                  dp.py/amplitude.py), recalcula so quando o mtime de
                  algum parquet muda, grava double buffer — mesmo padrao
                  de todo o resto do projeto.
Autor          : Julio Cesar Silvio Campanhola
Criado em      : 2026-09-26
Ultima edicao  : 2026-09-26
Versao         : 1.0.0
Projeto        : dashboard
Historico      : scripts_py/versoes/magnificas.md
"""

import datetime
import importlib
import json
import os
import time

try:
    pd = importlib.import_module("pandas")
except ImportError as exc:
    raise ImportError(
        "A dependencia pandas nao esta instalada. "
        "Instale-a com: pip install pandas pyarrow"
    ) from exc

BROKER = "mt5stock"

# Sete Magnificas — GOOGL escolhido como representante unico da Alphabet
# (a mesma empresa tem GOOGL e GOOG coletados em ativos.acoes_nasdaq100,
# mas "7 magnificas" e sempre uma lista de 7, nao 8).
RAIZES = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA"]

PAUSA_LOOP = 1.0  # segundos entre cada checagem de mtime, mesmo padrao de amplitude.py/dp.py


class ColetorMagnificas:
    """Cotacao atual + fechamento da sessao anterior de cada uma das 7
    magnificas, direto dos parquets de preco em MTF — mesmo padrao de
    mtime-watch + double buffer de amplitude.py/dp.py."""

    def __init__(self, base_dir=None):
        self.base_dir = base_dir or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.mtf_dir = os.path.join(self.base_dir, "parquet", "historicos", "MTF")
        output_dir = os.path.join(self.base_dir, "json", "last_json")
        self.output_path_a = os.path.join(output_dir, "magnificas_a.json")
        self.output_path_b = os.path.join(output_dir, "magnificas_b.json")
        self.stop_flag_path = os.path.join(self.base_dir, "parquet", "historicos", "_stop_last.flag")
        os.makedirs(output_dir, exist_ok=True)

        self.caminhos = {
            (raiz, tf): os.path.join(self.mtf_dir, raiz, f"{tf}.parquet")
            for raiz in RAIZES
            for tf in ("m1", "d1")
        }

        self.ultimo_mtime = {}
        self.estado_atual = {}  # raiz -> {"last", "session_close"}
        self._sujo = False
        self._proximo_arquivo = "a"

    # ---------- calculo por raiz ----------

    def _last_do_m1(self, raiz):
        caminho = self.caminhos[(raiz, "m1")]
        df = pd.read_parquet(caminho, columns=["time", "close"])
        if df.empty:
            return None
        df = df.sort_values("time")
        return float(df["close"].iloc[-1])

    def _session_close_do_d1(self, raiz):
        """Penultimo candle D1 = fechamento OFICIAL da sessao anterior (o
        ultimo D1 e hoje, ainda se formando — mesma logica de
        amplitude.py._calcular_um pro "fechamento_anterior")."""
        caminho = self.caminhos[(raiz, "d1")]
        df = pd.read_parquet(caminho, columns=["time", "close"])
        if len(df) < 2:
            return None
        df = df.sort_values("time")
        return float(df["close"].iloc[-2])

    # ---------- varredura (so mtime mudou) + flush (double buffer) ----------

    def _varrer(self):
        for raiz in RAIZES:
            caminho_m1 = self.caminhos[(raiz, "m1")]
            caminho_d1 = self.caminhos[(raiz, "d1")]
            try:
                mtime_m1 = os.path.getmtime(caminho_m1)
                mtime_d1 = os.path.getmtime(caminho_d1)
            except OSError:
                continue  # raiz ainda sem parquet coletado (historico.py nao cobre ela ainda)

            chave_mtime = (mtime_m1, mtime_d1)
            if self.ultimo_mtime.get(raiz) == chave_mtime:
                continue

            try:
                last = self._last_do_m1(raiz)
                session_close = self._session_close_do_d1(raiz)
            except Exception as exc:
                print(f"[magnificas] erro calculando {raiz}, seguindo: {exc}")
                continue

            self.ultimo_mtime[raiz] = chave_mtime
            if last is None and session_close is None:
                continue

            self.estado_atual[raiz] = {"last": last, "session_close": session_close}
            self._sujo = True

    def _flush(self):
        if not self._sujo:
            return

        agora_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        saida = [
            {
                "broker": BROKER,
                "symbol": raiz,
                "time": agora_iso,
                "last": valor["last"],
                "session_close": valor["session_close"],
            }
            for raiz, valor in self.estado_atual.items()
        ]

        alvo = self.output_path_a if self._proximo_arquivo == "a" else self.output_path_b
        tmp_path = alvo + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(saida, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, alvo)
        self._proximo_arquivo = "b" if self._proximo_arquivo == "a" else "a"

        print(f"[magnificas] atualizado ({len(saida)} ativo(s)) -> {os.path.basename(alvo)}")
        self._sujo = False

    def executar(self):
        print(f"[magnificas] magnificas.py rodando (Ctrl+C pra parar) — {len(RAIZES)} ativos: {', '.join(RAIZES)}")

        try:
            while not os.path.exists(self.stop_flag_path):
                try:
                    self._varrer()
                except Exception as exc:
                    print(f"[magnificas] erro na varredura, seguindo pro proximo ciclo: {exc}")
                try:
                    self._flush()
                except Exception as exc:
                    print(f"[magnificas] erro no flush, tentando de novo no proximo ciclo: {exc}")
                time.sleep(PAUSA_LOOP)
            print("[magnificas] sinal de parada recebido")
        except KeyboardInterrupt:
            print("[magnificas] Ctrl+C recebido")
        finally:
            self._flush()


if __name__ == "__main__":
    ColetorMagnificas().executar()
