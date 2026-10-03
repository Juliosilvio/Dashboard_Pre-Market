"""
Nome do script : last_int.py
Descricao      : Fica rodando continuamente (nao termina sozinho) capturando
                  SO o preco em tempo real (media entre bid e ask — ver
                  _info_atual() e o paragrafo "Pedido do usuario" no fim
                  deste cabecalho, 2026-09-18) de cada ticker visivel no
                  Market Watch, na corretora internacional ("int", internacional — mesma
                  convencao de int.py/int_m5.py). Nao lida com session_close_m5/d1 (isso
                  ja vem do historico_d1.parquet/historico_m5.parquet, obra
                  do int.py/int_m5.py) — o unico trabalho daqui e o preco
                  correndo. Conversa SO com o terminal MT5 (mt5.symbols_get()
                  + .visible), nunca com arquivo nenhum na varredura — quem
                  decide o que fica visivel e o grade.py, a partir da lista
                  curada do config.json; este coletor so segue o que ja esta
                  sincronizado no terminal.

                  Nasceu de duas rodadas de correcao no antigo tempo_real.py
                  (que fazia corretora nacional e corretora internacional no mesmo script, por
                  argumento de linha de comando) que continuavam nao
                  resolvendo de vez o problema: mesmo como processo Python
                  separado, qualquer script que conecta com o MESMO
                  path/login/server do MT5 gruda no MESMO terminal64.exe ja
                  aberto (e assim que o MT5 funciona, nao e coisa de script)
                  — entao esse coletor ficava competindo pelo mesmo canal com
                  vigente.py/grade.py/int.py/int_m5.py durante o ciclo pesado
                  do main.py, e o last travava atras de um backfill pesado
                  do int.py. A solucao definitiva e isolar de vez: este
                  script (last_int.py) e o last_nac.py agora sao dois
                  processos totalmente separados e dedicados, um por
                  corretora, cada um so fazendo essa unica coisa — e podem
                  (devem, quando configurado) usar um terminal MT5 PROPRIO,
                  isolado do terminal usado pelo resto do pipeline
                  (connections["corretora internacional_tempo_real"] no config.json, uma
                  instalacao portable separada, mesma conta — enquanto essa
                  chave nao existir, cai pra conexao normal/compartilhada
                  "corretora internacional" sem quebrar nada).

                  Mantem UMA ENTRADA POR SYMBOL (tabela de preco corrente, nao
                  log de historico) — a cada mudanca real de preco, a entrada
                  daquele symbol e atualizada em memoria (estado_atual) e o
                  arquivo inteiro e SOBRESCRITO no proximo flush, nunca
                  concatenado com o que ja existe. O arquivo fica pequeno e
                  fixo (um symbol = uma entrada), sempre com o ultimo preco de
                  cada um. O flush roda a CADA volta da varredura (PAUSA_LOOP,
                  0.3s) — nao so a cada N segundos: o guard interno (_sujo) ja
                  faz o flush ser barato (so escreve de verdade quando algum
                  symbol mudou de preco desde o ultimo flush), entao rodar o
                  flush toda volta custa quase nada quando o mercado esta
                  parado e reflete qualquer mudanca de preco quase que na hora
                  (dentro de ~0.3s) quando o mercado esta se mexendo.
                  Termina de forma limpa (grava o estado atual antes de sair,
                  se tiver mudanca pendente) tanto com Ctrl+C direto quanto
                  quando o main.py
                  cria o arquivo-sinal parquet/historicos/_stop_last.flag
                  (jeito mais confiavel de parar o processo de fora no
                  Windows, onde terminate() mata sem chance de rodar o
                  finally). Salva em json/last_json/last_int_a.json e
                  last_int_b.json (DOIS arquivos, alternando um por flush —
                  ver "double buffer" abaixo) — nomes proprios, separados do
                  last_nac.py: dois processos fazendo read+concat+write no
                  mesmo arquivo corrompem o dado (ja visto em producao no
                  tempo_real.py, com parquet). Escrita atomica dentro de cada
                  um (grava num .tmp e so troca de nome no final via
                  os.replace) — se o processo cair no meio do flush, o
                  arquivo anterior daquele lado fica intacto.

                  Double buffer (pedido do usuario): mesmo com escrita
                  atomica, no Windows um leitor com o arquivo aberto pode
                  colidir com o os.replace() de quem escreve (lock mais
                  rigido que no Linux) — trava quem escreve, ou falha quem
                  le. Por isso o flush alterna entre dois arquivos
                  (last_int_a / last_int_b): a cada volta grava so no
                  "proximo" (nunca no mesmo que acabou de gravar), entao o
                  outro fica parado e intacto, livre pra qualquer leitor
                  abrir sem disputa nenhuma com quem escreve. Quem for ler
                  compara o mtime dos dois e le sempre o mais recente —
                  nunca esbarra no que esta sendo escrito naquele instante
                  (pode ficar ate ~0.3s atras do preco real, nunca mais que
                  isso). CORRECAO (2026-09-15): a versao anterior descrevia
                  esse double buffer aqui no cabecalho mas o CODIGO nunca
                  tinha sido de fato atualizado pra implementar — ficou so
                  documentado, gravando ainda num unico last_int.parquet.
                  Corrigido nesta versao, junto com a troca pra JSON abaixo.

                  Corrigido um bug real de producao (visto em duas rodadas):
                  a 1a versao calculava a lista desejada lendo e reparseando
                  o config.json do ZERO a cada volta da varredura (0.3s,
                  ~200x/minuto, pra sempre) — mas o vigente.py escreve NESSE
                  MESMO ARQUIVO uma vez por volta do pipeline (~5min). Ler o
                  arquivo no instante exato da escrita dele (Windows bloqueia
                  o arquivo, ou o JSON fica incompleto no meio da escrita)
                  derrubava o processo inteiro sem tratamento — e como o
                  main.py so sobe o coletor uma vez (nao reinicia sozinho se
                  ele morrer), isso explicava o preco "funcionar e depois
                  sumir". A correcao definitiva nao foi so cachear a leitura
                  (2a versao) — foi tirar o arquivo da jogada de vez: agora
                  _lista_desejada() so pergunta pro terminal MT5
                  (mt5.symbols_get().visible), sem tocar em config.json
                  nenhuma vez durante a varredura. O grade.py continua sendo
                  quem decide o que fica visivel a partir do config.json;
                  este coletor so acompanha o terminal. Efeito colateral
                  aceito: por um instante, enquanto o vigente.py testa
                  candidatos (symbol_select em ticker que pode nao virar
                  vigente), esse candidato aparece visivel e pode gerar uma
                  entrada a mais no arquivo — autocorrige sozinho no ciclo
                  seguinte, quando o grade.py limpa o Market Watch de novo; e
                  infinitamente melhor que o processo inteiro morrer. O loop
                  principal tambem encapsula _varrer()/_flush() em
                  try/except, como reforco — nenhum erro transiente derruba
                  mais o processo 24/7.

                  Pedido do usuario: o arquivo virou tabela de preco corrente
                  (uma entrada por symbol, sobrescrita a cada flush) em vez de
                  log de historico (uma entrada nova por mudanca, acumulando
                  pra sempre) — o log crescia rapido demais pra quem so
                  queria o preco atual (symbol liquido tipo UsaTec gerava
                  centenas de linhas em meia hora).

                  Pedido do usuario: o flush nao podia mais esperar
                  FLUSH_A_CADA_SEGUNDOS (30s) — tinha que ser bem menor que 1s,
                  ou a cada mudanca de preco por ativo. Como o guard _sujo ja
                  garante que _flush() so escreve de verdade quando algo
                  mudou, a solucao foi simplesmente chamar _flush() a cada
                  volta do loop (junto com _varrer(), a cada PAUSA_LOOP =
                  0.3s) em vez de esperar uma janela de tempo — constante
                  FLUSH_A_CADA_SEGUNDOS removida, nao faz mais sentido.

                  Pedido do usuario: trocar o formato de parquet pra JSON —
                  leitor decidido como sendo sempre Python (view tambem em
                  Python), mas JSON fica mais leve/trivial de inspecionar e
                  ler pra um arquivo minusculo que e reescrito o tempo todo
                  (sem overhead de serializacao colunar do pyarrow pra uma
                  tabela de meia duzia de colunas). Saiu parquet/last_close/,
                  entrou json/last_json/ — dependencia de pandas removida
                  deste script (nao sobrou nenhum outro uso dela aqui).

                  Pedido do usuario: calcular a variacao diaria na tabela de
                  cotacoes do frontend — precisa comparar o preco corrente
                  (last) com o fechamento oficial da sessao anterior
                  (session_close) de cada symbol, e este arquivo (last_int_a/
                  b.json) so tinha last. Mesma tecnica ja usada no
                  last_nac.py 1.7.0 (feed da corretora nacional): _preco_atual() virou
                  _info_atual(), trocando symbol_info_tick() por
                  symbol_info() (mesma chamada MT5, um pouco mais pesada, mas
                  cobre last/bid E session_close numa passada so) — devolve
                  (preco, session_close). _varrer() so pula um symbol se os
                  DOIS vierem None (antes so olhava o preco). A chave de
                  "mudou desde a ultima volta" virou a tupla (preco,
                  session_close). Cada registro do JSON ganhou o campo
                  "session_close" (pode vir null quando o symbol nao tiver —
                  variacao entao fica "--" no frontend, ver QuotesTable.jsx).

                  Pedido do usuario (2026-09-18) — "TODOS OS CONTRATOS DA
                  corretora internacional DEVEM VIR PARA O DASHBOARD COM MEDIA ENTRE
                  bid e ask": _info_atual() trocou o preco corrente de
                  "last, com fallback pra bid" pra "media entre bid e ask,
                  com fallback em cascata pra um dos dois isolado e por
                  ultimo pra last". Motivo: investigando por que o vigente.py
                  nao promovia o GasolOct26 (diag_gasol.py), descobrimos que
                  contratos da corretora internacional cotam por BOOK, nao por ultimo
                  negocio — "last" fica 0.0 por tempo indeterminado mesmo
                  com o symbol ativo, e usar so um lado do book (bid OU ask)
                  nao reflete o preco justo tao bem quanto o meio do spread.
                  O campo do JSON continua se chamando "last" (nao
                  renomeado, pra nao precisar mexer em api_server.py/
                  QuotesTable.jsx/client.js por uma mudanca que e so de
                  CALCULO, nao de formato) — o valor e que mudou de
                  significado.
Autor          : Julio Cesar Silvio Campanhola
Criado em      : 2026-09-15
Ultima edicao  : 2026-09-18
Versao         : 1.8.0
Projeto        : dashboard
Historico      : scripts_py/versoes/last_int.md
"""

