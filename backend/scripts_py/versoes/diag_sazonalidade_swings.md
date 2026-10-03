Historico de versoes — diag_sazonalidade_swings.py
-------------------------------------------------------------------------
1.0.0 - 2026-09-26 - Julio - Diagnostico pontual Indice/Dolar: deteccao de
  swing (fractal N=2, M15), teste da hipotese "janela ima" (topo e fundo
  da mesma perna caindo na mesma janela de horario) e histograma marginal
  topo/fundo por horario. Descartavel a princípio, sem entrada em
  versoes/ (corrigido retroativamente nesta entrada).
-------------------------------------------------------------------------
1.1.0 - 2026-09-26 - Julio - Adiciona analisar_duracoes(): tempo em
  minutos entre um swing e o PROXIMO do mesmo tipo (topo->topo,
  fundo->fundo) - preco/direcao entre os pontos e irrelevante, so a
  distancia no tempo.
-------------------------------------------------------------------------
1.2.0 - 2026-09-26 - Julio - Corrige media >> mediana na duracao (ex.:
  Indice 400min vs 105min): par formado pelo ultimo ponto de um pregao com
  o primeiro do pregao seguinte carregava o fechamento do dia inteiro
  como se fosse duracao normal. Descarta par cuja data (dia calendario)
  dos dois pontos seja diferente.
-------------------------------------------------------------------------
2.0.0 - 2026-09-27 - Julio - Reescopo pedido pelo usuario: o script deixa
  de ser exclusivo de Indice/Dolar e passa a rodar no universo internacional
  inteiro (moedas_continuo, indices_continuo, commodities_internacionais,
  treasury_etf_eua, acoes_nasdaq100, vencimento_americano sem
  Dolar/Indice - mesma logica de exclusao tautologica ja usada em
  vies_direcional.py), via montar_universo() lendo direto do
  config.json. Nova METODO PARTE 2: cada ponto de swing e cruzado com o
  MACD/IFR/ATR M15 (merge exato por time) e o IFR M5 (merge_asof
  backward) ja calculados por indicadores_mtf.py - nada e recalculado
  aqui. Adiciona calcular_validacao() (taxa de fundo com MACD M15 < 0 e
  IFR M5 <= 30, taxa de topo com MACD M15 > 0 e IFR M5 >= 70, por ativo e
  agregado no universo) - primeira leitura crua da hipotese do usuario
  antes de qualquer modelo estatistico/ML. Troca o filtro de outlier de
  analisar_duracoes() de "descarta par com data de calendario diferente"
  (so funciona pra ativo de sessao unica tipo B3) pra "descarta duracao >
  5x a mediana bruta da propria serie" (generaliza pra ativo continuo/24h
  tipo forex/CFD, que agora entra no escopo). Nova saida:
  parquet/calculos/sazonalidade_swings_universo.parquet - dataset
  achatado (uma linha por ponto de swing) que vai alimentar a proxima
  etapa (ARCH/GARCH, regressao, ARIMA/SARIMAX, XGBoost/LightGBM/CatBoost
  - nenhum modelo entra neste script). Ainda standalone, nao registrado
  no main.py.
-------------------------------------------------------------------------
