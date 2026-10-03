"""
Nome do script : historico.py
Descricao      : Coleta os 8 timeframes de estudo MTF (M1, M5, M15, M30, H1,
                  H4, D1, W1) de cada ativo definido em json/config.json e
                  salva em parquet/historicos/MTF/<ativo>[/<mes-ano>]/<tf>.parquet.
                  Ativos com vencimento (curva_br da corretora nacional e
                  vencimento_americano da corretora internacional) tem uma subpasta por
                  vigente atual, criada automaticamente quando aparece um
                  vigente novo (rolagem de contrato na corretora internacional ou nova
                  ponta de vencimento entrando na curva na corretora nacional) - durante
                  uma janela de rolagem com dois vigentes simultaneos, as
                  duas subpastas ficam ativas ao mesmo tempo. Ativo sem
                  vencimento (nacionais, indices/moedas/commodities
                  continuos) salva direto na pasta raiz do ativo, sem
                  subpasta.
                  Roda de forma incremental: consulta
                  parquet/historicos/MTF/controle_atualizacao_mtf.parquet pra
                  saber a data da ultima atualizacao ja salva de cada
                  ativo+timeframe, busca no MT5 so o que falta a partir
                  dali (ou usa a profundidade padrao definida em
                  TIMEFRAMES na primeira coleta), funde no parquet do TF
                  (sem duplicar candle) e registra uma linha nova no
                  controle com a data e o preco de fechamento da
                  atualizacao - o controle nunca sobrescreve linha antiga,
                  so acrescenta embaixo.
                  M1/M15/M30/H1/H4/W1 nao existem nos parquets grandes do
                  pipeline principal (historico_d1/m5 so tem D1 e M5), entao
                  esses TFs sao sempre buscados direto no MT5, nunca
                  reaproveitados de outro parquet. Por isso, assim como
                  int.py/nac.py, so roda no Windows com o MT5 aberto.
                  NAO e standalone: e chamado automaticamente pelo
                  main.py (Orquestrador._rodar_lote()) a cada volta do
                  lote, como a unica coleta MTF (consolidacao
                  2026-09-21, ver nota da versao 1.4.0 abaixo). Comentario
                  antigo corrigido em 2026-09-29 - estava desatualizado e
                  levou a uma informacao errada passada ao usuario.
                  Flag opcional --reforcar TF:DIAS forca, so nessa rodada e so
                  pro TF indicado, uma busca mais profunda pra tras (ignorando
                  o incremental so ali) - usado pra alongar a amostra de um TF
                  especifico (ex: M5) sem afetar os demais nem duplicar candle
                  (merge existente ja deduplica por time). Repetir a flag pra
                  reforcar mais de um TF na mesma rodada.

                  1.2.0 (2026-09-26): terceiro broker - config.json ->
                  connections.mt5stock (terminal novo, instalado direto do
                  MQL5, servidor MetaQuotes-Demo). Dois grupos novos em
                  BROKER_POR_GRUPO, sem vencimento (ticker == raiz, igual
                  indices_continuo): "acoes_nasdaq100" (as 100 acoes do
                  indice Nasdaq-100, confirmadas uma a uma contra o catalogo
                  do mt5stock via verificar_mt5stock.py - EA/Electronic Arts
                  ficou de fora por nao existir mais nesse catalogo,
                  provavel efeito do fechamento de capital da empresa em
                  2026) e "treasury_etf_eua" (TLT/IEF/SHY - proxies de
                  juro longo/medio/curto americano, ja que esse terminal nao
                  tem contrato futuro de treasury direto, so ETF).

                  1.3.0 (2026-09-26): o terminal mt5stock (build 6230) tem um
                  bug reproduzido e isolado com diag_symbol_select_mt5stock.py
                  - qualquer symbol_select()/copy_rates_range() chamado pela
                  API Python externa devolve last_error=(-3, "Terminal: Out
                  of memory"), mesmo com o simbolo ja selecionado e com
                  cotacao valida (descartadas as hipoteses de Market Watch
                  cheio, elevacao/administrador do processo e versao do
                  pacote MetaTrader5 do pip, ja na mais nova). Contorno:
                  Service nativo dentro do proprio terminal
                  (backend/Claude outputs/ExportadorMt5Stock.mq5) exporta os
                  mesmos 8 TFs de todas as raizes de acoes_nasdaq100 e
                  treasury_etf_eua pra CSV em Common\Files\mt5stock_export\
                  <raiz>\<tf>.csv, formato identico ao que
                  mt5.copy_rates_range() devolveria (mesmos nomes de campo do
                  MqlRates). coletar_alvo_via_csv() le esse CSV em vez de
                  conectar no MT5 - broker "mt5stock" no executar() nao
                  chama mais conectar()/desconectar(), so essa rota nova.

                  1.4.0 (2026-09-29): novo grupo "etfs_sentimento_em"
                  (EWZ/EEM) em BROKER_POR_GRUPO/ORDEM_GRUPOS, mesmo padrao
                  de treasury_etf_eua (ETF a vista, sem vencimento,
                  catalogo mt5stock, rota coletar_alvo_via_csv). Pedido do
                  usuario 2026-09-29: "colocar o EWZ no Risk indice" -
                  EWZ (iShares MSCI Brazil) e EEM (iShares MSCI Emerging
                  Markets) como proxy de sentimento de risco Brasil/
                  emergentes fora do horario nacional. RAIZES[] do
                  ExportadorMt5Stock.mq5 (backend/Claude outputs/) tambem
                  atualizado - precisa recompilar no MetaEditor e
                  reiniciar o Service no terminal mt5stock (Navegador ->
                  Servicos) pra passar a exportar o CSV desses dois
                  ativos, senao coletar_alvo_via_csv() nao acha arquivo.
                  1.5.0 (2026-09-30): nova flag opcional --so
                  RAIZ1,RAIZ2,... (repetivel, uniao entre repeticoes ou
                  virgula na mesma ocorrencia) restringe a coleta desta
                  rodada so as raizes indicadas, sem afetar o controle
                  incremental dos demais ativos (eles so ficam de fora
                  desta rodada especifica, o proximo lote sem --so volta
                  a cobrir todos normalmente). Pensada pra usar junto com
                  --reforcar, pra aprofundar o historico so de quem um
                  estudo precisa sem reforcar o config.json inteiro (~200+
                  ativos) de uma vez - pedido do usuario 2026-09-30: "para
                  este tipo de estudo podemos criar um outro banco de
                  dados, nao sendo db literalmente, quero dizer um outro
                  service que carregue a quantidade necessaria de serie
                  historica para o estudo" (estudo do impulso de abertura
                  09:00, ver causalidade.py/correl.py). Exemplo pratico
                  do proprio estudo: python historico.py --reforcar
                  M1:180 --so Indice,Dolar,GOLD,ChinaA50,GBPUSD,USDSEK - Indice/
                  Dolar sao os continuos da corretora nacional (mesmos ativos de Indice/
                  Dolar na corretora internacional, sem a complicacao de rolagem
                  mensal de contrato futuro), GOLD/ChinaA50/GBPUSD/USDSEK
                  sao os preditores com causalidade de Granger confirmada
                  (causa_dolar=True, lag=1) e ficam na corretora internacional - a corretora nacional
                  nao tem essas cotacoes (confirmado pelo usuario). Roda
                  nos dois brokers na mesma execucao, reaproveitando o
                  loop conectar()/coletar_alvo()/desconectar() por broker
                  que ja existia em executar(), sem broker novo.
Autor          : Julio Cesar Silvio Campanhola
Criado em      : 2026-09-19
Ultima edicao  : 2026-09-30
Versao         : 1.5.0
Projeto        : dashboard
Historico      : scripts_py/versoes/historico.md
"""

