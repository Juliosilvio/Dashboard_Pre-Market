Historico de versoes — impulso_abertura.py
---------------------------------------------------------------------------
1.0.0 - 2026-09-30 - Julio - Criacao do script. Deteccao do "impulso de
                             abertura" do Indice e do Dolar (Task #7 do estudo
                             de aplicabilidade da causalidade de Granger --
                             ver causalidade.py). Pedido do usuario:
                             "quero ver numeros... o mercado vai abrir
                             amanha, quanto estaria valendo tanto indice
                             quanto dolar?", esclarecido depois: "este
                             valor nao ira se referir ao agora e sim ao
                             primeiro impulso as 09:00... andou 1,40% para
                             cima no intraday nos primeiros minutos da
                             manha, e este 1,40% que quero saber se vai
                             acontecer ou nao" -- e confirmado que a janela
                             deveria ser adaptativa por dia, nao fixa:
                             "nao gostaria que fosse uma janela fixa...
                             acho a adaptativa atraente".
                             Algoritmo: anda candle a candle desde a
                             abertura (09:00) dentro de um teto de
                             seguranca de 60min; so comeca a rastrear uma
                             direcao quando o retorno acumulado cruza
                             LIMIAR_RUIDO_PCT (0.15% Indice, 0.08% Dolar,
                             calibrado a ~8x a mediana de |retorno 1min| de
                             cada ativo dentro do pregao); guarda o extremo
                             enquanto ele avanca; da o impulso como
                             concluido quando o preco devolve 30% do
                             extremo (reversao real) -- duracao e magnitude
                             saem naturalmente do dado, dia a dia, sem
                             janela fixa. Dia sem reversao confirmada
                             dentro do teto fica marcado "aberto"
                             (tendencia em curso, nao erro).
                             Primeira rodada real (2026-09-30, 123 dias de
                             M1 via historico.py --reforcar M1:180 --so
                             Indice,Dolar,GOLD,ChinaA50,GBPUSD,USDSEK):
                             100% dos dias com impulso detectado nos dois
                             ativos, duracao mediana 5min (Indice e Dolar),
                             p90 ~30min (Indice) / ~23min (Dolar), magnitude
                             mediana 0.44% (Indice) / 0.14% (Dolar), 14/123
                             (Indice) e 3/123 (Dolar) dias "abertos", direcao
                             alta/baixa equilibrada nos dois (sem vies
                             estrutural do algoritmo).
                             Grava parquet/calculos/impulsoAbertura.parquet
                             (uma linha por dia por ativo). NAO esta no
                             loop automatico do main.py -- roda manualmente
                             por enquanto (mesmo status de causalidade.py/
                             curva_juros.py). Proximo passo (Task #8): so
                             a deteccao/rotulagem do alvo historico, ainda
                             nao e previsao -- falta montar o dataset dos
                             preditores overnight (causa_indice/causa_dolar=True
                             em causalidade.py) pra depois regredir contra
                             magnitude_pct/duracao_min daqui.

## 1.1.0 - 2026-09-30 - Julio - Campo novo velocidade_pct_min (e
                             velocidade_x_baseline). Pergunta do usuario:
                             "como podemos saber que o movimento e um
                             impulso? tamanho do candle vs tempo? no M1?".
                             Testado contra o dado real dos dois jeitos:
                             tamanho do MAIOR CANDLE UNICO no trajeto (nao
                             ajudou -- quase todo dia tem um candle bem
                             maior que o normal logo na abertura, e um
                             leilao, isso sozinho nao distingue nada) vs
                             VELOCIDADE MEDIA do trajeto inteiro ate o
                             pico (|magnitude_pct| / max(duracao_min, 1),
                             dividido pela mediana de |retorno 1min| do
                             proprio ativo dentro do pregao -- calculada
                             dinamicamente, nunca hardcoded). A velocidade
                             media fez diferenca real: filtrando o Dolar
                             so pros dias com velocidade >=5x a baseline
                             (47/123 dias), a regressao contra os
                             preditores overnight (causalidade_overnight.py
                             1.1.0) melhorou muito -- GBPUSD de p=0.102
                             pra p=0.0018/R2=0.237, USDSEK de p=0.025 pra
                             p=0.0097/R2=0.181. Misturar impulsos rapidos
                             de verdade com "grinds" lentos (mesma
                             distancia, so que devagar) estava diluindo o
                             sinal. IMPORTANTE: o corte de 5x veio de uma
                             busca em grade na MESMA amostra usada pra
                             julgar -- achado exploratorio, precisa
                             validar fora da amostra (Task #12) antes de
                             virar regra de producao.

## 1.2.0 - 2026-09-30 - Julio - Campos novos candles_ate_pivo_fractal/
                             tipo_pivo_fractal/horario_pivo_fractal/
                             preco_pivo_fractal/magnitude_pivo_fractal_pct.
                             Pedido do usuario: "primeiro pegue toda a
                             serie historica de M1 dos ativos DOLAR e INDICE,
                             conte quantos candles em media se formam
                             antes do 1o pivo... e ai que ta o pulo do
                             gato" -- critica correta ao metodo 1.0.0/1.1.0
                             (limiares calibrados a mao, nao vindos da
                             propria geometria da serie). Resolvido com um
                             fractal classico (Bill Williams, N_FRACTAL=3):
                             candle i e pivo de alta/baixa se seu high/low
                             e o maior/menor entre os N candles antes E
                             depois -- zero parametro de porcentagem.
                             Resultado (123 dias, mesmo universo): mediana
                             de 6 candles ate o 1o pivo pros DOIS ativos
                             (Indice e Dolar) -- bate de perto com a mediana
                             de duracao_min do metodo original (5min),
                             confirmando que ~5-6min e o ritmo natural da
                             abertura, nao artefato do limiar. Os dois
                             metodos ficam lado a lado no output. Proximo
                             passo: variacao_preditores_pivo.py (o que os
                             preditores Gi/dg fazem durante essa janela).
---------------------------------------------------------------------------
