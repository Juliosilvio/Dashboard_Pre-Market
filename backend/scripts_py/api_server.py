"""
Nome do script : api_server.py
Descricao      : Servidor HTTP local (FastAPI) que expoe pra web (React, em
                  http://localhost:5173 por padrao) os dados que o backend ja
                  produz em disco. Motivo de existir: o navegador nao le
                  arquivo local nenhum (json/last_json/*.json,
                  json/config.json etc.) — precisa de HTTP. Este script nao
                  calcula nada novo, so LE o que last_nac.py/last_int.py/
                  vigente.py ja escrevem e devolve como JSON puro pra quem
                  pedir.

                  Double buffer na leitura: cada feed de preco em tempo real
                  (last_nac.py, last_int.py) grava em dois arquivos
                  alternados (_a/_b, ver historico desses scripts) pra nunca
                  colidir com um leitor no meio de uma escrita no Windows.
                  Este servidor le os dois nomes, compara o mtime (os.stat) e
                  devolve o conteudo do mais recente — exatamente o mesmo
                  contrato que qualquer leitor externo (JS puro, outro
                  Python) deveria seguir. Helper _ler_double_buffer() faz
                  isso uma vez e e usado por todo endpoint de preco.

                  Endpoints:
                    GET /api/last/nac    -> lista de precos correntes, corretora nacional
                    GET /api/last/int    -> lista de precos correntes, corretora internacional
                    GET /api/last        -> {"nac": [...], "int": [...]} (os dois)
                    GET /api/vigentes    -> config.json -> "vigentes" (dict
                                            raiz -> lista de tickers, vigente
                                            primeiro; escrito pelo
                                            vigente.py). {} se a chave ainda
                                            nao existir (main.py nao rodou
                                            vigente.py ainda nesta sessao).
                    GET /api/grades-cotacoes -> registro declarativo (novo
                                            em 1.21.0) de cada pagina/view
                                            do frontend: nome de exibicao,
                                            raiz de referencia (quando
                                            houver) e quais FEEDS compoem a
                                            grade de cotacoes daquela
                                            pagina - combina config.json ->
                                            ativos_referencia_extra (raiz,
                                            ja lida por correl.py/
                                            vies_direcional.py/dp.py, NAO
                                            mexida aqui) com config.json ->
                                            grades_cotacoes (nome/feeds,
                                            nova chave, so consumida por
                                            este endpoint). Ver App.jsx e
                                            nota de 1.21.0 abaixo.
                    GET /api/curvas/juros -> curva de juros (DI1), dado REAL:
                                            {"last_di1": [...], "session_close_di1":
                                            [...], "session_close_oc1": [...]},
                                            cada serie uma lista [{rotulo:
                                            "MM/AAAA", valor: float}, ...] na
                                            ordem cronologica dos vertices de
                                            vencimento. Le config.json ->
                                            "vigentes" -> "DI1"/"OC1" (lista
                                            de tickers B3, ex "DI1V26") pra
                                            saber QUAIS vertices existem,
                                            decodifica cada ticker de volta
                                            pro vertice (_decodificar_vertice_b3,
                                            caminho inverso do vigente.py) e
                                            busca o valor (last/session_close)
                                            no double buffer que last_nac.py
                                            ja escreve. OC1 so tem
                                            session_close (nunca last nem
                                            candle D1 — ver docstring do
                                            last_nac.py/vigente.py), por isso
                                            so entra a serie session_close_oc1
                                            e nao existe last_oc1. Ticker sem
                                            dado ainda (double buffer vazio
                                            pra ele) e so pulado — a serie
                                            fica esparsa, nunca quebra.
                    GET /api/curvas/frc -> curva FRC, dado REAL:
                                            {"last_frc": [...], "session_close_frc":
                                            [...]} — mesma logica do DI1
                                            (_serie_curva_br), so raiz unica
                                            (FRC nao tem uma raiz-irma so-com-
                                            session_close tipo o OC1 do DI1).
                    GET /api/curvas/cupom-inflacao -> curva de Cupom de
                                            Inflacao (raiz DAP), dado REAL:
                                            {"last_dap": [...], "session_close_dap":
                                            [...]}. RAIZ_POR_TIPO_CURVA mapeia
                                            tipo (contrato HTTP) -> raiz B3.
                    GET /api/curvas/trio -> aproximacao pratica do "Trio"
                                            B3/Anbima (DOL + DDI + DI1 no
                                            mesmo vencimento — normalmente
                                            usado por mesa de arbitragem pra
                                            flagrar desalinhamento de preco
                                            entre os tres). Este projeto ainda
                                            NAO coleta a curva de vencimentos
                                            do dolar futuro (DOLAR/DOL) — so o
                                            continuo (Dolar, ver ativos.
                                            nacionais) — entao a perna DOL
                                            fica de fora por enquanto. O que
                                            DA pra calcular hoje: DDI (cupom
                                            cambial REAL negociado, "sujo",
                                            so ~5 vertices liquidos — ver
                                            RAIZES_TESTE no vigente.py 2.2.0)
                                            contra FRC (cupom cambial TEORICO/
                                            "limpo", sintetizado pela propria
                                            B3 a partir de duas pernas de
                                            DDI). Devolve {"last_ddi": [...],
                                            "last_frc": [...], "spread_ddi_frc":
                                            [...]} — as 3 series RESTRITAS aos
                                            vertices onde o DDI tem preco de
                                            verdade (_serie_trio), pra
                                            comparar exatamente na mesma
                                            janela em vez de FRC entrando com
                                            os ~39 vertices dele (que
                                            dominaria a escala do grafico e
                                            escondaria a divergencia que
                                            interessa). spread_ddi_frc = DDI -
                                            FRC em cada vertice — quanto maior
                                            o modulo, maior o desalinhamento
                                            entre o cupom negociado e o
                                            teorico.
                    GET /api/dolar-teorico -> pedido do usuario: "quero
                                            colocar um card pequeno ja com o
                                            resultado" (depois de perguntar
                                            onde o DOLAR vigente "deveria"
                                            fechar). Calcula o dolar futuro
                                            TEORICO pela paridade coberta de
                                            juros — Teorico = Spot x
                                            (1+DI1)^(du/252) / (1+CupomFRC x
                                            dc/360), no vertice do DOLAR
                                            vigente (corretora nacional/B3, raiz "DOLAR" em
                                            ativos.curva_br desde 2026-09-17)
                                            — e compara com o preco REAL
                                            negociado desse mesmo DOLAR. Spot =
                                            USDBRL (double buffer do
                                            last_int.py, ativos.
                                            moedas_continuo — a B3 nao tem
                                            instrumento de spot). DI1, Cupom
                                            (FRC) e o proprio DOLAR vem de
                                            config.json->vigentes, mesmo
                                            double buffer do last_nac.py que
                                            /api/curvas/{tipo} ja le. DI1 e
                                            DOLAR vem da MESMA familia curva_br
                                            (resolver_raiz() no vigente.py) e
                                            caem SEMPRE no mesmo vertice/mes.
                                            O FRC NAO — o vigente de verdade
                                            dele e sempre 1 mes A FRENTE do
                                            DI1/DOLAR (pedido do usuario,
                                            2026-09-17: "o FRC ja rolou e usa
                                            x26" enquanto o dolar usa v26 —
                                            ver docstring de _dolar_teorico()
                                            e versoes/api_server.md 1.9.0
                                            pro motivo, FRC e uma taxa a
                                            termo/FRA sintetizada de duas
                                            pernas de DDI). du/dc = dias
                                            uteis/corridos ate o vencimento
                                            REAL do DOLAR (ultimo dia util do
                                            mes — _ultimo_dia_util/
                                            _dias_uteis_ate) — ate a 1.7.0 o
                                            card comparava com o Dolar da
                                            corretora internacional (vence no ULTIMO dia
                                            util) contra o vencimento do
                                            DI1/FRC (PRIMEIRO dia util),
                                            descasamento que fazia o card
                                            devolver erro nas ~3 semanas
                                            finais de todo mes (ver
                                            versoes/api_server.md 1.8.0).
                                            Ainda e uma APROXIMACAO sem
                                            calendario de feriados da B3 (so
                                            desconta fim de semana) — bom o
                                            suficiente pra uma leitura de
                                            fair value, nao pra liquidacao
                                            exata. Devolve {"vertice",
                                            "vertice_cupom", "ticker",
                                            "spot_usdbrl", "di1_pct",
                                            "cupom_frc_pct",
                                            "dias_uteis_di1",
                                            "dias_corridos_cupom",
                                            "dolar_teorico",
                                            "dolar_negociado",
                                            "diferenca_pct"} — ou {"erro":
                                            "..."} quando faltar algum dado
                                            real ainda (double buffer vazio
                                            pra algum dos quatro insumos, ou
                                            DOLAR sem vigente).
                    GET /api/curva-juros -> indice de juros de prazo
                                            constante (DI 1 ano / DI 2 anos,
                                            interpolado da curva inteira do
                                            DI1 - ver curva_juros.py) x Meta
                                            Selic, SERIE TEMPORAL (um ponto
                                            por dia, diferente de
                                            /api/curvas/{tipo} que e por
                                            vertice num dia so). Lista
                                            ordenada por data:
                                            [{"data": "AAAA-MM-DD",
                                            "di_1ano", "di_2anos",
                                            "selic_meta", "spread_1ano",
                                            "spread_2anos"}, ...] — campos
                                            None quando o prazo alvo nao
                                            tinha vertice suficiente pra
                                            interpolar naquele dia (ver
                                            docstring do curva_juros.py:
                                            "DI 1 ano" so fica valido a
                                            partir de 2025-10-14). [] se
                                            parquet/calculos/curva_juros
                                            .parquet ainda nao existir
                                            (curva_juros.py roda manual por
                                            enquanto, nao esta no pipeline
                                            automatico do main.py ainda).
                    GET /api/health      -> {"status": "ok"} simples, pra
                                            debug/checagem manual.
                    GET /api/layout      -> le o layout salvo. Aceita
                                            query opcional ?cliente=<id>
                                            (POR PESSOA desde 1.20.0, ver
                                            client.js 1.2.0) — com cliente
                                            valido, le json/layout_<id>.json;
                                            se esse arquivo ainda nao
                                            existir, cai pro json/layout.json
                                            "legado" so como ponto de
                                            partida (a proxima gravacao ja
                                            isola esse cliente). Sem
                                            ?cliente (chamada antiga/direta),
                                            comportamento igual a antes: le
                                            json/layout.json direto. Devolve
                                            {} se nao existir nada ainda.
                    POST /api/layout     -> grava o objeto de layout mandado
                                            pelo frontend (corpo = objeto
                                            completo, sem merge parcial —
                                            o frontend sempre manda o layout
                                            inteiro). Com ?cliente=<id>
                                            valido, escreve em
                                            json/layout_<id>.json; sem
                                            cliente, escreve em
                                            json/layout.json (comportamento
                                            de antes de 1.20.0). Nenhum
                                            outro script do pipeline
                                            le/escreve nesses arquivos,
                                            entao nao ha corrida com
                                            vigente.py/last_nac.py.
                    GET /api/config-visual -> mesma logica por-cliente do
                                            /api/layout acima, mas pra
                                            preferencias de ESTILO dos
                                            graficos (ex: "mostrarPontos" —
                                            diferente de /api/layout, que e
                                            posicao/tamanho dos paineis).
                                            Salvo automaticamente pelo
                                            frontend a cada toggle no
                                            cabecalho (ver useConfigVisual.js
                                            /App.jsx), sem precisar de botao
                                            "Salvar" separado. Devolve {} se
                                            ninguem mudou nada ainda.
                    POST /api/config-visual -> grava o objeto de config visual
                                            mandado pelo frontend (mesma
                                            convencao do POST /api/layout,
                                            inclusive o ?cliente=<id>):
                                            corpo = objeto completo, sem
                                            merge parcial, arquivo
                                            json/config_visual[_<id>].json,
                                            mesma logica atomica do layout.
                    GET /api/vies-direcional -> viés direcional (indice/dolar/e
                                            cada ativo de
                                            ativos_referencia_extra, ex.:
                                            usatec) calculado pelo
                                            vies_direcional.py — le o
                                            double buffer
                                            vies_direcional_a/b.json.
                                            {} enquanto o script nao
                                            tiver rodado.
                    GET /api/peso-mercado -> ranking de "peso" (correlacao
                                            real, sem filtro de limiar) de
                                            cada ativo do universo com Indice
                                            (indice) e Dolar (dolar), pra o
                                            frontend ordenar a tabela de
                                            cotacoes "conforme o peso de cada
                                            um no indice e no dolar" (pedido
                                            do usuario). Le
                                            parquet/calculos/pesoMercadoD1
                                            .parquet, escrito pelo correl.py
                                            (AnalisadorCorrelacao.calcular_peso(),
                                            ver correl.md 1.1.0) — UNICO
                                            endpoint deste servidor que lê
                                            parquet em vez de JSON (pandas
                                            importado so pra isso). Devolve
                                            um dict symbol -> {correlacao_indice,
                                            correlacao_dolar, peso}. {} se o
                                            arquivo ainda nao existir
                                            (main.py nao rodou correl.py
                                            ainda nesta instalacao) — o
                                            frontend cai pra ordem natural
                                            nesse caso.
                    GET /api/amplitude -> amplitude de mercado (advance/
                                            decline + novas maximas/minimas)
                                            por universo (config.json ->
                                            amplitude_universos) e timeframe
                                            (M15 a W1), calculado pelo
                                            amplitude.py — le o double
                                            buffer amplitude_amostra_a/
                                            b.json. {"consolidado": []}
                                            enquanto o script nao tiver
                                            rodado, ou pro universo que
                                            ainda nao tem raizes
                                            configuradas.
                    GET /api/last/magnificas -> cotacao + variacao
                                            intradiaria das 7 magnificas
                                            (Apple/Microsoft/Alphabet/
                                            Amazon/Nvidia/Meta/Tesla),
                                            mesmo formato de /api/last/int
                                            (lista de {"broker", "symbol",
                                            "time", "last",
                                            "session_close"}) - le o
                                            double buffer que
                                            magnificas.py grava
                                            continuamente (parquet de MTF
                                            do mt5stock, SEM conexao MT5
                                            nova). [] enquanto o script
                                            nao tiver rodado.
                    GET /api/last/sentimento-em -> cotacao + variacao
                                            intradiaria de EWZ/EEM
                                            (sentimento de risco
                                            Brasil/emergentes), mesmo
                                            formato de /api/last/int -
                                            le o double buffer que
                                            sentimento_em.py grava
                                            continuamente (parquet de MTF
                                            do mt5stock, SEM conexao MT5
                                            nova). [] enquanto o script
                                            nao tiver rodado.
                    GET /api/modelo-swing/universo -> lista das 129 raizes
                                            do universo (mesma lista de
                                            diag_sazonalidade_swings.py),
                                            pro seletor de ativo do
                                            ModeloSwingCard.jsx.
                    GET /api/modelo-swing/{raiz} -> cenario completo do
                                            ativo (cenario_final_swing.py,
                                            1.18.0): tudo que ja saia daqui
                                            (GARCH(1,1) pra faixa de
                                            oscilacao + vies MACD M15/IFR M5
                                            + horario mais provavel de
                                            topo/fundo) MAIS sinal
                                            topo/fundo/indefinido dos
                                            classificadores LightGBM
                                            (modelo_classificador_swing.py),
                                            direcao sugerida (compra/venda),
                                            confianca, alvo (ponta da faixa
                                            GARCH) e duas entradas (a
                                            mercado / zona de pullback).
                                            UNICO endpoint que CALCULA na
                                            hora em vez de so ler arquivo
                                            pronto (ver
                                            cenario_final_swing.py) - por
                                            isso so deve ser chamado quando
                                            o usuario troca o ativo, nunca
                                            em poll continuo. 404 se a raiz
                                            nao tiver candle M15 suficiente,
                                            500 se `arch` nao estiver
                                            instalada no venv ou se os
                                            modelos do classificador ainda
                                            nao tiverem sido treinados
                                            (rodar modelo_classificador_
                                            swing.py primeiro).

                  CORS liberado por regex pra localhost/127.0.0.1 e pra
                  qualquer IP 100.x.x.x (faixa do Tailscale, ver paragrafo
                  de compartilhamento abaixo), sempre na porta 5173 (porta
                  padrao do Vite em dev), metodos GET e POST (POST usado
                  por /api/layout e /api/config-visual) — sem isso o
                  navegador bloqueia a chamada por origem cruzada.

                  Compartilhamento via VPN (Tailscale, 2026-09-27 — pedido
                  do usuario, "quero compartilhar com um colega"):
                  servidor sobe em host="0.0.0.0" (todas as interfaces de
                  rede, nao so localhost) pra aceitar conexao vinda da
                  VPN. frontend/src/api/client.js (1.1.0) monta a URL da
                  API a partir do MESMO host que serviu a pagina
                  (window.location.hostname), entao funciona tanto local
                  (localhost) quanto pro colega (IP Tailscale do Julio).
                  frontend/vite.config.js ganhou host: true pelo mesmo
                  motivo. Firewall do Windows precisa liberar as portas
                  8000/5173 pra entrada.

                  Nao guarda estado nenhum em memoria entre requests: cada
                  chamada le o arquivo na hora (os arquivos sao pequenos,
                  poucos KB, entao o custo de disco e desprezivel comparado
                  ao ganho de simplicidade — sem cache pra invalidar, sem
                  risco de servir dado velho).

                  1.22.0 (2026-09-29) adiciona GET /api/last/sentimento-em -
                  mesmo padrao de GET /api/last/magnificas, so que pra
                  EWZ/EEM (sentimento_em.py, ver historico.py 1.4.0 e
                  ExportadorMt5Stock.mq5 1.01). Pedido do usuario:
                  "colocar o EWZ no Risk indice" (ampliado pra EEM). Pra
                  esses dois ativos entrarem na grade de cotacoes,
                  config.json -> grades_cotacoes.principal.feeds precisa
                  incluir "sentimento_em" (ver client.js/App.jsx).

                  Como rodar: python api_server.py (ou uvicorn api_server:app
                  --reload). Precisa de fastapi + uvicorn instalados
                  (pip install fastapi uvicorn) no mesmo venv do resto do
                  backend.
Autor          : Julio Cesar Silvio Campanhola
Criado em      : 2026-09-15
Ultima edicao  : 2026-10-01
Versao         : 1.27.0
Projeto        : dashboard
Historico      : scripts_py/versoes/api_server.md

                  1.17.0 (2026-09-27) adiciona GET /api/modelo-swing/universo
                  e GET /api/modelo-swing/{raiz} - primeiro par de endpoints
                  do projeto que CALCULA na hora (GARCH(1,1) via
                  modelo_garch_swing.py) em vez de so ler double buffer/
                  parquet ja pronto - ver docstring de modelo_garch_swing.py.

                  1.18.0 (2026-09-27) GET /api/modelo-swing/{raiz} passa a
                  chamar CenarioFinalSwing (cenario_final_swing.py) em vez
                  de ModeloGarchSwing diretamente - resposta agora inclui
                  sinal/direcao/confianca/alvo/entradas em cima dos campos
                  antigos (GARCH continua la dentro, e um superset) -
                  pedido do usuario: "com os numeros gerados por essa fase
                  do sistema precisamos de recomendacao de onde o preco
                  pode ir e qual e a entrada". GET /api/modelo-swing/universo
                  sem mudanca (continua orfao do frontend desde a correcao
                  de design do ModeloSwingCard.jsx v2.0.0).

                  1.19.0 (2026-09-27) host="0.0.0.0" (era "127.0.0.1") +
                  CORS por allow_origin_regex (era allow_origins fixo) pra
                  aceitar tambem IP 100.x.x.x (Tailscale) - pedido do
                  usuario: compartilhar o dashboard com um colega via VPN.
                  Ver client.js 1.1.0 e vite.config.js.

                  1.20.0 (2026-09-27) /api/layout e /api/config-visual
                  passam a aceitar query opcional ?cliente=<id> e gravar um
                  arquivo POR CLIENTE (json/layout_<id>.json /
                  json/config_visual_<id>.json) em vez de um unico arquivo
                  global - pedido do usuario logo depois de perceber a
                  implicacao do compartilhamento via VPN: "tinha que ser
                  por pessoa" (o colega salvando layout ia sobrescrever o
                  do Julio). Sem ?cliente (chamada antiga/direta), cai no
                  arquivo global de sempre - compatibilidade preservada.
                  Ver client.js 1.2.0 (quem gera e manda o id).

                  1.21.0 (2026-09-29) adiciona GET /api/grades-cotacoes -
                  pedido do usuario: um "controller" declarativo pra quais
                  feeds compoem a grade de cotacoes de cada pagina/view do
                  frontend, no config.json, ao inves de hardcoded no
                  App.jsx - mesmo padrao ja usado em
                  ativos_referencia_extra pro correl.py/
                  vies_direcional.py ("adicionar um ativo novo e so uma
                  linha no config, sem editar o script"). Nova chave
                  config.json -> grades_cotacoes ({"principal": {"nome":
                  ..., "feeds": [...]}, "usatec": {...}}) e SEPARADA de
                  ativos_referencia_extra de proposito - juntar as duas
                  quebraria correl.py/vies_direcional.py/dp.py, que exigem
                  "raiz"/"broker" em TODO item desse dict (ver dp.py: "se
                  TLT/IEF/SHY entrassem em ativos_referencia_extra,
                  apareceriam como views fantasmas no menu"). Este
                  endpoint so LE as duas chaves e devolve mesclado - nao
                  escreve nada, nao muda nenhum script existente nem
                  endpoint ja em uso. Ver App.jsx (mudanca correspondente)
                  e "Decimo passo" no arquitetura.md.
"""

