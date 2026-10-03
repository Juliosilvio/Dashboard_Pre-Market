"""
Nome do script : situacao_pre_abertura.py
Descricao      : Monta o dataset "situacao -> resultado" pra Indice/Dolar: uma
                  linha por pregao, cruzando o estado do cesto de risco
                  internacional (Usa500, UsaVix) pouco antes da abertura da
                  B3 com o que o Indice/Dolar fizeram DEPOIS da abertura nesse
                  mesmo dia. E o insumo bruto pro estudo de ML discutido com
                  o usuario (2026-09-22/23) — nao treina nada ainda, so
                  produz a tabela situacao->resultado que um modelo
                  (regressao logistica / arvore / gradient boosting raso,
                  com validacao walk-forward) vai consumir depois. Ver nota
                  "Ideia em aberto" no arquitetura.md do projeto.

                  Le direto do parquet ja coletado por historico.py (MTF) —
                  nao conecta no MT5, roda em qualquer maquina com os
                  parquets disponiveis.

                  Definicoes (documentadas aqui pra ficar rastreavel, sao
                  decisao de design, nao verdade absoluta):
                  - "situacao": preco do Usa500/UsaVix no ultimo candle M5
                    disponivel ANTES da abertura do Indice do dia (abertura =
                    primeiro candle M5 do dia do Indice, tipicamente 09:00),
                    comparado ao preco desses mesmos ativos no instante do
                    FECHAMENTO do Indice do pregao anterior (ultimo candle M5
                    do dia util anterior) — e a variacao "overnight" do
                    cesto de risco desde a ultima vez que a B3 fechou.
                    UsaVix entra tambem em NIVEL (nao so variacao), porque
                    volatilidade alta em nivel absoluto ja e um regime de
                    risco por si so, independente de ter subido ou nao
                    nas ultimas horas.
                  - "resultado": retorno do Indice/Dolar da abertura ate 30min
                    depois, ate 60min depois, e ate o fechamento do proprio
                    dia — tres horizontes, pra nao travar numa escolha so
                    de janela antes de ter o modelo rodando.
                  - Alinhamento temporal: merge_asof (backward pro cesto de
                    risco — ultimo preco conhecido ATE o instante-alvo;
                    forward pro alvo INDICE/DOLAR — primeiro candle DISPONIVEL A
                    PARTIR do instante-alvo), robusto a candle faltando por
                    feriado/gap sem quebrar o script.
                  - Cada vencimento (Usa500 e continuo; UsaVix tem subpasta
                    por vigente) e lido concatenando TODAS as subpastas
                    mes-ano existentes + drop_duplicates(subset="time") —
                    na pratica cada ticker da corretora internacional ja carrega
                    historico continuo multi-ano por tras do nome do
                    vigente atual (validado empiricamente: Dolar/UsaVix
                    2026-09-23 mostraram ~719 dias de profundidade numa
                    unica subpasta, apos o reforco de M5 via
                    `historico.py --reforcar M5:720`), mas concatenar todas
                    as subpastas deixa o script correto tambem se isso
                    mudar no futuro (rollover criando serie realmente
                    segmentada).
Autor          : Julio Cesar Silvio Campanhola
Criado em      : 2026-09-23
Ultima edicao  : 2026-09-23
Versao         : 1.0.0
Projeto        : dashboard
Historico      : scripts_py/versoes/situacao_pre_abertura.md
"""

import glob
import importlib
import os

try:
    pd = importlib.import_module("pandas")
except ImportError as exc:
    raise ImportError(
        "A dependencia pandas nao esta instalada. "
        "Instale-a com: pip install pandas pyarrow"
    ) from exc


