"""
Nome do script : vies_direcional.py
Descricao      : Fica rodando continuamente (nao termina sozinho) calculando
                  o VIES DIRECIONAL de Indice e Dolar a partir de indicadores
                  MTF (H1/H4/D1) de todo o universo de ativos correlacionados,
                  mais um REFINAMENTO DE ENTRADA a partir do IFR em tempo
                  real (M1/M5) do proprio Indice/Dolar. Nao decide preco de
                  entrada (isso continua manual, o usuario olha a tela) — so
                  responde "da pra montar posicao, em qual direcao, e o
                  momento de entrada esta batendo agora?".

                  Regra combinada com o usuario (2026-09-21):

                  1) Universo de ativos: todo ativo coletado pelo
                     historico.py (config.json -> ativos), EXCETO:
                     - Indice/Dolar (sao o alvo, nao driver);
                     - Indice e Dolar (qualquer vencimento) — sao o MESMO
                       ativo que Indice/Dolar via corretora internacional, correlacao
                       proxima de 1.0 e tautologica, nao confirmacao
                       independente;
                     - OC1, DAP e o DOLAR da curva_br (curva de cupom
                       cambial) — nao pedidos pelo usuario, ficam de fora
                       por enquanto.
                     Da curva_br entram DI1 (Juros), FRC e DDI, mas so o
                     VERTICE MAIS PROXIMO (front) de cada curva por
                     enquanto — o usuario deixou claro que uma leitura mais
                     fina do DI1 (retorno da minima/maxima ate o preco,
                     regiao de IFR do DI1 impactando indice/dolar — nao e
                     uma correlacao de retorno simples) e um estudo a parte,
                     pra fazer depois. Isso aqui e so o ponto de partida.

                  2) Voto de cada ativo, em cada TF maior (H1, H4, D1):
                     sinal do histograma do MACD (positivo=alta,
                     negativo=baixa). O IFR entra como CONFIRMACAO, nao
                     como voto independente: se o IFR concorda com o MACD
                     (>50 quando MACD positivo, <50 quando negativo), o
                     voto pesa cheio (1.0); se discorda, pesa metade (0.5)
                     — o IFR sozinho e indicador de reversao a media e fica
                     esticado por muito tempo dentro de uma tendencia forte,
                     entao nao pode contar como voto igual ao MACD.

                  3) Combinacao entre os TFs maiores do mesmo ativo: media
                     ponderada, D1 pesando mais que H4, que pesa mais que
                     H1 (pesos TF_PESOS abaixo) — decisao do usuario.

                  4) Esse voto (por ativo) e multiplicado pela correlacao
                     JA CALCULADA pelo correl.py/calcular_peso()
                     (pesoMercadoD1.parquet — correlacao_indice e
                     correlacao_dolar, com sinal, SEM filtro de limiar,
                     universo inteiro) — isso inverte o voto sozinho
                     quando a correlacao e negativa (descorrelacao) e pesa
                     mais quem anda mais junto/contra INDICE ou DOLAR. Soma-se
                     tudo (normalizado pela soma dos pesos absolutos) e vira
                     uma pontuacao unica pra INDICE e outra pra DOLAR. Score >
                     LIMIAR_NEUTRO = vies de alta; < -LIMIAR_NEUTRO = vies
                     de baixa; entre os dois = neutro (sem consenso).

                  5) Refinamento de entrada (M1/M5, tempo real, Indice/Dolar):
                     le o IFR que o last_indicadores_nac.py ja calcula em
                     tempo real e detecta o momento em que ele SAI da zona
                     esticada 25/75 (decisao do usuario — nem o classico
                     30/70 nem um numero so meu, ficou no meio: 25/75) na
                     MESMA direcao do vies ja apurado: vies de alta + IFR
                     M5 cruzando de volta ACIMA de 25 (vindo de baixo) =
                     gatilho de entrada; vies de baixa + IFR M5 cruzando de
                     volta ABAIXO de 75 (vindo de cima) = gatilho de
                     entrada. M1 e calculado e exposto tambem (informativo),
                     mas o gatilho oficial usa M5 (menos ruido). Sem vies
                     definido (neutro), nao ha gatilho — o sistema nao
                     empurra entrada sem direcao.

                  Escopo explicito: isto NAO calcula nem sugere preco de
                  entrada — o usuario decide isso olhando a tela. Isto so
                  aponta direcao (viavel montar posicao ou nao, em qual
                  ativo, em qual sentido) e se o timing de entrada dentro
                  dessa direcao esta batendo agora.

                  Double buffer + escrita atomica + guard de "mudou desde a
                  ultima volta" + parada limpa via
                  parquet/historicos/_stop_last.flag: mesmo padrao de
                  last_nac.py/last_int.py/last_indicadores_nac.py. Sai em
                  json/last_json/vies_direcional_a.json e
                  vies_direcional_b.json.
                  6) Grupos indice/dolar (pedido do usuario 2026-09-21): Indice e
                     Indice pertencem ao grupo INDICE; Dolar, Dolar e USDBRL
                     pertencem ao grupo DOLAR — nenhum membro de um grupo
                     compara com outro membro do MESMO grupo (e a mesma
                     grandeza economica, ver RAIZES_EXCLUIDAS), mas cada um
                     tem sua propria correlacao com o RESTO da grade,
                     calculada pelo correl.py (correlacao_indice/
                     correlacao_indice/correlacao_dolar/correlacao_dolar/
                     correlacao_usdbrl). O score de Indice agora pondera o
                     voto de cada ativo da grade por DUAS correlacoes —
                     contra Indice e contra Indice — somadas (grade vs. um
                     membro do cluster, nunca cluster vs. cluster); o score
                     de Dolar pondera por TRES — contra Dolar, Dolar e
                     USDBRL. Continua sendo o mesmo ativo da grade votando,
                     so a base de correlacao usada pra pesar aquele voto
                     ficou mais ampla (ver GRUPO_INDICE/GRUPO_DOLAR).
Autor          : Julio Cesar Silvio Campanhola
Criado em      : 2026-09-21
Ultima edicao  : 2026-09-25
Versao         : 1.4.0
Projeto        : dashboard
Historico      : scripts_py/versoes/vies_direcional.md
"""

