"""
Nome do script : preditores_overnight.py
Descricao      : Monta o dataset de PREDITORES OVERNIGHT pro estudo do
                  impulso de abertura do Dolar (Task #8, ver
                  impulso_abertura.py e a secao "Estudo de aplicabilidade"
                  em causalidade-granger.md). Pra cada dia valido em
                  impulsoAbertura.parquet (ativo=="Dolar"), calcula o
                  retorno % "overnight" (entre o ultimo candle M1 do Dolar
                  no fechamento B3 do dia anterior e o horario de abertura
                  do dia atual) de cada preditor com causalidade de Granger
                  confirmada sobre o Dolar com lag=1 em causalidadeD1.parquet
                  (broker corretora internacional, causa_dolar=True, causa_dolar_lag==1):
                  GOLD, ChinaA50, GBPUSD, USDSEK (primeira rodada,
                  2026-09-30). USDRUB tambem causa Dolar mas com lag=4 --
                  dinamica diferente (nao "overnight" de 1 dia), fica de
                  fora deste dataset por enquanto.

                  "Fechamento anterior" de cada preditor e resolvido por
                  merge_asof (direction=backward) contra o horario real do
                  ULTIMO candle M1 do Dolar no dia de pregao anterior (nao
                  um horario fixo tipo 18:00 -- o pregao as vezes fecha
                  antes/depois) -- e "abertura atual" contra o
                  horario_abertura que ja saiu de impulso_abertura.py
                  (tipicamente 09:00). Isso cobre corretamente os gaps de
                  cada preditor (ex: GOLD tem um intervalo de manutencao
                  diario ~18h-19h sem candle, ChinaA50/GBPUSD/USDSEK tem
                  poucos minutos de gap no mesmo horario) -- o backward
                  asof so pega o ultimo preco disponivel antes do
                  instante-alvo, que e exatamente a semantica certa de
                  "preco de fechamento"/"preco no instante da abertura".

                  Saida (parquet/calculos/preditoresOvernightWDO.parquet):
                  uma linha por dia, colunas data/direcao/magnitude_pct/
                  duracao_min/aberto (alvo, vindo de impulsoAbertura) +
                  overnight_<PREDITOR> (retorno % de cada preditor) pra
                  cada preditor da lista acima. Dias em que algum preditor
                  nao tem preco valido em nenhuma das duas pontas (ex:
                  feriado so daquele mercado) ficam com NaN naquela coluna
                  -- decisao de dropar ou nao fica pro proximo passo
                  (ajuste da regressao, Task #9), nao aqui.

                  Isso ainda NAO e a regressao -- e so o dataset pronto
                  pra alimentar ela.
Autor          : Julio Cesar Silvio Campanhola
Criado em      : 2026-09-30
Versao         : 1.0.0
Projeto        : dashboard
Historico      : scripts_py/versoes/preditores_overnight.md
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

ALVO_ATIVO = "Dolar"
ALVO_COLUNA_CAUSA = "causa_dolar"
ALVO_COLUNA_LAG = "causa_dolar_lag"
LAG_ESTUDADO = 1  # so os preditores com lag=1 (overnight de UM dia) entram aqui
BROKER_PREDITORES = "corretora internacional"

# tolerancia maxima pro merge_asof (backward) nao devolver um preco velho
# demais quando o preditor teve um gap real (feriado local dele, etc.)
TOLERANCIA_ASOF = pd.Timedelta(days=4)


def _base_dir():
    return os.path.dirname(os.path.abspath(__file__))


def _caminho_mtf(raiz):
    return os.path.join(_base_dir(), "..", "parquet", "historicos", "MTF", raiz, "M1.parquet")


def listar_preditores():
    """Le causalidadeD1.parquet e devolve a lista de raizes corretora internacional com
    causa_dolar=True e lag==LAG_ESTUDADO (preditores de overnight de 1 dia)."""
    caminho = os.path.join(_base_dir(), "..", "parquet", "calculos", "causalidadeD1.parquet")
    df = pd.read_parquet(caminho)
    filtro = (
        (df["broker"] == BROKER_PREDITORES)
        & (df[ALVO_COLUNA_CAUSA] == True)  # noqa: E712
        & (df[ALVO_COLUNA_LAG] == LAG_ESTUDADO)
    )
    return sorted(df.loc[filtro, "symbol"].tolist())


def _fechamentos_por_dia(raiz):
    """Ultimo candle M1 de cada dia de pregao de uma raiz -- serve de
    'horario de fechamento' real (nao um horario fixo)."""
    df = pd.read_parquet(_caminho_mtf(raiz), columns=["time"])
    df["time"] = pd.to_datetime(df["time"]).dt.tz_localize(None)
    df["data"] = df["time"].dt.date
    fechamentos = df.groupby("data")["time"].max().sort_index()
    return fechamentos


def _preco_no_instante(raiz, instantes):
    """merge_asof (backward) do preco de fechamento (close) de uma raiz
    contra uma serie de instantes-alvo (timestamps). Devolve uma Series
    alinhada a 'instantes' (mesmo index), com NaN onde nao achou preco
    dentro de TOLERANCIA_ASOF."""
    df = pd.read_parquet(_caminho_mtf(raiz), columns=["time", "close"]).sort_values("time")
    df["time"] = pd.to_datetime(df["time"]).dt.tz_localize(None).astype("datetime64[ns]")

    alvo = pd.DataFrame({"instante": instantes}).dropna(subset=["instante"]).sort_values("instante")
    alvo["instante"] = alvo["instante"].astype("datetime64[ns]")
    fundido = pd.merge_asof(
        alvo, df, left_on="instante", right_on="time",
        direction="backward", tolerance=TOLERANCIA_ASOF,
    )
    fundido.index = alvo.index
    return fundido["close"].reindex(instantes.index)  # NaT/sem-match viram NaN aqui


def montar_dataset():
    base_dir = _base_dir()
    caminho_impulso = os.path.join(base_dir, "..", "parquet", "calculos", "impulsoAbertura.parquet")
    impulso = pd.read_parquet(caminho_impulso)
    impulso = impulso[impulso["ativo"] == ALVO_ATIVO].copy()
    impulso["data"] = pd.to_datetime(impulso["data"])
    impulso = impulso.sort_values("data").reset_index(drop=True)

    # horario de fechamento do PREGAO ANTERIOR de cada dia (usa o proprio
    # calendario de pregoes do Dolar, nao um horario fixo)
    fechamentos_dolar = _fechamentos_por_dia(ALVO_ATIVO)
    fechamentos_dolar.index = pd.to_datetime(fechamentos_dolar.index)
    fechamento_anterior = fechamentos_dolar.shift(1)
    impulso["fechamento_anterior_instante"] = impulso["data"].map(fechamento_anterior)
    impulso["abertura_instante"] = impulso["horario_abertura"]

    preditores = listar_preditores()

    saida = impulso[[
        "data", "direcao", "magnitude_pct", "duracao_min",
        "velocidade_pct_min", "velocidade_x_baseline", "aberto",
    ]].copy()

    for raiz in preditores:
        preco_fechamento = _preco_no_instante(raiz, impulso["fechamento_anterior_instante"])
        preco_abertura = _preco_no_instante(raiz, impulso["abertura_instante"])
        coluna = f"overnight_{raiz}"
        saida[coluna] = (preco_abertura - preco_fechamento) / preco_fechamento * 100

    return saida, preditores


def executar():
    saida, preditores = montar_dataset()
    base_dir = _base_dir()
    caminho = os.path.join(base_dir, "..", "parquet", "calculos", "preditoresOvernightWDO.parquet")
    saida.to_parquet(caminho, index=False)

    print(f"Preditores (causa_dolar=True, lag={LAG_ESTUDADO}): {preditores}")
    print(f"{len(saida)} dias no dataset")
    for raiz in preditores:
        coluna = f"overnight_{raiz}"
        validos = saida[coluna].notna().sum()
        print(
            f"  overnight_{raiz}: {validos}/{len(saida)} dias validos | "
            f"media {saida[coluna].mean():.4f}% | desvio {saida[coluna].std():.4f}%"
        )
    print(f"Salvo: {os.path.abspath(caminho)}")
    return saida


if __name__ == "__main__":
    executar()
