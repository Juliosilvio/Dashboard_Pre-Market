Historico de versoes — cenario_final_swing.py
-------------------------------------------------------------------------
1.0.0 - 2026-09-27 - Julio - "Quinto passo" da fila - pedido explicito do
  usuario depois de ver os numeros do classificador: "com os numeros
  gerados por essa fase do sistema precisamos de recomendacao de onde o
  preco pode ir e qual e a entrada". So COMBINA o que ja existe, nao
  recalcula nada: ModeloGarchSwing.analisar(raiz) (vies MACD/IFR + faixa
  esperada via GARCH) + os dois classificadores ja treinados
  (modelos/classificador_swing_topo.joblib e _fundo.joblib), pontuando o
  candle MTF mais recente do ativo com as mesmas 7 features do treino.
  Sinal = "topo"/"fundo" so quando a probabilidade calibrada passa do
  limiar salvo em json/limiares_classificador_swing.json (senao
  "indefinido" - disparar recomendacao errada e pior que nao dar
  nenhuma). Direcao: sinal "topo" (deve reverter pra baixo) -> venda;
  "fundo" -> compra. Alvo: ponta da faixa GARCH na direcao esperada.
  Confianca "alta" quando a regra crua MACD/IFR TAMBEM concorda com o
  sinal do modelo (dois metodos independentes bateram), "moderada"
  quando so o modelo aponta. Entrada - usuario pediu as DUAS opcoes
  (nao uma so): entrada_a_mercado (preco atual) e entrada_zona_pullback
  (ponto medio entre o preco atual e a ponta OPOSTA da faixa GARCH - ex.:
  sinal de venda espera o preco subir um pouco mais antes de reverter,
  vendendo mais caro; compra e o espelho) - so referencia geometrica
  dentro da faixa esperada, nao suporte/resistencia tecnica real,
  documentado no cabecalho. Sem calculo de stop nesta versao (fora do
  escopo pedido). Testado contra dado real da ponte Linux (mesmo dado
  montado do Windows): Indice/Dolar/EURUSD/AAPL/GOLD sem sinal no instante
  testado (normal - limiar calibrado pra disparar em so ~4,5% dos
  candles); GBPUSD/USDTRY/USDMXN dispararam sinal de fundo/compra com
  confianca alta (regra crua concordando) na mesma rodada de teste.
  Ainda standalone (nao registrado no main.py, sem endpoint proprio no
  api_server.py) - roda sob demanda com `python cenario_final_swing.py`.
-------------------------------------------------------------------------
1.1.0 - 2026-09-27 - Julio - Saida passa a ser um SUPERSET do dict de
  ModeloGarchSwing.analisar() (mantem preco_atual, vies_macd_m15,
  macd_m15, ifr_m5, ifr_m5_estado, sigma_garch_1passo_pct,
  candles_m15_amostra - todos ja consumidos pelo ModeloSwingCard.jsx) em
  vez de um dict novo so com os campos do cenario. Permitiu trocar
  direto a chamada do endpoint GET /api/modelo-swing/{raiz} em
  api_server.py (1.18.0) de ModeloGarchSwing pra CenarioFinalSwing sem
  quebrar nada que ja lia a resposta antiga - virou o endpoint em
  producao (deixou de ser so standalone). ModeloSwingCard.jsx (v3.0.0)
  ganhou um bloco de destaque (direcao/confianca/alvo/entradas) acima da
  tabela GARCH que ja existia, condicionado a `dado.sinal !== "indefinido"`.
-------------------------------------------------------------------------
