# Changelog - calculo_indicadores.py

## 1.0.0 - 2026-09-20
- Criacao do modulo. Extrai as formulas de IFR (RSI), ATR e MACD que
  estavam como metodo de classe dentro do indicadores_mtf.py (1.0.0/2.0.0)
  pra um modulo compartilhado, standalone (funcoes puras, sem classe) —
  fonte unica pra nao duplicar/divergir a formula entre quem calcula em
  lote (indicadores_mtf.py, historico completo da pasta MTF) e quem
  calcula em tempo real (last_indicadores_nac.py, Indice/Dolar M1/M5).
- Funcoes: calcular_ifr(close, periodo=14) — Wilder (EMA alpha=1/periodo)
  sobre ganhos/perdas do close, RS=0 tratado como IFR=100; calcular_atr
  (high, low, close, periodo=14) — Wilder sobre o True Range; calcular_macd
  (close, rapida=12, lenta=26, sinal=9) — EMA rapida - EMA lenta = linha,
  EMA(sinal) da linha = linha de sinal, histograma = linha - sinal; e
  calcular_todos(df, ...) — conveniencia que roda as 3 em cima de um
  DataFrame OHLC e devolve um DataFrame so com as colunas de indicador.
- Motivo do pedido (usuario 2026-09-20): "certos scripts tem que ter seu
  proprio terminal" -> "Terminal proprio, separado de tudo" — pra montar
  o coletor de indicadores em tempo real sem reimplementar/arriscar
  divergir a formula ja validada no calculo em lote.

## 1.1.0 - 2026-09-23
- MACD: linha de sinal trocada de EMA(9) para SMA(9) (media simples) da
  linha MACD — so isso muda, a linha MACD em si (EMA rapida - EMA lenta)
  continua igual. Motivo: e assim que o indicador nativo do MetaTrader
  (MT4/MT5) calcula por padrao, diferente do MACD "livro-texto" (ex.
  TradingView), que usa EMA no sinal.
- Pedido do usuario (2026-09-23): "tem que bater com a leitura do MACD da
  Activ e da corretora nacional" — mandou 2 prints do MT5 (IndiceOct26/corretora internacional e
  Indice/corretora nacional, ambos D1, indicador MACD(12,26,9)) pra conferir. Com o
  calculo antigo (sinal em EMA) os valores nao batiam (linha de sinal
  ~300 pontos fora nos dois); com sinal em SMA bateram (diferenca residual
  de poucos pontos, so pelo candle do dia ainda estar se formando na hora
  da comparacao).
- Efeito colateral (esperado, nao e bug): o cruzamento baixista do MACD
  que antes aparecia em 22/09 (Indice D1, com sinal EMA) passa a aparecer
  em 18/09 (Indice) e 17/09 (Indice/corretora internacional) com sinal SMA — cruzamento
  aconteceu antes do que a formula anterior mostrava, e vem acelerando
  desde entao.
- Afeta os 2 consumidores do modulo (calcular_todos): indicadores_mtf.py
  (lote, toda a pasta MTF) e last_indicadores_nac.py (tempo real, Indice/
  Dolar M1/M5) — nenhum dos dois precisou mudar, so importam
  calculo_indicadores e recalculam a serie inteira a cada rodada, entao a
  formula nova entra sozinha na proxima rodada de cada processo (precisa
  restart se algum dos dois ja estiver rodando com o processo antigo em
  memoria — main.py reinicia os dois nesse ciclo).
