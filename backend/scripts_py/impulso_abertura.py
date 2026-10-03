"""
Nome do script : impulso_abertura.py
Descricao      : Deteccao do "impulso de abertura" do Indice e do Dolar --
                  primeiro movimento direcional relevante apos a abertura
                  do pregao (09:00), com magnitude e duracao proprias de
                  cada dia (NAO uma janela fixa). Pedido do usuario
                  2026-09-30, discutindo como transformar causalidade de
                  Granger em algo acionavel: "quero ver numeros... o
                  mercado vai abrir amanha, quanto estaria valendo tanto
                  indice quanto dolar?" e depois "este valor nao ira se
                  referir ao agora e sim ao primeiro impulso as 09:00,
                  hoje por exemplo o ativo Indice andou 1,40% para cima no
                  intraday nos primeiros minutos da manha, e este 1,40%
                  que quero saber se vai acontecer ou nao" -- e mais tarde,
                  confirmando que a janela deveria ser adaptativa por dia
                  e nao fixa: "nao gostaria que fosse uma janela fixa, mas
                  sim uma media de horario de janela... acho a adaptativa
                  atraente".

                  Algoritmo (por dia, por ativo):
                  1. Preco de abertura = open do primeiro candle M1 do dia
                     (dias com abertura fora de 09:00-09:10 sao
                     descartados -- gap de coleta, nao abertura real).
                  2. Anda candle a candle dentro de uma janela de ate
                     JANELA_MAX_MIN minutos (teto de seguranca, nao o
                     resultado -- so evita que um dia de tendencia forte
                     vire o dia inteiro "impulso de abertura").
                  3. So passa a rastrear uma direcao quando o retorno
                     acumulado desde a abertura cruza LIMIAR_RUIDO_PCT
                     (limiar por ativo, calibrado por volatilidade M1
                     tipica de cada um -- ver justificativa abaixo). Antes
                     disso e ruido de bid/ask, nao impulso.
                  4. Uma vez com direcao definida, guarda o extremo (maior
                     avanco naquela direcao) e a hora em que ele ocorreu.
                  5. O impulso e dado como concluido quando o preco devolve
                     RETRACAO_CONFIRMA_PCT (30%) do extremo -- reversao
                     real confirma que aquele pico foi o "primeiro
                     impulso", nao so mais um candle de uma tendencia que
                     ainda vai continuar. Se a janela acabar sem essa
                     devolucao, o dia fica marcado "aberto" (tendencia
                     ainda em curso no fim da janela de seguranca -- o
                     extremo/horario registrado e o melhor disponivel ate
                     ali, nao o fim do movimento).

                  Calibracao dos limiares (2026-09-30, 123 dias de M1 via
                  historico.py --reforcar M1:180 --so Indice,Dolar,...):
                  volatilidade M1 tipica dentro do pregao (09h-18h) ficou
                  em ~0.018%/candle (mediana) pro Indice e ~0.010%/candle
                  pro Dolar -- LIMIAR_RUIDO_PCT foi calibrado bem acima
                  disso (0.15% Indice, 0.08% Dolar, ~8x a mediana) pra exigir
                  um movimento genuino antes de comecar a rastrear, nao
                  qualquer oscilacao de 1 candle. Com esses valores, 100%
                  dos 123 dias tiveram impulso detectado (nenhum ficou sem
                  cruzar o limiar), duracao mediana de 5 minutos (Indice e
                  Dolar), p90 em ~30min (Indice) e ~23min (Dolar), e so 14/123
                  (Indice) e 3/123 (Dolar) dias ficaram "abertos" (tendencia
                  sem reversao confirmada dentro da janela de seguranca).
                  Direcao (alta/baixa) ficou equilibrada nos dois ativos
                  (sem vies estrutural do algoritmo).

                  Isso e SO a deteccao/rotulagem do alvo historico (Task
                  #7 do estudo de impulso) -- ainda nao e previsao. A
                  previsao (regredir o overnight dos preditores causais
                  contra magnitude_pct/duracao_min daqui) e o proximo
                  passo, depois de montar o dataset de preditores
                  overnight (ver causalidade.py pra quem tem causa_indice/
                  causa_dolar=True).

                  Grava em parquet/calculos/impulsoAbertura.parquet (uma
                  linha por dia por ativo, ativo em {"Indice","Dolar"}).

                  1.1.0 (2026-09-30): campo novo velocidade_pct_min --
                  pergunta do usuario: "como podemos saber que o movimento
                  e um impulso? tamanho do candle vs tempo? no M1?".
                  Resposta encontrada testando contra o dado real: o que
                  importa nao e o tamanho de um candle isolado (quase todo
                  dia tem pelo menos 1 candle bem maior que o normal logo
                  na abertura -- e um leilao de abertura, e esperado), e
                  sim a VELOCIDADE MEDIA do trajeto inteiro ate o pico
                  (magnitude_pct / duracao_min) -- um "impulso de verdade"
                  e um movimento RAPIDO, nao so um movimento que acabou
                  indo longe. velocidade_pct_min = |magnitude_pct| /
                  max(duracao_min, 1) (o candle de abertura conta como 1
                  minuto decorrido, nunca 0, senao a divisao explode).
                  velocidade_x_baseline = velocidade_pct_min dividido pela
                  mediana de |retorno 1min| do proprio ativo dentro do
                  pregao (calculada aqui mesmo, dinamicamente, a cada
                  rodada -- nao hardcoded). Confirmado com dado real
                  (Dolar, 123 dias): filtrando so os dias com velocidade
                  >=5x a baseline (47/123 dias -- os "impulsos rapidos" de
                  verdade), a regressao contra os preditores overnight
                  (ver causalidade_overnight.py) melhora MUITO: GBPUSD sai
                  de p=0.102 (todos os dias) pra p=0.0018/R2=0.237,
                  USDSEK de p=0.025 pra p=0.0097/R2=0.181 -- misturar
                  impulsos rapidos com "grinds" lentos (mesma distancia
                  percorrida, so que devagar) estava DILUINDO o sinal. Um
                  teste equivalente usando so o TAMANHO DO MAIOR CANDLE
                  UNICO no trajeto (em vez da velocidade media) NAO
                  reproduziu essa melhora -- confirma que e o ritmo do
                  movimento inteiro que importa, nao um candle isolado.
                  IMPORTANTE: o corte de 5x acima veio de uma busca em
                  grade (testei 1.5x/2x/3x/5x) na MESMA amostra usada pra
                  julgar o resultado -- e um achado exploratorio
                  promissor, nao um limiar validado. Antes de virar regra
                  de producao (Task #9), precisa ser testado fora da
                  amostra (Task #12, backtest) pra garantir que nao e
                  overfitting do proprio corte.
                  1.2.0 (2026-09-30): campos novos candles_ate_pivo_fractal/
                  tipo_pivo_fractal/horario_pivo_fractal/preco_pivo_fractal/
                  magnitude_pivo_fractal_pct -- pedido do usuario: "primeiro
                  pegue toda a serie historica de M1 dos ativos DOLAR e INDICE,
                  conte quantos candles em media se formam antes do 1o
                  pivo... e ai que ta o pulo do gato". Critica correta: o
                  algoritmo de deteccao original (LIMIAR_RUIDO_PCT +
                  RETRACAO_CONFIRMA_PCT) usa limiares calibrados a mao
                  (8x a mediana do retorno 1min) -- nao vem da propria
                  geometria da serie. detectar_pivo_fractal() resolve isso
                  com um fractal classico (Bill Williams, N_FRACTAL=3):
                  candle i e pivo de alta/baixa se seu high/low e o
                  maior/menor entre os N candles antes E depois -- ZERO
                  parametro de porcentagem, so geometria de candle.
                  Resultado (123 dias, mesmo universo): mediana de 6
                  candles ate o 1o pivo pros DOIS ativos (Indice e Dolar) --
                  bate de perto com a mediana de duracao_min do metodo
                  original (5min), o que da confianca cruzada de que ~5-6
                  minutos e mesmo o "ritmo natural" da abertura, nao um
                  artefato do limiar escolhido. Os dois metodos ficam lado
                  a lado no output (nenhum substituiu o outro ainda) --
                  ver variacao_preditores_pivo.py pro proximo passo (o que
                  os preditores Gi/dg fazem durante essa janela).
Autor          : Julio Cesar Silvio Campanhola
Criado em      : 2026-09-30
Versao         : 1.2.0
Projeto        : dashboard
Historico      : scripts_py/versoes/impulso_abertura.md
"""

