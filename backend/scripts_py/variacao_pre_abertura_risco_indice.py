"""
Nome do script : variacao_pre_abertura_risco_indice.py
Descricao      : Monta um ARQUIVO com a serie historica intraday (OHLC) e
                  as variacoes (retorno % acumulado dentro da janela) de
                  TODOS os ativos que aparecem na tabela "Risco Indice" do
                  frontend (QuotesTable.jsx), no periodo ANTES das 09:00
                  (abertura do Indice), pra todos os dias disponiveis.

                  Pedido do usuario 2026-09-30, depois de ver o resultado
                  de variacao_universo_pivo.py (variacao DEPOIS da
                  abertura): "ainda nao entendeu, vamos la monte um
                  arquivo com as variacoes intraday (como uma serie
                  historica e variacoes) de todos os ativos de
                  RiscoIndice, antes das 09:00 de N dias em uma serie
                  historica. entendeu? assim poderemos pegar esses 3
                  candles que voce disse que forma antes do 1o pivot."

                  Diferenca crucial em relacao a tudo que veio antes: os
                  scripts anteriores (preditores_overnight.py, causalidade_
                  overnight.py, variacao_preditores_pivo.py, variacao_
                  universo_pivo.py) sempre resumiam a janela PRE-abertura a
                  UM numero por dia (retorno overnight fechamento->abertura)
                  ou olhavam a janela DEPOIS da abertura do alvo. Aqui NAO
                  ha resumo nenhum -- e a serie minuto a minuto (OHLC) crua
                  de cada candidato, ANTES das 09:00, guardada como esta,
                  pra depois rodar detectar_pivo_fractal() (mesma funcao de
                  impulso_abertura.py 1.2.0, N=3 candles antes/depois) EM
                  CIMA dela e achar se o candidato ja formou um pivo
                  proprio antes do Indice/Dolar abrir -- um sinal
                  potencialmente PREDITIVO de verdade (antes da abertura),
                  nao so uma confirmacao contemporanea (Passo 6/7).

                  Universo (ativos da tabela "Risco Indice", ver
                  QuotesTable.jsx APELIDOS_ATIVO e config.json):
                  EWZ, USDCAD, USDJPY, USDTRY, USDRUB, USDBRL, Usa500
                  (S&P500), UsaInd (Dow Jones), UsaTec (Nasdaq), UsaVix
                  (VIX), EEM, Brent (Brentfut/Brent -- ver ressalva).

                  Ressalva sobre vencimento (Brent/Dolar/UsaVix): esses 3
                  NAO tem M1.parquet direto na raiz -- moram em subpastas
                  por mes de vencimento (parquet/historicos/MTF/<raiz>/
                  <MM-YYYY>/m1.parquet, minusculo). config.json->vigentes
                  aponta BrentDec26/DolarNov26/UsaVixOct26 como vigentes,
                  mas a pasta com dado real mais recente coletado e
                  Brent/11-2026 (nao existe pasta 12-2026 ainda -- o
                  contrato de dezembro deve ainda nao ter sido coletado),
                  Dolar/11-2026 e UsaVix/10-2026 -- usados aqui por serem
                  os que tem dado ate 2026-09-29/30. "Brentfut" e "Brent"
                  (2 linhas na tabela do usuario) apontam pro MESMO dado
                  coletado (so existe uma serie de Brent no historico) --
                  documentado aqui, nao e erro de duplicar a coluna.
                  "DolFut" = Dolar (contrato especifico vigente do dolar
                  futuro). CORRECAO 2026-10-01 (usuario apontou erro
                  factual aqui): Dolar e Dolar/DolFut sao O MESMO ATIVO
                  (dolar futuro B3, so broker/feed diferente -- ver
                  descricao do projeto) e negociam exatamente o MESMO
                  horario, NAO 24h -- confirmado empiricamente, Dolar so
                  tem candle M1 entre 09h-18h, igual Dolar. A frase
                  anterior aqui ("DolFut, DIFERENTE do Dolar continuo") e
                  "diferente do Dolar (CFD que replica ele mas negocia
                  ~24h)" no changelog estavam ERRADAS -- Dolar nao e CFD
                  24h, isso foi um erro factual meu, nao verificado antes
                  de escrever.

                  Janela: PRE_ABERTURA_MIN minutos antes da abertura do
                  Indice (09:00, com a mesma tolerancia de
                  ABERTURA_MINUTO_TOLERANCIA de impulso_abertura.py) ate a
                  propria abertura, 1 candle M1 por minuto. Guarda OHLC
                  cru + retorno_pct acumulado desde o PRIMEIRO preco
                  disponivel na janela daquele dia (baseline flexivel,
                  mesma logica de variacao_universo_pivo.py 1.3.0 -- ativo
                  com sessao mais curta nao perde o dia inteiro).

                  Grava parquet/calculos/variacaoPreAberturaRiscoIndice.parquet
                  (long format: ativo, data, minutos_antes_abertura
                  [negativo, 0 = candle da propria abertura], horario,
                  open, high, low, close, retorno_pct). Isso e SO o dado
                  cru organizado -- a deteccao de pivo pre-abertura e o
                  proximo passo, depois que o usuario confirmar que a
                  janela/formato aqui estao corretos.
Autor          : Julio Cesar Silvio Campanhola
Criado em      : 2026-09-30
Versao         : 1.0.0
Projeto        : dashboard
Historico      : scripts_py/versoes/variacao_pre_abertura_risco_indice.md
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

ATIVO_REFERENCIA = "Indice"  # abertura usada como relogio pra todo mundo
ABERTURA_HORA_ESPERADA = 9
ABERTURA_MINUTO_TOLERANCIA = 10
PRE_ABERTURA_MIN = 120  # minutos ANTES da abertura cobertos pela janela

# raiz -> caminho relativo (a partir de parquet/historicos/MTF) do arquivo
# m1 -- maioria e "<raiz>/M1.parquet" (continuo), 3 precisam do subpasta
# de vencimento (ver ressalva na docstring)
RISCO_INDICE = {
    "EWZ": "EWZ/M1.parquet",
    "USDCAD": "USDCAD/M1.parquet",
    "USDJPY": "USDJPY/M1.parquet",
    "USDTRY": "USDTRY/M1.parquet",
    "USDRUB": "USDRUB/M1.parquet",
    "USDBRL": "USDBRL/M1.parquet",
    "S&P500": "Usa500/M1.parquet",
    "DowJones": "UsaInd/M1.parquet",
    "Nasdaq": "UsaTec/M1.parquet",
    "VIX": "UsaVix/10-2026/m1.parquet",
    "EEM": "EEM/M1.parquet",
    "Brent": "Brent/11-2026/m1.parquet",
    "Brentfut": "Brent/11-2026/m1.parquet",  # mesmo dado, ver ressalva
    "DolFut": "Dolar/11-2026/m1.parquet",
}


def _base_dir():
    return os.path.dirname(os.path.abspath(__file__))


def _mtf_dir():
    return os.path.join(_base_dir(), "..", "parquet", "historicos", "MTF")


def _dias_abertura(ativo_alvo=ATIVO_REFERENCIA):
    """Horario do 1o candle de cada dia do ativo de referencia (Indice) --
    mesma checagem de gap de impulso_abertura.py (descarta dias com
    abertura fora de 09:00-09:10, que sao gap de coleta, nao abertura
    real)."""
    caminho = os.path.join(_mtf_dir(), ativo_alvo, "M1.parquet")
    df = pd.read_parquet(caminho, columns=["time"])
    df["time"] = pd.to_datetime(df["time"]).dt.tz_localize(None).astype("datetime64[ns]")
    df["data"] = df["time"].dt.date
    aberturas = df.groupby("data")["time"].min().reset_index()
    aberturas.columns = ["data", "horario_abertura"]
    valido = (
        (aberturas["horario_abertura"].dt.hour == ABERTURA_HORA_ESPERADA)
        & (aberturas["horario_abertura"].dt.minute <= ABERTURA_MINUTO_TOLERANCIA)
    )
    return aberturas[valido].reset_index(drop=True)


def _serie_pre_abertura(caminho_relativo, dias):
    """Pra cada dia, OHLC minuto a minuto de PRE_ABERTURA_MIN minutos
    antes da abertura ate a propria abertura (inclusive). Baseline
    flexivel: retorno_pct e relativo ao primeiro close DISPONIVEL na
    janela daquele dia (nao necessariamente o do minuto -PRE_ABERTURA_MIN
    exato) -- evita descartar o dia inteiro quando o candidato tem sessao
    mais curta."""
    caminho = os.path.join(_mtf_dir(), caminho_relativo)
    m1 = pd.read_parquet(caminho, columns=["time", "open", "high", "low", "close"]).sort_values("time")
    m1["time"] = pd.to_datetime(m1["time"]).dt.tz_localize(None).astype("datetime64[ns]")

    dias_reset = dias.reset_index(drop=True)
    registros = []
    for idx, linha in dias_reset.iterrows():
        abertura = linha["horario_abertura"]
        for offset in range(-PRE_ABERTURA_MIN, 1):
            registros.append((idx, offset, abertura + pd.Timedelta(minutes=offset)))
    longa = pd.DataFrame(registros, columns=["dia_idx", "minutos_antes_abertura", "instante"])
    longa["instante"] = pd.to_datetime(longa["instante"]).astype("datetime64[ns]")
    longa = longa.sort_values("instante")

    fundido = pd.merge_asof(
        longa, m1, left_on="instante", right_on="time",
        direction="backward", tolerance=pd.Timedelta(minutes=5),
    )
    grupos = dict(tuple(fundido.groupby("dia_idx")))

    linhas = []
    for idx, linha in dias_reset.iterrows():
        sub = grupos.get(idx)
        if sub is None:
            continue
        sub = sub.sort_values("minutos_antes_abertura").reset_index(drop=True)
        closes = sub["close"].to_numpy(dtype=float)
        validos = ~np.isnan(closes)
        if not validos.any():
            continue
        idx_base = int(np.argmax(validos))
        preco_base = closes[idx_base]
        if preco_base == 0:
            continue
        for i in range(idx_base, len(sub)):
            if np.isnan(sub["close"].iloc[i]):
                continue
            linhas.append({
                "data": linha["data"],
                "minutos_antes_abertura": int(sub["minutos_antes_abertura"].iloc[i]),
                "horario": sub["instante"].iloc[i],
                "open": float(sub["open"].iloc[i]),
                "high": float(sub["high"].iloc[i]),
                "low": float(sub["low"].iloc[i]),
                "close": float(sub["close"].iloc[i]),
                "retorno_pct": round((sub["close"].iloc[i] - preco_base) / preco_base * 100, 5),
            })
    return linhas


def montar():
    dias = _dias_abertura()
    print(f"dias de abertura validos ({ATIVO_REFERENCIA}): {len(dias)}")

    partes = []
    for ativo, caminho_relativo in RISCO_INDICE.items():
        caminho_abs = os.path.join(_mtf_dir(), caminho_relativo)
        if not os.path.isfile(caminho_abs):
            print(f"  [pulando {ativo}: arquivo nao encontrado em {caminho_relativo}]")
            continue
        try:
            linhas = _serie_pre_abertura(caminho_relativo, dias)
        except Exception as exc:
            print(f"  [pulando {ativo}: {exc}]")
            continue
        if not linhas:
            print(f"  [pulando {ativo}: sem dado util na janela pre-abertura]")
            continue
        tabela = pd.DataFrame(linhas)
        tabela.insert(0, "ativo", ativo)
        partes.append(tabela)
        n_dias = tabela["data"].nunique()
        print(f"  {ativo:10s} {n_dias} dias | {len(tabela)} candles | {tabela['minutos_antes_abertura'].min()} a {tabela['minutos_antes_abertura'].max()} min antes da abertura")

    if not partes:
        print("Nada pra gravar.")
        return None

    saida = pd.concat(partes, ignore_index=True)
    caminho = os.path.join(_base_dir(), "..", "parquet", "calculos", "variacaoPreAberturaRiscoIndice.parquet")
    saida.to_parquet(caminho, index=False)
    print(f"Salvo: {os.path.abspath(caminho)} ({len(saida)} linhas)")
    return saida


def executar():
    return montar()


if __name__ == "__main__":
    executar()
