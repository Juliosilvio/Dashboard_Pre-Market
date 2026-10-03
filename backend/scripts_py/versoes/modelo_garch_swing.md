Historico de versoes — modelo_garch_swing.py
-------------------------------------------------------------------------
1.0.0 - 2026-09-27 - Julio - Primeiro modelo de "quando e a que preco" um
  proximo topo/fundo intradiario deve ocorrer, por ativo, sob demanda
  (nao continuo, nao entra no main.py). Combina: (1) horario mais
  provavel de topo/fundo, ja calculado por diag_sazonalidade_swings.py
  (json/diag_sazonalidade_swings.json, so leitura); (2) vies (sinal do
  MACD M15) e estado do IFR M5 (sobrecomprado/sobrevendido), lidos dos
  parquets de indicadores ja calculados por indicadores_mtf.py; (3) faixa
  de oscilacao esperada pro proximo candle M15 via GARCH(1,1) (biblioteca
  `arch`) sobre o retorno logaritmico do fechamento M15 - faixa =
  preco_atual x exp(+-1 sigma). Nao diferencia se o proximo extremo vai
  ser topo ou fundo (isso e sinalizado pelo vies, item 2) - simplificacao
  de primeira versao, documentada no cabecalho do script. Dependencia
  nova: `pip install arch` no venv do projeto (nao instalada ainda no
  venv do Windows, confirmado olhando o site-packages). Consumido pelo
  endpoint GET /api/modelo-swing/{raiz} (computa na hora, nao le arquivo
  pre-calculado - unico endpoint do projeto que funciona assim ate agora,
  ver comentario no api_server.py) e pelo card ModeloSwingCard.jsx no
  frontend (seletor de ativo -> chama o endpoint pro ativo escolhido).
-------------------------------------------------------------------------
