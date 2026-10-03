Historico de versoes — dadosgov.py
-------------------------------------------------------------------------
1.0.0 - 2026-09-21 - Julio - Criacao do script. Primeira fonte de dado do
                              projeto que NAO vem do MT5 — API publica do
                              Banco Central do Brasil (SGS), sem
                              autenticacao. Pedido do usuario: comparar a
                              expectativa de juros embutida no DI1 contra a
                              taxa livre de risco definida pelo Copom — pra
                              isso faltava a Selic no projeto. Colhe 2
                              series (config.json -> dados_gov -> bcb):
                              432 (Meta Selic definida pelo Copom, a que
                              interessa pra comparar com DI1) e 11 (Selic
                              efetiva diaria, guardada tambem a pedido do
                              usuario, nao e o alvo da comparacao). Coleta
                              incremental 1x por rodada (junto com
                              vigente.py no main.py) — decisao explicita do
                              usuario de NAO manter calendario proprio do
                              Copom (pode furar com reuniao extraordinaria):
                              so pergunta pra API o que tem de novo desde a
                              ultima data salva, mesma logica de nac.py/
                              int.py. Primeira coleta pede a janela maxima
                              da propria API (10 anos). Erro de rede/API e
                              tolerante (loga e segue, nao derruba o
                              pipeline — dado nao urgente). NAO faz
                              cruzamento com DI1 (spread) — fica pra depois,
                              passo separado (precisa de merge as-of, Selic
                              e "degrau" e DI1 e continuo). Salva em
                              parquet/historicos/dadosgov/<chave>.parquet
                              (colunas data/valor). Validado offline nesta
                              versao (parsing/incremental/parquet, mockando
                              a resposta da API com o formato real
                              confirmado via consulta externa) — a chamada
                              de rede em si nao pode ser testada a partir
                              do ambiente de desenvolvimento remoto (proxy
                              de saida bloqueia api.bcb.gov.br); precisa ser
                              confirmada rodando de verdade na maquina.
