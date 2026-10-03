# Changelog - last_indicadores_nac.py

## 1.0.0 - 2026-09-20
- Criacao do script (classe ColetorIndicadoresNac). Resolve a defasagem
  de ate ~5 minutos que o indicadores_mtf.py tem quando chamado dentro do
  loop em lote do main.py (que so avanca quando os dois brokers fecham
  candle M5 novo) — pra M1 de Indice/Dolar, os dois ativos-alvo do projeto,
  isso e defasagem grande demais pra quem acompanha tempo real.
- Processo separado e continuo (nao termina sozinho), mesmo padrao
  arquitetural de last_nac.py/last_int.py: terminal MT5 proprio via
  connections["corretora_nacional_indicadores"] no config.json (pedido do usuario:
  "Terminal proprio, separado de tudo" — TERCEIRA instalacao portable,
  separada tanto do terminal do pipeline em lote "corretora nacional" quanto do
  terminal dedicado do last_nac.py "corretora_nacional_tempo_real"), com fallback pra
  conexao normal "corretora nacional" enquanto essa chave nao existir.
- So acompanha Indice e Dolar (nao a MTF inteira — isso e papel do
  indicadores_mtf.py, em lote), em M1 e M5 (4 combinacoes). A cada ciclo
  (PAUSA_LOOP = 2s) busca as ultimas 500 barras via copy_rates_from_pos
  (incluindo a barra em formacao, posicao 0, pra refletir o preco
  correndo), recalcula IFR/ATR/MACD com calculo_indicadores.calcular_todos
  (modulo compartilhado, extraido do indicadores_mtf.py nesta mesma
  rodada) e guarda so a ULTIMA linha de cada combinacao — tabela de valor
  corrente, nao log de historico (serie historica completa continua
  sendo papel do indicadores_mtf.py/MTF).
- Double buffer + escrita atomica (.tmp + os.replace) + guard de "mudou
  desde a ultima volta" (_sujo) + parada limpa via
  parquet/historicos/_stop_last.flag: identico ao padrao de
  last_nac.py/last_int.py. Saida em
  json/last_json/last_indicadores_nac_a.json e
  last_indicadores_nac_b.json.
- Registrado no main.py (proc_last) — ver main.py 3.9.0.
- Pendente: usuario precisa instalar um terceiro MT5 portable (mesma
  conta, path proprio) e adicionar connections["corretora_nacional_indicadores"] no
  config.json pra ganhar o isolamento de terminal de verdade; ate la,
  roda no terminal compartilhado "corretora nacional" sem quebrar nada.

## 2.0.0 - 2026-09-21
- Correcao do usuario: o script NAO deve abrir conexao com o MT5 (nem
  precisa de connections["corretora_nacional_indicadores"], que foi removido) — isso
  seria coletar a mesma serie duas vezes a toa, ja que nac_m5.py/
  historico.py ja coletam e salvam em parquet/historicos/MTF/. Reescrito
  pra ler DIRETO os parquets de preco ja existentes (MTF/Indice/m1.parquet,
  m5.parquet, MTF/Dolar/m1.parquet, m5.parquet) — zero dependencia de MT5/
  psutil neste script.
- O ganho de velocidade nao vem de coletar preco mais novo que o pipeline
  (a frequencia de coleta continua sendo a do historico.py) — vem de
  pular a fila: em vez de esperar indicadores_mtf.py recalcular os outros
  ~1000 arquivos da MTF primeiro (rodando por ultimo no pipeline, depois
  de vigente/grade/nac/nac_m5/alinhar_d1/retorno/taxa_usatb/correl/
  descorrel/historico.py — ja levou 120-180s so essa etapa), este script
  fica de olho SO nos 4 arquivos de Indice/Dolar (m1+m5) e recalcula assim
  que o mtime de qualquer um deles muda, independente do resto do
  pipeline.
- Deteccao de mudanca via os.path.getmtime (comparacao de metadado,
  quase gratis) a cada 1s — so abre e le o parquet quando o arquivo
  realmente mudou.
- Validado: valores batem exatamente com os que o indicadores_mtf.py
  calculou pro mesmo arquivo (Indice M5: IFR 64.887, hist 18.851).
- Esclarecimento importante (usuario 2026-09-21): o pedido original
  ("certos scripts tem que ter seu proprio terminal" / "Terminal proprio,
  separado de tudo") era sobre JANELA DE CONSOLE/PowerShell, nao terminal
  MT5 — eu tinha interpretado errado. Como este script nem conecta no
  MT5, a questao nem se aplica a ele; a janela de console propria ficou
  por conta do main.py (_iniciar_last, CREATE_NEW_CONSOLE) — ver
  main.py 3.9.1.
