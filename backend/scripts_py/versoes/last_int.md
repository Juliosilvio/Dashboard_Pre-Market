Historico de versoes — last_int.py
-------------------------------------------------------------------------
1.0.0 - 2026-09-15 - Julio - Criacao do script (classe ColetorLastInt).
                              Substitui o papel do tempo_real.py pro lado
                              corretora internacional ("int"): processo dedicado, so pra
                              capturar o preco em tempo real (last, com
                              fallback pra bid quando o symbol nao tem
                              "ultimo negocio" de verdade — forex/CFD
                              continuo) de cada symbol da lista curada
                              (config.json -> ativos + vigentes, mesma logica
                              do grade.py). Nao lida mais com
                              session_close_m5/d1 — isso ja vem do
                              historico_d1/m5.parquet, obra do int.py/
                              int_m5.py; aqui o unico trabalho e o preco
                              correndo, o que deixa a varredura bem mais leve
                              e rapida (so um symbol_info_tick por symbol,
                              sem copy_rates_from_pos nenhum). Motivo de
                              existir como script proprio em vez do
                              tempo_real.py continuar servindo os dois lados
                              por argumento: mesmo como processo Python
                              separado, qualquer processo que conecta com o
                              MESMO path/login/server do MT5 gruda no MESMO
                              terminal64.exe ja aberto — entao o tempo_real
                              ficava competindo pelo mesmo canal de IPC com
                              vigente.py/grade.py/int.py/int_m5.py durante o
                              ciclo pesado do main.py, e o last travava atras
                              de um backfill pesado do int.py (confirmado em
                              producao logo apos zerarmos historico_d1/m5
                              .parquet). Suporta conexao DEDICADA opcional em
                              config.json -> connections["corretora internacional_tempo_real"]
                              (instalacao portable separada do terminal,
                              mesma conta) pra isolar de vez — cai pra conexao
                              normal "corretora internacional" enquanto essa chave nao
                              existir. So grava linha nova quando o preco
                              muda de verdade pro symbol (log de mudancas,
                              nao snapshot fixo). Buffer em memoria, gravado
                              no parquet/last_close/last_int.parquet a cada
                              FLUSH_A_CADA_SEGUNDOS, escrita atomica (.tmp +
                              os.replace). Para de forma limpa (grava o
                              buffer antes de sair) com Ctrl+C ou quando o
                              arquivo-sinal parquet/historicos/_stop_last
                              .flag aparece (main.py cria esse sinal — no
                              Windows terminate() mataria o processo sem
                              rodar o finally).
1.1.0 - 2026-09-15 - Julio - Corrigido bug real de producao: _lista_desejada()
                              relia o config.json do zero a cada volta da
                              varredura (0.3s, ~200x/minuto, pra sempre) — mas
                              o vigente.py escreve NESSE MESMO ARQUIVO uma vez
                              por volta do pipeline (~5min). Ler no instante
                              exato da escrita dele (arquivo bloqueado no
                              Windows, ou JSON incompleto) derrubava o
                              processo inteiro sem nenhum tratamento, e o
                              main.py nao reinicia o coletor sozinho — isso
                              explicava o preco "funcionar e depois sumir",
                              sem nenhuma relacao com terminal MT5
                              compartilhado (a hipotese que estavamos
                              perseguindo antes). Agora a lista fica em cache
                              por LISTA_DESEJADA_CACHE_SEGUNDOS (30s) e
                              qualquer falha de leitura mantem a lista
                              anterior em vez de quebrar. O loop principal
                              tambem passou a encapsular _varrer()/_flush()
                              em try/except — nenhum erro transiente derruba
                              mais o processo 24/7, so loga e segue.
1.2.0 - 2026-09-15 - Julio - Correcao definitiva (a 1.1.0 so cacheava a
                              leitura do config.json, o usuario apontou que o
                              certo era tirar o arquivo da jogada de vez):
                              _lista_desejada() volta a perguntar direto pro
                              terminal MT5 (mt5.symbols_get().visible, uma
                              chamada em memoria/IPC, zero disco) em vez de
                              ler config.json. O coletor agora NUNCA toca em
                              arquivo durante a varredura — so conversa com o
                              terminal — o que elimina de vez a corrida com o
                              vigente.py (que escreve config.json uma vez por
                              volta do pipeline). O grade.py continua sendo
                              quem decide o que fica visivel a partir da
                              lista curada; este coletor so segue. Efeito
                              colateral aceito: por um instante, enquanto o
                              vigente.py testa candidatos, um deles pode
                              aparecer visivel e gerar uma linha a mais no
                              parquet — autocorrige sozinho no ciclo
                              seguinte, e e infinitamente melhor que o
                              processo inteiro morrer (que era o problema
                              real). LISTA_DESEJADA_CACHE_SEGUNDOS removida
                              (nao faz mais sentido, nao ha mais leitura de
                              arquivo pra cachear).
