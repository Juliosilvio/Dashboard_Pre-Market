"""
Nome do script : variacao_universo_pivo.py
Descricao      : Mesma ideia de variacao_preditores_pivo.py (variacao REAL
                  de preco de um ativo durante a MESMA janela em que o
                  Indice/Dolar forma seu primeiro pivo fractal -- ver
                  impulso_abertura.py 1.2.0), mas SEM filtrar por
                  causalidade de Granger nem por correlacao previa: varre
                  TODO o universo de ativos com M1 disponivel em
                  parquet/historicos/MTF (menos os proprios alvos).

                  Pedido do usuario 2026-09-30, depois de ver o resultado
                  de variacao_preditores_pivo.py (so 4 preditores, os ja
                  confirmados por causalidadeD1.parquet): "nem 1 e nem 2
                  por enquanto, teste em mais ativos independente de
                  correlacao ou causalidade, quero a variacao intracandles
                  d1 desses ativos".

                  Metrica principal: NAO um minuto fixo (tipo minuto 10).
                  A mediana de candles_ate_pivo_fractal e so 6 -- um corte
                  fixo em qualquer minuto >6 ja descarta a maioria dos dias
                  "rapidos" e sobra uma amostra pequena e enviesada pros
                  dias "lentos" (1.0.0/1.1.0 tinham exatamente esse
                  problema: GOLD/GBPUSD/ChinaA50/USDSEK apareciam com
                  n=8~25 dias em vez dos ~123 disponiveis). A partir da
                  1.2.0 a metrica e o retorno do candidato exatamente NO
                  CANDLE em que o alvo formou o pivo (timing alinhado por
                  dia, minuto_offset=-1 na tabela) -- usa todos os dias
                  disponiveis, sem vies de velocidade.

                  Baseline flexivel (1.3.0): o preco de referencia de cada
                  dia e o PRIMEIRO preco disponivel do candidato na janela,
                  nao necessariamente o do minuto exato da abertura do
                  alvo. Ativos com sessao mais estreita que a do Indice/Dolar
                  (ex: USDBRL so comeca a negociar ~5min depois da abertura
                  do B3) tinham TODOS os dias descartados por causa disso,
                  nao por falta de dado real.

                  Achado de estrutura de mercado (nao e bug): dos ~125
                  candidatos varridos, so ~19 tem QUALQUER preco disponivel
                  durante a janela de abertura do B3 (09h BRT). O resto
                  (a maioria: acoes americanas individuais tipo AAPL/MSFT/
                  NVDA, ETFs de renda fixa, DI1, Brent/Gasol/commodities
                  locais) segue horario de pregao regional fixo e
                  simplesmente NAO ESTA ABERTO as 9h BRT -- nao da pra
                  achar sinal de "confirmacao em tempo real" num mercado
                  fechado. So sobrevivem ativos que negociam ~24h (forex,
                  CFDs de indice, GOLD) ou cuja sessao alcanca esse
                  horario (USDBRL).

                  Resultado (2026-09-30, valor no candle do pivo):
                  alem dos 4 ja conhecidos (GOLD/GBPUSD/ChinaA50/USDSEK,
                  123 dias cada, divergencia pequena a moderada e na
                  direcao esperada de "forca do dolar"), o universo amplo
                  revelou USDMXN e Euro50 com divergencia MAIOR que
                  qualquer um dos 4 originais tanto pro Indice quanto pro
                  Dolar (USDMXN: -0.063 Indice / +0.055 Dolar; Euro50: +0.062
                  Indice / -0.037 Dolar), e Usa500/UsaInd/UsaTec (CFDs de
                  indice americano, com pre-market ja aberto as 9h BRT)
                  tambem com divergencia consistente com "risco global"
                  (sobem com o Indice, caem com o Dolar). USDZAR e USDJPY
                  reforcam o padrao classico de forca do dolar. USDTRY fica
                  essencialmente zerado (sem sinal). USDBRL e USDRUB tem
                  sinal aparente mas com n_dias baixo (8-19 num universo de
                  ~29-35 dias possiveis) -- tratar como hipotese, nao
                  conclusao, ate rodar historico.py --reforcar --so USDBRL,
                  USDRUB e ter mais profundidade. IMPORTANTE: isso e SO a
                  variacao crua (media simples, sem regressao/p-valor) --
                  serve pra apontar candidatos, nao pra validar
                  estatisticamente nenhum deles (isso e o Task #12,
                  backtest fora da amostra).

                  Grava parquet/calculos/variacaoUniversoPivo.parquet (long
                  format: ativo_alvo, preditor, minuto_offset, tipo_pivo,
                  retorno_medio_pct, n_dias -- minuto_offset=-1 e o valor
                  no candle do pivo, os demais sao o path minuto a minuto
                  pra quem quiser o formato completo). O console imprime,
                  por alvo, o ranking dos ativos com maior divergencia
                  |alta-baixa| no candle do pivo, com n_dias de cada grupo
                  (pra deixar claro quais tem base solida e quais nao).
Autor          : Julio Cesar Silvio Campanhola
Criado em      : 2026-09-30
Versao         : 1.3.0
Projeto        : dashboard
Historico      : scripts_py/versoes/variacao_universo_pivo.md
"""

