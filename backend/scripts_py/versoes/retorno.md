Historico de versoes — retorno.py
-------------------------------------------------------------------------
1.0.0 - 2026-09-13 - Julio - Criacao do script (classe CalculadorRetorno).
                              Le historico_d1.parquet e historico_m5.parquet,
                              calcula o retorno percentual do close por
                              broker+symbol (pct_change, ordenado por tempo),
                              descarta a primeira linha de cada ativo (sem
                              candle anterior pra comparar), salva em
                              parquet/calculos/retornoD1.parquet e
                              retornoM5.parquet
1.1.0 - 2026-09-13 - Julio - Calculo continua em ordem crescente por dentro
                              (cada candle comparado so com o imediatamente
                              anterior), mas a gravacao final agora sai com
                              o mais recente primeiro, por ativo — igual ao
                              padrao de export do MT5
-------------------------------------------------------------------------
