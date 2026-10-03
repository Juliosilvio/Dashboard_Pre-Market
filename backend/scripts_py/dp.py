"""
Nome do script : dp.py
Descricao      : Projecao de desvios de preco (regiao mais provavel de
                  cruzamento do MACD + faixa de preco em torno dela) pra
                  Indice/Dolar em MTF (M15, M30, H1, H4, D1, W1) — formaliza
                  em script tudo que foi validado manualmente com o
                  usuario nesta sessao (2026-09-23), nesta ordem:

                  1) PERNA ATUAL DO HISTOGRAMA (geometria, nao regressao
                     crua nas 2 linhas MACD/sinal — essa e instavel
                     quando as linhas andam quase paralelas, ver 3):
                     acha o ULTIMO CRUZAMENTO DE ZERO do histograma
                     (macd_hist muda de sinal), depois a PONTA (pico ou
                     vale, |valor| maximo) dentro dessa perna. So projeta
                     cruzamento futuro quando ja passou da ponta (esta
                     "voltando" pro zero) — antes disso ("indo pra
                     ponta") ou logo apos cruzar ("cruzou_agora") nao ha
                     base pra reta nenhuma, e o campo fica None de
                     proposito (nao inventa numero so pra preencher).

                  2) REGRESSAO LINEAR da ponta ate agora, separada no
                     histograma (acha EM QUANTOS CANDLES cruza o zero) e
                     no PRECO (acha o preco mais provavel NAQUELE
                     instante) — pedido explicito do usuario: "quero
                     saber no preco qual regiao mais provavel vai
                     acontecer". media_base = (preco projetado + ultimo
                     fechamento) / 2.

                  3) POR QUE NAO REGREDIR AS 2 LINHAS CRUAS: testado e
                     descartado nesta sessao — quando MACD e sinal andam
                     quase paralelos (comum, sinal e media do proprio
                     MACD), o ponto de intersecao tem uma divisao por
                     (inclinacao1 - inclinacao2) que fica perto de zero,
                     e qualquer ruido de janela vira numero absurdo (ex:
                     -103.682 no MACD do Indice W1 testando janelas
                     diferentes). A perna ancorada em cruzamento+ponta
                     (1) e geometrica, nao sofre desse problema.

                  4) DESVIOS 1 e 2 — "PALPAVEL", MACD+ATR CANDLE A CANDLE
                     (nao raiz do tempo): quando o MACD ja confirma
                     direcao, os candles NAO sao independentes (reforcam
                     a mesma direcao) — a raiz do tempo (regra generica
                     de passeio aleatorio pra candles independentes)
                     amortece demais. Testado com dado real (2026-09-23,
                     Indice H1, candle das 09h->10h: fechamento 186.800 ->
                     189.405, maxima 190.140, um candle de ~3.3x o ATR):
                     projetando fechamento_atual + n*ATR na direcao que o
                     MACD ja apontava (hist positivo = alta), 3 passos
                     bateu quase exato no fechamento seguinte (189.548
                     vs 189.405 real, erro 0.08%) e 3.5 passos bateu quase
                     exato na maxima (190.006 vs 190.140 real, erro
                     0.07%). Por isso os desvios 1 e 2 usam ATR linear na
                     direcao do momentum (macd_hist>0 = alta), e tambem
                     calculam o lado CONTRARIO (mesma magnitude, direcao
                     oposta) pra quem quiser ver o cenario de reversao —
                     mas so o lado a favor do momentum tem
                     confirmado_macd=true. RESSALVA: validado com 1
                     evento real ate agora — nao assumir taxa de acerto
                     sem mais testes (registrado no changelog).

                  5) DESVIOS 3 e 4 — estatistico classico: ATR *
                     sqrt(candles_a_frente) em torno de media_base
                     (regra de passeio aleatorio padrao, adequada pra
                     horizontes mais longos/candles mais independentes).
                     Probabilidade de alcancar cada nivel = area da cauda
                     da normal padrao (1 - CDF(n), um lado), a formula
                     classica de z-score/desvio-padrao — nao vem da
                     regressao (a regressao so definiu o centro e o
                     horizonte), vem da distribuicao assumida.

                  6) CERTIFICACAO POR IFR (RSI): pra CADA nivel de desvio
                     (1 a 4, cima e baixo, dos 2 metodos), simula o preco
                     daquele nivel como se fosse o proximo fechamento e
                     recalcula o IFR(14) nesse cenario hipotetico. Se o
                     IFR simulado cair fora de 30-70, o nivel e
                     "esticado" (matematicamente possivel mas ja em zona
                     de sobrecompra/sobrevenda antes de chegar la) —
                     pedido do usuario: "usar RSI pra certificar que as
                     bandas estao dentro de 30 e 70".

                  7) CONSENSO MULTI-TIMEFRAME (1.1.0): pedido do usuario apos ver a
                     v1.0.0 mostrando as 6 TFs separadas — "nao precisa disso
                     projecao em 5 TF, faz duas tabelinhas so com Indice e
                     Dolar... o eixo x e a media que mais se repetir dentre as
                     tabelas dos TF". _consolidar() agrupa os media_base das
                     TFs que ficam proximos (TOLERANCIA_CONSENSO_PCT), pega o
                     MAIOR grupo (a "media que mais se repete") e usa a TF
                     mais curta desse grupo (TF_ORDEM) como referencia de
                     ATR/direcao/horizonte pros desvios em torno do centro
                     consolidado. O JSON de saida virou {"detalhe": [...] (as
                     12 combinacoes, mantido pra depuracao), "consolidado":
                     [...] (2 entradas, uma por ativo — o que o front usa)}.

                  8) ATIVOS EXTRA VIA config.json (1.2.0): pedido do usuario
                     depois de replicar a Curva de Treasurys/DP/Noticias na
                     view do Nasdaq — "tem que apresentar os valores apenas
                     para nasdaq" (o card estava mostrando Indice/Dolar la
                     tambem). ATIVOS_DESEJADOS (Indice/Dolar) virou so a base
                     FIXA; self.ativos = base + qualquer raiz em config.json
                     -> ativos_referencia_extra (ver _resolver_ativos_extra,
                     mesmo padrao de correl.py/vies_direcional.py). Nao
                     precisou resolver ticker vigente feito correl.py: a
                     pasta parquet/historicos/MTF/<raiz>/ ja e gravada por
                     RAIZ pro universo inteiro, entao a raiz do config.json E
                     o nome da pasta. Front (DesviosPainel.jsx) ganhou prop
                     `ativos` pra escolher quais blocos mostrar por view.

                  9) SEGUNDA FONTE DE EXTRA, SO PRO CARD DE JUROS (1.3.0):
                  pedido do usuario 2026-09-26 - "ve se tem alguma acao ou
                  ativo que reflete os juros americanos treasurys" -> achado
                  TLT/IEF/SHY no catalogo do terminal mt5stock (MetaQuotes-
                  Demo, ver verificar_mt5stock.py). Esses 3 nao entraram em
                  ativos_referencia_extra (a fonte de sempre) porque essa
                  mesma chave tambem alimenta vies_direcional.py, cujas
                  chaves viram VIEWS no menu dropdown do frontend (App.jsx
                  -> viewsExtra) - TLT/IEF/SHY sao um CARD dentro da view
                  usatec, nao uma view nova. Criada config.json ->
                  dp_ativos_extra, uma fonte irma so pro dp.py;
                  _resolver_ativos_extra() agora junta as duas (ver
                  docstring do metodo).

                  Le direto dos parquets de preco em MTF (mesma fonte de
                  last_indicadores_nac.py/indicadores_mtf.py), recalcula
                  so quando o mtime do parquet muda, grava double buffer —
                  mesmo padrao de todo o resto do projeto (last_nac.py,
                  last_indicadores_nac.py, yeldcurve.py).
Autor          : Julio Cesar Silvio Campanhola
Criado em      : 2026-09-23
Ultima edicao  : 2026-09-26
Versao         : 1.3.0
Projeto        : dashboard
Historico      : scripts_py/versoes/dp.md
"""

