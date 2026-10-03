Historico de versoes — preditores_overnight.py
---------------------------------------------------------------------------
1.0.0 - 2026-09-30 - Julio - Criacao do script. Task #8 do estudo de
                             aplicabilidade da causalidade de Granger (ver
                             impulso_abertura.py e a secao correspondente
                             em causalidade-granger.md). Monta o dataset
                             de preditores overnight do Dolar: le
                             causalidadeD1.parquet, filtra os preditores
                             corretora internacional com causa_dolar=True e lag=1
                             (ChinaA50, GBPUSD, GOLD, USDSEK -- USDRUB tem
                             lag=4, fica de fora por enquanto), e calcula
                             o retorno % de cada um entre o ultimo candle
                             M1 do Dolar no fechamento do pregao anterior e
                             o horario_abertura do dia atual (vindo de
                             impulsoAbertura.parquet) -- por merge_asof
                             backward, nao horario fixo, pra lidar com os
                             gaps de manutencao de cada preditor (ex: GOLD
                             tem ~1h de gap diario por volta das 18h-19h).
                             Grava
                             parquet/calculos/preditoresOvernightWDO.parquet
                             (uma linha por dia: alvo do impulso +
                             overnight_<PREDITOR> de cada um).
                             Primeira rodada (122 dias validos, 2026-09-30):
                             correlacao de cada preditor com o retorno
                             assinado do impulso (direcao*magnitude) ficou
                             FRACA -- USDSEK +0.204, GBPUSD -0.150, GOLD
                             -0.084, ChinaA50 +0.044. Hipotese mais provavel:
                             a causalidade de Granger foi testada em retorno
                             D1 (fechamento-a-fechamento, calendario cheio),
                             enquanto a janela "overnight" aqui e mais
                             estreita (so o periodo em que a B3 fica
                             fechada) -- as duas janelas nao sao a mesma
                             coisa, entao o preditor pode causar o D1 cheio
                             sem necessariamente se concentrar so na janela
                             overnight. Precisa decidir antes do Task #9:
                             (a) seguir com esses preditores mesmo assim e
                             deixar o backtest (Task #12) julgar, ou (b)
                             recalcular causalidade especificamente sobre
                             retorno overnight (nao D1 cheio) pra ver se o
                             sinal fica mais forte quando a janela bate
                             certo com o que causalidade.py testou.
---------------------------------------------------------------------------

## 1.1.0 - 2026-09-30 - Julio - Repassa velocidade_pct_min/
                             velocidade_x_baseline (novos em
                             impulso_abertura.py 1.1.0) pro dataset de
                             saida -- usado por causalidade_overnight.py
                             1.1.0 pra segmentar "impulsos rapidos" vs
                             "todos os dias". Sem mudanca na logica de
                             calculo do overnight em si.
