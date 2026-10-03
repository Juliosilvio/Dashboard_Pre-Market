Historico de versoes — grade.py
-------------------------------------------------------------------------
1.0.0 - 2026-09-15 - Julio - Criacao do script (classe SincronizadorGrade).
                              Monta a lista desejada de tickers por corretora
                              a partir de json/config.json (curva_br e
                              vencimento_americano usam os tickers ja
                              resolvidos em "vigentes"; nacionais,
                              indices_continuo, moedas_continuo e
                              commodities_internacionais entram com o nome
                              literal, ja que nao tem vencimento pra resolver
                              ou ainda nao passam pelo vigente.py). Compara
                              com os symbols atualmente visiveis no Market
                              Watch (mt5.symbols_get + .visible) e ajusta:
                              remove quem esta visivel e nao esta na lista,
                              adiciona quem esta na lista e nao esta visivel.
                              Falha ao remover (posicao/ordem/grafico aberto)
                              ou ao adicionar (ticker nao existe na corretora)
                              so entra no resumo final, nao derruba o script.
1.1.0 - 2026-09-15 - Julio - Corrigido: a lista desejada nao fica mais fixa
                              por corretora (curva_br+nacionais so na corretora nacional,
                              resto so na corretora internacional) — agora e UMA lista
                              soh com todas as categorias de ativos juntas, e
                              essa mesma lista e testada nas duas corretoras.
                              Quem decide se um ticker fica ou nao e o
                              proprio symbol_select() de cada terminal: existe
                              la, entra; nao existe, cai no resumo como "nao
                              existe nessa corretora" sem quebrar o script.
1.2.0 - 2026-09-24 - Julio - Corrigido: curva_br e vencimento_americano
                              nao usam mais a mesma regra em lista_desejada().
                              curva_br continua com a lista INTEIRA de
                              "vigentes" (precisa de todos os vertices pra
                              curva de juros). vencimento_americano passa a
                              usar SO O PRIMEIRO ticker (vigente/front) -
                              antes pegava a lista inteira igual curva_br, o
                              que deixava contratos futuros do mesmo ativo
                              (ex: BrentSep26/Nov26/Dec26) todos visiveis ao
                              mesmo tempo no Market Watch, e por consequencia
                              na tabela de cotacoes do frontend - usuario
                              reparou 3 linhas "Brent" e 2 linhas "Gasol"
                              diferentes na mesma tabela. Nenhum consumidor
                              do projeto usa os meses subsequentes de
                              vencimento_americano (correl.py, p.ex., so usa
                              candidatos[0] no CLUSTER_NACIONAL).
-------------------------------------------------------------------------
