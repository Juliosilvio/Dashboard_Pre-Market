Historico de versoes — correl.py
-------------------------------------------------------------------------
1.0.0 - 2026-09-13 - Julio - Criacao do script (classe AnalisadorCorrelacao).
                              Le retornoD1.parquet/retornoM5.parquet, calcula
                              a correlacao rolante (janela deslizante) do
                              retorno de cada ativo contra Indice e Dolar
                              (contrato corrente, corretora nacional) e mantem so o valor
                              mais recente de cada ativo. Filtra so quem bateu
                              LIMIAR_CORRELACAO (0.6) positivo contra INDICE ou
                              DOLAR, ordenado do mais forte pro mais fraco.
                              INDICE/DOLAR (qualquer variante) ficam fora do
                              universo analisado. Salva em
                              parquet/calculos/correlacaoD1.parquet e
                              correlacaoM5.parquet. Janela padrao: 20 (D1),
                              100 (M5).
1.1.0 - 2026-09-16 - Julio - Pedido do usuario: ordenar a tabela de cotacoes
                              do frontend "conforme o peso de cada um no
                              indice e no dolar", usando a correlacao REAL
                              (nao uma ordem fixa manual). O calculo existente
                              ja filtrava pra so quem batia LIMIAR_CORRELACAO
                              (0.6) — insuficiente pra ordenar a tabela
                              inteira (a maioria dos 27 ativos internacionais
                              mostrados nao chega no limiar, mas ainda tem
                              correlacao mensuravel). Calculo comum extraido
                              pra calcular_bruto() (sem filtro nenhum);
                              calcular() continua igual (so a positiva,
                              filtrada); novo calcular_peso() usa o mesmo
                              bruto pra montar um ranking com TODO o universo,
                              peso = maior valor absoluto entre
                              correlacao_indice/correlacao_dolar. Novo output:
                              parquet/calculos/pesoMercadoD1.parquet e
                              pesoMercadoM5.parquet — lido pelo api_server.py
                              (endpoint novo /api/peso-mercado, ver
                              api_server.md 1.5.0). Construtor de
                              AnalisadorCorrelacao ganhou o parametro
                              saida_peso_path (antes so retorno_path,
                              saida_path, janela).
-------------------------------------------------------------------------
1.2.0 - 2026-09-20 - Julio - Removida a correcao de fuso horario que este
                              script fazia sozinho (CORRECAO_FUSO_HORAS, lida
                              de config.json fuso_horario.correcao_horas) -
                              alem de ter descoberto que o offset fixo de -5h
                              usado ali estava errado metade do ano (a
                              corretora internacional segue horario de verao europeu, nao
                              um offset fixo), a correcao correta agora e
                              aplicada direto na coleta (historico_d1.parquet/
                              historico_m5.parquet ja nascem com o horario
                              certo via scripts_py/fuso_horario.py) - manter a
                              correcao aqui tambem ia corrigir em dobro.
-------------------------------------------------------------------------
1.3.0 - 2026-09-21 - Julio - Pedido do usuario: "USDBRL, INDICE, DOLAR, INDICE e
                              Dolar sao os ativos que precisam ser
                              comparados com outros ativos da grade e nao
                              comparar eles entre si" - antes so Indice/Dolar
                              eram referencia (correlacao_indice/correlacao_dolar);
                              agora Indice/Dolar/USDBRL tambem ganham sua
                              propria correlacao contra o resto da grade
                              (correlacao_indice/correlacao_dolar/
                              correlacao_usdbrl), ja que podem reagir a grade
                              internacional em horario diferente da sessao
                              B3 de Indice/Dolar. Nova constante
                              CLUSTER_NACIONAL (5 membros: indice, dolar, indice,
                              dolar, usdbrl) substitui a referencia fixa
                              Indice/Dolar; novo metodo _resolver_cluster() le
                              config.json->vigentes pra achar o ticker
                              vigente de Indice/Dolar (tem vencimento), sem
                              precisar importar historico.py (evita
                              dependencia transitiva de MetaTrader5).
                              calcular_bruto() agora exclui do universo,
                              alem da regex ^(INDICE|DOLAR) ja existente (pega
                              Indice/Dolar e toda a curva de vencimento DOLAR da
                              B3), tambem os tickers vigentes de Indice/
                              Dolar/USDBRL - nenhum dos 5 pode ser driver
                              de outro do proprio cluster (correlacao
                              tautologica, mesma grandeza economica em forma
                              diferente). calcular()/calcular_peso() e os
                              nomes/valores de correlacao_indice/correlacao_dolar
                              nao mudaram (retrocompativel - validado
                              contra pesoMercadoD1/M5.parquet e
                              correlacaoD1.parquet em producao, mesmos 104/
                              85/26 ativos, diferenca zero). Construtor
                              ganhou o parametro opcional config_path
                              (default: 3 niveis acima de retorno_path +
                              json/config.json).
