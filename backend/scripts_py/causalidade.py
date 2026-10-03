"""
Nome do script : causalidade.py
Descricao      : Versao DE PRODUCAO do diag_causalidade.py (prototipo,
                  2026-09-30) -- pedido do usuario depois de revisar o
                  resultado do prototipo: "adicione nas tabelas de risk
                  mesmo ja existentes". Reaproveita toda a logica de teste
                  do prototipo (import direto -- MAXLAG, SIGNIFICANCIA,
                  _serie, _testar_par -- mesmo padrao de reuso entre
                  scripts que spread_di1_selic.py ja faz com correl.py),
                  mas difere em dois pontos:

                  - So guarda resultado "SO UM SENTIDO" (candidato causa o
                    alvo, mas o alvo NAO causa de volta) -- bidirecional
                    fica de fora (sinal mais provavel de simultaneidade/
                    fator comum do que de preditor de verdade de verdade,
                    ver docstring do diag_causalidade.py) -- um badge no
                    frontend so deve acender pro sinal mais confiavel, nao
                    pra qualquer p<0.05.
                  - Formato de saida COMPACTO (broker/symbol + 1 booleano +
                    p-valor + lag por alvo), pronto pro _ler_peso_mercado()
                    do api_server.py so dar merge por symbol -- mesma chave
                    de pesoMercadoD1.parquet.

                  NAO esta no loop automatico do main.py ainda (mesmo
                  status do curva_juros.py: "roda manualmente por
                  enquanto") -- causalidade de Granger em D1 nao muda de
                  candle a candle, nao faz sentido recalcular a cada 5 min,
                  e ~1min de execucao pesa demais pro loop apertado. Rodar
                  manualmente (ou agendar 1x/dia fora do main.py) ate
                  decidir automatizar de verdade.

                  Grava em parquet/calculos/causalidadeD1.parquet.
Autor          : Julio Cesar Silvio Campanhola
Criado em      : 2026-09-30
Versao         : 1.0.0
Projeto        : dashboard
Historico      : scripts_py/versoes/causalidade.md
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

from diag_causalidade import MAXLAG, SIGNIFICANCIA, _serie, _testar_par
from correl import AnalisadorCorrelacao


def calcular():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    calculos = os.path.join(base_dir, "..", "parquet", "calculos")
    retorno_path = os.path.join(calculos, "retornoD1.parquet")

    df = pd.read_parquet(retorno_path, columns=["broker", "symbol", "time", "retorno"])

    # mesma resolucao de cluster que correl.py/diag_causalidade.py -- so
    # pra achar os tickers vigentes de INDICE/DOLAR, nunca executa/grava nada
    # com ela (mesmo padrao ja usado em spread_di1_selic.py)
    resolvedor = AnalisadorCorrelacao(retorno_path, os.devnull, os.devnull, janela=20)
    cluster = resolvedor._resolver_cluster()
    alvos = {"indice": cluster["indice"], "dolar": cluster["dolar"]}

    excluido_regex = df["symbol"].str.upper().str.match(r"^(INDICE|DOLAR)").to_numpy()
    universo = df[~excluido_regex]

    por_ativo = {}
    for (broker, symbol), _ in universo.groupby(["broker", "symbol"]):
        base_candidato = _serie(df, broker, symbol)
        if base_candidato.empty:
            continue
        linha = {"broker": broker, "symbol": symbol}
        tem_algo = False
        for nome_alvo, info_alvo in alvos.items():
            base_alvo = _serie(df, info_alvo["broker"], info_alvo["ticker"])
            if base_alvo.empty:
                continue
            p_ida, lag_ida, _ = _testar_par(base_candidato, base_alvo, MAXLAG)
            causa = False
            if p_ida is not None and p_ida < SIGNIFICANCIA:
                p_volta, _, _ = _testar_par(base_alvo, base_candidato, MAXLAG)
                reverso_sig = p_volta is not None and p_volta < SIGNIFICANCIA
                causa = not reverso_sig  # "so um sentido" -- o resultado forte
            linha[f"causa_{nome_alvo}"] = bool(causa)
            linha[f"causa_{nome_alvo}_p"] = round(p_ida, 5) if p_ida is not None else None
            linha[f"causa_{nome_alvo}_lag"] = lag_ida
            tem_algo = tem_algo or (p_ida is not None)
        if tem_algo:
            por_ativo[(broker, symbol)] = linha

    return pd.DataFrame(por_ativo.values())


def executar():
    saida = calcular()
    base_dir = os.path.dirname(os.path.abspath(__file__))
    caminho = os.path.join(base_dir, "..", "parquet", "calculos", "causalidadeD1.parquet")
    saida.to_parquet(caminho, index=False)
    n_indice = int(saida["causa_indice"].sum()) if "causa_indice" in saida.columns else 0
    n_dolar = int(saida["causa_dolar"].sum()) if "causa_dolar" in saida.columns else 0
    print(f"Salvo: {os.path.abspath(caminho)} ({len(saida)} ativos testados, "
          f"{n_indice} causam INDICE 'so um sentido', {n_dolar} causam DOLAR 'so um sentido')")
    return saida


if __name__ == "__main__":
    executar()
