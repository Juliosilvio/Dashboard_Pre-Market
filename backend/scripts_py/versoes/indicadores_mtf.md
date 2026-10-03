# Changelog - indicadores_mtf.py

## 1.0.0 - 2026-09-20
- Criacao do script (classe CalculadorIndicadoresMTF). Retomando o ponto da
  conversa antes do desvio pro bug de fuso horario: calcula IFR (RSI),
  ATR e MACD em cima de TODOS os parquets da pasta de estudo MTF — todo
  ativo, todo timeframe (M1, M5, M15, M30, H1, H4, D1, W1), nao so
  Indice/Dolar.
- Formulas: IFR e ATR de Wilder (periodo 14, EMA de Wilder alpha=1/14);
  MACD padrao 12/26/9 (EMA rapida - EMA lenta = linha; EMA(9) da linha =
  sinal; histograma = linha - sinal). Parametros ainda nao ajustados/
  otimizados pro projeto — sao os padroes de mercado.
- Salva a serie historica COMPLETA de cada indicador como colunas novas
  no proprio parquet de candles (ifr, atr, macd, macd_sinal, macd_hist) —
  nao so o valor mais recente. Recalculo sempre total (arquivo inteiro a
  cada rodada), nao incremental.
- 1047 de 1048 arquivos processados na primeira rodada (2.651.083 candles).
  1 falha: GOLD/w1.parquet corrompido por uma interrupcao no meio da
  primeira tentativa (timeout) — recriado vazio com schema valido,
  repopula sozinho no proximo historico.py.
- Script standalone da pasta MTF, igual historico.py — nao registrado no
  main.py por enquanto.

## 2.0.0 - 2026-09-20
- Mudanca estrutural pedida pelo usuario: os indicadores deixam de ser
  colunas dentro do proprio parquet de preco e passam a viver numa pasta
  "indicadores/" IRMA do arquivo de preco, dentro de cada pasta de ativo
  (ou de vencimento, quando o ativo tiver). Ex: MTF/Indice/m5.parquet
  (preco, intocado) e MTF/Indice/indicadores/m5.parquet (ifr/atr/macd/...).
  Mesma ideia pra ativo com vencimento: MTF/Indice/10-2026/indicadores/.
- Limpeza automatica: se o parquet de preco ainda tinha as colunas de
  indicador da 1.0.0 embutidas, esta versao remove e resalva o preco
  limpo (so OHLC) antes de gerar o arquivo separado em indicadores/.
- listar_arquivos_tf() passa a ignorar qualquer coisa dentro de uma pasta
  "indicadores/" pra nao reprocessar a propria saida numa rodada futura.
- 1046 de 1048 arquivos processados (2.638.678 candles). 2 falhas:
  GOLD/w1.parquet (ainda vazio, esperado) e USDCAD/m30.parquet (corrompido
  por interrupcao no meio da rodada anterior — recriado vazio com schema
  valido, repopula sozinho no proximo historico.py).

## 2.1.0 - 2026-09-20
- Refatoracao: remove as formulas duplicadas de IFR/ATR/MACD (que
  viviam como metodo de classe desde 1.0.0) e passa a importar do modulo
  compartilhado calculo_indicadores.py (calcular_todos) — mesma fonte
  que o last_indicadores_nac.py (tempo real) usa, pra nao duplicar/
  divergir formula entre o calculo em lote e o em tempo real. Nenhuma
  mudanca de comportamento/resultado (validado: mesmo output pra
  Indice/m5.parquet antes e depois da refatoracao).
