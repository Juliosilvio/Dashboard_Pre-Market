"""
Nome do script : main.py
Descricao      : Controlador unico do projeto — e o unico script que se roda
                  na mao, e nunca para sozinho (Ctrl+C pra encerrar). Sobe
                  duas frentes em paralelo:

                  Frente 1 (tempo real, continua): logo no inicio, sobe
                  cinco processos dedicados — last_nac.py (preco, corretora nacional) e
                  last_int.py (preco, corretora internacional), grudados no console do
                  main.py (decisao original, mantida), yeldcurve.py (curva
                  de juros dos treasurys americanos, le
                  excel/treasurys/yeldcurve.xlsx a cada 5min — tambem
                  grudado no console do main.py, mesmo espirito de
                  last_nac.py/last_int.py — ver yeldcurve.md pro racional
                  completo e pro requisito de manter o Excel aberto com o
                  Power Query atualizando), last_indicadores_nac.py
                  (IFR/ATR/MACD de Indice/Dolar, lendo direto dos parquets da
                  MTF — sem conexao MT5 propria — pra nao esperar a fila do
                  indicadores_mtf.py recalcular os outros ~1000 arquivos
                  antes de chegar em Indice/Dolar) e vies_direcional.py (cruza
                  os indicadores MTF de todo o universo correlacionado com
                  o peso/sinal do correl.py pra apurar o vies direcional de
                  Indice/Dolar, mais o refinamento de entrada via IFR M1/M5 em
                  tempo real — pedido do usuario 2026-09-21, ver docstring
                  do proprio script), os dois ultimos numa JANELA DE
                  CONSOLE PROPRIA cada (CREATE_NEW_CONSOLE, igual
                  api_server.py/frontend — pedido do usuario 2026-09-20
                  "certos scripts tem que ter seu proprio terminal" /
                  "Terminal proprio, separado de tudo"; esclarecido
                  2026-09-21: e janela de console/PowerShell, nao terminal
                  MT5 — nenhum dos dois conecta no MT5). Cada um so faz uma
                  coisa, girando sozinho, em ritmo proprio, sem esperar o
                  resto do pipeline. O preco (last_nac.py/last_int.py) usa
                  conexao MT5 DEDICADA (terminal MT5 de verdade —
                  connections["corretora_nacional_tempo_real"]/["corretora internacional_tempo_real"]
                  no config.json) porque senao grudava no mesmo
                  terminal64.exe que vigente.py/grade.py/nac.py/int.py usam
                  (mesmo path/login/server = mesmo terminal, e assim que o
                  MT5 funciona) e travava atras do backfill pesado deles —
                  bug real do antigo tempo_real.py, que os dois substituem.

                  Frente 2 (pipeline em lote, em loop): roda, em ordem,
                  (vigente.py + dadosgov.py em paralelo) -> grade.py ->
                  historico.py -> verificar_frescor_cotacoes.py ->
                  alinhar_d1.py -> (flat_mtf.py +
                  curva_juros.py em paralelo) -> retorno.py ->
                  taxa_usatb.py -> (correl.py + descorrel.py em paralelo)
                  -> indicadores_mtf.py. dadosgov.py (2026-09-21) coleta a
                  Selic (API publica do Banco Central, fora do MT5) de
                  forma incremental — nao depende de nada do resto do
                  pipeline, por isso roda em paralelo com o vigente.py sem
                  risco. curva_juros.py (novo, 2026-09-21) monta o indice
                  de juros de prazo constante (DI 1 ano/2 anos, curva
                  inteira do DI1) e compara com a Selic — depende so do
                  D1 do DI1 (ja pronto depois do alinhar_d1.py) e da Selic
                  (dadosgov.py, que ja rodou no inicio do lote), por isso
                  entra em paralelo com o flat_mtf.py sem risco.

                  Consolidacao 2026-09-21 (pedido do usuario: "isso e o que
                  precisamos: serie historica em MTF e preco em tempo real,
                  de forma centralizada, pra nao errar mais"): ate a versao
                  3.9.1, existiam DOIS pipelines de coleta independentes
                  buscando D1/M5 do MESMO MT5 pros MESMOS ativos —
                  nac.py/nac_m5.py (corretora nacional) e int.py/int_m5.py (corretora internacional)
                  alimentavam historico_d1.parquet/historico_m5.parquet
                  direto; historico.py buscava tudo de novo (D1/M5
                  inclusive) pra dentro da MTF. Isso ja causou uma
                  divergencia real (a correcao do alinhar_d1.py so tinha
                  sido aplicada numa das duas copias). Agora historico.py e
                  a UNICA coleta (atualiza a pasta de estudo MTF — todos os
                  ~35 ativos/vencimentos, 8 timeframes cada); nac.py/
                  nac_m5.py/int.py/int_m5.py saem do pipeline e foram
                  EXCLUIDOS do projeto (2026-09-21, pedido do usuario —
                  "se tiverem sem uso e melhor excluir"; changelog de cada
                  um continua em scripts_py/versoes/ como registro).
                  alinhar_d1.py (2.0.0) corrige o D1 da corretora internacional DENTRO
                  da propria MTF (resample do m5.parquet de cada alvo,
                  agrupado por dia calendario UTC — mesmo raciocinio de
                  sempre, so que a fonte e o destino mudaram de
                  historico_d1/m5.parquet pra MTF). flat_mtf.py (novo) DERIVA
                  historico_d1.parquet/historico_m5.parquet a partir da MTF
                  ja corrigida — mesmo formato, mesmo caminho de sempre, pra
                  retorno.py/taxa_usatb.py (os dois unicos consumidores
                  diretos) continuarem funcionando sem nenhuma mudanca.
                  Validado: retorno/correlacao/descorrelacao batem
                  identicos ao pipeline antigo pros mesmos ativos (unica
                  diferenca e a profundidade do M5, que caiu de ~360 pra
                  ~90 dias — a profundidade padrao de primeira coleta do
                  historico.py; nao mudou nenhum resultado porque as
                  janelas de rolagem usadas, 20 e 100, sao bem menores que
                  isso. Da pra aumentar mudando DIAS_HISTORICO em
                  historico.py se quiser mais profundidade).

                  indicadores_mtf.py recalcula IFR/ATR/MACD em cima da MTF
                  logo apos ela ser atualizada. Recalculo do indicador fica
                  amarrado ao ritmo do loop (sincronizado pelo M5, ver
                  _aguardar_novo_m5) — pra M1 fresco a cada minuto de
                  verdade, sem esperar a volta do lote inteiro, ver
                  last_indicadores_nac.py (frente 1). taxa_usatb.py converte
                  o preco do UsaTB (T-Bill futures, corretora internacional) pra taxa de
                  juros implicita (100 - preco), pro comparativo BR x EUA
                  (pedido do usuario 2026-09-19). scan_ativos.py saiu do
                  pipeline: seu papel (gravar quem esta visivel em
                  parquet/ativos.parquet) ficou orfao desde que
                  nac.py/nac_m5.py/int.py/int_m5.py passaram a ler o visivel
                  direto do MT5 (mt5.symbols_get()) — e agora nem roda mais.
                  Ao fim de uma volta, NAO dorme um tempo fixo — fica
                  checando o candle M5 mais recente de um
                  ativo de referencia em cada corretora (REF_CORRETORA_NACIONAL na corretora nacional,
                  REF_corretora internacional na corretora internacional) e comeca a proxima volta
                  assim que QUALQUER UM dos dois ja tiver um candle M5 mais
                  novo que o da volta anterior (CORRIGIDO 2026-09-29, ver
                  4.10.0 abaixo — antes exigia os DOIS, e travava o pipeline
                  inteiro sempre que um dos mercados estava fechado). Como o
                  timestamp do candle e epoch (absoluto), essa checagem
                  sincroniza as duas corretoras pelo dado real, sem depender
                  do fuso de servidor de cada uma (que sao diferentes entre
                  corretora nacional e corretora internacional).

                  Frente 3 (api_server.py, tambem continua): sobe junto com
                  last_nac.py/last_int.py a ponte HTTP local (FastAPI,
                  http://localhost:8000) que o frontend React le. Ao
                  contrario dos last_*, sobe numa JANELA DE CONSOLE PROPRIA
                  (subprocess.CREATE_NEW_CONSOLE) — util acompanhar o log do
                  uvicorn (cada request) separado do log do pipeline em
                  lote. Nao precisa de arquivo-sinal de parada feito nem
                  encerramento gracioso: nao guarda nenhum buffer em memoria
                  que precise ser salvo antes de sair (cada request le o
                  arquivo do disco na hora), entao um terminate() simples ao
                  encerrar o main.py e suficiente.

                  Frente 4 (frontend React, tambem continua): pedido do
                  usuario ("pede pro main.py ja ligar o servidor frontend")
                  — antes disso, depois de rodar main.py o usuario ainda
                  precisava abrir um segundo terminal e rodar 'npm run dev'
                  na mao dentro de frontend/ pra acessar
                  http://localhost:5173 (esquecer esse passo dava
                  ERR_CONNECTION_REFUSED no navegador, com o resto do
                  pipeline rodando normal). Sobe 'npm run dev' (Vite) numa
                  JANELA DE CONSOLE PROPRIA, igual o api_server.py. Detalhe
                  do Windows: 'npm' e um arquivo .cmd (nao um .exe), entao
                  rodar via shell=True sobe um cmd.exe intermediario que so
                  DEPOIS sobe o processo de verdade do Vite (node.exe) como
                  FILHO desse cmd — por isso a parada usa taskkill /T
                  (arvore inteira), nao terminate() (que mataria so o
                  cmd.exe de fora e deixaria o Vite orfao segurando a porta
                  5173, quebrando o proximo 'npm run dev').

                  Ao encerrar (Ctrl+C), cria o arquivo-sinal
                  parquet/historicos/_stop_last.flag pros dois processos
                  (last_nac.py/last_int.py) pararem de forma limpa (gravando
                  o buffer deles antes de sair) — terminate() no Windows
                  mataria os processos sem chance de rodar esse flush. O
                  api_server.py (frente 3) e so terminate()ado direto, pelo
                  motivo explicado acima; o frontend (frente 4) usa
                  taskkill /T, tambem explicado acima. A checagem do candle
                  M5 (_aguardar_novo_m5) so reconecta em quem ainda nao
                  avancou, a cada PAUSA_CHECAGEM_M5 (30s) — com backoff por
                  lado desde a 4.10.0, ver nota abaixo — reduzindo a
                  reconexao no terminal compartilhado (que last_nac.py/
                  last_int.py tambem usam enquanto a conexao dedicada deles
                  nao estiver configurada).

                  4.9.0 (2026-09-27): terceiro terminal MT5 (mt5stock, ver
                  connections.mt5stock no config.json) agora abre
                  AUTOMATICO tambem, logo no inicio de executar() -
                  _garantir_mt5stock_aberto() so garante que o executavel
                  esta rodando (os.startfile() se nao estiver), NUNCA
                  chama mt5.initialize() nele (a API Python trava com "-3
                  Out of memory" nesse terminal especifico, ver nota 1.3.0
                  do historico.py) - quem alimenta o dado de la e o Service
                  nativo ExportadorMt5Stock.mq5, rodando dentro do proprio
                  terminal assim que ele abre (ainda precisa ser iniciado
                  manualmente uma vez em Navegador > Servicos, isso o
                  Python nao alcanca de fora).

                  4.10.0 (2026-09-29): _aguardar_novo_m5 exigia candle M5
                  novo dos DOIS lados (corretora nacional e corretora internacional) pra liberar a
                  proxima volta do lote — em producao, isso travou o
                  pipeline inteiro (inclusive o lado internacional, que
                  continuava tendo candle novo normalmente) enquanto o
                  mercado nacional (B3/corretora nacional) estava fechado, e o log
                  mostrou reconexao repetida (mt5.initialize com login
                  completo) a cada 30s por um bom tempo, terminando em
                  '[corretora nacional] falha ao conectar: (-6, Authorization failed)' —
                  suspeita forte de relogin excessivo sendo tratado como
                  abuso pelo servidor da corretora. Pedido do usuario: "a
                  gente deveria montar uma logica que enquanto nao
                  aparecesse candle novo usasse o ultimo cotado, quando
                  aparecesse o novo usa ele" — em vez de exigir os DOIS,
                  agora libera assim que QUALQUER UM dos dois avanca; o
                  lado que nao avancou so carrega o 'ultimo' de antes pra
                  proxima comparacao (nenhum dado se perde — no candle
                  real seguinte desse lado, a diferenca e detectada
                  normalmente). Reconexao tambem ganhou backoff
                  independente por lado (PAUSA_CHECAGEM_M5_MAX,
                  FALHAS_PRA_DOBRAR): apos tentativas seguidas sem avancar,
                  o intervalo DAQUELE lado dobra (ate o teto de 5min) sem
                  afetar o ritmo do outro lado — evita martelar login por
                  horas no mercado fechado (fim de semana com os dois
                  fechados e o caso que mais se beneficia disso).
Autor          : Julio Cesar Silvio Campanhola
Criado em      : 2026-09-13
Ultima edicao  : 2026-10-01
Versao         : 4.12.0
Projeto        : dashboard
Historico      : scripts_py/versoes/main.md
"""