import argparse
import importlib
import json
import os
import time
from datetime import datetime, timedelta, timezone

from fuso_horario import (
    corrigir_horario_corretora internacional,
    reverter_horario_corretora internacional_escalar,
)

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

# tf_nome -> (constante MT5, dias de profundidade na primeira coleta)
# profundidade escalonada pelo volume de candle por TF (M1 pesa muito mais
# que W1) - ajustavel aqui se quiser mais ou menos historico inicial.
TIMEFRAMES = {
    "M1":  (mt5.TIMEFRAME_M1,  30),
    "M5":  (mt5.TIMEFRAME_M5,  90),
    "M15": (mt5.TIMEFRAME_M15, 180),
    "M30": (mt5.TIMEFRAME_M30, 365),
    "H1":  (mt5.TIMEFRAME_H1,  365),
    "H4":  (mt5.TIMEFRAME_H4,  730),
    "D1":  (mt5.TIMEFRAME_D1,  730),
    "W1":  (mt5.TIMEFRAME_W1,  730),
}

# grupos do config.json cuja raiz tem vencimento (precisa de subpasta mes-ano)
GRUPOS_COM_VENCIMENTO = {"curva_br", "vencimento_americano"}

# broker (terminal MT5) de cada grupo do config.json
BROKER_POR_GRUPO = {
    "curva_br": "corretora nacional",
    "vencimento_americano": "corretora internacional",
    "nacionais": "corretora nacional",
    "indices_continuo": "corretora internacional",
    "moedas_continuo": "corretora internacional",
    "commodities_internacionais": "corretora internacional",
    # terminal novo instalado direto do MQL5 (config.json ->
    # connections.mt5stock, servidor MetaQuotes-Demo) - pedido do usuario
    # 2026-09-26 depois de confirmar via verificar_mt5stock.py que esse
    # catalogo tem as acoes do Nasdaq-100 (e alguns ETFs de treasury) que a
    # corretora internacional nao tem. Acao/ETF a vista, sem vencimento (ticker == raiz,
    # igual indices_continuo) - por isso NAO entra em GRUPOS_COM_VENCIMENTO.
    "acoes_nasdaq100": "mt5stock",
    "treasury_etf_eua": "mt5stock",
    # EWZ (iShares MSCI Brazil) e EEM (iShares MSCI Emerging Markets) -
    # pedido do usuario 2026-09-29 pra montar um "sentimento EM" que ajude a
    # ler risco Brasil/emergentes fora do horario nacional. Mesmo padrao de
    # treasury_etf_eua (ETF a vista, sem vencimento, catalogo mt5stock).
    "etfs_sentimento_em": "mt5stock",
}