import importlib
import os

try:
    pd = importlib.import_module("pandas")
    np = importlib.import_module("numpy")
except ImportError as exc:
    raise ImportError(
        "A dependencia pandas/numpy nao esta instalada. "
        "Instale-as com: pip install pandas pyarrow numpy"
    ) from exc

MAX_OFFSET_MIN = 30  # cobre o MAXIMO real de candles_ate_pivo_fractal (27 Indice, 20 Dolar)
MIN_DIAS_RESUMO = 10  # abaixo disso, marca "dados insuficientes" no ranking

ALVOS = ["Indice", "Dolar"]


def _base_dir():
    return os.path.dirname(os.path.abspath(__file__))


def _caminho_mtf(raiz):
    return os.path.join(_base_dir(), "..", "parquet", "historicos", "MTF", raiz, "M1.parquet")


def _listar_universo():
    """Toda raiz com M1.parquet direto em parquet/historicos/MTF, menos os
    proprios alvos. Pastas de vencimento cru (Indice/Dolar/DOLAR, que guardam
    parquet por mes em vez de um M1.parquet consolidado) ficam de fora
    naturalmente -- nao tem esse arquivo no caminho esperado."""
    base = os.path.join(_base_dir(), "..", "parquet", "historicos", "MTF")
    raizes = []
    for nome in sorted(os.listdir(base)):
        if nome in ALVOS:
            continue
        if os.path.isfile(os.path.join(base, nome, "M1.parquet")):
            raizes.append(nome)
    return raizes


def _dias_com_pivo(ativo_alvo):
    """Le impulsoAbertura.parquet (ja gerado por impulso_abertura.py 1.2.0)
    e devolve so os dias com pivo fractal detectado pro ativo."""
    caminho = os.path.join(_base_dir(), "..", "parquet", "calculos", "impulsoAbertura.parquet")
    df = pd.read_parquet(caminho)
    df = df[df["ativo"] == ativo_alvo].dropna(subset=["candles_ate_pivo_fractal"]).copy()
    df["horario_abertura"] = pd.to_datetime(df["horario_abertura"]).astype("datetime64[ns]")
    return df


