Historico de versoes — main.py
-------------------------------------------------------------------------
1.0.0 - 2026-09-13 - Julio - Criacao do script (classe Orquestrador). Roda
                              int.py e nac.py em paralelo (processos
                              separados, uma conexao MT5 cada), junta o
                              resultado em historico_d1.parquet e apaga os
                              intermediarios
1.1.0 - 2026-09-13 - Julio - mesclar() agora combina com o historico_d1
                              .parquet ja existente (nao sobrescreve mais do
                              zero) e remove duplicatas por
                              broker+symbol+timeframe+time, mantendo o candle
                              mais recente buscado — acompanha a coleta
                              incremental dos coletores
1.2.0 - 2026-09-13 - Julio - Adiciona a fase M5: roda int_m5.py e nac_m5.py
                              (depois da fase D1, pra nao sobrecarregar o
                              mesmo terminal com duas coletas pesadas ao
                              mesmo tempo) e mescla o resultado em
                              historico_m5.parquet, com a mesma logica de
                              merge/dedup do D1 (_mesclar_arquivo() agora
                              generico pros dois timeframes)
2.0.0 - 2026-09-15 - Julio - Vira o controlador unico do projeto: alem de D1/M5,
                              agora roda TODO o pipeline em ordem (vigente ->
                              grade -> scan_ativos -> D1 -> M5 -> retorno ->
                              correl/descorrel) e nunca para sozinho — em vez
                              de rodar uma vez e sair, entra num loop que so
                              comeca a proxima volta quando o candle M5 de
                              Indice (corretora nacional) E EURUSD (corretora internacional) tiverem
                              avancado desde a volta anterior (timestamp epoch
                              e absoluto, entao sincroniza as duas corretoras
                              sem depender do fuso de servidor de cada uma,
                              que sao diferentes). Tambem sobe, logo no
                              inicio, dois processos continuos de tempo_real
                              .py (um por corretora) que ficam gravando cada
                              mudanca de preco em paralelo, no proprio ritmo,
                              sem esperar o pipeline em lote. Ao encerrar
                              (Ctrl+C), cria o arquivo-sinal
                              _stop_tempo_real.flag pros dois processos de
                              tempo_real.py pararem gravando o buffer deles
                              antes de sair — terminate() no Windows mataria
                              sem chance de rodar esse flush.
3.0.0 - 2026-09-15 - Julio - Troca tempo_real.py (script unico, corretora por
                              argumento) por dois processos dedicados:
                              last_nac.py (corretora nacional) e last_int.py (corretora internacional).
                              Motivo: mesmo como processos Python separados,
                              qualquer processo que conecta com o MESMO
                              path/login/server do MT5 gruda no MESMO
                              terminal64.exe ja aberto (assim que o MT5
                              funciona) — entao o tempo_real ficava
                              competindo pelo mesmo canal de IPC com
                              vigente.py/grade.py/nac.py/int.py durante o
                              ciclo pesado do pipeline, e o preco travava
                              atras de um backfill pesado (confirmado em
                              producao logo apos zerar historico_d1/m5
                              .parquet). last_nac.py/last_int.py assumem o
                              papel de _iniciar_last()/_parar_last() (antes
                              _iniciar_tempo_real()/_parar_tempo_real()), com
                              o arquivo-sinal renomeado pra
                              _stop_last.flag. tempo_real.py fica no projeto
                              sem uso (nao e mais chamado por aqui).
3.1.0 - 2026-09-15 - Julio - Reduz a reconexao do proprio main.py no terminal
                              MT5 compartilhado (usuario reportou last ainda
                              sem atualizar em tempo real mesmo com
                              last_nac.py/last_int.py isolados como
                              processo — confirmado que a conexao dedicada
                              deles ainda nao estava configurada no
                              config.json, entao seguiam no terminal
                              compartilhado). _aguardar_novo_m5() agora so
                              reconecta em quem AINDA nao confirmou candle M5
                              novo — assim que a corretora nacional ou a corretora internacional
                              avanca, para de reconectar nela enquanto espera
                              a outra, em vez de reconectar nas duas em toda
                              volta do loop de espera. PAUSA_CHECAGEM_M5
                              tambem sobe de 15 pra 30 segundos. E uma
                              mitigacao (reduz a reconexao, nao elimina) — o
                              isolamento definitivo continua sendo configurar
                              connections["corretora_nacional_tempo_real"]/
                              ["corretora internacional_tempo_real"] com terminal
                              portable dedicado.
