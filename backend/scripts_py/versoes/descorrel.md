Historico de versoes — descorrel.py
-------------------------------------------------------------------------
1.0.0 - 2026-09-13 - Julio - Criacao do script (classe AnalisadorDescorrelacao).
                              Mesmo calculo do correl.py (correlacao rolante
                              do retorno de cada ativo contra Indice e Dolar,
                              valor mais recente por ativo), mas filtra so
                              quem bateu -LIMIAR_CORRELACAO (0.6) negativo
                              contra INDICE ou DOLAR, ordenado do mais negativo pro
                              menos negativo. INDICE/DOLAR (qualquer variante)
                              ficam fora do universo analisado. Salva em
                              parquet/calculos/descorrelacaoD1.parquet e
                              descorrelacaoM5.parquet. Janela padrao: 20 (D1),
                              100 (M5).
-------------------------------------------------------------------------
1.1.0 - 2026-09-20 - Julio - Mesma correcao do correl.py 1.2.0: removida a
                              correcao de fuso horario redundante (e com
                              offset fixo errado) que este script fazia
                              sozinho - historico_d1/m5.parquet ja nascem com
                              o horario certo desde a coleta.
-------------------------------------------------------------------------
