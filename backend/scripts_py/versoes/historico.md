# Changelog - historico.py

## 1.0.0 - 2026-09-19
- Criacao do script. Coleta 8 timeframes (M1, M5, M15, M30, H1, H4, D1, W1)
  de cada ativo do config.json e salva em
  parquet/historicos/MTF/<ativo>[/<mes-ano>]/<tf>.parquet.
- Ativo com vencimento (curva_br e vencimento_americano) ganha subpasta
  mes-ano por vigente atual, criada automaticamente quando aparece um
  vigente novo (rolagem de contrato ou nova ponta de curva) - durante
  rolagem com dois vigentes simultaneos, as duas subpastas ficam ativas.
- Ativo sem vencimento salva direto na pasta raiz, sem subpasta.
- Incremental via parquet/historicos/controle_atualizacao_mtf.parquet:
  guarda data + preco de fechamento da ultima atualizacao por
  ativo+timeframe; cada rodada acrescenta linha nova (nunca sobrescreve).
- M1/M15/M30/H1/H4/W1 sempre buscados direto no MT5 (nao existem no
  pipeline principal, que so tem D1/M5).
- Script standalone da pasta de estudo MTF, nao registrado no main.py.

## 1.0.1 - 2026-09-19
- Corrigido local do parquet de controle: fica dentro de parquet/historicos/MTF/,
  nao mais em parquet/historicos/ (que e do pipeline principal) - a pasta MTF e
  um braco separado do projeto e nao deve se misturar com historico_d1/m5.parquet.

## 1.0.2 - 2026-09-20
- Corrigido bug critico de fuso: a correcao de horario da corretora internacional NAO e
  um offset fixo de -5h - o servidor dela acompanha o horario de verao
  europeu (DST). Usava -5h o ano todo (config.json fuso_horario.correcao_horas),
  o que so estava certo durante o horario de verao europeu; no horario de
  inverno europeu ficava 1h errado. Substituido pelo modulo
  scripts_py/fuso_horario.py (corrigir_horario_corretora internacional /
  reverter_horario_corretora internacional), que aplica -5h ou -4h conforme a data.
  Retroagido nos 208 parquets ja existentes em parquet/historicos/MTF/ e no
  controle_atualizacao_mtf.parquet.

## 1.0.3 - 2026-09-21
- Corrigido bug de descasamento de relogio em coletar_alvo(): so o limite
  inferior da consulta (data_de) era revertido pro horario cru do servidor
  da corretora internacional - o limite superior (agora, usado tanto no
  mt5.copy_rates_range quanto no calculo do data_de da primeira coleta)
  continuava em horario real/UTC. Os dois lados da janela ficavam em
  relogios diferentes, o que podia fazer o MT5 devolver janela errada ou
  vazia justamente na reabertura do mercado (fim de semana) - sintoma
  observado: candles MTF da corretora internacional (EURUSD, Usa500, GOLD, USDBRL)
  travados desde sexta 17h59 UTC, sem avancar durante o fim de
  semana/segunda de manha, mesmo com o feed de tick ao vivo (last_int.py)
  funcionando normalmente. Introduzida a variavel agora_consulta (= agora
  revertido quando eh_corretora internacional, senao igual a agora sem alteracao) e
  usada nos dois pontos que antes usavam agora diretamente.

## 1.0.4 - 2026-09-21
- Corrigida a CAUSA REAL do travamento de 3 dias na coleta corretora internacional
  (nao era so o bug de fuso da 1.0.3): o modulo fuso_horario.py nunca
  tinha sido importado em historico.py. As funcoes
  reverter_horario_corretora internacional_escalar/corrigir_horario_corretora internacional
  passaram a ser chamadas desde a 1.0.2 (correcao DST-aware), mas sem o
  "from fuso_horario import ...", cada chamada estourava
  NameError: name '...' is not defined - capturado silenciosamente pelo
  try/except por-ativo em executar() (so imprime "AVISO: falha em ...").
  Rodando ao vivo (log do usuario), TODOS os 30 alvos corretora internacional falharam
  com esse erro, todos os dias desde que a 1.0.2 entrou (20/09) - a coleta
  corretora nacional seguia normal porque nunca chama essas funcoes (eh_corretora internacional e
  sempre False pra ela). Adicionado o import que faltava.

