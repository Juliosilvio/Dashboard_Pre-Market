Historico de versoes — api_server.py
-------------------------------------------------------------------------
1.0.0 - 2026-09-15 - Julio - Criacao do script. Pedido do usuario: montar a
                              arquitetura do frontend em React. Como o
                              navegador nao le arquivo local nenhum, faltava
                              uma ponte HTTP entre o disco (json/last_json/*.json,
                              json/config.json) e a SPA React. Servidor
                              FastAPI local, sem estado em memoria (le o
                              arquivo na hora a cada request — arquivos
                              pequenos, custo de disco desprezivel). Reusa a
                              MESMA logica de leitura double buffer que
                              last_nac.py/last_int.py usam pra escrever
                              (_ler_double_buffer: compara mtime dos dois
                              arquivos _a/_b, le o mais recente, com
                              fallback pro outro se pegar uma leitura corrompida
                              no meio de uma troca rara). Endpoints:
                              /api/last/nac, /api/last/int, /api/last
                              (merge dos dois), /api/vigentes (config.json ->
                              chave "vigentes", escrita pelo vigente.py),
                              /api/curvas/{tipo} devolvendo HTTP 501 de
                              proposito pros tres tipos (juros, frc,
                              cupom-inflacao) — o calculo de curva (agrupar
                              contrato por vertice de vencimento) esta
                              marcado como "Pendente" na arquitetura do
                              projeto, entao o endpoint reserva o contrato
                              sem fingir dado que nao existe. CORS liberado
                              so pra localhost:5173 (porta padrao do Vite em
                              dev).
1.1.0 - 2026-09-15 - Julio - Pedido do usuario: primeiro grafico de curva de
                              verdade (juros/DI1) — /api/curvas/juros deixa
                              de devolver 501 e passa a calcular dado real.
                              Novo par de helpers: _decodificar_vertice_b3()
                              (decodifica um ticker B3 tipo "DI1V26" de volta
                              pro vertice de vencimento "10/2026" — caminho
                              inverso do _ticker_b3() do vigente.py, mesma
                              tabela LETRA_MES) e _serie_curva_br(raiz, campo,
                              registros) (monta uma serie [{rotulo, valor}]
                              pra uma raiz de curva_br, lendo config.json ->
                              vigentes -> <raiz> pra saber quais tickers
                              existem e o double buffer do last_nac.py pra
                              pegar o valor de cada um — last ou
                              session_close). Resposta de /api/curvas/juros:
                              {"last_di1": [...], "session_close_di1": [...],
                              "session_close_oc1": [...]}. OC1 so entra com
                              session_close (nunca tem last — ver
                              last_nac.py 1.7.0/vigente.py). frc e
                              cupom-inflacao continuam devolvendo 501 (ainda
                              nao foram calculados).
1.2.0 - 2026-09-15 - Julio - Pedido do usuario: redimensionar os paineis do
                              frontend e ter um botao "Salvar layout" no
                              menu superior, salvando tambem no backend (nao
                              so no navegador). Novos endpoints GET/POST
                              /api/layout, lendo/gravando json/layout.json —
                              arquivo PROPRIO deste endpoint (nenhum outro
                              script do pipeline mexe nele, sem risco de
                              corrida com vigente.py/last_nac.py). GET
                              devolve {} se ninguem salvou layout ainda;
                              POST recebe o objeto de layout INTEIRO (sem
                              merge parcial — o frontend manda tudo de novo
                              a cada salvamento) e grava via arquivo
                              temporario + os.replace (mesma logica atomica
                              do double buffer, adaptada pra escrita unica).
                              CORS passou a liberar tambem o metodo POST
                              (antes so GET).
1.3.0 - 2026-09-16 - Julio - Pedido do usuario: depois de tirar as bolinhas
                              de cada vertice do grafico de juros (JurosChart
                              .jsx), perguntou como salvar "esse tipo de
                              formato" — ou seja, quer as escolhas de ESTILO
                              do grafico persistidas como configuracao, nao
                              so hardcoded no componente. Novo par de
                              endpoints GET/POST /api/config-visual,
                              lendo/gravando json/config_visual.json — mesma
                              logica do /api/layout (arquivo PROPRIO, escrita
                              atomica via .tmp + os.replace, corpo POST e o
                              objeto completo sem merge parcial), so que pra
                              PREFERENCIA DE ESTILO (ex: "mostrarPontos") em
                              vez de posicao/tamanho de painel — arquivo
                              separado de layout.json de proposito, pra cada
                              preocupacao ficar isolada na sua propria
                              gaveta. Novos helpers _ler_config_visual()/
                              _salvar_config_visual(), espelhando
                              _ler_layout()/_salvar_layout(). CORS/metodos
                              nao mudaram (POST ja estava liberado desde a
                              1.2.0).
1.4.0 - 2026-09-16 - Julio - Pedido do usuario: "podemos adicionar aos
                              outros graficos os contratos que neles faltam e
                              session close e last?" — FRC e Cupom de
                              Inflacao (raiz DAP) deixam de devolver HTTP 501
                              e passam a calcular dado REAL, igual o DI1 fez
                              na 1.1.0. /api/curvas/frc devolve {"last_frc":
                              [...], "session_close_frc": [...]};
                              /api/curvas/cupom-inflacao devolve {"last_dap":
                              [...], "session_close_dap": [...]}. Reusa a
                              MESMA _serie_curva_br() generica que ja existia
                              pro DI1 (nenhum helper novo precisou ser
                              escrito) — a unica diferenca do DI1 e que FRC/
                              DAP nao tem uma raiz-irma so-com-session_close
                              tipo o OC1, entao cada uma tem so as 2 series
                              da propria raiz. Novo dict RAIZ_POR_TIPO_CURVA
                              (tipo do contrato HTTP -> raiz B3 em config
                              .json->vigentes) substitui o bloco que
                              levantava 501 pra esses dois tipos.
1.5.0 - 2026-09-16 - Julio - Pedido do usuario: ordenar a tabela de cotacoes
                              "conforme o peso de cada um no indice e no
                              dolar", usando correlacao REAL. Novo endpoint
                              GET /api/peso-mercado, lendo
                              parquet/calculos/pesoMercadoD1.parquet (escrito
                              pelo correl.py -> AnalisadorCorrelacao
                              .calcular_peso(), ver correl.md 1.1.0) — devolve
                              um dict symbol -> {correlacao_indice,
                              correlacao_dolar, peso}. Novo helper
                              _ler_peso_mercado(), mesma convencao defensiva
                              dos outros _ler_*() (devolve {} se o arquivo
                              ainda nao existir). PRIMEIRA vez que este
                              servidor le parquet — todo o resto e JSON puro
                              — entao pandas entrou como dependencia nova do
                              script (import protegido por try/except, mesmo
                              padrao MetaTrader5/psutil dos outros scripts).
                              CORS/metodos nao mudaram (GET ja bastava).
1.6.0 - 2026-09-17 - Julio - Pedido do usuario: montar um card separado pro
                              "Trio" da B3/Anbima (DOL + DDI + DI1 no mesmo
                              vencimento — quando as tres pernas nao fecham a
                              conta, e sinal de desalinhamento de preco).
                              Novo endpoint GET /api/curvas/trio, tipo "trio"
                              em TIPOS_CURVA_VALIDOS. Este projeto ainda nao
                              coleta a curva de VENCIMENTOS do dolar futuro
                              (DOLAR/DOL) — so o continuo Dolar (ativos.
                              nacionais) — entao a perna DOL fica de fora por
                              enquanto (documentado no proprio docstring do
                              endpoint; da pra estender pro Trio completo se
                              um dia o projeto passar a coletar essa curva,
                              resolvivel pelo vigente.py igual DI1/DAP/FRC/
                              DDI). O que da pra calcular hoje: DDI (cupom
                              cambial REAL negociado, so ~5 vertices liquidos
                              desde que "DDI" entrou em ativos.curva_br) x
                              FRC (cupom cambial TEORICO/"limpo", curva
                              cheia). Novo helper _serie_trio() — pega a
                              serie do DDI (curta) e SO aceita o FRC dos
                              MESMOS vertices, descartando o resto da curva
                              do FRC (~39 vertices) que dominaria a escala do
                              grafico e esconderia a divergencia — devolve
                              {"last_ddi": [...], "last_frc": [...],
                              "spread_ddi_frc": [...]}, spread = DDI - FRC no
                              mesmo vertice. Reusa _serie_curva_br() ja
                              existente, nenhuma mudanca nela. CORS/metodos
                              nao mudaram (GET ja bastava).
1.7.0 - 2026-09-17 - Julio - Pedido do usuario: depois de perguntar onde o
                              Dolar vigente "deveria" fechar (paridade
                              coberta de juros), pediu um card pequeno ja
                              com o resultado calculado. Novo endpoint GET
                              /api/dolar-teorico. Calcula o dolar futuro
                              TEORICO — Teorico = Spot(USDBRL) x
                              (1+DI1)^(du/252) / (1+CupomFRC x dc/360) — no
                              vertice do Dolar vigente, e compara com o
                              preco REAL negociado desse Dolar. Novos
                              helpers: _decodificar_vertice_americano()
                              (inverso do _ticker_americano() do vigente.py,
                              mesmo espirito do _decodificar_vertice_b3 ja
                              existente, so que pra convencao de ticker da
                              corretora internacional — raiz + 3 letras do mes em ingles
                              + ano), _primeiro_dia_util()/_dias_uteis_ate()
                              (aproximacao do vencimento do DI1/FRC pra
                              contar du/dc — SEM calendario de feriados B3,
                              documentado como aproximacao no docstring) e
                              _dolar_teorico() (junta os 4 insumos — DI1,
                              CupomFRC, spot USDBRL do last_int.py e o
                              proprio Dolar negociado — e roda a formula).
                              Multiplica o resultado por 1000 pra casar com
                              a escala do Dolar/DOLAR (R$ por US$1.000).
                              Devolve {"erro": "..."} quando faltar dado
                              real de algum dos 4 insumos, ou Dolar ainda
                              sem vigente. CORS/metodos nao mudaram (GET ja
                              bastava).
1.8.0 - 2026-09-17 - Julio - Pedido do usuario, depois de ver o card do
                              Dolar Teorico devolvendo erro toda vez ("usa o
                              dolarv26 da corretora nacional pra calcular e desconta os du
                              over"): _dolar_teorico() trocou a perna
                              negociada do Dolar (corretora internacional) pelo DOLAR
                              real (corretora nacional/B3, raiz nova "DOLAR" em
                              ativos.curva_br do config.json, processada
                              pelo vigente.py 2.3.0 — ver RAIZES_TESTE la).
                              Motivo da troca: Dolar vence no ULTIMO dia
                              util do mes, DI1/FRC/DDI/DAP vencem no
                              PRIMEIRO — enquanto o Dolar vigente nao
                              "alcancava" o mes do DI1/FRC (as ~3 semanas
                              finais de todo mes), o card so devolvia
                              "faltando dado real". Como o DOLAR agora vem da
                              MESMA resolver_raiz() do DI1/FRC/DDI no
                              vigente.py, os tres SEMPRE caem no mesmo
                              vertice/mes — decodificado com
                              _decodificar_vertice_b3 (convencao B3, nao
                              mais a americana). Novo helper
                              _ultimo_dia_util() (substitui
                              _primeiro_dia_util(), removido — ficou sem uso)
                              — vencimento REAL do DOLAR (ultimo dia util do
                              mes), usado como alvo do desconto tanto pro du
                              do DI1-over quanto pro dc do cupom cambial
                              (antes descontava pro vencimento do DI1/FRC,
                              so um proxy aproximado). "negociado" agora
                              vem do double buffer do last_nac.py (corretora nacional),
                              nao mais do last_int.py (corretora internacional) — spot
                              USDBRL continua vindo do last_int.py (B3 nao
                              tem instrumento de spot). Removidos por ficarem
                              sem uso: _decodificar_vertice_americano(),
                              NOME_MES, MES_POR_NOME. CORS/metodos nao
                              mudaram (GET ja bastava).
1.9.0 - 2026-09-17 - Julio - Corrigido: mesmo depois da 1.8.0 (DOLAR real),
                              o card continuava devolvendo "faltando dado
                              real de: FRC". Causa: o vigente.py monta o
                              "vigente" de QUALQUER raiz da curva_br como
                              mes atual+1 sem nunca conferir se esse
                              primeiro ticker tem preco real (so os
                              candidatos seguintes passam por
                              _tem_preco_real) — correto pro DI1/DDI/DAP/
                              DOLAR, mas nao pro FRC. Pedido do usuario, que
                              reconheceu o padrao: "os contratos de FRC
                              tem uma regra que diz que ele rola a frente
                              sempre um contrato a mais... enquanto o dolar
                              esta usando v26 pra este mes o FRC ja rolou e
                              usa x26". Confirmado nos dados: FRCV26 nunca
                              teve um preco real sequer no double buffer
                              (nem antes do feed da corretora nacional travar), FRCX26
                              (mes seguinte) tem historico normal — bate
                              com o FRC ser uma taxa a termo (estilo FRA)
                              sintetizada de duas pernas de DDI, que por
                              natureza mira um periodo a frente. Novo
                              helper _mes_seguinte() (mesma logica do
                              vigente.py). _dolar_teorico() agora busca o
                              cupom (FRC) no vertice de _mes_seguinte(ano,
                              mes) do DOLAR/DI1, nao mais no mesmo vertice.
                              Resposta ganhou o campo "vertice_cupom" (o
                              vertice do FRC usado, ex "11/2026", separado
                              de "vertice" — o do DOLAR/DI1) pra deixar
                              explicito no frontend que sao vertices
                              diferentes de proposito. CORS/metodos nao
                              mudaram (GET ja bastava).
-------------------------------------------------------------------------
1.10.0 - 2026-09-21 - Julio - Novo endpoint GET /api/curva-juros: serve
                              parquet/calculos/curva_juros.parquet (indice
                              de juros de prazo constante DI 1 ano/2 anos x
                              Meta Selic, ver curva_juros.py) como serie
                              temporal (um ponto por dia), diferente de
                              /api/curvas/{tipo} que e por vertice de
                              vencimento num dia so. [] se o parquet ainda
                              nao existir (curva_juros.py roda manual por
                              enquanto). Usado pelo novo SelicJurosChart.jsx
                              no frontend.
-------------------------------------------------------------------------

## 1.11.0 - 2026-09-23
- Novo endpoint `/api/yeldcurve` (GET) — curva de juros dos treasurys
  americanos (1M a 30Y), le o double buffer que yeldcurve.py grava
  (`json/last_json/yeldcurve_amostra_a.json` / `_b.json`), mesmo padrao de
  `/api/last/nac`. `yield_pct` = ultimo preco/leitura atual, `prev_pct` =
  fechamento D-1 (confirmado com o usuario). `[]` enquanto o yeldcurve.py
  nao tiver rodado (ou o Excel/Power Query nao estiver aberto). Consumido
  pelo novo painel "Curva de Juros — Treasurys (EUA)" no frontend
  (YeldCurveChart.jsx, ver App.jsx).

## 1.12.0 - 2026-09-23
- Adiciona GET /api/dp - le o double buffer que dp.py grava (projecao de
  desvios de preco MACD/ATR/IFR, Indice/Dolar em MTF). Mesmo padrao de
  /api/yeldcurve (_ler_double_buffer).

## 1.13.0 (2026-09-23)

- Adiciona `GET /api/noticias` — le o double buffer que `noticias.py`
  grava (manchetes em tempo real do canal publico do Telegram
  fonte de noticias). Lista de `{"id", "hora_iso", "texto", "link"}`, mais
  recente primeiro, ate 40 itens. Mesmo padrao double buffer dos demais
  endpoints de tempo real.

## 1.14.0 - 2026-09-25
- Adiciona `GET /api/vies-direcional` — le o double buffer que
  `vies_direcional.py` grava (indice/dolar + cada ativo de
  ativos_referencia_extra, ex.: usatec/Nasdaq), mesmo padrao
  `_ler_double_buffer` dos demais endpoints de tempo real. Primeiro passo
  do frontend pra expandir alem de Indice/Dolar (pedido do usuario:
  "vamos iniciar com o UsaTec/Nasdaq").
- `_ler_peso_mercado()` passa a incluir tambem as colunas
  `correlacao_<nome>` de `config.json -> ativos_referencia_extra` (alem de
  indice/dolar/peso, que ja existiam) — generico, um ativo extra novo no
  config.json ja aparece aqui sem editar este arquivo. Usado pelo
  `QuotesTable.jsx` pra montar a grade de cotacao de qualquer ativo
  operavel novo, nao so Indice/Dolar.

## 1.17.0 - 2026-09-27
- Adiciona `GET /api/modelo-swing/universo` (lista das 129 raizes do
  universo, mesma de `diag_sazonalidade_swings.py`) e
  `GET /api/modelo-swing/{raiz}` (primeiro modelo de "quando/a que preco"
  um proximo topo/fundo deve ocorrer no ativo escolhido — GARCH(1,1) via
  `modelo_garch_swing.py` + vies MACD M15/IFR M5 + horario mais provavel
  ja calculado). Unico par de endpoints do projeto que CALCULA na hora em
  vez de so ler arquivo pronto — pedido do usuario: card com seletor de
  ativo, resultado tem que ser sempre do ativo escolhido no input.
  `_modelo_garch_swing = ModeloGarchSwing()` instanciado uma vez a nivel
  de modulo (so guarda cache do json de sazonalidade); `arch` so e
  importada de fato dentro da chamada, entao o servidor sobe normal
  mesmo antes do `pip install arch`.
-------------------------------------------------------------------------
1.18.0 - 2026-09-27 - Julio - GET /api/modelo-swing/{raiz} passa a chamar
  CenarioFinalSwing (cenario_final_swing.py) em vez de ModeloGarchSwing
  diretamente - resposta agora inclui sinal/direcao_sugerida/confianca/
  alvo_sugerido/entrada_a_mercado/entrada_zona_pullback em cima de todos
  os campos antigos (GARCH continua la dentro, e um superset - ver
  cenario_final_swing.py 1.1.0). Pedido do usuario depois de ver os
  numeros do classificador: "com os numeros gerados por essa fase do
  sistema precisamos de recomendacao de onde o preco pode ir e qual e a
  entrada". `_cenario_final_swing = CenarioFinalSwing()` substitui
  `_modelo_garch_swing` a nivel de modulo; 500 tambem se os .joblib do
  classificador ainda nao tiverem sido treinados (FileNotFoundError).
  GET /api/modelo-swing/universo sem mudanca (continua orfao do
  frontend). ModeloSwingCard.jsx (v3.0.0) ganhou bloco de destaque com
  direcao/confianca/alvo/entradas.
-------------------------------------------------------------------------
## 1.19.0 - 2026-09-27
- `uvicorn.run(..., host="0.0.0.0")` (era `"127.0.0.1"`) e CORS trocado de
  `allow_origins` fixo pra `allow_origin_regex` liberando localhost/127.0.0.1
  e qualquer IP `100.x.x.x` (faixa CGNAT do Tailscale) na porta 5173 -
  pedido do usuario: "quero compartilhar essa pagina do indice e do dolar
  com um colega" via VPN (Tailscale). `frontend/src/api/client.js` (1.1.0)
  passou a montar a URL da API a partir de `window.location.hostname` em
  vez de `"localhost"` fixo, e `frontend/vite.config.js` ganhou `host: true`
  - sem os tres, o colega abrindo pelo IP da VPN receberia
  ERR_CONNECTION_REFUSED (Vite/uvicorn so aceitando localhost) ou o
  navegador dele tentaria buscar a API no proprio PC dele (BASE_URL fixo).
  Firewall do Windows precisa liberar as portas 8000/5173 pra entrada -
  fora do escopo deste script, orientado ao usuario separadamente.
-------------------------------------------------------------------------
1.20.0 - 2026-09-27 - Julio - `/api/layout` e `/api/config-visual` passam a
  aceitar query opcional `?cliente=<id>` e gravar um arquivo POR CLIENTE
  (`json/layout_<id>.json` / `json/config_visual_<id>.json`) em vez de um
  unico arquivo global (`json/layout.json` / `json/config_visual.json`).
  Pedido do usuario logo depois de entender a implicacao do
  compartilhamento via VPN (1.19.0 acima): "tinha que ser por pessoa" - sem
  isso, o colega clicando "Salvar layout" (ou mudando um toggle de config
  visual) reescreveria o layout/config que o proprio Julio tambem ve,
  porque os dois estariam lendo/escrevendo o MESMO arquivo. `client.js`
  (1.2.0) gera um id aleatorio uma vez por NAVEGADOR (guardado no
  localStorage dele, nunca sai do navegador) e manda em toda chamada desses
  dois endpoints. `_CLIENTE_ID_RE` valida o id (so alfanumerico/hifen/
  underscore, max 64 chars) antes de vira-lo nome de arquivo - protege
  contra path traversal. Sem `?cliente` (chamada antiga/direta, ex.: curl),
  cai no arquivo global de sempre - compatibilidade preservada. Quando um
  cliente novo ainda nao tem arquivo proprio, a LEITURA cai pro arquivo
  legado global como ponto de partida (ex.: o colega herda o layout atual
  do Julio no primeiro acesso, em vez de nascer no layout padrao vazio) -
  a proxima gravacao (autosave ou toggle) ja isola esse cliente sozinho.
  Testado de verdade (ponte Linux, dado real montado): sem cliente le o
  layout.json real do Julio (22 paineis); cliente novo salva e le isolado;
  cliente sem arquivo proprio ainda herda o legado; cliente com caracteres
  invalidos cai pro global sem erro.
-------------------------------------------------------------------------
1.21.0 - 2026-09-29 - Julio - Adiciona `GET /api/grades-cotacoes` - registro
  declarativo de cada pagina/view do frontend (nome de exibicao, raiz de
  referencia e quais FEEDS compoem a grade de cotacoes daquela pagina).
  Pedido do usuario: um "controller" pra quando novas abas forem criadas o
  sistema ja saber quais ativos entram na grade daquela aba, sem editar
  `App.jsx`. Nova chave `config.json -> grades_cotacoes` (nome/feeds) e
  SEPARADA de `ativos_referencia_extra` (broker/raiz) de proposito -
  juntar as duas quebraria `correl.py`/`vies_direcional.py`/`dp.py`, que
  exigem `raiz`/`broker` em todo item desse dict (`dp.py` ja documentava
  esse risco: "se TLT/IEF/SHY entrassem em ativos_referencia_extra,
  apareceriam como views fantasmas no menu"). O endpoint so LE as duas
  chaves e devolve mesclado - nao escreve nada, nao muda nenhum script
  existente nem endpoint ja em uso. Ver `client.js` 1.3.0 e `App.jsx`
  (consome o novo endpoint em vez do `ATIVOS_EXTRA_INFO` hardcoded) e
  "Decimo passo" no `arquitetura.md`.
-------------------------------------------------------------------------
1.22.0 - 2026-09-29 - Julio - Adiciona `GET /api/last/sentimento-em` -
  cotacao + variacao intradiaria de EWZ (iShares MSCI Brazil) e EEM
  (iShares MSCI Emerging Markets), mesmo padrao double buffer de
  `GET /api/last/magnificas`, le o que `sentimento_em.py` grava. Pedido
  do usuario: "colocar o EWZ no Risk indice" (ampliado pra EEM: "ambos
  ja estao visiveis"). Depende de `historico.py` 1.4.0 (grupo
  `etfs_sentimento_em`) e `ExportadorMt5Stock.mq5` 1.01. Pra esses dois
  ativos aparecerem na grade de cotacoes, `config.json ->
  grades_cotacoes.principal.feeds` precisa incluir `"sentimento_em"`
  (ver `client.js`/`App.jsx`).
-------------------------------------------------------------------------
1.23.0 - 2026-09-30 - Julio - _dolar_teorico(): duas mudancas no mesmo
                              incidente (Dolar Teorico preso em "faltando
                              dado real de FRC" mesmo depois do fix do
                              correl.py/resolver_raiz_americano() mais cedo
                              hoje). (1) Parou de CALCULAR o vertice do
                              cupom FRC como "mes do DOLAR + 1" (pressuposto
                              fixo que virou falso na pratica depois do fix
                              do resolver_raiz() no vigente.py 2.6.0 -- o
                              FRC vigente de verdade saiu 2 meses a frente
                              do DOLAR, nao 1) -- agora usa DIRETO o ticker
                              que vigentes["FRC"][0] ja resolveu
                              (verificado, com preco real confirmado), sem
                              recalcular vertice nenhum; se a distancia
                              FRC-DOLAR mudar de novo no futuro, este codigo
                              nao precisa mudar. (2) Trocou o "spot" da
                              formula de paridade (era o ultimo tick do
                              USDBRL) por um proxy de PTAX do Bacen: pedido
                              do usuario -- o DOLAR/DOL liquida contra PTAX e
                              o DI1/FRC ja sao precificados com essa
                              convencao implicita, entao misturar tick
                              instantaneo com curvas PTAX-referenciadas
                              introduzia ruido na formula. Nova funcao
                              _ptax_proxy_usdbrl(): replica as 4 janelas
                              oficiais de apuracao do Bacen
                              (10h-10h10/11h-11h10/12h-12h10/13h-13h10
                              horario de Brasilia -- metodologia confirmada
                              via busca), aproxima cada janela com OHLC4
                              (Abertura+Maxima+Minima+Fechamento)/4 dos
                              candles M1 do USDBRL daquela janela (nao ha
                              acesso as cotacoes de dealers que o Bacen usa
                              de verdade), e tira a media das janelas que
                              ja FECHARAM e tiveram dado real --
                              parcial/progressivo ao longo da manha, trava
                              depois das 13h10 (pedido do usuario: "faz pra
                              vermos"). Resposta do endpoint ganha ticker_f
                              rc/ptax_proxy_janelas/ptax_proxy_janelas_comp
                              letas; spot_usdbrl continua o mesmo nome de
                              campo (frontend nao precisou mudar). Backup: 
                              api_server.py.bak_antes_ptax_proxy_20260930_1
                              84222.
---------------------------------------------------------------------------
1.24.0 - 2026-09-30 - Julio - _ler_peso_mercado() passa a mesclar
                              causalidadeD1.parquet (causalidade.py, novo
                              -- ver versoes/causalidade.md) no dict que ja
                              devolvia peso/correlacao_indice/correlacao_dolar
                              por symbol -- causa_indice/causa_dolar (+ _p/_lag)
                              so entram quando True, pra nao inflar o
                              payload com falso pra todo mundo.
                              Opcional/resiliente igual PESO_MERCADO_PATH:
                              se causalidadeD1.parquet nao existir ainda
                              (script nunca rodado), {} e o resto do
                              endpoint funciona normal. Pedido do usuario:
                              "adicione nas tabelas de risk mesmo ja
                              existentes" -- ver QuotesTable.jsx (badge
                              "G") e causalidade.py.
---------------------------------------------------------------------------
1.25.0 - 2026-09-30 - Julio - _dias_uteis_ate()/_ultimo_dia_util() passam a
                              descontar feriados da B3, nao so fim de
                              semana. _pascoa(ano) (Meeus/Jones/Butcher)
                              deriva os feriados moveis (Carnaval,
                              Sexta-feira Santa, Corpus Christi) e
                              _feriados_b3(ano) junta com as datas fixas
                              confirmadas no calendario oficial 2026 da B3
                              (b3.com.br) -- validado 1:1 contra ele.
                              _e_dia_util_b3(d) e o helper comum. NAO
                              inclui 09/07 (feriado so de SP, B3 opera
                              normal) nem 18/02 (Quarta de Cinzas, so
                              expediente reduzido). dias_corridos (dc, base
                              Actual/360 do cupom cambial) continua
                              intocado -- so o du (base 252 do DI1) mudou.
                              Auto-suficiente: nao precisa baixar/atualizar
                              calendario nenhum ano, so recalcula a Pascoa.
                              Testado: ultimo dia util nov/2026 foi de 30
                              (sex, 20/11 e feriado) pra confirmar o
                              desconto; dolar_teorico() rodou ok com os
                              novos du. Pedido do usuario: "precisamos
                              baixar o calendario de vencimento?". Backup:
                              api_server.py.bak_antes_feriados_b3_20260930_
                              191805.
---------------------------------------------------------------------------
1.26.0 - 2026-10-01 - Julio - _dolar_teorico() passa a usar
                              _ptax_proxy_usdbrl_com_fallback() em vez de
                              _ptax_proxy_usdbrl() direto -- antes das
                              ~10h10 BRT (nenhuma janela de PTAX de hoje
                              fechou ainda), o card ficava ~1h toda manha
                              em "sem dados". Agora, quando nao ha PTAX
                              real de hoje, extrapola o ultimo PTAX real
                              conhecido (normalmente o de ontem, 4
                              janelas) pela variacao D1 do DXY (USDInd
                              vigente, corretora internacional) desde o fechamento de
                              ontem: anterior * (1 + variacao_dxy) -- ver
                              _variacao_d1_dxy() e
                              _ptax_proxy_usdbrl_com_fallback(), novas.
                              Resposta ganha spot_estimado (bool) +
                              spot_estimado_anterior/
                              spot_estimado_variacao_dxy_pct quando esse
                              caminho e usado -- DolarTeoricoCard.jsx v1.1
                              mostra uma tag "ESTIMADO" visivel nesse
                              caso, nunca deixa parecer PTAX real. Se nao
                              houver dia anterior com PTAX completo nem
                              DXY vigente/double buffer, cai de volta pro
                              comportamento antigo (valor=None, "sem
                              dados"). Pedido do usuario: "mostre o
                              anterior ate as 10:10 quando o novo ira
                              surgir e o anterior deve vir multiplicado
                              pela variacao D1 do dxy, tipo
                              Anterior*(1+vardxy)". Testado standalone
                              contra os dados reais de hoje (2026-10-01,
                              07h BRT): ontem fechou 5,17016 (4/4
                              janelas), DXY +0,363% desde o fechamento ->
                              estimado 5,18894. Backup:
                              api_server.py.bak_antes_fallback_ptax_dxy_
                              20261001.
---------------------------------------------------------------------------
1.27.0 - 2026-10-01 - Julio - BUG CORRIGIDO em _janela_ptax_utc()/
                              _ptax_proxy_usdbrl(): somava +3h (premissa
                              errada de que o m1.parquet estaria em UTC
                              verdadeiro) antes de comparar com df["time"]
                              -- que na verdade esta em horario DIRETO de
                              Brasilia (fuso_horario.py corrige a
                              corretora internacional exatamente pra isso, corretora nacional ja
                              nasce assim). Efeito pratico: a janela
                              "10:00-10:10 BRT" buscava candle rotulado
                              "13:00-13:10" (futuro a maior parte da
                              manha) -- sempre vinha vazia, mas o campo
                              completa virava True cedo demais porque
                              "agora" tambem estava em UTC verdadeiro
                              (~3h "na frente" do rotulo real). Resultado:
                              o PTAX NUNCA virava real, o dia inteiro --
                              so parecia "ainda nao fechou" (ver conversa
                              2026-10-01 de manha, incl. a 1.26.0 logo
                              acima, cujo fallback estimado via DXY so
                              existe PORQUE esse bug escondia o PTAX real
                              o tempo todo). Corrigido: _janela_ptax_utc()
                              nao soma mais nada, e "agora" (dentro de
                              _ptax_proxy_usdbrl() e
                              _ptax_proxy_usdbrl_com_fallback()) passa a
                              ser calculado no mesmo horario direto de
                              Brasilia antes de comparar com os limites de
                              janela / resolver "hoje" (tambem corrige um
                              off-by-one-day latente perto da meia-noite
                              BRT, nao reproduzido ainda mas mesma causa).
                              Validado contra o parquet real as 10:45 BRT
                              de hoje: janela 10:00-10:10 agora acha os 10
                              candles de verdade (preco 5,17769), janelas
                              11h/12h/13h corretamente completa=False
                              (ainda nao aconteceram) -- antes do fix as
                              3 apareciam completa=True com preco=None.
                              PTAX de ontem (dia inteiro fechado, 4/4
                              janelas) recalculado com a janela certa:
                              5,17603 -- os valores mostrados na conversa
                              de hoje de manha (ex: "ontem fechou
                              5,17016", estimados em 5,19021/5,18945)　
                              vieram das janelas ERRADAS (rotulo 13h-16h10
                              de ontem, nao 10h-13h10) -- nao sao PTAX de
                              verdade, ficam obsoletos com este fix.
                              FUSO_BRASILIA_PARA_UTC removida (ficou sem
                              uso). Backup:
                              api_server.py.bak_antes_fix_fuso_ptax_
                              20261001.
---------------------------------------------------------------------------
