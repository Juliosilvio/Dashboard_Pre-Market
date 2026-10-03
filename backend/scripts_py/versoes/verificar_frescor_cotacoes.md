# Changelog - verificar_frescor_cotacoes.py

## 1.0.0 - 2026-10-01
- Criacao do script. Watchdog de frescor das duas grades de cotacao (Risk
  Indice / Risk Dolar) - chamado automaticamente pelo main.py
  (Orquestrador._rodar_lote()), logo depois de historico.py e antes de
  alinhar_d1.py. Nao e pra uso standalone no dia a dia.
- Motivo: episodio do Dolar Teorico preso em "estimado" (PTAX proxy) por
  atraso real na coleta M1 do USDBRL que ninguem notou na hora - pedido do
  usuario foi explicito: "isso tinha que ser automatico", nao mais
  descoberto na mao perguntando "qual script puxa o m1 do usdbrl?".
- Algoritmo, em 5 passos:
  1. Resolve o universo das 28 raizes das duas grades direto de
     config.json -> grades_cotacoes.principal.feeds (last_int: uniao de
     moedas_continuo/indices_continuo/commodities_internacionais/
     vencimento_americano; sentimento_em: etfs_sentimento_em ou fallback
     EWZ/EEM), e a pasta/vigente atual de cada uma (mesma logica de
     montar_alvos() do historico.py, duplicada aqui pra nao depender do
     MetaTrader5 so pra checar frescor).
  2. Pra cada ativo, aprende sua JANELA DE PREGAO TIPICA a partir do
     proprio historico real: mediana do primeiro/ultimo horario de
     atualizacao (controle_atualizacao_mtf.parquet) dos ultimos 5 dias
     uteis - de proposito NAO assume regra fixa por classe de ativo (erro
     ja cometido antes neste projeto, ex. supor Dolar 24h quando nao e).
     Ativo com menos de 2 dias validos de historico fica de fora da
     checagem (sem base pra aprender janela).
  3. So avalia atraso de ativos cujo "agora" cai dentro da janela
     aprendida (+15min de folga) - fora da janela (mercado fechado pro
     ativo) nao e suspeito, e esperado.
  4. Calcula o atraso (agora - ultima atualizacao real) de cada ativo
     dentro da janela, tira a MEDIANA do grupo todo, e marca como
     suspeito quem passar de max(30min, 4x a mediana) - limite
     AUTOCALIBRADO: acompanha o ritmo real do pipeline no momento (evita
     falso positivo quando o loop inteiro esta mais lento) e ainda pega
     outlier de ativo unico.
  5. Pra cada suspeito, reforca via
     historico.py --reforcar M1:2 --so <raizes>, com cooldown de 45min
     por raiz (json/frescor_cotacoes_estado.json) pra nao martelar login
     MT5 repetido.
- Blindagem: todo o corpo roda em try/except amplo - erro de config
  ausente, parquet ilegivel, timeout do subprocesso de reforco (10min) ou
  qualquer outra falha e logado e engolido, NUNCA propaga pro main.py (o
  loop do pipeline nao pode travar por causa do watchdog).
- Validado contra dado real de producao (duas rodadas): primeira
  confirmou a logica de deteccao via harness com monkeypatch de
  datetime.now() (corrigindo o fato de a maquina de teste rodar em
  UTC, nao BRT, diferente da maquina Windows de producao) - sinalizou
  corretamente USDRUB como unico suspeito (~90min de atraso, janela
  aprendida 07:01-10:55 BRT) entre 28 candidatos, sem falso positivo em
  ativo de mercado fechado (EEM/EWZ) nem em ativo de cadencia normal.
  Segunda rodada, standalone e sem harness (so pra confirmar execucao
  limpa fim-a-fim), saiu com exit code 0.
- Pendente de validacao: a chamada de reforco (_reforcar(), via
  historico.py --reforcar) depende de MetaTrader5 e so pode ser testada
  de verdade na maquina Windows de producao - aqui so foi validada a
  deteccao (passos 1-4).
