# variacao_pre_abertura_risco_indice.py

## 1.0.0 - 2026-09-30 - Julio - serie historica pre-abertura, ativos da tabela Risco Indice
Pedido do usuario, depois de ver variacao_universo_pivo.py (que so olhava
a janela DEPOIS da abertura): "ainda nao entendeu, vamos la monte um
arquivo com as variacoes intraday (como uma serie historica e variacoes)
de todos os ativos de RiscoIndice, antes das 09:00 de N dias em uma serie
historica. entendeu? assim poderemos pegar esses 3 candles que voce disse
que forma antes do 1o pivot" -- ou seja, guardar a serie CRUA (OHLC +
retorno % acumulado) da janela ANTES da abertura do Indice, pra depois rodar
detectar_pivo_fractal() (mesma funcao de impulso_abertura.py, N=3 candles)
em cima dela.

Universo: os 14 ativos que aparecem na tabela "Risco Indice" do frontend
(QuotesTable.jsx): EWZ, USDCAD, USDJPY, USDTRY, USDRUB, USDBRL, S&P500
(Usa500), Dow Jones (UsaInd), Nasdaq (UsaTec), VIX (UsaVix), EEM, Brent,
Brentfut, DolFut (Dolar). 3 deles (Brent/UsaVix/Dolar) precisaram
resolver a subpasta de vencimento vigente (nao tem M1.parquet direto na
raiz) -- usada a pasta com dado mais recente coletado (Brent/11-2026,
Dolar/11-2026, UsaVix/10-2026), nao necessariamente o ticker exato que
config.json->vigentes aponta (ex: Brent aponta BrentDec26, mas so tem
dado coletado ate o contrato de novembro).

Janela: 120 minutos antes da abertura do Indice ate a propria abertura
(offset 0), 1 candle M1 por minuto, baseline flexivel (retorno_pct
relativo ao primeiro preco disponivel do candidato na janela, nao ao
minuto -120 exato -- mesma logica de variacao_universo_pivo.py 1.3.0).

Resultado da primeira rodada (2026-09-30): dos 14 ativos, 3 NAO tem
NENHUM dado antes das 09:00 BRT -- EWZ e EEM (ETFs americanos, mercado
so abre ~13:30 BRT, muito depois) e USDBRL (so comeca a negociar ~09:05,
ou seja, DEPOIS da abertura do B3, nunca antes). DolFut (Dolar, contrato
futuro NATIVO da B3, diferente do Dolar continuo/CFD usado no resto do
estudo) tem so ~3 minutos de dado antes da abertura -- achado real de
estrutura de mercado: o futuro de dolar nativo da B3 praticamente nao
negocia fora do horario de pregao, diferente do Dolar (CFD que replica ele
mas negocia ~24h). Os outros 10 (USDCAD/USDJPY/USDTRY/USDRUB/S&P500/
DowJones/Nasdaq/VIX/Brent/Brentfut) tem janela completa de -120 a 0
minutos, 27-29 dias cada (historico deles comeca em 2026-08-20/24).

Grava parquet/calculos/variacaoPreAberturaRiscoIndice.parquet (long
format: ativo, data, minutos_antes_abertura, horario, open, high, low,
close, retorno_pct). Isso e SO o dado cru organizado -- a deteccao de
pivo pre-abertura (proximo passo pedido pelo usuario) ainda nao foi
implementada aqui, fica pra confirmar que a janela/formato estao certos
primeiro.

## Correção 2026-10-01 - Julio - erro factual sobre horário do Dolar
O usuário apontou um erro factual: "Dolar NÃO É 24H É exatamente o mesmo
horário de dolfut e Dolar, pois são o mesmo ativo". Confirmado nos
dados: Dolar só tem candle M1 entre 09h-18h (igual Dolar) -- NÃO negocia
~24h. A frase no changelog da 1.0.0 ("DolFut, DIFERENTE do Dolar CFD que
replica ele mas negocia ~24h") estava errada -- Dolar e Dolar/DolFut são
o MESMO ativo (dólar futuro B3), com o MESMO horário de pregão, só vêm de
feeds/brokers diferentes (corretora nacional vs corretora internacional). Corrigido na docstring
do script. Isso NÃO afeta o resultado numérico já calculado (os caminhos
de arquivo usados continuam corretos), só a explicação estava errada.
