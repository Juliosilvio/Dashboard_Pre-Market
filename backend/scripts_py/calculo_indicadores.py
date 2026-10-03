"""
Nome do script : calculo_indicadores.py
Descricao      : Modulo compartilhado com as formulas de IFR (RSI), ATR e
                  MACD — fonte unica pra nao duplicar/divergir a formula
                  entre quem calcula em lote (indicadores_mtf.py, historico
                  completo da pasta MTF) e quem calcula em tempo real
                  (last_indicadores_nac.py, Indice/Dolar M1/M5). Extraido de
                  indicadores_mtf.py 1.0.0/2.0.0 (que tinha essas formulas
                  como metodo de classe) nesta rodada, junto da criacao do
                  script de tempo real — pedido do usuario 2026-09-20
                  ("certos scripts tem que ter seu proprio terminal").

                  Formulas (parametros padrao de mercado, ainda nao
                  ajustados/otimizados pro projeto):
                  - IFR (RSI) de Wilder, periodo 14: media movel exponencial
                    de Wilder (alpha=1/14) sobre ganhos e perdas do close.
                  - ATR de Wilder, periodo 14: media movel exponencial de
                    Wilder (alpha=1/14) sobre o True Range (max entre
                    high-low, |high-close anterior|, |low-close anterior|).
                  - MACD 12/26/9: EMA(12) - EMA(26) = linha MACD; SMA(9)
                    da linha MACD = linha de sinal; histograma = MACD -
                    sinal. Sinal em SMA (nao EMA) de proposito: e a
                    convencao do indicador nativo do MetaTrader (MT4/MT5),
                    que difere do MACD "livro-texto"/TradingView (EMA no
                    sinal) nesse detalhe — mudado em 1.1.0 pra bater com a
                    leitura que o usuario ve direto no terminal (corretora nacional e
                    corretora internacional), ver changelog.

                  Todas as funcoes recebem e devolvem pandas.Series/DataFrame
                  com a serie INTEIRA (nao so o ultimo valor) — cabe a quem
                  chama decidir se usa so a ultima linha (tempo real) ou
                  salva a serie inteira (lote, MTF).
Autor          : Julio Cesar Silvio Campanhola
Criado em      : 2026-09-20
Ultima edicao  : 2026-09-23
Versao         : 1.1.0
Projeto        : dashboard
Historico      : scripts_py/versoes/calculo_indicadores.md
"""

import importlib

try:
    pd = importlib.import_module("pandas")
except ImportError as exc:
    raise ImportError(
        "A dependencia pandas nao esta instalada. "
        "Instale-a com: pip install pandas pyarrow"
    ) from exc

PERIODO_IFR = 14
PERIODO_ATR = 14
MACD_RAPIDA = 12
MACD_LENTA = 26
MACD_SINAL = 9


def calcular_ifr(close, periodo=PERIODO_IFR):
    """IFR (RSI) de Wilder — media movel exponencial de Wilder
    (alpha=1/periodo) sobre ganhos e perdas do close. Retorna a serie
    inteira (NaN nos primeiros `periodo` candles, sem historico suficiente
    ainda)."""
    delta = close.diff()
    ganho = delta.clip(lower=0)
    perda = -delta.clip(upper=0)

    media_ganho = ganho.ewm(alpha=1 / periodo, min_periods=periodo, adjust=False).mean()
    media_perda = perda.ewm(alpha=1 / periodo, min_periods=periodo, adjust=False).mean()

    rs = media_ganho / media_perda.replace(0, pd.NA)
    ifr = 100 - (100 / (1 + rs))
    # perda media zero (serie so subindo) = IFR 100, nao NaN
    ifr = ifr.where(media_perda != 0, 100.0)
    return ifr


def calcular_atr(high, low, close, periodo=PERIODO_ATR):
    """ATR de Wilder — media movel exponencial de Wilder (alpha=1/periodo)
    sobre o True Range. Retorna a serie inteira (NaN nos primeiros
    `periodo` candles)."""
    fechamento_anterior = close.shift(1)
    tr1 = high - low
    tr2 = (high - fechamento_anterior).abs()
    tr3 = (low - fechamento_anterior).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1 / periodo, min_periods=periodo, adjust=False).mean()
    return atr


def calcular_macd(close, rapida=MACD_RAPIDA, lenta=MACD_LENTA, sinal=MACD_SINAL):
    """MACD no padrao do indicador nativo MT4/MT5 — EMA rapida - EMA lenta
    = linha MACD; SMA (media simples, NAO exponencial) da linha MACD =
    linha de sinal; histograma = MACD - sinal.

    O sinal em SMA (e nao EMA) e proposital (1.1.0): e assim que o
    MetaTrader calcula por padrao — diferente do MACD "livro-texto" (ex.
    TradingView), que usa EMA no sinal. Confirmado 2026-09-23 comparando
    contra a leitura ao vivo do indicador MACD(12,26,9) no terminal MT5
    do usuario, D1, nas duas corretoras (corretora nacional/Indice e corretora internacional/Indice):
    com SMA(9) no sinal os valores bateram (diferenca residual de poucos
    pontos, so pelo candle do dia ainda estar se formando); com EMA(9)
    batiam muito longe (~300 pontos de diferenca no sinal).

    Retorna as 3 series inteiras num DataFrame (macd, macd_sinal,
    macd_hist). NaN no sinal/histograma antes de acumular `sinal` candles
    de linha MACD (rolling exige a janela cheia)."""
    ema_rapida = close.ewm(span=rapida, adjust=False).mean()
    ema_lenta = close.ewm(span=lenta, adjust=False).mean()
    macd = ema_rapida - ema_lenta
    linha_sinal = macd.rolling(sinal).mean()
    histograma = macd - linha_sinal
    return pd.DataFrame({"macd": macd, "macd_sinal": linha_sinal, "macd_hist": histograma})


def calcular_todos(df, periodo_ifr=PERIODO_IFR, periodo_atr=PERIODO_ATR,
                    macd_rapida=MACD_RAPIDA, macd_lenta=MACD_LENTA, macd_sinal=MACD_SINAL):
    """Atalho: recebe um DataFrame com colunas high/low/close (ordenado por
    time) e devolve um DataFrame novo (mesmo indice) com as 5 colunas de
    indicador (ifr, atr, macd, macd_sinal, macd_hist)."""
    resultado = pd.DataFrame(index=df.index)
    resultado["ifr"] = calcular_ifr(df["close"], periodo_ifr)
    resultado["atr"] = calcular_atr(df["high"], df["low"], df["close"], periodo_atr)
    macd_df = calcular_macd(df["close"], macd_rapida, macd_lenta, macd_sinal)
    resultado["macd"] = macd_df["macd"]
    resultado["macd_sinal"] = macd_df["macd_sinal"]
    resultado["macd_hist"] = macd_df["macd_hist"]
    return resultado
