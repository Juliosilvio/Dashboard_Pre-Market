"""
Nome do script : noticias.py
Descricao      : Feed de manchetes em tempo real do canal publico do
                  Telegram fonte de noticias (agrega a fonte agregador de noticias —
                  dados economicos/mercado, cambio, bancos centrais,
                  geopolitica) — pedido do usuario (2026-09-23): "noticias
                  em tempo real". Lembrava de um coletor parecido feito
                  numa sessao anterior; nao foi encontrado documentado
                  neste projeto (arquitetura.md, changelogs, memoria) nem
                  no device do usuario — refeito do zero.

                  Le a pagina de PREVIEW PUBLICA do canal
                  (<url da fonte>) — NAO usa a API oficial do
                  Telegram (Bot API/MTProto), que exige credenciais criadas
                  em my.telegram.org (o usuario ja tinha travado la antes,
                  numa tentativa de bot pra notificacao de EA — ver
                  memoria). A preview web e publica, sem login/API key,
                  feita pelo proprio Telegram pra embutir/pre-visualizar
                  canais publicos em paginas externas — poll simples por
                  HTTP, sem autenticacao nenhuma, evita esse bloqueio.

                  HTML da preview (estrutura estavel, usada por varios
                  scrapers publicos): cada mensagem e um
                  <div class="tgme_widget_message" data-post="fonte de noticias/ID">;
                  o texto fica em <div class="tgme_widget_message_text">; o
                  horario, no atributo datetime (ISO, UTC) de <time> dentro
                  de <a class="tgme_widget_message_date">. A pagina mostra
                  so os ~20 posts mais recentes (nao e historico completo,
                  nao precisa ser — e feed de tempo real).

                  So GRAVA quando aparece post novo (id maior que o ultimo
                  visto), mantem uma janela das ultimas MAX_NOTICIAS
                  manchetes (mais recente primeiro) — mesmo padrao double
                  buffer (.tmp + os.replace, dois arquivos alternados) do
                  resto do projeto (last_nac.py, dp.py, yeldcurve.py).

                  Mensagens sem texto (so imagem/video/enquete) sao
                  ignoradas — nao ha o que mostrar como manchete.

                  Nao roda dentro do bridge do Claude (rede restrita por
                  allowlist ali) — roda nativo no Windows do usuario, via
                  main.py, com acesso de internet normal.

                  Traducao (2026-09-30, pedido do usuario: "precisamos de
                  tradutor nas atualizacoes das noticias"): a fonte
                  (agregador de noticias) publica em INGLES. Cada manchete NOVA
                  (so as novas -- nunca re-traduz o que ja esta na janela)
                  passa por deep_translator.GoogleTranslator (wrapper livre
                  do endpoint publico do Google Translate, sem API key --
                  mesma filosofia de "raspar endpoint publico sem
                  credencial" que este proprio script ja usa pra ler o
                  preview do Telegram). Guarda os DOIS textos no JSON --
                  "texto" (original, ingles) e "texto_pt" (traduzido) --
                  nunca descarta o original. Se a traducao falhar (rede,
                  endpoint fora do ar, rate limit) cai pra texto_pt=None
                  sem derrubar o coletor -- o frontend mostra o texto
                  original nesse caso (ver NoticiasPainel.jsx).

                  Validado na primeira rodada real (2026-09-30, Windows do
                  usuario): o Google barrou com "Server Error: You made too
                  many requests to the server [...] allowed to make 5
                  requests per second" -- a primeira carga (janela inteira,
                  ~20-25 manchetes) traduzia tudo num loop apertado, estourava
                  o limite de 5 req/s e TODAS ficavam com texto_pt=None
                  (mesmo as que vinham 1 por vez nos polls seguintes,
                  aparentemente o Google mantem o IP penalizado por um
                  tempo depois do estouro). Corrigido com
                  INTERVALO_MIN_TRADUCAO_S entre cada chamada de
                  _traduzir() dentro do loop de _atualizar() -- 0.3s da
                  bastante margem pro limite de 5/s mesmo traduzindo a
                  carga inicial inteira (25 manchetes * 0.3s = 7.5s, cabe
                  folgado dentro do poll de 15s). NAO usa
                  GoogleTranslator.translate_batch() -- conferido o codigo
                  fonte do deep_translator, translate_batch so faz um loop
                  translate() por dentro, mesma contagem de requisicoes,
                  nao ajuda em nada apesar do Google sugerir isso na
                  mensagem de erro.
Autor          : Julio Cesar Silvio Campanhola
Criado em      : 2026-09-23
Ultima edicao  : 2026-09-30
Versao         : 1.2.0
Projeto        : dashboard
Historico      : scripts_py/versoes/noticias.md
"""