# ordem em que os grupos sao processados ao montar a lista de alvos - define
# quem "ganha" quando uma raiz aparece em mais de um grupo (ex: Brent esta
# em vencimento_americano E em commodities_internacionais; processar
# vencimento_americano primeiro faz o Brent ficar com vencimento, que é o
# tratamento correto pra esse ativo)
ORDEM_GRUPOS = [
    "curva_br",
    "vencimento_americano",
    "nacionais",
    "indices_continuo",
    "moedas_continuo",
    "commodities_internacionais",
    "acoes_nasdaq100",
    "treasury_etf_eua",
    "etfs_sentimento_em",
]

# mes abreviado em ingles -> numero (tickers estilo corretora internacional: DolarOct26)
MESES_ABREV = {
    "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
    "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12,
}

# letra do codigo de mes futuro -> numero (tickers estilo corretora nacional/B3: DI1V26)
MESES_LETRA = {
    "F": 1, "G": 2, "H": 3, "J": 4, "K": 5, "M": 6,
    "N": 7, "Q": 8, "U": 9, "V": 10, "X": 11, "Z": 12,
}

# pasta onde o Service MQL5 (backend/Claude outputs/ExportadorMt5Stock.mq5)
# deixa os CSVs de candles do mt5stock - ve nota 1.3.0 no topo do arquivo
PASTA_EXPORT_MT5STOCK_MQL = os.path.join(
    os.path.expandvars("%APPDATA%"), "MetaQuotes", "Terminal", "Common", "Files", "mt5stock_export"
)



