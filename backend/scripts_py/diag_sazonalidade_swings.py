"""
Nome do script : diag_sazonalidade_swings.py
Descricao      : Constroi o dataset "swing -> estado MTF" (topo/fundo
                  intradiario cruzado com MACD/IFR ja calculados) pra TODO
                  o universo internacional/de contexto, nao so Indice/Dolar
                  mais (pedido do usuario 2026-09-27: o cenario de
                  Indice/Dolar nasce da leitura cruzada do universo inteiro -
                  moedas, indices continuos, commodities, treasury,
                  Nasdaq-100 - entao o dataset precisa cobrir esse
                  universo, nao so o proprio ativo operavel).

                  Escopo original (Indice/Dolar, so sazonalidade de horario,
                  v1.0.0 a v1.2.0): hipotese do usuario - topos e fundos
                  intradiarios nao sao independentes no horario em que
                  acontecem; pode existir uma "janela ima" onde os dois
                  pontos de uma perna caem na mesma janela de horario,
                  e/ou um "ciclo" dominante de repeticao (duracao entre um
                  topo e o proximo, ou uma minima e a proxima). Isso
                  continua calculado (METODO PARTE 1) - so deixou de ser
                  exclusivo de Indice/Dolar.

                  v2.0.0 (2026-09-27) muda o proposito do script: alem da
                  sazonalidade de horario, cada ponto de swing agora e
                  cruzado com o ESTADO do MACD/IFR (M15) e do IFR (M5) no
                  MESMO instante (ja calculados por indicadores_mtf.py,
                  nada e recalculado aqui) - a "jogada" descrita pelo
                  usuario: MACD M15 abaixo/acima de zero confirma regime
                  de baixa/alta; dentro da janela de horario onde
                  fundo/topo e mais provavel, so falta achar O NIVEL DE
                  PRECO (isso fica pra proxima etapa: ARCH/GARCH,
                  regressao, ARIMA/SARIMAX, XGBoost/LightGBM/CatBoost -
                  NENHUM desses modelos entra aqui, este script so monta o
                  dataset rotulado que vai alimentar eles).

                  METODO PARTE 1 - swings (por ativo, M15):
                  1) Le M15 de preco (high/low) direto do parquet MTF, ja
                     concatenando subpastas de vencimento (MM-AAAA) quando
                     existirem, dedup por time - mesmo padrao de
                     situacao_pre_abertura.py.
                  2) Detecta swings locais (fractal classico N=2: candle e
                     topo se sua maxima e >= a maxima dos N candles antes
                     E depois; fundo e o espelho com minima).
                  3) Filtra pernas ALTERNADAS (topo->fundo ou fundo->topo,
                     pontos consecutivos) e agrega por janela de horario
                     (ranking_janelas_ima) + histograma marginal
                     topo/fundo isolado.
                  4) Duracao entre swings do MESMO tipo (topo->topo,
                     fundo->fundo): NAO importa se o preco subiu ou desceu
                     entre os dois pontos (pedido explicito do usuario), so
                     a distancia em minutos. v2.0.0 TROCA o filtro de
                     outlier: v1.2.0 descartava par com datas de
                     calendario diferentes (funciona pra ativo de sessao
                     unica tipo B3, mas quebra pra ativo continuo/24h tipo
                     forex, que agora entra no escopo) - o novo filtro
                     descarta duracao > LIMITE_MULTIPLO_MEDIANA vezes a
                     mediana BRUTA da propria serie (gap de fim de
                     semana/rollover), generalizando pra qualquer
                     estrutura de pregao sem assumir horario de sessao.

                  METODO PARTE 2 - cruzamento com MTF (novo, v2.0.0):
                  5) Le indicadores/m15.parquet (ifr, atr, macd, macd_sinal,
                     macd_hist) e indicadores/m5.parquet (so ifr) do mesmo
                     ativo - ja calculados por indicadores_mtf.py, nao
                     recalcula nada aqui.
                  6) Cada ponto de swing ganha o valor do MACD/IFR/ATR M15
                     no MESMO candle (merge exato por time) e o ultimo IFR
                     M5 conhecido ATE aquele instante (merge_asof
                     backward).
                  7) Validacao rapida (so um primeiro numero antes de
                     partir pra modelo, nao e veredito): % de fundo com
                     MACD M15 < 0, % de topo com MACD M15 > 0, % de fundo
                     com IFR M5 <= 30, % de topo com IFR M5 >= 70, e a
                     combinacao dos dois - por ativo E agregado no
                     universo inteiro.

                  Universo (montar_universo(), le direto do config.json
                  pra nao duplicar a lista aqui): nacionais (so Indice/Dolar -
                  FRP0/FRP1 fora, ticker de rolagem/spread sem tratamento
                  no projeto ainda) + moedas_continuo + indices_continuo +
                  commodities_internacionais + treasury_etf_eua +
                  acoes_nasdaq100 + vencimento_americano SEM Dolar/Indice
                  (mesma logica ja usada em vies_direcional.py: sao o
                  MESMO ativo que Indice/Dolar via corretora internacional, correlacao
                  tautologica - aqui o motivo e o mesmo, nao faz sentido
                  cruzar Indice com o proprio Indice disfarcado de Indice).

                  Saida:
                  - json/diag_sazonalidade_swings.json: resumo por ativo
                    (sazonalidade de horario, duracao, validacao MACD/IFR)
                    - sem os pontos individuais, so pra leitura humana.
                  - parquet/calculos/sazonalidade_swings_universo.parquet:
                    dataset achatado, uma linha por ponto de swing (raiz,
                    tipo, time, preco, macd_m15, macd_sinal_m15,
                    macd_hist_m15, ifr_m15, atr_m15, ifr_m5) - e o insumo
                    pra proxima etapa (modelagem de preco/timing).

                  Ainda standalone (nao registrado no main.py) - roda sob
                  demanda com `python diag_sazonalidade_swings.py`.
Autor          : Julio Cesar Silvio Campanhola
Criado em      : 2026-09-26
Ultima edicao  : 2026-09-27
Versao         : 2.0.0
Projeto        : dashboard
Historico      : scripts_py/versoes/diag_sazonalidade_swings.md
"""

