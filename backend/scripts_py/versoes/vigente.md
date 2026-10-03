Historico de versoes — vigente.py
-------------------------------------------------------------------------
1.0.0 - 2026-09-15 - Julio - Criacao do script (classe ResolvedorVigente).
                              Primeira versao resolvia o vigente tentando
                              cotacao no MT5 mes a mes ate achar a primeira
                              que respondesse.
1.1.0 - 2026-09-15 - Julio - Corrigido: o vigente NAO depende do MT5 — e
                              conta pura de calendario da maquina (o
                              contrato do mes corrente ja expirou no dia 01,
                              entao vigente = mes atual + 1). So depois de
                              montado o vigente, o script conecta no MT5 e
                              anda mes a mes a partir dele testando os
                              contratos seguintes — entra na lista quem tiver
                              ultimo preco (last) E fechamento diario (close,
                              candle D1 recente ate 10 dias); parava no
                              primeiro que nao tivesse os dois. Saida em
                              json/config.json, chave "vigentes" (raiz ->
                              lista de tickers, vigente primeiro).
1.2.0 - 2026-09-15 - Julio - Corrigido: as raizes a processar agora sao
                              lidas direto de json/config.json ->
                              ativos.curva_br (antes estava hardcoded no
                              script, quebrava o proposito de manter a lista
                              soh no config). RAIZES_TESTE filtra pra rodar
                              soh DI1 nesta rodada — tirar o filtro (None)
                              depois de aprovado libera OC1/DAP/FRC tambem.
1.3.0 - 2026-09-15 - Julio - Corrigido: a curva brasileira de juros vai ate
                              10 anos a frente e fica esparsa quanto mais
                              longe (mensal, depois trimestral, depois so
                              janeiro) — o script parava cedo demais porque
                              tratava o primeiro mes sem contrato como fim da
                              lista. Agora varre os 10 anos inteiros
                              (JANELA_ANOS) a partir do vigente sem parar no
                              primeiro buraco, coletando todo mes que tiver
                              preco real.
1.4.0 - 2026-09-15 - Julio - Corrigido: a lista ainda saia curta (parava logo
                              depois do trecho mensal denso), porque
                              symbol_select() num ticker que nao estava
                              visivel no Market Watch nao populaa info/rates
                              na hora — o terminal precisa de um instante pra
                              sincronizar com o servidor (mesmo motivo das
                              passadas com pausa que ja existiam no
                              nac.py/int.py). Agora tenta de novo
                              (TENTATIVAS_SYNC=3, pausa de 1s) antes de
                              descartar um ticker como "sem preco".
1.5.0 - 2026-09-15 - Julio - Aprovado o DI1, estendido pra toda a curva_br:
                              RAIZES_TESTE passa a incluir DI1, OC1, DAP e
                              FRC. Nenhuma mudanca de logica necessaria — a
                              varredura mes a mes ja nao dependia de
                              calendario teorico fixo, entao cobre sozinha o
                              caso do DAP (que nao segue ciclo mensal
                              uniforme, fica denso perto e esparso longe).
1.6.0 - 2026-09-15 - Julio - Dois ajustes: (1) o calculo do "agora" tinha
                              ido pra UTC por engano — voltado pra hora LOCAL
                              da maquina (fuso do Brasil), senao nas ultimas
                              horas de cada dia o vigente podia adiantar um
                              mes por engano perto da virada; (2) OC1 e
                              excecao — so tem fechamento diario (close),
                              nunca ultimo preco (last). Criterio de "tem
                              preco real" agora aceita EXCECOES_SO_CLOSE
                              (raizes onde so o close conta, sem exigir
                              last).
1.7.0 - 2026-09-15 - Julio - Corrigido: OC1 continuava saindo com so o
                              vigente (nenhum subsequente entrava). Causa:
                              o close do OC1 so atualiza quando ha
                              reprecificacao teorica da curva, nao todo dia
                              (Mudanca diaria -100% no Market Watch confirma
                              que nao ha tick/last nunca) — entao o filtro
                              de recencia (RECENCIA_MAX_DIAS=10) descartava
                              contratos com close real mas desatualizado.
                              Pra raizes em EXCECOES_SO_CLOSE, o criterio
                              agora exige so um close valido (nao-zero),
                              sem checar recencia.