def _path_preditor_por_dia(raiz_preditor, dias_com_pivo):
    """Pra cada dia, path do ativo candidato (retorno % desde o preco na
    horario_abertura DO ALVO) minuto a minuto ate MAX_OFFSET_MIN, truncado
    no candles_ate_pivo_fractal daquele dia. Devolve lista de dicts
    {tipo_pivo, path}.

    Versao vetorizada (1.1.0): faz UM merge_asof so pra todos os dias de
    uma vez (em vez de um merge_asof por dia) -- com ~140 candidatos no
    universo, um merge_asof por dia por candidato (123 dias x 140 ativos =
    milhares de merges pequenos) estourava o tempo de execucao. Aqui monta
    uma tabela longa (dia_idx, minuto, instante) com todos os instantes de
    todos os dias, ordena por instante, faz UM merge_asof contra o M1 do
    candidato, e reagrupa por dia_idx depois -- mesmo resultado, muito mais
    rapido."""
    m1 = pd.read_parquet(_caminho_mtf(raiz_preditor), columns=["time", "close"]).sort_values("time")
    m1["time"] = pd.to_datetime(m1["time"]).dt.tz_localize(None).astype("datetime64[ns]")

    dias_reset = dias_com_pivo.reset_index(drop=True)
    registros = []
    for idx, linha in dias_reset.iterrows():
        abertura = linha["horario_abertura"]
        for k in range(MAX_OFFSET_MIN + 1):
            registros.append((idx, k, abertura + pd.Timedelta(minutes=k)))
    longa = pd.DataFrame(registros, columns=["dia_idx", "minuto", "instante"])
    longa["instante"] = pd.to_datetime(longa["instante"]).astype("datetime64[ns]")
    longa = longa.sort_values("instante")

    fundido = pd.merge_asof(
        longa, m1, left_on="instante", right_on="time",
        direction="backward", tolerance=pd.Timedelta(minutes=10),
    )
    grupos = dict(tuple(fundido.groupby("dia_idx")))

    resultado = []
    for idx, linha in dias_reset.iterrows():
        sub = grupos.get(idx)
        if sub is None:
            continue
        sub = sub.sort_values("minuto")
        precos = sub["close"].to_numpy(dtype=float)
        if len(precos) == 0:
            continue

        # baseline flexivel (1.3.0): usa o primeiro preco DISPONIVEL na
        # janela como referencia, nao necessariamente o minuto 0 exato --
        # ativos com sessao mais estreita que a do alvo (ex: USDBRL so
        # comeca a negociar ~5min depois da abertura do Indice/Dolar) sempre
        # tinham precos[0]==NaN e eram descartados por INTEIRO, todo santo
        # dia -- nao por falta de dado real, so por causa do ponto de
        # partida escolhido. Com isso, o path fica NaN antes do ativo abrir
        # (correto -- ele realmente nao tinha preco ainda) e valido a partir
        # dali, sem descartar o dia inteiro.
        validos = ~np.isnan(precos)
        if not validos.any():
            continue
        idx_base = int(np.argmax(validos))
        preco_base = precos[idx_base]
        if preco_base == 0:
            continue

        path = np.full(len(precos), np.nan)
        path[idx_base:] = (precos[idx_base:] - preco_base) / preco_base * 100

        limite = int(min(linha["candles_ate_pivo_fractal"], MAX_OFFSET_MIN))
        if limite < idx_base or np.isnan(path[limite]):
            # o ativo ainda nem tinha preco no candle em que o pivo do alvo
            # se formou -- nao da pra comparar esse dia pra esse ativo
            continue
        retorno_no_pivo = float(path[limite])
        path[limite + 1:] = np.nan
        resultado.append({
            "tipo_pivo": linha["tipo_pivo_fractal"],
            "path": path,
            "retorno_no_pivo": retorno_no_pivo,
        })
    return resultado


def montar_tabela(ativo_alvo):
    dias_com_pivo = _dias_com_pivo(ativo_alvo)
    universo = _listar_universo()

    linhas = []
    for candidato in universo:
        try:
            caminhos = _path_preditor_por_dia(candidato, dias_com_pivo)
        except Exception as exc:
            print(f"  [pulando {candidato}: {exc}]")
            continue
        for tipo in ("alta", "baixa"):
            matriz = np.array([d["path"] for d in caminhos if d["tipo_pivo"] == tipo])
            if matriz.size == 0:
                continue
            media = np.nanmean(matriz, axis=0)
            n_por_minuto = np.sum(~np.isnan(matriz), axis=0)
            for minuto in range(MAX_OFFSET_MIN + 1):
                linhas.append({
                    "ativo_alvo": ativo_alvo,
                    "preditor": candidato,
                    "tipo_pivo": tipo,
                    "minuto_offset": minuto,
                    "retorno_medio_pct": round(float(media[minuto]), 5) if not np.isnan(media[minuto]) else None,
                    "n_dias": int(n_por_minuto[minuto]),
                })

            no_pivo_vals = [d["retorno_no_pivo"] for d in caminhos if d["tipo_pivo"] == tipo]
            if no_pivo_vals:
                linhas.append({
                    "ativo_alvo": ativo_alvo,
                    "preditor": candidato,
                    "tipo_pivo": tipo,
                    "minuto_offset": -1,  # sentinela: valor NO candle do pivo, timing alinhado por dia
                    "retorno_medio_pct": round(float(np.mean(no_pivo_vals)), 5),
                    "n_dias": len(no_pivo_vals),
                })
    return pd.DataFrame(linhas), universo


