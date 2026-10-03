# Changelog - amplitude.py

## 1.0.0 - 2026-09-26
- Criacao do script. Amplitude de mercado (advance/decline + novas
  maximas/minimas) pras duas views do dashboard (Indice/B3 e Nasdaq) -
  pedido do usuario apos discutir que amplitude de verdade precisa do
  preco INDIVIDUAL de cada acao do universo, nao da pra calcular so com
  o indice/futuro agregado (Indice/UsaTec).
- Universos vem de config.json -> amplitude_universos (novo, ainda vazio
  nos dois: "indice" e "nasdaq"), cada um com uma lista de "raizes" -
  mesma convencao de ativos_referencia_extra (correl.py/vies_direcional.py/
  dp.py). Ainda sem nenhuma raiz configurada, e sem nenhuma delas sendo
  coletada pelo historico.py ainda - o usuario vai atras das acoes
  (descartada a rota de ADR pro Indice, cobre so uma fatia pequena e
  enviesada do Ibovespa - equivalente direto na B3 e melhor).
- Metricas por universo x timeframe (M15 a W1): avancos/declinios/
  inalterados (fechamento atual vs anterior, por acao, depois contado),
  novas_maximas/novas_minimas (high/low do candle atual bate a maior/
  menor janela de JANELA_MAXMIN_PADRAO=20 candles daquele TF - generico
  por timeframe, nao fixo em "52 semanas"), pct_avanco, indice_amplitude
  ((avancos-declinios)/total*100).
- Sem AD Line cumulativa (soma dia a dia desde sempre) nesta versao -
  quebraria o padrao do projeto de recalculo sempre total, sem estado
  incremental persistido (ver indicadores_mtf.py). Fica pra v2 se o
  usuario quiser depois.
- Mesmo padrao mtime-watch + double buffer
  (amplitude_amostra_a/b.json) de dp.py/last_nac.py. Nao registrado no
  main.py ainda (sem universo configurado, nao ha o que rodar) -
  registrar quando o usuario tiver as raizes e a coleta delas prontas.