## 1.1.0 - 2026-09-22
- Adicionada a flag opcional --reforcar TF:DIAS (repetivel) pra alongar a
  amostra historica de um timeframe especifico sem tocar nos demais e sem
  duplicar candle. Motivacao: viabilizar um dataset de ML pra cenario
  INDICE/DOLAR baseado em situacoes pre-abertura de ativos de risco
  (Usa500/UsaVix/etc) - o M5 so tinha 90 dias de profundidade na primeira
  coleta (TIMEFRAMES), pouco pra cobrir regimes de mercado diferentes.
  Quando a flag e passada pra um TF, coletar_alvo() ignora o
  data_ultima_atualizacao do controle so pra aquele TF nessa rodada e busca
  --reforcar M5:720 dias pra tras a partir de agora; o merge existente
  (concat + drop_duplicates(subset="time") + sort) ja garante que so o
  historico faltante e acrescentado, sem duplicar nem sobrescrever o que ja
  tinha. Os demais TFs seguem 100% incrementais, normalmente. Uso:
  python historico.py --reforcar M5:720 (ou --reforcar M5:720 --reforcar M1:180
  pra reforcar mais de um TF na mesma rodada).

## 1.2.0 - 2026-09-26
- Terceiro broker: config.json -> connections.mt5stock (terminal novo,
  instalado direto do MQL5, servidor MetaQuotes-Demo, conta demo) - pedido
  do usuario apos descobrir que a corretora internacional nao tem nenhuma acao
  americana individual (ver verificar_magnificas.py) mas esse terminal
  tem o catalogo inteiro do Nasdaq (confirmado via verificar_mt5stock.py:
  6208 acoes + ETFs).
- Dois grupos novos em BROKER_POR_GRUPO -> "mt5stock", sem vencimento
  (ticker == raiz, igual indices_continuo):
  - "acoes_nasdaq100": as 100 acoes do indice Nasdaq-100, uma a uma
    conferidas contra o catalogo do mt5stock. EA (Electronic Arts) ficou
    de fora - nao existe mais nesse catalogo, provavelmente por causa do
    fechamento de capital da empresa em 2026 (delisting).
  - "treasury_etf_eua": TLT/IEF/SHY - proxies de juro longo/medio/curto
    americano (ETF, ja que esse terminal nao tem contrato futuro de
    treasury direto). Alimentam um card novo na view Nasdaq via
    config.json -> dp_ativos_extra + dp.py 1.3.0 (ver dp.md) - separado
    de ativos_referencia_extra de proposito, pra nao virar view fantasma
    no menu dropdown do frontend (App.jsx -> viewsExtra vem das chaves de
    ativos_referencia_extra via vies_direcional.py).

## 1.4.0 - 2026-09-29
- Novo grupo "etfs_sentimento_em" (EWZ/EEM) em BROKER_POR_GRUPO/
  ORDEM_GRUPOS - mesmo padrao de treasury_etf_eua (ETF a vista, sem
  vencimento, catalogo mt5stock, rota coletar_alvo_via_csv). Pedido do
  usuario: "colocar o EWZ no Risk indice" - EWZ (iShares MSCI Brazil) e
  EEM (iShares MSCI Emerging Markets) como proxy de sentimento de risco
  Brasil/emergentes fora do horario nacional (quando Indice/Dolar nao estao
  negociando na B3).
- Nao entra em GRUPOS_COM_VENCIMENTO (ticker == raiz, igual
  acoes_nasdaq100/treasury_etf_eua).
- RAIZES[] do ExportadorMt5Stock.mq5 (backend/Claude outputs/) tambem
  ganhou EWZ/EEM - precisa recompilar no MetaEditor e reiniciar o
  Service no terminal mt5stock (Navegador -> Servicos) pra esses dois
  ativos comecarem a ter CSV exportado; sem isso coletar_alvo_via_csv()
  nao acha arquivo pra fundir no parquet.
- config.json -> ativos.etfs_sentimento_em: ["EWZ", "EEM"]. Nao entra em
  vigentes (sem vencimento).
- Placement na grade Risk Indice vs. Risk Dolar NAO e forcado aqui -
  quem decide isso e separarIndiceDolar() no frontend (QuotesTable.jsx),
  com base em correlacao_indice/correlacao_dolar real calculada por correl.py
  depois que o parquet MTF existir. EWZ tende fortemente a Indice (segue
  ativos brasileiros) mas isso e resultado do dado, nao hardcode.
- Confirmado com dado real de producao (2026-09-29): EWZ ->
  correlacao_indice=0.9547/correlacao_dolar=-0.9088 -> bucket Indice; EEM ->
  correlacao_indice=0.1905/correlacao_dolar=-0.4640 -> bucket Dolar. Depois,
  ja em producao com o feed de cotacao ao vivo (sentimento_em.py, ver
  sentimento_em.md 1.0.0), usuario confirmou os dois aparecendo nas
  grades certas (EWZ em Risk Indice, EEM em Risk Dolar) com variacao
  intraday bem negativa nos dois - leitura de aversao a risco
  Brasil/emergentes.
