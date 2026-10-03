Historico de versoes — variacao_preditores_pivo.py
---------------------------------------------------------------------------
1.0.0 - 2026-09-30 - Julio - Criacao do script. Pedido do usuario, na
                             sequencia direta da critica que gerou
                             impulso_abertura.py 1.2.0 (pivo fractal):
                             "voce tem que guardar a variacao dos ativos
                             gi e dg, para saber como o mercado se
                             comporta naquela janela de tempo independente
                             de correlacao, entendeu?".
                             Registra o retorno % minuto a minuto de cada
                             preditor Gi/dg (causa_indice/causa_dolar=True,
                             lag=1) durante a MESMA janela em que o
                             Indice/Dolar forma seu 1o pivo fractal -- SEM
                             resumir a um coeficiente de correlacao antes
                             de olhar: so a media crua do path, separada
                             por tipo_pivo (alta/baixa) do alvo.
                             Diferenca crucial vs preditores_overnight.py:
                             aquele mede o preditor ANTES da abertura
                             (overnight); este mede o preditor DURANTE a
                             janela em que a B3 esta abrindo -- os
                             preditores negociam ~24h, entao continuam se
                             mexendo ao mesmo tempo que o Indice/Dolar.
                             Resultado (Dolar, 123 dias, 63 alta/60 baixa,
                             minuto 10): USDSEK diverge claro (+0.018% nos
                             dias de alta do Dolar vs -0.025% nos dias de
                             baixa); GBPUSD diverge na direcao OPOSTA
                             (-0.002% vs +0.010% -- faz sentido, USD mais
                             forte derruba GBPUSD e sobe o Dolar ao mesmo
                             tempo); GOLD e ChinaA50 NAO mostram divergencia
                             clara (paths emaranhados). Bate com
                             causalidade_overnight.py (GBPUSD/USDSEK
                             sobrevivem, GOLD limitrofe, ChinaA50 morto),
                             mas muda a INTERPRETACAO: nao e mais "o
                             overnight prediz a abertura" -- e "o mercado
                             forex, que continua aberto, confirma em tempo
                             real o mesmo movimento que a B3 esta fazendo,
                             enquanto o pivo se forma". Indice ainda sem
                             preditores lag=1 com historico suficiente
                             (Usa500/UsaInd/UsaTec tem lag=4-5, precisam de
                             --reforcar proprio antes de repetir esse
                             estudo do lado Indice).
                             Grava
                             parquet/calculos/variacaoPreditoresPivo.parquet
                             (long format: ativo_alvo, preditor, tipo_pivo,
                             minuto_offset, retorno_medio_pct, n_dias).
---------------------------------------------------------------------------