import importlib
import json
import math
import os
import time

try:
    pd = importlib.import_module("pandas")
    np = importlib.import_module("numpy")
except ImportError as exc:
    raise ImportError(
        "As dependencias pandas/numpy nao estao instaladas. "
        "Instale-as com: pip install pandas numpy pyarrow"
    ) from exc

from calculo_indicadores import calcular_macd, calcular_atr, calcular_ifr

ATIVOS_DESEJADOS = ["Indice", "Dolar"]
TIMEFRAMES_DESEJADOS = ["m15", "m30", "h1", "h4", "d1", "w1"]

# candles minimos desde a ponta pra marcar a projecao como "confiavel" —
# abaixo disso a reta e praticamente 2 pontos (ver decisao no papo com o
# usuario, 2026-09-23); ainda assim devolve o numero, so com confiavel=false.
MIN_CANDLES_CONFIAVEL = 3

MOMENTUM_N = (1, 2)     # desvios 1 e 2: MACD (direcao) + ATR (tamanho de candle), linear
ESTATISTICO_N = (3, 4)  # desvios 3 e 4: ATR * sqrt(tempo), normal padrao

# ordem das TFs da mais curta pra mais longa - usada pra escolher a TF de
# REFERENCIA dentro do grupo consolidado (ver _consolidar): a mais curta do
# grupo que concorda fornece ATR/direcao/horizonte, ja que misturar ATR de
# TFs com duracao de candle muito diferente (M15 vs W1) nao faz sentido.
TF_ORDEM = {tf: i for i, tf in enumerate(TIMEFRAMES_DESEJADOS)}

