"""
Nome do script : correl.py
Descricao      : Calcula a correlacao rolante (janela deslizante) do retorno
                  de cada ativo do universo contra o retorno de referencia do
                  Indice e do Dolar (contrato corrente, corretora nacional), a
                  partir de parquet/calculos/retornoD1.parquet e
                  retornoM5.parquet. Pra cada ativo, pega o valor mais recente
                  da correlacao rolante contra INDICE e contra DOLAR e mantem so
                  quem bateu o limiar POSITIVO (LIMIAR_CORRELACAO) em pelo
                  menos uma das duas — candidatos a "andar junto" com INDICE/DOLAR.
                  Correlacao negativa (decorrelacao) fica no descorrel.py.
                  Ativos INDICE/DOLAR (qualquer variante) ficam de fora do
                  universo analisado — sao o alvo, nao candidato a driver.
                  Salva em parquet/calculos/correlacaoD1.parquet e
                  correlacaoM5.parquet.

                  Pedido do usuario: ordenar a tabela de cotacoes do frontend
                  "conforme o peso de cada um no indice e no dolar" — usando a
                  correlacao REAL calculada aqui, nao uma ordem fixa manual.
                  So que correlacaoD1/M5.parquet (acima) ja sai FILTRADO
                  (so quem bateu o limiar de 0.6) — pra ordenar a tabela
                  inteira (27 ativos, a maioria com correlacao fraca demais
                  pra passar no limiar) precisava do valor de peso de TODO
                  ativo, filtrado ou nao. Solucao: calcular_bruto() isola o
                  calculo comum (sem filtro nenhum) que calcular() ja fazia
                  por dentro — calcular() continua devolvendo so a correlacao
                  positiva filtrada (comportamento antigo, ninguem mais
                  precisou mudar), e o novo calcular_peso() usa o MESMO bruto
                  pra montar um ranking com TODO o universo, "peso" = maior
                  valor absoluto entre correlacao_indice/correlacao_dolar (positiva
                  ou negativa, tanto faz — quanto mais proximo de 1 pra
                  qualquer lado, mais a leitura de INDICE/DOLAR "pesa" naquele
                  ativo). Novo output: parquet/calculos/pesoMercadoD1.parquet
                  e pesoMercadoM5.parquet, lido pelo api_server.py
                  (/api/peso-mercado) — nao mexe em nada do que
                  correlacaoD1/M5.parquet ja servia (esta reservado pro
                  script futuro que cruza correlacao/descorrelacao com
                  ticker.json pra montar o cenario final, ver arquitetura.md).
Autor          : Julio Cesar Silvio Campanhola
Criado em      : 2026-09-13
Ultima edicao  : 2026-09-30
Versao         : 1.6.0
Projeto        : dashboard
Historico      : scripts_py/versoes/correl.md
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
try:
    np = importlib.import_module("numpy")
except ImportError as exc:
    raise ImportError(
        "A dependencia numpy nao esta instalada. "
        "Instale-a com: pip install numpy"
    ) from exc


BROKER_REF = "corretora nacional"
SYMBOL_INDICE = "Indice"
SYMBOL_DOLAR = "Dolar"
LIMIAR_CORRELACAO = 0.6

# Cluster nacional (pedido do usuario 2026-09-21): Indice, Dolar, Indice, Dolar
# e USDBRL sao a MESMA grandeza economica em formas diferentes (Indice=Indice e
# Dolar=Dolar via corretora internacional; USDBRL=Dolar a vista em vez de futuro) —
# nenhum dos 5 pode ser referencia OU driver de outro do proprio cluster
# (correlacao tautologica), mas cada um agora tem sua propria correlacao
# calculada contra o RESTO da grade (antes so Indice/Dolar eram referencia).
# Indice/Dolar tem vencimento — o ticker vigente e resolvido de config.json
# na hora de rodar (_resolver_cluster), sem precisar importar historico.py
# (que exige MetaTrader5 instalado so pra montar_alvos).
CLUSTER_NACIONAL = {
    "indice": {"broker": "corretora nacional", "raiz": "Indice"},
    "dolar": {"broker": "corretora nacional", "raiz": "Dolar"},
    "indice": {"broker": "corretora internacional", "raiz": "Indice"},
    "dolar": {"broker": "corretora internacional", "raiz": "Dolar"},
    "usdbrl": {"broker": "corretora internacional", "raiz": "USDBRL"},
}


class AnalisadorCorrelacao:
    """Correlacao rolante do retorno de cada ativo contra Indice e Dolar — mantem so a positiva
    (calcular()) e tambem o ranking de peso do universo inteiro, sem filtro (calcular_peso())."""

    def __init__(self, retorno_path, saida_path, saida_peso_path, janela, config_path=None):
        self.retorno_path = retorno_path
        self.saida_path = saida_path
        self.saida_peso_path = saida_peso_path
        self.janela = janela
        # 3 niveis acima de parquet/calculos/retornoD1.parquet -> backend/,
        # depois json/config.json — mesma convencao de outros scripts
        self.config_path = config_path or os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(retorno_path)))),
            "json", "config.json",
        )
        os.makedirs(os.path.dirname(self.saida_path), exist_ok=True)
        os.makedirs(os.path.dirname(self.saida_peso_path), exist_ok=True)

    def _serie_referencia(self, df, broker, symbol, rotulo):
        """Serie de retorno de um simbolo de referencia (qualquer membro do
        CLUSTER_NACIONAL), pronta pra merge por time."""
        ref = df[(df["broker"] == broker) & (df["symbol"] == symbol)][["time", "retorno"]]
        return ref.rename(columns={"retorno": rotulo}).sort_values("time")

    def _resolver_cluster(self):
        """Resolve o ticker VIGENTE de cada membro do CLUSTER_NACIONAL —
        Indice/Dolar tem vencimento (le config.json->vigentes, primeiro
        ticker da lista); indice/dolar/usdbrl nao tem, ticker == raiz."""
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
        except (OSError, json.JSONDecodeError):
            config = {}
        vigentes = config.get("vigentes", {})

        resolvido = {}
        for nome, info in CLUSTER_NACIONAL.items():
            candidatos = vigentes.get(info["raiz"]) or [info["raiz"]]
            resolvido[nome] = {"broker": info["broker"], "ticker": candidatos[0]}
        return resolvido

    def _resolver_extra(self):
        """Resolve o ticker VIGENTE de cada ativo em config.json ->
        ativos_referencia_extra (pedido do usuario 2026-09-25: lista fica no
        JSON, nao hardcoded aqui — adicionar Ouro/SP500/Petroleo etc. no
        futuro e so uma linha nesse dict do config, sem editar este
        arquivo). Mesma logica de _resolver_cluster (raiz com vencimento le
        config.json -> vigentes, raiz continua usa ela mesma como ticker)."""
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
        except (OSError, json.JSONDecodeError):
            config = {}
        vigentes = config.get("vigentes", {})
        extras_config = config.get("ativos_referencia_extra", {})

        resolvido = {}
        for nome, info in extras_config.items():
            candidatos = vigentes.get(info["raiz"]) or [info["raiz"]]
            resolvido[nome] = {"broker": info["broker"], "ticker": candidatos[0]}
        return resolvido

    def calcular_bruto(self):
        """Correlacao rolante no ultimo ponto disponivel de CADA ativo do
        universo, SEM filtro de limiar nenhum, contra CADA membro do
        CLUSTER_NACIONAL (indice/dolar/indice/dolar/usdbrl) — base compartilhada
        tanto pra calcular() (so positiva contra indice/dolar, LIMIAR_CORRELACAO)
        quanto pra calcular_peso() (ranking com todo mundo, pro frontend
        ordenar a tabela de cotacoes). correlacao_indice/correlacao_dolar
        continuam com o mesmo nome/sentido de sempre — calcular()/
        calcular_peso() nao mudam; so ganham 3 colunas novas
        (correlacao_indice/correlacao_dolar/correlacao_usdbrl), pedido do
        usuario 2026-09-21: "USDBRL, INDICE, DOLAR, INDICE e Dolar sao os ativos
        que precisam ser comparados com outros ativos da grade e nao
        comparar eles entre si" — Indice/Dolar/USDBRL sao a MESMA grandeza
        que Indice/Dolar (so via corretora internacional/a vista), entao correlacionar um
        contra o outro seria tautologico; mas cada um pode reagir a grade
        internacional em horario diferente de Indice/Dolar (sessao B3), entao a
        correlacao deles contra o resto da grade e informacao nova."""
        df = pd.read_parquet(self.retorno_path, columns=["broker", "symbol", "time", "retorno"])
        cluster = self._resolver_cluster()
        extra = self._resolver_extra()

        series_ref = {
            nome: self._serie_referencia(df, info["broker"], info["ticker"], f"ret_{nome}")
            for nome, info in {**cluster, **extra}.items()
        }
        # chave (broker, ticker) de cada extra, pra auto-excluir so a PROPRIA
        # coluna de correlacao daquele ativo (nao o ativo inteiro do
        # universo — ver ATIVOS_REFERENCIA_EXTRA acima)
        chave_extra = {nome: (info["broker"], info["ticker"]) for nome, info in extra.items()}

        # fora do universo (nao pode ser driver de ninguem do cluster):
        # Indice/Dolar e toda a curva de vencimento "DOLAR" da B3 (DOLARV26, DOLARX26,
        # ... — mesmo dolar futuro de Dolar em vencimentos diferentes; regex
        # ja usada e validada desde a 1.0.0) + Indice/Dolar/USDBRL, que sao a
        # mesma grandeza via corretora internacional/cambio a vista (novo). Os ativos de
        # ATIVOS_REFERENCIA_EXTRA (ex.: UsaTec) NAO entram aqui — continuam
        # dentro do universo (podem ser driver de INDICE/DOLAR/outros extras
        # normalmente), so se auto-excluem da propria coluna mais abaixo.
        excluido_regex = df["symbol"].str.upper().str.match(r"^(INDICE|DOLAR)").to_numpy()
        tickers_novo_cluster = {
            (info["broker"], info["ticker"]) for nome, info in cluster.items() if nome in ("indice", "dolar", "usdbrl")
        }
        chave = list(zip(df["broker"], df["symbol"]))
        excluido_novo_cluster = np.array([par in tickers_novo_cluster for par in chave])
        universo = df[~(excluido_regex | excluido_novo_cluster)]

        linhas = []
        for (broker, symbol), grupo in universo.groupby(["broker", "symbol"]):
            # obs: nao precisa mais corrigir fuso aqui - historico_d1/m5.parquet
            # ja nascem com o horario correto (corrigido na coleta, ver
            # scripts_py/fuso_horario.py)
            base_ativo = grupo[["time", "retorno"]].sort_values("time")

            # Correcao 2026-09-30 (incidente Risk Dolar/Dolar Teorico vazios):
            # cada referencia agora faz o PROPRIO merge com o ativo, em vez
            # de um unico merge acumulado (inner join) com TODAS as
            # referencias de uma vez. Antes, se uma unica referencia do
            # cluster estivesse vazia (ex.: Dolar vigente apontando pra um
            # contrato que acabou de rolar e ainda sem historico — vigente.py
            # pegou DolarSep26 na virada do mes, contrato ja sem dado, em
            # vez do DolarOct26 que ja tinha preco real), o merge encadeado
            # zerava a base pra TODO o universo, esvaziando
            # correlacaoD1/M5.parquet e pesoMercadoD1/M5.parquet por inteiro
            # — e isso derrubava tanto a tabela "Risk Dolar" do frontend
            # (QuotesTable sem peso calculado pra nenhum ativo) quanto o
            # card "Dolar Teorico" (dependente do vigente do Dolar pra
            # achar o vertice certo da curva FRC). Agora uma referencia sem
            # dado (ou sem pontos suficientes na janela) so fica None
            # NAQUELA coluna, sem derrubar as demais — um problema pontual
            # de rolagem de contrato nao tira mais o painel do ar inteiro.
            linha = {"broker": broker, "symbol": symbol}
            algum_valor = False
            maior_n_pontos = 0
            ultimo_time = base_ativo["time"].iloc[-1]
            for nome, serie in series_ref.items():
                # auto-exclusao: um ativo de ATIVOS_REFERENCIA_EXTRA nao
                # correlaciona contra ele mesmo (sempre ~1.0, nao e
                # informacao) — os demais (indice/dolar/indice/dolar/usdbrl e
                # outros extras) continuam normalmente pra essa linha.
                if chave_extra.get(nome) == (broker, symbol):
                    linha[f"correlacao_{nome}"] = None
                    continue
                if serie.empty:
                    linha[f"correlacao_{nome}"] = None
                    continue
                merge_par = base_ativo.merge(serie, on="time", how="inner")
                if len(merge_par) < self.janela:
                    linha[f"correlacao_{nome}"] = None
                    continue
                serie_corr = merge_par["retorno"].rolling(self.janela).corr(merge_par[f"ret_{nome}"]).dropna()
                valor = float(serie_corr.iloc[-1]) if not serie_corr.empty else None
                linha[f"correlacao_{nome}"] = valor
                if valor is not None:
                    algum_valor = True
                    maior_n_pontos = max(maior_n_pontos, len(merge_par))
                    ultimo_time = merge_par["time"].iloc[-1]
            if not algum_valor:
                continue
            linha["time"] = ultimo_time
            linha["n_pontos"] = maior_n_pontos
            linhas.append(linha)

        return pd.DataFrame(linhas)

    def calcular(self):
        """So a correlacao POSITIVA (>= LIMIAR_CORRELACAO em INDICE ou DOLAR) — comportamento original."""
        saida = self.calcular_bruto()
        if saida.empty:
            return saida

        positivos = saida[
            (saida["correlacao_indice"] >= LIMIAR_CORRELACAO)
            | (saida["correlacao_dolar"] >= LIMIAR_CORRELACAO)
        ].copy()
        positivos["forca"] = positivos[["correlacao_indice", "correlacao_dolar"]].max(axis=1)
        positivos = positivos.sort_values("forca", ascending=False).drop(columns="forca").reset_index(drop=True)
        return positivos

    def calcular_peso(self):
        """Ranking de "peso" no indice (INDICE) e no dolar (DOLAR) pra TODO ativo
        do universo, sem filtro de limiar — pedido do usuario pra ordenar a
        tabela de cotacoes do frontend pela forca real da relacao com
        INDICE/DOLAR, e nao so quem passou no limiar de 0.6 (a maioria dos 27
        ativos internacionais mostrados na tabela fica abaixo disso, mas
        ainda tem uma correlacao mensuravel que vale pra ordenar). peso =
        maior valor absoluto entre correlacao_indice e correlacao_dolar — tanto
        faz se a correlacao e positiva ou negativa, o que importa pra "peso"
        e o quanto o ativo se move junto (ou contra) INDICE/DOLAR, nao a direcao."""
        bruto = self.calcular_bruto()
        if bruto.empty:
            return bruto
        bruto = bruto.copy()
        bruto["peso"] = bruto[["correlacao_indice", "correlacao_dolar"]].abs().max(axis=1)
        bruto = bruto.sort_values("peso", ascending=False).reset_index(drop=True)
        return bruto

    def executar(self):
        df = self.calcular()
        df.to_parquet(self.saida_path, index=False)
        print(f"Salvo: {os.path.abspath(self.saida_path)} "
              f"({len(df)} ativos correlacionados, janela={self.janela})")

        peso = self.calcular_peso()
        peso.to_parquet(self.saida_peso_path, index=False)
        print(f"Salvo: {os.path.abspath(self.saida_peso_path)} "
              f"({len(peso)} ativos no ranking de peso, janela={self.janela})")
        return df


if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.abspath(__file__))
    calculos = os.path.join(base_dir, "..", "parquet", "calculos")

    AnalisadorCorrelacao(
        os.path.join(calculos, "retornoD1.parquet"),
        os.path.join(calculos, "correlacaoD1.parquet"),
        os.path.join(calculos, "pesoMercadoD1.parquet"),
        janela=20,
    ).executar()

    AnalisadorCorrelacao(
        os.path.join(calculos, "retornoM5.parquet"),
        os.path.join(calculos, "correlacaoM5.parquet"),
        os.path.join(calculos, "pesoMercadoM5.parquet"),
        janela=100,
    ).executar()
