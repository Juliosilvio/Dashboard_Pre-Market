Historico de versoes — last_nac.py
-------------------------------------------------------------------------
1.0.0 - 2026-09-15 - Julio - Criacao do script (classe ColetorLastNac).
                              Substitui o papel do tempo_real.py pro lado
                              corretora nacional ("nac"): processo dedicado, so pra
                              capturar o preco em tempo real (last, com
                              fallback pra bid quando o symbol nao tem
                              "ultimo negocio" de verdade — forex/CFD
                              continuo) de cada symbol da lista curada
                              (config.json -> ativos + vigentes, mesma logica
                              do grade.py). Nao lida mais com
                              session_close_m5/d1 — isso ja vem do
                              historico_d1/m5.parquet, obra do nac.py/
                              nac_m5.py; aqui o unico trabalho e o preco
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
                              vigente.py/grade.py/nac.py/nac_m5.py durante o
                              ciclo pesado do main.py, e o last travava atras
                              de um backfill pesado do nac.py (confirmado em
                              producao logo apos zerarmos historico_d1/m5
                              .parquet). Suporta conexao DEDICADA opcional em
                              config.json -> connections["corretora_nacional_tempo_real"]
                              (instalacao portable separada do terminal,
                              mesma conta) pra isolar de vez — cai pra conexao
                              normal "corretora nacional" enquanto essa chave nao existir.
                              So grava linha nova quando o preco muda de
                              verdade pro symbol (log de mudancas, nao
                              snapshot fixo). Buffer em memoria, gravado no
                              parquet/last_close/last_nac.parquet a cada
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
1.5.0 - 2026-09-15 - Julio - Pedido do usuario: preparar o arquivo pra servir
                              de feed de preco em tempo real pra um leitor
                              externo sem risco de colisao com a escrita no
                              Windows. Virou double buffer: self.output_path
                              (unico) virou output_path_a/output_path_b
                              (last_nac_a.parquet/last_nac_b.parquet) +
                              self._proximo_arquivo ("a"/"b"); _flush() agora
                              grava so no "proximo", nunca no mesmo que
                              acabou de gravar, e alterna a cada vez. Quem for
                              ler compara o mtime dos dois e le o mais
                              recente.
1.6.0 - 2026-09-15 - Julio - Pedido do usuario: trocar parquet por JSON — o
                              leitor decidido como sendo sempre Python (a
                              view tambem), e JSON e mais leve/trivial de
                              inspecionar pra um arquivo minusculo reescrito
                              o tempo todo, sem overhead de serializacao
                              colunar do pyarrow. Saida moveu de
                              parquet/last_close/ pra json/last_json/
                              (last_nac_a.json/last_nac_b.json); _flush()
                              agora monta uma lista de dicts (time em
                              isoformat) e grava com json.dump (mesma
                              escrita atomica .tmp + os.replace, mesmo double
                              buffer). Dependencia de pandas removida do
                              script (nao sobrou outro uso dela aqui).
1.6.1 - 2026-09-15 - Julio - Pedido do usuario: JSON saia tudo em uma linha
                              so, dificil de ler. json.dump() ganhou
                              indent=2 — arquivo agora sai formatado
                              (empilhado), so isso.
1.7.0 - 2026-09-15 - Julio - Pedido do usuario: capturar tambem session_close
                              de cada symbol, pro grafico de curva de juros
                              (DI1) no frontend precisar de 3 linhas (last,
                              session close do DI1, session close do OC1).
                              OC1 e o caso critico — e uma raiz
                              EXCECOES_SO_CLOSE (vigente.py): nunca tem last
                              nem candle D1, so symbol_info().session_close.
                              _preco_atual() virou _info_atual(): troca
                              symbol_info_tick() por symbol_info() (mesmo
                              custo de chamada MT5, cobre last/bid E
                              session_close numa passada so) e devolve os
                              dois juntos. _varrer() agora so pula um symbol
                              se AMBOS vierem None (antes so olhava o preco —
                              por isso OC1 nunca entrava no arquivo, ja que
                              nunca tem preco). Chave de deteccao de mudanca
                              virou a tupla (preco, session_close). Registro
                              JSON ganhou o campo "session_close" (null
                              quando o symbol nao tiver).
-------------------------------------------------------------------------