import importlib
import json
import os
import sys
import time
from datetime import datetime, timezone

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

BROKER = "corretora internacional"

PAUSA_LOOP = 0.3             # segundos entre cada varredura de tick — so leitura de tick, e barato
                              # o flush roda junto, a cada volta (guard _sujo torna isso barato)


class ColetorLastInt:
    """Grava o preco (media entre bid e ask, com fallback em cascata — ver
    _info_atual()) e o session_close de todo symbol da lista curada, na
    corretora internacional — uma entrada por symbol, sempre com o valor mais recente."""

    def __init__(self, base_dir=None):
        self.broker = BROKER
        self.base_dir = base_dir or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.config_path = os.path.join(self.base_dir, "json", "config.json")
        output_dir = os.path.join(self.base_dir, "json", "last_json")
        self.output_path_a = os.path.join(output_dir, "last_int_a.json")
        self.output_path_b = os.path.join(output_dir, "last_int_b.json")
        self.stop_flag_path = os.path.join(self.base_dir, "parquet", "historicos", "_stop_last.flag")
        os.makedirs(output_dir, exist_ok=True)
        self.conexao = None
        self.ultimo_valor = {}    # symbol -> (last, session_close) (pra detectar mudanca)
        self.estado_atual = {}    # symbol -> entrada atual (broker/symbol/time/last/session_close)
        self._sujo = False        # True quando estado_atual mudou desde o ultimo flush
        self._proximo_arquivo = "a"  # double buffer: qual dos dois leva a proxima escrita

    def _carregar_config(self):
        with open(self.config_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def carregar_conexao(self):
        """Usa uma conexao DEDICADA (terminal MT5 proprio, instalacao portable
        separada) se existir em config.json -> connections["corretora internacional_tempo_real"]
        — assim este coletor nunca compartilha o terminal64.exe (e o canal de IPC
        dele) com vigente.py/grade.py/int.py/int_m5.py etc. Enquanto essa chave
        nao existir, cai pra conexao normal (compartilhada) sem quebrar nada."""
        config = self._carregar_config()
        connections = config.get("connections", {})
        self.conexao = connections.get("corretora internacional_tempo_real") or connections["corretora internacional"]
        return self.conexao

    def _lista_desejada(self):
        """Quem esta visivel no Market Watch agora — pergunta direto pro MT5
        (mt5.symbols_get(), uma chamada em memoria/IPC com o terminal, ZERO
        leitura de arquivo). O coletor so conversa com o terminal MT5, nunca
        com o config.json na varredura — isso tira de vez a corrida de
        leitura/escrita com o vigente.py (que escreve config.json uma vez por
        volta do pipeline) que derrubava o processo. O grade.py e quem decide
        o que fica visivel, a partir da lista curada do config.json — este
        coletor so segue o que ja esta sincronizado no terminal. Pode pegar um
        candidato extra por um instante enquanto o vigente.py testa symbols
        (fica visivel de leve ate o grade.py limpar, no mesmo ciclo) — efeito
        colateral aceito: e so uma entrada a mais no arquivo, autocorrige
        sozinho no proximo ciclo, e nunca derruba o processo."""
        return [s.name for s in mt5.symbols_get() if s.visible]

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

    def conectar(self):
        if self.conexao is None:
            self.carregar_conexao()
        self._garantir_terminal_aberto(self.conexao["path"])
        ok = mt5.initialize(
            path=self.conexao["path"],
            login=self.conexao["login"],
            password=self.conexao["password"],
            server=self.conexao["server"],
        )
        if not ok:
            raise RuntimeError(f"[{self.broker}] falha ao conectar: {mt5.last_error()}")

    def _info_atual(self, symbol):
        """Le mt5.symbol_info(symbol) UMA UNICA VEZ por symbol — traz o preco
        corrente E session_close (fechamento oficial da sessao) no MESMO
        struct, entao nao precisa de uma segunda chamada MT5 so pra
        session_close (usado na variacao diaria da tabela de cotacoes do
        frontend — ver QuotesTable.jsx).

        Preco corrente (pedido do usuario, 2026-09-18 — "TODOS OS CONTRATOS
        DA corretora internacional DEVEM VIR PARA O DASHBOARD COM MEDIA ENTRE bid e
        ask"): MEDIA entre bid e ask quando os dois existirem — nao mais
        "last, com fallback pra bid". Motivo: diagnosticado com o Gasol
        (diag_gasol.py) que contratos da corretora internacional cotam por BOOK (bid/
        ask), nao por ultimo negocio — o "last" fica 0.0 por tempo
        indeterminado mesmo com o symbol ativo e negociando de verdade, e
        so olhar bid OU so ask (like antes: "last or bid") pega so um lado
        do spread, nao o meio. Fallback em cascata pra symbol com o book
        incompleto (raro): se so um dos dois existir, usa esse; se nenhum
        dos dois existir, cai pro last como ultimo recurso (mantem alguma
        cobertura em vez de descartar o symbol). Devolve (preco,
        session_close), qualquer um dos dois pode vir None se o symbol nao
        tiver aquele dado.

        Efeito colateral bom: USDBRL (moedas_continuo, tambem passa por
        aqui) alimenta o spot_usdbrl de _dolar_teorico() no api_server.py —
        o meio do book e uma referencia mais estavel que um lado so do
        spread pra esse calculo."""
        info = mt5.symbol_info(symbol)
        if info is None:
            return None, None
        bid = info.bid or None
        ask = info.ask or None
        if bid and ask:
            preco = (bid + ask) / 2
        else:
            preco = bid or ask or info.last or None
        session_close = info.session_close or None
        return preco, session_close

    def _varrer(self):
        """Uma passada por todo symbol da lista curada (config.json); atualiza o
        estado atual (uma entrada por symbol) de quem mudou de preco ou de
        session_close desde a ultima volta — nao acumula historico, so o
        valor mais recente de cada symbol. Symbol sem NENHUM dos dois (nem
        preco nem session_close) e ignorado — nao ha nada aproveitavel pra
        gravar ainda."""
        desejados = self._lista_desejada()
        agora = datetime.now(timezone.utc)

        for symbol in desejados:
            if not mt5.symbol_select(symbol, True):
                continue
            preco, session_close = self._info_atual(symbol)
            if preco is None and session_close is None:
                continue

            chave_mudanca = (preco, session_close)
            if self.ultimo_valor.get(symbol) == chave_mudanca:
                continue

            self.ultimo_valor[symbol] = chave_mudanca
            self.estado_atual[symbol] = {
                "broker": self.broker,
                "symbol": symbol,
                "time": agora,
                "last": preco,
                "session_close": session_close,
            }
            self._sujo = True

    def _flush(self):
        """Grava o estado atual inteiro em JSON (uma entrada por symbol, sempre
        SOBRESCREVENDO — nao concatena com o que ja existe, isso nao e log de
        historico, e tabela de preco corrente). Double buffer: cada flush
        grava so no arquivo "proximo" (a ou b), nunca no mesmo que acabou de
        ser gravado — assim o outro fica sempre parado e completo, livre pra
        qualquer leitor abrir sem disputar lock com esta escrita (no Windows,
        um leitor com o arquivo aberto pode travar o os.replace() de quem
        escreve, mesmo com escrita atomica). Escrita atomica dentro de cada
        arquivo: vai pra um .tmp primeiro e so troca de nome no final — se o
        processo cair no meio do flush, o arquivo anterior daquele lado fica
        intacto."""
        if not self._sujo:
            return
        registros = [
            {
                "broker": linha["broker"],
                "symbol": linha["symbol"],
                "time": linha["time"].isoformat(),
                "last": linha["last"],
                "session_close": linha["session_close"],
            }
            for linha in self.estado_atual.values()
        ]

        alvo = self.output_path_a if self._proximo_arquivo == "a" else self.output_path_b
        tmp_path = alvo + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(registros, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, alvo)
        self._proximo_arquivo = "b" if self._proximo_arquivo == "a" else "a"

        print(f"[{self.broker}] tabela atualizada ({len(registros)} symbols) -> {os.path.basename(alvo)}")
        self._sujo = False

    def executar(self):
        self.conectar()
        print(f"[{self.broker}] last_int rodando (Ctrl+C pra parar)")

        try:
            while not os.path.exists(self.stop_flag_path):
                try:
                    self._varrer()
                except Exception as exc:  # nunca deixa um erro transiente matar o coletor 24/7
                    print(f"[{self.broker}] erro na varredura, seguindo pro proximo ciclo: {exc}")
                try:
                    self._flush()  # flush a cada volta — o guard _sujo torna isso barato quando nada mudou
                except Exception as exc:
                    print(f"[{self.broker}] erro no flush, tentando de novo no proximo ciclo: {exc}")
                time.sleep(PAUSA_LOOP)
            print(f"[{self.broker}] sinal de parada recebido")
        except KeyboardInterrupt:
            print(f"[{self.broker}] Ctrl+C recebido")
        finally:
            self._flush()
            mt5.shutdown()


if __name__ == "__main__":
    ColetorLastInt().executar()
