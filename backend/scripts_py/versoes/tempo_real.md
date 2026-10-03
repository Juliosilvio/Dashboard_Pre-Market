Historico de versoes — tempo_real.py
-------------------------------------------------------------------------
1.0.0 - 2026-09-15 - Julio - Criacao do script (classe ColetorTempoReal).
                              Roda em loop continuo (um processo por
                              corretora, recebida como argumento de linha de
                              comando — corretora nacional ou corretora internacional), capturando
                              last, session_close_m5 (close do ultimo candle
                              M5) e session_close_d1 (close do ultimo candle
                              D1) de todo symbol visivel no Market Watch. So
                              grava linha nova quando algum dos tres valores
                              muda de verdade pro symbol — vira um log de
                              mudancas de preco, nao um snapshot de tempo
                              fixo. Raizes em EXCECOES_SO_CLOSE (OC1, mesma
                              lista do vigente.py) usam symbol_info()
                              .session_close nas duas colunas de fechamento,
                              ja que nao tem last nem candle nenhum. Buffer em
                              memoria, gravado no parquet/historicos/tempo_real
                              .parquet a cada FLUSH_A_CADA_SEGUNDOS. Para de
                              forma limpa (grava o buffer antes de sair) com
                              Ctrl+C ou quando o arquivo-sinal
                              parquet/historicos/_stop_tempo_real.flag aparece
                              (e como o main.py pede pra parar sem arriscar
                              perder o buffer, ja que terminate() no Windows
                              mata o processo sem rodar o finally).
1.1.0 - 2026-09-15 - Julio - Corrigido: os dois processos (corretora nacional e
                              corretora internacional) escreviam no MESMO parquet
                              (tempo_real.parquet) ao mesmo tempo — confirmado
                              em producao, um processo lia o arquivo enquanto
                              o outro estava no meio da escrita, corrompia
                              (TProtocolException) e o proximo flush quebrava
                              o script inteiro. Agora cada corretora grava no
                              proprio arquivo (tempo_real_corretora_nacional.parquet /
                              tempo_real_corretora internacional.parquet), zero disputa.
                              Escrita tambem virou atomica (grava num .tmp e
                              so troca de nome no final via os.replace) — se o
                              processo cair no meio do flush, o parquet
                              anterior fica intacto em vez de corrompido.
2.0.0 - 2026-09-15 - Julio - Corrigido: (1) last nao atualizava — vinha de
                              symbol_info().last, que fica parado; agora vem
                              de symbol_info_tick().last, o tick de verdade.
                              (2) estava puxando contrato demais — dependia
                              do atributo 'visible' do MT5, que o proprio
                              vigente.py polui ao testar candidatos com
                              symbol_select() (fica visivel mesmo quando o
                              candidato nunca vira 'vigente'), e como os dois
                              processos rodam ao mesmo tempo o tempo_real.py
                              pegava esse lixo antes do grade.py limpar
                              (confirmado em producao). Agora calcula a lista
                              desejada direto do config.json (ativos +
                              vigentes), a mesma logica do grade.py,
                              recarregando a cada varredura — acompanha um
                              vigente novo sem precisar reiniciar. (3) saida
                              mudou de parquet/historicos/ pra
                              parquet/last_close/ (pasta propria, criada
                              automaticamente no primeiro run).
2.1.0 - 2026-09-15 - Julio - Corrigido: last continuava sem atualizar mesmo
                              apos trocar pra symbol_info_tick() — pra ativo
                              cotado por bid/ask (forex, CFD de indice/
                              commodity continuo: EURUSD, UsaTec, Euro50 etc.)
                              o MT5 nunca preenche tick.last (fica travado em
                              0), porque esses instrumentos nao tem "ultimo
                              negocio" de verdade, so cotacao. Agora cai pro
                              tick.bid nesse caso, que se move de verdade a
                              cada tick. Ativo negociado em bolsa (Indice, Dolar,
                              DI1 etc.), que tem last de verdade, continua
                              usando tick.last normalmente.
2.2.0 - 2026-09-15 - Julio - Corrigido: last so parecia mudar de 5 em 5 (em
                              degraus, junto com o loop) em vez de seguir o
                              preco de verdade. Causa: toda volta da
                              varredura buscava session_close_m5 E
                              session_close_d1 (copy_rates_from_pos, 2
                              chamadas caras ao MT5) de TODO symbol da lista
                              curada — com ~40-60 symbols isso fazia cada
                              volta levar varios segundos, e o last so podia
                              mudar no parquet uma vez por volta inteira.
                              Agora last e fechamentos sao desacoplados: o
                              tick (last/bid, barato) e varrido bem mais
                              rapido — PAUSA_LOOP caiu de 2.0 pra 0.5s — e os
                              fechamentos M5/D1 (caros, e que so mudam quando
                              um candle novo fecha de verdade, nao a cada
                              tick) ficam em cache por symbol e so sao
                              rebuscados a cada PAUSA_FECHAMENTOS (novo,
                              20s). Resultado: last acompanha a mudanca de
                              preco na hora, no ritmo real da cotacao, sem
                              sobrecarregar a API com busca de candle
                              desnecessaria.
-------------------------------------------------------------------------
