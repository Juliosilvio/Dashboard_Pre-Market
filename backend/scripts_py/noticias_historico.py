"""
Nome do script : noticias_historico.py
Descricao      : Coletor de HISTORICO real do canal de noticias do Telegram
                  (fonte de noticias, mesmo canal do noticias.py), via API oficial
                  do Telegram (biblioteca Telethon, login de USUARIO, nao
                  bot) — pedido do usuario (2026-09-27): "o script faz uma
                  varredura buscando todas as mensagens do canal a partir
                  do dia 01/01/2026 e salva em arquivo .csv".

                  Diferenca em relacao a noticias.py: aquele le a pagina de
                  PREVIEW PUBLICA (<url da fonte> sem
                  autenticacao), que so mostra os ~20 posts mais recentes —
                  nao tem historico. Este aqui loga como USUARIO de verdade
                  (api_id/api_hash gerados em https://my.telegram.org) e usa
                  client.iter_messages(), que devolve o historico completo
                  do canal, sem limite de quantidade.

                  Credenciais: lidas de json/config.json, chave "telegram"
                  ("api_id", "api_hash", "canal", "desde") — NUNCA
                  hardcoded aqui nem passadas por linha de comando, mesma
                  convencao das credenciais de corretora do projeto. A
                  chave ja foi criada no config.json com valores null;
                  preencher api_id/api_hash com o que aparecer em
                  my.telegram.org depois de criar um app la.

                  Sessao Telegram: primeira execucao PRECISA ser interativa
                  (o Telethon pede o numero de telefone, o codigo que chega
                  no proprio Telegram do usuario, e a senha de 2FA se
                  tiver) — so pode rodar no Windows do usuario, nunca daqui
                  da ponte Claude (mesma restricao de rede ja documentada
                  no noticias.py, e MTProto/Telethon usa conexao TCP direta
                  aos servidores do Telegram, nao HTTP, entao nem passaria
                  pelo proxy mesmo se a rede fosse liberada). Depois do
                  primeiro login, a sessao fica salva em
                  scripts_py/_sessao_telegram/fonte de noticias.session e as
                  proximas execucoes (inclusive futura chamada pelo
                  main.py) rodam sem pedir nada de novo.

                  Escreve direto na arvore de pastas do
                  organizar_noticias.py (analise_noticias/AAAA/<mes>/
                  Nasemana/diaDD-MM-AAAA_<diadasemana>.csv), convertendo o
                  horario (Telethon devolve UTC) pra America/Sao_Paulo antes
                  de decidir em qual pasta/dia a mensagem cai.

                  Incremental (mesmo espirito de historico.py/noticias.py):
                  grava em json/controle_historico_noticias.json o maior id
                  de mensagem ja processado; a proxima execucao so busca
                  mensagens com id MAIOR que esse (client.iter_messages(...,
                  min_id=ultimo_id)), nunca reprocessa nem duplica. Na
                  primeira execucao (sem controle ainda), usa
                  offset_date=<"desde" do config.json> + reverse=True pra
                  comecar do passado pro presente.

                  Mensagens sem texto (so imagem/video/enquete) sao
                  ignoradas, mesma regra do noticias.py. O canal costuma
                  prefixar a mensagem como "Fonte - <url da fonte>
                  - manchete..." — aqui, diferente do noticias.py (que so
                  queria a manchete pro card), a fonte e a manchete vao pra
                  colunas SEPARADAS do CSV (o historico se beneficia de
                  manter a fonte).

                  AVISO DE VALIDACAO (2026-09-27): testado nesta versao
                  SEM acesso real ao Telegram (sem api_id/api_hash
                  liberados ainda, e a rede da ponte Claude nao alcancaria
                  o MTProto de qualquer forma) — testado o que dava pra
                  testar sem rede real: sintaxe, a funcao pura
                  _processar_mensagens() (logica de separar fonte/manchete,
                  fuso horario, gravacao incremental e atualizacao do
                  controle) contra mensagens FALSAS simulando o formato
                  real do Telethon, e import da biblioteca telethon
                  (instalada e funcional na ponte Linux, versao 1.45.0).
                  A chamada de rede de verdade (TelegramClient.iter_messages)
                  em si NAO foi exercitada contra o Telegram real. Rodar
                  com cautela na primeira vez: conferir se a data mais
                  antiga coletada bate com "desde" (2026-01-01) antes de
                  confiar no restante do backfill.
Autor          : Julio Cesar Silvio Campanhola
Criado em      : 2026-09-27
Ultima edicao  : 2026-09-27
Versao         : 1.0.0
Projeto        : dashboard
Historico      : scripts_py/versoes/noticias_historico.md
"""

import argparse
import json
import os
import re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import organizar_noticias

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJETO_BASE_DIR = os.path.dirname(BASE_DIR)
CONFIG_PATH = os.path.join(PROJETO_BASE_DIR, "json", "config.json")
CONTROLE_PATH = os.path.join(PROJETO_BASE_DIR, "json", "controle_historico_noticias.json")
SESSAO_DIR = os.path.join(BASE_DIR, "_sessao_telegram")

FUSO_BR = ZoneInfo("America/Sao_Paulo")

# mesma ideia do noticias.py: mensagem costuma vir "Fonte - <link do canal> - manchete".
# aqui a fonte tambem interessa (coluna propria do CSV), entao captura os dois lados.
_RE_FONTE_MANCHETE = re.compile(
    r"^(?P<fonte>.*?)\s*-\s*https://t\.me/\S+\s*-\s*(?P<manchete>.*)$",
    re.DOTALL,
)

