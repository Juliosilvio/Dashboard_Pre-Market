"""
Nome do script : vigente.py
Descricao      : Resolve o ticker vigente + a lista de contratos
                  subsequentes com preco real, pra duas familias lidas de
                  json/config.json (nao fica hardcoded no script):

                  1) ativos.curva_br (corretora nacional, padrao B3 raiz+letra+
                     ano) — o vigente NAO depende do MT5, e conta pura de
                     calendario da maquina: o contrato do mes corrente
                     sempre ja expirou (vence no dia 01), entao o vigente e
                     sempre o do mes seguinte (mes atual + 1). A varredura
                     dos subsequentes cobre os proximos 10 anos inteiros
                     (JANELA_ANOS) sem parar no primeiro mes vazio — a curva
                     fica esparsa quanto mais longe (mensal, trimestral,
                     depois so janeiro), um mes sem contrato e so um buraco
                     no meio da curva, nao o fim dela.

                  2) ativos.vencimento_americano (corretora corretora internacional,
                     padrao raiz+nome do mes+ano) — aqui o vigente PRECISA
                     consultar o MT5: a corretora so cria o symbol do mes
                     novo quando ela quiser, sem calendario teorico fixo pra
                     confiar. Tenta mes atual+1 primeiro; se nao existir
                     ainda, cai pro mes atual. Varredura dos subsequentes
                     numa janela menor (JANELA_MESES_AMERICANO), sem
                     pre-listagem de anos como a B3.

                  2.4.0 (pedido do usuario, caso do Gasol): a familia
                  vencimento_americano agora aceita bid/ask como "tem preco
                  real" em vez de exigir last (ver usar_bid_ask em
                  _tem_preco_real()) — contratos da corretora internacional cotam por
                  book, e o "last" pode ficar 0.0 por tempo indeterminado
                  mesmo com o symbol ativo (visto com GasolOct26, via
                  diag_gasol.py). A familia curva_br continua usando last,
                  sem mudanca.

                  Em ambas, hora sempre LOCAL da maquina (fuso do Brasil),
                  nunca UTC, senao nas ultimas horas de cada dia o calculo
                  pode adiantar o mes por engano. Criterio de "tem preco
                  real": ultimo preco (last) E fechamento diario (close,
                  candle D1 recente). Excecao: raizes em EXCECOES_SO_CLOSE
                  (hoje so OC1) nunca tem last nem candle D1
                  (copy_rates_from_pos volta vazio, confirmado) — o preco
                  real delas vem de symbol_info().session_close. Salva em
                  json/config.json, chave "vigentes" (raiz -> lista de
                  tickers, vigente primeiro), sem mexer no resto do arquivo.
                  RAIZES_TESTE / RAIZES_TESTE_AMERICANO filtram quais raizes
                  cada rodada processa. Um symbol_select() num ticker que
                  nao estava visivel no Market Watch nao populaa info/rates
                  na hora — o terminal precisa de um instante pra
                  sincronizar com o servidor (mesmo motivo das passadas com
                  pausa que ja existem no nac.py/int.py) — por isso o
                  script tenta de novo (TENTATIVAS_SYNC) antes de descartar
                  um ticker como "sem preco".
                  Grava config.json UMA UNICA VEZ, no final de executar(),
                  depois de resolver todas as raizes em memoria (nunca
                  escreve por raiz) — nao imprime nada no terminal.
Autor          : Julio Cesar Silvio Campanhola
Criado em      : 2026-09-15
Ultima edicao  : 2026-09-30
Versao         : 2.6.0
Projeto        : dashboard
Historico      : scripts_py/versoes/vigente.md
"""

import importlib
import json
import os
import time
from datetime import datetime, timedelta, timezone

try:
    mt5 = importlib.import_module("MetaTrader5")
except ImportError as exc:
    raise ImportError(
        "A dependencia MetaTrader5 nao esta instalada. "
        "Instale-a com: pip install MetaTrader5"
    ) from exc
try:
    psutil = importlib.import_module("psutil")
except ImportError as exc:
    raise ImportError(
        "A dependencia psutil nao esta instalada. "
        "Instale-a com: pip install psutil"
    ) from exc

