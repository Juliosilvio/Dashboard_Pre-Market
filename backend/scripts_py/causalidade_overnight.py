"""
Nome do script : causalidade_overnight.py
Descricao      : Reteste da causalidade dos preditores do Dolar (GOLD,
                  ChinaA50, GBPUSD, USDSEK -- ver causalidade.py e
                  preditores_overnight.py), agora na janela CORRETA:
                  overnight (fechamento do pregao anterior ate a abertura
                  do dia atual), nao mais o retorno D1 cheio
                  (fechamento-a-fechamento) usado no teste original.

                  Pedido do usuario 2026-09-30, depois de ver a correlacao
                  fraca em preditores_overnight.py 1.0.0: "recalcular a
                  causalidade especificamente sobre retorno overnight" --
                  confirmado com "b pode ser" (opcao b da checagem
                  anterior).

                  IMPORTANTE -- por que isso NAO reusa o
                  grangercausalitytests() multi-lag de causalidade.py/
                  diag_causalidade.py: aquele teste (MAXLAG=5) faz sentido
                  em cima de duas series D1 alinhadas dia-a-dia, onde o
                  "lag" natural e testar se o retorno de X de N dias atras
                  ajuda a prever o retorno de Y hoje. Aqui a precedencia
                  temporal ja esta EMBUTIDA na propria definicao da janela:
                  overnight_<preditor>_t e, por construcao, o movimento
                  do preditor que termina exatamente no instante da
                  abertura do dia t -- ou seja, ele SEMPRE acontece antes
                  do impulso_t, no mesmo dia t, sem precisar de nenhum lag
                  extra. Forcar um lag>=1 aqui testaria uma pergunta
                  diferente e menos direta ("o overnight de ontem ainda
                  ajuda a prever o impulso de hoje?"), nao a pergunta que
                  interessa ("o overnight de HOJE prediz o impulso de
                  HOJE?"). Por isso o teste certo aqui e uma regressao OLS
                  simples (overnight_t -> impulso_t, mesmo dia), com um
                  controle extra pra robustez: o proprio impulso de ONTEM
                  (alvo_lag1) entra como regressor, pra checar se o
                  preditor ainda ajuda depois de controlar a autocorrelacao
                  natural do alvo (nao so pegando carona em "dias de
                  tendencia se repetem").

                  Resultado da primeira rodada (2026-09-30, 122 dias,
                  alvo = direcao * magnitude_pct do impulso do Dolar):
                  ChinaA50 p=0.658 (era p=0.005 no teste D1 -- NAO
                  sobrevive), GOLD p=0.373 (era p=0.035 -- NAO sobrevive),
                  GBPUSD p=0.102 (era p=0.013 -- fica so limitrofe),
                  USDSEK p=0.025 (era p=0.022 -- o UNICO que se mantem
                  significativo, e mesmo assim com R2=0.042 -- explica
                  muito pouco da variancia). Testadas tambem as hipoteses
                  alternativas de volatilidade (|overnight| -> |magnitude|)
                  e de duracao (overnight -> duracao_min): nenhuma delas
                  melhorou o quadro. Modelo conjunto com os 4 preditores
                  juntos: R2=0.054, nenhum individualmente significativo a
                  0.05 no conjunto.

                  Conclusao honesta: a maior parte do sinal de causalidade
                  D1 nao sobrevive quando testado na janela que de fato
                  importa (overnight) -- ChinaA50 em particular, que era o
                  preditor mais forte no teste D1 (p=0.005), praticamente
                  zera (p=0.658). So USDSEK mantem um sinal fraco. Isso NAO
                  significa que o estudo falhou -- significa que o teste
                  original (D1 cheio) estava pegando um efeito diferente
                  (provavelmente co-movimento durante o proprio horario em
                  que os mercados se sobrepoem, nao especificamente o
                  "gap" que fica pra reprecificar na abertura da B3).

                  Grava
                  parquet/calculos/causalidadeOvernightWDO.parquet (uma
                  linha por preditor: symbol, n, coef, p_valor_simples,
                  p_valor_com_ar, r2_com_ar).
Autor          : Julio Cesar Silvio Campanhola
Criado em      : 2026-09-30
Versao         : 1.0.0
Projeto        : dashboard
Historico      : scripts_py/versoes/causalidade_overnight.md
"""

import importlib
import os

try:
    pd = importlib.import_module("pandas")
    sm = importlib.import_module("statsmodels.api")
except ImportError as exc:
    raise ImportError(
        "Dependencia faltando. Instale com: pip install pandas pyarrow statsmodels"
    ) from exc

