Historico de versoes — causalidade_overnight.py
---------------------------------------------------------------------------
1.0.0 - 2026-09-30 - Julio - Criacao do script. Reteste da causalidade dos
                             4 preditores do Dolar (GOLD, ChinaA50, GBPUSD,
                             USDSEK), agora especificamente na janela
                             overnight (fechamento do pregao anterior ate a
                             abertura do dia atual) em vez do retorno D1
                             cheio usado em causalidade.py -- pedido do
                             usuario depois de ver correlacao fraca em
                             preditores_overnight.py 1.0.0, confirmado com
                             "b pode ser".
                             NAO reusa o grangercausalitytests() multi-lag
                             de causalidade.py/diag_causalidade.py -- a
                             precedencia temporal ja esta embutida na
                             propria janela overnight (o retorno do
                             preditor termina exatamente na abertura do
                             mesmo dia do impulso, sem precisar de lag
                             extra), entao o teste certo e uma regressao
                             OLS direta (overnight_t -> impulso_t, mesmo
                             dia), com o impulso de ontem como regressor
                             extra pra controlar a autocorrelacao natural
                             do alvo.
                             Resultado (122 dias, alvo = direcao *
                             magnitude_pct): ChinaA50 p=0.658 (era p=0.005
                             no teste D1 -- NAO sobrevive), GOLD p=0.373
                             (era p=0.035 -- NAO sobrevive), GBPUSD p=0.102
                             (era p=0.013 -- limitrofe), USDSEK p=0.025
                             (era p=0.022 -- UNICO que se mantem, com
                             R2=0.042). Tambem testadas as hipoteses de
                             volatilidade (|overnight| -> |magnitude|) e de
                             duracao (overnight -> duracao_min): nenhuma
                             melhorou. Modelo conjunto com os 4 juntos:
                             R2=0.054.
                             Conclusao: a maior parte do sinal de
                             causalidade D1 nao sobrevive na janela que de
                             fato importa -- o teste D1 original
                             provavelmente estava pegando co-movimento
                             durante o proprio horario em que os mercados
                             se sobrepoem, nao especificamente o "gap" que
                             fica pra reprecificar na abertura da B3.
                             Grava
                             parquet/calculos/causalidadeOvernightWDO.parquet.
---------------------------------------------------------------------------

## 1.1.0 - 2026-09-30 - Julio - Reteste segmentado por velocidade do
                             impulso (velocidade_x_baseline, novo em
                             impulso_abertura.py 1.1.0). Roda o mesmo
                             teste (overnight -> impulso sinalizado, com
                             controle de AR) duas vezes: "todos" (dataset
                             completo, resultado da 1.0.0) e "rapidos"
                             (so dias com velocidade_x_baseline >= 5x,
                             corte exploratorio -- LIMIAR_VELOCIDADE_
                             EXPLORATORIO). No segmento "rapidos" (46
                             dias), GBPUSD e USDSEK ficam claramente
                             significativos (p=0.0018/R2=0.237 e
                             p=0.0097/R2=0.181) -- bem mais fortes que no
                             dataset completo. GOLD fica limitrofe
                             (p=0.0565), ChinaA50 continua morto. Impresso
                             e gravado (parquet/calculos/
                             causalidadeOvernightWDO.parquet, coluna
                             'segmento') com aviso explicito de que o
                             corte de velocidade foi escolhido na MESMA
                             amostra usada pra julgar o resultado --
                             achado promissor, nao validado, precisa do
                             backtest (Task #12) fora da amostra antes de
                             virar regra de producao.
