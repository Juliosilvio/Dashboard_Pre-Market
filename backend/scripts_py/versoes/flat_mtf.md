# Changelog - flat_mtf.py

## 1.0.0 - 2026-09-21
- Criacao do script (classe DerivadorFlatMTF). Parte da consolidacao pedida
  pelo usuario ("isso e o que precisamos: serie historica em MTF e preco em
  tempo real, de forma centralizada, pra nao errar mais") — o projeto tinha
  DOIS pipelines de coleta independentes buscando D1/M5 do MESMO MT5 pros
  MESMOS ativos (nac.py/nac_m5.py/int.py/int_m5.py -> historico_d1/
  m5.parquet; historico.py -> MTF), que ja tinham divergido de verdade (a
  correcao do alinhar_d1.py so tinha pegado uma das duas copias).
- Em vez de historico_d1.parquet/historico_m5.parquet serem coletados de
  novo do MT5, agora sao DERIVADOS da MTF (que virou a unica coleta, via
  historico.py). Usa historico.ColetorHistoricoMTF.montar_alvos() (mesma
  lista de alvos que o historico.py usa) pra saber broker/ticker bruto/
  pasta de cada ativo, le d1.parquet e m5.parquet de cada um e empilha no
  mesmo schema de sempre (broker, symbol=ticker bruto, timeframe, time,
  OHLCV) — retorno.py e taxa_usatb.py (os dois unicos consumidores diretos)
  nao precisaram de NENHUMA mudanca.
- Validado contra o pipeline antigo: retorno/correlacao/descorrelacao
  batem IDENTICOS pros mesmos ativos (diferenca de correlacao ~1e-15,
  ruido de ponto flutuante). Unica diferenca real: profundidade do M5 caiu
  de ~360 pra ~90 dias (profundidade padrao de primeira coleta do
  historico.py) — nao mudou nenhum resultado, porque as janelas de rolagem
  usadas (20 no D1, 100 no M5) sao bem menores que isso.
- Alguns tickers antigos (ja expirados, fora do vigentes.json atual —
  ex: DDIF29, DOLARK27) somem do historico_d1/m5.parquet derivado, porque
  montar_alvos() so cobre o vigente atual — sao contratos ja mortos que
  nao recebiam candle novo mesmo antes.
- Roda depois de historico.py + alinhar_d1.py e antes de retorno.py — ver
  main.py 4.0.0.
