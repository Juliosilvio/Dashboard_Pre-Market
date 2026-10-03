Historico de versoes -- organizar_noticias.py
-------------------------------------------------------------------------
1.0.0 - 2026-09-27 - Julio - Criacao do script. Usuario pediu (2026-09-27)
                              uma arvore de pastas pra analise de noticias
                              dentro de backend/analise_noticias/, no
                              formato AAAA/<mes>/Nasemana/
                              diaDD-MM-AAAA_<diadasemana>.<ext>, com
                              exemplo dado: 2026/setembro/1asemana/
                              dia01-09-2026_segundafeira.txt (ou csv/
                              parquet). Duas decisoes tomadas nesta
                              versao:
                              (1) Definicao de "semana": usuario escolheu,
                              entre 3 opcoes oferecidas (blocos de 5 dias
                              uteis / semana civil seg-dom / blocos fixos
                              de 7 dias corridos), a opcao de BLOCOS FIXOS
                              DE 7 DIAS CORRIDOS (1-7, 8-14, 15-21, 22-28,
                              29-31), justificando que a analise vai
                              cruzar o impacto de noticias de 1 a 5 dias
                              atras no intraday/day trade com o que ja
                              existe no projeto pra formar vies
                              direcional.
                              (2) Formato do arquivo: usuario deixou a
                              cargo do Claude ("o que for mais leve e
                              atraente"); escolhido CSV (leve, legivel,
                              e facil de cruzar depois com pandas contra
                              as series MTF do projeto -- parquet so
                              compensaria em volume bem maior que um
                              arquivo de noticias por dia).
                              Funcoes: pasta_do_dia(), caminho_arquivo_dia(),
                              adicionar_noticia() (grava uma linha de
                              noticia no CSV do dia, criando cabecalho na
                              primeira chamada). importar_historico() foi
                              deixada como stub/NotImplementedError: o
                              usuario tambem pediu pra organizar
                              automaticamente um arquivo de historico de
                              conversas com series ja separadas por data,
                              mas isso depende de ver o formato real
                              desse arquivo (como as datas sao marcadas
                              nele) -- implementar "no escuro" arriscaria
                              cortar as datas no lugar errado. Assim que
                              o usuario mandar o arquivo real (ou um
                              trecho de exemplo), esta funcao sera escrita
                              de verdade.
                              Testado no bridge Linux (fora do projeto,
                              copia isolada em /tmp) contra 12 datas
                              cobrindo todas as viradas de bloco de semana
                              (dia 1, 7, 8, 14, 15, 21, 22, 28, 29) mais
                              fim de mes de 31 dias e mes de 30 dias, e
                              teste real de escrita/leitura do CSV
                              (cabecalho criado so na primeira linha,
                              chamadas seguintes acrescentam sem duplicar
                              cabecalho).