# margem (%) pra duas medias de TFs diferentes serem consideradas "a mesma
# regiao" no consenso multi-timeframe (ver _consolidar) - pedido do usuario
# (2026-09-23): "o eixo x e a media que mais se repetir dentre as tabelas
# dos TF" - agrupa as medias proximas, o maior grupo vence, os TFs fora do
# grupo (outliers, tipo perna recente/pouco confiavel) ficam de fora.
TOLERANCIA_CONSENSO_PCT = 0.5

PAUSA_LOOP = 1.0  # segundos entre cada checagem de mtime — so leitura de metadado, quase gratis


def _prob_alem(n):
    """Probabilidade (um lado, %) de um valor normal-padrao ficar alem de
    n desvios — formula classica (erfc), sem depender de scipy."""
    return 0.5 * math.erfc(n / math.sqrt(2)) * 100.0


def _certificado(ifr_valor):
    """True/False se o IFR simulado fica dentro da faixa 30-70 (nao
    esticado); None se o IFR nao pode ser calculado (serie curta demais)."""
    if ifr_valor is None or pd.isna(ifr_valor):
        return None
    return 30.0 <= ifr_valor <= 70.0


def _achar_perna_atual(hist):
    """Acha o inicio da perna atual do histograma = ultimo CRUZAMENTO DE
    ZERO (macd_hist muda de sinal), e dentro dela a PONTA (pico/vale,
    |valor| maximo). Ver docstring do modulo (item 1) pro raciocinio
    completo. Devolve um dict com "fase":
      - "cruzou_agora"   : sem cruzamento anterior na janela, ou cruzou
                            no ultimo candle (perna com <=1 candle) —
                            cedo demais pra qualquer projecao.
      - "indo_pra_ponta" : ja tem perna, mas ainda nao formou pico/vale
                            (ainda se afastando do zero) — cedo demais
                            pra projetar a volta.
      - "voltando"       : ja formou a ponta e esta voltando pro zero —
                            unico caso com "idx_ponta" preenchido, unico
                            que pode virar projecao (ver _projetar)."""
    n = len(hist)
    sinal_atual = np.sign(hist[-1])
    if sinal_atual == 0:
        return {"fase": "cruzou_agora"}

    idx_cruzamento = None
    for i in range(n - 2, 0, -1):
        if np.sign(hist[i]) != sinal_atual and np.sign(hist[i]) != 0:
            idx_cruzamento = i + 1
            break
    if idx_cruzamento is None or idx_cruzamento >= n - 1:
        return {"fase": "cruzou_agora"}

    perna = hist[idx_cruzamento:]
    idx_ponta_rel = int(np.argmax(np.abs(perna)))
    if idx_ponta_rel >= len(perna) - 1:
        return {"fase": "indo_pra_ponta", "candles_desde_cruzamento": len(perna) - 1}

    idx_ponta = idx_cruzamento + idx_ponta_rel
    return {
        "fase": "voltando",
        "idx_ponta": idx_ponta,
        "candles_desde_ponta": (n - 1) - idx_ponta,
    }