-------------------------------------------------------------------------
1.4.0 - 2026-09-25 - Julio - Inicio da expansao do projeto pra alem de
                              Indice/Dolar (pedido do usuario: "vamos iniciar
                              com o UsaTec/Nasdaq"). Novo dict
                              ATIVOS_REFERENCIA_EXTRA (so UsaTec por
                              enquanto) ganha coluna correlacao_usatec em
                              pesoMercadoD1/M5.parquet, calculada do mesmo
                              jeito que correlacao_indice/dolar/indice/dolar/
                              usdbrl (grade inteira vs esse ativo). Diferenca
                              do CLUSTER_NACIONAL: UsaTec NAO e a mesma
                              grandeza economica de nada, entao continua
                              DENTRO do universo normalmente (pode ser
                              driver de INDICE/DOLAR e ter sua propria leitura ao
                              mesmo tempo) — so se auto-exclui da PROPRIA
                              coluna (correlacionar um ativo contra ele
                              mesmo sempre da ~1.0). calcular()/
                              calcular_peso()/correlacao_indice/correlacao_dolar
                              nao mudaram nada (aditivo, retrocompativel).
-------------------------------------------------------------------------
1.5.0 - 2026-09-25 - Julio - ATIVOS_REFERENCIA_EXTRA deixa de ser dict
                              hardcoded no modulo e passa a vir de
                              config.json -> ativos_referencia_extra
                              (pedido do usuario: "nao seria interessante
                              criar um arquivo json que faz isso?").
                              _resolver_extra() agora le essa chave nova do
                              config (mesmo padrao de vigentes) — adicionar
                              um ativo novo no futuro (Ouro, SP500,
                              Petroleo...) vira uma linha no JSON, sem
                              editar este arquivo. Comportamento identico
                              ao 1.4.0 pro UsaTec (config.json ja migrado
                              com a mesma entrada usatec/corretora internacional).
-------------------------------------------------------------------------
1.6.0 - 2026-09-30 - Julio - Correcao de incidente real: "Risk Dolar" e
                              card "Dolar Teorico" vazios no frontend.
                              Causa raiz: vigente.py resolveu DolarSep26
                              (contrato ja sem dado, mes rolando) como
                              vigente do Dolar em vez de DolarOct26 (que
                              ja tinha preco real). calcular_bruto() fazia
                              UM merge encadeado (inner join) com TODAS as
                              referencias do cluster de uma vez so — uma
                              unica referencia vazia zerava a base pra TODO
                              o universo, esvaziando correlacaoD1/M5.parquet
                              e pesoMercadoD1/M5.parquet por completo (nao
                              so a coluna daquela referencia). Reescrito pra
                              cada referencia fazer o PROPRIO merge com o
                              ativo, isolado das demais — referencia sem
                              dado (ou sem pontos suficientes na janela) fica
                              None so naquela coluna, sem derrubar as outras.
                              Efeito colateral positivo: correlacao de cada
                              referencia agora usa o alinhamento temporal
                              PROPRIO dela (merge individual), em vez de ficar
                              restrita a intersecao de datas de TODAS as
                              referencias ao mesmo tempo — normalmente
                              identico ao resultado anterior (mesmas datas
                              disponiveis pra INDICE/DOLAR/Indice/Dolar/USDBRL na
                              pratica), mas mais correto e resiliente pra
                              qualquer referencia com historico mais curto
                              ou com buraco pontual. calcular()/
                              calcular_peso() e o schema de saida
                              (colunas correlacao_<nome>/time/n_pontos) nao
                              mudaram.
-------------------------------------------------------------------------