import importlib
import os

try:
    pd = importlib.import_module("pandas")
except ImportError as exc:
    raise ImportError(
        "A dependencia pandas nao esta instalada. "
        "Instale-a com: pip install pandas pyarrow"
    ) from exc

ATIVOS = ["Indice", "Dolar"]

# teto de seguranca -- nao e o resultado esperado, so evita que um dia de
# tendencia forte vire "impulso" do pregao inteiro
JANELA_MAX_MIN = 60

# limiar de materialidade por ativo (retorno % desde a abertura precisa
# cruzar isso antes de comecar a rastrear uma direcao) -- calibrado a
# ~8x a mediana de |retorno 1min| de cada ativo dentro do pregao, ver
# docstring acima
LIMIAR_RUIDO_PCT = {
    "Indice": 0.15,
    "Dolar": 0.08,
}

# fracao do extremo que, devolvida, confirma que o impulso acabou
# (reversao real, nao so um candle parado)
RETRACAO_CONFIRMA_PCT = 0.30

# dias com primeiro candle fora dessa janela sao descartados (gap de
# coleta / abertura sem dado, nao abertura real do pregao)
ABERTURA_HORA_ESPERADA = 9
ABERTURA_MINUTO_TOLERANCIA = 10

# fractal classico (Bill Williams): candle i e pivo de alta se seu high e
# o maior dos N candles antes E depois; simetrico pro pivo de baixa. ZERO
# parametros de %/limiar -- so geometria de candle. Ver v1.2.0 na docstring:
# pedido do usuario pra achar "quantos candles em media se formam antes do
# 1o pivo" direto na serie, sem depender do limiar de materialidade acima.
N_FRACTAL = 3
JANELA_MAX_MIN_FRACTAL = 90  # teto de seguranca pra busca do 1o pivo fractal


