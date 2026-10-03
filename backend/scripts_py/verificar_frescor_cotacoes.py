"""
Nome do script : verificar_frescor_cotacoes.py
Descricao      : Watchdog de frescor pros ativos das duas grades de
                  cotacao (Risk Indice / Risk Dolar, QuotesTable.jsx) --
                  pedido do usuario (2026-09-30 a noite, retomado
                  2026-10-01): "sim resolva, mas deixe de forma automatica
                  para os ativos que compoe as duas grades de cotação" /
                  "isso tinha que ser automatico" (depois de achar o
                  USDBRL e, na noite anterior, Brent/Dolar/UsaVix com
                  historico M1 travado horas/dias sem ninguem notar ate
                  abrir o card errado na tela).

                  NAO e standalone no dia a dia: chamado automaticamente
                  pelo main.py (Orquestrador._rodar_lote()), logo depois
                  de historico.py, igual o padrao do proprio historico.py
                  (ver docstring dele). Pode rodar manualmente tambem
                  (python verificar_frescor_cotacoes.py) pra inspecionar
                  sem esperar o loop.

                  O QUE FAZ, por ativo das duas grades
                  (config.json -> grades_cotacoes.principal.feeds,
                  resolvido dinamicamente, NUNCA hardcoded -- se o
                  usuario mudar os feeds/grupos no config.json, este
                  script acompanha sozinho, mesmo espirito do
                  vigente.py):

                  1. Resolve a pasta ATUAL do ativo (vigente de verdade,
                     pra vencimento_americano -- nunca cai numa pasta de
                     contrato ja rolado, que fica parada no disco pra
                     sempre e isso e normal, nao e staleness).
                  2. Aprende a JANELA TIPICA (hora min/hora max com preco
                     real) olhando o historico de atualizacoes desse
                     ativo (controle_atualizacao_mtf.parquet, que ja e
                     append-only -- nunca sobrescreve, so acrescenta) nos
                     ultimos N dias uteis anteriores a hoje. NAO assume
                     horario fixo nenhum por ativo (aprendemos com o erro
                     "Dolar e 24h" nesta mesma conversa que isso quebra) --
                     os proprios dados dizem quando cada ativo costuma
                     ter preco de verdade.
                  3. So dentro dessa janela (+ folga), compara o atraso
                     (lag) do ativo com a MEDIANA do atraso de todo o
                     resto do universo que tambem esta dentro da propria
                     janela agora. Isso se auto-calibra na velocidade
                     REAL do loop do main.py no momento (se o main.py
                     inteiro reiniciou agora e tudo esta com 20min de
                     atraso, a mediana tambem sobe e ninguem e sinalizado
                     a toa) -- so sinaliza quem esta discrepante dos
                     PROPRIOS colegas, nunca contra um numero fixo
                     chutado.
                  4. Ativo discrepante (lag > max(TOLERANCIA_MIN_ABSOLUTA,
                     TOLERANCIA_MULTIPLICADOR x mediana do grupo)) vira
                     candidato a reforco.
                  5. Reforco: chama historico.py --reforcar M1:<dias> --so
                     <raizes candidatas> (uma unica chamada, todas juntas)
                     -- so se ainda nao tentou reforcar essa mesma raiz
                     nos ultimos COOLDOWN_MIN minutos (json/
                     frescor_cotacoes_estado.json guarda o ultimo
                     reforco por raiz) -- evita martelar o MT5/disco toda
                     volta do loop se o problema for estrutural (ex:
                     bug de resolucao de vigente, que reforcar nao
                     resolve -- nesse caso so loga e deixa pro usuario
                     investigar, nao fica tentando pra sempre).

                  Resiliente de proposito: qualquer erro em QUALQUER
                  etapa (config ausente, controle ausente, parquet
                  corrompido, falha no subprocesso) e capturado e
                  LOGADO, nunca propagado -- este script nunca pode
                  derrubar a volta do main.py por causa de um bug aqui
                  dentro. Rodar o CHECK (etapas 1-4) nao precisa do MT5
                  (so le json/parquet) -- so o REFORCO (etapa 5) precisa,
                  por isso so funciona de verdade quando chamado pelo
                  main.py na maquina com o MT5 aberto.
Autor          : Julio Cesar Silvio Campanhola
Criado em      : 2026-10-01
Ultima edicao  : 2026-10-01
Versao         : 1.0.0
Projeto        : dashboard
Historico      : scripts_py/versoes/verificar_frescor_cotacoes.md
"""