3.2.0 - 2026-09-15 - Julio - Remove scan_ativos.py do pipeline. Seu papel
                              (gravar quem esta visivel em
                              parquet/ativos.parquet) ficou orfao desde que
                              nac.py/nac_m5.py/int.py/int_m5.py passaram a
                              ler o visivel direto do MT5
                              (mt5.symbols_get()), sem depender mais desse
                              parquet — nada mais consome a saida do
                              scan_ativos.py. _rodar_lote() agora vai direto
                              de grade.py pra int.py/nac.py.
3.3.0 - 2026-09-15 - Julio - Pedido do usuario: subir o api_server.py junto
                              com o main.py, na ordem de execucao, em vez de
                              precisar abrir na mao todo santo dia. Nova
                              "frente 3": _iniciar_api_server() sobe o
                              api_server.py (FastAPI, ponte HTTP pro
                              frontend React) como subprocess.Popen, igual
                              last_nac.py/last_int.py — mas numa JANELA DE
                              CONSOLE PROPRIA (creationflags=
                              subprocess.CREATE_NEW_CONSOLE), diferente dos
                              last_*, que ficam grudados no console do
                              main.py — vale a pena ver o log do uvicorn
                              (uma linha por request) separado do log do
                              pipeline em lote. Chamado em executar() junto
                              com _iniciar_last(). Ao encerrar,
                              _parar_api_server() so faz terminate() direto
                              (com kill() de seguranca se nao responder em
                              10s) — sem arquivo-sinal como o _parar_last(),
                              porque o api_server.py nao guarda nenhum
                              buffer em memoria que precise ser salvo antes
                              de sair (cada request le o arquivo do disco na
                              hora, sem estado nenhum entre requests).
3.4.0 - 2026-09-16 - Julio - Pedido do usuario: subir tambem o frontend
                              (Vite) junto com o main.py — antes disso,
                              esquecer de rodar 'npm run dev' na mao depois
                              do main.py dava ERR_CONNECTION_REFUSED no
                              navegador (relatado em producao: main.py
                              rodando normal, localhost:5173 recusando
                              conexao). Nova "frente 4": _iniciar_frontend()
                              sobe 'npm run dev' dentro de frontend/ como
                              subprocess.Popen, numa JANELA DE CONSOLE
                              PROPRIA (mesma ideia do api_server.py, frente
                              3) — shell=True porque 'npm' e um .cmd no
                              Windows, nao um .exe. Chamado em executar()
                              logo apos _iniciar_api_server(). Parada exige
                              cuidado extra: 'npm' (.cmd) sobe atras de um
                              cmd.exe intermediario que so DEPOIS sobe o
                              processo de verdade do Vite (node.exe) como
                              FILHO desse cmd — um terminate() simples (como
                              o do api_server.py) so mataria o cmd.exe de
                              fora, deixando o Vite orfao segurando a porta
                              5173 (quebrando o proximo 'npm run dev').
                              _parar_frontend() usa
                              'taskkill /F /T /PID <pid>' (mata a arvore
                              inteira a partir do PID) em vez de
                              proc.terminate().
-------------------------------------------------------------------------
3.5.0 - 2026-09-19 - Julio - Novo passo no pipeline em lote: taxa_usatb.py
                              roda logo depois do retorno.py e antes de
                              correl.py/descorrel.py. Converte o preco do
                              UsaTB (T-Bill futures, corretora internacional) pra taxa
                              de juros implicita — pedido do usuario pro
                              comparativo BR x EUA (inflacao via
                              gasolina), que so tinha curva de juros do
                              lado brasileiro (DI1/DAP/FRC/DDI).
-------------------------------------------------------------------------
3.6.0 - 2026-09-20 - Julio - Novo passo no pipeline em lote: alinhar_d1.py
                              roda logo apos o merge do M5 e antes do
                              retorno.py. Recalcula o D1 da corretora internacional a
                              partir do M5 (agrupado por dia calendario
                              UTC), corrigindo um bug estrutural que fazia
                              o D1 nativo dela ficar incomparavel com o D1
                              da corretora nacional mesmo depois da correcao de fuso
                              horario (ver fuso_horario.py e alinhar_d1.py).
-------------------------------------------------------------------------
3.7.0 - 2026-09-20 - Julio - Novo passo no final do pipeline em lote:
                              historico.py (coleta MTF — todos os
                              ativos/vencimentos, 8 timeframes cada) passa
                              a rodar automaticamente a cada volta, depois
                              de correl.py/descorrel.py. Continua sendo um
                              braco separado (nao alimenta nem depende do
                              resto do pipeline) — colocado por ultimo pra
                              nao atrasar os outputs que o frontend consome.
                              Pedido do usuario.