def _baseline_ret1min(df_ativo):
    """Mediana de |retorno 1min| do ativo dentro do pregao regular
    (09h-18h) -- referencia de 'velocidade normal' pra julgar se um
    movimento foi rapido (impulso de verdade) ou so foi longe devagar
    (grind). Calculada aqui, a cada rodada, em cima do proprio dado --
    nunca hardcoded (ao contrario de LIMIAR_RUIDO_PCT, que e calibrado
    manualmente uma vez)."""
    sessao = df_ativo[(df_ativo["time"].dt.hour >= 9) & (df_ativo["time"].dt.hour < 18)].copy()
    ret1min = sessao.groupby("data")["close"].pct_change().abs() * 100
    return float(ret1min.median())


def detectar_pivo_fractal(candles_dia, n=N_FRACTAL, janela_max_min=JANELA_MAX_MIN_FRACTAL):
    """Acha o primeiro pivo (fractal classico, sem limiar de %) depois da
    abertura: candle i e pivo de alta se high[i] e o maior de
    high[i-n:i+n+1] (idem baixa/low). Devolve dict com
    candles_ate_pivo_fractal/tipo_pivo_fractal/horario_pivo_fractal/
    magnitude_pivo_fractal, ou None se nao achar pivo dentro do teto de
    seguranca. Precisa de colunas time/open/high/low."""
    abertura_time = candles_dia["time"].iloc[0]
    if (
        abertura_time.hour != ABERTURA_HORA_ESPERADA
        or abertura_time.minute > ABERTURA_MINUTO_TOLERANCIA
    ):
        return None

    janela = candles_dia[
        candles_dia["time"] <= abertura_time + pd.Timedelta(minutes=janela_max_min)
    ].reset_index(drop=True)
    if len(janela) < 2 * n + 1:
        return None

    preco_abertura = janela["open"].iloc[0]
    highs = janela["high"].to_numpy()
    lows = janela["low"].to_numpy()
    for i in range(n, len(janela) - n):
        janela_high = highs[i - n:i + n + 1]
        janela_low = lows[i - n:i + n + 1]
        if highs[i] == janela_high.max() and janela_high.argmax() == n:
            preco_pivo = float(highs[i])
            tipo = "alta"
        elif lows[i] == janela_low.min() and janela_low.argmin() == n:
            preco_pivo = float(lows[i])
            tipo = "baixa"
        else:
            continue
        horario_pivo = janela["time"].iloc[i]
        return {
            "candles_ate_pivo_fractal": i,
            "tipo_pivo_fractal": tipo,
            "horario_pivo_fractal": horario_pivo,
            "preco_pivo_fractal": preco_pivo,
            "magnitude_pivo_fractal_pct": round((preco_pivo - preco_abertura) / preco_abertura * 100, 5),
        }
    return None  # nenhum pivo confirmado dentro do teto de seguranca