FONTE_PADRAO = "fonte de noticias (Telegram)"


def _separar_fonte_manchete(texto_bruto: str):
    """
    Recebe o texto cru da mensagem do Telegram e devolve (fonte, manchete).
    Se o padrao "Fonte - link - manchete" nao for reconhecido, usa
    FONTE_PADRAO e o texto inteiro (limpo) como manchete.
    """
    texto_bruto = texto_bruto.strip()
    m = _RE_FONTE_MANCHETE.match(texto_bruto)
    if m:
        fonte = m.group("fonte").strip(" - ") or FONTE_PADRAO
        manchete = re.sub(r"\s{2,}", " ", m.group("manchete")).strip(" - ")
        return fonte, manchete
    manchete = re.sub(r"\s{2,}", " ", texto_bruto).strip()
    return FONTE_PADRAO, manchete


def _ler_controle() -> int:
    if not os.path.exists(CONTROLE_PATH):
        return 0
    try:
        with open(CONTROLE_PATH, encoding="utf-8") as f:
            return int(json.load(f).get("ultimo_id", 0))
    except (json.JSONDecodeError, ValueError, OSError):
        return 0


def _salvar_controle(ultimo_id: int) -> None:
    os.makedirs(os.path.dirname(CONTROLE_PATH), exist_ok=True)
    tmp = CONTROLE_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"ultimo_id": ultimo_id}, f, indent=2)
    os.replace(tmp, CONTROLE_PATH)


def _processar_mensagens(mensagens, ultimo_id_inicial: int = 0):
    """
    Funcao PURA (sem rede): recebe um iteravel de objetos com atributos
    .id (int), .date (datetime tz-aware, UTC) e .text (str ou None) —
    exatamente o formato de telethon.tl.custom.Message, mas tambem aceita
    um objeto fake equivalente pra teste. Grava cada mensagem valida via
    organizar_noticias.adicionar_noticia() e devolve
    (maior_id_visto, total_gravadas, total_ignoradas).
    Separado do metodo assincrono de rede (ColetorHistoricoNoticias.coletar)
    justamente pra poder testar esta logica sem precisar de conexao real
    com o Telegram.
    """
    maior_id = ultimo_id_inicial
    total_gravadas = 0
    total_ignoradas = 0
    for msg in mensagens:
        maior_id = max(maior_id, msg.id)
        if not msg.text:
            total_ignoradas += 1
            continue
        fonte, manchete = _separar_fonte_manchete(msg.text)
        if not manchete:
            total_ignoradas += 1
            continue
        data_local = msg.date.astimezone(FUSO_BR)
        organizar_noticias.adicionar_noticia(
            data_local.date(),
            hora=data_local.strftime("%H:%M:%S"),
            ativo_relacionado="",
            fonte=fonte,
            manchete=manchete,
        )
        total_gravadas += 1
    return maior_id, total_gravadas, total_ignoradas


class ColetorHistoricoNoticias:
    """Varre o historico do canal do Telegram e organiza em
    analise_noticias/ via organizar_noticias.py. Ver docstring do modulo."""

    def __init__(self, config_path: str = CONFIG_PATH):
        with open(config_path, encoding="utf-8") as f:
            cfg = json.load(f)
        tg = cfg.get("telegram") or {}
        self.api_id = tg.get("api_id")
        self.api_hash = tg.get("api_hash")
        self.canal = tg.get("canal", "fonte de noticias")
        desde_str = tg.get("desde", "2026-01-01")
        self.desde = datetime.strptime(desde_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)

        if not self.api_id or not self.api_hash:
            raise RuntimeError(
                "config.json -> chave 'telegram' -> api_id/api_hash ainda "
                "nao preenchidos. Gere um app em https://my.telegram.org, "
                "e coloque os valores direto no config.json (nao precisa "
                "passar isso pro Claude em conversa)."
            )

        os.makedirs(SESSAO_DIR, exist_ok=True)
        self.sessao_path = os.path.join(SESSAO_DIR, self.canal)

    async def coletar_async(self):
        """Conecta no Telegram (pode pedir login interativo na primeira
        vez) e varre o historico do canal, gravando via
        organizar_noticias.py. Devolve (total_gravadas, total_ignoradas)."""
        from telethon import TelegramClient  # import tardio: so precisa existir na maquina que roda de verdade

        ultimo_id = _ler_controle()
        async with TelegramClient(self.sessao_path, self.api_id, self.api_hash) as client:
            entidade = await client.get_entity(self.canal)
            kwargs = {"reverse": True}
            if ultimo_id:
                kwargs["min_id"] = ultimo_id
            else:
                kwargs["offset_date"] = self.desde

            mensagens = []
            async for msg in client.iter_messages(entidade, **kwargs):
                mensagens.append(msg)

        maior_id, total_gravadas, total_ignoradas = _processar_mensagens(mensagens, ultimo_id)
        if maior_id != ultimo_id:
            _salvar_controle(maior_id)
        return total_gravadas, total_ignoradas


if __name__ == "__main__":
    import asyncio

    parser = argparse.ArgumentParser(description="Coleta historico do canal de noticias do Telegram.")
    parser.parse_args()

    coletor = ColetorHistoricoNoticias()
    gravadas, ignoradas = asyncio.run(coletor.coletar_async())
    print(f"Concluido: {gravadas} noticia(s) gravada(s), {ignoradas} mensagem(ns) sem texto ignorada(s).")