class ConstrutorSituacaoPreAbertura:
    """Monta o dataset situacao (cesto de risco pre-abertura) -> resultado
    (retorno do Indice/Dolar pos-abertura), uma linha por pregao."""

    # janelas de retorno pos-abertura, em minutos (candle M5 mais proximo
    # disponivel A PARTIR do instante alvo = abertura + janela)
    JANELAS_MINUTOS = {"30m": 30, "60m": 60}

    def __init__(self, base_dir=None):
        self.base_dir = base_dir or os.path.dirname(os.path.abspath(__file__))
        self.mtf_dir = os.path.join(self.base_dir, "..", "parquet", "historicos", "MTF")
        self.saida_path = os.path.join(
            self.base_dir, "..", "parquet", "calculos", "situacao_pre_abertura.parquet"
        )

    # -- leitura -----------------------------------------------------------

    def _carregar_m5(self, raiz):
        """Le e concatena TODOS os m5.parquet de uma raiz (direto na pasta,
        ou em qualquer subpasta mes-ano de vencimento), dedup por time."""
        pasta_raiz = os.path.join(self.mtf_dir, raiz)
        # subpasta de vencimento e sempre "MM-AAAA" - padrao restrito evita
        # pegar a subpasta "indicadores" (schema diferente: ifr/atr/macd)
        candidatos = sorted(glob.glob(os.path.join(pasta_raiz, "m5.parquet"))) + sorted(
            glob.glob(os.path.join(pasta_raiz, "[0-9][0-9]-[0-9][0-9][0-9][0-9]", "m5.parquet"))
        )
        if not candidatos:
            raise FileNotFoundError(f"Nenhum m5.parquet encontrado pra {raiz!r} em {pasta_raiz}")

        partes = [pd.read_parquet(c, columns=["time", "open", "high", "low", "close"]) for c in candidatos]
        df = pd.concat(partes, ignore_index=True)
        df = df.drop_duplicates(subset="time", keep="last").sort_values("time").reset_index(drop=True)
        return df

    # -- montagem ------------------------------------------------------------

    def _dias_de_pregao(self, df_alvo):
        """Devolve, por dia (date), o instante de abertura (primeiro candle)
        e de fechamento (ultimo candle) do ativo-alvo (Indice ou Dolar)."""
        df_alvo = df_alvo.copy()
        df_alvo["dia"] = df_alvo["time"].dt.date
        agg = df_alvo.groupby("dia")["time"].agg(abertura="min", fechamento="max")
        agg = agg.sort_index()
        # preco de abertura/fechamento de cada dia, pra calcular retorno
        aberturas = df_alvo.merge(agg[["abertura"]].reset_index(), left_on=["dia", "time"], right_on=["dia", "abertura"])
        aberturas = aberturas.set_index("dia")["open"].rename("preco_abertura")
        fechamentos = df_alvo.merge(agg[["fechamento"]].reset_index(), left_on=["dia", "time"], right_on=["dia", "fechamento"])
        fechamentos = fechamentos.set_index("dia")["close"].rename("preco_fechamento")
        agg = agg.join(aberturas).join(fechamentos)
        return agg

    def _situacao_cesto(self, df_cesto, instantes, prefixo):
        """merge_asof backward: ultimo preco do df_cesto conhecido ATE cada
        instante (Series de Timestamp). Devolve Series alinhada a
        `instantes`, mesmo index."""
        # merge_asof nao aceita chave nula (o primeiro dia da serie nao
        # tem fechamento anterior, vira NaT) - filtra, mescla, e devolve
        # com o index original (NaN nas linhas filtradas, tratadas depois
        # pelo dropna de colunas essenciais em construir()).
        instantes_validos = instantes.dropna()
        base = pd.DataFrame({"instante": instantes_validos}, index=instantes_validos.index).sort_values("instante")
        resultado = pd.merge_asof(
            base, df_cesto[["time", "close"]].rename(columns={"time": "instante"}),
            on="instante", direction="backward", tolerance=pd.Timedelta(hours=6),
        )
        resultado.index = base.index
        return resultado["close"].reindex(instantes.index).rename(prefixo)

    def _resultado_alvo(self, df_alvo, dias, sufixo):
        """Pra cada dia, calcula o retorno da abertura ate abertura+30m,
        +60m (merge_asof forward — primeiro candle disponivel a partir do
        instante alvo) e ate o fechamento do proprio dia (ja calculado em
        `dias`)."""
        saida = pd.DataFrame(index=dias.index)
        base_alvo = df_alvo[["time", "close"]].sort_values("time")

        for rotulo, minutos in self.JANELAS_MINUTOS.items():
            instantes = (dias["abertura"] + pd.Timedelta(minutes=minutos)).dt.as_unit("us")
            instantes_validos = instantes.dropna()
            base = pd.DataFrame({"instante": instantes_validos}, index=instantes_validos.index).sort_values("instante")
            merged = pd.merge_asof(
                base, base_alvo.rename(columns={"time": "instante"}),
                on="instante", direction="forward", tolerance=pd.Timedelta(minutes=15),
            )
            merged.index = base.index
            preco_horizonte = merged["close"].reindex(dias.index)
            saida[f"{sufixo}_retorno_{rotulo}"] = preco_horizonte / dias["preco_abertura"] - 1

        saida[f"{sufixo}_retorno_dia"] = dias["preco_fechamento"] / dias["preco_abertura"] - 1
        return saida

    def construir(self):
        indice = self._carregar_m5("Indice")
        dolar = self._carregar_m5("Dolar")
        usa500 = self._carregar_m5("Usa500")
        usavix = self._carregar_m5("UsaVix")

        dias_indice = self._dias_de_pregao(indice)
        # Dolar tem seu proprio preco de abertura/fechamento (nao pode
        # reaproveitar o preco do Indice so porque a sessao e a mesma) - mas
        # alinha pelo calendario de pregao do Indice (indice mestre do
        # dataset), pro caso raro de um dos dois faltar candle num dia que
        # o outro tem.
        dias_dolar = self._dias_de_pregao(dolar).reindex(dias_indice.index)

        # fechamento do pregao ANTERIOR (shift 1 na linha do tempo de dias
        # de pregao do Indice — respeita feriados/fins de semana automaticamente,
        # nao e so "dia - 1")
        fechamento_anterior = dias_indice["fechamento"].shift(1).rename("instante_fech_anterior")
        corte_pre_abertura = (dias_indice["abertura"] - pd.Timedelta(minutes=5)).dt.as_unit("us").rename("instante_pre_abertura")

        situacao = pd.DataFrame(index=dias_indice.index)
        situacao["usa500_fech_anterior"] = self._situacao_cesto(usa500, fechamento_anterior, "usa500_fech_anterior")
        situacao["usa500_pre_abertura"] = self._situacao_cesto(usa500, corte_pre_abertura, "usa500_pre_abertura")
        situacao["usa500_var_pre_pct"] = situacao["usa500_pre_abertura"] / situacao["usa500_fech_anterior"] - 1

        situacao["usavix_fech_anterior"] = self._situacao_cesto(usavix, fechamento_anterior, "usavix_fech_anterior")
        situacao["usavix_pre_abertura"] = self._situacao_cesto(usavix, corte_pre_abertura, "usavix_pre_abertura")
        situacao["usavix_var_pre_pct"] = situacao["usavix_pre_abertura"] / situacao["usavix_fech_anterior"] - 1
        situacao["usavix_nivel_pre"] = situacao["usavix_pre_abertura"]

        resultado_indice = self._resultado_alvo(indice, dias_indice, "indice")
        resultado_dolar = self._resultado_alvo(dolar, dias_dolar, "dolar")

        dataset = pd.concat([situacao, resultado_indice, resultado_dolar], axis=1)
        dataset = dataset.reset_index().rename(columns={"dia": "pregao"})

        # descarta linhas sem situacao completa (primeiro dia da serie, sem
        # fechamento anterior) ou sem resultado (dia mais recente, ainda
        # sem candle de fechamento formado)
        colunas_essenciais = [
            "usa500_var_pre_pct", "usavix_var_pre_pct", "usavix_nivel_pre",
            "indice_retorno_60m", "dolar_retorno_60m",
        ]
        antes = len(dataset)
        dataset = dataset.dropna(subset=colunas_essenciais).reset_index(drop=True)
        descartadas = antes - len(dataset)

        return dataset, descartadas

    def salvar(self, dataset):
        os.makedirs(os.path.dirname(self.saida_path), exist_ok=True)
        dataset.to_parquet(self.saida_path, index=False)
        return self.saida_path


if __name__ == "__main__":
    construtor = ConstrutorSituacaoPreAbertura()
    dataset, descartadas = construtor.construir()
    caminho = construtor.salvar(dataset)

    print(f"Dataset salvo em: {caminho}")
    print(f"{len(dataset)} pregoes completos (descartadas {descartadas} linhas incompletas nas pontas da serie)")
    if len(dataset):
        print(f"Periodo: {dataset['pregao'].min()} -> {dataset['pregao'].max()}")
        print()
        print(dataset.describe().T[["count", "mean", "std", "min", "max"]])