import datetime
import importlib
import json
import os
import re

from fastapi import Body, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

try:
    pd = importlib.import_module("pandas")
except ImportError as exc:
    raise ImportError(
        "A dependencia pandas nao esta instalada. "
        "Instale-a com: pip install pandas pyarrow"
    ) from exc

from cenario_final_swing import CenarioFinalSwing
from diag_sazonalidade_swings import montar_universo

# instancia unica, reaproveitada entre requests (so guarda cache do json de
# diag_sazonalidade_swings.py, via ModeloGarchSwing.__init__, mais os dois
# modelos .joblib do classificador, carregados uma vez na primeira chamada -
# ver CenarioFinalSwing._carregar_modelos()) - a dependencia 'arch' so e
# importada de fato dentro de ModeloGarchSwing.analisar(), entao o servidor
# sobe normal mesmo antes do "pip install arch"; so a CHAMADA do endpoint
# falha ate instalar (ou ate rodar modelo_classificador_swing.py, se os
# .joblib ainda nao existirem).
_cenario_final_swing = CenarioFinalSwing()

# ---------------------------------------------------------------------------
# Caminhos — mesma convencao de last_nac.py/last_int.py: base_dir e a pasta
# "backend" (dois niveis acima deste arquivo, que mora em backend/scripts_py).
# ---------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JSON_DIR = os.path.join(BASE_DIR, "json")
LAST_JSON_DIR = os.path.join(JSON_DIR, "last_json")
CONFIG_PATH = os.path.join(JSON_DIR, "config.json")
LAYOUT_PATH = os.path.join(JSON_DIR, "layout.json")
CONFIG_VISUAL_PATH = os.path.join(JSON_DIR, "config_visual.json")