1.8.0 - 2026-09-15 - Julio - Corrigido de vez com dado real: confirmado via
                              symbols_get(group="OC1*") que
                              copy_rates_from_pos volta vazio pra TODOS os
                              45 symbols OC1 (nao e so questao de recencia —
                              nao existe candle D1 nenhum pra essa raiz). O
                              preco real do OC1 vem de
                              symbol_info().session_close, que veio populado
                              (nao-zero) em todos os 45. EXCECOES_SO_CLOSE
                              agora checa session_close em vez de tentar
                              close via candle.
2.0.0 - 2026-09-15 - Julio - Estendido pra segunda familia: ativos.
                              vencimento_americano (corretora internacional, padrao
                              raiz+nome do mes+ano). Diferente da curva_br,
                              aqui o vigente PRECISA consultar o MT5 —
                              tenta mes atual+1 e, se ainda nao existir na
                              corretora, cai pro mes atual (fallback pro
                              contrato que ja deve estar ativo). Varredura
                              dos subsequentes numa janela menor
                              (JANELA_MESES_AMERICANO=12), ja que a
                              corretora internacional nao pre-lista anos a frente feito
                              a B3. executar() agora conecta na corretora nacional,
                              processa curva_br, desconecta, conecta na
                              corretora internacional, processa vencimento_americano,
                              desconecta — as duas familias no mesmo
                              config.json["vigentes"].
2.2.0 - 2026-09-16 - Julio - Adicionado "DDI" a RAIZES_TESTE (pedido do
                              usuario: adicionou "DDI" em ativos.curva_br no
                              config.json, pra montar a curva americana
                              implicita via paridade de juros DI1 x cupom
                              cambial). Sem esse ajuste, carregar_raizes_
                              curva_br() ignoraria a raiz nova silenciosamente
                              (so processa quem esta nos dois lugares:
                              config.json E RAIZES_TESTE) e vigentes["DDI"]
                              nunca seria criado — quebrando em cadeia o
                              grade.py (cairia no fallback vigentes.get(
                              "DDI", ["DDI"]) e tentaria selecionar um ticker
                              literal "DDI", que nao existe na B3) e por
                              tabela o last_nac.py (nunca veria DDI visivel
                              no Market Watch pra coletar). DDI e future
                              padrao (tem last e close normais, como DI1/DAP/
                              FRC) — nao entra em EXCECOES_SO_CLOSE.
