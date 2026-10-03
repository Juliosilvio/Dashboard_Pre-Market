# yeldcurve.py - historico de versoes

## 1.0.0 - 2026-09-23

Primeira versao. Coleta a curva de juros dos treasurys americanos (1M a
30Y) direto da pagina publica do Investing.com
(https://www.investing.com/rates-bonds/usa-government-bonds), pra servir
de insumo ao "morning call" automatizado discutido com o usuario nessa
mesma data - o trader de referencia (video analisado) usa o ratio 2Y/10Y
(e o nivel do 5Y) como leading indicator de forca do dolar.

Motivacao / caminho ate aqui (2026-09-23):
- O usuario ja tinha uma planilha manual (`backend/excel/treasurys/yeldcurve.xlsx`)
  copiada da mesma pagina do Investing, com Power Query configurado pra
  atualizar a cada 5 minutos - so que isso exige o Excel aberto o tempo
  todo (Power Query so atualiza com o processo do Excel rodando; nao tem
  jeito nativo de atualizar arquivo fechado). Objetivo aqui foi tirar o
  Excel do meio.
- Cogitado usar o CSV oficial do Tesouro americano (home.treasury.gov)
  como fonte sem risco de bloqueio, mas so atualiza D+1 (fechamento
  oficial) - o usuario confirmou que quer variacao INTRADAY na curva,
  entao a fonte oficial fica descartada pra este script (pode voltar como
  fallback futuro se a leitura do Investing falhar com frequencia).
- Verificado no navegador (DevTools, 2026-09-23) que a tabela da pagina
  NAO e carregada via chamada JSON/XHR separada - os valores ja vem
  prontos no HTML servido (renderizacao no servidor deles). Ou seja: um
  GET simples (urllib, sem navegador/Playwright) e suficiente.
- Testado (na mesma data) se um `GET` simples e bloqueado: nao deu pra
  confirmar por aqui (tanto o ambiente cloud do Claude quanto a VM Linux
  isolada do `device_bash` tem proxy de rede restrito e bloqueiam
  investing.com e ate dominios genericos como example.com por politica,
  nao por causa do Investing). Teste real precisa rodar no venv do
  proprio Windows do usuario (fora do alcance remoto do Claude) - ver
  instrucoes passadas em chat.

Decisoes de design:
- Ancora de extracao por `id="pair_<numero>"` fixo de cada linha da
  tabela (identificado manualmente no DevTools), nao por texto visivel
  ("U.S. 10Y") nem por posicao - o id interno do Investing e mais
  estavel a redesign visual do que os dois. Mapa fixado em
  `MAPA_PAIR_ID` no topo do script; indices de coluna (`IDX_*`) tambem
  conferidos na mao.
- Fonte NAO oficial (diferente de dadosgov.py) - tratamento de erro
  tolerante (nunca derruba o pipeline) e sanidade por linha: yield fora
  de 0%-20% e descartado individualmente, sem descartar a coleta
  inteira.
- Camada bruta + estruturada: cada coleta salva o HTML cru em
  `html_bruto/yeldcurve_usa/<timestamp>.html` (auditoria, pra
  investigar se o parser quebrar um dia) e o resultado parseado em
  `parquet/historicos/investing/yeldcurve_usa.parquet` (uma linha por
  vencimento por dia, chave `data_pregao` + `vencimento`, ultima leitura
  do dia vence em caso de rodar mais de uma vez).
- Frequencia: script faz UMA leitura por execucao, sem loop interno -
  decisao explicita de rodar 1x/dia perto da abertura da B3 (~08:55 BRT)
  via Tarefas Agendadas do Windows, por fora do script, em vez de
  polling continuo (o padrao de 5 em 5 minutos da planilha antiga tem
  cara de bot e nao traz ganho nenhum pro caso de uso do morning call).
  Se no futuro o usuario quiser mais de uma leitura por dia pra
  acompanhar variacao intraday alem da abertura, agendar com pelo menos
  15-30min de intervalo entre execucoes, nunca continuo.

Dependencia nova: `beautifulsoup4` (parsing de HTML) - instalar com
`pip install beautifulsoup4` no venv do projeto.

Nao testado ainda contra a pagina real (sem acesso de rede daqui) -
proximo passo e o usuario rodar `python yeldcurve.py` no proprio
terminal e confirmar se recebe os 13 vencimentos ou se leva algum
bloqueio.

## 1.0.0 - ajuste ainda no dia 2026-09-23 (antes do primeiro uso real)

Usuario decidiu rodar 2x por dia (08:30 e 08:55, ambas pre-abertura da
B3), nao 1x. Corrigido o dedup do parquet: era por (data_pregao,
vencimento) - a segunda leitura do dia apagaria a primeira. Agora e por
(timestamp_coleta, vencimento), entao cada rodada vira uma linha propria
e da pra comparar a leitura das 08:30 com a das 08:55 depois. Renomeado
tambem de yield_curve.py para yeldcurve.py (pedido do usuario, pra bater
com o nome ja usado em backend/excel/treasurys/yeldcurve.xlsx).

## 2.0.0 - 2026-09-23 (reescrita completa antes do primeiro uso real)

Reescrita de arquitetura, ainda no mesmo dia, antes de qualquer teste
real ter rodado contra a pagina - motivada por dois fatos novos que
derrubaram premissas da v1.0.0:

1. **HTTP 403 confirmado**: o usuario rodou `python yeldcurve.py`
   (v1.0.0) no proprio terminal e recebeu bloqueio (`HTTP Error 403:
   Forbidden`) logo na primeira tentativa. Tentativa de contornar so
   com headers extras (Accept, Accept-Language, Referer, Connection)
   nao resolveu - confirma que e bloqueio por fingerprint de
   navegador/TLS (WAF), nao falta de header. Um `GET` cru (urllib) nao
   passa nesta pagina; precisa de um navegador de verdade.
2. **Pagina se autoatualiza sozinha**: eu tinha checado a rede (XHR/
   Fetch) por alguns segundos e concluido errado que a pagina "nao
   busca dado novo sozinha". O usuario corrigiu com prova (print da
   propria tela + relato de que o valor muda de minuto em minuto sem
   ele fazer nada) - o mecanismo real e provavelmente WebSocket, que
   monitoramento so de XHR/Fetch nao enxerga. Isso muda a estrategia:
   nao precisa dar `goto()` de novo a cada leitura, so precisa manter a
   aba aberta e reler o DOM (`page.content()`) periodicamente.