import importlib
import json
import os
import subprocess
import sys
import time

try:
    mt5 = importlib.import_module("MetaTrader5")
except ImportError as exc:
    raise ImportError(
        "A dependencia MetaTrader5 nao esta instalada. "
        "Instale-a com: pip install MetaTrader5"
    ) from exc
try:
    pd = importlib.import_module("pandas")
except ImportError as exc:
    raise ImportError(
        "A dependencia pandas nao esta instalada. "
        "Instale-a com: pip install pandas pyarrow"
    ) from exc
try:
    psutil = importlib.import_module("psutil")
except ImportError as exc:
    raise ImportError(
        "A dependencia psutil nao esta instalada. "
        "Instale-a com: pip install psutil"
    ) from exc

# ativos de referencia pra sincronizar o loop do lote pelo fechamento do M5 —
# Indice ja e o alvo do projeto na corretora nacional; EURUSD negocia quase 24/5 na
# corretora internacional, entao sempre tem candle M5 fresco pra comparar
REF_CORRETORA_NACIONAL = "Indice"
REF_corretora internacional = "EURUSD"
PAUSA_CHECAGEM_M5 = 30       # segundos entre cada checagem de candle novo, enquanto espera
PAUSA_CHECAGEM_M5_MAX = 300  # teto do backoff (5min) pro lado que nao avanca ha muito tempo (mercado fechado)
FALHAS_PRA_DOBRAR = 3        # a cada N tentativas seguidas sem avancar, dobra o intervalo DESSE lado (ate o teto)


