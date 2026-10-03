Historico de versoes — nac.py
-------------------------------------------------------------------------
1.0.0 - 2026-09-13 - Julio - Criacao do script (classe ColetorNacional).
                              Coleta D1 (2 anos) de todos os ativos da corretora nacional
                              listados em ativos.parquet, salva em
                              _tmp_nac.parquet (consumido pelo main.py)
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
1.3.0 - 2026-09-13 - Julio - As passadas nao reduziram falha nenhuma (1094
                              falhas identicas nos dois runs) — sinal de que
                              nao e timing. Coletar_symbol agora retorna o
                              motivo (symbol_select/symbol_info invalido, ou
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
