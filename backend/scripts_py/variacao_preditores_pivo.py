"""
Nome do script : variacao_preditores_pivo.py
Descricao      : Registra a variacao REAL (minuto a minuto, retorno %
                  desde a abertura) de cada preditor com causalidade de
                  Granger confirmada (Gi -> causa_indice, dg -> causa_dolar,
                  lag=1), durante a MESMA janela em que o Indice/Dolar forma
                  seu primeiro pivo fractal (ver impulso_abertura.py 1.2.0,
                  campo candles_ate_pivo_fractal) -- SEM resumir isso a um
                  coeficiente de correlacao ou p-valor de antemao.

                  Pedido do usuario 2026-09-30, depois de ver o reteste de
                  causalidade_overnight.py: "primeiro pegue toda a serie
                  historica de M1 dos ativos DOLAR e INDICE, conte quantos
                  candles em media se formam antes do 1o pivo, e e ai que
                  ta o pulo do gato, voce tem que guardar a variacao dos
                  ativos gi e dg, para saber como o mercado se comporta
                  naquela janela de tempo independente de correlacao".

                  Diferenca crucial em relacao a preditores_overnight.py:
                  aquele mede o retorno do preditor ANTES da abertura
                  (fechamento do pregao anterior -> abertura de hoje --
                  uma janela "overnight", o preditor ja tinha se mexido
                  antes do Dolar/Indice abrir). Este aqui mede o retorno do
                  preditor DURANTE a janela em que o Indice/Dolar esta
                  formando o pivo -- ou seja, o preditor (GOLD/ChinaA50/
                  GBPUSD/USDSEK negociam ~24h) continua se mexendo AO
                  MESMO TEMPO que a B3 abre. Nao e mais "o overnight
                  prediz a abertura" -- e "o mercado global inteiro (B3 +
                  forex/commodities) se move junto, ao mesmo tempo, e da
                  pra literalmente ver isso acontecendo minuto a minuto".

                  Metodo: pra cada dia com pivo fractal detectado, pega o
                  path do preditor (retorno % acumulado desde o MESMO
                  horario_abertura do alvo) minuto a minuto ate
                  MAX_OFFSET_MIN, truncado no candles_ate_pivo_fractal
                  daquele dia (nao extrapola alem do pivo). Agrupa os dias
                  por tipo_pivo_fractal do alvo (alta/baixa) e tira a
                  MEDIA simples do path em cada minuto -- sem regressao,
                  sem p-valor, so a media crua da variacao real. Se o
                  preditor realmente acompanha o alvo, os dois grupos
                  (alta/baixa) devem divergir visivelmente com o passar
                  dos minutos.

                  Resultado (Dolar, 2026-09-30, 123 dias, 63 alta/60 baixa):
                  USDSEK e GBPUSD mostram divergencia clara e crescente
                  entre os grupos alta/baixa (USDSEK: +0,018% nos dias de
                  alta do Dolar vs -0,025% nos dias de baixa, no minuto 10;
                  GBPUSD move na direcao OPOSTA do Dolar, o que faz sentido
                  -- USD mais forte = GBPUSD cai E Dolar sobe, e USD mais
                  fraco = os dois invertem). GOLD e ChinaA50 NAO mostram
                  divergencia clara (paths dos dois grupos ficam
                  emaranhados, sem separacao consistente). Isso concorda
                  com causalidade_overnight.py (GBPUSD/USDSEK sobrevivem,
                  GOLD fica limitrofe, ChinaA50 morre) mas muda a
                  INTERPRETACAO: nao e um preditor "antecedente" (overnight
                  -> abertura) -- e um sinal de CONFIRMACAO EM TEMPO REAL
                  (o mercado forex, que continua aberto, mostra o mesmo
                  movimento que a B3 esta fazendo, ao vivo, enquanto o
                  pivo se forma).

                  Grava parquet/calculos/variacaoPreditoresPivo.parquet
                  (long format: ativo_alvo, preditor, minuto_offset,
                  tipo_pivo, retorno_medio_pct, n_dias).
Autor          : Julio Cesar Silvio Campanhola
Criado em      : 2026-09-30
Versao         : 1.0.0
Projeto        : dashboard
Historico      : scripts_py/versoes/variacao_preditores_pivo.md
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

MAX_OFFSET_MIN = 15  # cobre ate o p90 do candles_ate_pivo_fractal (~13)
BROKER_PREDITORES = "corretora internacional"

ALVOS = {
    "Indice": {"coluna_causa": "causa_indice", "coluna_lag": "causa_indice_lag"},
    "Dolar": {"coluna_causa": "causa_dolar", "coluna_lag": "causa_dolar_lag"},
}
LAG_ESTUDADO = 1


def _base_dir():
    return os.path.dirname(os.path.abspath(__file__))


def _caminho_mtf(raiz):
    return os.path.join(_base_dir(), "..", "parquet", "historicos", "MTF", raiz, "M1.parquet")


def listar_preditores(coluna_causa, coluna_lag):
    caminho = os.path.join(_base_dir(), "..", "parquet", "calculos", "causalidadeD1.parquet")
    df = pd.read_parquet(caminho)
    filtro = (
        (df["broker"] == BROKER_PREDITORES)
        & (df[coluna_causa] == True)  # noqa: E712
        & (df[coluna_lag] == LAG_ESTUDADO)
    )
    return sorted(df.loc[filtro, "symbol"].tolist())


def _dias_com_pivo(ativo_alvo):
    """Le impulsoAbertura.parquet (ja gerado por impulso_abertura.py
    1.2.0) e devolve so os dias com pivo fractal detectado pro ativo."""
    caminho = os.path.join(_base_dir(), "..", "parquet", "calculos", "impulsoAbertura.parquet")
    df = pd.read_parquet(caminho)
    df = df[df["ativo"] == ativo_alvo].dropna(subset=["candles_ate_pivo_fractal"]).copy()
    df["horario_abertura"] = pd.to_datetime(df["horario_abertura"]).astype("datetime64[ns]")
    return df


def _path_preditor_por_dia(raiz_preditor, dias_com_pivo):
    """Pra cada dia, path do preditor (retorno % desde o preco na
    horario_abertura DO ALVO) minuto a minuto ate MAX_OFFSET_MIN, truncado
    no candles_ate_pivo_fractal daquele dia. Devolve lista de dicts
    {tipo_pivo, path} (path = array numpy de tamanho MAX_OFFSET_MIN+1,
    com NaN a partir do pivo)."""
    m1 = pd.read_parquet(_caminho_mtf(raiz_preditor), columns=["time", "close"]).sort_values("time")
    m1["time"] = pd.to_datetime(m1["time"]).dt.tz_localize(None).astype("datetime64[ns]")

    resultado = []
    for _, linha in dias_com_pivo.iterrows():
        abertura = linha["horario_abertura"]
        instantes = pd.to_datetime(
            [abertura + pd.Timedelta(minutes=k) for k in range(MAX_OFFSET_MIN + 1)]
        ).astype("datetime64[ns]")
        alvo_df = pd.DataFrame({"instante": instantes})
        fundido = pd.merge_asof(
            alvo_df, m1, left_on="instante", right_on="time",
            direction="backward", tolerance=pd.Timedelta(minutes=10),
        )
        precos = fundido["close"].to_numpy(dtype=float)
        if np.isnan(precos[0]) or precos[0] == 0:
            continue
        path = (precos - precos[0]) / precos[0] * 100
        limite = int(min(linha["candles_ate_pivo_fractal"], MAX_OFFSET_MIN))
        path[limite + 1:] = np.nan
        resultado.append({"tipo_pivo": linha["tipo_pivo_fractal"], "path": path})
    return resultado


def montar_tabela(ativo_alvo):
    info = ALVOS[ativo_alvo]
    dias_com_pivo = _dias_com_pivo(ativo_alvo)
    preditores = listar_preditores(info["coluna_causa"], info["coluna_lag"])

    linhas = []
    for preditor in preditores:
        caminhos = _path_preditor_por_dia(preditor, dias_com_pivo)
        for tipo in ("alta", "baixa"):
            matriz = np.array([d["path"] for d in caminhos if d["tipo_pivo"] == tipo])
            if matriz.size == 0:
                continue
            media = np.nanmean(matriz, axis=0)
            n_por_minuto = np.sum(~np.isnan(matriz), axis=0)
            for minuto in range(MAX_OFFSET_MIN + 1):
                linhas.append({
                    "ativo_alvo": ativo_alvo,
                    "preditor": preditor,
                    "tipo_pivo": tipo,
                    "minuto_offset": minuto,
                    "retorno_medio_pct": round(float(media[minuto]), 5) if not np.isnan(media[minuto]) else None,
                    "n_dias": int(n_por_minuto[minuto]),
                })
    return pd.DataFrame(linhas), preditores


def executar():
    partes = []
    for ativo_alvo in ALVOS:
        tabela, preditores = montar_tabela(ativo_alvo)
        if tabela.empty:
            print(f"{ativo_alvo}: sem preditores lag={LAG_ESTUDADO} com historico suficiente, pulando.")
            continue
        partes.append(tabela)

        print(f"=== {ativo_alvo} -- variacao dos preditores durante a janela do pivo (preditores: {preditores}) ===")
        for preditor in preditores:
            sub = tabela[tabela["preditor"] == preditor]
            if sub.empty:
                continue
            pivo10_alta = sub[(sub["tipo_pivo"] == "alta") & (sub["minuto_offset"] == 10)]
            pivo10_baixa = sub[(sub["tipo_pivo"] == "baixa") & (sub["minuto_offset"] == 10)]
            v_alta = pivo10_alta["retorno_medio_pct"].iloc[0] if len(pivo10_alta) else None
            v_baixa = pivo10_baixa["retorno_medio_pct"].iloc[0] if len(pivo10_baixa) else None
            print(f"  {preditor:12s} no minuto 10: dias 'alta'={v_alta} | dias 'baixa'={v_baixa}")
        print()

    if not partes:
        print("Nada pra gravar.")
        return None

    saida = pd.concat(partes, ignore_index=True)
    caminho = os.path.join(_base_dir(), "..", "parquet", "calculos", "variacaoPreditoresPivo.parquet")
    saida.to_parquet(caminho, index=False)
    print(f"Salvo: {os.path.abspath(caminho)} ({len(saida)} linhas)")
    return saida


if __name__ == "__main__":
    executar()