CAMINHOS_NAC = (
    os.path.join(LAST_JSON_DIR, "last_nac_a.json"),
    os.path.join(LAST_JSON_DIR, "last_nac_b.json"),
)
CAMINHOS_INT = (
    os.path.join(LAST_JSON_DIR, "last_int_a.json"),
    os.path.join(LAST_JSON_DIR, "last_int_b.json"),
)
# curva de juros dos treasurys americanos (yeldcurve.py, le o xlsx do Excel
# a cada 5min) - mesmo padrao double buffer dos dois acima.
CAMINHOS_YELDCURVE = (
    os.path.join(LAST_JSON_DIR, "yeldcurve_amostra_a.json"),
    os.path.join(LAST_JSON_DIR, "yeldcurve_amostra_b.json"),
)
# projecao de desvios de preco (dp.py) - MACD (perna/regressao) + ATR
# (candle) + IFR (certificacao 30-70), Indice/Dolar em MTF.
CAMINHOS_DP = (
    os.path.join(LAST_JSON_DIR, "dp_amostra_a.json"),
    os.path.join(LAST_JSON_DIR, "dp_amostra_b.json"),
)
# manchetes em tempo real do canal publico do Telegram fonte de noticias
# (noticias.py) - lista, mais recente primeiro.
CAMINHOS_NOTICIAS = (
    os.path.join(LAST_JSON_DIR, "noticias_amostra_a.json"),
    os.path.join(LAST_JSON_DIR, "noticias_amostra_b.json"),
)

# vies direcional (indice/dolar + ativos_referencia_extra), escrito pelo
# vies_direcional.py -> MotorViesDirecional (mesmo padrao double buffer).
CAMINHOS_VIES_DIRECIONAL = (
    os.path.join(LAST_JSON_DIR, "vies_direcional_a.json"),
    os.path.join(LAST_JSON_DIR, "vies_direcional_b.json"),
)

# amplitude de mercado (advance/decline + novas maximas/minimas), por
# universo (config.json -> amplitude_universos) e timeframe - escrito pelo
# amplitude.py -> ColetorAmplitude (mesmo padrao double buffer).
CAMINHOS_AMPLITUDE = (
    os.path.join(LAST_JSON_DIR, "amplitude_amostra_a.json"),
    os.path.join(LAST_JSON_DIR, "amplitude_amostra_b.json"),
)

# cotacao + variacao intradiaria das 7 magnificas (Apple/Microsoft/
# Alphabet/Amazon/Nvidia/Meta/Tesla) - escrito pelo magnificas.py ->
# ColetorMagnificas (mesmo padrao double buffer, mesmo shape de
# CAMINHOS_INT pra poder ser concatenado direto na mesma lista `cotacoes`
# do frontend).
CAMINHOS_MAGNIFICAS = (
    os.path.join(LAST_JSON_DIR, "magnificas_a.json"),
    os.path.join(LAST_JSON_DIR, "magnificas_b.json"),
)

# cotacao + variacao intradiaria de EWZ (iShares MSCI Brazil) e EEM
# (iShares MSCI Emerging Markets) - sentimento de risco Brasil/
# emergentes fora do horario da B3 - escrito pelo sentimento_em.py ->
# ColetorSentimentoEm (mesmo padrao double buffer de CAMINHOS_MAGNIFICAS).
CAMINHOS_SENTIMENTO_EM = (
    os.path.join(LAST_JSON_DIR, "sentimento_em_a.json"),
    os.path.join(LAST_JSON_DIR, "sentimento_em_b.json"),
)

# ranking de "peso" no indice/dolar (correlacao real com Indice/Dolar, sem
# filtro de limiar), escrito pelo correl.py -> AnalisadorCorrelacao
# .calcular_peso() — ver /api/peso-mercado abaixo. D1 (nao M5): "peso" e
# leitura ESTRUTURAL/macro de quem realmente move indice/dolar, faz mais
# sentido numa janela de ~1 mes (20 candles D1) do que na janela intradia
# curta do M5 (ruido de poucas horas).
PESO_MERCADO_PATH = os.path.join(BASE_DIR, "parquet", "calculos", "pesoMercadoD1.parquet")

# causalidade de Granger "so um sentido" de cada ativo contra Indice/Dolar
# (causalidade.py, roda manualmente/periodico por enquanto — ver docstring
# la) — mesclado no /api/peso-mercado por symbol, mesma chave de
# pesoMercadoD1.parquet (ver _ler_peso_mercado()).
CAUSALIDADE_PATH = os.path.join(BASE_DIR, "parquet", "calculos", "causalidadeD1.parquet")

# indice de juros de prazo constante (DI 1 ano/2 anos, interpolado da curva
# do DI1) comparado com a Meta Selic (dadosgov.py) - ver curva_juros.py.
# NAO esta no pipeline automatico do main.py ainda (roda manualmente por
# enquanto), entao pode nao existir - ver _ler_curva_juros().
CURVA_JUROS_PATH = os.path.join(BASE_DIR, "parquet", "calculos", "curva_juros.parquet")

# historico M1 do USDBRL (fuso_horario.py ja corrige o horario na coleta —
# mesmo dado que correl.py/vigente.py ja confiam em outros pontos do
# projeto) — usado so pelo proxy de PTAX em _ptax_proxy_usdbrl() abaixo.
HISTORICO_USDBRL_M1_PATH = os.path.join(BASE_DIR, "parquet", "historicos", "MTF", "USDBRL", "m1.parquet")

# janelas oficiais de apuracao da PTAX do Bacen, horario de Brasilia (4
# consultas por dia — confirmado via busca 2026-09-30, nao so memoria).
# Brasilia e UTC-3 o ano inteiro desde que o pais aboliu horario de verao
# em 2019 — deslocamento fixo; se o Brasil um dia voltar a ter horario de
# verao, isso precisa virar dinamico por data.
JANELAS_PTAX_BRT = (("10:00", "10:10"), ("11:00", "11:10"), ("12:00", "12:10"), ("13:00", "13:10"))
# FUSO_BRASILIA_PARA_UTC removida 2026-10-01 -- premissa errada de que o
# m1.parquet estaria em UTC verdadeiro (ver nota do bug corrigido na
# docstring de _janela_ptax_utc() abaixo).

TIPOS_CURVA_VALIDOS = {"juros", "frc", "cupom-inflacao", "trio"}

# tipo de curva (contrato HTTP do frontend) -> raiz B3 correspondente em
# config.json -> vigentes (resolvida pelo vigente.py — ver RAIZES_TESTE la).
# "juros" nao entra aqui porque combina DUAS raizes (DI1 + OC1), tratado a
# parte no endpoint /api/curvas/{tipo}.
RAIZ_POR_TIPO_CURVA = {"frc": "FRC", "cupom-inflacao": "DAP"}

# mesma convencao do vigente.py (B3: raiz + letra do mes + 2 digitos do ano,
# ex "DI1V26") — aqui e o caminho INVERSO: decodificar o ticker de volta pro
# vertice de vencimento (mes/ano), pra virar rotulo de eixo X no frontend.
LETRA_MES = {1: "F", 2: "G", 3: "H", 4: "J", 5: "K", 6: "M",
             7: "N", 8: "Q", 9: "U", 10: "V", 11: "X", 12: "Z"}