def detectar_impulso_dia(candles_dia, limiar):
    """Recebe os candles M1 de UM dia (ja ordenados por time, com colunas
    time/open/close), o limiar de materialidade do ativo, e devolve um
    dict com direcao/magnitude_pct/horario_pico/duracao_min/aberto, ou
    None se o dia nao tiver candles suficientes ou abertura fora do
    horario esperado. Ver algoritmo completo na docstring do modulo."""
    abertura_time = candles_dia["time"].iloc[0]
    if (
        abertura_time.hour != ABERTURA_HORA_ESPERADA
        or abertura_time.minute > ABERTURA_MINUTO_TOLERANCIA
    ):
        return None

    preco_abertura = candles_dia["open"].iloc[0]
    janela = candles_dia[
        candles_dia["time"] <= abertura_time + pd.Timedelta(minutes=JANELA_MAX_MIN)
    ].reset_index(drop=True)
    if len(janela) < 5:
        return None

    janela = janela.copy()
    janela["retorno_pct"] = (janela["close"] - preco_abertura) / preco_abertura * 100

    direcao = 0
    extremo = 0.0
    idx_extremo = 0
    for i in range(len(janela)):
        r = janela["retorno_pct"].iloc[i]
        if direcao == 0:
            if abs(r) >= limiar:
                direcao = 1 if r > 0 else -1
                extremo = r
                idx_extremo = i
            continue
        avancou = (direcao == 1 and r > extremo) or (direcao == -1 and r < extremo)
        if avancou:
            extremo = r
            idx_extremo = i
            continue
        devolvido = abs(extremo - r)
        if abs(extremo) > 0 and devolvido / abs(extremo) >= RETRACAO_CONFIRMA_PCT:
            horario_pico = janela["time"].iloc[idx_extremo]
            return {
                "direcao": direcao,
                "magnitude_pct": round(float(extremo), 5),
                "preco_abertura": float(preco_abertura),
                "preco_pico": float(janela["close"].iloc[idx_extremo]),
                "horario_abertura": abertura_time,
                "horario_pico": horario_pico,
                "duracao_min": round((horario_pico - abertura_time).total_seconds() / 60, 2),
                "aberto": False,
            }

    if direcao == 0:
        return None  # dia sem nenhum movimento acima do limiar de materialidade

    horario_pico = janela["time"].iloc[idx_extremo]
    return {
        "direcao": direcao,
        "magnitude_pct": round(float(extremo), 5),
        "preco_abertura": float(preco_abertura),
        "preco_pico": float(janela["close"].iloc[idx_extremo]),
        "horario_abertura": abertura_time,
        "horario_pico": horario_pico,
        "duracao_min": round((horario_pico - abertura_time).total_seconds() / 60, 2),
        "aberto": True,  # janela de seguranca acabou sem reversao confirmada -- tendencia em curso
    }