-------------------------------------------------------------------------
3.8.0 - 2026-09-20 - Julio - Novo passo no final do pipeline em lote:
                              indicadores_mtf.py roda logo apos historico.py,
                              recalculando IFR/ATR/MACD (pasta indicadores/)
                              pra toda a MTF a cada volta. Continua sendo um
                              braco separado (nao alimenta nem depende do
                              resto do pipeline). Pendente: recalculo fica
                              amarrado ao ritmo do loop (sincronizado pelo
                              M5) — ainda nao e tempo real de verdade pro M1
                              (so atualiza a cada fechamento de M5, nao a
                              cada minuto); resolver isso e passo separado,
                              pedido do usuario. Pedido do usuario 2026-09-20.
-------------------------------------------------------------------------

## 3.9.0 - 2026-09-20
- Registra last_indicadores_nac.py (novo, IFR/ATR/MACD de Indice/Dolar em
  tempo real, terminal MT5 proprio) como um terceiro processo dedicado na
  Frente 1, junto de last_nac.py/last_int.py (proc_last, _iniciar_last/
  _parar_last) — resolve a defasagem de ate ~5min que indicadores_mtf.py
  tem dentro do loop em lote, pedido do usuario 2026-09-20 ("nao esqueca
  que precisamos arrumar uma forma de calcular em tempo real os
  indicadores" + "Terminal proprio, separado de tudo").

## 3.9.1 - 2026-09-21
- Correcao de mal-entendido: o pedido do usuario de ontem ("certos
  scripts tem que ter seu proprio terminal") era sobre JANELA DE CONSOLE/
  PowerShell, nao terminal MT5 — eu tinha entendido errado e criado uma
  chave de conexao MT5 desnecessaria (connections["corretora_nacional_indicadores"],
  removida — ver last_indicadores_nac.py 2.0.0).
- last_indicadores_nac.py passa a subir numa JANELA DE CONSOLE PROPRIA
  (CREATE_NEW_CONSOLE), igual api_server.py/frontend. last_nac.py/
  last_int.py continuam grudados no console do main.py — decisao original
  do projeto, nao mexida (nao precisam de log separado).

## 4.0.0 - 2026-09-21
- Consolidacao da serie historica (pedido do usuario: "isso e o que
  precisamos: serie historica em MTF e preco em tempo real, de forma
  centralizada, pra nao errar mais"). O projeto tinha DOIS pipelines de
  coleta independentes buscando D1/M5 do MESMO MT5 pros MESMOS ativos —
  ja causou uma divergencia real (alinhar_d1.py so corrigia uma das duas
  copias). historico.py (MTF) vira a UNICA coleta; nac.py/nac_m5.py/
  int.py/int_m5.py saem do _rodar_lote() (ficam no projeto sem uso, como
  o tempo_real.py antigo) — e o passo de merge (_mesclar_arquivo) foi
  removido.
- Nova ordem do pipeline em lote: vigente.py -> grade.py -> historico.py
  -> alinhar_d1.py (2.0.0, agora corrige o D1 dentro da MTF) ->
  flat_mtf.py (novo, deriva historico_d1/m5.parquet da MTF) -> retorno.py
  -> taxa_usatb.py -> correl.py/descorrel.py -> indicadores_mtf.py.
- Backup do estado anterior (main.py, alinhar_d1.py, nac*.py, int*.py,
  historico_d1/m5.parquet) em backend/_backup_consolidacao_mtf_2026-09-21/
  — pra reverter esse passo se precisar, e so restaurar esses arquivos e
  desfazer a ordem do _rodar_lote().
- Validado ponta a ponta: retorno/correlacao/descorrelacao rodaram contra
  o historico_d1/m5.parquet derivado e bateram IDENTICOS ao pipeline
  antigo (mesmos 29 ativos em correlacaoD1, mesmos 3 em correlacaoM5,
  diferenca de correlacao ~1e-15). Unica mudanca real: profundidade do M5
  caiu de ~360 pra ~90 dias (nao afetou nenhum resultado).

## 4.0.1 - 2026-09-21
- nac.py, nac_m5.py, int.py e int_m5.py EXCLUIDOS do projeto (estavam sem
  uso desde a 4.0.0, pedido do usuario: "se tiverem sem uso e melhor
  excluir" — diferente do tempo_real.py, que so tinha ficado orfao no
  disco). Changelog de cada um mantido em scripts_py/versoes/ como
  registro historico.

## 4.1.0 - 2026-09-21
- Registrado o quarto processo continuo: vies_direcional.py (vies
  direcional de Indice/Dolar + refinamento de entrada via IFR M1/M5),
  janela de console propria (CREATE_NEW_CONSOLE) igual
  last_indicadores_nac.py — nao conecta no MT5. Ver
  versoes/vies_direcional.md.
4.2.0 - 2026-09-21 - Julio - Inclui dadosgov.py no pipeline em lote, rodando
                              em paralelo com vigente.py no inicio do ciclo
                              (nenhum dos dois depende do outro; dadosgov.py
                              tambem nao e dependencia de mais nada ainda).
                              Ver dadosgov.md pro que o script faz (coleta
                              da Selic via API do Banco Central).
-------------------------------------------------------------------------
4.3.0 - 2026-09-21 - Julio - Inclui curva_juros.py no pipeline em lote,
                              rodando em paralelo com flat_mtf.py logo
                              depois do alinhar_d1.py (so depende do D1 do
                              DI1, ja fechado nesse ponto do ciclo, e da
                              Selic, que dadosgov.py ja coletou no inicio
                              do lote). Ver curva_juros.md pro que o script
                              faz (indice de juros de prazo constante x
                              Meta Selic).
-------------------------------------------------------------------------

## 4.4.0 - 2026-09-23
- Inclui yeldcurve.py no grupo de processos continuos (Frente 1), junto
  com last_nac.py/last_int.py — mesmo console compartilhado com o main.py
  (baixo volume de log, uma leitura a cada 5min), mesmo arquivo-sinal de
  parada (_stop_last.flag). Coleta a curva de juros dos treasurys
  americanos (1M a 30Y) lendo excel/treasurys/yeldcurve.xlsx (mantido
  atualizado pelo Power Query do proprio Excel, que o usuario precisa
  manter aberto). Ver yeldcurve.md pro historico completo de como se
  chegou nesse desenho (tentativas de ler a pagina do Investing.com
  direto via urllib/Playwright/CDP, todas bloqueadas ou pouco confiaveis).

## 4.5.0 - 2026-09-23
- Adiciona dp.py ao grupo de processos continuos (self.proc_last), mesmo
  console dedicado de last_indicadores_nac.py/vies_direcional.py
  (CREATE_NEW_CONSOLE) - dp.py so le parquet de preco (sem MT5), roda
  junto com os indicadores continuos.

## 4.6.0 (2026-09-23)

- Adiciona `noticias.py` (manchetes em tempo real do canal publico do
  Telegram fonte de noticias, ver `versoes/noticias.md`) na lista de processos
  continuos (`proc_last`), janela de console propria (mesmo padrao de
  `last_indicadores_nac.py`/`dp.py`/`vies_direcional.py`). Pedido do
  usuario: "noticias em tempo real!!!".

## 4.8.0 - 2026-09-26
- Adiciona amplitude.py (advance/decline + novas maximas/minimas por
  universo, config.json -> amplitude_universos) ao grupo de processos
  continuos (self.proc_last), janela de console propria (mesmo padrao de
  dp.py/noticias.py/vies_direcional.py) - pedido do usuario, agora que a
  view Nasdaq tem universo de verdade (acoes_nasdaq100, via terceiro
  broker mt5stock). So calcula algo depois que historico.py coletar as
  raizes configuradas (roda automatico no ciclo de lote de sempre, nao
  precisa rodar na mao).

## 4.9.0 - 2026-09-27
- Terceiro terminal MT5 (mt5stock) agora abre AUTOMATICO junto com os
  outros dois - pedido do usuario depois de reiniciar o main.py do zero e
  ver so corretora internacional/corretora nacional abrirem ("se tem mais um terminal e ele
  alimenta o projeto tambem, entao obviamente que ele tem que ligar
  automatico"). `_garantir_mt5stock_aberto()`, chamado uma vez no inicio
  de `executar()`, so garante que o EXECUTAVEL esta rodando
  (`os.startfile()` se fechado) - nunca chama `mt5.initialize()` nele,
  porque a API Python trava com "-3 Out of memory" nesse terminal
  especifico (bug isolado em `diag_symbol_select_mt5stock.py`, ver nota
  1.3.0 do `historico.py`). O dado de la continua vindo do Service nativo
  `ExportadorMt5Stock.mq5` rodando dentro do proprio terminal - esse
  Service ainda precisa ser iniciado manualmente uma vez (Navegador >
  Servicos), o Python nao alcanca isso de fora.

## 4.10.0 - 2026-09-29
- `_aguardar_novo_m5` exigia candle M5 novo dos DOIS lados (corretora nacional e
  corretora internacional) pra liberar a proxima volta do lote em `_rodar_lote()` — em
  producao (29/09), isso travou o pipeline inteiro (inclusive o lado
  internacional, que continuava tendo candle novo normalmente) enquanto o
  mercado nacional (B3/corretora nacional) estava fechado, e o log mostrou reconexao
  repetida (`mt5.initialize` com login completo) a cada 30s por um bom
  tempo, terminando em `[corretora nacional] falha ao conectar: (-6, Authorization
  failed)` — suspeita forte de relogin excessivo sendo tratado como abuso
  pelo servidor da corretora (mesmo padrao ja visto com login do Telegram
  em outra frente do projeto). Pedido do usuario: "deveriamos montar uma
  logica que enquanto nao aparecesse candle novo usasse o ultimo cotado,
  quando aparecesse o novo usa ele". Mudou pra: libera assim que QUALQUER
  UM dos dois avanca (nao precisa mais dos DOIS); o lado que nao avancou
  carrega o "ultimo" de antes pra proxima comparacao — nenhum dado se
  perde, so nao bloqueia mais o pipeline enquanto um mercado esta fechado.
  Reconexao ganhou backoff independente por lado (novas constantes
  `PAUSA_CHECAGEM_M5_MAX` = 300s e `FALHAS_PRA_DOBRAR` = 3): apos
  tentativas seguidas sem avancar, o intervalo DAQUELE lado dobra (30s →
  60s → 120s → 240s → 300s, teto) sem afetar o ritmo do outro — o caso que
  mais se beneficia e fim de semana, com os dois mercados fechados ao
  mesmo tempo por muitas horas. Logica testada isolada (sem MT5/rede,
  mesma tecnica ja usada no projeto — ver `noticias_historico.py`) contra
  4 cenarios: lado internacional libera com o nacional fechado (e
  vice-versa), backoff cresce e respeita o teto, recuperacao normal quando
  os dois reabrem — os 4 passaram antes de aplicar no arquivo real.

## 4.11.0 - 2026-09-29
- Novo processo continuo em `_iniciar_last()`: `sentimento_em.py`
  (cotacao + variacao intradiaria de EWZ/EEM, mesmo padrao/motivo de
  `magnificas.py` — le parquet de MTF ja alimentado, sem conexao MT5
  propria). Pedido do usuario: "colocar o EWZ no Risk indice" (ampliado
  pra EEM). Depende de `historico.py` 1.4.0 (grupo
  `etfs_sentimento_em`) e `ExportadorMt5Stock.mq5` 1.01 (Service MQL5
  recompilado com EWZ/EEM em `RAIZES[]`).
- Janela de console propria (mesmo grupo de `dp.py`/`amplitude.py`/
  `magnificas.py`), entra tambem na mensagem de timeout de
  `_parar_last()`.

## 4.12.0 - 2026-10-01
- Novo passo no pipeline em lote (`_rodar_lote()`): `verificar_frescor_cotacoes.py`
  entra logo depois de `historico.py` e antes de `alinhar_d1.py`. Pedido do
  usuario ("isso tinha que ser automatico") apos episodio do Dolar Teorico
  travado em PTAX estimado por atraso de dado real do USDBRL — em vez de so
  corrigir aquele caso pontual, o pipeline passa a se auto-fiscalizar a cada
  volta.
- O que o script novo faz (ver `verificar_frescor_cotacoes.md` pro design
  completo): le `controle_atualizacao_mtf.parquet` (sem tocar em m1.parquet),
  aprende a janela de pregao tipica de cada ativo das grades de cotacao
  (Risk Indice/Risk Dolar) pelos ultimos 5 dias de historico real, e compara
  o atraso de cada ativo-dentro-da-janela contra a MEDIANA dos pares —
  limite adaptativo (`max(30min, 4x mediana)`), nao um numero fixo por
  ativo/classe (evita repetir o erro ja cometido antes neste projeto de
  supor regra fixa de horario por classe de ativo, ex. "Dolar e 24h"). Ativo
  discrepante vira reforco automatico via `historico.py --reforcar M1:2
  --so <raizes>`, com cooldown de 45min por raiz pra nao martelar o MT5.
- Blindado pra nunca derrubar o loop do `main.py`: qualquer erro (config
  ausente, parquet ilegivel, timeout do reforco) e capturado e logado,
  nunca propagado.
- Valido contra dado real de producao: corretamente sinalizou USDRUB como
  unico suspeito (~90min de atraso, janela aprendida 07:01-10:55) entre 28
  ativos candidatos, sem falso positivo em ativos de mercado fechado
  (EEM/EWZ) nem nos de cadencia normal.
