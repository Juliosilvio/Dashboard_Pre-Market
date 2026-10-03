Historico de versoes — int.py
-------------------------------------------------------------------------
1.0.0 - 2026-09-13 - Julio - Criacao do script (classe ColetorInternacional).
                              Coleta D1 (2 anos) de todos os ativos da
                              corretora internacional listados em ativos.parquet, salva em
                              _tmp_int.parquet (consumido pelo main.py)
1.1.0 - 2026-09-13 - Julio - Coleta incremental: le a ultima data salva por
                              simbolo em historico_d1.parquet e busca so a
                              partir dali (2 anos completos apenas pra ativo
                              novo, sem historico ainda)
1.2.0 - 2026-09-13 - Julio - Coleta em ate 3 passadas: ativo que falha
                              (historico ainda nao sincronizado pelo
                              terminal com o servidor — comum em ativo novo,
                              copy_rates_range devolve vazio na hora em vez
                              de esperar o download) e retentado nas
                              passadas seguintes, com pausa curta entre elas.
                              Corrige o caso em que TODO ativo novo virava
                              falha na primeira tentativa
1.3.0 - 2026-09-13 - Julio - Coletar_symbol agora retorna o motivo
                              (symbol_select/symbol_info invalido, ou
                              last_error do MT5 quando vem sem candle) e o
                              final mostra um resumo agregado por motivo, com
                              exemplo de simbolo — pra diagnosticar de fato
                              em vez de so contar falha
1.4.0 - 2026-09-15 - Julio - Corrigido: carregar_simbolos() nao le mais
                              parquet/ativos.parquet — agora pega direto do
                              MT5 (mt5.symbols_get + atributo "visible") quem
                              esta visivel no Market Watch no momento da
                              coleta. Quem decide isso e o grade.py, a partir
                              da lista curada em json/config.json; scan_ativos
                              .py deixa de ser pre-requisito pra rodar este
                              script.
-------------------------------------------------------------------------
1.5.0 - 2026-09-20 - Julio - Corrigido bug critico de fuso: a correcao de
                              horario da corretora internacional usada aqui (adicionada
                              sem changelog numa edicao anterior) era um
                              offset fixo de -5h, mas o servidor dela segue o
                              horario de verao europeu (DST) - -5h so estava
                              certo no horario de verao europeu, errado em 1h
                              no horario de inverno. Substituido pelo modulo
                              scripts_py/fuso_horario.py (corrigir_horario_
                              corretora internacional / reverter_horario_corretora internacional_
                              escalar), que aplica -5h ou -4h conforme a
                              data. Retroagido em historico_d1.parquet
                              (16548 linhas corretora internacional).
-------------------------------------------------------------------------