2.3.0 - 2026-09-17 - Julio - Adicionado "DOLAR" a RAIZES_TESTE (pedido do
                              usuario, junto com a troca do card Dolar
                              Teorico no api_server.py 1.8.0: "usa o dolarv26
                              da corretora nacional pra calcular"). Mesmo motivo/mecanismo
                              da DDI na 2.2.0 (config.json E RAIZES_TESTE
                              precisam da raiz nova pros dois lados, senao
                              vigentes["DOLAR"] nunca seria criado) — DOLAR
                              tambem e future padrao (last + close normais),
                              nao entra em EXCECOES_SO_CLOSE. Motivo de
                              processar o DOLAR pela MESMA resolver_raiz() do
                              DI1/FRC/DDI em vez de um caminho proprio: o
                              vigente do DOLAR cai sempre no MESMO mes do
                              DI1/FRC (todos usam _mes_vigente() = mes
                              atual+1), fechando o descasamento de vertice
                              que existia comparando com o Dolar da
                              corretora internacional (vence no ultimo dia util do mes,
                              nao no primeiro feito DI1/FRC/DDI/DAP) — ver
                              _dolar_teorico() no api_server.py 1.8.0 pro
                              detalhe completo do calculo e do desconto
                              du/dc pro vencimento real do DOLAR.
-------------------------------------------------------------------------
2.4.0 - 2026-09-18 - Julio - Pedido do usuario: adicionado "Gasol" em
                              ativos.vencimento_americano (config.json) —
                              essa familia ja e 100% generica no script
                              (RAIZES_TESTE_AMERICANO = None le tudo do
                              config), entao a raiz nova nao precisou de
                              mudanca de codigo pra ser processada. So que o
                              main.py salvou o vigente errado (GasolSep26 em
                              vez de GasolOct26, que era o mes de verdade) —
                              diagnosticado com diag_gasol.py: GasolOct26 JA
                              EXISTIA no terminal e tinha candle D1 recente,
                              mas o "last" ficava 0.0 (contrato cota por
                              book, nao por ultimo negocio) e o criterio
                              antigo de _tem_preco_real() exigia last != 0,
                              entao o candidato de outubro nunca passava e o
                              script ficava preso em setembro (que a
                              corretora ja tinha ate removido do terminal
                              quando o usuario conferiu). Corrigido com o
                              parametro usar_bid_ask em _tem_preco_real():
                              quando True (resolver_raiz_americano() sempre
                              passa True agora), aceita bid OU ask != 0 em
                              vez de exigir last — a familia curva_br
                              continua usando last (default, sem mudanca de
                              comportamento pra DI1/FRC/DDI/DOLAR/DAP).
-------------------------------------------------------------------------
2.5.0 - 2026-09-30 - Julio - Corrigido junto com o correl.py (mesmo
                             incidente Risk Dolar/Dolar Teorico vazios):
                             resolver_raiz_americano() confiava cegamente
                             que "mes atual" ainda estava ativo quando
                             "mes+1" nao existia -- nunca reconfirmava com
                             o MT5. Quebrou no Dolar quando a corretora internacional
                             rolou o contrato direto de Set26 pra Nov26
                             (sem Out26 no meio): nem Set26 (ja rolado) nem
                             Out26 (nunca existiu) tinham preco real, mas o
                             script ficava preso no Set26 morto porque
                             nunca testava o "mes atual" antes de aceitar.
                             Isso alimentava vigente errado pro
                             _dolar_teorico() (api_server.py), que buscava
                             vertice FRC pro vencimento do Dolar errado e
                             caia no erro "Faltando dado real de FRC".
                             Reescrito para testar candidato a candidato
                             (mes+1, mes atual, mes+2, mes+3... ate
                             JANELA_MESES_AMERICANO meses a frente) e usar
                             o primeiro que realmente tiver preco real
                             (bid/ask) via MT5 -- nunca mais aceita um mes
                             as cegas. mes+1 continua com prioridade sobre
                             mes atual (mesma ordem de antes), mas agora so
                             entra se passar no teste de verdade; se nenhum
                             candidato da janela passar, cai no
                             comportamento antigo (mes atual sem garantia)
                             so pra nao devolver lista vazia -- esse caso
                             extremo precisa de investigacao manual.
                             Aplicado direto no arquivo em producao a
                             partir de screenshots do usuario mostrando a
                             tabela Risk Dolar vazia e o card Dolar Teorico
                             com erro; confirmado pelo usuario que a causa
                             foi a corretora internacional ja ter rolado o Dolar pra
                             novembro. A parte de leitura de bid/ask no MT5
                             (_tem_preco_real) nao pode ser testada a
                             partir deste ambiente (sem terminal MT5
                             acessivel) -- validado por revisao de codigo +
                             compilacao; confirmacao real vem do proximo
                             ciclo do vigente.py resolvendo Dolar para
                             DolarNov26.
---------------------------------------------------------------------------
2.6.0 - 2026-09-30 - Julio - Mesmo incidente Risk Dolar/Dolar Teorico
                             vazios, 3a causa raiz do dia: resolver_raiz()
                             (familia curva_br/corretora nacional --
                             DI1/FRC/DDI/DOLAR/DAP) tinha o MESMO bug
                             generico que o resolver_raiz_americano()
                             (corrigido mais cedo hoje, v2.5.0) -- o
                             candidato de posicao 1 (mes_ref+1) virava
                             "vigente" sem passar por _tem_preco_real(), so
                             os candidatos seguintes eram verificados. Pra
                             DI1/DDI/DAP/DOLAR nunca deu problema (o mes+1
                             deles sempre tem preco real). Pro FRC deu:
                             FRCV26 (mes+1 de hoje) nunca teve UM preco
                             real sequer (nem double buffer, nem
                             retornoD1.parquet) e mesmo assim virava
                             vigente as cegas -- _dolar_teorico()
                             (api_server.py) ficava permanentemente preso
                             em "faltando dado real de FRC" tentando ler um
                             vertice morto. Reescrito pra andar candidato a
                             candidato (mes_ref+1, +2, +3... ate
                             JANELA_MESES a frente) e usar o PRIMEIRO que
                             realmente tiver preco real -- exatamente o
                             mesmo padrao do resolver_raiz_americano()
                             2.5.0, so que aplicado na familia curva_br.
                             Resultado real apos o fix: FRC vigente saiu de
                             FRCV26 (morto) pra FRCZ26 -- 2 meses a frente
                             do DOLAR, nao 1 como o codigo antigo de
                             api_server.py assumia (ver api_server.py
                             1.23.0, que parou de calcular esse vertice e
                             passou a usar o vigente resolvido aqui
                             direto). Backup: vigente.py.bak_antes_walk_for
                             ward_b3_20260930_182317.
---------------------------------------------------------------------------
