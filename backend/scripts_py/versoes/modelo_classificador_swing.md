Historico de versoes — modelo_classificador_swing.py
-------------------------------------------------------------------------
1.0.0 - 2026-09-27 - Julio - Segunda peca de modelagem da fila (depois do
  GARCH em modelo_garch_swing.py). Treina dois classificadores binarios
  LightGBM (topo, fundo) POOLED no universo inteiro (129 ativos),
  reconstruindo a serie M15 COMPLETA de cada ativo (nao so os pontos de
  swing ja confirmados que sazonalidade_swings_universo.parquet guarda -
  faltava o negativo pra treinar classificador) e rotulando 1/0 via o
  mesmo detectar_swings() de diag_sazonalidade_swings.py (reaproveitado
  por import). Features: macd_m15, macd_sinal_m15, macd_hist_m15,
  ifr_m15, atr_m15, ifr_m5, minutos_do_dia. Classe desbalanceada (~15% de
  prevalencia) compensada via scale_pos_weight, nao oversampling.
  Validacao walk-forward: 3 dobras expansivas por QUANTIL de tempo
  (ativos tem profundidade historica bem diferente, data de calendario
  fixa deixaria ativo novo inteiro de um lado so). Resultado (dataset
  real, 459.546 candles, 129 ativos): regra crua (macd + ifr_m5 nos
  extremos) acerta ~32% quando dispara; o modelo, disparando na MESMA
  frequencia (~4,5% dos candles), acerta ~47-48% (AUC medio ~0,76 pros
  dois alvos). Modelo final (treinado com todo o dado, apos a validacao
  ja medir o desempenho fora da amostra) salvo em
  modelos/classificador_swing_topo.joblib e _fundo.joblib. Tambem calcula
  e salva um LIMIAR de score calibrado (percentil do score que bate a
  mesma taxa de disparo media da regra crua nas dobras - nao um "0.5"
  arbitrario, que nao faz sentido pra uma classe rara) em
  json/limiares_classificador_swing.json, consumido por
  cenario_final_swing.py. Dependencias novas no venv do projeto:
  `lightgbm`, `scikit-learn` (nenhuma das duas estava instalada antes
  desta versao). Ainda standalone (nao registrado no main.py, sem
  endpoint proprio no api_server.py) - roda sob demanda com
  `python modelo_classificador_swing.py`.