import importlib
import json
import os
import time

try:
    pd = importlib.import_module("pandas")
except ImportError as exc:
    raise ImportError(
        "A dependencia pandas nao esta instalada. "
        "Instale-a com: pip install pandas pyarrow"
    ) from exc

from historico import ColetorHistoricoMTF

BROKER_REF = "corretora nacional"
SYMBOL_INDICE = "Indice"
SYMBOL_DOLAR = "Dolar"

# ativos que sao o MESMO instrumento (ou a mesma grandeza economica) que
# Indice/Dolar — fora do universo de voto porque a correlacao deles e
# tautologica, nao confirmacao independente: Indice/Dolar via corretora internacional
# sao literalmente o mesmo ativo que Indice/Dolar; USDBRL e ativo NACIONAL
# (cambio a vista real/dolar) — a mesma grandeza que o Dolar (dolar futuro),
# so que a vista em vez de futuro (correcao do usuario 2026-09-21, apos o
# USDBRL ter dominado sozinho um teste de backtest por causa da correlacao
# de 0,84-0,97 com INDICE/DOLAR)
RAIZES_EXCLUIDAS = {"Indice", "Dolar", "USDBRL"}

# grupos indice/dolar (pedido do usuario 2026-09-21) — quais colunas de
# correlacao (todas grade-vs-um-membro-do-cluster, calculadas pelo
# correl.py) entram no score de cada alvo. Indice le indice inteiro (indice +
# indice); Dolar le dolar inteiro (dolar + dolar + usdbrl) — nunca um membro
# do cluster pesado pela correlacao de outro membro do MESMO cluster.
GRUPO_INDICE = ("correlacao_indice", "correlacao_indice")
GRUPO_DOLAR = ("correlacao_dolar", "correlacao_dolar", "correlacao_usdbrl")