import importlib
import json
import os
import re
import time

try:
    requests = importlib.import_module("requests")
except ImportError as exc:
    raise ImportError(
        "A dependencia requests nao esta instalada. "
        "Instale-a com: pip install requests"
    ) from exc

try:
    bs4 = importlib.import_module("bs4")
    BeautifulSoup = bs4.BeautifulSoup
except ImportError as exc:
    raise ImportError(
        "A dependencia beautifulsoup4 nao esta instalada. "
        "Instale-a com: pip install beautifulsoup4"
    ) from exc
try:
    GoogleTranslator = importlib.import_module("deep_translator").GoogleTranslator
except ImportError as exc:
    raise ImportError(
        "A dependencia deep-translator nao esta instalada. "
        "Instale-a com: pip install deep-translator"
    ) from exc

CANAL = "fonte de noticias"
URL_PREVIEW = f"<url da fonte>"

# o canal costuma prefixar cada manchete com "Fonte - <url da fonte>
# - manchete..." - pedido do usuario (2026-09-23): nem a fonte nem o link
# do canal (repetido em toda mensagem) interessam pro card, so a manchete.
# Como o link SEMPRE aparece entre a fonte e a manchete de verdade, corta
# no primeiro link e fica so com o que vem DEPOIS dele.
_RE_LINK_CANAL = re.compile(r"https://t\.me/\S+")


def _limpar_texto(texto_bruto):
    partes = _RE_LINK_CANAL.split(texto_bruto, maxsplit=1)
    texto = partes[-1] if len(partes) > 1 else texto_bruto
    texto = texto.strip(" -\u00a0")
    texto = re.sub(r"\s{2,}", " ", texto).strip()
    return texto

def _traduzir(texto):
    """Traduz uma manchete (ingles -> portugues) via deep_translator
    (endpoint publico/gratuito do Google Translate, sem API key). Devolve
    None em qualquer falha (rede, endpoint fora do ar, rate limit, texto
    vazio) -- NUNCA propaga excecao pro chamador: uma manchete que nao
    traduziu ainda tem o texto original pra mostrar (ver NoticiasPainel.jsx,
    "item.texto_pt ?? item.texto"), o coletor nao pode travar por causa de
    um servico de terceiro que nem e o core do script."""
    if not texto:
        return None
    try:
        traduzido = GoogleTranslator(source="auto", target="pt").translate(texto)
        return traduzido.strip() if traduzido else None
    except Exception as exc:
        print(f"[noticias] falha ao traduzir manchete, mantendo so o original: {exc}")
        return None


MAX_NOTICIAS = 40  # quantas manchetes ficam na janela gravada (mais recente primeiro)

# Google barra o endpoint gratuito de traducao em 5 requisicoes/segundo
# (confirmado 2026-09-30 -- ver docstring do modulo). 0.3s entre cada
# chamada de _traduzir() da margem confortavel (~3.3 req/s) mesmo
# traduzindo a janela inteira de uma vez na primeira rodada apos o
# script subir (ultimo_id ainda None -> todas as manchetes da pagina
# contam como "novas").
INTERVALO_MIN_TRADUCAO_S = 0.3

PAUSA_LOOP = 15.0  # segundos entre cada checagem — "tempo real" sem martelar o Telegram

# alguns servidores recusam/limitam requisicao sem User-Agent de navegador
# (bloqueiam client generico tipo "python-requests/x.y"); usa um comum.
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Indice64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}


def _extrair_noticias(html):
    """Faz o parse da pagina de preview e devolve lista de dicts
    {"id": int, "hora_iso": str|None, "texto": str, "link": str}, na ordem
    que aparecem na pagina (mais antiga primeiro — quem le inverte se
    quiser mais recente primeiro). "texto_pt" (traducao) NAO vem daqui —
    e acrescentado depois, so pras manchetes novas, em _atualizar()."""
    soup = BeautifulSoup(html, "html.parser")
    noticias = []

    for bloco in soup.select("div.tgme_widget_message"):
        data_post = bloco.get("data-post")  # ex: "fonte de noticias/785272"
        if not data_post or "/" not in data_post:
            continue
        try:
            post_id = int(data_post.rsplit("/", 1)[-1])
        except ValueError:
            continue

        texto_div = bloco.select_one("div.tgme_widget_message_text")
        if texto_div is None:
            continue  # so midia/enquete, sem texto - nao ha manchete pra mostrar
        texto = _limpar_texto(texto_div.get_text(separator=" ", strip=True))
        if not texto:
            continue

        time_el = bloco.select_one("a.tgme_widget_message_date time") or bloco.select_one("time")
        hora_iso = time_el.get("datetime") if time_el is not None else None

        noticias.append({
            "id": post_id,
            "hora_iso": hora_iso,
            "texto": texto,
            "link": f"<url da fonte>",
        })

    return noticias


