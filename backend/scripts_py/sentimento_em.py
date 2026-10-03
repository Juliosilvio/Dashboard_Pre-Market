"""
Nome do script : sentimento_em.py
Descricao      : Cotacao "atual" + variacao intradiaria de dois ETFs usados
                  como termometro de sentimento de risco Brasil/mercados
                  emergentes fora do horario da B3 — EWZ (iShares MSCI
                  Brazil) e EEM (iShares MSCI Emerging Markets) — pedido do
                  usuario 2026-09-29 ("colocar o EWZ no Risk indice",
                  ampliado pra EEM tambem: "ambos ja estao visiveis" no
                  Market Watch do mt5stock).

                  Mesmo padrao de magnificas.py (ver docstring dele pro
                  motivo completo): o terminal mt5stock tem um bug que
                  quebra symbol_select()/copy_rates_range() via API Python
                  externa (Terminal: Out of memory), contornado com o
                  Service MQL5 nativo (ExportadorMt5Stock.mq5 1.01+) que
                  exporta CSV pra dentro do parquet de MTF via
                  historico.py 1.4.0 (grupo "etfs_sentimento_em" em
                  BROKER_POR_GRUPO/ORDEM_GRUPOS). Este script SO LE esse
                  parquet ja alimentado — nenhuma conexao MT5 propria.

                  Formato de saida IDENTICO a magnificas.py/last_int.py
                  (lista de {"broker", "symbol", "time", "last",
                  "session_close"}) pra poder compor a grade de cotacoes
                  via feedsCotacoes/cotacoesDaView (App.jsx) — variacao
                  intradiaria calculada no FRONTEND, mesma formula de
                  sempre.

                  Por simbolo:
                  - "last" = fechamento do ULTIMO candle M1 coletado do
                    mt5stock (mesma semantica de magnificas.py).
                  - "session_close" = fechamento do PENULTIMO candle D1
                    (o ultimo D1 e hoje, ainda se formando intraday).

                  IMPORTANTE - onde EWZ/EEM aparecem na grade (Risk Indice
                  ou Risk Dolar) NAO e decidido aqui: este script so
                  entrega a cotacao. Quem decide e separarIndiceDolar()
                  no frontend (QuotesTable.jsx), com base em
                  correlacao_indice/correlacao_dolar REAL calculada por
                  correl.py a partir do parquet de MTF (config.json ->
                  grades_cotacoes.principal.feeds precisa incluir
                  "sentimento_em" pra esses dois ativos entrarem na grade
                  principal - ver client.js/App.jsx).
Autor          : Julio Cesar Silvio Campanhola
Criado em      : 2026-09-29
Ultima edicao  : 2026-09-29
Versao         : 1.0.0
Projeto        : dashboard
Historico      : scripts_py/versoes/sentimento_em.md
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

# EWZ (iShares MSCI Brazil) + EEM (iShares MSCI Emerging Markets) - mesma
# raiz = ticker do config.json -> ativos.etfs_sentimento_em.
RAIZES = ["EWZ", "EEM"]

PAUSA_LOOP = 1.0  # segundos entre cada checagem de mtime, mesmo padrao de magnificas.py/amplitude.py/dp.py


class ColetorSentimentoEm:
    """Cotacao atual + fechamento da sessao anterior de EWZ/EEM, direto dos
    parquets de preco em MTF — mesmo padrao de mtime-watch + double buffer
    de magnificas.py/amplitude.py/dp.py."""

    def __init__(self, base_dir=None):
        self.base_dir = base_dir or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.mtf_dir = os.path.join(self.base_dir, "parquet", "historicos", "MTF")
        output_dir = os.path.join(self.base_dir, "json", "last_json")
        self.output_path_a = os.path.join(output_dir, "sentimento_em_a.json")
        self.output_path_b = os.path.join(output_dir, "sentimento_em_b.json")
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
        ultimo D1 e hoje, ainda se formando intraday — mesma logica de
        magnificas.py/amplitude.py pro "fechamento_anterior")."""
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
                print(f"[sentimento_em] erro calculando {raiz}, seguindo: {exc}")
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

        print(f"[sentimento_em] atualizado ({len(saida)} ativo(s)) -> {os.path.basename(alvo)}")
        self._sujo = False

    def executar(self):
        print(f"[sentimento_em] sentimento_em.py rodando (Ctrl+C pra parar) — {len(RAIZES)} ativos: {', '.join(RAIZES)}")

        try:
            while not os.path.exists(self.stop_flag_path):
                try:
                    self._varrer()
                except Exception as exc:
                    print(f"[sentimento_em] erro na varredura, seguindo pro proximo ciclo: {exc}")
                try:
                    self._flush()
                except Exception as exc:
                    print(f"[sentimento_em] erro no flush, tentando de novo no proximo ciclo: {exc}")
                time.sleep(PAUSA_LOOP)
            print("[sentimento_em] sinal de parada recebido")
        except KeyboardInterrupt:
            print("[sentimento_em] Ctrl+C recebido")
        finally:
            self._flush()


if __name__ == "__main__":
    ColetorSentimentoEm().executar()
