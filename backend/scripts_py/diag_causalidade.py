"""
Nome do script : diag_causalidade.py
Descricao      : Diagnostico EXPLORATORIO (prototipo, nao roda dentro do
                  main.py ainda) -- pedido do usuario 2026-09-30: alem da
                  correlacao ja calculada em correl.py, explorar
                  CAUSALIDADE entre os ativos e Indice/Dolar (usuario disse
                  nao saber fazer essa conta sozinho).

                  Causalidade de Granger != causalidade de verdade: e um
                  teste estatistico de PRECEDENCIA TEMPORAL -- "o retorno
                  passado de X melhora a previsao do retorno de Y, alem do
                  que o proprio passado de Y ja explica?". Correlacao
                  (correl.py) mede se dois ativos se movem JUNTOS no mesmo
                  instante; causalidade de Granger mede se um ativo LIDERA
                  o outro no tempo -- relevante pra trading porque um
                  ativo que "causa" Indice/Dolar nesse sentido e, em tese, um
                  preditor ANTECEDENTE, nao so um companheiro de
                  movimento.

                  Reaproveita a MESMA resolucao de cluster/extra e a MESMA
                  base (retornoD1.parquet) que correl.py ja usa
                  (AnalisadorCorrelacao -- import direto, mesmo padrao que
                  spread_di1_selic.py ja usa), pra manter os dois calculos
                  consistentes entre si (mesmo universo, mesmo vigente
                  resolvido).

                  Diferenca deliberada em relacao ao universo de
                  correl.py: la, Indice/Dolar/USDBRL sao EXCLUIDOS de
                  serem candidatos (driver) de INDICE/DOLAR porque sao a MESMA
                  grandeza economica no mesmo instante -- correlacionar
                  contra o proprio INDICE/DOLAR seria tautologico. Aqui NAO
                  exclui: causalidade de Granger so usa valores DEFASADOS
                  (lag >= 1), entao testar se o Indice/Dolar de ONTEM
                  ajuda a prever o Indice/Dolar de HOJE nao e tautologico --
                  pelo contrario, e um dos testes mais uteis do script,
                  porque a corretora internacional (internacional) pode reagir a
                  noticia/sessao fora do horario da B3 e "chegar primeiro".
                  So continua excluido da lista de candidatos o proprio
                  Indice/Dolar e toda a curva de vencimento deles (regex
                  ^(INDICE|DOLAR) -- mesmo padrao do correl.py) -- comparar
                  DOLARF27 contra Dolar e sim tautologico (mesmo ativo,
                  vencimento diferente, arbitragem de curva prende os dois
                  quase juntos em qualquer lag).

                  Testa as DUAS direcoes pra cada par (candidato -> alvo e
                  alvo -> candidato). Quando as duas direcoes dao
                  significativas ao mesmo tempo, marca "bidirecional" --
                  sinal de que pode ser simultaneidade/fator comum (os
                  dois reagem juntos a alguma coisa externa) e nao um
                  preditor de verdade andando na frente; "so um sentido"
                  (so candidato->alvo significativo) e o resultado mais
                  forte pra usar como preditor.

                  Script descartavel/prototipo -- so depois do usuario
                  revisar o resultado (e decidir se faz sentido de
                  verdade) que vale pensar em integrar num script de
                  producao (correl.py ganharia colunas novas, ou um
                  causal.py separado no loop do main.py).

                  Grava em backend/json/diag_causalidade.json e imprime um
                  ranking no console (por p-valor minimo, mais
                  significativo primeiro).
Autor          : Julio Cesar Silvio Campanhola
Criado em      : 2026-09-30
Versao         : 1.0.0 (diagnostico/prototipo, sem entrada em versoes/)
"""

import importlib
import json
import os

try:
    pd = importlib.import_module("pandas")
except ImportError as exc:
    raise ImportError(
        "A dependencia pandas nao esta instalada. "
        "Instale-a com: pip install pandas pyarrow"
    ) from exc
try:
    np = importlib.import_module("numpy")
except ImportError as exc:
    raise ImportError(
        "A dependencia numpy nao esta instalada. "
        "Instale-a com: pip install numpy"
    ) from exc
try:
    grangercausalitytests = importlib.import_module("statsmodels.tsa.stattools").grangercausalitytests
except ImportError as exc:
    raise ImportError(
        "A dependencia statsmodels nao esta instalada (script novo, ainda "
        "nao esta no fluxo padrao do projeto -- so faz sentido instalar de "
        "verdade se a causalidade se provar util). Instale com: "
        "pip install statsmodels"
    ) from exc

from correl import AnalisadorCorrelacao

MAXLAG = 5          # ~1 semana de pregao em D1 (dias uteis)
SIGNIFICANCIA = 0.05
MIN_PONTOS = 60      # amostra minima pro teste nao virar ruido -- exclui
                      # sozinho os contratos de curva distante/ilíquidos
                      # (ex. DAPX26 com 1 ponto so) sem precisar de lista


def _serie(df, broker, symbol):
    s = df[(df["broker"] == broker) & (df["symbol"] == symbol)][["time", "retorno"]]
    return s.sort_values("time").reset_index(drop=True)