# Ativos-alvo NOVOS (pedido do usuario 2026-09-25, primeiro = UsaTec/Nasdaq)
# — mesmo motor de voto (MACD H1/H4/D1 + IFR confirmacao), so muda a coluna
# de correlacao usada pra pesar cada voto da grade. Ao contrario de
# indice/dolar, aqui NAO tem par de instrumento gemeo (Indice pro indice,
# Dolar/USDBRL pro dolar) — e so uma coluna por grupo (a que o correl.py
# ja calcula a partir de config.json -> ativos_referencia_extra). O ativo
# continua dentro do self.universo normalmente (pode votar em indice/dolar) — o
# correl.py ja zera (None) a correlacao dele contra ele mesmo, entao
# _acumular_grupo pula essa linha sozinho pro proprio score dele, sem
# precisar de mais nenhuma exclusao aqui. Lista fica no config.json (pedido
# do usuario: "nao seria interessante criar um arquivo json que faz isso?")
# — ver self.alvos_extra/_resolver_alvos_extra abaixo, nao mais hardcoded
# aqui.

# raizes da curva_br que existem no config.json mas nao entram no vies por
# enquanto (nao pedidas pelo usuario) — so DI1/FRC/DDI entram, e so o
# vertice mais proximo de cada uma (ver _montar_universo)
CURVA_RAIZES_TODAS = {"DI1", "OC1", "DAP", "FRC", "DDI", "DOLAR"}
CURVA_RAIZES_INCLUIDAS = {"DI1", "FRC", "DDI"}

TIMEFRAMES_VIES = ["h1", "h4", "d1"]
TF_PESOS = {"h1": 1.0, "h4": 2.0, "d1": 3.0}

LIMIAR_NEUTRO = 0.15  # |score| abaixo disso = sem consenso (neutro)

ZONA_ESTICADA_BAIXA = 25.0  # decisao do usuario: nem 30 classico nem um numero so meu, ficou 25/75
ZONA_ESTICADA_ALTA = 75.0

PAUSA_LOOP = 1.0