def processar_ativo(raiz):
    """Le o M1 completo de uma raiz (Indice/Dolar) em parquet/historicos/MTF/
    e devolve um DataFrame com uma linha por dia (so os dias com impulso
    detectado -- dias com gap de abertura ou sem candles suficientes nao
    entram)."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    caminho = os.path.join(base_dir, "..", "parquet", "historicos", "MTF", raiz, "M1.parquet")
    df = pd.read_parquet(caminho, columns=["time", "open", "high", "low", "close"])
    df["time"] = pd.to_datetime(df["time"]).dt.tz_localize(None)
    df["data"] = df["time"].dt.date

    baseline = _baseline_ret1min(df)
    limiar = LIMIAR_RUIDO_PCT[raiz]
    linhas = []
    for dia, candles_dia in df.groupby("data"):
        candles_dia = candles_dia.sort_values("time").reset_index(drop=True)
        resultado = detectar_impulso_dia(candles_dia, limiar)
        if resultado is not None:
            min_decorridos = max(resultado["duracao_min"], 1)
            velocidade = abs(resultado["magnitude_pct"]) / min_decorridos
            resultado["velocidade_pct_min"] = round(velocidade, 5)
            resultado["velocidade_x_baseline"] = round(velocidade / baseline, 2) if baseline else None
            resultado["ativo"] = raiz
            resultado["data"] = dia
            pivo_fractal = detectar_pivo_fractal(candles_dia)
            if pivo_fractal is not None:
                resultado.update(pivo_fractal)
            linhas.append(resultado)

    colunas = [
        "ativo", "data", "direcao", "magnitude_pct", "duracao_min",
        "velocidade_pct_min", "velocidade_x_baseline",
        "horario_abertura", "horario_pico", "preco_abertura", "preco_pico", "aberto",
        "candles_ate_pivo_fractal", "tipo_pivo_fractal", "horario_pivo_fractal",
        "preco_pivo_fractal", "magnitude_pivo_fractal_pct",
    ]
    return pd.DataFrame(linhas, columns=colunas)


def calcular():
    partes = [processar_ativo(raiz) for raiz in ATIVOS]
    return pd.concat(partes, ignore_index=True)


def executar():
    saida = calcular()
    base_dir = os.path.dirname(os.path.abspath(__file__))
    caminho = os.path.join(base_dir, "..", "parquet", "calculos", "impulsoAbertura.parquet")
    saida.to_parquet(caminho, index=False)
    for raiz in ATIVOS:
        parte = saida[saida["ativo"] == raiz]
        n_abertos = int(parte["aberto"].sum())
        mediana_dur = parte["duracao_min"].median()
        mediana_mag = parte["magnitude_pct"].abs().median()
        mediana_vel = parte["velocidade_x_baseline"].median()
        print(
            f"{raiz}: {len(parte)} dias | duracao mediana {mediana_dur:.1f}min | "
            f"magnitude mediana {mediana_mag:.3f}% | velocidade mediana {mediana_vel:.1f}x baseline | "
            f"{n_abertos} dias 'abertos' (tendencia sem reversao confirmada)"
        )
        com_fractal = parte.dropna(subset=["candles_ate_pivo_fractal"])
        if len(com_fractal):
            mediana_candles = com_fractal["candles_ate_pivo_fractal"].median()
            print(
                f"  pivo fractal (sem limiar de %): {len(com_fractal)} dias | "
                f"mediana {mediana_candles:.0f} candles ate o 1o pivo"
            )
    print(f"Salvo: {os.path.abspath(caminho)} ({len(saida)} linhas)")
    return saida


if __name__ == "__main__":
    executar()