import datetime
import json
import os
import subprocess
import sys

import pandas as pd

# SCRIPTS_DIR = backend/scripts_py (onde este arquivo e historico.py
# moram) -- mesma convencao de main.py (self.base_dir). BASE_DIR =
# backend/ (um nivel acima) -- mesma convencao de api_server.py e
# ColetorHistoricoMTF.base_dir em historico.py (dirname(dirname(...))),
# onde json/ e parquet/ realmente moram.
SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(SCRIPTS_DIR)
JSON_DIR = os.path.join(BASE_DIR, "json")
CONFIG_PATH = os.path.join(JSON_DIR, "config.json")
ESTADO_PATH = os.path.join(JSON_DIR, "frescor_cotacoes_estado.json")
MTF_DIR = os.path.join(BASE_DIR, "parquet", "historicos", "MTF")
CONTROLE_PATH = os.path.join(MTF_DIR, "controle_atualizacao_mtf.parquet")
HISTORICO_SCRIPT_PATH = os.path.join(SCRIPTS_DIR, "historico.py")

# mes abreviado em ingles -> numero (tickers estilo corretora internacional:
# DolarOct26) -- mesma tabela de historico.py (duplicada aqui de
# proposito pra este script NAO precisar importar historico.py, que
# exige o modulo MetaTrader5 instalado so pra isso).
MESES_ABREV = {
    "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
    "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12,
}


# piso absoluto de atraso (minutos) -- nunca sinaliza abaixo disso, e a
# cadencia normal de uma volta do loop do main.py
TOLERANCIA_MIN_ABSOLUTA = 30
# multiplicador sobre a mediana do grupo (dentro da janela) -- sinaliza
# so quem esta nitidamente pra tras dos proprios colegas agora
TOLERANCIA_MULTIPLICADOR = 4
# quantos dias uteis anteriores a hoje usa pra aprender a janela tipica
JANELA_DIAS_HISTORICO = 5
# folga (minutos) nas duas pontas da janela tipica antes de considerar
# "fora do horario esperado"
JANELA_FOLGA_MIN = 15
# quantos dias de M1 pede no --reforcar quando aciona
REFORCO_DIAS_M1 = 2
# nao tenta reforcar a MESMA raiz de novo antes disso (minutos) -- evita
# martelar MT5/disco se o problema for estrutural (reforcar nao resolve
# bug de vigente, por exemplo)
COOLDOWN_REFORCO_MIN = 45


def _ler_config():
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)


