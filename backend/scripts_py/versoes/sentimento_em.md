# Changelog - sentimento_em.py

## 1.0.0 - 2026-09-29
- Criacao do script. Cotacao "atual" + variacao intradiaria de EWZ
  (iShares MSCI Brazil) e EEM (iShares MSCI Emerging Markets) pra grade
  de cotacoes do frontend - pedido do usuario ("colocar o EWZ no Risk
  indice", ampliado pra EEM: "ambos ja estao visiveis").
- Mesmo padrao de magnificas.py: le direto o parquet de MTF ja
  alimentado por historico.py 1.4.0 (grupo "etfs_sentimento_em") +
  ExportadorMt5Stock.mq5 1.01 (Service MQL5 nativo, contorna o bug
  "Out of memory" do terminal mt5stock via API Python) - nenhuma
  conexao MT5 propria. Double buffer (sentimento_em_a/b.json),
  mtime-watch, mesmo formato de saida de last_int.py/magnificas.py.
- Placement na grade Risk Indice vs. Risk Dolar NAO e decidido aqui -
  quem decide e separarIndiceDolar() no frontend, com base na
  correlacao real calculada por correl.py. Primeira leitura real
  (2026-09-29): EWZ correlacao_indice=0.955 (Indice), EEM
  correlacao_indice=0.190/correlacao_dolar=-0.464 (Dolar).
