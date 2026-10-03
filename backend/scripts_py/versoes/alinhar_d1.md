# Changelog - alinhar_d1.py

## 1.0.0 - 2026-09-20
- Criacao do script. Normaliza o D1 da corretora internacional pra ficar comparavel com
  o D1 nativo da corretora nacional (Indice/Dolar) de uma vez por todas.
- Problema: mesmo com o horario do candle corrigido (fuso_horario.py,
  DST-aware), o D1 NATIVO da corretora internacional tem o barramento (range de 24h
  agregado) seguindo o dia do proprio servidor, nao o dia calendario UTC —
  cruza dois dias UTC (ex: Usa500 abre 19h/20h UTC), enquanto o D1 nativo
  da corretora nacional ja e exatamente o pregao da B3 (09:00-18:30 UTC) rotulado
  00:00 UTC do mesmo dia (confirmado batendo D1 nativo do Indice contra o M5
  do mesmo dia calendario). Comparar "mesma data" entre os dois D1 nativos
  mistura pregoes diferentes (SP500 x Indice D1 dava 0.35, numero que nao se
  sustentava).
- Solucao: recalcula o D1 da corretora internacional a partir do M5 (ja corrigido),
  agrupado por dia calendario UTC (00:00-24:00) — igual a corretora nacional ja usa.
  Substitui as linhas "corretora internacional" de historico_d1.parquet pelo resultado;
  linhas "corretora nacional" ficam intocadas. Roda no main.py logo apos o merge do M5 e
  antes do retorno.py (ver main.py 3.6.0).
- Validado: Indice x Indice (mesmo ativo) em D1 bateu 0.9575 de correlacao
  (era ~0 antes de qualquer correcao, e nao dava pra confiar so com a
  correcao de fuso). SP500 x Indice D1 = 0.311, SP500 x Dolar D1 = -0.446 —
  sinais consistentes com o resultado ja validado em M5 (0.297 / -0.318).
- Contrapartida aceita: como o M5 so guarda ~360 dias, o D1 recalculado da
  corretora internacional cobre so esse periodo (as linhas mais antigas do D1 nativo,
  ~1 ano a mais, foram descartadas por serem estruturalmente incomparaveis
  mesmo antes disso). taxaUsaTBD1.parquet caiu de 1041 pra 611 candles
  como consequencia direta.

## 2.0.0 - 2026-09-21
- Reescrito pra consolidacao MTF (pedido do usuario: serie historica
  centralizada). Antes corrigia o D1 dentro de historico_d1.parquet/
  historico_m5.parquet (pipeline "antigo", nac.py/int.py). Agora que
  historico.py (MTF) virou a UNICA coleta, o D1 nativo salvo em
  parquet/historicos/MTF/<ativo>/[<vencimento>/]d1.parquet pra ativos da
  corretora internacional tinha o MESMO bug de fronteira de dia — confirmado
  (MTF/Indice/10-2026/d1.parquet abria 19h UTC antes desta correcao, so
  tinha sido consertado na copia antiga). Reescrito pra corrigir DENTRO da
  propria MTF: usa historico.ColetorHistoricoMTF.montar_alvos() pra saber
  quais alvos sao da corretora internacional, resample o m5.parquet de cada um
  (agrupado por dia calendario UTC) e sobrescreve o d1.parquet daquele
  mesmo alvo.
- Validado: Indice/10-2026/d1.parquet agora abre 00:00:00 UTC (era
  19:00:00 UTC) — 26/30 alvos da corretora internacional corrigidos (os 4 restantes
  sao contratos ja expirados/rolados sem m5.parquet coletado).
- Roda entre historico.py e flat_mtf.py no main.py — ver main.py 4.0.0.
