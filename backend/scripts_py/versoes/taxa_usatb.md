1.0.0 - 2026-09-19 - Julio - Script criado. Converte preco -> taxa pro
                              UsaTB (T-Bill futures, corretora internacional, familia
                              vencimento_americano): taxa = 100 - preco
                              (convencao IMM, mesma de Eurodollar/SOFR/Fed
                              Funds futures). High/low se invertem na
                              conversao (preco alto = taxa baixa). Le
                              qualquer symbol comecando com "UsaTB" (ex:
                              UsaTBDec26), entao sobrevive a virada de
                              vencimento sem ajuste manual. Roda pro D1 e
                              pro M5, salva em parquet/calculos/
                              taxaUsaTBD1.parquet e taxaUsaTBM5.parquet.
                              Pedido do usuario, parte do comparativo de
                              inflacao BR x EUA via gasolina (juros ainda
                              so tinha lado brasileiro no projeto).
-------------------------------------------------------------------------
