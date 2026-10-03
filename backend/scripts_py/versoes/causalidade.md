Historico de versoes — causalidade.py
---------------------------------------------------------------------------
1.0.0 - 2026-09-30 - Julio - Criacao do script -- versao de PRODUCAO do
                             prototipo diag_causalidade.py (mesmo dia).
                             Reaproveita a logica de teste do prototipo
                             (MAXLAG=5, SIGNIFICANCIA=0.05, import direto
                             de _serie/_testar_par -- mesmo padrao de reuso
                             entre scripts que spread_di1_selic.py ja faz
                             com correl.py), mas so guarda resultado "SO UM
                             SENTIDO" (candidato causa o alvo, alvo nao
                             causa de volta -- bidirecional fica de fora,
                             mais provavel ser simultaneidade/fator comum
                             do que preditor de verdade) e grava num
                             formato compacto (causalidadeD1.parquet:
                             broker/symbol + causa_indice/ causa_dolar booleanos
                             + p-valor + lag), pronto pro
                             _ler_peso_mercado() do api_server.py (1.24.0)
                             so dar merge por symbol em cima de
                             pesoMercadoD1.parquet -- mesma chave. Pedido
                             do usuario depois de revisar o resultado do
                             prototipo: "adicione nas tabelas de risk mesmo
                             ja existentes" -- QuotesTable.jsx ganhou um
                             badge "G" ao lado do nome do ativo quando esse
                             ativo causa (so um sentido) o alvo daquele
                             card (Risk Dolar -> causa_dolar, Risk Indice ->
                             causa_indice), com p-valor/lag no tooltip. NAO
                             esta no loop automatico do main.py ainda
                             (mesmo status do curva_juros.py: "roda
                             manualmente por enquanto") -- ~1min de
                             execucao pesa demais pro loop apertado de
                             5min, e causalidade em D1 nao muda de candle a
                             candle mesmo. Primeira rodada real
                             (2026-09-30): 213 ativos testados, 22 causam
                             INDICE e 22 causam DOLAR "so um sentido".
---------------------------------------------------------------------------
