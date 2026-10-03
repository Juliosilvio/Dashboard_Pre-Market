Historico de versoes — int_m5.py
-------------------------------------------------------------------------
1.0.0 - 2026-09-13 - Julio - Criacao do script (classe ColetorInternacionalM5).
                              Coleta M5 (360 dias) de todos os ativos da
                              corretora internacional listados em ativos.parquet,
                              incremental (le a ultima data salva em
                              historico_m5.parquet), salva em
                              _tmp_int_m5.parquet (consumido pelo main.py)
1.1.0 - 2026-09-13 - Julio - Coleta em ate 3 passadas: ativo que falha
                              (historico M5 ainda nao sincronizado pelo
                              terminal — praticamente 100% dos ativos na
                              primeira coleta, ja que M5 tem muito mais
                              candle que D1 e copy_rates_range devolve vazio
                              na hora em vez de esperar o download) e
                              retentado nas passadas seguintes, com pausa
                              entre elas. Corrige o 0 candles coletados na
                              primeira execucao
1.2.0 - 2026-09-13 - Julio - As passadas nao recuperaram nenhum ativo (0
                              candles nos dois runs) — sinal de que nao e
                              timing. Coletar_symbol agora retorna o motivo
                              (symbol_select/symbol_info invalido, ou
                              last_error do MT5 quando vem sem candle) e o
                              final mostra um resumo agregado por motivo, com
                              exemplo de simbolo — pra diagnosticar de fato
                              em vez de so contar falha
1.3.0 - 2026-09-15 - Julio - Corrigido: carregar_simbolos() nao le mais
                              parquet/ativos.parquet — agora pega direto do
                              MT5 (mt5.symbols_get + atributo "visible") quem
                              esta visivel no Market Watch no momento da
                              coleta. Quem decide isso e o grade.py, a partir
                              da lista curada em json/config.json; scan_ativos
                              .py deixa de ser pre-requisito pra rodar este
                              script.
-------------------------------------------------------------------------
1.4.0 - 2026-09-20 - Julio - Mesma correcao do int.py 1.5.0: bug do offset
                              fixo de -5h substituido pela correcao DST-aware
                              de scripts_py/fuso_horario.py. Retroagido em
                              historico_m5.parquet (1890901 linhas
                              corretora internacional).
-------------------------------------------------------------------------