MES_POR_LETRA = {letra: mes for mes, letra in LETRA_MES.items()}

def _ler_double_buffer(caminho_a: str, caminho_b: str) -> list:
    """Le o par de arquivos double buffer e devolve o conteudo do mais
    recente (maior mtime). Se so um dos dois existir, le esse. Se nenhum
    existir ainda (coletor nao rodou nesta maquina/sessao), devolve lista
    vazia em vez de quebrar — o frontend trata lista vazia normalmente."""
    candidatos = []
    for caminho in (caminho_a, caminho_b):
        if os.path.exists(caminho):
            candidatos.append((os.path.getmtime(caminho), caminho))

    if not candidatos:
        return []

    candidatos.sort(key=lambda par: par[0], reverse=True)
    caminho_mais_recente = candidatos[0][1]

    try:
        with open(caminho_mais_recente, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        # Corrida rara: arquivo pego no meio de um os.replace() (nao deveria
        # acontecer por causa do double buffer, mas nao custa nao derrubar o
        # servidor por isso). Tenta o outro arquivo do par antes de desistir.
        if len(candidatos) > 1:
            try:
                with open(candidatos[1][1], "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                pass
        return []


def _ler_config() -> dict:
    """Le config.json inteiro. Devolve {} se o arquivo nao existir ainda."""
    if not os.path.exists(CONFIG_PATH):
        return {}
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


# ?cliente=<id> (1.20.0, ver docstring do modulo) - id gerado pelo
# client.js (1.2.0) e guardado no localStorage de CADA navegador; serve so
# pra layout/config-visual nao serem mais compartilhados entre quem abre
# o dashboard (pedido do usuario: "tinha que ser por pessoa"). Regex evita
# path traversal (o id vira nome de arquivo direto).
_CLIENTE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def _caminho_layout(cliente: str | None) -> str:
    if cliente and _CLIENTE_ID_RE.match(cliente):
        return os.path.join(JSON_DIR, f"layout_{cliente}.json")
    return LAYOUT_PATH


def _caminho_config_visual(cliente: str | None) -> str:
    if cliente and _CLIENTE_ID_RE.match(cliente):
        return os.path.join(JSON_DIR, f"config_visual_{cliente}.json")
    return CONFIG_VISUAL_PATH


def _ler_layout(cliente: str | None = None) -> dict:
    """Le o layout salvo (tamanho de cada painel + divisao da coluna
    FRC/Cupom, salvos pelo botao 'Salvar layout' do frontend). Desde 1.20.0
    e POR CLIENTE (ver _caminho_layout) — se o arquivo proprio do cliente
    ainda nao existir, cai pro json/layout.json 'legado' so como ponto de
    partida (a proxima gravacao ja isola esse cliente sozinho); sem cliente
    valido, le json/layout.json direto (comportamento de antes de 1.20.0).
    Arquivos PROPRIOS deste endpoint, separados de config.json — nenhum
    outro script do pipeline (vigente.py, last_nac.py...) le ou escreve
    neles, entao nao ha risco de corrida. Devolve {} se nada existir ainda.
    """
    caminho = _caminho_layout(cliente)
    if not os.path.exists(caminho):
        caminho = LAYOUT_PATH
        if not os.path.exists(caminho):
            return {}
    try:
        with open(caminho, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _salvar_layout(layout: dict, cliente: str | None = None) -> None:
    """Grava o layout inteiro — o frontend sempre manda o objeto completo
    (sem merge parcial), mais simples e sem risco de misturar layout velho
    com novo. Desde 1.20.0, escreve no arquivo PROPRIO do cliente (ou no
    json/layout.json global, sem cliente valido — ver _caminho_layout).
    Escreve em arquivo temporario e da os.replace no final (atomico,
    funciona no Windows tambem) pelo mesmo motivo do double buffer de
    last_nac.py/last_int.py: nunca deixar um leitor pegar o arquivo pela
    metade."""
    os.makedirs(JSON_DIR, exist_ok=True)
    caminho = _caminho_layout(cliente)
    tmp_path = caminho + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(layout, f, ensure_ascii=False, indent=2)
    os.replace(tmp_path, caminho)


def _ler_config_visual(cliente: str | None = None) -> dict:
    """Le as preferencias de ESTILO dos graficos (ex: 'mostrarPontos' — ver
    useConfigVisual.js no frontend). Mesma logica por-cliente de
    _ler_layout() (ver docstring la) desde 1.20.0 — arquivo PROPRIO,
    separado tanto de config.json (dado de mercado, escrito pelo pipeline)
    quanto do layout (posicao/tamanho dos paineis). Devolve {} se nada
    existir ainda."""
    caminho = _caminho_config_visual(cliente)
    if not os.path.exists(caminho):
        caminho = CONFIG_VISUAL_PATH
        if not os.path.exists(caminho):
            return {}
    try:
        with open(caminho, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _salvar_config_visual(config: dict, cliente: str | None = None) -> None:
    """Grava a config visual inteira — mesma convencao do _salvar_layout()
    (inclusive por-cliente desde 1.20.0, ver _caminho_config_visual):
    o frontend manda o objeto completo (sem merge parcial), escrita
    atomica via arquivo temporario + os.replace (funciona no Windows
    tambem)."""
    os.makedirs(JSON_DIR, exist_ok=True)
    caminho = _caminho_config_visual(cliente)
    tmp_path = caminho + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
    os.replace(tmp_path, caminho)


def _ler_peso_mercado() -> dict:
    """Le parquet/calculos/pesoMercadoD1.parquet (ranking de "peso" de cada
    ativo do universo na correlacao com Indice/Dolar — TODO ativo entra, sem
    filtro de limiar, ver correl.py -> calcular_peso()). Usado pelo frontend
    pra ordenar a tabela de cotacoes pelo peso real no indice/dolar (pedido
    do usuario: "organizar os tickers conforme o peso de cada um no indice e
    no dolar"). Devolve {} se o arquivo ainda nao existir (main.py nao rodou
    correl.py ainda nesta instalacao) — o frontend cai pra ordem natural
    nesse caso. Chave do dict e so o symbol (ignora broker — corretora nacional e
    corretora internacional nao tem symbol repetido entre si neste projeto).

    2026-09-30: mescla tambem causa_indice/causa_dolar (+ p-valor/lag) de
    causalidadeD1.parquet quando existir (ver causalidade.py) — pedido do
    usuario depois de revisar o prototipo de causalidade de Granger:
    "adicione nas tabelas de risk mesmo ja existentes". So entra no
    registro quando True (economiza campo, frontend so precisa checar
    presenca) — ativo sem causalidade "so um sentido" significativa
    simplesmente nao ganha essas chaves."""
    if not os.path.exists(PESO_MERCADO_PATH):
        return {}
    try:
        df = pd.read_parquet(PESO_MERCADO_PATH)
    except (OSError, ValueError):
        return {}

    # pedido do usuario 2026-09-25 (comecando por UsaTec/Nasdaq): as colunas
    # correlacao_<nome> de config.json -> ativos_referencia_extra tambem
    # precisam chegar no frontend, pro QuotesTable conseguir montar a grade
    # de cotacao de qualquer ativo operavel novo — generico, entao um ativo
    # extra novo no config.json ja aparece aqui sem editar este arquivo.
    extras_config = _ler_config().get("ativos_referencia_extra", {})
    colunas_extra = [f"correlacao_{nome}" for nome in extras_config if f"correlacao_{nome}" in df.columns]

    # causalidade.py e OPCIONAL (arquivo pode nao existir ainda, ou o
    # usuario pode nunca ter rodado) — {} nesse caso, sem quebrar o resto
    # do endpoint (mesma resiliencia de PESO_MERCADO_PATH acima).
    causalidade_por_symbol = {}
    if os.path.exists(CAUSALIDADE_PATH):
        try:
            df_causa = pd.read_parquet(CAUSALIDADE_PATH)
            for _, linha_c in df_causa.iterrows():
                campos = {}
                for chave in ("causa_indice", "causa_dolar"):
                    if chave in linha_c and bool(linha_c[chave]):
                        campos[chave] = True
                        campos[f"{chave}_p"] = None if pd.isna(linha_c.get(f"{chave}_p")) else float(linha_c[f"{chave}_p"])
                        campos[f"{chave}_lag"] = None if pd.isna(linha_c.get(f"{chave}_lag")) else int(linha_c[f"{chave}_lag"])
                if campos:
                    causalidade_por_symbol[linha_c["symbol"]] = campos
        except (OSError, ValueError):
            pass

    resultado = {}
    for _, linha in df.iterrows():
        registro = {
            "correlacao_indice": None if pd.isna(linha["correlacao_indice"]) else float(linha["correlacao_indice"]),
            "correlacao_dolar": None if pd.isna(linha["correlacao_dolar"]) else float(linha["correlacao_dolar"]),
            "peso": None if pd.isna(linha["peso"]) else float(linha["peso"]),
        }
        for coluna in colunas_extra:
            registro[coluna] = None if pd.isna(linha[coluna]) else float(linha[coluna])
        registro.update(causalidade_por_symbol.get(linha["symbol"], {}))
        resultado[linha["symbol"]] = registro
    return resultado


def _ler_curva_juros() -> list:
    """Le parquet/calculos/curva_juros.parquet (indice de juros de prazo
    constante DI 1 ano / DI 2 anos, interpolado da curva inteira do DI1 em
    dias uteis, comparado com a Meta Selic via merge_asof - ver
    curva_juros.py). Devolve uma lista de registros ordenada por data,
    formato serie temporal (diferente de /api/curvas/{tipo}, que e por
    VERTICE de vencimento num dia so) - pro frontend desenhar a evolucao no
    tempo (SelicJurosChart.jsx). [] se o arquivo ainda nao existir
    (curva_juros.py precisa ter rodado manualmente pelo menos uma vez -
    ainda nao esta no pipeline automatico do main.py)."""
    if not os.path.exists(CURVA_JUROS_PATH):
        return []
    try:
        df = pd.read_parquet(CURVA_JUROS_PATH).sort_values("data")
    except (OSError, ValueError):
        return []

    registros = []
    for _, linha in df.iterrows():
        registros.append({
            "data": linha["data"].strftime("%Y-%m-%d") if pd.notna(linha["data"]) else None,
            "di_1ano": None if pd.isna(linha.get("di_1ano")) else float(linha["di_1ano"]),
            "di_2anos": None if pd.isna(linha.get("di_2anos")) else float(linha["di_2anos"]),
            "selic_meta": None if pd.isna(linha.get("selic_meta")) else float(linha["selic_meta"]),
            "spread_1ano": None if pd.isna(linha.get("spread_1ano")) else float(linha["spread_1ano"]),
            "spread_2anos": None if pd.isna(linha.get("spread_2anos")) else float(linha["spread_2anos"]),
        })
    return registros


def _decodificar_vertice_b3(ticker: str, raiz: str):
    """'DI1V26' + raiz 'DI1' -> (2026, 10, '10/2026') — decodifica um ticker
    B3 (raiz + letra do mes + 2 digitos do ano) no vertice de vencimento.
    Caminho inverso do vigente.py (_ticker_b3), que CONSTROI o ticker com a
    mesma tabela LETRA_MES. Devolve None se o ticker nao seguir o padrao
    esperado — defensivo, nao deveria acontecer com ticker vindo de
    config.json->vigentes (so tem o que o proprio vigente.py gerou)."""
    if not ticker.startswith(raiz) or len(ticker) < len(raiz) + 3:
        return None
    sufixo = ticker[len(raiz):]
    letra, digitos_ano = sufixo[0], sufixo[1:]
    mes = MES_POR_LETRA.get(letra)
    if mes is None or not digitos_ano.isdigit():
        return None
    ano = 2000 + int(digitos_ano)
    return ano, mes, f"{mes:02d}/{ano}"


def _serie_curva_br(raiz: str, campo: str, registros_por_symbol: dict) -> list:
    """Monta uma serie [{rotulo, valor}] pra uma raiz de curva_br (DI1, OC1,
    DAP, FRC), na ordem cronologica dos vertices de vencimento. 'campo' e
    'last' ou 'session_close' — lido do double buffer que last_nac.py ja
    escreve (registros_por_symbol: symbol -> registro). Ticker sem esse
    campo (None) ou sem entrada no double buffer ainda e simplesmente
    pulado — a curva fica esparsa onde faltar dado, igual o vigente.py ja
    documenta ("um mes sem contrato e so um buraco no meio da curva")."""
    config = _ler_config()
    tickers = config.get("vigentes", {}).get(raiz, [])

    pontos = []
    for ticker in tickers:
        vertice = _decodificar_vertice_b3(ticker, raiz)
        if vertice is None:
            continue
        ano, mes, rotulo = vertice

        registro = registros_por_symbol.get(ticker)
        if registro is None:
            continue
        valor = registro.get(campo)
        if valor is None:
            continue

        pontos.append((ano, mes, rotulo, valor))

    pontos.sort(key=lambda p: (p[0], p[1]))
    return [{"rotulo": rotulo, "valor": valor} for _, _, rotulo, valor in pontos]


def _serie_trio(registros_por_symbol: dict) -> dict:
    """Aproximacao pratica do "Trio" B3/Anbima (DOL + DDI + DI1) sem a perna
    DOL — ver docstring do modulo, secao /api/curvas/trio, pro motivo (o
    projeto ainda nao coleta a curva de vencimentos do dolar futuro). Compara
    DDI (cupom REAL negociado) com FRC (cupom TEORICO/"limpo") exatamente nos
    MESMOS vertices — pega a serie do DDI (ja curta, so ~5 vertices liquidos)
    e so aceita o FRC de cada vertice que o DDI tambem tem, descartando o
    resto da curva do FRC (~39 vertices) que so dominaria a escala do
    grafico sem ajudar a comparacao. spread = DDI - FRC no mesmo vertice."""
    serie_ddi = _serie_curva_br("DDI", "last", registros_por_symbol)
    frc_por_rotulo = {p["rotulo"]: p["valor"] for p in _serie_curva_br("FRC", "last", registros_por_symbol)}

    last_ddi, last_frc, spread = [], [], []
    for ponto in serie_ddi:
        valor_frc = frc_por_rotulo.get(ponto["rotulo"])
        if valor_frc is None:
            continue  # vertice do DDI sem par no FRC ainda (double buffer nao chegou la) — so pula
        last_ddi.append(ponto)
        last_frc.append({"rotulo": ponto["rotulo"], "valor": valor_frc})
        spread.append({"rotulo": ponto["rotulo"], "valor": ponto["valor"] - valor_frc})

    return {"last_ddi": last_ddi, "last_frc": last_frc, "spread_ddi_frc": spread}


def _pascoa(ano: int) -> datetime.date:
    """Domingo de Pascoa pro ano informado, algoritmo de Meeus/Jones/Butcher
    (calendario Gregoriano) — validado em 2026-09-30 contra o calendario
    oficial 2026 da B3 (b3.com.br/pt_br/noticias/calendario-de-negociacao-
    da-b3-confira-o-funcionamento-da-bolsa-em-2026.htm): Pascoa 2026 =
    05/04, Carnaval 16-17/02, Sexta Santa 03/04, Corpus Christi 04/06 —
    todos batem. Usada em _feriados_b3() pra derivar os feriados moveis
    sem precisar baixar/atualizar calendario nenhum ano a ano."""
    a = ano % 19
    b = ano // 100
    c = ano % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    mes = (h + l - 7 * m + 114) // 31
    dia = ((h + l - 7 * m + 114) % 31) + 1
    return datetime.date(ano, mes, dia)


def _feriados_b3(ano: int) -> set:
    """Calendario de feriados da B3 (fechamento TOTAL do pregao) pro ano
    informado — combina datas fixas confirmadas no calendario oficial 2026
    da B3 com feriados moveis derivados de _pascoa() (Carnaval = Pascoa-48
    e Pascoa-47, Sexta-feira Santa = Pascoa-2, Corpus Christi = Pascoa+60).
    Confirmado em 2026-09-30 via b3.com.br: NAO inclui 09/07 (Revolucao
    Constitucionalista — feriado estadual de SP, B3 opera normal) nem
    18/02 (Quarta-feira de Cinzas — expediente reduzido, NAO e fechamento).
    31/12 entra como convencao especifica da B3 (vespera de Ano Novo),
    mesmo nao sendo feriado nacional. Auto-suficiente: nao precisa de
    atualizacao manual ano a ano, so recalcula a Pascoa."""
    pascoa = _pascoa(ano)
    return {
        datetime.date(ano, 1, 1),                              # Confraternizacao Universal
        pascoa - datetime.timedelta(days=48),                  # Carnaval (segunda)
        pascoa - datetime.timedelta(days=47),                  # Carnaval (terca)
        pascoa - datetime.timedelta(days=2),                   # Sexta-feira Santa
        datetime.date(ano, 4, 21),                              # Tiradentes
        datetime.date(ano, 5, 1),                               # Dia do Trabalho
        pascoa + datetime.timedelta(days=60),                   # Corpus Christi
        datetime.date(ano, 9, 7),                               # Independencia
        datetime.date(ano, 10, 12),                             # Nossa Senhora Aparecida
        datetime.date(ano, 11, 2),                              # Finados
        datetime.date(ano, 11, 20),                             # Consciencia Negra (nacional desde 2024)
        datetime.date(ano, 12, 25),                             # Natal
        datetime.date(ano, 12, 31),                             # Vespera de Ano Novo (convencao B3)
    }


def _e_dia_util_b3(d: datetime.date) -> bool:
    """Um dia e util pra B3 quando nao cai em fim de semana E nao esta no
    calendario de feriados de _feriados_b3() pro ano de d — helper comum
    usado tanto por _ultimo_dia_util() quanto por _dias_uteis_ate()."""
    return d.weekday() < 5 and d not in _feriados_b3(d.year)


def _ultimo_dia_util(ano: int, mes: int) -> datetime.date:
    """Aproximacao do vencimento REAL do DOLAR/DOL (ultimo dia util do mes) —
    desde 2026-09-30 desconta fim de semana E feriados da B3 (via
    _feriados_b3(), calendario oficial + algoritmo de Pascoa pros moveis,
    ver docstring la). Antes so descontava fim de semana, o que podia
    atrasar o vencimento calculado em 1-3 dias uteis perto de feriado.
    Usada como alvo do desconto (du/dc) em _dolar_teorico() desde que o
    card passou a comparar com o DOLAR real (corretora nacional/B3) em vez do Dolar
    (corretora internacional) — diferente do DI1/FRC/DDI/DAP, que vencem no PRIMEIRO
    dia util do mes."""
    if mes == 12:
        ano_seguinte, mes_seguinte = ano + 1, 1
    else:
        ano_seguinte, mes_seguinte = ano, mes + 1
    d = datetime.date(ano_seguinte, mes_seguinte, 1) - datetime.timedelta(days=1)
    while not _e_dia_util_b3(d):
        d -= datetime.timedelta(days=1)
    return d


def _mes_seguinte(ano: int, mes: int):
    """Mes seguinte ao informado, virando o ano em dezembro->janeiro — mesma
    logica do vigente.py (_mes_seguinte la). Usado em _dolar_teorico() pra
    achar o vertice do FRC (sempre 1 mes A FRENTE do vertice do DOLAR/DI1, ver
    docstring de _dolar_teorico)."""
    if mes == 12:
        return ano + 1, 1
    return ano, mes + 1


def _dias_uteis_ate(data_alvo: datetime.date) -> int:
    """Conta dias uteis (seg-sex, sem feriado da B3 — via _e_dia_util_b3(),
    desde 2026-09-30; antes so descontava fim de semana) entre hoje e
    data_alvo — usa a data LOCAL da maquina (mesma convencao do
    vigente.py, ver _mes_vigente la: "o calculo do agora tinha ido pra UTC
    por engano")."""
    hoje = datetime.date.today()
    if data_alvo <= hoje:
        return 0
    dias = 0
    d = hoje
    while d < data_alvo:
        d += datetime.timedelta(days=1)
        if _e_dia_util_b3(d):
            dias += 1
    return dias


def _janela_ptax_utc(hhmm_ini: str, hhmm_fim: str, data_ref) -> tuple:
    """Converte uma janela em horario de Brasilia (string 'HH:MM') pro par
    (inicio, fim) tz-aware, no dia data_ref, NO MESMO "fuso" que a coluna
    time dos parquets MTF usa de verdade.

    BUG CORRIGIDO 2026-10-01 (achado investigando por que o Dolar Teorico
    nunca saia do modo estimado mesmo horas depois das janelas de PTAX
    terem fechado de verdade): esta funcao somava FUSO_BRASILIA_PARA_UTC
    (+3h) antes de comparar com df["time"], a partir da premissa (escrita
    no docstring antigo de _ptax_proxy_usdbrl) de que o m1.parquet estaria
    em UTC verdadeiro. Essa premissa esta ERRADA — ver fuso_horario.py: a
    correcao DST-aware aplicada na ingestao dos dados da corretora internacional existe
    EXATAMENTE pra fazer o horario dela bater com o horario direto de
    Brasilia (mesma convencao que a corretora nacional ja usa nativamente, sem
    correcao nenhuma) — "abertura do pregao do Indice (corrigido) bate
    09:00 UTC (= Indice)" no docstring de fuso_horario.py quer dizer que
    BATE COM O HORARIO DIRETO DE BRASILIA que a coluna time do Indice usa,
    nao com UTC de verdade. Confirmado empiricamente nesta correcao:
    comparando o ultimo candle real de USDBRL/GOLD (corretora internacional) e Indice
    (corretora nacional) contra o relogio de agora, os tres batem direto com o horario
    de Brasilia (~15-20min de defasagem normal do loop), SEM precisar de
    +3h nenhum. Com o +3h antigo, a janela "10:00-10:10 BRT" acabava
    buscando candle rotulado "13:00-13:10" no parquet — que e Brasilia
    13h-13h10 de VERDADE, ainda no futuro a maior parte da manha — por
    isso a janela aparecia sempre com completa=True (pois datetime.now
    verdadeiro ja tinha passado de 13:10 em UTC) mas preco=None (porque
    esse horario futuro nunca tem candle ainda): o PTAX parecia "fechado"
    mas sem dado, nunca virava real. Agora usa o horario BRT direto, sem
    soma nenhuma — simetrico ao que Indice/Dolar e todo o resto do projeto
    ja faz."""
    def _converter(hhmm):
        h, m = (int(x) for x in hhmm.split(":"))
        local = datetime.datetime.combine(data_ref, datetime.time(h, m))
        return local.replace(tzinfo=datetime.timezone.utc)
    return _converter(hhmm_ini), _converter(hhmm_fim)


def _ptax_proxy_usdbrl(data_ref=None) -> dict:
    """Aproximacao da PTAX do Bacen pro USDBRL, pra usar como "spot" da
    paridade coberta de juros em _dolar_teorico() — pedido do usuario
    (2026-09-30): "o DOLAR/DOL liquida contra PTAX, o DI1/FRC ja sao
    precificados com essa convencao implicita — misturar um tick
    instantaneo do USDBRL com curvas PTAX-referenciadas introduz ruido/
    descasamento na formula". Metodologia oficial do Bacen (confirmada via
    busca, nao so memoria): 4 consultas por dia, 10h-10h10 / 11h-11h10 /
    12h-12h10 / 13h-13h10 (horario de Brasilia, ver JANELAS_PTAX_BRT), cada
    uma com ~20 dealers credenciados (descarta as 2 maiores e as 2 menores
    cotacoes, tira a media do resto); a PTAX do dia e a media aritmetica
    simples das 4 consultas.

    O projeto nao tem acesso a cotacoes de dealers (so o feed USDBRL de UMA
    corretora via MT5) — aproxima cada janela com OHLC4 (Abertura+Maxima+
    Minima+Fechamento)/4 dos candles M1 daquela janela, em vez de tentar
    imitar uma cotacao pontual no fim da janela: OHLC4 da peso igual aos 4
    pontos, captura a variacao dentro da janela (o quanto foi na maxima/
    minima) sem deixar 1 tick isolado dominar sozinho.

    PARCIAL/progressivo (pedido do usuario — "faz pra vermos"): usa a media
    so das janelas que ja FECHARAM (agora >= fim da janela) E que tiveram
    pelo menos 1 candle M1 de verdade — mesmo espirito do "buraco no meio
    da curva nao derruba tudo" ja usado em correl.py/vigente.py. Antes das
    10h10 BRT (nenhuma janela fechada ainda), ou se nenhuma janela fechada
    teve dado real, devolve valor=None — quem chama decide o que fazer (ver
    _dolar_teorico()).

    Trabalha inteiramente em UTC (mesmo fuso do m1.parquet) — sem precisar
    decidir "qual e o dia de hoje em horario local", porque as 4 janelas
    (13h-16h10 UTC) nunca cruzam a virada de dia UTC (que acontece as
    21h BRT, bem depois da ultima janela)."""
    if not os.path.exists(HISTORICO_USDBRL_M1_PATH):
        return {"valor": None, "janelas": [], "erro": "historico M1 do USDBRL ainda nao existe"}

    try:
        df = pd.read_parquet(HISTORICO_USDBRL_M1_PATH, columns=["time", "open", "high", "low", "close"])
    except (OSError, ValueError):
        return {"valor": None, "janelas": [], "erro": "nao deu pra ler o historico M1 do USDBRL"}

    agora_real = datetime.datetime.now(datetime.timezone.utc)
    # "agora" no MESMO fuso direto de Brasilia que df["time"] usa e que
    # _janela_ptax_utc() agora devolve (fix 2026-10-01, ver docstring
    # dela) -- sem este ajuste, completa comparava um agora em UTC
    # verdadeiro (~3h "na frente") contra limites de janela em horario de
    # Brasilia, fazendo toda janela aparecer "completa" cedo demais,
    # mesmo as que ainda nem comecaram de verdade.
    agora = (agora_real - datetime.timedelta(hours=3)).replace(tzinfo=datetime.timezone.utc)
    hoje = data_ref or agora.date()

    janelas = []
    for ini_s, fim_s in JANELAS_PTAX_BRT:
        ini, fim = _janela_ptax_utc(ini_s, fim_s, hoje)
        completa = agora >= fim
        bloco = df[(df["time"] >= ini) & (df["time"] < fim)]
        if bloco.empty:
            janelas.append({"janela": f"{ini_s}-{fim_s} BRT", "completa": completa, "n_candles": 0, "preco": None})
            continue
        o = float(bloco["open"].iloc[0])
        h = float(bloco["high"].max())
        l = float(bloco["low"].min())
        c = float(bloco["close"].iloc[-1])
        janelas.append({
            "janela": f"{ini_s}-{fim_s} BRT",
            "completa": completa,
            "n_candles": int(len(bloco)),
            "preco": round((o + h + l + c) / 4, 5),
        })

    usaveis = [j["preco"] for j in janelas if j["completa"] and j["preco"] is not None]
    valor = round(sum(usaveis) / len(usaveis), 5) if usaveis else None

    return {"valor": valor, "janelas_completas": len(usaveis), "janelas": janelas}


def _variacao_d1_dxy() -> float | None:
    """Variacao D1 (intraday, desde o fechamento de ontem) do indice DXY
    futuro (raiz "USDInd" em ativos.vencimento_americano, corretora internacional) --
    usada em _ptax_proxy_usdbrl_com_fallback() pra "rolar" o ultimo PTAX
    real conhecido ate agora, antes da 1a janela de PTAX de hoje fechar.
    Pedido do usuario (2026-10-01), depois de descobrir que o card Dolar
    Teorico fica sem dado ate as ~10h10 BRT (ver _ptax_proxy_usdbrl()):
    "mostre o anterior ate as 10:10 quando o novo ira surgir e o anterior
    deve vir multiplicado pela variacao D1 do dxy, tipo Anterior*(1+vardxy)".

    last/session_close vem do MESMO double buffer internacional
    (last_int.py, CAMINHOS_INT) que todo o resto do projeto ja usa pra
    variacao D1 (ver QuotesTable.jsx) -- session_close e o fechamento do
    pregao anterior, gravado pela propria corretora (MT5), nao calculado
    aqui. Devolve None se o USDInd ainda nao tem vigente resolvido ou se
    o double buffer ainda nao tem o symbol (double buffer vazio/corrompido
    nao e erro fatal pro card -- quem chama decide o que fazer)."""
    config = _ler_config()
    ticker_usdind = (config.get("vigentes", {}).get("USDInd") or [None])[0]
    if ticker_usdind is None:
        return None

    registros_int = {r["symbol"]: r for r in _ler_double_buffer(*CAMINHOS_INT)}
    reg = registros_int.get(ticker_usdind)
    if not reg:
        return None

    last = reg.get("last")
    fechamento = reg.get("session_close")
    if last is None or not fechamento:
        return None

    return (last / fechamento) - 1


def _ptax_proxy_usdbrl_com_fallback() -> dict:
    """Wrapper de _ptax_proxy_usdbrl() que EXTRAPOLA o spot quando hoje
    ainda nao tem nenhuma janela de PTAX fechada (tipico antes das ~10h10
    BRT, ou em dia sem pregao ainda) -- em vez de devolver valor=None e o
    card virar "sem dados" por ~1h toda manha. Pedido do usuario
    (2026-10-01) -- ver _variacao_d1_dxy() pro contexto completo.

    Metodologia: pega o PTAX real do ultimo dia ANTERIOR com dado no
    historico M1 (normalmente ontem, com as 4 janelas fechadas) chamando
    _ptax_proxy_usdbrl(data_ref=<esse dia>) -- reaproveita a MESMA funcao,
    so muda o dia de referencia -- e multiplica pela variacao D1 do DXY
    (USDInd vigente) desde o fechamento de ontem: anterior * (1 +
    variacao_dxy). DXY sobe = dolar forte no mundo todo = USDBRL tende a
    subir tambem, entao serve de proxy rapido pro quanto o USDBRL real
    deve ter andado desde o ultimo PTAX fechado, sem precisar esperar a
    B3 abrir.

    SEMPRE marca "estimado": True nesse caminho -- NUNCA deve ser
    confundido com PTAX real (ver DolarTeoricoCard.jsx, que precisa
    avisar visualmente que o numero e estimado). Se qualquer peca faltar
    (sem historico, sem dia anterior, sem DXY vigente/double buffer),
    cai de volta pro resultado original (valor=None, estimado=False) --
    o card volta a mostrar "sem dados" como antes, nunca inventa numero
    sem poder explicar de onde veio."""
    hoje_result = _ptax_proxy_usdbrl()
    if hoje_result["valor"] is not None:
        return {**hoje_result, "estimado": False}

    if not os.path.exists(HISTORICO_USDBRL_M1_PATH):
        return {**hoje_result, "estimado": False}

    try:
        df = pd.read_parquet(HISTORICO_USDBRL_M1_PATH, columns=["time"])
    except (OSError, ValueError):
        return {**hoje_result, "estimado": False}

    # mesmo ajuste de fuso que _ptax_proxy_usdbrl() agora usa (fix
    # 2026-10-01) -- df["time"] e direto em horario de Brasilia, "hoje"
    # precisa ser calculado no mesmo fuso pra nao errar a data perto da
    # meia-noite (BRT 23h30 ja seria UTC verdadeiro do dia seguinte).
    agora = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=3)).replace(tzinfo=datetime.timezone.utc)
    hoje = agora.date()
    dias_com_dado = sorted({t.date() for t in df["time"]})
    dia_anterior = max((d for d in dias_com_dado if d < hoje), default=None)
    if dia_anterior is None:
        return {**hoje_result, "estimado": False}

    ptax_anterior = _ptax_proxy_usdbrl(dia_anterior)
    if ptax_anterior["valor"] is None:
        return {**hoje_result, "estimado": False, "ptax_anterior_tentativa": ptax_anterior}

    variacao_dxy = _variacao_d1_dxy()
    if variacao_dxy is None:
        return {**hoje_result, "estimado": False, "ptax_anterior": ptax_anterior}

    valor_estimado = round(ptax_anterior["valor"] * (1 + variacao_dxy), 5)

    return {
        "valor": valor_estimado,
        "janelas_completas": 0,
        "janelas": hoje_result["janelas"],
        "estimado": True,
        "ptax_anterior": {"data": dia_anterior.isoformat(), "valor": ptax_anterior["valor"]},
        "variacao_dxy_pct": round(variacao_dxy * 100, 4),
    }


def _dolar_teorico() -> dict:
    """Dolar futuro TEORICO pro vencimento do DOLAR vigente (corretora nacional/B3), via
    paridade coberta de juros: Teorico = Spot x (1+DI1)^(du/252) /
    (1+CupomFRC x dc/360) — ver docstring do endpoint /api/dolar-teorico
    pro detalhe completo. Compara com o preco REAL negociado do proprio DOLAR
    vigente — mesma convencao de ticker (raiz+letra+ano) do DI1/DDI/FRC/DAP,
    decodificada com _decodificar_vertice_b3 (nao a americana). Ate a 1.7.0
    esse calculo comparava com o Dolar da corretora internacional (CFD, vence no
    ULTIMO dia util do mes) contra DI1/FRC (vencem no PRIMEIRO) — um
    descasamento de vertice que fazia o card devolver erro sempre que o
    Dolar ainda nao tinha "alcancado" o mes do DI1/FRC (nas ~3 semanas
    finais de todo mes). Pedido do usuario (2026-09-17): "usa o dolarv26 da
    corretora nacional pra calcular e desconta os du over" — trocar a perna negociada
    pelo DOLAR real fecha o descasamento de vez (DOLAR/DI1/FRC vem da MESMA
    familia curva_br, resolvidos pela MESMA resolver_raiz() no vigente.py —
    ver RAIZES_TESTE la —, entao caem sempre no mesmo mes) e o desconto
    (du do DI1-over e dc do cupom cambial) passa a mirar o vencimento REAL
    do DOLAR (ultimo dia util do mes — _ultimo_dia_util) em vez do vencimento
    do DI1/FRC (primeiro dia util), que era so um proxy aproximado. Spot
    continua sendo USDBRL (double buffer do last_int.py, ativos.
    moedas_continuo) — a B3 nao tem instrumento de spot, so futuro, entao
    essa perna nao muda. Multiplica o resultado por 1000 pra casar com a
    escala do DOLAR (cotado em R$ por US$1.000, ex "5165,75" =
    R$5,16575/US$) — se algum dia o projeto trocar a fonte do spot por algo
    em outra escala, esse x1000 precisa ser revisto junto.

    FRC num vertice A FRENTE do DOLAR/DI1 — ate 2026-09-30 esse vertice era
    CALCULADO (_mes_seguinte(ano, mes) do DOLAR, buscado na curva do FRC),
    partindo do pressuposto fixo "FRC mira sempre EXATAMENTE 1 mes a frente
    do DOLAR/DI1". Reescrito 2026-09-30 (mesmo incidente Risk Dolar/Dolar
    Teorico vazios, 3a causa raiz encontrada no mesmo dia — ver
    resolver_raiz() no vigente.py e o correl.py 1.6.0): esse pressuposto
    ficou FALSO na pratica. resolver_raiz() (curva_br/corretora nacional) tinha o MESMO
    bug do resolver_raiz_americano() — o candidato de posicao 1 (mes+1)
    entrava como "vigente" sem checar _tem_preco_real(). Pro FRC isso
    escondia que FRCV26 (mes+1 de hoje) nunca teve UM preco real sequer
    (nem double buffer, nem historico) — apos corrigir resolver_raiz() pra
    verificar TODO candidato (mesmo padrao do fix do resolver_raiz_
    americano()), o vigente de verdade do FRC saiu 2 meses a frente do DOLAR,
    nao 1 — contrariando o "sempre 1 mes" hardcoded aqui. Em vez de tentar
    adivinhar de novo quantos meses de distancia e "normal", agora usa
    DIRETO o vigente[0] que o vigente.py resolveu pra FRC (ja verificado,
    ja com preco real confirmado) — sem recalcular vertice nenhum. Se o
    FRC voltar a andar 1 mes a frente do DOLAR (ou 3, ou qualquer outro
    numero), esse codigo nao precisa mudar — so acompanha o que o
    vigente.py disser que e o FRC vigente de verdade."""
    config = _ler_config()
    ticker_dolar = (config.get("vigentes", {}).get("DOLAR") or [None])[0]
    if ticker_dolar is None:
        return {"erro": "DOLAR ainda sem vigente (confira se 'DOLAR' esta em ativos.curva_br do config.json e rode o main.py/vigente.py pelo menos uma volta)"}

    vertice = _decodificar_vertice_b3(ticker_dolar, "DOLAR")
    if vertice is None:
        return {"erro": f"nao decodificou o vertice do ticker vigente {ticker_dolar!r}"}
    ano, mes, rotulo = vertice

    ticker_frc = (config.get("vigentes", {}).get("FRC") or [None])[0]
    vertice_frc = _decodificar_vertice_b3(ticker_frc, "FRC") if ticker_frc else None
    rotulo_frc = vertice_frc[2] if vertice_frc else None

    registros_nac = {r["symbol"]: r for r in _ler_double_buffer(*CAMINHOS_NAC)}

    di1_por_rotulo = {p["rotulo"]: p["valor"] for p in _serie_curva_br("DI1", "last", registros_nac)}

    di1 = di1_por_rotulo.get(rotulo)
    cupom = (registros_nac.get(ticker_frc) or {}).get("last") if ticker_frc else None
    # _ptax_proxy_usdbrl_com_fallback() (nao mais _ptax_proxy_usdbrl() direto)
    # -- pedido do usuario (2026-10-01): enquanto a 1a janela de PTAX de
    # hoje nao fecha (~10h10 BRT), extrapola o ultimo PTAX real conhecido
    # pela variacao D1 do DXY, em vez do card ficar ~1h toda manha sem
    # numero nenhum. ptax["estimado"] diz se foi esse o caminho.
    ptax = _ptax_proxy_usdbrl_com_fallback()
    spot = ptax["valor"]
    negociado = (registros_nac.get(ticker_dolar) or {}).get("last")

    faltando = [
        nome
        for nome, valor in (
            ("DI1", di1),
            (ticker_frc or "FRC (sem vigente)", cupom),
            ("PTAX-proxy USDBRL (nem real nem estimavel via DXY)", spot),
            (ticker_dolar, negociado),
        )
        if valor is None
    ]
    if faltando:
        return {"vertice": rotulo, "erro": f"faltando dado real de: {', '.join(faltando)}", "ptax_proxy": ptax}

    data_alvo = _ultimo_dia_util(ano, mes)
    du = _dias_uteis_ate(data_alvo)
    dc = (data_alvo - datetime.date.today()).days

    fator_di1 = (1 + di1 / 100) ** (du / 252)
    fator_cupom = 1 + (cupom / 100) * (dc / 360)
    dolar_teorico = spot * fator_di1 / fator_cupom * 1000
    diferenca_pct = ((negociado - dolar_teorico) / dolar_teorico) * 100 if dolar_teorico else None

    return {
        "vertice": rotulo,
        "vertice_cupom": rotulo_frc,
        "ticker": ticker_dolar,
        "ticker_frc": ticker_frc,
        "spot_usdbrl": spot,
        "spot_estimado": ptax.get("estimado", False),
        "spot_estimado_anterior": ptax.get("ptax_anterior"),
        "spot_estimado_variacao_dxy_pct": ptax.get("variacao_dxy_pct"),
        "ptax_proxy_janelas": ptax["janelas"],
        "ptax_proxy_janelas_completas": ptax["janelas_completas"],
        "di1_pct": di1,
        "cupom_frc_pct": cupom,
        "dias_uteis_di1": du,
        "dias_corridos_cupom": dc,
        "dolar_teorico": round(dolar_teorico, 2),
        "dolar_negociado": negociado,
        "diferenca_pct": round(diferenca_pct, 3) if diferenca_pct is not None else None,
    }


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(title="Painel INDICE/DOLAR — API local")

# CORS liberado pra localhost/127.0.0.1 (uso normal) + faixa 100.x.x.x do
# Tailscale (compartilhamento com colega via VPN, 2026-09-27) - ver
# docstring do modulo e versoes/api_server.md 1.19.0.
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"^http://(localhost|127\.0\.0\.1|100\.\d{1,3}\.\d{1,3}\.\d{1,3}):5173$",
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/layout")
def obter_layout(cliente: str | None = None):
    return _ler_layout(cliente)


@app.post("/api/layout")
def salvar_layout(layout: dict = Body(...), cliente: str | None = None):
    _salvar_layout(layout, cliente)
    return {"ok": True}


@app.get("/api/config-visual")
def obter_config_visual(cliente: str | None = None):
    return _ler_config_visual(cliente)


@app.post("/api/config-visual")
def salvar_config_visual(config: dict = Body(...), cliente: str | None = None):
    _salvar_config_visual(config, cliente)
    return {"ok": True}


@app.get("/api/last/nac")
def last_nac():
    return _ler_double_buffer(*CAMINHOS_NAC)


@app.get("/api/last/int")
def last_int():
    return _ler_double_buffer(*CAMINHOS_INT)


@app.get("/api/last")
def last_merged():
    return {
        "nac": _ler_double_buffer(*CAMINHOS_NAC),
        "int": _ler_double_buffer(*CAMINHOS_INT),
    }


@app.get("/api/yeldcurve")
def yeldcurve():
    """Curva de juros dos treasurys americanos (1M a 30Y) - le o double
    buffer que yeldcurve.py grava (yield_pct = ultimo preco/leitura atual,
    prev_pct = fechamento D-1), mesmo padrao de /api/last/nac. [] enquanto
    o yeldcurve.py nao tiver rodado (ou o Excel/Power Query nao estiver
    aberto - ver docstring do proprio script)."""
    return _ler_double_buffer(*CAMINHOS_YELDCURVE)


@app.get("/api/dp")
def dp():
    """Projecao de desvios de preco (dp.py), Indice/Dolar em MTF (M15 a W1) -
    le o double buffer que dp.py grava: por combinacao, a "perna" atual do
    histograma do MACD (fase/candles_a_frente/preco_projetado quando ja
    formou a ponta e esta voltando pro zero), media_base, e os niveis de
    desvio (1-2: MACD+ATR linear na direcao do momentum; 3-4: estatistico,
    ATR*sqrt(tempo) com probabilidade normal), cada um ja com o IFR
    simulado e a certificacao (dentro de 30-70 ou "esticado"). Ver
    docstring do modulo dp.py pro racional completo. [] enquanto o dp.py
    nao tiver rodado."""
    return _ler_double_buffer(*CAMINHOS_DP)


@app.get("/api/noticias")
def noticias():
    """Manchetes em tempo real do canal publico do Telegram fonte de noticias
    (agrega a fonte agregador de noticias) - le o double buffer que noticias.py
    grava via poll da preview publica do canal (sem API/credencial
    nenhuma). Lista de {"id", "hora_iso", "texto", "link"}, mais recente
    primeiro, ate 40 itens. [] enquanto o noticias.py nao tiver rodado."""
    return _ler_double_buffer(*CAMINHOS_NOTICIAS)


@app.get("/api/vigentes")
def vigentes():
    config = _ler_config()
    return config.get("vigentes", {})


@app.get("/api/grades-cotacoes")
def grades_cotacoes():
    """Registro declarativo (pedido do usuario 2026-09-29) de cada
    pagina/view do frontend: nome de exibicao, raiz de referencia (quando
    houver) e quais FEEDS (arrays ja pollados no App.jsx, ex.: last_int/
    magnificas) compoem a grade de cotacoes daquela pagina. Combina DUAS
    chaves do config.json, de proposito separadas: ativos_referencia_extra
    (broker/raiz, ja consumida por correl.py/vies_direcional.py/dp.py -
    NAO mexida aqui, so lida) e grades_cotacoes (nome/feeds, nova, so
    consumida por este endpoint - misturar as duas quebraria os outros
    scripts, que exigem raiz/broker em todo item). Adicionar uma pagina
    nova no futuro vira so uma entrada em grades_cotacoes, sem editar
    App.jsx - mesmo principio ja usado em ativos_referencia_extra."""
    config = _ler_config()
    extras = config.get("ativos_referencia_extra", {})
    grades = config.get("grades_cotacoes", {})
    chaves = set(extras.keys()) | set(grades.keys())
    resultado = {}
    for chave in chaves:
        info_extra = extras.get(chave, {})
        info_grade = grades.get(chave, {})
        resultado[chave] = {
            "nome": info_grade.get("nome", chave),
            "raiz": info_extra.get("raiz"),
            "feeds": info_grade.get("feeds", ["last_int"]),
        }
    return resultado


@app.get("/api/peso-mercado")
def peso_mercado():
    return _ler_peso_mercado()


@app.get("/api/vies-direcional")
def vies_direcional():
    """Vies direcional (indice/dolar + cada ativo de ativos_referencia_extra,
    ex.: usatec) — le o double buffer que vies_direcional.py grava. {}
    enquanto o script nao tiver rodado ainda nesta sessao."""
    return _ler_double_buffer(*CAMINHOS_VIES_DIRECIONAL)


@app.get("/api/amplitude")
def amplitude():
    """Amplitude de mercado (advance/decline + novas maximas/minimas) por
    universo (config.json -> amplitude_universos) e timeframe (M15 a W1) -
    le o double buffer que amplitude.py grava continuamente. {"consolidado":
    []} enquanto o script nao tiver rodado, ou pro universo que ainda nao
    tem raizes configuradas (ver docstring do amplitude.py)."""
    return _ler_double_buffer(*CAMINHOS_AMPLITUDE)


@app.get("/api/last/magnificas")
def last_magnificas():
    """Cotacao + variacao intradiaria das 7 magnificas (Apple/Microsoft/
    Alphabet/Amazon/Nvidia/Meta/Tesla) - mesmo formato de /api/last/int
    (lista de {"broker", "symbol", "time", "last", "session_close"}), le o
    double buffer que magnificas.py grava continuamente. [] enquanto o
    script nao tiver rodado ainda nesta sessao."""
    return _ler_double_buffer(*CAMINHOS_MAGNIFICAS)


@app.get("/api/last/sentimento-em")
def last_sentimento_em():
    """Cotacao + variacao intradiaria de EWZ (iShares MSCI Brazil) e EEM
    (iShares MSCI Emerging Markets) - termometro de sentimento de risco
    Brasil/emergentes fora do horario da B3 - mesmo formato de
    /api/last/int (lista de {"broker", "symbol", "time", "last",
    "session_close"}), le o double buffer que sentimento_em.py grava
    continuamente. [] enquanto o script nao tiver rodado ainda nesta
    sessao."""
    return _ler_double_buffer(*CAMINHOS_SENTIMENTO_EM)


@app.get("/api/modelo-swing/universo")
def modelo_swing_universo():
    """Lista de raizes disponiveis pro seletor de ativo do
    ModeloSwingCard.jsx - mesmo universo de diag_sazonalidade_swings.py
    (129 ativos: Indice/Dolar + moedas_continuo + indices_continuo +
    commodities_internacionais + treasury_etf_eua + acoes_nasdaq100 +
    vencimento_americano sem Dolar/Indice)."""
    return montar_universo()


@app.get("/api/modelo-swing/{raiz}")
def modelo_swing(raiz: str):
    """Unico endpoint do projeto que CALCULA na hora em vez de so ler um
    arquivo pre-pronto (ver docstring de cenario_final_swing.py) - roda o
    GARCH(1,1) + le vies MACD/IFR + sazonalidade de horario, MAIS os dois
    classificadores LightGBM (sinal/direcao/confianca/alvo/entradas) pro
    ativo escolhido pelo usuario no seletor do card. So e chamado quando o
    usuario TROCA o ativo (nunca em poll continuo) - custo (~1s, ajuste do
    GARCH) e aceitavel nesse uso, mas nao seria pra um endpoint pollado."""
    try:
        return _cenario_final_swing.analisar(raiz)
    except (ImportError, FileNotFoundError) as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/dolar-teorico")
def dolar_teorico():
    return _dolar_teorico()


@app.get("/api/curva-juros")
def curva_juros():
    return _ler_curva_juros()


@app.get("/api/curvas/{tipo}")
def curva(tipo: str):
    if tipo not in TIPOS_CURVA_VALIDOS:
        raise HTTPException(
            status_code=404,
            detail=f"tipo de curva desconhecido: {tipo!r}. Use um de {sorted(TIPOS_CURVA_VALIDOS)}.",
        )

    registros_por_symbol = {r["symbol"]: r for r in _ler_double_buffer(*CAMINHOS_NAC)}

    if tipo == "trio":
        return _serie_trio(registros_por_symbol)

    if tipo == "juros":
        # DI1 e a raiz principal (last + session_close dela mesma) mais uma
        # 3a serie de referencia cruzada com OC1 (raiz que so tem
        # session_close — ver EXCECOES_SO_CLOSE no vigente.py) — por isso
        # essa e a unica que combina DUAS raizes num so grafico.
        return {
            "last_di1": _serie_curva_br("DI1", "last", registros_por_symbol),
            "session_close_di1": _serie_curva_br("DI1", "session_close", registros_por_symbol),
            "session_close_oc1": _serie_curva_br("OC1", "session_close", registros_por_symbol),
        }

    # frc / cupom-inflacao: pedido do usuario ("podemos adicionar aos outros
    # graficos os contratos que neles faltam e session close e last?") —
    # mesma logica do DI1 (_serie_curva_br ja e generica), so que cada uma
    # com UMA raiz so (nem FRC nem DAP tem uma raiz-irma so-com-session_close
    # tipo OC1, entao aqui sao so as 2 series da propria raiz). raiz vem de
    # config.json -> vigentes (resolvida pelo vigente.py, mesma familia
    # curva_br do DI1/OC1 — ver RAIZES_TESTE no vigente.py).
    raiz = RAIZ_POR_TIPO_CURVA[tipo]
    chave = raiz.lower()
    return {
        f"last_{chave}": _serie_curva_br(raiz, "last", registros_por_symbol),
        f"session_close_{chave}": _serie_curva_br(raiz, "session_close", registros_por_symbol),
    }


if __name__ == "__main__":
    import uvicorn

    # host="0.0.0.0" (era "127.0.0.1") - 2026-09-27, pedido do usuario:
    # compartilhar o dashboard com um colega via VPN (Tailscale). Com
    # "127.0.0.1" o servidor so aceitava conexao do proprio PC; com
    # "0.0.0.0" ele escuta em toda interface de rede, entao um PC de
    # fora na mesma VPN tambem alcanca. CORS (acima) e quem continua
    # controlando QUEM pode chamar, nao o bind do socket.
    uvicorn.run(app, host="0.0.0.0", port=8000)
