# Changelog — noticias.py

## 1.0.0 (2026-09-23)

- Primeira versao. Pedido do usuario: "agora só falta mais uma coisinha,
  noticias em tempo real!!!". Perguntado que tipo de noticia e de onde
  viria o dado, o usuario descartou calendario economico (ja tem em outro
  lugar) e pediu manchetes em tempo real, lembrando de um coletor
  parecido feito numa sessao anterior a partir de um canal publico do
  Telegram — procurado em `arquitetura.md`, nos changelogs, na memoria e
  no device (`backend/scripts_py`, `frontend/src`, pasta raiz do projeto)
  e NAO encontrado documentado em lugar nenhum; refeito do zero. Canal
  confirmado pelo usuario: `fonte de noticias` ("fonte de noticias", agrega a
  fonte agregador de noticias — dados economicos/mercado, cambio, bancos
  centrais, geopolitica).
- Le a pagina de PREVIEW PUBLICA do canal (`<url da fonte>`)
  em vez da API oficial do Telegram (Bot API/MTProto) — essa exigiria
  credenciais criadas em my.telegram.org, onde o usuario ja tinha
  travado antes numa tentativa de bot pra notificacao de EA (ver
  memoria). A preview web e publica, sem login/API key, feita pelo
  proprio Telegram pra embutir/pre-visualizar canais publicos — poll por
  HTTP simples evita aquele bloqueio.
- Parse via BeautifulSoup: cada mensagem e um
  `div.tgme_widget_message[data-post="fonte de noticias/ID"]`; texto em
  `div.tgme_widget_message_text`; horario no atributo `datetime` (ISO,
  UTC) de `<time>` dentro de `a.tgme_widget_message_date`. Mensagens sem
  texto (so midia/enquete) sao ignoradas. So grava quando aparece post
  com id maior que o ultimo visto — mantem janela das ultimas
  `MAX_NOTICIAS` (40) manchetes, mais recente primeiro.
- Poll a cada 15s (`PAUSA_LOOP`) — "tempo real" sem martelar o Telegram
  (a preview publica so mostra os ~20 posts mais recentes mesmo, nao ha
  ganho em pollar muito mais rapido que isso).
- Mesmo padrao double buffer (`.tmp` + `os.replace`, dois arquivos
  alternados `noticias_amostra_a/b.json` em `json/last_json/`) do resto
  do projeto (last_nac.py, dp.py, yeldcurve.py).
- Integrado ao `main.py` (sobe junto, janela de console propria) e ao
  `api_server.py` (`GET /api/noticias`). Novo painel no frontend
  (`NoticiasPainel.jsx`), poll de 15s (mesma cadencia do backend).
- Ressalva registrada pro usuario: como o parser depende da estrutura
  HTML atual da preview publica do Telegram (fora do controle do
  projeto), uma mudanca de layout do lado do Telegram pode quebrar a
  extracao — o script nao derruba o `main.py` se isso acontecer (loop
  continua, so loga o erro e tenta de novo no proximo ciclo), mas o
  painel fica sem noticia nova ate alguem notar e ajustar os seletores.
- Nao testado end-to-end em tempo real nesta sessao: o bridge usado pra
  editar o projeto (Claude/Cowork) tem a rede restrita por allowlist e
  bloqueou o teste direto contra t.me durante o desenvolvimento — o
  script roda nativo no Windows do usuario (via `main.py`), com acesso
  de internet normal, fora dessa restricao. Pendente confirmar com o
  usuario que a primeira rodada real gravou manchetes corretamente.

## 1.1.0 (2026-09-30)

- Pedido do usuario: "precisamos de tradutor nas atualizações das
  notícias" — a fonte (agregador de noticias) publica em ingles, usuario e
  publico do painel sao de fala portuguesa.
- Cada manchete NOVA (nunca re-traduz quem ja estava na janela) passa por
  `deep_translator.GoogleTranslator` (wrapper livre do endpoint publico
  do Google Translate, sem API key — mesma filosofia de "raspar endpoint
  publico sem credencial" que este script ja usa pra ler o preview do
  Telegram). Guarda os DOIS textos no JSON: `texto` (original, ingles,
  nunca descartado) e `texto_pt` (traduzido).
- Falha de traducao (rede, endpoint fora do ar, rate limit) nunca derruba
  o coletor — `_traduzir()` devolve `None` e loga uma linha; o frontend
  (`NoticiasPainel.jsx`) mostra o texto original nesse caso, com um
  tooltip mostrando o original mesmo quando a traducao deu certo (pra
  quem quiser conferir).
- Nao testado com internet de verdade nesta sessao: nem o bridge do
  Claude nem o ambiente de desenvolvimento alcancam
  `translate.google.com` (bloqueado pelo proxy/allowlist) — validado que
  o fluxo inteiro roda sem excecao e cai pro fallback (`texto_pt=None`)
  corretamente quando a chamada de rede falha, mas a traducao de verdade
  só é confirmada na primeira rodada real do usuario, nativo no Windows.
- Novo requisito: `pip install deep-translator` no ambiente do usuario.

## 1.2.0 (2026-09-30)

- Corrigido rate limit do Google Translate confirmado na primeira rodada
  real do usuario, nativo no Windows: `Server Error: You made too many
  requests to the server [...] allowed to make 5 requests per second`.
  Causa: a primeira carga apos o script subir traduz a janela inteira
  (`ultimo_id` ainda `None` → tudo conta como "novo", ~20-25 manchetes)
  num loop apertado, sem pausa nenhuma entre as chamadas — estourava os
  5 req/s do Google na largada e deixava o IP penalizado por um tempo
  (mesmo os polls seguintes, traduzindo 1 manchete por vez, continuavam
  falhando).
- Adicionado `INTERVALO_MIN_TRADUCAO_S = 0.3` — pausa de 0.3s ENTRE cada
  chamada de `_traduzir()` dentro do loop de `_atualizar()` (não antes da
  primeira). Dá margem confortável (~3.3 req/s) mesmo traduzindo a janela
  inteira de uma vez (25 × 0.3s = 7.5s, cabe folgado dentro do poll de
  15s).
- Avaliado e descartado `GoogleTranslator.translate_batch()` (sugestão do
  próprio Google na mensagem de erro) — conferido o código-fonte do
  `deep_translator`: `translate_batch` só faz um loop `translate()` por
  dentro, mesma contagem de requisições, não reduz nada.
- Testado com um smoke test isolado (mock de `_traduzir`/`_buscar`,
  timing real): 5 manchetes novas → 4 pausas de 0.3s → ~1.2s total, todas
  traduzidas. Pedido do usuário, log real colado no chat: "precisamos que
  seja português".
