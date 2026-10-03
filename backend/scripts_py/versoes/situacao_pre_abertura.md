# Changelog - situacao_pre_abertura.py

## 1.0.0 - 2026-09-23
- Criacao do script. Monta o dataset "situacao -> resultado" discutido com
  o usuario: uma linha por pregao, cruzando o cesto de risco internacional
  (Usa500, UsaVix) pouco antes da abertura da B3 com o retorno do
  Indice/Dolar depois da abertura (30min, 60min, dia inteiro). So le parquet
  ja coletado pelo historico.py (MTF) - nao conecta no MT5.
- Requer o M5 de Usa500/UsaVix/Indice/Dolar com profundidade real (motivo do
  `historico.py --reforcar M5:720` feito antes) - com M5 raso o dataset
  sairia com poucas dezenas de linhas, insuficiente pra qualquer modelo.
- Validado contra os dados reais (2026-09-23): 486 pregoes completos,
  periodo 2024-10-04 -> 2026-09-22 (~2 anos). Correlacao linear simples
  entre as features (usa500_var_pre_pct, usavix_var_pre_pct,
  usavix_nivel_pre) e os alvos ficou fraca (|r| < 0.1) - esperado pra
  feature unica/crua contra retorno de curto prazo; e exatamente por isso
  que a proxima etapa e um modelo de verdade (nao correlacao linear), com
  validacao walk-forward, nao uma conclusao de que a ideia nao funciona.
- Bugs corrigidos durante a validacao inicial (documentados aqui porque
  sao pegadinha pra quem for mexer depois):
  - O glob de subpasta de vencimento (`<raiz>/*/m5.parquet`) pegava
    tambem a subpasta `indicadores/` (saida do indicadores_mtf.py, schema
    ifr/atr/macd, sem open/high/low/close) - restrito pro padrao
    `[0-9][0-9]-[0-9][0-9][0-9][0-9]` (mes-ano), que e o unico formato de
    subpasta de vencimento que o historico.py cria.
  - `pd.merge_asof` exige as duas chaves tz-aware com a MESMA unidade de
    tempo (us vs ns) - subtrair/somar `pd.Timedelta` numa Series
    datetime64[us, UTC] promove pra datetime64[ns, UTC] nesta versao do
    pandas, quebrando o merge contra o parquet (datetime64[us, UTC]).
    Corrigido com `.dt.as_unit("us")` apos toda soma/subtracao de
    Timedelta usada como chave de merge.
  - `merge_asof` tambem nao aceita chave nula (NaT) - o primeiro dia da
    serie nao tem "fechamento do pregao anterior" (vira NaT no shift(1)).
    Corrigido filtrando os instantes validos antes do merge e devolvendo
    com `.reindex()` pro index original (essas linhas ja saem descartadas
    depois pelo dropna de colunas essenciais).
  - Bug mais serio: Dolar estava calculando retorno em cima do PRECO DE
    ABERTURA/FECHAMENTO DO Indice (reaproveitava `dias_indice` inteiro em vez
    de montar `dias_dolar` proprio) - dava retorno em torno de -96% (Dolar
    dividido por Indice, ativos com escala de preco completamente
    diferente). Corrigido calculando `dias_dolar` separado (proprio preco
    de abertura/fechamento do Dolar), so reaproveitando o calendario/
    instante de abertura do Indice como referencia de tempo (mesma sessao).
- Saida: `parquet/calculos/situacao_pre_abertura.parquet`.