SIGNIFICANCIA = 0.05

# corte exploratorio (2026-09-30): dias com velocidade_x_baseline >= isso
# sao os "impulsos rapidos de verdade" (ver impulso_abertura.py 1.1.0,
# secao sobre velocidade). ACHADO EXPLORATORIO, NAO VALIDADO -- o corte
# veio de uma busca em grade (1.5x/2x/3x/5x) na MESMA amostra usada pra
# julgar o resultado. So reportado lado a lado com o teste completo pra
# nao esconder a diferenca -- decisao de usar isso em producao (Task #9)
# fica pro backtest (Task #12) confirmar fora da amostra.
LIMIAR_VELOCIDADE_EXPLORATORIO = 5.0


def _base_dir():
    return os.path.dirname(os.path.abspath(__file__))


def _listar_preditores(df):
    return sorted(c[len("overnight_"):] for c in df.columns if c.startswith("overnight_"))


def _testar_segmento(df, preditores, segmento):
    linhas = []
    for symbol in preditores:
        coluna = f"overnight_{symbol}"
        sub = df.dropna(subset=[coluna, "alvo_sinalizado", "alvo_lag1"])
        n = len(sub)
        if n < 15:
            continue

        x_simples = sm.add_constant(sub[[coluna]])
        modelo_simples = sm.OLS(sub["alvo_sinalizado"], x_simples).fit()
        p_simples = float(modelo_simples.pvalues[coluna])

        x_completo = sm.add_constant(sub[[coluna, "alvo_lag1"]])
        modelo_completo = sm.OLS(sub["alvo_sinalizado"], x_completo).fit()
        p_com_ar = float(modelo_completo.pvalues[coluna])
        coef = float(modelo_completo.params[coluna])
        r2 = float(modelo_completo.rsquared)

        linhas.append({
            "segmento": segmento,
            "symbol": symbol,
            "n": n,
            "coef": round(coef, 5),
            "p_valor_simples": round(p_simples, 5),
            "p_valor_com_ar": round(p_com_ar, 5),
            "r2_com_ar": round(r2, 5),
            "significativo": bool(p_com_ar < SIGNIFICANCIA),
        })
    return linhas


def testar():
    """Roda o teste (overnight -> impulso sinalizado, com controle de AR)
    duas vezes: 'todos' (todo o dataset) e 'rapidos' (so dias com
    velocidade_x_baseline >= LIMIAR_VELOCIDADE_EXPLORATORIO -- ver aviso
    de overfitting na constante acima). Devolve os dois lado a lado."""
    base_dir = _base_dir()
    caminho_dataset = os.path.join(base_dir, "..", "parquet", "calculos", "preditoresOvernightWDO.parquet")
    df = pd.read_parquet(caminho_dataset).sort_values("data").reset_index(drop=True)
    df["alvo_sinalizado"] = df["direcao"] * df["magnitude_pct"].abs()
    df["alvo_lag1"] = df["alvo_sinalizado"].shift(1)

    preditores = _listar_preditores(df)

    linhas = _testar_segmento(df, preditores, "todos")

    if "velocidade_x_baseline" in df.columns:
        rapidos = df[df["velocidade_x_baseline"] >= LIMIAR_VELOCIDADE_EXPLORATORIO]
        linhas += _testar_segmento(rapidos, preditores, "rapidos (exploratorio)")

    return pd.DataFrame(linhas).sort_values(["segmento", "p_valor_com_ar"])


def executar():
    saida = testar()
    base_dir = _base_dir()
    caminho = os.path.join(base_dir, "..", "parquet", "calculos", "causalidadeOvernightWDO.parquet")
    saida.to_parquet(caminho, index=False)

    for segmento in saida["segmento"].unique():
        parte = saida[saida["segmento"] == segmento]
        print(f"Reteste na janela overnight -- segmento '{segmento}':")
        for _, linha in parte.iterrows():
            marca = "SIGNIFICATIVO" if linha["significativo"] else "nao significativo"
            print(
                f"  {linha['symbol']:12s} n={int(linha['n']):3d} | "
                f"p(simples)={linha['p_valor_simples']:.4f} | p(com AR)={linha['p_valor_com_ar']:.4f} | "
                f"R2={linha['r2_com_ar']:.4f} -> {marca}"
            )
        if segmento != "todos":
            print("  (ACHADO EXPLORATORIO -- corte de velocidade escolhido na mesma amostra, ver docstring)")
        print()
    print(f"Salvo: {os.path.abspath(caminho)}")
    return saida


if __name__ == "__main__":
    executar()