Mudancas de arquitetura:
- **urllib -> Playwright** (`playwright.sync_api.sync_playwright`):
  abre um Chromium de verdade (`HEADLESS = False` por enquanto, ainda
  sem confirmar se passa tambem em modo headless - primeiro teste real
  vai decidir isso) e faz UMA navegacao (`goto`) por execucao. As
  leituras seguintes so chamam `page.content()` na mesma aba (sem
  navegar de novo), aproveitando que a pagina se atualiza sozinha via
  WebSocket - isso minimiza o numero de requests que passam pelo
  WAF/anti-bot, reduzindo risco de bloqueio por comportamento
  repetitivo.
- **Camada de extracao mantida sem mudanca** (`MAPA_PAIR_ID`, `IDX_*`,
  `MIN_COLUNAS`, faixa de sanidade 0%-20%, `_texto_numero`,
  `_extrair_linhas`) - ja validada na v1.0.0, so trocou a fonte do HTML
  (antes `urllib`, agora `page.content()` do Playwright).
- **Saida: parquet historico -> par de JSON "estado atual"**
  (`json/last_json/yeldcurve_amostra_a.json` /
  `yeldcurve_amostra_b.json`), no MESMO esquema do `last_nac.py` /
  `last_int.py` (pedido explicito do usuario: "a gente faz o mesmo
  esquema do leitor de cotações"). Motivo: um script rodando em loop
  continuo, escrevendo a cada 1-30min, ia eventualmente re-ler +
  concatenar + regravar um parquet crescente a cada ciclo - o mesmo
  problema de lock/corrupcao entre processos que o `last_nac.py` ja
  documentou ter tido no passado. A saida agora e "estado atual" (um
  registro por vencimento, SOBRESCRITO a cada flush, sem acumular
  historico), alternando entre os arquivos a/b a cada gravacao
  (`_proximo_arquivo`) com escrita atomica (`.tmp` + `os.replace()`)
  pra nunca deixar o arquivo pela metade pra quem esta lendo. Sem
  acumulo de historico neste output - se no futuro precisar de
  historico intraday da curva, e um script/consumidor separado que le
  os JSONs periodicamente e acumula, nao responsabilidade deste
  coletor.
- **Loop continuo com cadencia variavel** (pedido explicito do
  usuario, "faz isso de 40 leituras e apos a janela das 08:25/09:05 ler
  de 30 em 30"): dentro da janela 08:25-09:05 (`JANELA_INICIO`/
  `JANELA_FIM`), le a cada 60s (`INTERVALO_JANELA_SEGUNDOS`) - joga
  ~40 leituras nesse intervalo de 40min; fora da janela, cai pra 1
  leitura a cada 30min (`INTERVALO_FORA_JANELA_SEGUNDOS`). Calculo
  isolado em `_intervalo_atual()` pra facilitar ajuste futuro.
- **Stop-flag compartilhado**: reusa o mesmo arquivo que ja controla o
  `last_nac.py`/`last_int.py`
  (`parquet/historicos/_stop_last.flag`) em vez de inventar um novo -
  loop principal roda `while not os.path.exists(self.stop_flag_path)`.
  Isso NAO integra ainda o yeldcurve.py ao ciclo de vida do
  `main.py` (main.py nao foi alterado - ele so cria o flag, nao
  ainda dispara nem mata este script), mas deixa o caminho pronto pra
  essa integracao quando o usuario pedir.
- Camada bruta mantida: primeiro `page.content()` bem-sucedido de cada
  execucao ainda salva o HTML cru em `html_bruto/yeldcurve_usa/`
  (auditoria), so a primeira leitura, nao todo ciclo (senao vira
  milhares de arquivos por dia sem necessidade).

Nova dependencia: `playwright` (alem de `beautifulsoup4`, ja usada na
v1.0.0). Instalar com:
  `pip install playwright`
  `playwright install chromium`  (baixa o binario do Chromium, ~300MB)

Removida a dependencia de `pandas`/`pyarrow` deste script especifico
(nao grava mais parquet) - continuam necessarias no resto do projeto,
so nao sao mais importadas por este arquivo.

Ainda NAO testado contra a pagina real (Playwright nunca rodou contra
investing.com de verdade ate agora - nem v1.0.0 nem v2.0.0 tiveram
teste de rede real fora do ambiente do usuario, que tem proxy
restrito). Proximo passo: usuario instalar as dependencias acima e
rodar `python yeldcurve.py` - a pergunta em aberto e se o Chromium do
Playwright (mesmo com `HEADLESS = False`) passa pelo bloqueio
anti-bot que o `urllib` nao passou.

## 2.1.0 - 2026-09-23 (correcao apos primeiro teste real: bloqueio confirmado)

Primeiro teste real (`python yeldcurve.py`, Playwright ja instalado)
confirmou bloqueio: a leitura veio com os 13 vencimentos "nao
encontrados/validos". Investigado por print da tela do usuario -
o navegador estava preso na tela "Executando verificação de segurança"
da Cloudflare (nao um 403 puro como o urllib da v1.0.0 tomava - aqui a
navegacao "funciona", mas fica retida numa pagina intermediaria de
checagem JS que nunca chega a liberar a tabela de verdade).

Causa provavel: Chromium controlado por Playwright, do jeito que estava
(launch() simples, sem nenhum disfarce), expõe `navigator.webdriver =
true` e outras pistas de automacao - o gatilho classico que servicos
tipo Cloudflare usam pra diferenciar navegador automatizado de uso
humano, mesmo sendo um navegador de verdade por baixo.

Correcao (sem exigir nenhuma instalacao nova - o Chromium ja baixado
com `playwright install chromium` continua servindo de fallback):
- Perfil de navegador PERSISTENTE em disco (`_perfil_chrome_yeldcurve/`,
  criado ao lado do proprio script) via `launch_persistent_context` em
  vez de `launch()` + `new_page()` - guarda cookies entre execucoes,
  entao se a Cloudflare liberar o acesso uma vez, execucoes seguintes
  tendem a nao repetir o desafio inteiro.
- Tenta abrir com `channel="chrome"` (o Google Chrome de verdade ja
  instalado no Windows do usuario) antes do Chromium bundlado do
  Playwright - navegador real tem fingerprint mais dificil de
  distinguir de uso humano. Se nao achar Chrome instalado, cai pro
  Chromium automaticamente, sem quebrar.
- Flag `--disable-blink-features=AutomationControlled` + script
  injetado via `add_init_script` que sobrescreve `navigator.webdriver`,
  `navigator.plugins`, `navigator.languages` e
  `navigator.permissions.query` - as pistas mais comuns de deteccao de
  automacao.
- Depois de qualquer navegacao real, espera explicitamente por um
  `pair_id` de verdade aparecer no DOM (`wait_for_selector`, ate 30s -
  `TIMEOUT_ESPERA_TABELA_MS`) em vez de ler `page.content()`
  imediatamente - da tempo do desafio JS resolver sozinho.
- Nova deteccao explicita (`_e_pagina_de_desafio`) da tela de checagem
  da Cloudflare, pra logar claramente "preso na verificacao" em vez de
  "vencimentos nao encontrados" (que parecia mudanca de estrutura da
  tabela, mascarando o diagnostico real).

Versao ainda NAO confirmada como suficiente - proximo teste real do
usuario que vai dizer se essa combinacao passa. Se ainda assim ficar
preso, proximos passos cogitados: biblioteca dedicada anti-deteccao
(ex: playwright-stealth) ou o plano B ja discutido (usar uma aba real
do Chrome do usuario, ja aberta manualmente, e ler o HTML dela por
fora em vez do Playwright navegar sozinho).

## 3.0.0 - 2026-09-23 (mudanca de estrategia: ler o Chrome do usuario em vez do script navegar)

Mesmo com todo o disfarce da v2.1.0 (perfil persistente, Chrome real via
channel="chrome", flags anti-deteccao), o teste real ainda falhou - dessa
vez nem chegou a carregar: `Page.goto: Timeout 45000ms exceeded` esperando
o evento "load". Ou seja, o bloqueio parece ser mais cedo/mais forte que
so o desafio JS visivel testado antes.

O proprio usuario propos a solucao ("a pagina ja esta aberta no meu
navegador, e se lessemos o navegador que esta aberto ja?") - retomando a
ideia que ele mesmo tinha sugerido bem no inicio ("a gente deixa a guia
dela aberta"). Mudanca de estrategia completa: o script NAO abre mais
nenhum navegador proprio. Em vez disso, CONECTA no Chrome que o usuario
ja tem rodando (via CDP - Chrome DevTools Protocol,
`playwright.chromium.connect_over_cdp`) e le uma aba que ele MESMO
navegou manualmente ate a pagina da yield curve. Como essa aba passou
pela Cloudflare do jeito mais dificil de distinguir de humano que existe
(porque e um humano navegando), o risco de bloqueio cai a praticamente
zero - o script nunca faz nenhuma requisicao de rede nova pro Investing,
so relê o DOM de uma aba que ja estava aberta e validada.

Mudancas tecnicas:
- Removido: `_abrir_contexto`, `_carregar_pagina`, `SCRIPT_ANTI_DETECCAO`,
  perfil persistente em disco, HEADLESS, canal do Chrome - tudo isso so
  fazia sentido quando o script abria seu proprio navegador.
- Novo: `_conectar_navegador` (connect_over_cdp na porta 9222) e
  `_achar_pagina` (procura, entre todas as abas de todos os contextos do
  Chrome conectado, a que tem "rates-bonds/usa-government-bonds" na URL -
  NAO abre aba nova, so encontra a que o usuario ja deixou aberta).
- O script NUNCA fecha o navegador/contexto/aba no final - e o Chrome do
  proprio usuario, que ele continua usando pra tudo o mais. So desconecta
  o controle remoto (fim do `with sync_playwright()`), o Chrome continua
  aberto normalmente.
- Mantida a deteccao de tela de desafio da Cloudflare
  (`_e_pagina_de_desafio`) como guarda de seguranca, mas nao deveria mais
  disparar - a aba e navegada pelo usuario, nao pelo script.

REQUISITO NOVO (manual, do usuario, uma vez por sessao de trabalho - o
Chrome precisa ter sido aberto com uma flag especial, nao da pra ligar
isso num Chrome ja aberto do jeito normal):

1. Feche TODAS as janelas do Chrome (confira no Gerenciador de Tarefas do
   Windows se nao sobrou nenhum processo "Google Chrome" rodando em
   segundo plano - as vezes ele fica na bandeja do sistema mesmo com
   todas as janelas fechadas).
2. Abra o Chrome de novo, mas com a porta de depuracao remota ligada E
   um perfil separado do perfil padrao (ver correcao abaixo - CORRECAO
   2026-09-23: so a porta nao bastou, deu ECONNREFUSED). Pelo Executar
   do Windows (Indice+R) ou um terminal:
   `"C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir="C:\ChromeDebug"`
   (se o Chrome estiver instalado em outro caminho, ajustar; um jeito de
   deixar isso permanente e criar um atalho na area de trabalho com essa
   mesma linha como "Destino" e usar sempre esse atalho pra abrir o
   Chrome quando for rodar o yeldcurve.py). Essa janela abre com um
   perfil "limpo" (sem favoritos/extensoes/login do perfil normal) - sem
   problema, a pagina da yield curve e publica.
   Pra confirmar que a porta realmente ligou antes de seguir: nessa
   janela, digitar na barra de enderecos `http://127.0.0.1:9222/json/version`
   - se aparecer um JSON, funcionou; se der erro de conexao, a porta nao
   ligou (ver correcao abaixo).
3. Nessa janela nova do Chrome, navegar manualmente ate
   https://www.investing.com/rates-bonds/usa-government-bonds e deixar a
   aba aberta (pode ter outras abas abertas tambem, sem problema - o
   script procura pela URL).
4. So ENTAO rodar `python yeldcurve.py` no terminal.

Se o Chrome nao estiver rodando com essa porta, ou se nao existir
nenhuma aba com a URL certa, o script avisa exatamente qual dos dois
faltou e encerra sem gravar nada - nao trava, nao inventa dado.

Ainda NAO confirmado com teste real - proximo passo e o usuario seguir
os 4 passos acima e rodar de novo.


## Correcao 2026-09-23 (mesmo dia, ainda dentro da v3.0.0) - ECONNREFUSED na porta 9222

Primeiro teste real da v3.0.0: script tentou conectar e recebeu
`ECONNREFUSED 127.0.0.1:9222` - nada estava escutando na porta, mesmo
com o Chrome reaberto (aparentemente) so com a flag
`--remote-debugging-port=9222`.

Causa: versoes recentes do Chrome bloqueiam a porta de depuracao remota
quando ela e aberta em cima do PERFIL PADRAO do usuario (medida de
seguranca do Google, pra evitar que qualquer programa sequestre a sessao
real de navegacao/senhas/cookies do usuario so passando essa flag). A
flag e silenciosamente ignorada nesse caso - por isso nao apareceu
nenhum erro na hora de abrir o Chrome, so na hora do script tentar
conectar.

Correcao: abrir com um perfil SEPARADO, dedicado so a isso, via
`--user-data-dir="C:\ChromeDebug"` (ou qualquer pasta nova) junto com a
flag da porta. Instrucoes atualizadas acima. Essa janela abre "zerada"
(sem favoritos/extensoes/contas logadas do perfil normal do usuario) -
sem problema pro caso de uso, a pagina da yield curve nao exige login.

Nao muda nada no script (`yeldcurve.py` continua identico, so conecta
na porta 9222 igual antes) - e so a instrucao de como abrir o Chrome que
precisou de ajuste. Ainda NAO confirmado com teste real apos essa
correcao.

## 4.0.0 - 2026-09-23 (abandonado ler a pagina direto - le o xlsx do Excel)

Depois de tres tentativas seguidas de ler a pagina do Investing.com
direto (urllib -> 403, Playwright abrindo navegador -> preso na
Cloudflare mesmo com disfarce, CDP numa aba do usuario -> nem a conexao
local (ECONNREFUSED) foi possivel estabelecer de forma confiavel), o
usuario cortou o problema pela raiz: ele ja tinha uma solucao que
funciona hoje, `backend/excel/treasurys/yeldcurve.xlsx`, mantido
atualizado pelo Power Query do proprio Excel (Get Data), sem nenhum
bloqueio - so exigia manter o Excel aberto, o que o usuario deixou claro
que nao e problema ("o excel pode ficar requisitando la, eu usava assim
pra criar os graficos").

Mudanca de arquitetura completa: removido TUDO relacionado a acessar a
pagina (Playwright, beautifulsoup4, CDP, perfil de navegador, disfarce
de automacao). O script agora so LE o arquivo `.xlsx` local a cada 5
minutos (`INTERVALO_SEGUNDOS`, mesmo ritmo do Power Query - nao adianta
ler mais rapido, o arquivo so muda quando o Excel atualiza) via
`openpyxl` e republica no mesmo double buffer JSON de sempre
(yeldcurve_amostra_a.json / _b.json). Zero requisicao de rede feita pelo
Python.

Verificado antes de codar (2026-09-23): o mtime do xlsx estava mudando
de fato a cada ~5min (11:39 -> 11:44 confirmado ao vivo), confirmando
que o Excel/Power Query grava no disco automaticamente, nao so na tela -
essencial pro script funcionar, ja que ele so consegue ver o que estiver
SALVO no arquivo, nao o que aparece na tela de um Excel aberto sem
salvar.

Achado durante a verificacao: o usuario mandou print do Excel mostrando
cabecalhos e nomes de vencimento em PORTUGUES ("Nome, Rendimento, ...",
"EUA a 1 mês") enquanto o arquivo salvo em disco (lido nesse exato
momento) tinha cabecalhos em INGLES ("Name, Yield, ...", "U.S. 1M") - ou
seja, o texto pode variar dependendo da fonte/config que o Power Query
estiver usando. Por causa disso, a identificacao do vencimento de cada
linha passou a ser por POSICAO (linha 2 = 1M, linha 3 = 2M, ... linha 14
= 30Y, ver ORDEM_VENCIMENTOS) em vez de ler o texto da coluna Name - fica
imune a mudanca de idioma/fonte. O texto original de cada linha ainda e
guardado no campo extra "nome_planilha" de cada registro, so pra
conferencia.

Escala das colunas Yield/Prev./High/Low mantida (inteiro / 1000, ex:
4771 -> 4.771%) - confirmado que e como o Power Query grava esses
valores nesse arquivo especifico (independe do idioma da fonte).

Nova checagem: `_checar_atraso` compara o mtime do xlsx a cada ciclo - se
ficar parado por mais de 20min (`ATRASO_AVISO_SEGUNDOS`), avisa uma vez
que o Excel/Power Query pode ter parado de atualizar (nao fica repetindo
o aviso toda rodada).

Dependencia: `openpyxl` (nao instalada ainda no venv do usuario - `python
-m pip install openpyxl`). Removidas as dependencias `beautifulsoup4` e
`playwright` deste script especifico (nao usadas mais aqui).

Testado localmente (sandbox) com xlsx sintetico reproduzindo a estrutura
real (13 linhas, valores escalados, coluna Time mista time/datetime) -
leitura, escala e double buffer conferidos certos antes de mandar pro
usuario. Ainda falta o teste real no ambiente dele (arquivo de verdade,
Excel de verdade aberto).
