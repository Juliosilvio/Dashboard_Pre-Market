Historico de versoes -- noticias_historico.py
-------------------------------------------------------------------------
1.0.0 - 2026-09-27 - Julio - Criacao do script. Usuario pediu (2026-09-27)
                              um jeito de puxar o HISTORICO completo do
                              canal de noticias do Telegram (fonte de noticias,
                              o mesmo do noticias.py), ja que a pagina de
                              preview publica (usada pelo noticias.py) so
                              mostra os ~20 posts mais recentes, sem
                              historico nenhum. Usuario sugeriu a
                              biblioteca Telethon/Pyrogram com
                              api_id/api_hash de my.telegram.org, varrendo
                              desde 01/01/2026.

                              Implementado com Telethon, login de USUARIO
                              (nao bot) -- unico jeito de ler historico
                              completo de um canal publico via API oficial.
                              Credenciais lidas de json/config.json, chave
                              nova "telegram" (api_id/api_hash/canal/desde)
                              -- criada nesta versao com valores null,
                              pendente o usuario preencher com o que gerar
                              em my.telegram.org (nunca passado por chat,
                              mesma convencao das credenciais de corretora
                              do projeto). Sessao Telegram fica salva em
                              scripts_py/_sessao_telegram/ apos o primeiro
                              login interativo (so pode ser feito no
                              Windows do usuario, nunca na ponte Claude --
                              rede restrita la, e MTProto usa TCP direto,
                              nem passaria pelo proxy mesmo liberado).

                              Escreve direto na arvore do
                              organizar_noticias.py (analise_noticias/AAAA/
                              <mes>/Nasemana/diaDD-MM-AAAA_<diadasemana>.csv),
                              convertendo o horario UTC do Telethon pra
                              America/Sao_Paulo antes de decidir o dia --
                              testado explicitamente o caso de virada de
                              dia por fuso (mensagem as 02:00 UTC de um
                              dia cai as 23:00 do dia ANTERIOR em horario
                              de Brasilia). Diferente do noticias.py (que
                              so guarda a manchete pro card em tempo real),
                              aqui fonte e manchete vao pra colunas
                              SEPARADAS do CSV -- o historico se beneficia
                              de manter a fonte.

                              Incremental (mesmo espirito de
                              historico.py/noticias.py): grava o maior id
                              de mensagem ja processado em
                              json/controle_historico_noticias.json;
                              proxima execucao so busca id maior que esse
                              (min_id), nunca duplica. Primeira execucao
                              (sem controle ainda) usa offset_date="desde"
                              do config.json + reverse=True.

                              Logica de escrita/parsing/incremental
                              separada numa funcao PURA
                              (_processar_mensagens(), sem rede) exatamente
                              pra poder ser testada sem depender do
                              Telegram real -- testada na ponte Linux com
                              mensagens falsas simulando o formato do
                              Telethon (separacao fonte/manchete, mensagem
                              sem texto ignorada, virada de dia por fuso,
                              gravacao/leitura do controle incremental,
                              segunda rodada so pegando id novo). NAO
                              testado ainda contra a rede real do Telegram
                              (sem api_id/api_hash liberados nesta sessao,
                              e a ponte Claude nao alcancaria MTProto de
                              qualquer forma) -- avaliar o resultado da
                              primeira execucao real com cautela (conferir
                              se a data mais antiga coletada bate com
                              01/01/2026).
