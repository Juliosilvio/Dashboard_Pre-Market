# Changelog - fuso_horario.py

## 1.0.0 - 2026-09-20
- Criacao do modulo. Centraliza a correcao de fuso horario entre corretoras,
  substituindo a correcao fixa (config.json fuso_horario.correcao_horas =
  -5h pra corretora internacional) que se mostrou errada: o servidor da corretora internacional
  segue o horario de verao europeu (DST), nao um offset fixo.
- corrigir_horario_corretora internacional / reverter_horario_corretora internacional (+ versoes
  escalares): aplicam -5h no horario de verao europeu (ultimo domingo de
  marco ao ultimo domingo de outubro, 01:00 UTC) e -4h fora dele.
- Validado comparando Indice (corretora nacional) com Indice (corretora internacional), mesmo ativo:
  offset fixo -5h o ano todo batia 0.636 de correlacao M5; DST-aware bateu
  0.953. Abertura do pregao do Indice corrigido bate 09:00 UTC (= Indice) em
  mais de 97% dos dias de pregao (resto e feriado/half-day).
- Usado por: historico.py, int.py, int_m5.py (na coleta, escrevem o
  historico ja com horario certo). correl.py e descorrel.py NAO usam mais
  nenhuma correcao — leem historico_d1/m5.parquet, que ja nascem corrigidos.