def _projetar_regressao(hist, close, idx_ponta):
    """Regressao linear na perna (da ponta ate agora), separada no
    histograma (acha candles_a_frente = em quantos candles cruza o zero)
    e no preco (acha o preco mais provavel naquele instante). None se a
    perna ja teria cruzado o zero (reta apontando pro passado — sem
    cruzamento futuro sob esta tendencia linear) ou se o histograma nao
    tem inclinacao (linhas paralelas)."""
    perna_h = hist[idx_ponta:]
    perna_c = close[idx_ponta:]
    n = len(perna_h)
    if n < 2:
        return None

    x = np.arange(n)
    a_h, b_h = np.polyfit(x, perna_h, 1)
    if abs(a_h) < 1e-9:
        return None
    x_zero = -b_h / a_h
    candles_a_frente = float(x_zero - (n - 1))
    if candles_a_frente <= 0:
        return None

    a_p, b_p = np.polyfit(x, perna_c, 1)
    preco_projetado = float(a_p * x_zero + b_p)
    return {"candles_a_frente": candles_a_frente, "preco_projetado": preco_projetado}


class ColetorDesviosPreco:
    """Recalcula a projecao de desvios (MACD/ATR/IFR) de Indice e Dolar em
    MTF direto dos parquets de preco, so quando o parquet muda — mesmo
    padrao de mtime-watch de last_indicadores_nac.py."""

    def __init__(self, base_dir=None):
        self.base_dir = base_dir or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        mtf_dir = os.path.join(self.base_dir, "parquet", "historicos", "MTF")
        output_dir = os.path.join(self.base_dir, "json", "last_json")
        self.output_path_a = os.path.join(output_dir, "dp_amostra_a.json")
        self.output_path_b = os.path.join(output_dir, "dp_amostra_b.json")
        self.stop_flag_path = os.path.join(self.base_dir, "parquet", "historicos", "_stop_last.flag")
        self.config_path = os.path.join(self.base_dir, "json", "config.json")
        os.makedirs(output_dir, exist_ok=True)

        # ATIVOS_DESEJADOS (Indice/Dolar) + qualquer ativo extra em config.json
        # -> ativos_referencia_extra (pedido do usuario 2026-09-25, mesmo
        # padrao ja usado em correl.py/vies_direcional.py: "replique esses
        # tres cards la" pra view do Nasdaq, so que com os NUMEROS do
        # Nasdaq, nao do Indice/Dolar). indicadores_mtf.py/historico.py ja
        # gravam parquet/historicos/MTF/<raiz>/<tf>.parquet pro universo
        # inteiro (nao so Indice/Dolar), entao um ativo extra so precisa
        # aparecer nessa lista pra ganhar sua propria projecao de desvios —
        # sem coleta nova nenhuma.
        self.ativos = list(ATIVOS_DESEJADOS) + self._resolver_ativos_extra()

        self.caminhos_preco = {
            (ativo, tf): os.path.join(mtf_dir, ativo, f"{tf}.parquet")
            for ativo in self.ativos
            for tf in TIMEFRAMES_DESEJADOS
        }

        self.ultimo_mtime = {}
        self.estado_atual = {}
        self._close_cache = {}  # (ativo, tf) -> serie de close valida, pra _consolidar montar os desvios em torno da media consolidada
        self._sujo = False
        self._proximo_arquivo = "a"

    def _resolver_ativos_extra(self):
        """Le config.json -> ativos_referencia_extra + dp_ativos_extra e
        devolve so as RAIZES (pedido do usuario 2026-09-25: lista fica no
        JSON, adicionar um ativo novo aqui e so uma linha no config, sem
        editar este script). Ao contrario de correl.py (que resolve o
        ticker VIGENTE), aqui nao ha vencimento pra resolver: as pastas de
        parquet/historicos/MTF/ ja sao gravadas por RAIZ (indicadores_mtf.py
        cobre o universo inteiro), entao a raiz do config.json E o nome da
        pasta direto.

        Duas fontes SEPARADAS de proposito (1.3.0, pedido do usuario
        2026-09-26 - card de juros TLT/IEF/SHY na view Nasdaq):
        ativos_referencia_extra tambem alimenta vies_direcional.py, cujas
        chaves viram os itens do MENU DROPDOWN de view no frontend
        (App.jsx -> viewsExtra). dp_ativos_extra e so pro dp.py - um ativo
        aqui vira um CARD dentro de uma view existente, nao uma view nova.
        Se TLT/IEF/SHY entrassem em ativos_referencia_extra, apareceriam
        como views fantasmas no menu (ver App.jsx/vies_direcional.py)."""
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
        except (OSError, json.JSONDecodeError):
            config = {}
        extras_config = config.get("ativos_referencia_extra", {})
        dp_extras_config = config.get("dp_ativos_extra", {})
        raizes = [info["raiz"] for info in extras_config.values()]
        raizes += [info["raiz"] for info in dp_extras_config.values() if info["raiz"] not in raizes]
        return raizes

    # ---------- calculo por combinacao ativo+tf ----------

    def _ifr_simulado(self, close, preco_hipotetico):
        serie = pd.concat([close, pd.Series([preco_hipotetico])], ignore_index=True)
        valor = calcular_ifr(serie).iloc[-1]
        return None if pd.isna(valor) else float(valor)

    def _montar_nivel(self, close, n, metodo, preco_cima, preco_baixo, prob_pct=None, confirmado_macd_cima=None, confirmado_macd_baixo=None):
        ifr_cima = self._ifr_simulado(close, preco_cima)
        ifr_baixo = self._ifr_simulado(close, preco_baixo)
        nivel = {
            "n": n,
            "metodo": metodo,
            "preco_cima": round(preco_cima, 2),
            "ifr_simulado_cima": ifr_cima,
            "certificado_cima": _certificado(ifr_cima),
            "preco_baixo": round(preco_baixo, 2),
            "ifr_simulado_baixo": ifr_baixo,
            "certificado_baixo": _certificado(ifr_baixo),
        }
        if prob_pct is not None:
            nivel["prob_pct"] = round(prob_pct, 4)
        if confirmado_macd_cima is not None:
            nivel["confirmado_macd_cima"] = confirmado_macd_cima
            nivel["confirmado_macd_baixo"] = confirmado_macd_baixo
        return nivel

    def _calcular_um(self, ativo, tf, caminho):
        df = pd.read_parquet(caminho)
        if df.empty:
            return None
        df = df.sort_values("time").reset_index(drop=True)
        close = df["close"]

        macd_df = calcular_macd(close)
        atr_serie = calcular_atr(df["high"], df["low"], close)
        base = pd.concat([close, macd_df], axis=1).dropna(subset=["macd_hist"]).reset_index(drop=True)
        if len(base) < MIN_CANDLES_CONFIAVEL + 2:
            return None  # aquecimento (MACD/sinal) ainda nao completou

        hist = base["macd_hist"].values
        close_valido = base["close"]
        self._close_cache[(ativo, tf)] = close_valido
        fechamento_atual = float(close_valido.iloc[-1])
        atr_atual = atr_serie.dropna()
        atr_atual = float(atr_atual.iloc[-1]) if len(atr_atual) else None
        macd_atual = float(base["macd"].iloc[-1])
        macd_sinal_atual = float(base["macd_sinal"].iloc[-1])
        macd_hist_atual = float(base["macd_hist"].iloc[-1])
        ifr_atual_serie = calcular_ifr(close_valido).dropna()
        ifr_atual = float(ifr_atual_serie.iloc[-1]) if len(ifr_atual_serie) else None

        direcao_momentum = "alta" if macd_hist_atual > 0 else ("baixa" if macd_hist_atual < 0 else "neutro")

        entrada = {
            "ativo": ativo,
            "tf": tf.upper(),
            "time": df["time"].iloc[-1],
            "fechamento_atual": round(fechamento_atual, 2),
            "atr": round(atr_atual, 2) if atr_atual is not None else None,
            "ifr_atual": round(ifr_atual, 1) if ifr_atual is not None else None,
            "macd": round(macd_atual, 2),
            "macd_sinal": round(macd_sinal_atual, 2),
            "macd_hist": round(macd_hist_atual, 2),
            "direcao_momentum": direcao_momentum,
            "perna": None,
            "media_base": None,
            "desvios": [],
        }

        # ---- desvios 1-2: MACD + ATR, linear na direcao do momentum (ver item 4) ----
        if atr_atual is not None and direcao_momentum != "neutro":
            sinal_dir = 1.0 if direcao_momentum == "alta" else -1.0
            for n in MOMENTUM_N:
                preco_favor = fechamento_atual + sinal_dir * n * atr_atual
                preco_contra = fechamento_atual - sinal_dir * n * atr_atual
                preco_cima = preco_favor if sinal_dir > 0 else preco_contra
                preco_baixo = preco_contra if sinal_dir > 0 else preco_favor
                entrada["desvios"].append(self._montar_nivel(
                    close_valido, n, "momentum_atr",
                    preco_cima, preco_baixo,
                    confirmado_macd_cima=(sinal_dir > 0),
                    confirmado_macd_baixo=(sinal_dir < 0),
                ))

        # ---- perna atual (item 1) + projecao (item 2) ----
        perna = _achar_perna_atual(hist)
        entrada["perna"] = perna

        if perna.get("fase") == "voltando":
            proj = _projetar_regressao(hist, close_valido.values, perna["idx_ponta"])
            if proj is not None:
                perna["candles_a_frente"] = round(proj["candles_a_frente"], 2)
                perna["preco_projetado"] = round(proj["preco_projetado"], 2)
                perna["confiavel"] = perna["candles_desde_ponta"] >= MIN_CANDLES_CONFIAVEL

                media_base = (proj["preco_projetado"] + fechamento_atual) / 2.0
                entrada["media_base"] = round(media_base, 2)

                # ---- desvios 3-4: estatistico, ATR * sqrt(tempo) em torno da media (item 5) ----
                if atr_atual is not None:
                    desvio_estat = atr_atual * math.sqrt(proj["candles_a_frente"])
                    for n in ESTATISTICO_N:
                        preco_cima = media_base + n * desvio_estat
                        preco_baixo = media_base - n * desvio_estat
                        entrada["desvios"].append(self._montar_nivel(
                            close_valido, n, "estatistico_normal",
                            preco_cima, preco_baixo,
                            prob_pct=_prob_alem(n),
                        ))

        return entrada

    # ---------- consenso multi-timeframe (ver _flush) ----------

    def _consolidar(self, ativo):
        """Junta as leituras das 6 TFs de um ativo num unico ponto de
        consenso — pedido do usuario (2026-09-23): "nao precisa disso
        projecao em 5 TF, faz duas tabelinhas so com Indice e Dolar... usa
        dentre todos os TF a regressao linear pra ver qual o mais provavel
        dos pontos" / "o eixo x e a media que mais se repetir dentre as
        tabelas dos TF". Metodo (clustering, nao regressao no eixo TF —
        TF nao e uma variavel continua, entao "a media que mais se repete"
        vira: agrupa os media_base de cada TF que estao proximos uns dos
        outros (dentro de TOLERANCIA_CONSENSO_PCT), pega o MAIOR grupo — o
        maior numero de TFs concordando na mesma regiao de preco — e usa
        a media desse grupo como o centro consolidado. As TFs fora do
        grupo vencedor (outliers — ex: ponta recente/pouco confiavel, ou
        uma TF numa perna totalmente diferente) ficam de fora do calculo
        mas sao listadas em "tfs_fora_consenso" pra transparencia. Os
        desvios em torno do centro consolidado usam ATR/direcao/horizonte
        da TF MAIS CURTA dentro do grupo vencedor (TF_ORDEM) — misturar
        ATR de TFs com duracao de candle muito diferente (M15 vs W1) nao
        faz sentido; a mais curta do grupo que concorda e a referencia
        mais "acionavel". Devolve None se nenhuma TF do ativo tem
        media_base calculada ainda (todas em cruzou_agora/indo_pra_ponta)."""
        disponiveis = []
        for tf in TIMEFRAMES_DESEJADOS:
            chave = (ativo, tf)
            entrada = self.estado_atual.get(chave)
            if entrada is not None and entrada.get("media_base") is not None:
                disponiveis.append((tf, entrada))

        if not disponiveis:
            return None

        valores = [e["media_base"] for _, e in disponiveis]
        melhor_grupo = []
        for i, v in enumerate(valores):
            if v == 0:
                continue
            grupo = [j for j, x in enumerate(valores) if abs(x - v) / abs(v) * 100.0 <= TOLERANCIA_CONSENSO_PCT]
            if len(grupo) > len(melhor_grupo):
                melhor_grupo = grupo

        if not melhor_grupo:
            return None

        tfs_grupo = [disponiveis[j][0] for j in melhor_grupo]
        valores_grupo = [disponiveis[j][1]["media_base"] for j in melhor_grupo]
        media_consolidada = sum(valores_grupo) / len(valores_grupo)

        tf_ref = min(tfs_grupo, key=lambda tf: TF_ORDEM[tf])
        entrada_ref = self.estado_atual[(ativo, tf_ref)]
        close_ref = self._close_cache.get((ativo, tf_ref))
        atr_ref = entrada_ref.get("atr")
        direcao_ref = entrada_ref.get("direcao_momentum")
        perna_ref = entrada_ref.get("perna") or {}
        candles_a_frente_ref = perna_ref.get("candles_a_frente")

        desvios = []
        if close_ref is not None and atr_ref is not None and direcao_ref != "neutro":
            sinal_dir = 1.0 if direcao_ref == "alta" else -1.0

            for n in MOMENTUM_N:
                preco_favor = media_consolidada + sinal_dir * n * atr_ref
                preco_contra = media_consolidada - sinal_dir * n * atr_ref
                preco_cima = preco_favor if sinal_dir > 0 else preco_contra
                preco_baixo = preco_contra if sinal_dir > 0 else preco_favor
                desvios.append(self._montar_nivel(
                    close_ref, n, "momentum_atr",
                    preco_cima, preco_baixo,
                    confirmado_macd_cima=(sinal_dir > 0),
                    confirmado_macd_baixo=(sinal_dir < 0),
                ))

            if candles_a_frente_ref:
                desvio_estat = atr_ref * math.sqrt(candles_a_frente_ref)
                for n in ESTATISTICO_N:
                    preco_cima = media_consolidada + n * desvio_estat
                    preco_baixo = media_consolidada - n * desvio_estat
                    desvios.append(self._montar_nivel(
                        close_ref, n, "estatistico_normal",
                        preco_cima, preco_baixo,
                        prob_pct=_prob_alem(n),
                    ))

        return {
            "ativo": ativo,
            "media_consolidada": round(media_consolidada, 2),
            "tf_referencia": tf_ref.upper(),
            "tfs_no_consenso": [t.upper() for t in tfs_grupo],
            "tfs_fora_consenso": [t.upper() for t, _ in disponiveis if t not in tfs_grupo],
            "fechamento_atual": entrada_ref.get("fechamento_atual"),
            "direcao_momentum": direcao_ref,
            "desvios": desvios,
        }

        # ---------- varredura (so mtime mudou) + flush (double buffer) ----------

    def _varrer(self):
        for chave, caminho in self.caminhos_preco.items():
            ativo, tf = chave
            try:
                mtime = os.path.getmtime(caminho)
            except OSError:
                continue

            if self.ultimo_mtime.get(chave) == mtime:
                continue

            try:
                entrada = self._calcular_um(ativo, tf, caminho)
            except Exception as exc:
                print(f"[dp] erro calculando {ativo}/{tf}, seguindo: {exc}")
                continue

            self.ultimo_mtime[chave] = mtime
            if entrada is None:
                continue

            self.estado_atual[chave] = entrada
            self._sujo = True

    def _flush(self):
        if not self._sujo:
            return

        detalhe = []
        for linha in self.estado_atual.values():
            registro = dict(linha)
            registro["time"] = linha["time"].isoformat()
            detalhe.append(registro)

        consolidado = []
        for ativo in self.ativos:
            item = self._consolidar(ativo)
            if item is not None:
                consolidado.append(item)

        saida = {"detalhe": detalhe, "consolidado": consolidado}

        alvo = self.output_path_a if self._proximo_arquivo == "a" else self.output_path_b
        tmp_path = alvo + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(saida, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, alvo)
        self._proximo_arquivo = "b" if self._proximo_arquivo == "a" else "a"

        print(f"[dp] atualizados ({len(detalhe)} combinacoes, {len(consolidado)} consolidados) -> {os.path.basename(alvo)}")
        self._sujo = False

    def executar(self):
        print(f"[dp] dp.py rodando (Ctrl+C pra parar) — projecao de desvios MACD/ATR/IFR MTF ({', '.join(self.ativos)})")

        try:
            while not os.path.exists(self.stop_flag_path):
                try:
                    self._varrer()
                except Exception as exc:
                    print(f"[dp] erro na varredura, seguindo pro proximo ciclo: {exc}")
                try:
                    self._flush()
                except Exception as exc:
                    print(f"[dp] erro no flush, tentando de novo no proximo ciclo: {exc}")
                time.sleep(PAUSA_LOOP)
            print("[dp] sinal de parada recebido")
        except KeyboardInterrupt:
            print("[dp] Ctrl+C recebido")
        finally:
            self._flush()


if __name__ == "__main__":
    ColetorDesviosPreco().executar()