class MotorViesDirecional:
    """Cruza indicadores MTF (H1/H4/D1) de todo o universo correlacionado
    com o peso/sinal de correlacao do correl.py pra apurar um vies
    direcional de Indice/Dolar, e cruza com o IFR M1/M5 em tempo real do
    proprio Indice/Dolar pra apontar o momento de entrada dentro desse vies."""

    def __init__(self, base_dir=None):
        self.base_dir = base_dir or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.mtf_dir = os.path.join(self.base_dir, "parquet", "historicos", "MTF")
        self.peso_path = os.path.join(self.base_dir, "parquet", "calculos", "pesoMercadoD1.parquet")

        last_json_dir = os.path.join(self.base_dir, "json", "last_json")
        self.indicadores_nac_paths = (
            os.path.join(last_json_dir, "last_indicadores_nac_a.json"),
            os.path.join(last_json_dir, "last_indicadores_nac_b.json"),
        )

        output_dir = last_json_dir
        os.makedirs(output_dir, exist_ok=True)
        self.output_path_a = os.path.join(output_dir, "vies_direcional_a.json")
        self.output_path_b = os.path.join(output_dir, "vies_direcional_b.json")
        self.stop_flag_path = os.path.join(self.base_dir, "parquet", "historicos", "_stop_last.flag")

        self.coletor = ColetorHistoricoMTF(self.base_dir)
        self.universo = None  # montado uma vez (so muda se config.json mudar — reinicia o script pra recarregar)
        self.alvos_extra = {}  # idem — resolvido junto com self.universo, ver _resolver_alvos_extra

        self.ultimo_mtime = {}     # caminho -> mtime, pra saber se precisa recalcular o vies
        self.ifr_anterior = {}     # (symbol, timeframe) -> ultimo IFR visto, pra detectar cruzamento de zona
        self.estado_atual = {"indice": None, "dolar": None}
        self._sujo = False
        self._proximo_arquivo = "a"

    # ---------- universo de ativos ----------

    def _montar_universo(self):
        """Le config.json e devolve a lista de alvos {broker, raiz, ticker,
        pasta_rel} que entram no voto do vies — Indice/Dolar, Indice/Dolar e
        OC1/DAP/DOLAR(curva) de fora; DI1/FRC/DDI reduzidos ao vertice mais
        proximo (front) de cada curva."""
        self.coletor.carregar_config()
        alvos = self.coletor.montar_alvos()

        universo = []
        for alvo in alvos:
            raiz = alvo["raiz"]
            if raiz in (SYMBOL_INDICE, SYMBOL_DOLAR):
                continue
            if raiz in RAIZES_EXCLUIDAS:
                continue
            if raiz in CURVA_RAIZES_TODAS and raiz not in CURVA_RAIZES_INCLUIDAS:
                continue
            universo.append(alvo)

        def _chave_vencimento(alvo):
            resultado = ColetorHistoricoMTF.extrai_mes_ano_curva(alvo["ticker"], alvo["raiz"])
            if resultado is None:
                return (9999, 99)
            mes, ano = resultado
            return (ano, mes)

        por_curva = {}
        resto = []
        for alvo in universo:
            if alvo["raiz"] in CURVA_RAIZES_INCLUIDAS:
                por_curva.setdefault(alvo["raiz"], []).append(alvo)
            else:
                resto.append(alvo)

        for raiz, lista in por_curva.items():
            frente = min(lista, key=_chave_vencimento)
            resto.append(frente)

        return resto

    def _resolver_alvos_extra(self):
        """Deriva os ativos-alvo extras (ex.: usatec) de config.json ->
        ativos_referencia_extra — pedido do usuario 2026-09-25 pra nao
        hardcoded ficar em Python (adicionar Ouro/SP500/Petroleo no futuro
        vira so uma linha no config.json). grupo_correlacao e sempre
        (f"correlacao_{nome}",) — mesma convencao de nome de coluna que o
        correl.py usa pra cada entrada desse mesmo dict do config. Chamado
        logo apos self.coletor.carregar_config() (dentro de
        _montar_universo), entao self.coletor.config ja esta fresco."""
        extras_config = (self.coletor.config or {}).get("ativos_referencia_extra", {})
        return {
            nome: {"raiz": info["raiz"], "grupo_correlacao": (f"correlacao_{nome}",)}
            for nome, info in extras_config.items()
        }

    # ---------- indicadores MTF (H1/H4/D1) ----------

    def _caminho_indicador(self, alvo, timeframe):
        pasta = os.path.join(self.mtf_dir, *alvo["pasta_rel"].split("/"))
        return os.path.join(pasta, "indicadores", f"{timeframe}.parquet")

    def _ultimo_indicador(self, alvo, timeframe):
        caminho = self._caminho_indicador(alvo, timeframe)
        if not os.path.exists(caminho):
            return None
        df = pd.read_parquet(caminho, columns=["time", "ifr", "macd_hist"])
        if df.empty:
            return None
        ultima = df.sort_values("time").iloc[-1]
        if pd.isna(ultima["ifr"]) or pd.isna(ultima["macd_hist"]):
            return None
        return {"ifr": float(ultima["ifr"]), "macd_hist": float(ultima["macd_hist"])}

    @staticmethod
    def _voto_ativo_tf(indicador):
        """Sinal do histograma MACD e o voto; IFR so confirma (peso cheio
        se concordar, metade se nao)."""
        macd_hist = indicador["macd_hist"]
        if macd_hist == 0:
            return 0.0
        sinal = 1.0 if macd_hist > 0 else -1.0
        ifr = indicador["ifr"]
        concorda = (sinal > 0 and ifr > 50) or (sinal < 0 and ifr < 50)
        peso_confirmacao = 1.0 if concorda else 0.5
        return sinal * peso_confirmacao

    def _voto_ativo(self, alvo):
        """Combina H1/H4/D1 do ativo num voto so (media ponderada, D1 > H4
        > H1). Devolve None se nenhum TF tiver indicador pronto ainda."""
        soma = 0.0
        soma_pesos = 0.0
        for timeframe in TIMEFRAMES_VIES:
            indicador = self._ultimo_indicador(alvo, timeframe)
            if indicador is None:
                continue
            voto = self._voto_ativo_tf(indicador)
            peso_tf = TF_PESOS[timeframe]
            soma += voto * peso_tf
            soma_pesos += peso_tf
        if soma_pesos == 0:
            return None
        return soma / soma_pesos

    # ---------- peso/sinal de correlacao (correl.py) ----------

    def _ler_peso(self):
        if not os.path.exists(self.peso_path):
            return {}
        colunas_extra = [c for info in self.alvos_extra.values() for c in info["grupo_correlacao"]]
        colunas = ["broker", "symbol"] + list(GRUPO_INDICE) + list(GRUPO_DOLAR) + colunas_extra
        df = pd.read_parquet(self.peso_path, columns=colunas)
        return {(linha["broker"], linha["symbol"]): linha for _, linha in df.iterrows()}

    def _classificar(self, score):
        if score > LIMIAR_NEUTRO:
            return "alta"
        if score < -LIMIAR_NEUTRO:
            return "baixa"
        return "neutro"

    @staticmethod
    def _acumular_grupo(soma, peso, voto, peso_row, colunas_grupo, entrada):
        """Soma voto*correlacao pra cada coluna do grupo (indice ou dolar)
        disponivel naquele ativo — cada coluna e grade-vs-UM-membro-do-
        cluster (nunca cluster-vs-cluster), entao pode empilhar mais de uma
        no mesmo score sem violar a regra de nao comparar o cluster com ele
        mesmo. Devolve (soma, peso, usou_alguma)."""
        usou = False
        for coluna in colunas_grupo:
            corr = peso_row.get(coluna)
            if corr is None or pd.isna(corr):
                continue
            soma += voto * corr
            peso += abs(corr)
            entrada[coluna] = round(float(corr), 3)
            usou = True
        return soma, peso, usou

    def calcular_vies(self):
        """Pontuacao de vies pra INDICE (grupo indice: indice+indice), DOLAR (grupo
        dolar: dolar+dolar+usdbrl) e cada ALVOS_EXTRA (ex.: usatec — so a
        propria coluna de correlacao, sem par gemeo): soma do voto de cada
        ativo da grade multiplicado pela correlacao (com sinal) desse ativo
        contra CADA membro do grupo, normalizada pela soma dos pesos
        absolutos de correlacao usados de fato. Cada correlacao usada e
        sempre grade-vs-um-membro-do-cluster/alvo — nunca um membro do
        cluster contra outro do mesmo cluster (regra do usuario,
        2026-09-21), nem um ativo extra contra ele mesmo (correl.py ja
        zera essa correlacao especifica)."""
        peso_lookup = self._ler_peso()

        # um acumulador [soma, peso, n_considerados] por alvo — indice/dolar
        # continuam com os MESMOS nomes/grupos de sempre; ALVOS_EXTRA
        # entra no mesmo loop generico, sem duplicar logica.
        grupos_por_alvo = {"indice": GRUPO_INDICE, "dolar": GRUPO_DOLAR}
        grupos_por_alvo.update({nome: info["grupo_correlacao"] for nome, info in self.alvos_extra.items()})
        acumuladores = {nome: [0.0, 0.0, 0] for nome in grupos_por_alvo}
        detalhes = []

        for alvo in self.universo:
            peso_row = peso_lookup.get((alvo["broker"], alvo["ticker"]))
            if peso_row is None:
                continue
            voto = self._voto_ativo(alvo)
            if voto is None:
                continue

            entrada = {"raiz": alvo["raiz"], "ticker": alvo["ticker"], "voto": round(voto, 3)}
            usou_algum = False

            for nome, colunas_grupo in grupos_por_alvo.items():
                soma, peso, n = acumuladores[nome]
                soma, peso, usou = self._acumular_grupo(soma, peso, voto, peso_row, colunas_grupo, entrada)
                acumuladores[nome] = [soma, peso, n + usou]
                usou_algum = usou_algum or usou

            if usou_algum:
                detalhes.append(entrada)

        resultado = {}
        for nome, (soma, peso, n) in acumuladores.items():
            score = soma / peso if peso > 0 else 0.0
            resultado[nome] = {"score": round(score, 3), "vies": self._classificar(score), "ativos_considerados": n}
        resultado["detalhes"] = detalhes
        return resultado

    # ---------- refinamento de entrada (M1/M5 tempo real) ----------

    def _ler_indicadores_tempo_real(self):
        """Le o double buffer do last_indicadores_nac.py (mesmo padrao de
        leitura do api_server.py: pega o arquivo com mtime mais recente)."""
        caminho_a, caminho_b = self.indicadores_nac_paths
        candidatos = [(os.path.getmtime(c), c) for c in (caminho_a, caminho_b) if os.path.exists(c)]
        if not candidatos:
            return []
        candidatos.sort(key=lambda par: par[0], reverse=True)
        try:
            with open(candidatos[0][1], "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            if len(candidatos) > 1:
                try:
                    with open(candidatos[1][1], "r", encoding="utf-8") as f:
                        return json.load(f)
                except (json.JSONDecodeError, OSError):
                    pass
            return []

    def _detectar_gatilho(self, symbol, vies, ifr_por_tf):
        """Gatilho oficial usa M5 (menos ruido); M1 fica so informativo.
        Cruzamento de VOLTA pra dentro da zona 25/75, na direcao do vies —
        sem vies definido, nunca ha gatilho."""
        ifr_m5 = ifr_por_tf.get("m5")
        if ifr_m5 is None or vies == "neutro":
            return False

        anterior = self.ifr_anterior.get((symbol, "m5"))
        self.ifr_anterior[(symbol, "m5")] = ifr_m5
        if anterior is None:
            return False

        if vies == "alta":
            return anterior <= ZONA_ESTICADA_BAIXA < ifr_m5
        if vies == "baixa":
            return anterior >= ZONA_ESTICADA_ALTA > ifr_m5
        return False

    def calcular_refinamento(self, vies_indice, vies_dolar):
        registros = self._ler_indicadores_tempo_real()
        ifr_indice = {}
        ifr_dolar = {}
        for registro in registros:
            symbol = registro["symbol"]
            timeframe = registro["timeframe"].lower()
            if symbol == SYMBOL_INDICE:
                ifr_indice[timeframe] = registro["ifr"]
            elif symbol == SYMBOL_DOLAR:
                ifr_dolar[timeframe] = registro["ifr"]
            # mantem o "anterior" de M1 tambem atualizado, mesmo sem uso no
            # gatilho oficial, pra nao perder o rastro se decidirmos usar
            # M1 no gatilho no futuro
            self.ifr_anterior.setdefault((symbol, timeframe), registro["ifr"])

        gatilho_indice = self._detectar_gatilho(SYMBOL_INDICE, vies_indice, ifr_indice)
        gatilho_dolar = self._detectar_gatilho(SYMBOL_DOLAR, vies_dolar, ifr_dolar)

        return (
            {"ifr_m1": ifr_indice.get("m1"), "ifr_m5": ifr_indice.get("m5"), "gatilho_entrada": gatilho_indice},
            {"ifr_m1": ifr_dolar.get("m1"), "ifr_m5": ifr_dolar.get("m5"), "gatilho_entrada": gatilho_dolar},
        )

    def _alvo_por_raiz(self, raiz):
        for alvo in self.universo:
            if alvo["raiz"] == raiz:
                return alvo
        return None

    def calcular_refinamento_extra(self, nome, raiz, vies):
        """Refinamento de entrada pros ALVOS_EXTRA (ex.: usatec) — mesmo
        gatilho M5 saindo da zona 25/75 de calcular_refinamento, so que le o
        IFR M5 direto do parquet MTF do proprio ativo (indicadores_mtf.py)
        em vez do feed em tempo real dedicado que so existe pra Indice/Dolar
        (last_indicadores_nac.py, corretora nacional) — esses ativos sao corretora internacional,
        ainda sem feed proprio de tempo real. M5 e o suficiente pro gatilho
        oficial (a cadencia do loop em lote ja e pautada por candle M5 novo
        — ver _aguardar_novo_m5 no main.py); so o M1 (so informativo mesmo
        pro INDICE/DOLAR, nao usado no gatilho) fica de fora aqui, sai sempre
        null."""
        alvo = self._alvo_por_raiz(raiz)
        indicador = self._ultimo_indicador(alvo, "m5") if alvo else None
        ifr_m5 = indicador["ifr"] if indicador else None
        ifr_por_tf = {"m5": ifr_m5} if ifr_m5 is not None else {}
        gatilho = self._detectar_gatilho(raiz, vies, ifr_por_tf)
        return {"ifr_m1": None, "ifr_m5": ifr_m5, "gatilho_entrada": gatilho}

    # ---------- watch de mudanca (so recalcula o vies quando algo mudou) ----------

    def _algo_mudou(self):
        """Compara mtime dos arquivos de indicador H1/H4/D1 do universo
        inteiro + do peso — leitura de metadado, quase gratis. So reabre
        parquet de verdade (calcular_vies) quando algo realmente mudou."""
        mudou = False
        caminhos = [self.peso_path]
        for alvo in self.universo:
            for timeframe in TIMEFRAMES_VIES:
                caminhos.append(self._caminho_indicador(alvo, timeframe))

        for caminho in caminhos:
            try:
                mtime = os.path.getmtime(caminho)
            except OSError:
                continue
            if self.ultimo_mtime.get(caminho) != mtime:
                self.ultimo_mtime[caminho] = mtime
                mudou = True
        return mudou

    # ---------- ciclo principal ----------

    def _rodar_ciclo(self):
        if self.universo is None:
            self.universo = self._montar_universo()
            self.alvos_extra = self._resolver_alvos_extra()

        if self._algo_mudou() or self.estado_atual["indice"] is None:
            vies = self.calcular_vies()
            self.estado_atual["indice"] = vies["indice"]
            self.estado_atual["dolar"] = vies["dolar"]
            for nome in self.alvos_extra:
                self.estado_atual[nome] = vies[nome]
            self.estado_atual["detalhes"] = vies["detalhes"]
            self._sujo = True

        if self.estado_atual["indice"] is None:
            return  # ainda sem indicador/peso suficiente pra um primeiro calculo

        refinamento_indice, refinamento_dolar = self.calcular_refinamento(
            self.estado_atual["indice"]["vies"], self.estado_atual["dolar"]["vies"]
        )
        if self.estado_atual.get("refinamento_indice") != refinamento_indice:
            self.estado_atual["refinamento_indice"] = refinamento_indice
            self._sujo = True
        if self.estado_atual.get("refinamento_dolar") != refinamento_dolar:
            self.estado_atual["refinamento_dolar"] = refinamento_dolar
            self._sujo = True

        for nome, info in self.alvos_extra.items():
            refinamento = self.calcular_refinamento_extra(nome, info["raiz"], self.estado_atual[nome]["vies"])
            chave = f"refinamento_{nome}"
            if self.estado_atual.get(chave) != refinamento:
                self.estado_atual[chave] = refinamento
                self._sujo = True

    def _flush(self):
        if not self._sujo:
            return
        saida = {
            "atualizado_em": pd.Timestamp.now(tz="UTC").isoformat(),
            "indice": {**self.estado_atual["indice"], **(self.estado_atual.get("refinamento_indice") or {})},
            "dolar": {**self.estado_atual["dolar"], **(self.estado_atual.get("refinamento_dolar") or {})},
            "detalhes": self.estado_atual.get("detalhes", []),
        }
        for nome in self.alvos_extra:
            saida[nome] = {**self.estado_atual[nome], **(self.estado_atual.get(f"refinamento_{nome}") or {})}

        alvo = self.output_path_a if self._proximo_arquivo == "a" else self.output_path_b
        tmp_path = alvo + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(saida, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, alvo)
        self._proximo_arquivo = "b" if self._proximo_arquivo == "a" else "a"

        extras_log = " | ".join(
            f"{nome.upper()} {saida[nome]['vies']} ({saida[nome]['score']})" for nome in self.alvos_extra
        )
        print(f"[vies] INDICE {saida['indice']['vies']} ({saida['indice']['score']}) | "
              f"DOLAR {saida['dolar']['vies']} ({saida['dolar']['score']})"
              + (f" | {extras_log}" if extras_log else "")
              + f" -> {os.path.basename(alvo)}")
        self._sujo = False

    def executar(self):
        print("[vies] vies_direcional rodando (Ctrl+C pra parar)")
        try:
            while not os.path.exists(self.stop_flag_path):
                try:
                    self._rodar_ciclo()
                except Exception as exc:
                    print(f"[vies] erro no ciclo, seguindo pro proximo: {exc}")
                try:
                    self._flush()
                except Exception as exc:
                    print(f"[vies] erro no flush, tentando de novo no proximo ciclo: {exc}")
                time.sleep(PAUSA_LOOP)
            print("[vies] sinal de parada recebido")
        except KeyboardInterrupt:
            print("[vies] Ctrl+C recebido")
        finally:
            self._flush()


if __name__ == "__main__":
    MotorViesDirecional().executar()