class ColetorNoticias:
    """Poll continuo da preview publica do canal fonte de noticias, grava double
    buffer so quando aparece manchete nova (id maior que o ultimo visto)."""

    def __init__(self, base_dir=None):
        self.base_dir = base_dir or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        output_dir = os.path.join(self.base_dir, "json", "last_json")
        self.output_path_a = os.path.join(output_dir, "noticias_amostra_a.json")
        self.output_path_b = os.path.join(output_dir, "noticias_amostra_b.json")
        self.stop_flag_path = os.path.join(self.base_dir, "parquet", "historicos", "_stop_last.flag")
        os.makedirs(output_dir, exist_ok=True)

        self.janela = []  # lista de dicts, mais recente primeiro, ate MAX_NOTICIAS
        self.ultimo_id = None
        self._proximo_arquivo = "a"

    def _buscar(self):
        resposta = requests.get(URL_PREVIEW, headers=HEADERS, timeout=10)
        resposta.raise_for_status()
        return _extrair_noticias(resposta.text)

    def _atualizar(self):
        """Busca a pagina e mescla o que for novo na janela. Devolve True
        se algo mudou (janela precisa ser gravada de novo)."""
        noticias = self._buscar()  # mais antiga primeiro
        if not noticias:
            return False

        maior_id_pagina = noticias[-1]["id"]
        if self.ultimo_id is not None and maior_id_pagina <= self.ultimo_id:
            return False  # nada novo desde a ultima checagem

        novas = [n for n in noticias if self.ultimo_id is None or n["id"] > self.ultimo_id]
        if not novas:
            return False

        # traduz SO as novas (nunca re-traduz quem ja estava na janela) --
        # ver _traduzir(), nunca lanca excecao, so devolve None na falha.
        # Throttle de INTERVALO_MIN_TRADUCAO_S ENTRE cada chamada (nao antes
        # da primeira) -- Google limita a 5 req/s no endpoint gratuito e um
        # estouro (tipico na primeira carga, quando "novas" e a janela
        # inteira) parecia deixar o IP penalizado por um tempo depois,
        # travando ate as traducoes seguintes de 1 manchete so (ver
        # docstring do modulo, incidente 2026-09-30).
        for i, n in enumerate(novas):
            if i > 0:
                time.sleep(INTERVALO_MIN_TRADUCAO_S)
            n["texto_pt"] = _traduzir(n["texto"])

        self.ultimo_id = maior_id_pagina
        self.janela = list(reversed(novas)) + self.janela  # mais recente primeiro
        self.janela = self.janela[:MAX_NOTICIAS]
        return True

    def _flush(self):
        alvo = self.output_path_a if self._proximo_arquivo == "a" else self.output_path_b
        tmp_path = alvo + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(self.janela, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, alvo)
        self._proximo_arquivo = "b" if self._proximo_arquivo == "a" else "a"

        ultima = self.janela[0]["hora_iso"] if self.janela else "—"
        print(f"[noticias] {len(self.janela)} manchetes (mais recente: {ultima}) -> {os.path.basename(alvo)}")

    def executar(self):
        print(f"[noticias] noticias.py rodando (Ctrl+C pra parar) — poll de {PAUSA_LOOP:.0f}s em {URL_PREVIEW}")

        try:
            while not os.path.exists(self.stop_flag_path):
                try:
                    if self._atualizar():
                        self._flush()
                except requests.RequestException as exc:
                    print(f"[noticias] erro de rede buscando o canal, seguindo pro proximo ciclo: {exc}")
                except Exception as exc:
                    print(f"[noticias] erro inesperado, seguindo pro proximo ciclo: {exc}")
                time.sleep(PAUSA_LOOP)
            print("[noticias] sinal de parada recebido")
        except KeyboardInterrupt:
            print("[noticias] Ctrl+C recebido")


if __name__ == "__main__":
    ColetorNoticias().executar()
