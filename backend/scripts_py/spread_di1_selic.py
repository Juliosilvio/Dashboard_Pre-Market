"""
Nome do script : spread_di1_selic.py
Descricao      : Calcula o spread entre o DI1 (vertice mais proximo/front)
                  e a Meta Selic (dadosgov.py, serie selic_meta) — a
                  expectativa de juros que o mercado ja precifica no DI1
                  comparada contra a taxa livre de risco que o Copom
                  decidiu por ultimo. Pedido do usuario (2026-09-21):
                  "montar um vertice com t0=selic e tvar=di1, comparar a
                  expectativa com a taxa livre de risco" e depois "comparar
                  como o indice e o dolar se comportaram em relacao ao
                  comportamento da expectativa em relacao a taxa do copom".

                  spread(t) = DI1_front(t) - Selic_meta_vigente(t). DI1 ja
                  vem cotado em taxa (% a.a., mesma unidade da Selic,
                  confirmado em dado real: ~13,65 contra Selic de 13,75 —
                  sem conversao de PU pra taxa necessaria). DI1 e intraday
                  continuo (D1 por enquanto); Selic vem em degrau (muda so
                  em decisao do Copom) — alinhados por merge as-of (Selic
                  vigente naquela data, sem espiar o futuro), mesmo padrao
                  ja usado nos backtests do vies_direcional.py.

                  Depois de montar o spread, mede a relacao entre a
                  VARIACAO do spread e o retorno (log, retorno.py) de cada
                  ativo do indice (Indice, Indice) e do dolar (Dolar, Dolar,
                  USDBRL) — reaproveita CLUSTER_NACIONAL/_resolver_cluster()
                  do correl.py, mesma resolucao de ticker vigente ja
                  validada, pra nao duplicar. CADA UM DOS 5 E TESTADO
                  SEPARADO CONTRA O SPREAD, NUNCA UM CONTRA O OUTRO nem
                  indice contra dolar (regra explicita do usuario 2026-09-
                  21: nenhum dos 5 pode ser comparado com outro do proprio
                  grupo nem entre grupos — aqui a unica comparacao e
                  "ativo X vs spread DI1-Selic", igual a grade ja compara
                  cada um dos 5 contra si so, nunca um contra o outro).

                  Vertice usado: so o FRONT (vencimento mais proximo) do
                  DI1 por enquanto — mesma reducao que o vies_direcional.py
                  ja faz pra DI1/FRC/DDI (CURVA_RAIZES_INCLUIDAS). Full-
                  curve (varios vertices ao mesmo tempo, pra olhar
                  inclinacao/paralelo da curva) fica pra depois, se o
                  usuario pedir — decisao registrada, nao decidida sozinho.

                  Salva o spread em
                  parquet/calculos/spread_di1_selic.parquet (colunas data,
                  di1, selic_meta, spread). Nao escreve nada em
                  correlacaoD1/pesoMercadoD1 (nao mexe no que a grade ja
                  serve pro frontend) — este script e so a analise pedida,
                  standalone.
Autor          : Julio Cesar Silvio Campanhola
Criado em      : 2026-09-21
Ultima edicao  : 2026-09-21
Versao         : 1.0.0
Projeto        : dashboard
Historico      : scripts_py/versoes/spread_di1_selic.md
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

from correl import AnalisadorCorrelacao, CLUSTER_NACIONAL
from historico import ColetorHistoricoMTF

# rotulo de exibicao de cada membro do cluster + o grupo que ele pertence
# (so pra organizar o relatorio final - a comparacao em si e sempre 1x1
# contra o spread, nunca entre membros)
GRUPOS = {
    "indice": "indice", "indice": "indice",
    "dolar": "dolar", "dolar": "dolar", "usdbrl": "dolar",
}


class AnaliseSpreadDI1Selic:
    """Spread DI1(front) - Selic meta, e a correlacao dele com o retorno
    de cada ativo do indice/dolar (sempre 1x1 contra o spread)."""

    def __init__(self, base_dir=None):
        self.base_dir = base_dir or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.calculos_dir = os.path.join(self.base_dir, "parquet", "calculos")
        self.mtf_dir = os.path.join(self.base_dir, "parquet", "historicos", "MTF")
        self.dadosgov_dir = os.path.join(self.base_dir, "parquet", "historicos", "dadosgov")
        self.retorno_path = os.path.join(self.calculos_dir, "retornoD1.parquet")
        self.saida_path = os.path.join(self.calculos_dir, "spread_di1_selic.parquet")
        self.coletor = ColetorHistoricoMTF(self.base_dir)

    # ---------- DI1 front ----------

    def _resolver_di1_front(self):
        """Mesma logica de reducao ao vertice mais proximo que o
        vies_direcional.py ja usa pra DI1/FRC/DDI — reaproveitada aqui, nao
        duplicada por acidente (so nao importa de la porque MotorViesDirecional
        monta o universo inteiro; aqui so precisamos do DI1)."""
        self.coletor.carregar_config()
        alvos_di1 = [a for a in self.coletor.montar_alvos() if a["raiz"] == "DI1"]
        if not alvos_di1:
            raise RuntimeError("nenhum alvo DI1 encontrado em config.json -> ativos.curva_br")

        def _chave_vencimento(alvo):
            resultado = ColetorHistoricoMTF.extrai_mes_ano_curva(alvo["ticker"], alvo["raiz"])
            if resultado is None:
                return (9999, 99)
            mes, ano = resultado
            return (ano, mes)

        return min(alvos_di1, key=_chave_vencimento)

    def _carregar_di1_front(self):
        alvo = self._resolver_di1_front()
        caminho = os.path.join(self.mtf_dir, *alvo["pasta_rel"].split("/"), "d1.parquet")
        df = pd.read_parquet(caminho, columns=["time", "close"]).sort_values("time")
        df["data"] = pd.to_datetime(df["time"], utc=True).dt.date
        return df[["data", "close"]].rename(columns={"close": "di1"}), alvo["ticker"]

    # ---------- Selic meta ----------

    def _carregar_selic_meta(self):
        caminho = os.path.join(self.dadosgov_dir, "selic_meta.parquet")
        if not os.path.exists(caminho):
            raise RuntimeError(
                f"{caminho} nao existe ainda - rode dadosgov.py primeiro pra coletar a Selic"
            )
        df = pd.read_parquet(caminho, columns=["data", "valor"]).sort_values("data")
        return df.rename(columns={"valor": "selic_meta"})

    # ---------- spread ----------

    def calcular_spread(self):
        """DI1(front) - Selic_meta vigente naquela data (as-of, sem espiar
        o futuro - Selic muda em degrau, entao a mesma Selic vale ate a
        proxima mudanca aparecer na serie)."""
        di1, ticker_di1 = self._carregar_di1_front()
        selic = self._carregar_selic_meta()

        di1["data"] = pd.to_datetime(di1["data"])
        selic["data"] = pd.to_datetime(selic["data"])

        combinado = pd.merge_asof(
            di1.sort_values("data"),
            selic.sort_values("data"),
            on="data",
            direction="backward",
        )
        combinado["spread"] = combinado["di1"] - combinado["selic_meta"]
        combinado = combinado.dropna(subset=["selic_meta"]).reset_index(drop=True)
        self._ticker_di1_usado = ticker_di1
        return combinado

    def executar(self):
        spread = self.calcular_spread()
        os.makedirs(os.path.dirname(self.saida_path), exist_ok=True)
        spread.to_parquet(self.saida_path, index=False)
        print(
            f"Salvo: {os.path.abspath(self.saida_path)} "
            f"({len(spread)} dias, DI1={self._ticker_di1_usado}, "
            f"spread atual={spread['spread'].iloc[-1]:+.3f}pp)"
        )
        return spread

    # ---------- comparacao com indice/dolar (1x1, nunca cruzado) ----------

    def comparar_ativos(self, spread=None):
        """Correlacao entre a VARIACAO diaria do spread e o retorno (log)
        de CADA UM dos 5 ativos do cluster nacional, sempre 1x1 contra o
        spread - nunca ativo contra ativo (regra do usuario). Devolve um
        DataFrame com uma linha por ativo: grupo, ticker, n_dias, correlacao."""
        if spread is None:
            spread = self.calcular_spread()
        spread = spread.copy()
        spread["delta_spread"] = spread["spread"].diff()
        spread["time"] = pd.to_datetime(spread["data"], utc=True)

        retorno = pd.read_parquet(self.retorno_path, columns=["broker", "symbol", "time", "retorno"])
        retorno["time"] = pd.to_datetime(retorno["time"], utc=True)

        # reaproveita a resolucao de ticker vigente ja validada do correl.py
        # (Indice/Dolar tem vencimento, indice/dolar/usdbrl nao) - instancia so
        # pra chamar _resolver_cluster(), nunca executa/grava nada com ela
        resolvedor = AnalisadorCorrelacao(self.retorno_path, os.devnull, os.devnull, janela=20)
        cluster = resolvedor._resolver_cluster()

        linhas = []
        for nome, info in cluster.items():
            serie_ativo = retorno[(retorno["broker"] == info["broker"]) & (retorno["symbol"] == info["ticker"])]
            juntado = spread[["time", "delta_spread"]].merge(serie_ativo[["time", "retorno"]], on="time", how="inner")
            juntado = juntado.dropna(subset=["delta_spread", "retorno"])
            correlacao = juntado["delta_spread"].corr(juntado["retorno"]) if len(juntado) > 2 else float("nan")
            linhas.append({
                "grupo": GRUPOS[nome],
                "ativo": nome,
                "ticker": info["ticker"],
                "n_dias": len(juntado),
                "correlacao_com_delta_spread": round(correlacao, 4) if pd.notna(correlacao) else None,
            })

        return pd.DataFrame(linhas)


if __name__ == "__main__":
    analise = AnaliseSpreadDI1Selic()
    spread = analise.executar()

    relatorio = analise.comparar_ativos(spread)
    print("\nCorrelacao (retorno diario do ativo) x (variacao diaria do spread DI1-Selic):")
    print(relatorio.to_string(index=False))