import glob
import json
import os

import pandas as pd

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MTF_DIR = os.path.join(BASE_DIR, "parquet", "historicos", "MTF")
CONFIG_PATH = os.path.join(BASE_DIR, "json", "config.json")
SAIDA_JSON_PATH = os.path.join(BASE_DIR, "json", "diag_sazonalidade_swings.json")
SAIDA_PARQUET_PATH = os.path.join(BASE_DIR, "parquet", "calculos", "sazonalidade_swings_universo.parquet")

TF_SWING = "m15"
N_SWING = 2  # fractal classico: janela de 2*N_SWING+1 = 5 candles M15 (75min)
BUCKET_MINUTOS = 15
BUCKET_DURACAO_MINUTOS = 15
LIMITE_MULTIPLO_MEDIANA = 5  # descarta duracao > 5x a mediana bruta (gap de fim de semana/rollover)

COLUNAS_INDICADOR_M15 = ["ifr", "atr", "macd", "macd_sinal", "macd_hist"]
COLUNAS_INDICADOR_M5 = ["ifr"]

# mesma logica ja usada em vies_direcional.py: sao o MESMO ativo que
# Indice/Dolar via corretora internacional (correlacao tautologica) - fora do universo
RAIZES_EXCLUIDAS_POR_TAUTOLOGIA = {"Dolar", "Indice"}


def montar_universo(config_path=CONFIG_PATH):
    with open(config_path, encoding="utf-8") as f:
        ativos = json.load(f)["ativos"]

    grupos = [
        ativos["nacionais"][:2],  # so Indice, Dolar
        ativos["moedas_continuo"],
        ativos["indices_continuo"],
        ativos["commodities_internacionais"],
        ativos["treasury_etf_eua"],
        ativos["acoes_nasdaq100"],
        [r for r in ativos["vencimento_americano"] if r not in RAIZES_EXCLUIDAS_POR_TAUTOLOGIA],
    ]

    universo, vistos = [], set()
    for grupo in grupos:
        for raiz in grupo:
            if raiz not in vistos:
                vistos.add(raiz)
                universo.append(raiz)
    return universo