def _ranking_resumo(tabela):
    """Por candidato, pega alta/baixa NO CANDLE DO PIVO (minuto_offset=-1 --
    timing alinhado por dia, usa todos os dias) e ordena por |diferenca|
    desc -- ranking rapido pra escanear um universo grande. Evita o vies
    de escolher um minuto fixo tipo 10: como a mediana de candles_ate_pivo_
    fractal e so 6, um corte fixo em 10 descartaria a maioria dos dias
    'rapidos' e sobraria so uma amostra pequena e enviesada pros dias
    'lentos' (achado real do proprio estudo, ver impulso_abertura.py)."""
    sub = tabela[tabela["minuto_offset"] == -1]
    linhas = []
    for candidato, grupo in sub.groupby("preditor"):
        alta = grupo[grupo["tipo_pivo"] == "alta"]
        baixa = grupo[grupo["tipo_pivo"] == "baixa"]
        if alta.empty or baixa.empty:
            continue
        v_alta = alta["retorno_medio_pct"].iloc[0]
        v_baixa = baixa["retorno_medio_pct"].iloc[0]
        if v_alta is None or v_baixa is None:
            continue
        n_alta = int(alta["n_dias"].iloc[0])
        n_baixa = int(baixa["n_dias"].iloc[0])
        linhas.append({
            "preditor": candidato,
            "retorno_alta": v_alta,
            "retorno_baixa": v_baixa,
            "diverge": round(v_alta - v_baixa, 5),
            "n_dias_alta": n_alta,
            "n_dias_baixa": n_baixa,
            "dados_suficientes": bool(min(n_alta, n_baixa) >= MIN_DIAS_RESUMO),
        })
    ranking = pd.DataFrame(linhas)
    if ranking.empty:
        return ranking
    return ranking.reindex(ranking["diverge"].abs().sort_values(ascending=False).index)


def executar():
    partes = []
    for ativo_alvo in ALVOS:
        print(f"=== {ativo_alvo}: varrendo universo amplo (sem filtro de causalidade/correlacao) ===")
        tabela, universo = montar_tabela(ativo_alvo)
        if tabela.empty:
            print(f"{ativo_alvo}: nenhum candidato com dado util, pulando.")
            continue
        partes.append(tabela)

        ranking = _ranking_resumo(tabela)
        print(f"{len(universo)} candidatos testados | ranking por divergencia |alta-baixa| NO CANDLE DO PIVO (timing alinhado por dia):")
        for _, linha in ranking.head(20).iterrows():
            marca = "" if linha["dados_suficientes"] else "  [DADOS INSUFICIENTES, ignorar por ora]"
            print(
                f"  {linha['preditor']:10s} alta={linha['retorno_alta']:+.5f}% baixa={linha['retorno_baixa']:+.5f}% "
                f"diverge={linha['diverge']:+.5f} (n_alta={linha['n_dias_alta']}, n_baixa={linha['n_dias_baixa']}){marca}"
            )
        print()

    if not partes:
        print("Nada pra gravar.")
        return None

    saida = pd.concat(partes, ignore_index=True)
    caminho = os.path.join(_base_dir(), "..", "parquet", "calculos", "variacaoUniversoPivo.parquet")
    saida.to_parquet(caminho, index=False)
    print(f"Salvo: {os.path.abspath(caminho)} ({len(saida)} linhas)")
    return saida


if __name__ == "__main__":
    executar()
