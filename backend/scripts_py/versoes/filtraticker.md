Historico de versoes — filtraticker.py
-------------------------------------------------------------------------
1.0.0 - 2026-09-13 - Julio - Criacao do script (classe FiltroTicker).
                              Calendario teorico de vencimento por raiz de
                              contrato (CICLOS_NACIONAL/CICLOS_INTERNACIONAL,
                              pesquisado nas especificacoes oficiais B3/CME/
                              ICE/Eurex). So considera "com vencimento" quem
                              esta em BMF (corretora nacional) ou CFD Forward* (corretora internacional). Resolve mes a mes o ticker "front
                              month" (primeiro mes do ciclo >= mes atual).
                              Cobertura: do inicio do historico_d1.parquet
                              ate 12 meses apos o fim. Produtos de curva
                              (DI1, DDI, DAP, FRC) e o ticker de rolagem
                              WI1... ficam FORA desta versao — nao tem um
                              "front month" unico. Salva em json/ticker.json.
1.1.0 - 2026-09-13 - Julio - Adicionada a lista de series CONTINUAS/sem
                              vencimento por broker (Indice, INDICE@, Dolar, DOLAR@
                              e variantes D/N na corretora nacional; EURUSD, GOLD,
                              SILVER, indices a vista etc. na corretora internacional) —
                              tudo que nao bate no padrao raiz+mes+ano.
                              Trocado o criterio de validacao: agora exige
                              candle real em historico_d1.parquet OU
                              historico_m5.parquet (nao so estar listado em
                              ativos.parquet) — bid/ask/ultimo em tempo real
                              nao ficam salvos, entao candle e o proxy usado
                              pra "tem preco de fechamento". Aplica esse
                              criterio tanto pros tickers com vencimento
                              quanto pras series continuas. Saida agora e
                              {"corretora nacional": {"vencimento": {...}, "continuo":
                              [...]}, "corretora internacional": {"vencimento": {...},
                              "continuo": [...]}}.
-------------------------------------------------------------------------