def _listar_arquivos(pasta_raiz, subpasta, nome_arquivo):
    """Lista os parquets de uma raiz (direto na pasta, ou em qualquer
    subpasta de vencimento MM-AAAA), com ou sem a subpasta 'indicadores'
    no meio - mesmo padrao de concatenacao usado em
    situacao_pre_abertura.py (corretora internacional pode segmentar por vencimento)."""
    partes_meio = [subpasta] if subpasta else []
    caminho_direto = os.path.join(pasta_raiz, *partes_meio, nome_arquivo)
    caminho_vencimento = os.path.join(
        pasta_raiz, "[0-9][0-9]-[0-9][0-9][0-9][0-9]", *partes_meio, nome_arquivo
    )
    return sorted(glob.glob(caminho_direto)) + sorted(glob.glob(caminho_vencimento))


def _carregar_concatenado(raiz, subpasta, nome_arquivo, colunas):
    pasta_raiz = os.path.join(MTF_DIR, raiz)
    arquivos = _listar_arquivos(pasta_raiz, subpasta, nome_arquivo)
    if not arquivos:
        return None

    partes = [pd.read_parquet(a, columns=colunas) for a in arquivos]
    df = pd.concat(partes, ignore_index=True).drop_duplicates(subset="time")
    # normaliza resolucao do timestamp (preco vem em ns, indicadores em us
    # dependendo de quem gravou o parquet) - senao merge/merge_asof por
    # "time" quebra com "incompatible merge keys"
    df["time"] = pd.to_datetime(df["time"], utc=True).astype("datetime64[ns, UTC]")
    return df.sort_values("time").reset_index(drop=True)


def carregar_precos(raiz, tf=TF_SWING):
    return _carregar_concatenado(raiz, None, f"{tf}.parquet", ["time", "high", "low"])


def carregar_indicadores(raiz, tf, colunas):
    return _carregar_concatenado(raiz, "indicadores", f"{tf}.parquet", ["time"] + colunas)


