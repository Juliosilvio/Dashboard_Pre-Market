"""
Nome do script : curva_juros.py
Descricao      : Constroi um indice de taxa de juros de "prazo constante"
                  (constant maturity) a partir da curva inteira do DI1 (todos
                  os vertices configurados em ativos.curva_br), por
                  interpolacao linear em dias uteis ate o vencimento (DU/252,
                  convencao do mercado brasileiro; aproximacao sem calendario
                  de feriados B3, mesmo padrao ja usado no projeto).

                  Motivo de nao usar so o vertice mais proximo (front): o
                  vertice mais curto converge mecanicamente pra Selic
                  perto do vencimento (efeito de "roll-down"), entao ele nao
                  e um bom termometro estavel de expectativa ao longo do
                  tempo. Um ponto de prazo constante (ex: "DI de 1 ano")
                  sempre representa o mesmo horizonte, dia apos dia, e por
                  isso compara direito com a Meta Selic (dadosgov.py) e
                  sustenta uma serie historica coerente.

                  Limitacao de dados, documentada de proposito: config.json
                  so lista os vertices do DI1 ATUALMENTE negociados (vistos
                  de hoje pra frente). Contratos curtos que ja venceram no
                  passado (ex: o vertice de 12 meses em 2024) nao estao no
                  projeto - a serie deles nunca foi coletada. Por isso:
                  - "DI de 2 anos" (504 DU) tem cobertura quase completa
                    desde o inicio do MTF (2024-09-20), porque o vertice mais
                    curto que ja tinhamos historico (DI1V26) estava, la
                    atras, proximo de 2 anos do proprio vencimento.
                  - "DI de 1 ano" (252 DU) SO fica valido a partir de
                    2025-10-14 (quando um vertice curto o suficiente passou a
                    ter historico no projeto) - antes disso fica NaN de
                    proposito, em vez de extrapolar (o que inventaria dado).
Autor          : Julio Cesar Silvio Campanhola
Criado em      : 2026-09-21
Ultima edicao  : 2026-09-21
Versao         : 1.0.1
Projeto        : dashboard
Historico      : scripts_py/versoes/curva_juros.md
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

from historico import ColetorHistoricoMTF

# horizontes de prazo constante, em dias uteis (base 252 = 1 ano no mercado BR)
HORIZONTES = {"1ano": 252, "2anos": 504}


class AnaliseCurvaJuros:
    def __init__(self, base_dir=None):
        self.base_dir = base_dir or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.calculos_dir = os.path.join(self.base_dir, "parquet", "calculos")
        self.mtf_dir = os.path.join(self.base_dir, "parquet", "historicos", "MTF")
        self.dadosgov_dir = os.path.join(self.base_dir, "parquet", "historicos", "dadosgov")
        self.saida_path = os.path.join(self.calculos_dir, "curva_juros.parquet")
        self.coletor = ColetorHistoricoMTF(self.base_dir)

    @staticmethod
    def _primeiro_dia_util(ano, mes):
        """Vencimento do DI1 = primeiro dia util do mes de vencimento
        (aproximacao sem calendario de feriados B3 - mesmo padrao ja usado
        no _ultimo_dia_util do api_server.py e do dadosgov.py)."""
        dia = pd.Timestamp(year=ano, month=mes, day=1)
        while dia.weekday() >= 5:  # 5=sabado, 6=domingo
            dia += pd.Timedelta(days=1)
        return dia

    def _montar_curva_di1(self):
        """Le TODOS os vertices do DI1 configurados e devolve um DataFrame
        longo (data, ticker, vencimento, close, du_ate_venc) - uma linha por
        combinacao (dia, vertice) com dado disponivel."""
        self.coletor.carregar_config()
        alvos_di1 = [a for a in self.coletor.montar_alvos() if a["raiz"] == "DI1"]
        if not alvos_di1:
            raise RuntimeError("nenhum alvo DI1 encontrado em config.json -> ativos.curva_br")

        registros = []
        for alvo in alvos_di1:
            resultado = ColetorHistoricoMTF.extrai_mes_ano_curva(alvo["ticker"], alvo["raiz"])
            if resultado is None:
                continue
            mes, ano = resultado
            vencimento = self._primeiro_dia_util(ano, mes)
            caminho = os.path.join(self.mtf_dir, *alvo["pasta_rel"].split("/"), "d1.parquet")
            if not os.path.exists(caminho):
                continue
            df = pd.read_parquet(caminho, columns=["time", "close"])
            df["data"] = pd.to_datetime(df["time"], utc=True).dt.tz_localize(None).dt.normalize()
            df["ticker"] = alvo["ticker"]
            df["vencimento"] = vencimento
            registros.append(df[["data", "ticker", "vencimento", "close"]])

        if not registros:
            raise RuntimeError("nenhum vertice DI1 com d1.parquet encontrado")

        curva = pd.concat(registros, ignore_index=True)
        curva["du_ate_venc"] = np.busday_count(
            curva["data"].to_numpy().astype("datetime64[D]"),
            curva["vencimento"].to_numpy().astype("datetime64[D]"),
        )
        # descarta pontos ja vencidos (nao deveria acontecer, mas por seguranca)
        return curva[curva["du_ate_venc"] > 0].reset_index(drop=True)

    @staticmethod
    def _interpolar_du(grupo, alvo_du):
        """Interpolacao linear entre os 2 vertices mais proximos (um de cada
        lado) do prazo alvo, dentro da curva daquele dia. Nunca extrapola:
        se o prazo alvo estiver fora do range de vertices disponiveis
        naquele dia, devolve NaN (documentado no cabecalho do script)."""
        grupo = grupo.sort_values("du_ate_venc")
        abaixo = grupo[grupo["du_ate_venc"] <= alvo_du].tail(1)
        acima = grupo[grupo["du_ate_venc"] >= alvo_du].head(1)
        if abaixo.empty or acima.empty:
            return float("nan")
        x0, y0 = abaixo["du_ate_venc"].iloc[0], abaixo["close"].iloc[0]
        x1, y1 = acima["du_ate_venc"].iloc[0], acima["close"].iloc[0]
        if x0 == x1:
            return y0
        return y0 + (y1 - y0) * (alvo_du - x0) / (x1 - x0)

    def calcular_indice(self):
        """Devolve um DataFrame (data, di_1ano, di_2anos, n_vertices) - o
        indice de juros de prazo constante, um ponto por dia util."""
        curva = self._montar_curva_di1()
        linhas = []
        for data, grupo in curva.groupby("data"):
            linha = {"data": data, "n_vertices": len(grupo)}
            for rotulo, du_alvo in HORIZONTES.items():
                linha[f"di_{rotulo}"] = self._interpolar_du(grupo, du_alvo)
            linhas.append(linha)
        indice = pd.DataFrame(linhas).sort_values("data").reset_index(drop=True)
        colunas = ["data"] + [f"di_{rotulo}" for rotulo in HORIZONTES] + ["n_vertices"]
        return indice[colunas]

    def _carregar_selic_meta(self):
        caminho = os.path.join(self.dadosgov_dir, "selic_meta.parquet")
        if not os.path.exists(caminho):
            raise RuntimeError(f"{caminho} nao existe ainda - rode dadosgov.py primeiro pra coletar a Selic")
        df = pd.read_parquet(caminho, columns=["data", "valor"]).sort_values("data")
        return df.rename(columns={"valor": "selic_meta"})

    def comparar_com_selic(self, indice=None):
        if indice is None:
            indice = self.calcular_indice()
        indice = indice.copy()
        # merge_asof exige as duas colunas de merge no MESMO dtype exato
        # (nao so "ambas datetime") - a coluna 'data' do indice DI1 vem do
        # parquet MTF em datetime64[us] (as vezes [s], dependendo da
        # origem), enquanto a Selic (dadosgov, texto->to_datetime) vira
        # datetime64[ns]. Sem forcar os dois pro mesmo unit aqui, o pandas
        # 2.x recusa o merge com "incompatible merge keys ... must be the
        # same type" mesmo os dois sendo datetime. Normaliza pra ns antes
        # de comparar (mesmo padrao ja usado no fix do
        # backtest_vies_direcional.py pro mesmo tipo de erro).
        indice["data"] = pd.to_datetime(indice["data"]).astype("datetime64[ns]")
        selic = self._carregar_selic_meta()
        selic["data"] = pd.to_datetime(selic["data"]).astype("datetime64[ns]")
        combinado = pd.merge_asof(
            indice.sort_values("data"), selic.sort_values("data"),
            on="data", direction="backward",
        )
        for rotulo in HORIZONTES:
            combinado[f"spread_{rotulo}"] = combinado[f"di_{rotulo}"] - combinado["selic_meta"]
        return combinado

    def executar(self):
        combinado = self.comparar_com_selic()
        os.makedirs(os.path.dirname(self.saida_path), exist_ok=True)
        combinado.to_parquet(self.saida_path, index=False)
        ultima = combinado.dropna(subset=["di_2anos"]).iloc[-1]
        print(
            f"Salvo: {os.path.abspath(self.saida_path)} ({len(combinado)} dias) - "
            f"ultimo DI 1 ano={ultima.get('di_1ano', float('nan')):.3f}%, "
            f"DI 2 anos={ultima['di_2anos']:.3f}%, Selic meta={ultima['selic_meta']:.2f}%"
        )
        return combinado


if __name__ == "__main__":
    AnaliseCurvaJuros().executar()