-------------------------------------------------------------------------
1.0.1 - 2026-09-21 - Julio - Rodou de verdade na maquina (primeira execucao
                              real, fora do ambiente de desenvolvimento):
                              selic_efetiva (serie 11) trouxe 2506 pontos
                              certinho (~10 anos de dado diario, magnitude
                              esperada); selic_meta (serie 432, que roda
                              PRIMEIRO no loop) deu timeout ("read operation
                              timed out") na primeira chamada HTTPS do
                              processo — a segunda chamada (serie 11, mesma
                              rodada) funcionou normal, entao nao parece
                              rede fora do ar, e sim a latencia mais alta da
                              conexao HTTPS fria (primeira do processo).
                              Timeout subido de 15s pra 30s (ajuste minimo,
                              nao a logica pesada de retry — decisao
                              explicita do usuario 2026-09-21). Nada foi
                              gravado incorretamente: a falha e tratada
                              antes de qualquer escrita em parquet, entao
                              selic_meta.parquet so nao existe ainda,
                              nenhum dado corrompido.
-------------------------------------------------------------------------
1.0.2 - 2026-09-21 - Julio - selic_meta (432) continuou dando timeout mesmo
                              com 30s (2a execucao real na maquina) enquanto
                              selic_efetiva (11), com a MESMA janela de 10
                              anos, funcionou nas duas vezes — nao da pra
                              confirmar a causa exata (lado servidor ou rede
                              do usuario) sem acesso de rede a partir do
                              ambiente de desenvolvimento remoto (bloqueado
                              por allowlist de saida). Ajuste: janela inicial
                              de coleta reduzida de 10 anos (limite da API)
                              pra 3 anos — cobre com folga o historico real
                              de D1 do DI1 (2 anos), que e o dado que a
                              Selic vai ser comparada, entao nao faz falta
                              pedir os 10 anos inteiros; reduz o trabalho
                              do servidor e o tamanho da resposta. Timeout
                              tambem subido pra 45s, por seguranca. Pesquisado
                              se existe fonte alternativa oficial (API
                              Olinda/OData do BC) - nao ha um endpoint
                              documentado equivalente pra serie historica de
                              Meta Selic; a API SGS (432) continua sendo a
                              fonte padrao. Se o timeout persistir mesmo com
                              janela menor, alternativa de contorno (nao
                              implementada ainda, so registrada): aproximar
                              a Meta Selic a partir da propria selic_efetiva
                              (11, que ja coleta bem) - ela fica colada na
                              meta com variacao de poucos centesimos, entao
                              serviria como proxy imperfeito enquanto a 432
                              nao for confiavel.
-------------------------------------------------------------------------
1.0.3 - 2026-09-21 - Julio - Achada a pista real: o usuario clicou na mesma
                              URL exata que estava dando timeout via Python
                              (serie 432, janela de 10 anos) direto no
                              navegador, e abriu na hora, resposta completa.
                              Isso descarta API fora do ar, rate limit ou
                              bloqueio de rede geral — o problema e
                              especifico da chamada via Python/urllib
                              naquela maquina. Padrao classico de rota IPv6
                              quebrada/lenta: navegador tenta IPv4 e IPv6 em
                              paralelo (Happy Eyeballs) e fica com quem
                              responde primeiro; o socket do Python tenta na
                              ordem que o DNS devolve (normalmente IPv6
                              primeiro) e so cai pro IPv4 depois de esgotar
                              o timeout naquele. Fix: socket.getaddrinfo
                              sobrescrito no processo deste script pra so
                              devolver enderecos IPv4 (escopo: so afeta
                              dadosgov.py, que e single-purpose - nao mexe
                              em nada fora daqui). Validado offline
                              (import + regressao do fluxo completo com
                              urlopen mockado) - a causa raiz (rota IPv6)
                              e um diagnostico, nao uma certeza confirmada
                              por teste de rede real (nenhum ambiente que eu
                              tenho acesso consegue testar rede real contra
                              api.bcb.gov.br); precisa rodar de novo na
                              maquina do usuario pra confirmar.
-------------------------------------------------------------------------
1.0.4 - 2026-09-21 - Julio - Corrigido o 404 real que apareceu na serie 11
                              apos o fix de IPv4 (a 432 funcionou, 1096
                              pontos - janela de 3 anos confirmada certa).
                              Suspeita: pedir um intervalo cujo dataFinal e
                              HOJE, quando a Selic do dia ainda nao foi
                              publicada, faz a API devolver 404 em vez de
                              lista vazia nesse caso-limite (a serie 11 ja
                              tinha historico ate perto de hoje, entao a
                              chamada incremental pediu um intervalo curto
                              terminando em hoje). Fix: coleta agora vai so
                              ate ONTEM (horario de Sao Paulo), nunca hoje -
                              Selic nao muda intraday, entao nao faz falta o
                              dado do dia corrente na hora. Tambem: log de
                              erro agora inclui o intervalo de datas pedido,
                              pra diagnosticar sem precisar pedir print de
                              novo pro usuario. Validado offline (3 cenarios:
                              primeira coleta pede ate ontem; segunda rodada
                              no mesmo dia nao rechama a API; erro real
                              (404 simulado) loga o intervalo certo e nao
                              trava).
-------------------------------------------------------------------------
1.0.5 - 2026-09-21 - Julio - Achada a causa real do 404: o log com o
                              intervalo (novidade da 1.0.4) mostrou que o
                              pedido foi 19/09/2026 (sabado) a 20/09/2026
                              (domingo) - fim de semana inteiro, nenhum dia
                              util. Selic (432 e 11) so existe em dia util;
                              pedir um intervalo caindo so em fim de semana
                              faz a API devolver 404 em vez de lista vazia
                              nesse caso-limite. "Ate ontem" (1.0.4) nao
                              bastava porque numa segunda-feira "ontem" e
                              domingo. Fix definitivo: novo metodo estatico
                              _ultimo_dia_util() (mesma aproximacao sem
                              feriado B3 que api_server.py ja usa pro Dolar
                              Teorico) - anda pra tras a partir de agora ate
                              cair em dia de semana (seg-sex), e a coleta
                              usa esse limite em vez de "ontem" cru. Numa
                              segunda, o limite fica cravado na sexta
                              anterior ate a propria segunda virar "ontem"
                              de verdade (terca) - sabado/domingo nunca mais
                              geram pedido de rede. Validado offline
                              simulando o dia real do teste (segunda,
                              21/09/2026): limite calculado cai certinho na
                              sexta (18/09), e a segunda rodada no mesmo dia
                              nao gera nenhuma chamada (era exatamente o
                              cenario que quebrava antes).
-------------------------------------------------------------------------