def truncar_horario(hhmm_minutos, bucket):
    return (hhmm_minutos // bucket) * bucket


def minutos_do_dia(timestamp):
    return timestamp.hour * 60 + timestamp.minute


def fmt_janela(minutos):
    return f"{minutos // 60:02d}:{minutos % 60:02d}"


def detectar_swings(df, n=N_SWING):
    """Fractal classico: candle i e topo se high[i] >= high de TODOS os n
    candles antes e depois (e estritamente maior que pelo menos um deles,
    pra nao marcar platos inteiros); fundo e o espelho com low."""
    highs = df["high"].to_numpy()
    lows = df["low"].to_numpy()
    tempos = df["time"].to_numpy()

    pontos = []
    total = len(df)
    for i in range(n, total - n):
        janela_high = highs[i - n : i + n + 1]
        janela_low = lows[i - n : i + n + 1]

        if highs[i] >= janela_high.max() and highs[i] > janela_high.min():
            pontos.append({"tipo": "topo", "time": pd.Timestamp(tempos[i]), "preco": float(highs[i])})
        elif lows[i] <= janela_low.min() and lows[i] < janela_low.max():
            pontos.append({"tipo": "fundo", "time": pd.Timestamp(tempos[i]), "preco": float(lows[i])})

    return pontos


def formar_pernas_alternadas(pontos):
    pernas = []
    for a, b in zip(pontos, pontos[1:]):
        if a["tipo"] != b["tipo"]:
            pernas.append((a, b))
    return pernas


def analisar_duracoes(pontos, tipo):
    """Duracao (min) entre uma ocorrencia de `tipo` e a PROXIMA do MESMO
    tipo - preco/direcao entre os dois pontos e irrelevante, so a
    distancia no tempo. Descarta duracao > LIMITE_MULTIPLO_MEDIANA vezes a
    mediana bruta da propria serie (gap de fim de semana/rollover) -
    generaliza pra qualquer estrutura de pregao (sessao unica tipo B3, ou
    continua tipo forex/CFD 24h)."""
    filtrados = [p for p in pontos if p["tipo"] == tipo]
    brutas = [(b["time"] - a["time"]).total_seconds() / 60 for a, b in zip(filtrados, filtrados[1:])]

    if not brutas:
        return {"n": 0, "media_min": None, "mediana_min": None,
                "moda_bucket_min": None, "histograma_ordenado": []}

    mediana_bruta = pd.Series(brutas).median()
    limite = mediana_bruta * LIMITE_MULTIPLO_MEDIANA
    duracoes = [d for d in brutas if d <= limite] or brutas

    serie = pd.Series(duracoes)
    histograma = {}
    for d in duracoes:
        bucket = int(d // BUCKET_DURACAO_MINUTOS) * BUCKET_DURACAO_MINUTOS
        histograma[bucket] = histograma.get(bucket, 0) + 1
    moda_bucket = max(histograma.items(), key=lambda kv: kv[1])[0]

    return {
        "n": len(duracoes),
        "n_descartados_gap": len(brutas) - len(duracoes),
        "media_min": round(float(serie.mean()), 1),
        "mediana_min": round(float(serie.median()), 1),
        "moda_bucket_min": f"{moda_bucket}-{moda_bucket + BUCKET_DURACAO_MINUTOS}",
        "moda_bucket_contagem": histograma[moda_bucket],
        "moda_bucket_pct_do_total": round(histograma[moda_bucket] / len(duracoes) * 100, 1),
        "histograma_ordenado": sorted(histograma.items(), key=lambda kv: -kv[1])[:8],
    }


def enriquecer_pontos(pontos, ind_m15, ind_m5):
    """Anexa o MACD/IFR/ATR M15 (mesmo instante, merge exato) e o ultimo
    IFR M5 conhecido ATE o instante (merge_asof backward) a cada ponto de
    swing. So anexa o dado bruto - nenhum filtro/regra aplicado aqui."""
    colunas_saida = ["tipo", "time", "preco", "macd_m15", "macd_sinal_m15",
                      "macd_hist_m15", "ifr_m15", "atr_m15", "ifr_m5"]
    if not pontos:
        return pd.DataFrame(columns=colunas_saida)

    df = pd.DataFrame(pontos).sort_values("time").reset_index(drop=True)
    df["time"] = pd.to_datetime(df["time"], utc=True).astype("datetime64[ns, UTC]")

    if ind_m15 is not None:
        df = df.merge(
            ind_m15.rename(columns={"ifr": "ifr_m15", "atr": "atr_m15", "macd": "macd_m15",
                                     "macd_sinal": "macd_sinal_m15", "macd_hist": "macd_hist_m15"}),
            on="time", how="left",
        )
    else:
        for col in ("macd_m15", "macd_sinal_m15", "macd_hist_m15", "ifr_m15", "atr_m15"):
            df[col] = None

    if ind_m5 is not None:
        ind_m5_renom = ind_m5.rename(columns={"ifr": "ifr_m5"}).sort_values("time")
        df = pd.merge_asof(df, ind_m5_renom, on="time", direction="backward")
    else:
        df["ifr_m5"] = None

    return df


def calcular_validacao(df_enriquecido):
    """Primeiro numero (leitura crua, nao e modelo) de quanto a 'jogada'
    do usuario ja se sustenta sozinha: MACD M15 abaixo/acima de zero e
    IFR M5 em 30/70 concordando com o tipo de swing."""

    def taxa_pct(serie_bool):
        serie_bool = serie_bool.dropna()
        if len(serie_bool) == 0:
            return None
        return round(float(serie_bool.mean()) * 100, 1)

    fundos = df_enriquecido[df_enriquecido["tipo"] == "fundo"]
    topos = df_enriquecido[df_enriquecido["tipo"] == "topo"]

    fundos_macd = fundos.dropna(subset=["macd_m15"])
    topos_macd = topos.dropna(subset=["macd_m15"])
    fundos_rsi = fundos.dropna(subset=["ifr_m5"])
    topos_rsi = topos.dropna(subset=["ifr_m5"])
    fundos_ambos = fundos.dropna(subset=["macd_m15", "ifr_m5"])
    topos_ambos = topos.dropna(subset=["macd_m15", "ifr_m5"])

    return {
        "n_fundos_com_macd": len(fundos_macd),
        "n_topos_com_macd": len(topos_macd),
        "fundo_macd_m15_negativo_pct": taxa_pct(fundos_macd["macd_m15"] < 0) if len(fundos_macd) else None,
        "topo_macd_m15_positivo_pct": taxa_pct(topos_macd["macd_m15"] > 0) if len(topos_macd) else None,
        "fundo_ifr_m5_oversold_le30_pct": taxa_pct(fundos_rsi["ifr_m5"] <= 30) if len(fundos_rsi) else None,
        "topo_ifr_m5_overbought_ge70_pct": taxa_pct(topos_rsi["ifr_m5"] >= 70) if len(topos_rsi) else None,
        "fundo_confirmado_macd_e_ifr_pct": (
            taxa_pct((fundos_ambos["macd_m15"] < 0) & (fundos_ambos["ifr_m5"] <= 30)) if len(fundos_ambos) else None
        ),
        "topo_confirmado_macd_e_ifr_pct": (
            taxa_pct((topos_ambos["macd_m15"] > 0) & (topos_ambos["ifr_m5"] >= 70)) if len(topos_ambos) else None
        ),
    }


def analisar_raiz(raiz):
    df_precos = carregar_precos(raiz)
    if df_precos is None or len(df_precos) < (2 * N_SWING + 1):
        return None

    pontos = detectar_swings(df_precos)
    pernas = formar_pernas_alternadas(pontos)

    marginal_topo, marginal_fundo = {}, {}
    for p in pontos:
        janela = truncar_horario(minutos_do_dia(p["time"]), BUCKET_MINUTOS)
        alvo = marginal_topo if p["tipo"] == "topo" else marginal_fundo
        alvo[janela] = alvo.get(janela, 0) + 1

    toca, ima = {}, {}
    for a, b in pernas:
        janela_a = truncar_horario(minutos_do_dia(a["time"]), BUCKET_MINUTOS)
        janela_b = truncar_horario(minutos_do_dia(b["time"]), BUCKET_MINUTOS)
        toca[janela_a] = toca.get(janela_a, 0) + 1
        if janela_b != janela_a:
            toca[janela_b] = toca.get(janela_b, 0) + 1
        if janela_a == janela_b:
            ima[janela_a] = ima.get(janela_a, 0) + 1

    ranking = []
    for janela, n_ima in sorted(ima.items(), key=lambda kv: kv[1], reverse=True):
        n_toca = toca.get(janela, 0)
        ranking.append({
            "janela": fmt_janela(janela),
            "pernas_ima_mesma_janela": n_ima,
            "pernas_que_tocam_essa_janela": n_toca,
            "taxa_ima_sobre_toca_pct": round(n_ima / n_toca * 100, 1) if n_toca else None,
            "pct_do_total_de_pernas": round(n_ima / len(pernas) * 100, 1) if pernas else None,
        })

    duracao_topo_topo = analisar_duracoes(pontos, "topo")
    duracao_fundo_fundo = analisar_duracoes(pontos, "fundo")

    ind_m15 = carregar_indicadores(raiz, "m15", COLUNAS_INDICADOR_M15)
    ind_m5 = carregar_indicadores(raiz, "m5", COLUNAS_INDICADOR_M5)
    df_enriquecido = enriquecer_pontos(pontos, ind_m15, ind_m5)
    validacao = calcular_validacao(df_enriquecido)

    df_enriquecido = df_enriquecido.copy()
    df_enriquecido.insert(0, "raiz", raiz)

    resumo = {
        "raiz": raiz,
        "candles_m15": len(df_precos),
        "periodo": {"inicio": str(df_precos["time"].min()), "fim": str(df_precos["time"].max())},
        "swings_detectados": len(pontos),
        "pernas_alternadas": len(pernas),
        "ranking_janelas_ima": ranking,
        "marginal_topo": {fmt_janela(k): v for k, v in sorted(marginal_topo.items(), key=lambda kv: -kv[1])},
        "marginal_fundo": {fmt_janela(k): v for k, v in sorted(marginal_fundo.items(), key=lambda kv: -kv[1])},
        "duracao_topo_topo_min": duracao_topo_topo,
        "duracao_fundo_fundo_min": duracao_fundo_fundo,
        "validacao_direcional": validacao,
    }
    return resumo, df_enriquecido


def main():
    universo = montar_universo()
    print(f"[diag_sazonalidade_swings] universo: {len(universo)} ativos")

    relatorio = {}
    datasets = []

    for raiz in universo:
        try:
            resultado = analisar_raiz(raiz)
        except Exception as exc:
            print(f"AVISO: falha em {raiz}: {exc}")
            continue

        if resultado is None:
            print(f"AVISO: sem dado M15 suficiente pra {raiz}, pulando")
            continue

        resumo, df_enriquecido = resultado
        relatorio[raiz] = resumo
        datasets.append(df_enriquecido)

        v = resumo["validacao_direcional"]
        print(
            f"{raiz:10s} swings={resumo['swings_detectados']:4d} "
            f"pernas={resumo['pernas_alternadas']:4d} | "
            f"fundo: macd={v['fundo_macd_m15_negativo_pct']}% rsi={v['fundo_ifr_m5_oversold_le30_pct']}% "
            f"ambos={v['fundo_confirmado_macd_e_ifr_pct']}% | "
            f"topo: macd={v['topo_macd_m15_positivo_pct']}% rsi={v['topo_ifr_m5_overbought_ge70_pct']}% "
            f"ambos={v['topo_confirmado_macd_e_ifr_pct']}%"
        )

    os.makedirs(os.path.dirname(SAIDA_JSON_PATH), exist_ok=True)
    with open(SAIDA_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(relatorio, f, ensure_ascii=False, indent=2)
    print(f"\n[diag_sazonalidade_swings] resumo por ativo salvo em {SAIDA_JSON_PATH}")

    if datasets:
        dataset_final = pd.concat(datasets, ignore_index=True)
        os.makedirs(os.path.dirname(SAIDA_PARQUET_PATH), exist_ok=True)
        dataset_final.to_parquet(SAIDA_PARQUET_PATH, index=False)
        print(
            f"[diag_sazonalidade_swings] dataset ({len(dataset_final)} pontos, "
            f"{len(datasets)} ativos) salvo em {SAIDA_PARQUET_PATH}"
        )

        fundos = dataset_final[dataset_final["tipo"] == "fundo"].dropna(subset=["macd_m15", "ifr_m5"])
        topos = dataset_final[dataset_final["tipo"] == "topo"].dropna(subset=["macd_m15", "ifr_m5"])
        if len(fundos):
            taxa_fundo = round(((fundos["macd_m15"] < 0) & (fundos["ifr_m5"] <= 30)).mean() * 100, 1)
            print(f"\n[agregado universo] fundo confirmado (macd<0 E ifr_m5<=30): {taxa_fundo}% de {len(fundos)} fundos")
        if len(topos):
            taxa_topo = round(((topos["macd_m15"] > 0) & (topos["ifr_m5"] >= 70)).mean() * 100, 1)
            print(f"[agregado universo] topo confirmado (macd>0 E ifr_m5>=70): {taxa_topo}% de {len(topos)} topos")


if __name__ == "__main__":
    main()