def _testar_par(base_causa, base_efeito, maxlag):
    """base_causa = quem supostamente lidera; base_efeito = quem
    supostamente reage. Merge por time (inner -- so dias em que os dois
    tem preco), roda grangercausalitytests numa matriz [efeito, causa] --
    a API do statsmodels testa se a 2a coluna causa a 1a. Devolve
    (menor p-valor entre os lags 1..maxlag, lag desse p-valor minimo,
    n_pontos) ou (None, None, n) se nao deu pra rodar."""
    par = base_efeito.merge(base_causa, on="time", suffixes=("_efeito", "_causa"))
    n = len(par)
    if n < MIN_PONTOS:
        return None, None, n

    dados = par[["retorno_efeito", "retorno_causa"]].to_numpy()
    try:
        try:
            # versoes antigas do statsmodels aceitam verbose=False (silencia
            # o print automatico da lib, que senao polui o console pra cada
            # par testado); versoes novas (>=0.15) removeram o parametro --
            # cai pra chamada sem ele nesse caso.
            resultado = grangercausalitytests(dados, maxlag=maxlag, verbose=False)
        except TypeError:
            resultado = grangercausalitytests(dados, maxlag=maxlag)
    except Exception:
        # statsmodels pode reclamar de colinearidade/serie quase-constante
        # em ativos muito ilíquidos (retorno quase sempre zero) -- nao e
        # bug do script, e dado ruim; melhor pular o par do que derrubar o
        # diagnostico inteiro (mesmo espirito da resiliencia aplicada no
        # correl.py 1.6.0 -- um par ruim nao pode derrubar os outros).
        return None, None, n

    p_por_lag = {lag: teste[0]["ssr_ftest"][1] for lag, teste in resultado.items()}
    melhor_lag = min(p_por_lag, key=p_por_lag.get)
    return p_por_lag[melhor_lag], melhor_lag, n


def diagnosticar():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    calculos = os.path.join(base_dir, "..", "parquet", "calculos")
    retorno_path = os.path.join(calculos, "retornoD1.parquet")

    df = pd.read_parquet(retorno_path, columns=["broker", "symbol", "time", "retorno"])

    # mesma resolucao de cluster que correl.py -- instancia so pra chamar
    # _resolver_cluster(), nunca executa/grava nada com ela (mesmo padrao
    # ja usado em spread_di1_selic.py)
    resolvedor = AnalisadorCorrelacao(retorno_path, os.devnull, os.devnull, janela=20)
    cluster = resolvedor._resolver_cluster()
    alvos = {"indice": cluster["indice"], "dolar": cluster["dolar"]}

    excluido_regex = df["symbol"].str.upper().str.match(r"^(INDICE|DOLAR)").to_numpy()
    universo = df[~excluido_regex]

    linhas = []
    for (broker, symbol), _ in universo.groupby(["broker", "symbol"]):
        base_candidato = _serie(df, broker, symbol)
        if base_candidato.empty:
            continue
        for nome_alvo, info_alvo in alvos.items():
            base_alvo = _serie(df, info_alvo["broker"], info_alvo["ticker"])
            if base_alvo.empty:
                continue

            p_ida, lag_ida, n = _testar_par(base_candidato, base_alvo, MAXLAG)
            if p_ida is None:
                continue
            p_volta, lag_volta, _ = _testar_par(base_alvo, base_candidato, MAXLAG)

            significativo = p_ida < SIGNIFICANCIA
            reverso_significativo = (p_volta is not None and p_volta < SIGNIFICANCIA)

            linhas.append({
                "broker": broker,
                "symbol": symbol,
                "alvo": nome_alvo,
                "n_pontos": n,
                "p_valor_min": round(p_ida, 5),
                "lag_p_valor_min": lag_ida,
                "significativo": bool(significativo),
                "reverso_p_valor_min": round(p_volta, 5) if p_volta is not None else None,
                "reverso_significativo": bool(reverso_significativo),
                "so_um_sentido": bool(significativo and not reverso_significativo),
            })

    saida = pd.DataFrame(linhas)
    if not saida.empty:
        saida = saida.sort_values(["alvo", "p_valor_min"]).reset_index(drop=True)
    return saida


def main():
    saida = diagnosticar()

    base_dir = os.path.dirname(os.path.abspath(__file__))
    json_path = os.path.join(base_dir, "..", "json", "diag_causalidade.json")
    registros = saida.to_dict(orient="records")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(
            {"maxlag": MAXLAG, "significancia": SIGNIFICANCIA, "resultados": registros},
            f, ensure_ascii=False, indent=2,
        )
    print(f"Salvo: {os.path.abspath(json_path)} ({len(registros)} pares testados)")

    for nome_alvo in ("indice", "dolar"):
        sub = saida[(saida["alvo"] == nome_alvo) & (saida["significativo"])].sort_values("p_valor_min")
        print(f"\n=== Causalidade de Granger significativa -> {nome_alvo.upper()} (p < {SIGNIFICANCIA}) ===")
        if sub.empty:
            print("(nenhum candidato significativo)")
        else:
            for _, linha in sub.iterrows():
                marca = "SO UM SENTIDO (mais forte)" if linha["so_um_sentido"] else "bidirecional (cuidado: pode ser simultaneidade)"
                print(f"  {linha['broker']}:{linha['symbol']:<14} p={linha['p_valor_min']:.5f} "
                      f"lag={linha['lag_p_valor_min']}  n={linha['n_pontos']:<4}  {marca}")


if __name__ == "__main__":
    main()