class Orquestrador:
    """Controlador unico: sobe last_nac.py/last_int.py (preco continuo), yeldcurve.py (curva de juros dos treasurys, le o xlsx do Excel), last_indicadores_nac.py (indicadores continuos de Indice/Dolar), dp.py (projecao de desvios de preco MACD/ATR/IFR, MTF), noticias.py (manchetes em tempo real do canal fonte de noticias), vies_direcional.py (vies direcional + refinamento de entrada) amplitude.py (amplitude de mercado, advance/decline + novas maximas/minimas, universos em config.json -> amplitude_universos) e magnificas.py (cotacao + variacao intradiaria das 7 magnificas pra grade de cotacoes, lendo o parquet que o mt5stock ja alimenta), e roda o pipeline em lote em loop, sincronizado pelo M5."""

    def __init__(self, base_dir=None):
        self.base_dir = base_dir or os.path.dirname(os.path.abspath(__file__))
        self.config_path = os.path.join(self.base_dir, "..", "json", "config.json")
        historicos = os.path.join(self.base_dir, "..", "parquet", "historicos")

        self.stop_flag_path = os.path.join(historicos, "_stop_last.flag")

        # frontend/ e IRMA de backend/ (nao filha) — self.base_dir e
        # backend/scripts_py, entao sobe dois niveis (-> backend -> raiz do
        # projeto) antes de descer em frontend/
        self.frontend_dir = os.path.join(self.base_dir, "..", "..", "frontend")

        self._conexoes = {}
        self.proc_last = []
        self.proc_api = None
        self.proc_frontend = None

    # ---------- conexao MT5 (so pra checar o candle M5 de referencia) ----------

    def _carregar_conexao(self, broker):
        if broker not in self._conexoes:
            with open(self.config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
            self._conexoes[broker] = config["connections"][broker]
        return self._conexoes[broker]

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

    def _garantir_mt5stock_aberto(self):
        """Abre so o EXECUTAVEL do terminal mt5stock (config.json ->
        connections.mt5stock) se ainda nao estiver rodando - pedido do
        usuario 2026-09-27 ("se tem mais um terminal e ele alimenta o
        projeto tambem, entao obviamente que ele tem que ligar
        automatico"). NUNCA chama mt5.initialize() aqui (diferente de
        corretora nacional/corretora internacional em _hora_ultimo_m5 acima) - a API Python pra esse
        terminal especifico tem o bug de "-3 Out of memory" isolado em
        diag_symbol_select_mt5stock.py (ver nota 1.3.0 do historico.py), o
        Service nativo ExportadorMt5Stock.mq5 e quem exporta o dado (via
        Common\Files\mt5stock_export\), rodando dentro do proprio terminal
        assim que ele abre. Chamado uma vez, no inicio de executar() - so
        garante que a janela existe, nao fica reconectando feito
        _hora_ultimo_m5."""
        conexao = self._carregar_conexao("mt5stock")
        if self._terminal_esta_aberto(conexao["path"]):
            return
        print("[mt5stock] terminal fechado, abrindo automaticamente...")
        self._garantir_terminal_aberto(conexao["path"])
        print("[mt5stock] terminal aberto - confira se o Service "
              "ExportadorMt5Stock esta rodando (Navegador > Servicos)")

    def _hora_ultimo_m5(self, broker, symbol):
        """Timestamp (epoch, absoluto) do candle M5 mais recente do symbol nessa corretora."""
        conexao = self._carregar_conexao(broker)
        self._garantir_terminal_aberto(conexao["path"])
        ok = mt5.initialize(
            path=conexao["path"],
            login=conexao["login"],
            password=conexao["password"],
            server=conexao["server"],
        )
        if not ok:
            print(f"[{broker}] falha ao conectar pra checar M5: {mt5.last_error()}")
            return None

        mt5.symbol_select(symbol, True)
        rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M5, 0, 1)
        mt5.shutdown()

        if rates is None or len(rates) == 0:
            return None
        return int(rates[0]["time"])

    def _aguardar_novo_m5(self, ultimo_indice, ultimo_eur):
        """Libera a proxima volta do lote assim que QUALQUER UM dos dois (Indice
        na corretora nacional OU EURUSD na corretora internacional) tiver candle M5 mais novo que o da
        volta anterior — nao precisa mais dos DOIS ao mesmo tempo. CORRIGIDO
        (4.10.0, 2026-09-29, pedido do usuario — ver nota no cabecalho do
        modulo): a versao anterior exigia os dois, e travava o pipeline
        INTEIRO (inclusive o lado internacional, que continuava tendo candle
        novo) sempre que o mercado nacional (B3/corretora nacional) estava fechado. O lado
        que ainda nao avancou simplesmente carrega o "ultimo" de antes pra
        proxima comparacao — nenhum dado se perde: no proximo candle real
        dele, seja quando for, a comparacao detecta a diferenca normalmente e
        libera nessa hora.

        Backoff por lado (mesmo pedido, causa raiz): reconectar com login
        completo (mt5.initialize) a cada PAUSA_CHECAGEM_M5 (30s), por HORAS a
        fio enquanto um mercado esta fechado, e a suspeita numero um do
        "[corretora nacional] falha ao conectar: (-6, Authorization failed)" visto em
        producao (relogin excessivo tende a ser tratado como abuso pelo
        servidor da corretora). Cada lado tem seu proprio contador de
        falhas: depois de FALHAS_PRA_DOBRAR tentativas seguidas sem avancar,
        o intervalo DAQUELE lado dobra (o outro lado nao e afetado), ate o
        teto de PAUSA_CHECAGEM_M5_MAX — o lado aberto continua no ritmo
        normal, o lado fechado vai reconectando cada vez mais devagar em vez
        de martelar o login por horas (fim de semana, com os dois mercados
        fechados, e o caso que mais se beneficia disso)."""
        hora_indice_final = ultimo_indice
        hora_eur_final = ultimo_eur
        intervalo_indice = PAUSA_CHECAGEM_M5
        intervalo_eur = PAUSA_CHECAGEM_M5
        falhas_indice = 0
        falhas_eur = 0
        proxima_indice = 0.0
        proxima_eur = 0.0

        while True:
            agora = time.monotonic()

            if agora >= proxima_indice:
                hora_indice = self._hora_ultimo_m5("corretora nacional", REF_CORRETORA_NACIONAL)
                if hora_indice is not None and hora_indice > ultimo_indice:
                    return hora_indice, hora_eur_final
                falhas_indice += 1
                if falhas_indice % FALHAS_PRA_DOBRAR == 0:
                    intervalo_indice = min(intervalo_indice * 2, PAUSA_CHECAGEM_M5_MAX)
                proxima_indice = time.monotonic() + intervalo_indice

            if agora >= proxima_eur:
                hora_eur = self._hora_ultimo_m5("corretora internacional", REF_corretora internacional)
                if hora_eur is not None and hora_eur > ultimo_eur:
                    return hora_indice_final, hora_eur
                falhas_eur += 1
                if falhas_eur % FALHAS_PRA_DOBRAR == 0:
                    intervalo_eur = min(intervalo_eur * 2, PAUSA_CHECAGEM_M5_MAX)
                proxima_eur = time.monotonic() + intervalo_eur

            agora = time.monotonic()
            print(f"aguardando candle M5 novo — corretora nacional/{REF_CORRETORA_NACIONAL}: esperando "
                  f"(proxima checagem em {max(0, int(proxima_indice - agora))}s), "
                  f"corretora internacional/{REF_corretora internacional}: esperando "
                  f"(proxima checagem em {max(0, int(proxima_eur - agora))}s)")
            time.sleep(min(intervalo_indice, intervalo_eur, PAUSA_CHECAGEM_M5))

    # ---------- frente 1: preco em tempo real (continuo) ----------

    def _iniciar_last(self):
        """Sobe os processos dedicados — last_nac.py e last_int.py
        (preco continuo, console compartilhado com o main.py),
        yeldcurve.py (curva de juros dos treasurys, tambem console
        compartilhado — baixo volume de log, uma leitura a cada 5min),
        last_indicadores_nac.py (IFR/ATR/MACD de Indice/Dolar, lendo direto da
        MTF, janela de console PROPRIA), dp.py (projecao de desvios,
        janela propria), noticias.py (manchetes, janela propria),
        vies_direcional.py (vies direcional + refinamento de entrada,
        janela de console PROPRIA), amplitude.py (amplitude de mercado,
        janela propria, 2026-09-26 — so calcula algo depois que
        historico.py coletar as raizes de config.json ->
        amplitude_universos) e magnificas.py (cotacao + variacao
        intradiaria das 7 magnificas — Apple/Microsoft/Alphabet/Amazon/
        Nvidia/Meta/Tesla — pra grade de cotacoes do frontend, janela
        propria, 2026-09-26 — le o mesmo parquet de MTF que amplitude.py/
        dp.py, SEM conexao MT5 nova pro mt5stock, ver docstring do
        magnificas.py pro motivo) e sentimento_em.py (cotacao + variacao
        intradiaria de EWZ/EEM, mesmo padrao/motivo de magnificas.py,
        janela propria, 2026-09-29 — pedido do usuario, ver historico.py
        1.4.0) — rodando sozinhos, em paralelo com o resto do pipeline, ate o
        main.py parar. Cada um so faz uma coisa (ver docstring de cada
        um). yeldcurve.py exige o Excel aberto com
        excel/treasurys/yeldcurve.xlsx e o Power Query atualizando — se
        nao estiver, o proprio script avisa sozinho (nao derruba o
        main.py)."""
        if os.path.exists(self.stop_flag_path):
            os.remove(self.stop_flag_path)  # sinal de uma parada anterior, nao vale mais

        # last_nac.py/last_int.py/yeldcurve.py continuam grudados no
        # console do main.py (decisao original, mantida — nao precisam de
        # log separado). Ja last_indicadores_nac.py e vies_direcional.py
        # ganham JANELA DE CONSOLE PROPRIA cada um, igual
        # api_server.py/frontend — pedido do usuario 2026-09-20 ("certos
        # scripts tem que ter seu proprio terminal" / "Terminal proprio,
        # separado de tudo"; esclarecido 2026-09-21: janela de console,
        # nao terminal MT5 — nenhum dos dois conecta no MT5).
        flags_indicadores = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
        self.proc_last = [
            subprocess.Popen([sys.executable, os.path.join(self.base_dir, "last_nac.py")], cwd=self.base_dir),
            subprocess.Popen([sys.executable, os.path.join(self.base_dir, "last_int.py")], cwd=self.base_dir),
            subprocess.Popen([sys.executable, os.path.join(self.base_dir, "yeldcurve.py")], cwd=self.base_dir),
            subprocess.Popen([sys.executable, os.path.join(self.base_dir, "last_indicadores_nac.py")],
                              cwd=self.base_dir, creationflags=flags_indicadores),
            subprocess.Popen([sys.executable, os.path.join(self.base_dir, "dp.py")],
                              cwd=self.base_dir, creationflags=flags_indicadores),
            subprocess.Popen([sys.executable, os.path.join(self.base_dir, "noticias.py")],
                              cwd=self.base_dir, creationflags=flags_indicadores),
            subprocess.Popen([sys.executable, os.path.join(self.base_dir, "vies_direcional.py")],
                              cwd=self.base_dir, creationflags=flags_indicadores),
            subprocess.Popen([sys.executable, os.path.join(self.base_dir, "amplitude.py")],
                              cwd=self.base_dir, creationflags=flags_indicadores),
            subprocess.Popen([sys.executable, os.path.join(self.base_dir, "magnificas.py")],
                              cwd=self.base_dir, creationflags=flags_indicadores),
            subprocess.Popen([sys.executable, os.path.join(self.base_dir, "sentimento_em.py")],
                              cwd=self.base_dir, creationflags=flags_indicadores),
        ]

    def _parar_last(self):
        """Cria o arquivo-sinal (terminate() no Windows mataria os processos sem
        chance de gravar o buffer deles) e espera os dois encerrarem sozinhos."""
        if not self.proc_last:
            return
        open(self.stop_flag_path, "w", encoding="utf-8").close()
        for p in self.proc_last:
            try:
                p.wait(timeout=30)
            except subprocess.TimeoutExpired:
                print("last_nac.py/last_int.py/yeldcurve.py/last_indicadores_nac.py/dp.py/noticias.py/vies_direcional.py/amplitude.py/magnificas.py/sentimento_em.py nao respondeu ao sinal de parada a tempo, encerrando a forca")
                p.terminate()
        if os.path.exists(self.stop_flag_path):
            os.remove(self.stop_flag_path)

    # ---------- frente 2: pipeline em lote ----------

    def _rodar(self, *scripts):
        """Roda um ou mais scripts em paralelo (processos separados) e espera todos terminarem."""
        procs = [subprocess.Popen([sys.executable, os.path.join(self.base_dir, s)], cwd=self.base_dir)
                 for s in scripts]
        for p in procs:
            p.wait()
        for p, s in zip(procs, scripts):
            if p.returncode != 0:
                print(f"aviso: {s} terminou com codigo {p.returncode}")

    def _rodar_lote(self):
        """Uma volta inteira do pipeline em lote, na ordem definida.
        Consolidacao 2026-09-21: historico.py e a UNICA coleta (MTF);
        alinhar_d1.py corrige o D1 da corretora internacional dentro dela; flat_mtf.py
        deriva historico_d1/m5.parquet da MTF pra retorno.py/taxa_usatb.py
        continuarem funcionando sem mudanca nenhuma."""
        self._rodar("vigente.py", "dadosgov.py")
        self._rodar("grade.py")

        self._rodar("historico.py")
        self._rodar("verificar_frescor_cotacoes.py")
        self._rodar("alinhar_d1.py")
        self._rodar("flat_mtf.py", "curva_juros.py")

        self._rodar("retorno.py")
        self._rodar("taxa_usatb.py")
        self._rodar("correl.py", "descorrel.py")

        self._rodar("indicadores_mtf.py")

        # TESTE 2026-09-24 (pedido do usuario): historico.py seleciona no MT5
        # (symbol_select True) TODOS os meses de vigentes[raiz] de
        # vencimento_americano (ex.: BrentSep26/Nov26/Dec26) pra buscar o
        # historico de cada um — isso e proposital, ele PRECISA continuar
        # puxando esses meses (nao mexer nisso). O problema e que ele nunca
        # desseleciona depois, entao a grade de cotacao (que so quer o
        # vigente) volta a mostrar os meses extras. Rodando grade.py de novo
        # aqui, no fim da volta, ele reaplica a lista desejada (lista_desejada
        # em grade.py) e tira do Market Watch o que nao devia estar visivel —
        # sem tocar em nada que historico.py ja coletou. E teste: se
        # funcionar, decidir se fica assim ou se o certo e historico.py
        # desselecionar sozinho ao terminar de usar cada ticker extra.
        self._rodar("grade.py")

    # ---------- frente 3: api_server.py (ponte HTTP pro frontend) ----------

    def _iniciar_api_server(self):
        """Sobe o api_server.py (FastAPI, http://localhost:8000) numa janela
        de console PROPRIA — diferente de last_nac.py/last_int.py, que
        rodam grudados no console do main.py, aqui vale a pena separar pra
        acompanhar o log do uvicorn (uma linha por request) sem misturar
        com o log do pipeline em lote."""
        flags = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
        self.proc_api = subprocess.Popen(
            [sys.executable, os.path.join(self.base_dir, "api_server.py")],
            cwd=self.base_dir,
            creationflags=flags,
        )

    def _parar_api_server(self):
        """Sem arquivo-sinal aqui: o api_server.py nao guarda buffer nenhum
        em memoria (le o disco a cada request), entao nao ha nada pra
        perder num terminate() direto — diferente do _parar_last()."""
        if self.proc_api is None:
            return
        self.proc_api.terminate()
        try:
            self.proc_api.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.proc_api.kill()

    # ---------- frente 4: frontend React (npm run dev / Vite) ----------

    def _iniciar_frontend(self):
        """Sobe 'npm run dev' (Vite, http://localhost:5173) numa janela de
        console PROPRIA, igual o api_server.py — precisa ficar visivel pro
        usuario acompanhar o log do Vite (porta, erro de build) separado do
        resto. Pedido do usuario: "pede pro main.py ja ligar o servidor
        frontend" — antes disso, esquecer de rodar 'npm run dev' na mao
        depois do main.py dava ERR_CONNECTION_REFUSED no navegador. shell=True
        e necessario porque 'npm' e um .cmd no Windows, nao um .exe — ver
        docstring do modulo pro motivo de a parada usar taskkill /T em vez
        de terminate()."""
        flags = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
        self.proc_frontend = subprocess.Popen(
            "npm run dev",
            cwd=self.frontend_dir,
            shell=True,
            creationflags=flags,
        )

    def _parar_frontend(self):
        """terminate() so mataria o cmd.exe que interpreta o 'npm' (.cmd),
        deixando o Vite (node.exe) orfao segurando a porta 5173 — por isso
        taskkill /F /T (arvore inteira a partir do PID) em vez de
        proc.terminate(). capture_output=True so pra nao poluir o console
        do main.py com a saida do taskkill (sucesso ou 'processo ja
        encerrado', nenhum dos dois interessa aqui)."""
        if self.proc_frontend is None:
            return
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(self.proc_frontend.pid)],
            capture_output=True,
        )

    def executar(self):
        self._garantir_mt5stock_aberto()
        self._iniciar_last()
        self._iniciar_api_server()
        self._iniciar_frontend()
        try:
            ultimo_indice = self._hora_ultimo_m5("corretora nacional", REF_CORRETORA_NACIONAL) or 0
            ultimo_eur = self._hora_ultimo_m5("corretora internacional", REF_corretora internacional) or 0

            while True:
                print("=== nova volta do pipeline em lote ===")
                self._rodar_lote()
                ultimo_indice, ultimo_eur = self._aguardar_novo_m5(ultimo_indice, ultimo_eur)
        except KeyboardInterrupt:
            print("Ctrl+C recebido, encerrando...")
        finally:
            self._parar_last()
            self._parar_api_server()
            self._parar_frontend()


if __name__ == "__main__":
    Orquestrador().executar()