# raizes de curva_br a processar nesta rodada (lidas de config.json, filtradas por essa lista)
# pedido do usuario: "ADICIONEI O DDI" em ativos.curva_br (config.json) —
# sem incluir aqui tambem, essa lista IGNORARIA a raiz nova silenciosamente
# (carregar_raizes_curva_br() so deixa passar quem esta nos dois lugares) e
# vigentes["DDI"] nunca seria criado, quebrando o grade.py/last_nac.py em
# cadeia (grade.py cai pro fallback vigentes.get("DDI", ["DDI"]) e tenta
# selecionar um ticker literal "DDI" que nao existe na B3 — o certo e
# "DDIV26", "DDIF27" etc, igual DI1/FRC).
# DOLAR entrou em 2026-09-17 (pedido do usuario: "usa o dolarv26 da corretora nacional pra
# calcular" — ver _dolar_teorico() no api_server.py 1.8.0). Motivo de
# processar o DOLAR pela MESMA resolver_raiz() do DI1/FRC/DDI em vez de um
# caminho proprio: assim o vertice vigente do DOLAR cai SEMPRE no mesmo mes
# do DI1/FRC (os tres usam o mesmo _mes_vigente() = mes atual+1), fechando
# de vez o descasamento que existia comparando com o Dolar da corretora internacional
# (que vence no ULTIMO dia util do mes, nao no primeiro feito DI1/FRC/DDI/
# DAP — ver historico da 1.7.0/1.8.0 do api_server.py). O vencimento REAL
# do DOLAR (ultimo dia util) so importa pro DESCONTO du/dc em
# _dolar_teorico(), nao pra escolha de QUAL vertice comparar.
RAIZES_TESTE = ["DI1",
      "OC1",
      "DAP",
      "FRC",
      "DDI",
      "DOLAR"]

# raizes de vencimento_americano a processar nesta rodada (None = todas do config.json)
RAIZES_TESTE_AMERICANO = None

# raizes que so tem fechamento diario (close), nunca ultimo preco (last) —
# pra essas, o criterio de "tem preco real" cai so pro close
EXCECOES_SO_CLOSE = ["OC1"]

LETRA_MES = {1: "F", 2: "G", 3: "H", 4: "J", 5: "K", 6: "M",
             7: "N", 8: "Q", 9: "U", 10: "V", 11: "X", 12: "Z"}