1.3.0 - 2026-09-15 - Julio - Pedido do usuario: o arquivo virou tabela de
                              preco corrente (uma linha por symbol,
                              sobrescrita a cada flush) em vez de log de
                              historico (uma linha nova por mudanca,
                              acumulando pra sempre) — o log crescia rapido
                              demais pra quem so queria o preco atual (ex:
                              UsaTec gerou 485 linhas em 29 minutos). buffer
                              (lista) virou estado_atual (dict symbol->linha)
                              + flag _sujo; _flush() agora sobrescreve o
                              parquet inteiro em vez de ler+concatenar.
1.4.0 - 2026-09-15 - Julio - Pedido do usuario: o flush nao podia mais
                              esperar FLUSH_A_CADA_SEGUNDOS (30s) — tinha
                              que ser bem menor que 1s, ou a cada mudanca de
                              preco por ativo. Como o guard _sujo ja garante
                              que _flush() so escreve de verdade quando algo
                              mudou desde o ultimo flush, a solucao foi
                              tirar o time-gate: executar() agora chama
                              _flush() a cada volta do loop, junto com
                              _varrer() (a cada PAUSA_LOOP = 0.3s), em vez
                              de esperar uma janela de 30s. Constante
                              FLUSH_A_CADA_SEGUNDOS removida (nao faz mais
                              sentido — nao ha mais janela de tempo pra
                              configurar). Efeito pratico: qualquer mudanca
                              de preco aparece no parquet dentro de ~0.3s,
                              e quando o mercado esta parado o flush nao
                              custa quase nada (so o `if not self._sujo:
                              return` no topo).
1.5.0 - 2026-09-15 - Julio - Pedido do usuario: mesmo pedido de double buffer
                              feito pro last_nac.py. FALHA DE PROCESSO: o
                              cabecalho deste script foi atualizado descrevendo
                              o double buffer, mas o CODIGO (__init__/_flush)
                              nao chegou a ser alterado — ficou rodando a
                              versao anterior (self.output_path unico,
                              last_int.parquet) por engano. Bug so percebido
                              na 1.6.0 abaixo, comparando com o last_nac.py
                              (que recebeu a implementacao de verdade).
1.6.0 - 2026-09-15 - Julio - Corrige a lacuna da 1.5.0 (double buffer nunca
                              implementado de fato) E aplica o pedido do
                              usuario de trocar parquet por JSON, tudo numa
                              vez so: output_path unico virou
                              output_path_a/output_path_b
                              (last_int_a.json/last_int_b.json) +
                              self._proximo_arquivo ("a"/"b"); _flush() grava
                              so no "proximo" a cada vez (double buffer de
                              verdade agora) e monta uma lista de dicts (time
                              em isoformat) gravada com json.dump em vez de
                              pd.DataFrame.to_parquet (mesma escrita atomica
                              .tmp + os.replace). Saida moveu de
                              parquet/last_close/ pra json/last_json/.
                              Dependencia de pandas removida do script.
1.6.1 - 2026-09-15 - Julio - Pedido do usuario: JSON saia tudo em uma linha
                              so, dificil de ler. json.dump() ganhou
                              indent=2 — arquivo agora sai formatado
                              (empilhado), so isso.
1.7.0 - 2026-09-16 - Julio - Pedido do usuario: variacao diaria na tabela de
                              cotacoes do frontend — precisa comparar o preco
                              corrente (last) com o fechamento oficial da
                              sessao anterior (session_close), que este
                              arquivo nao gravava. Mesma tecnica ja aplicada
                              no last_nac.py 1.7.0: _preco_atual() virou
                              _info_atual(), trocando symbol_info_tick() por
                              symbol_info() (mesma chamada MT5, cobre
                              last/bid E session_close numa passada so) —
                              devolve (preco, session_close). _varrer() so
                              pula um symbol se os DOIS vierem None (antes so
                              olhava o preco). Chave de "mudou desde a ultima
                              volta" virou a tupla (preco, session_close).
                              Registro do JSON ganhou o campo "session_close"
                              (null quando o symbol nao tiver).
-------------------------------------------------------------------------
1.8.0 - 2026-09-18 - Julio - Pedido do usuario: "TODOS OS CONTRATOS DA
                              corretora internacional DEVEM VIR PARA O DASHBOARD COM
                              MEDIA ENTRE bid e ask" (coluna Preco da tabela
                              de cotacoes do frontend). _info_atual() trocou
                              o preco corrente de "last, com fallback pra
                              bid" pra "media entre bid e ask, com fallback
                              em cascata pra um dos dois isolado e por
                              ultimo pra last". Motivo: investigando por que
                              o vigente.py nao promovia o GasolOct26
                              (diag_gasol.py), descobrimos que contratos da
                              corretora internacional cotam por BOOK — "last" fica 0.0
                              por tempo indeterminado mesmo com o symbol
                              ativo e negociando, e usar so um lado do book
                              (bid OU ask, como antes) nao reflete o preco
                              justo tao bem quanto o meio do spread. Campo
                              do JSON continua se chamando "last" (mudanca e
                              so de CALCULO, nao de formato — evita mexer em
                              api_server.py/QuotesTable.jsx/client.js a
                              toa). Efeito colateral bom: USDBRL passa por
                              aqui e alimenta o spot_usdbrl de
                              _dolar_teorico() no api_server.py — o meio do
                              book e referencia mais estavel que um lado so
                              do spread.
-------------------------------------------------------------------------
