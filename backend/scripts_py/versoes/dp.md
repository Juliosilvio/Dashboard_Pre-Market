# Changelog - dp.py

## 1.0.0 - 2026-09-23
- Criacao do script. Projecao de desvios de preco (regiao mais provavel
  de cruzamento do MACD + faixa de preco em torno dela) pra Indice/Dolar em
  MTF (M15, M30, H1, H4, D1, W1) - formaliza em script tudo que foi
  validado manualmente com o usuario durante a sessao de 2026-09-23:
  - Perna atual do histograma: ultimo cruzamento de zero -> ponta
    (pico/vale) -> so projeta se ja esta voltando pro zero. Descartado
    regredir as 2 linhas MACD/sinal cruas (instavel quando andam quase
    paralelas - testado, deu valores absurdos tipo -103.682 no Indice W1).
  - Regressao linear na perna (ponta ate agora), separada no histograma
    (candles_a_frente) e no preco (preco_projetado); media_base =
    (preco_projetado + fechamento_atual) / 2.
  - Desvios 1-2: MACD (direcao) + ATR (tamanho de candle) linear, NAO
    raiz do tempo - candles nao sao independentes quando o MACD ja
    confirma direcao. Validado com 1 evento real (Indice H1, candle das
    09h->10h de 2026-09-23: fechamento 186.800->189.405, maxima 190.140,
    candle de ~3.3x o ATR): projetando fechamento + n*ATR na direcao do
    MACD, 3 passos bateu o fechamento seguinte (erro 0.08%) e 3.5 passos
    bateu a maxima (erro 0.07%). Ressalva: validado com 1 evento so ate
    agora, nao assumir taxa de acerto sem mais teste.
  - Desvios 3-4: estatistico classico, ATR * sqrt(candles_a_frente) em
    torno da media_base, probabilidade = cauda da normal padrao (1 lado).
  - Certificacao por IFR: cada nivel de desvio (1-4, cima e baixo, dos 2
    metodos) simula o preco como proximo fechamento e recalcula o IFR -
    fora de 30-70 = "esticado" (matematicamente possivel mas ja em
    sobrecompra/sobrevenda antes de chegar la).
  - Mesmo padrao double-buffer (dp_amostra_a/b.json) e mtime-watch
    (recalcula so quando o parquet de preco muda) de
    last_indicadores_nac.py - 12 combinacoes (Indice/Dolar x MTF).
- Pedido do usuario (2026-09-23), em varias mensagens seguidas
  desenhando/refinando o metodo: "quero saber no preco qual regiao mais
  provavel vai acontecer... o proximo cruzamento das medias, onde esta a
  linha 0, e usando regressao linear qual o preco mais provavel" ->
  "precisamos sempre do proximo cruzamento... e nao de cruzamentos que ja
  foram" -> "pega as pontas da linha e projeta... regressao linear" ->
  "usar RSI pra certificar que as bandas estao dentro de 30 e 70" -> "atr
  e tamanho de candle... podemos projetar o tamanho do candle usando MACD
  junto com atr" -> validado com o salto real do Indice H1 -> "monta, vamos
  testar em tempo real, o script vai chamar dp.py".
- Testado em tempo real no device do usuario: rodado por alguns segundos,
  gravou as 12 combinacoes no double buffer corretamente (fases da perna
  variando entre cruzou_agora/indo_pra_ponta/voltando conforme o estado
  real de cada TF no momento do teste).

## 1.1.0 (2026-09-23)

- Consenso multi-timeframe: o usuario viu a v1.0.0 rodando ao vivo no
  dashboard (grade com as 12 combinacoes Indice/Dolar x MTF, uma mini-card
  cada) e pediu pra simplificar: "nao precisa disso projecao em 5 TF????
  pra que faz duas tabelinhas so com Indice e Dolar, uma pra cada e usas
  dentre todos os TF a regressao linear pra ver qual o mais provavel dos
  pontos entendeu?". Perguntado qual seria o eixo x dessa regressao entre
  TFs, respondeu: "o eixo x e a media que mais se repetir dentre as 5
  tabelas dos TF entendeu?" - ou seja, nao e uma regressao no sentido
  literal (TF nao e uma variavel continua), e sim um consenso por
  agrupamento: a media (media_base) que mais TFs concordam e a resposta.
