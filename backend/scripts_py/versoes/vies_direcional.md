# Changelog - vies_direcional.py

## 1.0.0 - 2026-09-21
- Criacao do script (classe MotorViesDirecional). Primeira versao do
  motor de decisao pedido pelo usuario 2026-09-21: "precisa o tempo
  todo ter arquivo avisando se da ou nao pra montar posicao em DOLAR ou
  INDICE, e qual a posicao mais indicada". Nao calcula nem sugere preco de
  entrada (isso continua manual, o usuario olha a tela) — so aponta
  direcao e timing de entrada dentro dela.
- Universo de ativos: todo alvo de historico.py/montar_alvos(), exceto
  Indice/Dolar (sao o alvo), Indice/Dolar (mesmo instrumento que Indice/Dolar
  via corretora internacional — correlacao tautologica, pedido explicito do
  usuario) e OC1/DAP/DOLAR(curva_br) (nao pedidos). De curva_br entram
  DI1 (Juros)/FRC/DDI, reduzidos ao vertice mais proximo (front) de
  cada curva — leitura mais fina do DI1 (retorno de minima/maxima ate
  o preco, regiao de IFR do DI1) fica pra um estudo a parte, o usuario
  deixou isso explicito.
- Voto por ativo, por TF maior (H1/H4/D1): sinal do histograma MACD;
  IFR confirma (peso 1.0 se concorda, 0.5 se discorda) em vez de votar
  sozinho — regra do usuario, pra nao deixar o IFR (indicador de
  reversao a media) brigar com uma tendencia forte. TFs combinados em
  media ponderada, D1 > H4 > H1 (TF_PESOS), tambem decisao do usuario.
- Vies final: voto de cada ativo multiplicado pela correlacao COM
  SINAL que o correl.py ja calcula (pesoMercadoD1.parquet,
  correlacao_indice/correlacao_dolar, sem filtro de limiar) — inverte
  sozinho quando a correlacao e negativa, pesa mais quem anda mais
  junto/contra. Soma normalizada pela soma dos pesos absolutos vira o
  score; LIMIAR_NEUTRO=0.15 decide alta/baixa/neutro.
- Refinamento de entrada: le o IFR M1/M5 em tempo real que o
  last_indicadores_nac.py ja calcula pra Indice/Dolar e detecta o
  cruzamento de VOLTA pra dentro da zona 25/75 (decisao do usuario —
  nem o classico 30/70 nem um numero so meu) na mesma direcao do vies
  ja apurado. Gatilho oficial usa M5 (menos ruido); M1 fica exposto
  como informativo.
- Mesmo padrao arquitetural de last_nac.py/last_int.py/
  last_indicadores_nac.py: double buffer + escrita atomica + guard de
  "mudou desde a ultima volta" (so reabre parquet quando o mtime do
  indicador ou do peso mudou de verdade) + parada limpa via
  parquet/historicos/_stop_last.flag (compartilhado com os outros tres
  processos continuos). Saida em
  json/last_json/vies_direcional_a.json e vies_direcional_b.json.
- Registrado no main.py (proc_last), com janela de console propria
  (CREATE_NEW_CONSOLE) — nao conecta no MT5, mesma logica do
  last_indicadores_nac.py. Ver main.py 4.1.0.
- Validado com dados reais da MTF do usuario: universo de 33 ativos
  (28 com correlacao ja calculada), score/vies calculado pra INDICE e DOLAR,
  refinamento de entrada lido do double buffer do
  last_indicadores_nac.py — sem gatilho no momento do teste (IFR fora
  da zona de cruzamento).

## 1.1.0 - 2026-09-21
- RAIZES_EXCLUIDAS ganhou USDBRL, alem de Indice/Dolar — correcao do
  usuario apos o USDBRL ter dominado sozinho um teste de backtest
  (correlacao de 0,84-0,97 com INDICE/DOLAR): USDBRL e ativo NACIONAL, a
  MESMA grandeza que o Dolar (dolar futuro), so que a vista em vez de
  futuro — nao pode ser driver/confirmacao independente, mesma logica
  tautologica de Indice/Dolar.

## 1.2.0 - 2026-09-21
- Grupos indice/dolar (pedido do usuario): Indice+Indice = grupo INDICE;
  Dolar+Dolar+USDBRL = grupo DOLAR. Nenhum membro de um grupo compara
  com outro do MESMO grupo (correlacao_indice/correlacao_indice nunca
  entram como referencia um do outro, mesma logica de RAIZES_EXCLUIDAS)
  — mas agora o score de Indice pondera o voto de cada ativo da grade
  pela correlacao com Indice E com Indice somadas (GRUPO_INDICE); o score
  de Dolar pondera por Dolar, Dolar E USDBRL (GRUPO_DOLAR). Cada
  correlacao usada continua sendo grade-vs-um-membro-do-cluster,
  calculada pelo correl.py 1.3.0 — nunca cluster-vs-cluster. Novo
  metodo estatico _acumular_grupo() faz o pooling; _ler_peso() agora le
  as 5 colunas de correlacao (antes so indice/dolar). Validado com dados
  reais: INDICE (indice) score -0,197 (baixa, 27 ativos), DOLAR (dolar)
  score +0,094 (neutro, 27 ativos) — mesma ordem de grandeza de antes,
  como esperado (Indice/Dolar/USDBRL correlacionam em lockstep com
  Indice/Dolar, entao o pooling refina mas nao muda o sinal).

## 1.3.0 - 2026-09-25
- Inicio da expansao pra alem de Indice/Dolar (pedido do usuario: "vamos
  iniciar com o UsaTec/Nasdaq"). calcular_vies() generalizado pra um loop
  so, com um acumulador por alvo (indice/dolar continuam identicos, ganha um
  terceiro "usatec" via novo dict ALVOS_EXTRA). Diferenca de indice/dolar:
  usatec nao tem par de instrumento gemeo (nada tautologico com ele) —
  so uma coluna de correlacao (correlacao_usatec, calculada pelo correl.py
  1.4.0), e o proprio correl.py ja zera a correlacao dele contra ele
  mesmo, entao ele nunca vota na propria pontuacao. Refinamento de entrada
  (gatilho M5 saindo da zona 25/75) ganhou calcular_refinamento_extra() —
  como usatec e corretora internacional (sem feed de tempo real dedicado tipo
  last_indicadores_nac.py, que so existe pra Indice/Dolar na corretora nacional), le o M5
  direto do parquet MTF do proprio ativo (indicadores_mtf.py) em vez do
  JSON em tempo real; M1 fica null (so informativo mesmo, gatilho oficial
  sempre foi M5). _ler_peso()/_rodar_ciclo()/_flush() generalizados pra
  incluir qualquer alvo de ALVOS_EXTRA automaticamente na saida JSON
  (vies_direcional_a/b.json ganha uma chave "usatec" igual a "indice"/"dolar").

## 1.4.0 - 2026-09-25
- ALVOS_EXTRA deixa de ser dict hardcoded e passa a vir de config.json ->
  ativos_referencia_extra (mesmo pedido do usuario que motivou a mudanca
  equivalente no correl.py 1.5.0: "nao seria interessante criar um arquivo
  json que faz isso?"). Novo metodo _resolver_alvos_extra() le essa chave
  (self.coletor.config, ja carregado por _montar_universo) e deriva
  grupo_correlacao automaticamente como f"correlacao_{nome}" — nao precisa
  duplicar isso no JSON. self.alvos_extra substitui o ALVOS_EXTRA de
  modulo em toda parte (_ler_peso/calcular_vies/_rodar_ciclo/_flush).
  Comportamento identico ao 1.3.0 pro UsaTec.