- Corrigido comentario desatualizado no cabecalho do modulo ("Script
  standalone... nao faz parte do pipeline do main.py") - ficou de uma
  fase anterior a consolidacao de 2026-09-21 e levou a uma informacao
  errada passada ao usuario (historico.py na verdade E chamado
  automaticamente pelo main.py, via Orquestrador._rodar_lote(), como a
  unica coleta MTF). Usuario perguntou diretamente ("o main tinha que
  rodar o historico nao tinha?") e a checagem no codigo confirmou.

## 1.3.0 - 2026-09-26
- Terminal mt5stock (build 6230) tem um bug isolado com
  diag_symbol_select_mt5stock.py: symbol_select()/copy_rates_range()
  chamados pela API Python externa (MetaTrader5) devolvem
  last_error=(-3, "Terminal: Out of memory") pra QUALQUER simbolo, mesmo
  ja selecionado e com cotacao valida em tempo real - reproduzido de forma
  consistente em varias rodadas, descartadas as hipoteses de Market Watch
  cheio, elevacao/administrador do processo Python vs. terminal, e versao
  desatualizada do pacote MetaTrader5 do pip (ja era a mais nova).
- Contorno: Service nativo dentro do proprio terminal (backend/Claude
  outputs/ExportadorMt5Stock.mq5) roda em segundo plano e, sem passar pela
  ponte externa Python<->MT5 (onde mora o bug), faz SymbolSelect()/
  CopyRates() nativos pras 103 raizes de acoes_nasdaq100 + treasury_etf_eua
  nos mesmos 8 TFs de TIMEFRAMES, exportando CSV (mesmas colunas de
  mt5.copy_rates_range: time,open,high,low,close,tick_volume,spread,
  real_volume) pra Common\Files\mt5stock_export\<raiz>\<tf>.csv (pasta
  compartilhada entre terminais, fora do sandbox de cada um).
- coletar_alvo_via_csv() novo metodo: mesma fusao/dedup/parquet de
  coletar_alvo(), so que lendo esse CSV em vez de chamar a API MT5. No
  executar(), o broker "mt5stock" agora usa essa rota e NAO chama mais
  conectar()/desconectar() (nao depende mais da conexao Python quebrada
  pra esse terminal especifico).

## 1.5.0 - 2026-09-30
- Nova flag opcional --so RAIZ1,RAIZ2,... (repetivel; uniao entre
  repeticoes ou virgula na mesma ocorrencia) restringe a coleta desta
  rodada so as raizes indicadas (nomes exatos de config.json -> ativos),
  sem afetar o controle incremental dos demais ativos - eles so ficam de
  fora desta rodada especifica, a proxima rodada sem --so volta a cobrir
  o config.json inteiro normalmente.
- Pensada pra usar junto com --reforcar, pra aprofundar o historico so
  dos ativos que um estudo especifico precisa, sem reforcar as ~200+
  raizes do config.json de uma vez (mais rapido, nao sobrecarrega o
  MT5/disco a toa). Pedido do usuario 2026-09-30, discutindo como viabilizar
  o estudo do impulso de abertura (09:00) via causalidade de Granger:
  "para este tipo de estudo podemos criar um outro banco de dados, nao
  sendo db literalmente, quero dizer um outro service que carregue a
  quantidade necessaria de serie historica para o estudo".
- Uso concreto combinado (o proprio estudo do impulso): python
  historico.py --reforcar M1:180 --so Indice,Dolar,GOLD,ChinaA50,GBPUSD,USDSEK
  - Indice/Dolar sao os tickers continuos da corretora nacional (mesmo Indice/Dolar da
  corretora internacional, mas sem a complicacao de rolagem mensal de contrato futuro
  - correcao do usuario: "temos as series historicas do INDICE e DOLAR
  (series continuas) na corretora nacional que sao os mesmos Indice e Dolar mas
  ticker com nome diferente"); GOLD/ChinaA50/GBPUSD/USDSEK sao os 4
  preditores com causalidade de Granger confirmada sobre Dolar
  (causa_dolar=True, lag=1) e ficam na corretora internacional, nao na corretora nacional -
  confirmado pelo usuario: "a corretora sera a activ pois a corretora nacional nao
  tem essas cotacoes".
- Roda nos dois brokers na mesma execucao, reaproveitando o loop
  conectar()/coletar_alvo()/desconectar() por broker que ja existia em
  executar() - nenhum broker/conexao nova, so o filtro de alvos.
- Se --so pedir uma raiz que nao existe em config.json -> ativos, imprime
  aviso (nao interrompe a rodada com os demais alvos validos).