- `_consolidar(ativo)` (novo metodo): agrupa os media_base das TFs em
  fase "voltando" que ficam dentro de `TOLERANCIA_CONSENSO_PCT` (0.5%)
  uma da outra, pega o MAIOR grupo (o "eixo x mais repetido"), tira a
  media desse grupo (`media_consolidada`) e usa a TF MAIS CURTA dentro do
  grupo vencedor (`TF_ORDEM`) como referencia de ATR/direcao/horizonte
  pra montar os 4 desvios em torno do centro consolidado (mesma logica
  momentum_atr/estatistico_normal de `_calcular_um`, so que centrada em
  `media_consolidada` em vez de `media_base` individual). TFs fora do
  grupo vencedor (ex: ponta recente pouco confiavel, ou perna numa
  direcao diferente) ficam de fora do calculo mas aparecem em
  "tfs_fora_consenso" pra transparencia. Ativo sem nenhuma TF em
  "voltando" ainda -> `_consolidar` devolve None, nao entra no
  "consolidado" (evita inventar consenso sem dado).
- JSON de saida mudou de lista plana pra `{"detalhe": [...], "consolidado":
  [...]}` - "detalhe" mantem as 12 combinacoes originais (usado so pra
  depuracao/auditoria), "consolidado" tem no maximo 2 entradas (uma por
  ativo), e e isso que o front (`DesviosPainel.jsx`) passa a consumir.
- Testado em tempo real no device: `_consolidar` rodou certo nos dois
  ativos - Indice so tinha 1 TF (D1) em "voltando" no momento do teste,
  entao usou ela sozinha (grupo de 1); Dolar tinha 3 TFs em "voltando"
  (M15, H4, W1) com media_base entre 5.132 e 5.168, o algoritmo agrupou
  as 3 dentro da tolerancia (cada uma checada contra as outras, nao so
  pares mutuos - por isso um grupo pode incluir 2 pontas que entre si
  passam de 0.5% mas ambas ficam dentro de 0.5% da 3a) e usou M15 (a
  mais curta) como referencia de ATR/direcao.

## 1.2.0 (2026-09-25)
- Pedido do usuario depois de replicar Curva de Treasurys/DP/Noticias na
  view do Nasdaq: "mas aqui tem que apresentar os valores apenas para
  nasdaq" - o card de Desvios estava mostrando SEMPRE Indice/Dolar, mesmo
  dentro da view do Nasdaq (dado global, sem parametrizacao por view).
- `ATIVOS_DESEJADOS` (Indice/Dolar) virou so a base FIXA. Novo metodo
  `_resolver_ativos_extra()` le `config.json -> ativos_referencia_extra`
  (mesmo padrao ja usado em `correl.py`/`vies_direcional.py`: lista fica
  no JSON, adicionar um ativo novo e so uma linha no config, sem editar
  este script) e devolve as RAIZES desses ativos. `self.ativos = list
  (ATIVOS_DESEJADOS) + self._resolver_ativos_extra()`, usado tanto pra
  montar `self.caminhos_preco` (antes so com o modulo-level
  ATIVOS_DESEJADOS) quanto no loop de `_flush()` que monta "consolidado".
- Diferente de `correl.py`, nao precisou resolver ticker VIGENTE: as
  pastas `parquet/historicos/MTF/<raiz>/<tf>.parquet` ja sao gravadas por
  RAIZ pro universo inteiro (`indicadores_mtf.py`/`historico.py`), entao a
  raiz do config.json E o nome da pasta direto - `_resolver_ativos_extra`
  so le e devolve a lista, sem `vigentes` nem broker.
- `DesviosPainel.jsx` ganhou prop `ativos` (default `["Indice", "Dolar"]`,
  mesmo comportamento de sempre pra view principal) pra escolher quais
  blocos do "consolidado" mostrar em cada view - a view do Nasdaq passa
  `ativos={["UsaTec"]}`.
- Testado (main.py rodando): pasta `parquet/historicos/MTF/UsaTec/`
  confirmada com os 6 timeframes (M15 a W1), `self.ativos` passou a
  incluir "UsaTec" automaticamente a partir do config.json, sem editar
  este arquivo.

## 1.3.0 - 2026-09-26
- Segunda fonte de ativo extra, separada de ativos_referencia_extra:
  config.json -> dp_ativos_extra. Pedido do usuario ("ve se tem alguma
  acao ou ativo que reflete os juros americanos treasurys") - achados
  TLT/IEF/SHY no catalogo do terminal mt5stock (MetaQuotes-Demo). Nao
  entraram em ativos_referencia_extra porque essa chave tambem alimenta
  vies_direcional.py, cujas chaves viram itens do menu dropdown de view
  no frontend (App.jsx -> viewsExtra) - TLT/IEF/SHY sao um CARD dentro da
  view usatec, nao uma view nova; se entrassem la, apareceriam como views
  fantasmas no menu. _resolver_ativos_extra() agora le as duas chaves e
  junta as raizes (sem duplicar).