class ColetorHistoricoMTF:
    """Coleta os 8 TFs de estudo MTF de cada ativo do config.json, com
    subpastas de vencimento automaticas e atualizacao incremental via
    parquet de controle."""

    def __init__(self, base_dir=None):
        self.base_dir = base_dir or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.config_path = os.path.join(self.base_dir, "json", "config.json")
        self.mtf_dir = os.path.join(self.base_dir, "parquet", "historicos", "MTF")
        self.controle_path = os.path.join(self.mtf_dir, "controle_atualizacao_mtf.parquet")
        self.config = None

    def carregar_config(self):
        with open(self.config_path, "r", encoding="utf-8") as f:
            self.config = json.load(f)
        return self.config

    # -- conexao MT5 (mesmo esquema do int.py/nac.py) -----------------

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

    def conectar(self, nome_broker):
        conexao = self.config["connections"][nome_broker]
        self._garantir_terminal_aberto(conexao["path"])
        ok = mt5.initialize(
            path=conexao["path"],
            login=conexao["login"],
            password=conexao["password"],
            server=conexao["server"],
        )
        if not ok:
            raise RuntimeError(f"[{nome_broker}] falha ao conectar: {mt5.last_error()}")

    def desconectar(self):
        mt5.shutdown()

    # -- parsing de vencimento -----------------------------------------

    @staticmethod
    def extrai_mes_ano_americano(ticker, raiz):
        """DolarOct26 -> (10, 2026). Formato corretora internacional: raiz + mes (3
        letras em ingles) + ano (2 digitos)."""
        sufixo = ticker[len(raiz):]
        for nome, numero in MESES_ABREV.items():
            idx = sufixo.find(nome)
            if idx != -1:
                ano2 = sufixo[idx + 3: idx + 5]
                if ano2.isdigit():
                    return numero, 2000 + int(ano2)
        return None

    @staticmethod
    def extrai_mes_ano_curva(ticker, raiz):
        """DI1V26 -> (10, 2026). Formato corretora nacional/B3: raiz + letra do codigo de
        mes futuro + ano (2 digitos)."""
        sufixo = ticker[len(raiz):]
        if len(sufixo) < 3:
            return None
        letra, ano2 = sufixo[0], sufixo[1:3]
        if letra not in MESES_LETRA or not ano2.isdigit():
            return None
        return MESES_LETRA[letra], 2000 + int(ano2)

    # -- montagem dos alvos ---------------------------------------------

    def montar_alvos(self):
        """Le o config.json e devolve a lista de alvos a coletar: cada
        alvo e um dict {broker, raiz, ticker, pasta_rel}. Ativo com
        vencimento gera um alvo por vigente atual (pode ser mais de um
        durante rolagem); ativo sem vencimento gera um alvo unico com
        ticker == raiz."""
        ativos = self.config["ativos"]
        vigentes = self.config.get("vigentes", {})

        raiz_para_grupo = {}
        for grupo in ORDEM_GRUPOS:
            for raiz in ativos.get(grupo, []):
                if raiz not in raiz_para_grupo:
                    raiz_para_grupo[raiz] = grupo

        alvos = []
        for raiz, grupo in raiz_para_grupo.items():
            broker = BROKER_POR_GRUPO[grupo]

            if grupo in GRUPOS_COM_VENCIMENTO:
                tickers = vigentes.get(raiz, [])
                if not tickers:
                    print(f"AVISO: {raiz} nao tem vigente no config.json, pulando")
                    continue
                extrator = (
                    self.extrai_mes_ano_americano
                    if grupo == "vencimento_americano"
                    else self.extrai_mes_ano_curva
                )
                for ticker in tickers:
                    resultado = extrator(ticker, raiz)
                    if resultado is None:
                        print(f"AVISO: nao consegui extrair vencimento de {ticker} (raiz {raiz})")
                        continue
                    mes, ano = resultado
                    pasta_rel = f"{raiz}/{mes:02d}-{ano}"
                    alvos.append({"broker": broker, "raiz": raiz, "ticker": ticker, "pasta_rel": pasta_rel})
            else:
                alvos.append({"broker": broker, "raiz": raiz, "ticker": raiz, "pasta_rel": raiz})

        return alvos

    # -- controle de atualizacao -----------------------------------------

    def _ultima_data_controle(self, controle_df, pasta_rel, tf_nome):
        if controle_df is None or controle_df.empty:
            return None
        filtro = controle_df[
            (controle_df["ativo_pasta"] == pasta_rel) & (controle_df["timeframe"] == tf_nome)
        ]
        if filtro.empty:
            return None
        return filtro["data_ultima_atualizacao"].max().to_pydatetime()

    # -- coleta -----------------------------------------------------------

    def coletar_alvo(self, alvo, controle_df, reforco=None):
        """Coleta os 8 TFs de um alvo, funde no parquet de cada TF (sem
        duplicar candle) e devolve as linhas novas pro parquet de
        controle."""
        raiz, ticker, pasta_rel = alvo["raiz"], alvo["ticker"], alvo["pasta_rel"]
        pasta_destino = os.path.join(self.mtf_dir, *pasta_rel.split("/"))
        os.makedirs(pasta_destino, exist_ok=True)

        selecionado = mt5.symbol_select(ticker, True)
        info = mt5.symbol_info(ticker)
        if not selecionado or info is None:
            print(f"AVISO: nao consegui selecionar {ticker} (symbol_select={selecionado})")
            return []

        agora = datetime.now(timezone.utc)
        eh_corretora internacional = alvo["broker"] == "corretora internacional"
        # os dois limites da consulta ao MT5 (data_de e o superior) precisam
        # estar no MESMO relogio - pro corretora internacional isso e o horario cru do
        # servidor (revertido), pra corretora nacional e o proprio horario real (sem
        # correcao). Antes desse fix so o data_de era revertido, o que
        # descasava os dois lados da janela justamente na reabertura do
        # mercado (fim de semana) - sintoma: candles corretora internacional travados.
        agora_consulta = (
            reverter_horario_corretora internacional_escalar(agora) if eh_corretora internacional else agora
        )
        linhas_controle = []

        for tf_nome, (tf_mt5, dias_primeira_coleta) in TIMEFRAMES.items():
            arquivo_tf = os.path.join(pasta_destino, f"{tf_nome.lower()}.parquet")

            dias_reforco = (reforco or {}).get(tf_nome)
            ultima_data = self._ultima_data_controle(controle_df, pasta_rel, tf_nome)
            if dias_reforco is not None:
                # reforco de profundidade: ignora o incremental so pra esse TF
                # nesta rodada e busca dias_reforco dias pra tras a partir de
                # agora - o merge com drop_duplicates(subset='time') abaixo ja
                # cuida de nao duplicar o que ja existia, so preenche o que
                # faltava mais pra tras. Nao mexe no data_ultima_atualizacao
                # gravado no controle (continua sendo o candle mais recente).
                data_de = agora_consulta - timedelta(days=dias_reforco)
            elif ultima_data is not None:
                # o controle guarda o horario ja corrigido/alinhado entre
                # corretoras - o MT5 espera o horario cru do proprio servidor
                # da corretora, entao desfaz a correcao so pra essa consulta
                # (DST-aware: -5h no horario de verao europeu, -4h fora dele)
                data_de = (
                    reverter_horario_corretora internacional_escalar(ultima_data)
                    if eh_corretora internacional else ultima_data
                )
            else:
                data_de = agora_consulta - timedelta(days=dias_primeira_coleta)

            rates = mt5.copy_rates_range(ticker, tf_mt5, data_de, agora_consulta)
            if rates is None or len(rates) == 0:
                continue

            df_novo = pd.DataFrame(rates)
            df_novo["time"] = pd.to_datetime(df_novo["time"], unit="s", utc=True)
            if eh_corretora internacional:
                df_novo["time"] = corrigir_horario_corretora internacional(df_novo["time"])

            if os.path.exists(arquivo_tf):
                df_existente = pd.read_parquet(arquivo_tf)
                df_final = pd.concat([df_existente, df_novo], ignore_index=True)
                df_final = df_final.drop_duplicates(subset="time", keep="last")
            else:
                df_final = df_novo

            df_final = df_final.sort_values("time").reset_index(drop=True)
            df_final.to_parquet(arquivo_tf, index=False)

            ultima_linha = df_final.iloc[-1]
            linhas_controle.append({
                "ativo_pasta": pasta_rel,
                "ticker": ticker,
                "timeframe": tf_nome,
                "data_ultima_atualizacao": ultima_linha["time"],
                "preco_ultima_atualizacao": float(ultima_linha["close"]),
            })

        return linhas_controle

    def coletar_alvo_via_csv(self, alvo, controle_df):
        """Mesma fusao/dedup de coletar_alvo(), mas lendo os candles de um
        CSV exportado pelo Service MQL5 (backend/Claude outputs/
        ExportadorMt5Stock.mq5) em vez de chamar mt5.copy_rates_range() -
        contorna o bug do terminal mt5stock (build 6230) isolado com
        diag_symbol_select_mt5stock.py, ver nota 1.3.0 no topo do arquivo."""
        raiz, pasta_rel = alvo["raiz"], alvo["pasta_rel"]
        pasta_destino = os.path.join(self.mtf_dir, *pasta_rel.split("/"))
        os.makedirs(pasta_destino, exist_ok=True)

        linhas_controle = []
        for tf_nome in TIMEFRAMES:
            csv_origem = os.path.join(PASTA_EXPORT_MT5STOCK_MQL, raiz, f"{tf_nome.lower()}.csv")
            if not os.path.exists(csv_origem):
                print(f"AVISO: CSV nao encontrado pra {raiz} {tf_nome} ({csv_origem}) - Service ExportadorMt5Stock rodando?")
                continue

            try:
                df_novo = pd.read_csv(csv_origem)
            except Exception as exc:
                print(f"AVISO: falha lendo {csv_origem}: {exc}")
                continue
            if df_novo.empty:
                continue

            df_novo["time"] = pd.to_datetime(df_novo["time"], unit="s", utc=True)

            arquivo_tf = os.path.join(pasta_destino, f"{tf_nome.lower()}.parquet")
            if os.path.exists(arquivo_tf):
                df_existente = pd.read_parquet(arquivo_tf)
                df_final = pd.concat([df_existente, df_novo], ignore_index=True)
                df_final = df_final.drop_duplicates(subset="time", keep="last")
            else:
                df_final = df_novo

            df_final = df_final.sort_values("time").reset_index(drop=True)
            df_final.to_parquet(arquivo_tf, index=False)

            ultima_linha = df_final.iloc[-1]
            linhas_controle.append({
                "ativo_pasta": pasta_rel,
                "ticker": raiz,
                "timeframe": tf_nome,
                "data_ultima_atualizacao": ultima_linha["time"],
                "preco_ultima_atualizacao": float(ultima_linha["close"]),
            })

        return linhas_controle

    def executar(self, reforco=None, so=None):
        """so: conjunto opcional de raizes (ex {"Indice","Dolar","GOLD"}) pra
        restringir a coleta so a elas nesta rodada -- pedido do usuario
        2026-09-30 ("um outro service que carregue a quantidade necessaria
        de serie historica pra o estudo"), usado junto com --reforcar pra
        aprofundar o M1 so dos ativos de um estudo especifico (ex: impulso
        de abertura) sem reforcar as centenas de ativos do config.json
        inteiro de uma vez -- mais rapido e nao sobrecarrega o MT5/disco a
        toa. None (padrao) mantem o comportamento de sempre, todos os
        alvos do config.json."""
        self.carregar_config()
        alvos = self.montar_alvos()
        if so:
            alvos_filtrados = [a for a in alvos if a["raiz"] in so]
            faltando = so - {a["raiz"] for a in alvos_filtrados}
            if faltando:
                print(f"AVISO: --so pediu raiz(es) que nao existem em config.json -> ativos: {sorted(faltando)}")
            alvos = alvos_filtrados

        controle_existente = None
        if os.path.exists(self.controle_path):
            try:
                controle_existente = pd.read_parquet(self.controle_path)
            except Exception:
                controle_existente = None

        alvos_por_broker = {}
        for alvo in alvos:
            alvos_por_broker.setdefault(alvo["broker"], []).append(alvo)

        novas_linhas = []
        for broker, lista_alvos in alvos_por_broker.items():
            print(f"[{broker}] coletando {len(lista_alvos)} ativos/vencimentos (8 TFs cada)...")

            if broker == "mt5stock":
                # Service MQL5 (ExportadorMt5Stock.mq5) ja exporta os CSVs
                # nativamente de dentro do terminal - nao conecta via API
                # Python externa pra esse broker (ver nota 1.3.0)
                for alvo in lista_alvos:
                    try:
                        linhas = self.coletar_alvo_via_csv(alvo, controle_existente)
                        novas_linhas.extend(linhas)
                    except Exception as exc:
                        print(f"AVISO: falha em {alvo['ticker']} ({alvo['pasta_rel']}): {exc}")
                continue

            self.conectar(broker)
            for alvo in lista_alvos:
                try:
                    linhas = self.coletar_alvo(alvo, controle_existente, reforco=reforco)
                    novas_linhas.extend(linhas)
                except Exception as exc:
                    print(f"AVISO: falha em {alvo['ticker']} ({alvo['pasta_rel']}): {exc}")
            self.desconectar()

        if novas_linhas:
            df_novas = pd.DataFrame(novas_linhas)
            if controle_existente is not None and not controle_existente.empty:
                df_controle_final = pd.concat([controle_existente, df_novas], ignore_index=True)
            else:
                df_controle_final = df_novas
            os.makedirs(os.path.dirname(self.controle_path), exist_ok=True)
            df_controle_final.to_parquet(self.controle_path, index=False)
            print(f"Controle atualizado: {self.controle_path} (+{len(df_novas)} linhas)")
        else:
            print("Nenhuma linha nova pro controle.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Coleta historico MTF (8 TFs) do config.json",
    )
    parser.add_argument(
        "--reforcar",
        action="append",
        default=[],
        metavar="TF:DIAS",
        help=(
            "Forca busca de mais historico pra tras num TF especifico "
            "nesta rodada, ignorando o incremental so pra ele "
            "(ex: --reforcar M5:720). Repetir a flag pra reforcar mais "
            "de um TF na mesma rodada. Nao afeta os demais TFs, que "
            "seguem incrementais normalmente."
        ),
    )
    parser.add_argument(
        "--so",
        action="append",
        default=[],
        metavar="RAIZ1,RAIZ2,...",
        help=(
            "Restringe a coleta desta rodada so as raizes indicadas (nomes "
            "exatos de config.json -> ativos, ex: Indice,Dolar,GOLD). Repetir "
            "a flag ou separar por virgula tem o mesmo efeito (uniao). Nao "
            "afeta o controle incremental dos demais ativos -- eles so "
            "ficam de fora desta rodada especifica. Pensado pra usar junto "
            "com --reforcar, pra aprofundar o historico so de quem um "
            "estudo precisa (ex: impulso de abertura) sem mexer no "
            "config.json inteiro de uma vez."
        ),
    )
    args = parser.parse_args()

    conjunto_so = set()
    for item in args.so:
        conjunto_so.update(p.strip() for p in item.split(",") if p.strip())

    reforco = {}
    for item in args.reforcar:
        tf_nome, _, dias_txt = item.partition(":")
        tf_nome = tf_nome.upper()
        if tf_nome not in TIMEFRAMES or not dias_txt.isdigit():
            print(
                f"AVISO: --reforcar invalido ignorado: {item!r} "
                "(formato esperado TF:DIAS, ex M5:720)"
            )
            continue
        reforco[tf_nome] = int(dias_txt)

    ColetorHistoricoMTF().executar(reforco=reforco or None, so=conjunto_so or None)