NOME_MES = {1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "May", 6: "Jun",
            7: "Jul", 8: "Aug", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec"}

JANELA_ANOS = 10  # curva brasileira de juros vai ate 10 anos a frente
JANELA_MESES = JANELA_ANOS * 12
JANELA_MESES_AMERICANO = 12  # corretora internacional nao pre-lista anos a frente feito a B3
RECENCIA_MAX_DIAS = 10   # candle D1 mais velho que isso nao conta como "tem fechamento"
TENTATIVAS_SYNC = 3      # symbol recem-visivel pode levar um instante pra sincronizar
PAUSA_SYNC = 1.0         # segundos entre tentativas de sincronizacao


class ResolvedorVigente:
    """Resolve o vigente por calendario e a lista de subsequentes com preco real no MT5."""

    def __init__(self, base_dir=None):
        self.base_dir = base_dir or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.config_path = os.path.join(self.base_dir, "json", "config.json")
        self.conexao = None

    def _carregar_config(self):
        with open(self.config_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def carregar_conexao(self, broker):
        config = self._carregar_config()
        self.conexao = config["connections"][broker]
        return self.conexao

    def carregar_raizes_curva_br(self):
        """Le as raizes direto de json/config.json -> ativos.curva_br (nao fica hardcoded no script)."""
        config = self._carregar_config()
        raizes = config["ativos"]["curva_br"]
        if RAIZES_TESTE is not None:
            raizes = [r for r in raizes if r in RAIZES_TESTE]
        return raizes

    def carregar_raizes_vencimento_americano(self):
        """Le as raizes direto de json/config.json -> ativos.vencimento_americano."""
        config = self._carregar_config()
        raizes = config["ativos"]["vencimento_americano"]
        if RAIZES_TESTE_AMERICANO is not None:
            raizes = [r for r in raizes if r in RAIZES_TESTE_AMERICANO]
        return raizes

    def _terminal_esta_aberto(self, exe_path):
        alvo = os.path.normcase(os.path.abspath(exe_path))
        for proc in psutil.process_iter(["exe"]):
            try:
                exe = proc.info.get("exe")
                if exe and os.path.normcase(os.path.abspath(exe)) == alvo:
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
        return False

    def _garantir_terminal_aberto(self, exe_path, espera_max=20):
        if self._terminal_esta_aberto(exe_path):
            return
        os.startfile(exe_path)
        for _ in range(espera_max):
            time.sleep(1)
            if self._terminal_esta_aberto(exe_path):
                time.sleep(3)
                return

    def conectar(self, broker):
        self.carregar_conexao(broker)
        self._garantir_terminal_aberto(self.conexao["path"])
        ok = mt5.initialize(
            path=self.conexao["path"],
            login=self.conexao["login"],
            password=self.conexao["password"],
            server=self.conexao["server"],
        )
        if not ok:
            raise RuntimeError(f"[{broker}] falha ao conectar: {mt5.last_error()}")

    def _ticker_b3(self, raiz, ano, mes):
        return f"{raiz}{LETRA_MES[mes]}{ano % 100:02d}"

    def _ticker_americano(self, raiz, ano, mes):
        return f"{raiz}{NOME_MES[mes]}{ano % 100:02d}"

    def _mes_seguinte(self, ano_ref, mes_ref):
        """Mes seguinte ao informado, virando o ano em dezembro->janeiro."""
        mes = mes_ref + 1
        ano = ano_ref
        if mes > 12:
            mes = 1
            ano += 1
        return ano, mes

    def _mes_vigente(self, ano_ref, mes_ref):
        """Contrato do mes corrente ja expirou (vence dia 01) — vigente e sempre mes+1."""
        return self._mes_seguinte(ano_ref, mes_ref)

    def _tem_preco_real(self, ticker, excecao=False, usar_bid_ask=False):
        """Raiz normal: exige "tem cotacao corrente" (ver usar_bid_ask abaixo) E
        fechamento diario (close, candle D1 recente). Raiz em EXCECOES_SO_CLOSE
        (ex: OC1): nunca tem last nem candle D1 (copy_rates_from_pos volta vazio
        pra ela — confirmado), o preco real dela vem de
        mt5.symbol_info().session_close, que o MT5 atualiza a cada reprecificacao
        teorica da curva (nao segue calendario de pregao, entao sem checar recencia).

        usar_bid_ask (pedido do usuario, caso do Gasol): a familia
        vencimento_americano (corretora internacional) passa usar_bid_ask=True — em vez de
        exigir ultimo negocio (last), aceita ter bid OU ask populado. Motivo:
        diagnosticado com o GasolOct26 (diag_gasol.py) — o symbol JA EXISTIA no
        terminal e tinha candle D1 recente de verdade, mas o "last" ficava 0.0
        indefinidamente (contrato que cota por book, nao por ultimo negocio,
        igual boa parte dos CFDs/forex continuos da corretora internacional) — com o
        criterio antigo (so last), esse candidato NUNCA vira vigente, mesmo
        sendo o mes certo, e o script fica preso no mes anterior (que a
        corretora as vezes ja nem lista mais, como aconteceu aqui). A familia
        curva_br (corretora nacional — DI1/FRC/DDI/DOLAR/DAP) continua usando o criterio
        antigo (last) por padrao — la funciona bem e nao ha motivo pra mudar.
        Um symbol_select() em ticker que nao estava visivel no Market Watch nao
        populaa info/rates na hora — o terminal precisa de um instante pra sincronizar
        com o servidor (mesmo motivo das passadas com pausa no nac.py/int.py). Por
        isso tenta de novo algumas vezes antes de dar como "sem preco"."""
        if not mt5.symbol_select(ticker, True):
            return False

        for tentativa in range(TENTATIVAS_SYNC):
            info = mt5.symbol_info(ticker)

            if excecao:
                tem_preco = info is not None and info.session_close not in (0, 0.0)
            else:
                if usar_bid_ask:
                    tem_last = info is not None and (
                        info.bid not in (0, 0.0) or info.ask not in (0, 0.0)
                    )
                else:
                    tem_last = info is not None and info.last not in (0, 0.0)
                rates = mt5.copy_rates_from_pos(ticker, mt5.TIMEFRAME_D1, 0, 1)
                tem_close = False
                if rates is not None and len(rates) > 0:
                    candle_time = datetime.fromtimestamp(rates[0]["time"], tz=timezone.utc)
                    recente = (datetime.now(timezone.utc) - candle_time) <= timedelta(days=RECENCIA_MAX_DIAS)
                    tem_close = recente and rates[0]["close"] not in (0, 0.0)
                tem_preco = tem_last and tem_close

            if tem_preco:
                return True
            if tentativa < TENTATIVAS_SYNC - 1:
                time.sleep(PAUSA_SYNC)

        return False

    def resolver_raiz(self, raiz, ano_ref, mes_ref):
        """Vigente por calendario (mes+1); varre os proximos JANELA_ANOS anos inteiros
        coletando todo mes que tiver preco real. A curva brasileira nao e mensal o
        tempo todo (fica esparsa — trimestral, depois so janeiro — quanto mais longe),
        entao NAO para no primeiro mes vazio: um mes sem contrato e so um buraco no
        meio da curva, nao o fim dela.

        Reescrito 2026-09-30 (mesmo incidente Risk Dolar/Dolar Teorico vazios
        que motivou o fix do resolver_raiz_americano() mais cedo hoje --
        MESMO padrao de bug, dessa vez do lado curva_br/corretora nacional): antes, o
        candidato de posicao 1 (mes_ref+1) entrava na lista SEM checar
        _tem_preco_real() -- so os candidatos seguintes eram verificados.
        Pra DI1/DDI/DAP/DOLAR isso nunca deu problema (o mes+1 deles sempre
        tem preco real). Pro FRC deu: FRCV26 (mes+1 de hoje) nunca teve UM
        preco real sequer (nem no double buffer, nem no historico
        retornoD1.parquet) -- mesmo assim virava "vigente" as cegas, e o
        _dolar_teorico() (api_server.py) ficava permanentemente preso em
        "faltando dado real de FRC" tentando usar um vertice morto. Agora
        anda candidato a candidato (mes_ref+1, +2, +3... ate JANELA_MESES a
        frente) e usa o PRIMEIRO que realmente tiver preco real -- igual
        resolver_raiz_americano() ja faz. Depois de achado, continua
        andando a partir dali pra completar a curva esparsa, igual antes."""
        excecao = raiz in EXCECOES_SO_CLOSE
        ano_cand, mes_cand = self._mes_vigente(ano_ref, mes_ref)

        ano_vig = mes_vig = ticker_vigente = None
        for _ in range(JANELA_MESES):
            candidato = self._ticker_b3(raiz, ano_cand, mes_cand)
            if self._tem_preco_real(candidato, excecao=excecao):
                ano_vig, mes_vig, ticker_vigente = ano_cand, mes_cand, candidato
                break
            mes_cand += 1
            if mes_cand > 12:
                mes_cand = 1
                ano_cand += 1

        if ticker_vigente is None:
            # nenhum candidato na janela toda teve preco real -- ultimo
            # recurso (comportamento antigo, sem garantia), so pra nao
            # devolver lista vazia; precisa de investigacao manual.
            ano_vig, mes_vig = self._mes_vigente(ano_ref, mes_ref)
            ticker_vigente = self._ticker_b3(raiz, ano_vig, mes_vig)

        lista = [ticker_vigente]
        ano, mes = ano_vig, mes_vig
        for _ in range(JANELA_MESES - 1):
            mes += 1
            if mes > 12:
                mes = 1
                ano += 1
            candidato = self._ticker_b3(raiz, ano, mes)
            if self._tem_preco_real(candidato, excecao=excecao):
                lista.append(candidato)

        return lista

    def resolver_raiz_americano(self, raiz, ano_ref, mes_ref):
        """Diferente da curva_br, aqui o vigente PRECISA consultar o MT5: a
        corretora internacional so cria o symbol do mes novo quando ela quiser, nao tem
        calendario teorico fixo pra confiar cegamente.

        Reescrito 2026-09-30 (incidente Risk Dolar/Dolar Teorico vazios):
        antes, testava so "mes atual+1"; se esse nao tivesse preco real,
        caia pro "mes atual" SEM CONFIRMAR que ele ainda estava ativo —
        assumia cegamente que sim. Isso quebrou no Dolar: a corretora internacional
        rolou o contrato direto de Set26 pra Nov26 (sem Out26 no meio), e
        o dia em que isso aconteceu, nem "mes atual" (Set26, ja rolado)
        nem "mes+1" (Out26, nunca existiu) tinham preco real — o script
        ficava preso no Set26 morto mesmo assim, porque nunca checava.

        Agora testa candidato a candidato (mes+1, mes atual, mes+2, mes+3,
        ... ate JANELA_MESES_AMERICANO meses a frente) e usa o PRIMEIRO que
        realmente tiver preco real (bid/ask) — nunca mais aceita um mes as
        cegas. mes+1 continua tendo prioridade sobre mes atual (mesma
        ordem de antes, pra pegar rolagem antecipada quando o proximo mes
        ja estiver ativo), mas agora mes atual so entra se REALMENTE
        passar no teste; se nem um nem outro passar, continua andando pra
        frente em vez de desistir. A partir do vigente encontrado, anda
        mes a mes testando os subsequentes pra completar a curva, igual
        antes."""
        ano_mais1, mes_mais1 = self._mes_seguinte(ano_ref, mes_ref)

        candidatos_ordem = [(ano_mais1, mes_mais1), (ano_ref, mes_ref)]
        ano_extra, mes_extra = ano_mais1, mes_mais1
        for _ in range(JANELA_MESES_AMERICANO):
            mes_extra += 1
            if mes_extra > 12:
                mes_extra = 1
                ano_extra += 1
            candidatos_ordem.append((ano_extra, mes_extra))

        ano_vig = mes_vig = ticker_vigente = None
        for ano_c, mes_c in candidatos_ordem:
            candidato = self._ticker_americano(raiz, ano_c, mes_c)
            if self._tem_preco_real(candidato, usar_bid_ask=True):
                ano_vig, mes_vig, ticker_vigente = ano_c, mes_c, candidato
                break

        if ticker_vigente is None:
            # nenhum candidato na janela toda teve preco real — ultimo
            # recurso (comportamento antigo, sem garantia), so pra nao
            # devolver lista vazia; um caso assim precisa de investigacao
            # manual (corretora pode estar sem nenhum contrato ativo desse
            # ativo no momento).
            ano_vig, mes_vig = ano_ref, mes_ref
            ticker_vigente = self._ticker_americano(raiz, ano_vig, mes_vig)

        lista = [ticker_vigente]
        ano, mes = ano_vig, mes_vig
        for _ in range(JANELA_MESES_AMERICANO - 1):
            mes += 1
            if mes > 12:
                mes = 1
                ano += 1
            candidato = self._ticker_americano(raiz, ano, mes)
            if self._tem_preco_real(candidato, usar_bid_ask=True):
                lista.append(candidato)

        return lista

    def executar(self):
        agora = datetime.now()  # hora LOCAL da maquina (fuso do Brasil) — nunca UTC
        vigentes = {}

        raizes_br = self.carregar_raizes_curva_br()
        if raizes_br:
            self.conectar("corretora nacional")
            for raiz in raizes_br:
                lista = self.resolver_raiz(raiz, agora.year, agora.month)
                vigentes[raiz] = lista
            mt5.shutdown()

        raizes_us = self.carregar_raizes_vencimento_americano()
        if raizes_us:
            self.conectar("corretora internacional")
            for raiz in raizes_us:
                lista = self.resolver_raiz_americano(raiz, agora.year, agora.month)
                vigentes[raiz] = lista
            mt5.shutdown()

        config = self._carregar_config()
        config.setdefault("vigentes", {}).update(vigentes)
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)

        return vigentes


if __name__ == "__main__":
    ResolvedorVigente().executar()