def _ler_estado():
    if not os.path.exists(ESTADO_PATH):
        return {}
    try:
        with open(ESTADO_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def _salvar_estado(estado):
    try:
        with open(ESTADO_PATH, "w", encoding="utf-8") as f:
            json.dump(estado, f, ensure_ascii=False, indent=2)
    except OSError as exc:
        print(f"AVISO verificar_frescor_cotacoes: nao consegui salvar {ESTADO_PATH}: {exc}")


def _universo_grades(config):
    """Raizes das duas grades de cotacao (Risk Indice + Risk Dolar),
    lidas DINAMICAMENTE de config.json -> grades_cotacoes.principal.feeds
    -- ver docstring do modulo pro motivo de nao ser hardcoded aqui."""
    ativos = config.get("ativos", {})
    feeds = config.get("grades_cotacoes", {}).get("principal", {}).get("feeds", [])
    raizes = set()
    if "last_int" in feeds:
        for grupo in ("moedas_continuo", "indices_continuo", "commodities_internacionais", "vencimento_americano"):
            raizes.update(ativos.get(grupo, []))
    if "sentimento_em" in feeds:
        raizes.update(ativos.get("etfs_sentimento_em", []) or {"EWZ", "EEM"})
    return raizes


def _extrai_mes_ano_americano(ticker, raiz):
    """Identico a ColetorHistoricoMTF.extrai_mes_ano_americano() do
    historico.py -- duplicado aqui pra nao precisar importar aquele
    modulo (exige MetaTrader5 instalado so pra isso)."""
    sufixo = ticker[len(raiz):]
    for nome, numero in MESES_ABREV.items():
        idx = sufixo.find(nome)
        if idx != -1:
            ano2 = sufixo[idx + 3: idx + 5]
            if ano2.isdigit():
                return numero, 2000 + int(ano2)
    return None


def _ativo_pasta(raiz, config):
    """(pasta_rel, ticker) do vigente ATUAL -- mesma logica de
    montar_alvos() do historico.py. None se o ativo nao tiver vigente
    resolvido ainda (ex: config.json->vigentes vazio pra essa raiz --
    nao e staleness, e so nunca rodou vigente.py pra ela)."""
    ativos = config.get("ativos", {})
    if raiz in ativos.get("vencimento_americano", []):
        tickers = config.get("vigentes", {}).get(raiz) or []
        if not tickers:
            return None
        ticker = tickers[0]
        resultado = _extrai_mes_ano_americano(ticker, raiz)
        if resultado is None:
            return None
        mes, ano = resultado
        return f"{raiz}/{mes:02d}-{ano}", ticker
    return raiz, raiz


def _historico_controle(controle_m1, pasta_rel):
    """Linhas de controle (ja filtradas em timeframe=='M1') desta
    pasta_rel, ordenadas por data_ultima_atualizacao -- controle e
    append-only, entao isso e o historico completo de quando esse ativo
    teve preco novo, sem precisar tocar no m1.parquet (mais leve)."""
    sub = controle_m1[controle_m1["ativo_pasta"] == pasta_rel]
    return sub.sort_values("data_ultima_atualizacao")


def _janela_tipica(historico_pasta, dias=JANELA_DIAS_HISTORICO):
    """Janela tipica (hora:min inicio, hora:min fim) de preco real deste
    ativo, pelos ultimos `dias` dias de pregao ANTERIORES a hoje --
    aprendida dos proprios dados (controle_atualizacao_mtf.parquet),
    nunca assumida (ver docstring do modulo). None se nao tiver pelo
    menos 2 dias com historico suficiente pra confiar -- quem chama
    PULA o ativo nesse caso (nunca sinaliza sem conseguir julgar)."""
    if historico_pasta.empty:
        return None
    hoje = datetime.datetime.now().date()
    datas = sorted({t.date() for t in historico_pasta["data_ultima_atualizacao"]}, reverse=True)
    datas_anteriores = [d for d in datas if d < hoje][:dias]
    if len(datas_anteriores) < 2:
        return None
    inicios, fins = [], []
    for d in datas_anteriores:
        do_dia = historico_pasta[historico_pasta["data_ultima_atualizacao"].dt.date == d]
        if do_dia.empty:
            continue
        inicios.append(do_dia["data_ultima_atualizacao"].min())
        fins.append(do_dia["data_ultima_atualizacao"].max())
    if len(inicios) < 2:
        return None
    inicios_min = sorted(t.hour * 60 + t.minute for t in inicios)
    fins_min = sorted(t.hour * 60 + t.minute for t in fins)
    mediana_inicio = inicios_min[len(inicios_min) // 2]
    mediana_fim = fins_min[len(fins_min) // 2]
    return mediana_inicio, mediana_fim


def _dentro_da_janela(agora_min, janela, folga=JANELA_FOLGA_MIN):
    if janela is None:
        return False
    inicio, fim = janela
    return (inicio - folga) <= agora_min <= (fim + folga)


def _reforcar(raizes, estado, agora_ts):
    """Chama historico.py --reforcar M1:REFORCO_DIAS_M1 --so <raizes>
    numa unica rodada -- so pras raizes que nao foram reforcadas nos
    ultimos COOLDOWN_REFORCO_MIN minutos (estado em
    json/frescor_cotacoes_estado.json). Atualiza o estado mesmo se a
    chamada falhar (evita loop de retry imediato -- se falhou agora,
    provavelmente falha nas proximas tentativas tambem, espera o
    cooldown normal)."""
    elegveis = []
    for raiz in raizes:
        ultimo = estado.get(raiz)
        if ultimo is not None and (agora_ts - ultimo) < COOLDOWN_REFORCO_MIN * 60:
            print(f"  [cooldown] {raiz}: ja tentou reforcar ha menos de {COOLDOWN_REFORCO_MIN}min, pulando")
            continue
        elegveis.append(raiz)

    if not elegveis:
        return

    print(f"  reforcando (M1:{REFORCO_DIAS_M1} dias): {', '.join(sorted(elegveis))}")
    for raiz in elegveis:
        estado[raiz] = agora_ts
    _salvar_estado(estado)

    try:
        resultado = subprocess.run(
            [
                sys.executable, HISTORICO_SCRIPT_PATH,
                "--reforcar", f"M1:{REFORCO_DIAS_M1}",
                "--so", ",".join(sorted(elegveis)),
            ],
            cwd=SCRIPTS_DIR,
            timeout=600,
        )
        if resultado.returncode != 0:
            print(f"  AVISO: historico.py --reforcar terminou com codigo {resultado.returncode}")
    except subprocess.TimeoutExpired:
        print("  AVISO: historico.py --reforcar nao terminou em 10min, abandonado")
    except OSError as exc:
        print(f"  AVISO: nao consegui chamar historico.py --reforcar: {exc}")


def verificar():
    try:
        config = _ler_config()
    except (OSError, json.JSONDecodeError) as exc:
        print(f"AVISO verificar_frescor_cotacoes: nao consegui ler {CONFIG_PATH}: {exc} -- pulando esta volta")
        return

    if not os.path.exists(CONTROLE_PATH):
        print("AVISO verificar_frescor_cotacoes: controle_atualizacao_mtf.parquet ainda nao existe -- pulando")
        return

    try:
        controle = pd.read_parquet(CONTROLE_PATH, columns=["ativo_pasta", "timeframe", "data_ultima_atualizacao"])
    except (OSError, ValueError) as exc:
        print(f"AVISO verificar_frescor_cotacoes: nao consegui ler o controle: {exc} -- pulando esta volta")
        return

    controle_m1 = controle[controle["timeframe"] == "M1"]
    agora = datetime.datetime.now()
    agora_min = agora.hour * 60 + agora.minute

    universo = sorted(_universo_grades(config))
    linhas = []  # (raiz, pasta_rel, lag_min)
    fora_da_janela = []
    sem_historico = []

    for raiz in universo:
        resolvido = _ativo_pasta(raiz, config)
        if resolvido is None:
            sem_historico.append(raiz)
            continue
        pasta_rel, ticker = resolvido

        historico_pasta = _historico_controle(controle_m1, pasta_rel)
        if historico_pasta.empty:
            sem_historico.append(raiz)
            continue

        janela = _janela_tipica(historico_pasta)
        if not _dentro_da_janela(agora_min, janela):
            fora_da_janela.append(raiz)
            continue

        # .replace(tzinfo=None): a coluna data_ultima_atualizacao vem
        # tipada tz-aware (UTC) do parquet, mas o VALOR numerico ja e
        # horario direto de Brasilia (mesma convencao do resto do
        # projeto -- tag de fuso e so cosmetica aqui, ver fuso_horario.py
        # e o fix de 2026-10-01 na 1.27.0 do api_server.py). agora
        # (datetime.now(), sem tz) precisa comparar com algo igualmente
        # naive, senao Python recusa a subtracao.
        ultima_atualizacao = historico_pasta["data_ultima_atualizacao"].iloc[-1].to_pydatetime().replace(tzinfo=None)
        lag_min = (agora - ultima_atualizacao).total_seconds() / 60
        linhas.append((raiz, pasta_rel, lag_min))

    if not linhas:
        print(f"verificar_frescor_cotacoes: nenhum ativo dentro da janela esperada agora ({len(fora_da_janela)} fora do horario, {len(sem_historico)} sem historico suficiente) -- nada pra checar")
        return

    lags = sorted(l for _, _, l in linhas)
    mediana = lags[len(lags) // 2]
    limite = max(TOLERANCIA_MIN_ABSOLUTA, TOLERANCIA_MULTIPLICADOR * mediana)

    suspeitos = [(raiz, lag) for raiz, _, lag in linhas if lag > limite]

    print(
        f"verificar_frescor_cotacoes: {len(linhas)} ativos dentro da janela "
        f"(mediana de atraso {mediana:.1f}min, limite {limite:.1f}min) -- "
        f"{len(suspeitos)} suspeito(s)"
    )
    for raiz, lag in sorted(suspeitos, key=lambda x: -x[1]):
        print(f"  SUSPEITO: {raiz} com {lag:.1f}min de atraso (limite {limite:.1f}min)")

    if not suspeitos:
        return

    estado = _ler_estado()
    agora_ts = agora.timestamp()
    _reforcar([raiz for raiz, _ in suspeitos], estado, agora_ts)


if __name__ == "__main__":
    verificar()
