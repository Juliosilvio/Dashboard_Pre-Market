# variacao_universo_pivo.py

## 1.0.0 - 2026-09-30 - Julio - varredura do universo amplo, sem filtro de causalidade
Pedido do usuario, depois de ver variacao_preditores_pivo.py (so 4
preditores confirmados por causalidade): "nem 1 e nem 2 por enquanto,
teste em mais ativos independente de correlacao ou causalidade, quero a
variacao intracandles d1 desses ativos". Reaproveita o metodo de
variacao_preditores_pivo.py mas troca a lista de candidatos: em vez de
filtrar por causalidadeD1.parquet, varre TODA raiz com M1.parquet direto
em parquet/historicos/MTF (~125 candidatos, menos Indice/Dolar).

## 1.1.0 - 2026-09-30 - Julio - vetorizacao (performance)
Com ~125 candidatos x 123 dias, um merge_asof por dia por candidato
(milhares de merges pequenos) estourava o tempo de execucao (>180s,
processo morto por timeout). Trocado por UM merge_asof por candidato
(tabela longa com todos os dias de uma vez, reagrupada depois por
dia_idx) -- mesmo resultado, execucao completa em ~1min30s.

## 1.2.0 - 2026-09-30 - Julio - metrica "no candle do pivo" em vez de minuto fixo
Achado do proprio debug: a mediana de candles_ate_pivo_fractal e so 6
(ver impulso_abertura.py 1.2.0). Um ranking fixo em "minuto 10" descartava
a maioria dos dias "rapidos" (que ja resolveram o pivo antes do minuto 10
e ficam NaN dali pra frente) -- GOLD/GBPUSD/ChinaA50/USDSEK apareciam com
n=8~25 dias em vez dos ~123 disponiveis, sobrando so uma amostra pequena
e enviesada pros dias "lentos". Trocado por uma metrica alinhada por dia:
o retorno do candidato exatamente NO CANDLE em que o alvo formou o pivo
(minuto_offset=-1 na tabela de saida) -- usa todos os dias, sem vies de
velocidade. Reteste confirmou n=123 (48 alta + 75 baixa) pro Indice e n=123
(63 alta + 60 baixa) pro Dolar nos 4 preditores originais, batendo com o
numero de dias real.

## 1.3.0 - 2026-09-30 - Julio - baseline flexivel (ativos de sessao estreita)
Descoberta ao investigar por que USDBRL/USDRUB apareciam com ZERO dias
validos mesmo tendo historico no periodo: o metodo usava sempre o preco
do minuto exato da abertura do alvo (minuto 0) como referencia -- ativos
cuja sessao comeca alguns minutos DEPOIS da abertura do Indice/Dolar (USDBRL
so comeca a negociar ~09:05, a abertura do B3 e ~09:00) tinham
precos[0]==NaN TODO santo dia, e o dia inteiro era descartado -- nao por
falta de dado real, so pela escolha do ponto de partida. Trocado por
baseline flexivel: usa o PRIMEIRO preco disponivel do candidato na janela
como referencia (path fica NaN antes disso, que e o correto -- o ativo
realmente nao tinha preco ainda). USDBRL/USDRUB passaram a aparecer no
ranking (ainda com n baixo, 8-19 dias -- historico deles so comeca em
2026-08-20, precisam de mais profundidade antes de tirar conclusao).

Resultado final (2026-09-30, valor no candle do pivo, Indice e Dolar): dos
~125 candidatos varridos, so ~19 tem QUALQUER preco disponivel durante a
janela de abertura do B3 -- o resto (acoes americanas individuais, ETFs
de renda fixa, DI1, commodities locais) segue horario de pregao regional
fixo e esta simplesmente FECHADO as 9h BRT (achado de estrutura de
mercado, nao bug). Dentro dos ~19 com dado: GOLD/GBPUSD/ChinaA50/USDSEK
(123 dias, ja conhecidos) confirmam divergencia pequena/moderada na
direcao "forca do dolar"; USDMXN e Euro50 aparecem com divergencia MAIOR
que qualquer um dos 4 originais (USDMXN -0.063%/+0.055% Indice/Dolar; Euro50
+0.062%/-0.037%); Usa500/UsaInd/UsaTec (CFDs com pre-market as 9h BRT) e
USDZAR/USDJPY reforcam o mesmo padrao de "risco global"/forca do dolar;
USDTRY fica essencialmente zerado (sem sinal); USDBRL/USDRUB tem sinal
aparente mas n_dias baixo, tratar como hipotese ate ter mais historico.
