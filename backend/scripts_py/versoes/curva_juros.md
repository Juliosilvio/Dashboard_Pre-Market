1.0.0 - 2026-09-21 - Julio - Primeira versao. Indice de taxa de juros de prazo constante (constant maturity), interpolado linearmente em dias uteis (DU/252) a partir de TODOS os vertices do DI1 configurados em ativos.curva_br (40 vertices). Vencimento de cada vertice = primeiro dia util do mes de vencimento (mesma aproximacao sem calendario de feriados B3 ja usada no _ultimo_dia_util do api_server.py/dadosgov.py). Calcula "DI de 1 ano" (252 DU) e "DI de 2 anos" (504 DU), sem extrapolar (NaN quando o prazo alvo fica fora do range de vertices disponiveis naquele dia). Compara com a Meta Selic (dadosgov.py) via merge_asof, gerando spread_1ano e spread_2anos. Salva em parquet/calculos/curva_juros.parquet. Validado com dados reais: DI 2 anos com cobertura quase completa (473/498 dias, desde 2024-09-20) porque o vertice mais curto com historico profundo (DI1V26) ja nascia perto de 2 anos do proprio vencimento; DI 1 ano so fica valido a partir de 2025-10-14 (233/498 dias) porque config.json so lista vertices ATUALMENTE negociados - contratos curtos que ja venceram nunca foram coletados, entao nao da pra reconstruir o "1 ano" mais pra tras sem inventar dado. Ultimo ponto real (21/09/2026): DI 1 ano = 13,55%, DI 2 anos = 13,69%, Selic meta = 13,75% (spread_1ano = -0,20pp, spread_2anos = -0,06pp).

## 1.0.1 - 2026-09-21
- Corrigido MergeError no merge_asof de comparar_com_selic(): a coluna
  'data' do indice DI1 (derivada do parquet MTF) e a da Selic (dadosgov)
  vinham em dtypes datetime64 de unit diferente (us/s vs ns) - pandas 2.x
  exige unit identico no merge_asof, mesmo as duas sendo datetime. Ambas
  as colunas agora sao forcadas pra datetime64[ns] antes do merge (mesmo
  padrao de fix ja usado no backtest_vies_direcional.py pro mesmo tipo de
  erro).
