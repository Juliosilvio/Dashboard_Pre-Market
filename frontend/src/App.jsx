// App.jsx — tela unica do painel: curva de juros (DI1), FRC e Cupom de
// Inflacao (DAP) — as 3 com dado REAL — e a tabela de cotacoes.
//
// Em tela larga (desktop, > TELA_PEQUENA_PX): cada grafico e uma "janela"
// livre dentro do dashboard-canvas (ver Panel.jsx) — arrasta pra qualquer
// lugar pela barrinha de cima, redimensiona puxando o canto inferior
// direito, e o desenho (SVG) acompanha o tamanho em tempo real. Arrastar ou
// redimensionar um painel tambem traz ele pro topo da pilha (onFront ->
// trazerParaFrente), senao ele fica preso atras de outro declarado depois —
// bug relatado pelo usuario ("os graficos entram embaixo... e somem").
//
// O canvas inteiro (todos os paineis juntos, no tamanho que o arranjo
// atual ocupa) e reescalado com CSS transform:scale() pra caber EXATAMENTE
// na largura disponivel, seja qual for — pedido do usuario: "os graficos
// tem que se adaptar a janela principal e a janela principal a pagina,
// independente do tamanho da tela". Antes disso, o canvas tinha um tamanho
// fixo em px e so ficava com scroll horizontal quando a janela era menor
// que ele (ex: navegador dividido ao meio na tela) — agora ele sempre
// encolhe OU estica pra preencher a largura da janela, sem cortar nada e
// sem sobrar espaco morto. useLarguraContainer() mede a largura real
// disponivel (ResizeObserver no .dashboard-canvas-viewport) e o App calcula
// escala = largura_disponivel / largura_logica_do_canvas; essa escala e
// repassada pra cada Panel (que precisa dela pra converter pixel de mouse
// em pixel de layout ao arrastar/redimensionar — ver Panel.jsx).
//
// Em tela pequena (celular/tablet, <= TELA_PEQUENA_PX): pedido do usuario
// ("a janela principal tem que se adaptar ao tamanho da tela pois pode ser
// que seja aberto em celulares e tablets") — o canvas livre nao faz sentido
// numa tela estreita (arrastar com o dedo numa alcinha pequena e ruim, e
// nao sobra espaco horizontal pra espalhar janela nenhuma). Os mesmos 4
// graficos caem pra uma pilha vertical normal, largura 100%, sem arrastar
// nem redimensionar manual — cada um ja e responsivo por CSS (flex/percent,
// ver JurosChart) e se adapta sozinho a largura da tela.
//
// Botao "Salvar layout" no cabecalho grava a posicao/tamanho de cada painel
// (modo desktop) no localStorage E no backend (json/layout.json via POST
// /api/layout) — pedido do usuario: "salve em backend tambem".
//
// Checkbox "Mostrar pontos" no cabecalho: config de ESTILO dos graficos
// (JurosChart), separada do layout dos paineis — pedido do usuario depois
// de tirar as bolinhas do grafico de juros: "como podemos salvar esse tipo
// de formato... um controller pra frontend tambem?". Usa useConfigVisual.js
// (mesmo padrao do useLayout.js: localStorage + backend via GET/POST
// /api/config-visual), so que sem botao "Salvar" separado — cada toggle ja
// salva sozinho na hora (ver comentario no proprio hook).
//
// Cotacoes: poll em /api/last/int a cada 1s (o backend flusha a cada ~0.3s,
// 1s de poll ja acompanha bem sem martelar a API a toa).
//
// Tabela de cotacoes — pedido do usuario ("colocar as colunas em ordem:
// hora, ativo, variação diária, preço com célula piscante; organizar os
// tickers conforme o peso de cada um no índice e no dólar"): variação
// diária e a célula piscante vem de dados que ja chegam em /api/last/int
// (session_close novo no last_int.py 1.7.0) — não precisam de poll
// separado. A ordenação por peso já precisa: poll em /api/peso-mercado a
// cada 60s (correlação real contra Indice/Dolar, calculada pelo correl.py só
// uma vez por rodada do pipeline — ~5min — 60s de poll já acompanha sem
// martelar a API por um dado que quase nunca muda). Ver QuotesTable.jsx pra
// a lógica de ordenação/variação/blink em si.
//
// Painel de cotacoes agora usa o padrao children-como-funcao do Panel.jsx
// (o mesmo que o JurosChart ja usava) pra receber a largura REAL do painel
// e decidir quantas colunas cabem — pedido do usuario: "conforme eu estreito
// o box do painel quero que os ativos se empilhem um embaixo do outro" (a
// tabela empilha em 1 coluna sozinha quando o painel fica estreito, ver
// calcularNumColunas em QuotesTable.jsx).
//
// Curva de juros (DI1), FRC e Cupom de Inflacao (DAP): poll em
// /api/curvas/{tipo} a cada 5s — os 3 endpoints JA calculam dado real (lidos
// do double buffer do last_nac.py + config.json->vigentes, ver
// api_server.py). Pedido do usuario: "podemos adicionar aos outros graficos
// os contratos que neles faltam e session close e last?" — antes, FRC/Cupom
// eram so uma amostra ilustrativa fixa (5 pontos, sem session close); agora
// os 3 graficos usam o MESMO componente (JurosChart, reaproveitado — ver
// useSeriesCurvaSimples) mostrando TODOS os contratos vigentes (ver
// config.json->vigentes) com 2 series cada (Last + Session Close da propria
// raiz). Sem amostra ilustrativa em nenhum dos 3: se vier vazio, mostra
// "sem dados" (ver JurosChart) em vez de fingir numero. CurveChart.jsx (o
// componente antigo, com resumo "headline + delta") ficou sem uso — nao foi
// apagado (mesma cautela do Resizable.jsx), so nenhum painel importa mais
// ele.
//
// Card "Trio" (painel-trio) — pedido do usuario: aproximacao pratica do
// "Trio" B3/Anbima (DOL + DDI + DI1 no mesmo vencimento — quando as tres
// pernas nao fecham a conta, e sinal de desalinhamento de preco). Sem a
// perna DOL (o projeto ainda nao coleta a curva de vencimentos do dolar
// futuro — ver docstring de /api/curvas/trio no api_server.py), o card
// compara DDI (cupom cambial REAL negociado, so ~5 vertices liquidos) com
// FRC (cupom cambial TEORICO/"limpo") nos MESMOS vertices, reaproveitando o
// JurosChart de novo (2 series). O spread numerico (DDI - FRC) por vertice
// vem num resumo abaixo do grafico (footer do JurosChart, ver
// useSeriesTrio()) — LIMIAR_SPREAD_ALERTA destaca em vermelho quando o
// modulo do spread foge do normal (limiar inicial arbitrario, ajustavel).

import { useEffect, useRef, useState } from "react";
import JurosChart from "./components/JurosChart.jsx";
import YeldCurveChart from "./components/YeldCurveChart.jsx";
import DesviosPainel from "./components/DesviosPainel.jsx";
import AmplitudePainel from "./components/AmplitudePainel.jsx";
import ModeloSwingCard from "./components/ModeloSwingCard.jsx";
import NoticiasPainel from "./components/NoticiasPainel.jsx";
import SelicJurosChart from "./components/SelicJurosChart.jsx";
import Panel from "./components/Panel.jsx";
import QuotesTable from "./components/QuotesTable.jsx";
import DolarTeoricoCard from "./components/DolarTeoricoCard.jsx";
import CausalidadeLegenda from "./components/CausalidadeLegenda.jsx";
import { usePolling } from "./hooks/usePolling.js";
import { useLayout } from "./hooks/useLayout.js";
import { useConfigVisual } from "./hooks/useConfigVisual.js";
import { api } from "./api/client.js";

// Posicao/tamanho padrao de cada painel (px, dentro do dashboard-canvas,
// modo desktop) — so vale enquanto ninguem salvou layout ainda; depois
// disso quem manda e o que estiver salvo (backend > localStorage, ver
// useLayout.js). "z" e a ordem de empilhamento inicial (arbitraria — o
// primeiro arrasto/redimensionamento de qualquer painel ja reordena).
// pedido do usuario: "vamos montar outro localhost, pois iremos montar uma
// area onde tera um menu de opções" — decidido NAO criar um segundo
// processo/porta (ver conversa), e sim um menu interno que troca a VIEW
// dentro do mesmo app (mesmo backend :8000). As chaves aqui tem que bater
// com as chaves de ativos_referencia_extra do config.json (o nome que
// vies_direcional.py usa pra gravar o bloco no /api/vies-direcional e o
// mesmo que correl.py usa em "correlacao_<nome>" — ver QuotesTable.jsx
// ordenarPorCorrelacaoAbsoluta()). Chaves do /api/vies-direcional que NAO
// sao ativo nenhum (metadados do payload), filtradas do menu.
const CHAVES_VIES_NAO_ATIVO = new Set(["atualizado_em", "indice", "dolar", "detalhes"]);
// ATIVOS_EXTRA_INFO (nome de exibicao + raiz por view) saiu daqui em
// 2026-09-29 (Decimo passo, pedido do usuario: "controller" pra quando
// uma view nova for criada o sistema ja saber quais ativos entram na
// grade dela) — agora vem de GET /api/grades-cotacoes (config.json ->
// ativos_referencia_extra + grades_cotacoes), lido como `registroViews`
// dentro do componente. Ver cotacoesDaView()/feedsCotacoes la dentro.

const LAYOUT_PADRAO = {
  "painel-juros": { x: 0, y: 0, width: 1180, height: 340, z: 1 },
  "painel-frc": { x: 0, y: 356, width: 570, height: 280, z: 2 },
  "painel-cupom": { x: 590, y: 356, width: 570, height: 280, z: 3 },
  "painel-cotacoes": { x: 0, y: 652, width: 1180, height: 360, z: 4 },
  // novo — ver "Card 'Trio'" no comentario do topo do arquivo. Posicionado
  // depois dos demais (nao colide com layout ja salvo de ninguem: useLayout.js
  // mescla LAYOUT_PADRAO com o que estiver salvo, entao uma chave nova sempre
  // aparece na posicao padrao mesmo pra quem ja tinha layout salvo antes).
  "painel-trio": { x: 0, y: 1028, width: 570, height: 300, z: 5 },
  // novo — card "Dolar Teorico" (ver comentario proprio mais abaixo, perto
  // de useDolarTeorico()). Ao lado do Trio, bem menor (so numero, sem
  // grafico) — altura menor que os outros cards de proposito.
  "painel-dolar-teorico": { x: 590, y: 1028, width: 570, height: 190, z: 6 },
  // novo — indice de juros de prazo constante (DI 1 ano/2 anos) x Selic
  // Meta, ver curva_juros.py/SelicJurosChart.jsx. Painel largo (serie
  // temporal longa, ~2 anos), posicionado depois dos demais (mesma logica
  // dos outros paineis novos: nao colide com layout ja salvo de ninguem).
  "painel-selic-juros": { x: 0, y: 1218, width: 1180, height: 300, z: 7 },
  // novo — pedido do usuario: "montar duas tabelas, Risk Índice e Risk
  // Dólar, uma ao lado da outra" — clone do "painel-cotacoes" (mesma
  // largura/altura padrao), posicionado ao lado pra caber lado a lado.
  // Quem ja tinha "painel-cotacoes" com layout salvo (posicao/tamanho
  // customizados) mantem esse layout intacto — so essa chave nova entra
  // com o padrao abaixo (useLayout.js so aplica o padrao pra chave que
  // ainda nao foi salva).
  "painel-cotacoes-dolar": { x: 1200, y: 652, width: 1180, height: 360, z: 8 },
  // novo — curva de juros dos treasurys americanos (yeldcurve.py, ver
  // YeldCurveChart.jsx / /api/yeldcurve no api_server.py). Posicionado
  // depois dos demais (mesma logica dos outros paineis novos: nao colide
  // com layout ja salvo de ninguem).
  "painel-yeldcurve": { x: 0, y: 1532, width: 1180, height: 340, z: 9 },
  "painel-dp": { x: 0, y: 1892, width: 1180, height: 640, z: 9 },
  // novo — manchetes em tempo real do canal fonte de noticias (ver noticias.py
  // / NoticiasPainel.jsx). Posicionado depois dos demais (mesma logica
  // dos outros paineis novos: nao colide com layout ja salvo de ninguem).
  "painel-noticias": { x: 0, y: 2548, width: 1180, height: 480, z: 10 },
  // pedido do usuario: "quero mover a grade como podemos mover na view do
  // indice e do dolar" — a view de um ativo extra (ex.: usatec/Nasdaq)
  // ganha o MESMO tipo de painel arrastavel/redimensionavel (Panel.jsx) que
  // a view principal usa, so que so ele aparece quando essa view esta ativa
  // (ver graficosExtra/idsPaineisExtra mais abaixo). Convencao de id:
  // "painel-cotacoes-<chave>" — o proximo ativo extra (ex.: gold) so
  // precisa de mais 1 linha aqui, com a MESMA chave usada em
  // config.json -> ativos_referencia_extra/grades_cotacoes. Chegou a
  // existir um "painel-vies-<chave>" tambem
  // (card com score/vies/IFR) — removido a pedido do usuario ("esse card e
  // desnecessario, pode deleta-lo"); o componente continua em
  // ViesDirecionalCard.jsx se um dia precisar de volta.
  "painel-cotacoes-usatec": { x: 0, y: 0, width: 1180, height: 640, z: 11 },
  // pedido do usuario (depois de ver a view do Nasdaq): "replique esses
  // tres cards la" — Curva de Juros Treasurys (EUA), Projecao de Desvios
  // (DP) e Noticias sao paineis GLOBAIS (mesma serie/dado da view
  // principal, nao ha versao "so do Nasdaq" deles) — so ganham um id
  // proprio aqui pra poder ficar em posicao/tamanho diferente em cada view.
  "painel-yeldcurve-usatec": { x: 0, y: 656, width: 1180, height: 340, z: 12 },
  "painel-dp-usatec": { x: 0, y: 1012, width: 1180, height: 640, z: 13 },
  "painel-noticias-usatec": { x: 0, y: 1668, width: 1180, height: 480, z: 14 },
  // card de juros americanos (TLT/IEF/SHY, ver config.json ->
  // dp_ativos_extra + dp.py 1.3.0) — SO existe na view usatec, pedido do
  // usuario 2026-09-26 ("ve se tem alguma acao ou ativo que reflete os
  // juros americanos treasurys"). Diferente dos 4 paineis acima, este NAO
  // e generico por chave (nao faz sentido treasury americano numa
  // hipotetica view futura de outro ativo) — ver idsPaineisExtra abaixo.
  "painel-juros-usatec": { x: 0, y: 2164, width: 1180, height: 480, z: 15 },
  // amplitude de mercado (advance/decline + novas maximas/minimas) das
  // 100 acoes do Nasdaq-100 (config.json -> amplitude_universos.nasdaq,
  // coletadas via mt5stock) - amplitude.py / AmplitudePainel.jsx. SO
  // existe na view usatec, mesma logica do painel-juros-usatec acima
  // (nao generico por chave - "indice" ainda nao tem raizes configuradas,
  // ver docstring do amplitude.py).
  "painel-amplitude-usatec": { x: 0, y: 2644, width: 1180, height: 420, z: 16 },
  // card generico "Cenario de Swing" por view extra (ver ModeloSwingCard.jsx
  // v2.0.0 / idsPaineisExtra abaixo) - so existe view usatec por enquanto,
  // mas a chave e generica (nao especifico feito juros/amplitude acima).
  "painel-modelo-swing-usatec": { x: 0, y: 3064, width: 570, height: 420, z: 18 },
  // primeiro modelo de cenario de swing (GARCH + vies MACD/IFR +
  // sazonalidade de horario) - pedido do usuario 2026-09-27 ("monte o
  // primeiro modelo"). v2.0.0 do ModeloSwingCard.jsx (2026-09-27):
  // corrigido pra NAO ter seletor proprio - o ativo vem do CONTEXTO ja
  // existente (mesma logica de painel-cotacoes/painel-cotacoes-dolar,
  // simboloFuturo="Indice"/"Dolar") - "o cenario e construido pelo ativo
  // que eu escolho [na view] e os cards aparecem na pagina escolhida".
  // Por isso, na view principal, sao DOIS paineis lado a lado (Indice/Indice
  // e Dolar/Dolar, igual ao par de cotacoes) em vez de um so. Posicionados
  // depois de todos os demais da view principal, mesma logica de nao
  // colidir com layout ja salvo de ninguem.
  "painel-modelo-swing-indice": { x: 0, y: 3028, width: 570, height: 420, z: 17 },
  "painel-modelo-swing-dolar": { x: 600, y: 3028, width: 570, height: 420, z: 17 },
  // novo — legenda explicando os badges Gi/dg de causalidade de Granger
  // nas tabelas Risk Indice/Risk Dolar (ver CausalidadeLegenda.jsx,
  // QuotesTable.jsx). Pedido do usuario: "coloque um indice explicando o
  // que e dg e gi... pode ser um card novo nao tem problema".
  // Posicionado depois de todos os demais (mesma logica de nao colidir
  // com layout ja salvo de ninguem).
  "painel-causalidade-legenda": { x: 0, y: 3468, width: 780, height: 240, z: 19 },
};

// ids dos paineis da view "principal" (Indice/Dolar) — usado tanto pra
// decidir o bounding box do canvas (tamanhoCanvas, so conta os paineis da
// view ATIVA, nao todos os que existem no layout salvo) quanto pra saber
// qual JSX renderizar (graficos vs graficosExtra, ver App()).
const IDS_PAINEIS_PRINCIPAL = [
  "painel-juros",
  "painel-frc",
  "painel-cupom",
  "painel-cotacoes",
  "painel-cotacoes-dolar",
  "painel-trio",
  "painel-dolar-teorico",
  "painel-selic-juros",
  "painel-yeldcurve",
  "painel-dp",
  "painel-noticias",
  "painel-modelo-swing-indice",
  "painel-modelo-swing-dolar",
  "painel-causalidade-legenda",
];

// ids dos paineis de uma view de ativo extra (ex.: "usatec") — sempre os
// mesmos 2, so muda o sufixo. Ver comentario da convencao de id acima.
function idsPaineisExtra(chave) {
  const ids = [
    `painel-cotacoes-${chave}`,
    `painel-yeldcurve-${chave}`,
    `painel-dp-${chave}`,
    `painel-noticias-${chave}`,
    `painel-modelo-swing-${chave}`,
  ];
  // painel-juros-usatec e especifico da view usatec (treasury americano so
  // faz sentido pro Nasdaq) — nao generico por chave como os 4 de cima, ver
  // comentario em LAYOUT_PADRAO.
  if (chave === "usatec") {
    ids.push(`painel-juros-${chave}`);
    ids.push(`painel-amplitude-${chave}`);
  }
  return ids;
}

const MARGEM_CANVAS = 40;

// bounding box de todos os paineis + margem — extraida como funcao pura (em
// vez de inline) porque agora e chamada tanto no estado inicial quanto no
// useEffect que so roda quando ninguem esta arrastando (ver comentario em
// tamanhoCanvas dentro do App()).
function calcularTamanhoCanvas(paineis) {
  let maxX = 0;
  let maxY = 0;
  Object.values(paineis).forEach((p) => {
    maxX = Math.max(maxX, p.x + p.width);
    maxY = Math.max(maxY, p.y + p.height);
  });
  return { width: maxX + MARGEM_CANVAS, height: maxY + MARGEM_CANVAS };
}

// Abaixo disso (celular, tablet, notebook pequeno, OU janela do navegador
// dividida com outra na tela — usuario relatou: "dividi metade da tela e
// nao se adaptou") a tela cai pra pilha vertical fixa (ver comentario do
// topo do arquivo). O numero e maior que a largura minima do canvas livre
// (~1220px, ver LAYOUT_PADRAO) DE PROPOSITO: antes era 1024px, exatamente
// menor que os ~1220px que o canvas padrao precisa pra caber sem cortar
// nada — sobrava uma faixa (1024-1220px) onde a pagina nao empilhava (nao
// era "pequena" o bastante) mas tambem nao cabia inteira (scroll horizontal
// cortando grafico e tabela). 1280px fecha essa brecha com folga.
const TELA_PEQUENA_PX = "(max-width: 1280px)";

const ROTULO_STATUS = {
  salvando: "Salvando…",
  salvo: "Layout salvo ✓",
  erro: "Salvo só neste navegador (backend fora do ar)",
};

// valores padrao da config visual (ver useConfigVisual.js) — so entram em
// vigor enquanto ninguem mudou nada ainda nesta instalacao (backend e
// localStorage vazios); depois disso quem manda e o que estiver salvo.
// mostrarPontos:false = comportamento atual (pedido do usuario: "pode tirar
// essas bolinhas de todas as linhas do grafico?").
const CONFIG_VISUAL_PADRAO = { mostrarPontos: false };

const ROTULO_STATUS_CONFIG = {
  salvando: "Salvando…",
  salvo: "Salvo ✓",
  erro: "Salvo só neste navegador (backend fora do ar)",
};

// FRC e Cupom (DAP) tem o mesmo formato de resposta entre si (2 series: Last
// + Session Close da propria raiz — ver /api/curvas/{tipo} no api_server.py)
// diferente do DI1, que combina 2 raizes (DI1 + OC1) em 3 series — por isso
// esse hook e generico (raiz parametrizada) e useSeriesJuros() continua
// separado, com suas 3 chaves explicitas.
function useSeriesCurvaSimples(tipo, raiz, corLast, corSessionClose) {
  const { dado } = usePolling(() => api.curva(tipo), 5000, [tipo]);
  const chave = raiz.toLowerCase();
  return [
    { key: "last", label: `Last (${raiz})`, cor: corLast, pontos: dado?.[`last_${chave}`] ?? [] },
    {
      key: "session_close",
      label: `Session Close (${raiz})`,
      cor: corSessionClose,
      pontos: dado?.[`session_close_${chave}`] ?? [],
    },
  ];
}

function useSeriesJuros() {
  const { dado } = usePolling(() => api.curva("juros"), 5000, []);
  return [
    { key: "last_di1", label: "Last (DI1)", cor: "var(--s-juros)", pontos: dado?.last_di1 ?? [] },
    {
      key: "session_close_di1",
      label: "Session Close (DI1)",
      cor: "var(--s-frc)",
      pontos: dado?.session_close_di1 ?? [],
    },
    {
      key: "session_close_oc1",
      label: "Session Close (OC1)",
      cor: "var(--s-cupom)",
      pontos: dado?.session_close_oc1 ?? [],
    },
  ];
}

// spread (DDI - FRC, em pontos percentuais) acima deste modulo entra
// destacado em vermelho no footer do card do Trio (ver .trio-spread-item--
// alerta em tokens.css) — limiar inicial arbitrario (0,15pp), so pra
// separar "ruido normal de D-1 lag" de "desalinhamento que chama atencao";
// ajustavel depois com mais dado real acumulado.
const LIMIAR_SPREAD_ALERTA = 0.15;

// Card do Trio (DDI x FRC, ver /api/curvas/trio no api_server.py) — 2 series
// pro JurosChart (mesmo componente do DI1/FRC/Cupom) + o spread numerico
// (DDI - FRC por vertice), usado no footer do card em vez de entrar como
// 3a linha no grafico (escala diferente: spread e uma diferenca pequena,
// ~0,1-0,5pp, perto de 0 — numa linha junto com DDI/FRC, que ficam na casa
// de 5-8%, ela sumiria achatada no fundo do grafico).
function useSeriesTrio() {
  const { dado } = usePolling(() => api.curva("trio"), 5000, []);
  const series = [
    { key: "last_ddi", label: "Last (DDI — real)", cor: "var(--s-ddi)", pontos: dado?.last_ddi ?? [] },
    { key: "last_frc", label: "Last (FRC — teórico)", cor: "var(--s-frc)", pontos: dado?.last_frc ?? [] },
  ];
  return { series, spread: dado?.spread_ddi_frc ?? [] };
}

// Card "Curva de Juros — Treasurys (EUA)" (ver /api/yeldcurve no
// api_server.py / yeldcurve.py) — 2 series pro YeldCurveChart: Atual
// (yield_pct, ultima leitura) e Fechamento D-1 (prev_pct) — confirmado
// com o usuario (2026-09-23): "o ultimo preco equivale a este yield_pct e
// o fechamento D1 equivale a este prev_pct". Mesmo par de cores
// azul/laranja dos outros cards (azul = valor vivo, laranja = referencia
// anterior). Poll a cada 30s — o yeldcurve.py so atualiza a cada 5min
// (ritmo do Power Query do Excel), nao faz sentido pollar tao rapido
// quanto as curvas B3 (5s, que tem MT5 em tempo real por tras).
function useSeriesYeldCurve() {
  const { dado } = usePolling(api.yeldcurve, 30000, []);
  const linhas = dado ?? [];
  return [
    {
      key: "atual",
      label: "Atual",
      cor: "var(--s-juros)",
      pontos: linhas.map((l) => ({ rotulo: l.vencimento, valor: l.yield_pct })),
    },
    {
      key: "prev_d1",
      label: "Fechamento D-1",
      cor: "var(--s-frc)",
      pontos: linhas.map((l) => ({ rotulo: l.vencimento, valor: l.prev_pct })).filter((p) => p.valor != null),
    },
  ];
}

// Card "Dólar Teórico" (ver /api/dolar-teorico no api_server.py) — pedido
// do usuario: "quero colocar um card pequeno ja com o resultado" (depois de
// perguntar onde o Dolar vigente deveria fechar). Poll a cada 5s, mesma
// cadencia das curvas — o resultado ja vem pronto (teorico, negociado,
// diferenca), sem transformacao nenhuma aqui.
// dp.py / /api/dp — projecao de desvios de preco (MACD/ATR/IFR) de
// Indice/Dolar em MTF. Poll de 1h (PAUSA_DP): pedido do usuario (2026-09-23)
// "nao precisa ser rapidao, pode atualizar de hora em hora" — dp.py em si
// recalcula toda vez que o parquet de preco muda (bem mais rapido que
// isso), mas nao faz sentido o FRONT pollar mais rapido do que o usuario
// pediu pra olhar.
const PAUSA_DP = 60 * 60 * 1000;

function useDesviosDp() {
  // dp.py 1.1.0: agora entrega {"detalhe": [...], "consolidado": [...]}
  // em vez de uma lista plana (ver DesviosPainel.jsx) — consolidado tem no
  // maximo 2 entradas (uma por ativo, Indice/Dolar), o que o painel consome.
  const { dado } = usePolling(api.dp, PAUSA_DP, []);
  return dado ?? { detalhe: [], consolidado: [] };
}

// amplitude.py / /api/amplitude — amplitude de mercado (advance/decline +
// novas maximas/minimas) por universo (config.json -> amplitude_universos)
// e timeframe. Poll de 1 minuto: o motor recalcula sozinho toda vez que o
// mtime de um parquet do universo muda (mesmo padrao de dp.py), mas o
// TF mais curto que ele agrega e M15 — nao ha ganho em pollar mais rapido
// que isso, e evita bater no endpoint sem necessidade.
const PAUSA_AMPLITUDE = 60 * 1000;

function useAmplitude() {
  const { dado } = usePolling(api.amplitude, PAUSA_AMPLITUDE, []);
  return dado ?? { consolidado: [] };
}

// noticias.py / /api/noticias — manchetes em tempo real do canal publico
// do Telegram fonte de noticias. Poll de 15s (mesma cadencia do poll que
// noticias.py ja faz contra o Telegram — pedido do usuario (2026-09-23):
// "noticias em tempo real!!!", entao aqui sim faz sentido acompanhar de
// perto, ao contrario do PAUSA_DP acima).
const PAUSA_NOTICIAS = 15 * 1000;

function useNoticias() {
  const { dado } = usePolling(api.noticias, PAUSA_NOTICIAS, []);
  return dado ?? [];
}


function useDolarTeorico() {
  const { dado } = usePolling(api.dolarTeorico, 5000, []);
  return dado;
}

// Card "Juros de Prazo Constante x Selic" (ver /api/curva-juros no
// api_server.py / curva_juros.py) — 3 linhas (DI 1 ano, DI 2 anos, Selic
// Meta) numa SERIE TEMPORAL (SelicJurosChart, diferente do JurosChart que
// e por vertice). Mesmo trio de cores validado pelo skill dataviz que o
// JurosChart ja usa (--s-juros/--s-frc/--s-cupom) — reaproveitado aqui
// pelo mesmo motivo: distincao "todos contra todos" com 3 series juntas.
function useSeriesSelicJuros() {
  const { dado } = usePolling(api.curvaJuros, 5000, []);
  const pontos = dado ?? [];
  return [
    {
      key: "di_1ano",
      label: "DI 1 ano (constant maturity)",
      cor: "var(--s-juros)",
      pontos: pontos.map((p) => ({ data: p.data, valor: p.di_1ano })),
    },
    {
      key: "di_2anos",
      label: "DI 2 anos (constant maturity)",
      cor: "var(--s-frc)",
      pontos: pontos.map((p) => ({ data: p.data, valor: p.di_2anos })),
    },
    {
      key: "selic_meta",
      label: "Selic Meta (Copom)",
      cor: "var(--s-cupom)",
      pontos: pontos.map((p) => ({ data: p.data, valor: p.selic_meta })),
    },
  ];
}

// pedido do usuario (2026-09-23): relogio do cabecalho mostrava a hora UTC
// crua (toISOString), 3h a frente do horario real de Sao Paulo — mesma
// causa/correcao ja aplicada em QuotesTable.jsx (formatarHora): converte de
// verdade pro fuso America/Sao_Paulo via Intl, fixo independente do fuso do
// navegador de quem esta olhando a tela (Brasil nao tem horario de verao
// desde 2019, offset sempre -3h).
function useRelogioSP() {
  const [agora, setAgora] = useState(() => new Date());
  useEffect(() => {
    const id = setInterval(() => setAgora(new Date()), 1000);
    return () => clearInterval(id);
  }, []);
  return agora.toLocaleTimeString("pt-BR", {
    timeZone: "America/Sao_Paulo",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function useTelaPequena() {
  const [pequena, setPequena] = useState(
    () => typeof window !== "undefined" && window.matchMedia(TELA_PEQUENA_PX).matches
  );
  useEffect(() => {
    const mq = window.matchMedia(TELA_PEQUENA_PX);
    const ouvir = (e) => setPequena(e.matches);
    mq.addEventListener("change", ouvir);
    return () => mq.removeEventListener("change", ouvir);
  }, []);
  return pequena;
}

// mede a largura real do container (o .dashboard-canvas-viewport, que e a
// janela do navegador descontando o padding da pagina) — usada pra calcular
// a escala do canvas livre (ver comentario no topo do arquivo). ResizeObserver
// em vez de so 'resize' da window porque tambem reage a mudanca de padding/
// fonte/zoom e a entrada/saida da barra de rolagem vertical, nao so ao
// redimensionar a janela.
//
// Zoom do navegador (Ctrl +/- ou Ctrl+scroll) — 2 pedidos do usuario sobre o
// mesmo assunto:
//   1) "o layout não mudou" com o zoom -> resolvido escutando tambem
//      'resize' da window/visualViewport (ver mais abaixo).
//   2) DEPOIS disso, o usuario reparou o oposto: "o cabecalho diminui mas os
//      graficos e a tabela não" — ou seja, o canvas ATE reage ao zoom, mas
//      de um jeito que CANCELA o efeito visual do zoom nele (ver por que
//      abaixo), enquanto o texto normal (cabecalho) encolhe/cresce normal.
//
// Explicacao do porque isso acontece — e nao e bug de digitacao, e
// consequencia matematica direta do pedido anterior ("os graficos tem que
// se adaptar a janela... independente do tamanho da tela"): zoom de pagina
// (Ctrl +/-) muda quantos pixels CSS cabem na janela (dar zoom OUT aumenta
// esse numero, dar zoom IN diminui) — e o navegador renderiza esses pixels
// CSS fisicamente MAIORES ou MENORES conforme o zoom. Nosso canvas sempre
// recalcula "escala" pra ocupar 100% da largura em pixels CSS disponivel —
// entao quando o zoom aumenta o numero de pixels CSS disponiveis, o canvas
// cresce em pixels CSS pra preencher esse espaco, e o navegador desenha
// esses pixels CSS extras FISICAMENTE MENORES (por causa do proprio zoom) —
// as duas coisas se cancelam matematicamente, e o tamanho FISICO na tela do
// canvas fica sempre o mesmo, zoom nenhum muda ele. O cabecalho (texto
// normal, sem esse recalculo) nao tem esse problema — encolhe/cresce junto
// com o zoom que nem qualquer site.
//
// Correcao: normalizar a largura medida pelo FATOR DE ZOOM atual antes de
// calcular a escala, cancelando o proprio cancelamento. window.devicePixelRatio
// e a forma pratica de detectar zoom de pagina no Chrome/Edge: ele MUDA
// proporcionalmente ao nivel de zoom (sobe quando da zoom in, desce quando
// da zoom out), enquanto fica constante quando a janela so e redimensionada
// de verdade (arrastar borda, split screen). Guarda o DPR do primeiro
// render como "linha de base" (nao precisa ser exatamente 100% de zoom, so
// precisa ser um ponto fixo de referencia) e usa fatorZoom = dpr_atual /
// dpr_base pra desfazer o efeito do zoom na medicao. Resultado: o canvas so
// recalcula escala quando a janela MESMO muda de tamanho — zoom passa a
// encolher/crescer ele fisicamente junto com o resto da pagina, como
// qualquer conteudo normal (inclusive os rotulos ficam maiores/menores pra
// ler, o que zoom deveria fazer).
// pedido do usuario: "em 50% de zoom a tela treme" — causa raiz era a barra
// de rolagem vertical da pagina entrando/saindo (ver scrollbar-gutter:stable
// em tokens.css, que resolve isso de vez). Esse EPSILON aqui e so uma
// segunda trava de seguranca: ignora mudanca de largura menor que 1px (ruido
// de arredondamento de subpixel do proprio calculo de fatorZoom, que pode
// nao bater exatamente com um numero inteiro) — sem isso, um valor tipo
// 1179.6 vs 1179.4 dispara um re-render (setLargura) que nao muda nada
// visualmente mas custa um recalculo de escala inteiro a toa a cada
// callback do ResizeObserver.
const EPSILON_LARGURA_PX = 1;

function useLarguraContainer() {
  const ref = useRef(null);
  const [largura, setLargura] = useState(0);
  const dprBase = useRef(typeof window !== "undefined" ? window.devicePixelRatio || 1 : 1);

  useEffect(() => {
    const el = ref.current;
    if (!el) return undefined;

    const medir = () => {
      const dprAtual = window.devicePixelRatio || 1;
      const fatorZoom = dprAtual / dprBase.current;
      // largura "normalizada": desfaz o efeito do zoom (ver comentario
      // acima) — muda so quando a janela de verdade muda de tamanho
      const novaLargura = el.getBoundingClientRect().width * fatorZoom;
      setLargura((atual) => (Math.abs(atual - novaLargura) < EPSILON_LARGURA_PX ? atual : novaLargura));
    };

    const observer = new ResizeObserver(medir);
    observer.observe(el);

    window.addEventListener("resize", medir);
    window.visualViewport?.addEventListener("resize", medir);

    medir(); // primeira medicao — nao espera o 1o callback do observer

    return () => {
      observer.disconnect();
      window.removeEventListener("resize", medir);
      window.visualViewport?.removeEventListener("resize", medir);
    };
  }, []);

  return [ref, largura];
}

export default function App() {
  const seriesJuros = useSeriesJuros();
  // mesmo esquema de cor em todo mundo: Last = azul (--s-juros), Session
  // Close (da mesma raiz) = a cor "propria" do card (FRC laranja, Cupom
  // aqua) — os 3 vem do mesmo trio validado pelo skill dataviz (ver
  // comentario no topo do JurosChart.jsx).
  const seriesFrc = useSeriesCurvaSimples("frc", "FRC", "var(--s-juros)", "var(--s-frc)");
  const seriesCupom = useSeriesCurvaSimples("cupom-inflacao", "DAP", "var(--s-juros)", "var(--s-cupom)");
  const { series: seriesTrio, spread: spreadTrio } = useSeriesTrio();
  const seriesYeldCurve = useSeriesYeldCurve();
  const dadosDp = useDesviosDp();
  const dadosAmplitude = useAmplitude();
  const dadosNoticias = useNoticias();
  const dolarTeorico = useDolarTeorico();
  const seriesSelicJuros = useSeriesSelicJuros();
  const { dado: cotacoesInt, erro: erroCotacoes } = usePolling(api.lastInt, 1000, []);
  // cotacao + variacao intradiaria das 7 magnificas (Apple/Microsoft/
  // Alphabet/Amazon/Nvidia/Meta/Tesla) — pedido do usuario 2026-09-26
  // ("coloque as 7 magnificas na grade de cotacao tambem, e sua variacao
  // intradiaria"). Poll bem mais espacado que o lastInt (1min vs 1s): o
  // dado so muda quando o Service do mt5stock atualiza o parquet
  // (~15-20min por volta completa, ver magnificas.py), tick a tick como
  // a corretora internacional nao rola aqui.
  const { dado: cotacoesMagnificas } = usePolling(api.lastMagnificas, 60000, []);
  // cotacao + variacao intradiaria de EWZ/EEM (sentimento de risco
  // Brasil/emergentes) — pedido do usuario 2026-09-29 ("colocar o EWZ
  // no Risk indice", ampliado pra EEM). Mesmo poll espacado de
  // cotacoesMagnificas, mesmo motivo (sentimento_em.py le o mesmo
  // parquet de MTF do mt5stock).
  const { dado: cotacoesSentimentoEm } = usePolling(api.lastSentimentoEm, 60000, []);
  // Decimo passo (2026-09-29, mesmo dia, pedido do usuario): a separacao
  // acima ("separar o po da areia" — grade Indice/Dolar x grade Nasdaq)
  // ainda deixava a composicao de cada grade HARDCODED aqui
  // (`cotacoesIndiceDolar` vs `cotacoes`, ATIVOS_EXTRA_INFO no topo do
  // arquivo). Pedido novo: um "controller" declarativo, no config.json,
  // pra quando uma view nova for criada o sistema ja saber quais ativos
  // entram na grade dela — sem editar este arquivo. Vem de
  // GET /api/grades-cotacoes (config.json -> ativos_referencia_extra +
  // grades_cotacoes, api_server.py 1.21.0/client.js 1.3.0).
  // feedsCotacoes e o dicionario dos feeds ja pollados que uma view pode
  // declarar (last_int, magnificas, sentimento_em — este ultimo,
  // 2026-09-29, foi o primeiro feed novo desde que o mecanismo existe:
  // so precisou de uma entrada aqui + uma linha no config.json, sem
  // mexer em mais nada). Enquanto o primeiro poll do /api/grades-cotacoes nao
  // respondeu, cotacoesDaView cai no fallback ["last_int"] — mesmo
  // comportamento que a grade Indice/Dolar ja tinha antes desta
  // mudanca, entao nao ha regressao visivel nesse instante inicial.
  const { dado: registroViews } = usePolling(api.gradesCotacoes, 60000, []);
  const feedsCotacoes = {
    last_int: cotacoesInt ?? [],
    magnificas: cotacoesMagnificas ?? [],
    sentimento_em: cotacoesSentimentoEm ?? [],
  };
  function cotacoesDaView(chave) {
    const feeds = registroViews?.[chave]?.feeds ?? ["last_int"];
    return feeds.flatMap((nomeFeed) => feedsCotacoes[nomeFeed] ?? []);
  }
  const cotacoesIndiceDolar = cotacoesDaView("principal");
  const { dado: pesoMercado } = usePolling(api.pesoMercado, 60000, []);
  // vies direcional (indice/dolar + ativos extra, ex.: usatec) — processo
  // continuo (vies_direcional.py), poll mais rapido que pesoMercado pra
  // acompanhar o placar/gatilho de entrada quase em tempo real.
  const { dado: viesDirecional } = usePolling(api.viesDirecional, 5000, []);
  // qual view esta ativa: "principal" (Indice/Dolar, layout de canvas livre
  // de sempre) ou a chave de um ativo extra (ex.: "usatec") — deriva do que
  // ja chegou em viesDirecional, entao o menu cresce sozinho conforme o
  // backend for ganhando ativos novos em ativos_referencia_extra. Nome de
  // exibicao e feeds de cada view vem de registroViews (ver acima) — uma
  // view nova nao precisa de nenhuma linha aqui, so de entradas em
  // config.json (ativos_referencia_extra + grades_cotacoes).
  const [viewAtiva, setViewAtiva] = useState("principal");
  const viewsExtra = Object.keys(viesDirecional ?? {}).filter((chave) => !CHAVES_VIES_NAO_ATIVO.has(chave));
  const relogio = useRelogioSP();
  const telaPequena = useTelaPequena();
  const { paineis, definirPainel, trazerParaFrente, salvar, status } = useLayout(LAYOUT_PADRAO);
  const { config: configVisual, definir: definirConfigVisual, status: statusConfigVisual } =
    useConfigVisual(CONFIG_VISUAL_PADRAO);
  const [viewportRef, larguraViewport] = useLarguraContainer();
  // pedido do usuario: "tem como fazer uma setinha no menu? clicamos nela e
  // escolhemos o ativo, tipo pais de origem em formulario" — trocado o menu
  // de botoes lado a lado por um dropdown (botao com o nome da view atual +
  // seta, clica e abre uma lista). menuAtivosRef fecha a lista ao clicar
  // fora (fora do proprio menu).
  const [menuAtivosAberto, setMenuAtivosAberto] = useState(false);
  const menuAtivosRef = useRef(null);

  useEffect(() => {
    if (!menuAtivosAberto) return undefined;
    function aoClicarFora(e) {
      if (menuAtivosRef.current && !menuAtivosRef.current.contains(e.target)) {
        setMenuAtivosAberto(false);
      }
    }
    document.addEventListener("mousedown", aoClicarFora);
    return () => document.removeEventListener("mousedown", aoClicarFora);
  }, [menuAtivosAberto]);

  const rotuloViewAtiva =
    viewAtiva === "principal" ? "Índice/Dólar" : registroViews?.[viewAtiva]?.nome ?? viewAtiva;

  // zoom manual continuo no canvas via Ctrl+scroll (ou pinch de trackpad,
  // que o navegador reporta como wheel + ctrlKey) — pedido do usuario
  // comparando com o HTS Trader: la o zoom e continuo (redimensiona janela
  // OS-level), aqui o Ctrl+scroll caia direto no zoom NATIVO da pagina do
  // Chrome/Edge, que so pula entre degraus fixos (50%, 67%, 75%...). A
  // interceptacao abaixo com preventDefault() impede o navegador de fazer
  // seu proprio zoom discreto e deixa a gente aplicar um fator continuo,
  // multiplicado em cima da "escala" (auto-fit ou fixo=1) mais abaixo — ver
  // "escalaFinal". So ativo em modo desktop (sem canvas livre no
  // celular/tablet, ver telaPequena acima) — { passive: false } no listener
  // nativo e necessario porque preventDefault() dentro de um onWheel do
  // React nao funciona (o React registra esse listener como passive).
  const [zoomManual, setZoomManual] = useState(1);
  const ZOOM_MANUAL_MIN = 0.4;
  const ZOOM_MANUAL_MAX = 2.5;

  useEffect(() => {
    const el = viewportRef.current;
    if (!el || telaPequena) return undefined;

    function aoRolar(e) {
      if (!e.ctrlKey) return; // scroll normal (sem ctrl) continua rolando a pagina, sem mexer no zoom
      e.preventDefault();
      const fator = Math.exp(-e.deltaY * 0.0015); // continuo: cada "tick" da roda muda um pouco, nao pula degrau
      setZoomManual((atual) => Math.min(ZOOM_MANUAL_MAX, Math.max(ZOOM_MANUAL_MIN, atual * fator)));
    }

    el.addEventListener("wheel", aoRolar, { passive: false });
    return () => el.removeEventListener("wheel", aoRolar);
  }, [telaPequena, viewportRef]);

  // canvas cresce pra sempre caber todo painel, mesmo que o usuario arraste
  // um pra bem longe — evita cortar/clipar uma janela fora da area visivel
  // (so importa no modo desktop; em tela pequena nem existe canvas livre).
  // Esse tamanho e a largura/altura LOGICA do arranjo — o que aparece na
  // tela e ela multiplicada pela escala (calculada logo abaixo).
  //
  // "arrastando" + o useEffect abaixo (em vez de um useMemo direto em cima
  // de "paineis"): pedido do usuario: "quando estou mexendo nos boxes
  // aumenta ou diminui o zoom, acho que não é normal né?" — um useMemo comum
  // recalcularia isso a CADA pixel de mousemove (onChange do Panel.jsx
  // dispara a cada frame do arrasto), entao redimensionar UM grafico maior
  // fazia o bounding box de TODOS os paineis crescer e a escala do canvas
  // INTEIRO encolher em tempo real — parecia um zoom saindo do controle
  // enquanto voce so queria mexer numa caixa. Agora o calculo so RODA DE
  // VERDADE quando "arrastando" esta false — durante o arrasto, o tamanho
  // fica CONGELADO no que era antes de comecar, e so atualiza (de uma vez,
  // limpo) quando o Panel.jsx avisa que o mouse soltou (onArrastoFim).
  const [arrastando, setArrastando] = useState(false);
  const [tamanhoCanvas, setTamanhoCanvas] = useState(() => calcularTamanhoCanvas(LAYOUT_PADRAO));

  // pedido do usuario ("tenta outra configuração", depois de reclamar que o
  // auto-fit deixava tudo "enorme" mesmo com o navegador em 25% de zoom):
  // MODO_CANVAS troca entre as duas estrategias de tamanho do canvas —
  // "auto-fit" (a de sempre, ver comentario grande no topo do arquivo) versus
  // "fixo" (canvas em tamanho REAL de px, sem nenhum transform:scale()
  // calculado — obedece o zoom do navegador do jeito normal, como qualquer
  // site: zoom in aumenta fisicamente, zoom out diminui). Trade-off do modo
  // fixo: pode sobrar espaço vazio na janela (arranjo menor que a tela) ou
  // pedir rolagem horizontal (arranjo maior que a tela), dependendo do
  // tamanho da janela/zoom no momento — ao contrario do auto-fit, que nunca
  // sobra nem falta espaço mas também nunca deixa o zoom mudar o tamanho
  // físico de verdade. Fácil de reverter: só trocar esta constante.
  const MODO_CANVAS = "fixo"; // "fixo" | "auto-fit"

  useEffect(() => {
    if (arrastando) return; // congelado — ver comentario acima
    const ids = viewAtiva === "principal" ? IDS_PAINEIS_PRINCIPAL : idsPaineisExtra(viewAtiva);
    const paineisDaView = {};
    ids.forEach((id) => {
      if (paineis[id]) paineisDaView[id] = paineis[id];
    });
    setTamanhoCanvas(calcularTamanhoCanvas(paineisDaView));
  }, [paineis, arrastando, viewAtiva]);

  // escala = quanto o canvas logico precisa encolher ou esticar pra ocupar
  // EXATAMENTE a largura disponivel agora. 1 antes da 1a medicao
  // (larguraViewport ainda 0) pra nao piscar um flash gigante/minusculo.
  // No modo "fixo" (ver MODO_CANVAS acima) a escala e sempre 1 — o canvas
  // desenha no tamanho real dele, sem recalculo nenhum, e quem manda no
  // tamanho fisico na tela e o zoom do navegador, como em qualquer site.
  const escala =
    MODO_CANVAS === "fixo" ? 1 : larguraViewport > 0 ? larguraViewport / tamanhoCanvas.width : 1;

  const escalaFinal = escala * zoomManual;

  const graficos = (
    <>
      <Panel
        id="painel-juros"
        title="Curva de Juros — DI1"
        layout={paineis["painel-juros"]}
        onChange={definirPainel}
        onFront={trazerParaFrente}
        onArrastoInicio={() => setArrastando(true)}
        onArrastoFim={() => setArrastando(false)}
        fixo={telaPequena}
        escala={escalaFinal}
      >
        {({ width }) => (
          <JurosChart
            titulo="Curva de Juros — DI1"
            series={seriesJuros}
            larguraDisponivel={width}
            mostrarPontos={configVisual.mostrarPontos}
            espessuraLinha={1}
            brilho
          />
        )}
      </Panel>

      <Panel
        id="painel-frc"
        title="Curva FRC"
        layout={paineis["painel-frc"]}
        onChange={definirPainel}
        onFront={trazerParaFrente}
        onArrastoInicio={() => setArrastando(true)}
        onArrastoFim={() => setArrastando(false)}
        fixo={telaPequena}
        escala={escalaFinal}
      >
        {({ width }) => (
          <JurosChart
            titulo="Curva FRC"
            series={seriesFrc}
            larguraDisponivel={width}
            mostrarPontos={configVisual.mostrarPontos}
          />
        )}
      </Panel>

      <Panel
        id="painel-cupom"
        title="Curva de Cupom de Inflação — DAP"
        layout={paineis["painel-cupom"]}
        onChange={definirPainel}
        onFront={trazerParaFrente}
        onArrastoInicio={() => setArrastando(true)}
        onArrastoFim={() => setArrastando(false)}
        fixo={telaPequena}
        escala={escalaFinal}
      >
        {({ width }) => (
          <JurosChart
            titulo="Curva de Cupom de Inflação — DAP"
            series={seriesCupom}
            larguraDisponivel={width}
            mostrarPontos={configVisual.mostrarPontos}
          />
        )}
      </Panel>

      <Panel
        id="painel-cotacoes"
        title="Risk Índice — Mercado Internacional (corretora internacional)"
        layout={paineis["painel-cotacoes"]}
        onChange={definirPainel}
        onFront={trazerParaFrente}
        onArrastoInicio={() => setArrastando(true)}
        onArrastoFim={() => setArrastando(false)}
        fixo={telaPequena}
        escala={escalaFinal}
      >
        {({ width }) => (
          <QuotesTable
            cotacoes={cotacoesIndiceDolar}
            pesos={pesoMercado ?? {}}
            larguraDisponivel={width}
            grupo="indice"
            simboloFuturo="Indice"
          />
        )}
      </Panel>

      {/* pedido do usuario: "montar duas tabelas, Risk Índice e Risk Dólar,
          uma do lado da outra, configuração de um card clonada pro outro
          mudando só os ativos" — mesmo Panel/QuotesTable do card acima,
          só troca id/title/grupo (ver separarIndiceDolar em
          QuotesTable.jsx). */}
      <Panel
        id="painel-cotacoes-dolar"
        title="Risk Dólar — Mercado Internacional (corretora internacional)"
        layout={paineis["painel-cotacoes-dolar"]}
        onChange={definirPainel}
        onFront={trazerParaFrente}
        onArrastoInicio={() => setArrastando(true)}
        onArrastoFim={() => setArrastando(false)}
        fixo={telaPequena}
        escala={escalaFinal}
      >
        {({ width }) => (
          <QuotesTable
            cotacoes={cotacoesIndiceDolar}
            pesos={pesoMercado ?? {}}
            larguraDisponivel={width}
            grupo="dolar"
            simboloFuturo="Dolar"
          />
        )}
      </Panel>

      <Panel
        id="painel-trio"
        title='Trio — DDI (real) × FRC (teórico)'
        layout={paineis["painel-trio"]}
        onChange={definirPainel}
        onFront={trazerParaFrente}
        onArrastoInicio={() => setArrastando(true)}
        onArrastoFim={() => setArrastando(false)}
        fixo={telaPequena}
        escala={escalaFinal}
      >
        {({ width }) => (
          <JurosChart
            titulo="Trio — DDI (real) × FRC (teórico)"
            series={seriesTrio}
            larguraDisponivel={width}
            footer={
              spreadTrio.length > 0 && (
                <div className="trio-spread-footer">
                  {spreadTrio.map((p) => (
                    <span
                      key={p.rotulo}
                      className={`trio-spread-item mono ${
                        Math.abs(p.valor) >= LIMIAR_SPREAD_ALERTA ? "trio-spread-item--alerta" : ""
                      }`}
                    >
                      {p.rotulo}: {p.valor >= 0 ? "+" : ""}
                      {p.valor.toFixed(3).replace(".", ",")}pp
                    </span>
                  ))}
                </div>
              )
            }
          />
        )}
      </Panel>

      <Panel
        id="painel-dolar-teorico"
        title="Dólar Teórico"
        layout={paineis["painel-dolar-teorico"]}
        onChange={definirPainel}
        onFront={trazerParaFrente}
        onArrastoInicio={() => setArrastando(true)}
        onArrastoFim={() => setArrastando(false)}
        fixo={telaPequena}
        escala={escalaFinal}
      >
        <DolarTeoricoCard dado={dolarTeorico} />
      </Panel>

      <Panel
        id="painel-selic-juros"
        title="Juros de Prazo Constante × Selic"
        layout={paineis["painel-selic-juros"]}
        onChange={definirPainel}
        onFront={trazerParaFrente}
        onArrastoInicio={() => setArrastando(true)}
        onArrastoFim={() => setArrastando(false)}
        fixo={telaPequena}
        escala={escalaFinal}
      >
        {({ width }) => (
          <SelicJurosChart
            titulo="Juros de Prazo Constante × Selic"
            series={seriesSelicJuros}
            larguraDisponivel={width}
          />
        )}
      </Panel>

      <Panel
        id="painel-yeldcurve"
        title="Curva de Juros — Treasurys (EUA)"
        layout={paineis["painel-yeldcurve"]}
        onChange={definirPainel}
        onFront={trazerParaFrente}
        onArrastoInicio={() => setArrastando(true)}
        onArrastoFim={() => setArrastando(false)}
        fixo={telaPequena}
        escala={escalaFinal}
      >
        {({ width }) => (
          <YeldCurveChart
            titulo="Curva de Juros — Treasurys (EUA)"
            series={seriesYeldCurve}
            larguraDisponivel={width}
          />
        )}
      </Panel>

      <Panel
        id="painel-dp"
        title="Projeção de Desvios — MACD/ATR/IFR (MTF)"
        layout={paineis["painel-dp"]}
        onChange={definirPainel}
        onFront={trazerParaFrente}
        onArrastoInicio={() => setArrastando(true)}
        onArrastoFim={() => setArrastando(false)}
        fixo={telaPequena}
        escala={escalaFinal}
      >
        {() => (
          <DesviosPainel dados={dadosDp} />
        )}
      </Panel>

      <Panel
        id="painel-noticias"
        title="Notícias"
        layout={paineis["painel-noticias"]}
        onChange={definirPainel}
        onFront={trazerParaFrente}
        onArrastoInicio={() => setArrastando(true)}
        onArrastoFim={() => setArrastando(false)}
        fixo={telaPequena}
        escala={escalaFinal}
      >
        {() => (
          <NoticiasPainel dados={dadosNoticias} />
        )}
      </Panel>

      <Panel
        id="painel-modelo-swing-indice"
        title="Cenário de Swing — Índice (Indice)"
        layout={paineis["painel-modelo-swing-indice"]}
        onChange={definirPainel}
        onFront={trazerParaFrente}
        onArrastoInicio={() => setArrastando(true)}
        onArrastoFim={() => setArrastando(false)}
        fixo={telaPequena}
        escala={escalaFinal}
      >
        {() => (
          <ModeloSwingCard raiz="Indice" />
        )}
      </Panel>

      <Panel
        id="painel-modelo-swing-dolar"
        title="Cenário de Swing — Dólar (Dolar)"
        layout={paineis["painel-modelo-swing-dolar"]}
        onChange={definirPainel}
        onFront={trazerParaFrente}
        onArrastoInicio={() => setArrastando(true)}
        onArrastoFim={() => setArrastando(false)}
        fixo={telaPequena}
        escala={escalaFinal}
      >
        {() => (
          <ModeloSwingCard raiz="Dolar" />
        )}
      </Panel>

      <Panel
        id="painel-causalidade-legenda"
        title="Legenda — Causalidade de Granger"
        layout={paineis["painel-causalidade-legenda"]}
        onChange={definirPainel}
        onFront={trazerParaFrente}
        onArrastoInicio={() => setArrastando(true)}
        onArrastoFim={() => setArrastando(false)}
        fixo={telaPequena}
        escala={escalaFinal}
      >
        <CausalidadeLegenda />
      </Panel>
    </>
  );

  // pedido do usuario: "quero mover a grade como podemos mover na view do
  // indice e do dolar" — a view de um ativo extra usa o MESMO tipo de
  // painel arrastavel/redimensionavel (Panel.jsx) que a view principal.
  // Cotacoes ranqueadas (parametrizada por viewAtiva, ver QuotesTable
  // grupo={viewAtiva}) + os 3 paineis GLOBAIS replicados a pedido do
  // usuario ("replique esses tres cards la"): Curva de Juros Treasurys
  // (EUA), Projecao de Desvios (DP) e Noticias — mesmos dados/series da
  // view principal (seriesYeldCurve/dadosDp/dadosNoticias), so entram aqui
  // de novo com id proprio pra poder ter posicao/tamanho independente.
  // Proximo ativo extra nao precisa de nenhuma linha nova aqui, so das
  // entradas em LAYOUT_PADRAO (ver comentario la) + 1 linha em
  // config.json -> ativos_referencia_extra/grades_cotacoes (ver Decimo
  // passo no arquitetura.md). (O painel de vies direcional foi removido a
  // pedido do usuario, ver comentario no LAYOUT_PADRAO acima.)
  const nomeViewAtiva = registroViews?.[viewAtiva]?.nome ?? viewAtiva;
  const cotacoesViewAtual = cotacoesDaView(viewAtiva);
  const graficosExtra = viewAtiva !== "principal" && (
    <>
      <Panel
        id={`painel-cotacoes-${viewAtiva}`}
        title={`Risk ${nomeViewAtiva}`}
        layout={paineis[`painel-cotacoes-${viewAtiva}`]}
        onChange={definirPainel}
        onFront={trazerParaFrente}
        onArrastoInicio={() => setArrastando(true)}
        onArrastoFim={() => setArrastando(false)}
        fixo={telaPequena}
        escala={escalaFinal}
      >
        {({ width }) => (
          <QuotesTable
            cotacoes={cotacoesViewAtual}
            pesos={pesoMercado ?? {}}
            larguraDisponivel={width}
            grupo={viewAtiva}
            titulo={`Risk ${nomeViewAtiva}`}
            simboloFuturo={registroViews?.[viewAtiva]?.raiz}
          />
        )}
      </Panel>

      <Panel
        id={`painel-yeldcurve-${viewAtiva}`}
        title="Curva de Juros — Treasurys (EUA)"
        layout={paineis[`painel-yeldcurve-${viewAtiva}`]}
        onChange={definirPainel}
        onFront={trazerParaFrente}
        onArrastoInicio={() => setArrastando(true)}
        onArrastoFim={() => setArrastando(false)}
        fixo={telaPequena}
        escala={escalaFinal}
      >
        {({ width }) => (
          <YeldCurveChart
            titulo="Curva de Juros — Treasurys (EUA)"
            series={seriesYeldCurve}
            larguraDisponivel={width}
          />
        )}
      </Panel>

      <Panel
        id={`painel-dp-${viewAtiva}`}
        title="Projeção de Desvios — MACD/ATR/IFR (MTF)"
        layout={paineis[`painel-dp-${viewAtiva}`]}
        onChange={definirPainel}
        onFront={trazerParaFrente}
        onArrastoInicio={() => setArrastando(true)}
        onArrastoFim={() => setArrastando(false)}
        fixo={telaPequena}
        escala={escalaFinal}
      >
        {() => (
          // pedido do usuario: "tem que apresentar os valores apenas para
          // nasdaq" — dado (dadosDp) e o MESMO global de sempre, so filtra
          // qual(is) ativo(s) mostrar via a raiz de registroViews (ver
          // DesviosPainel.jsx prop `ativos`).
          <DesviosPainel dados={dadosDp} ativos={[registroViews?.[viewAtiva]?.raiz]} />
        )}
      </Panel>

      <Panel
        id={`painel-noticias-${viewAtiva}`}
        title="Notícias"
        layout={paineis[`painel-noticias-${viewAtiva}`]}
        onChange={definirPainel}
        onFront={trazerParaFrente}
        onArrastoInicio={() => setArrastando(true)}
        onArrastoFim={() => setArrastando(false)}
        fixo={telaPequena}
        escala={escalaFinal}
      >
        {() => (
          <NoticiasPainel dados={dadosNoticias} />
        )}
      </Panel>

      <Panel
        id={`painel-modelo-swing-${viewAtiva}`}
        title={`Cenário de Swing — ${nomeViewAtiva}`}
        layout={paineis[`painel-modelo-swing-${viewAtiva}`]}
        onChange={definirPainel}
        onFront={trazerParaFrente}
        onArrastoInicio={() => setArrastando(true)}
        onArrastoFim={() => setArrastando(false)}
        fixo={telaPequena}
        escala={escalaFinal}
      >
        {() => (
          <ModeloSwingCard raiz={registroViews?.[viewAtiva]?.raiz} />
        )}
      </Panel>

      {viewAtiva === "usatec" && (
        <>
          {/* card de juros americanos (TLT/IEF/SHY) — SO na view usatec, ver
              comentario em LAYOUT_PADRAO/idsPaineisExtra. Mesmo componente
              DesviosPainel de sempre, so que lendo config.json ->
              dp_ativos_extra em vez de ativos_referencia_extra (ver dp.py
              1.3.0 pro motivo dessa fonte separada). */}
          <Panel
            id="painel-juros-usatec"
            title="Juros Americanos — Treasury (TLT/IEF/SHY)"
            layout={paineis["painel-juros-usatec"]}
            onChange={definirPainel}
            onFront={trazerParaFrente}
            onArrastoInicio={() => setArrastando(true)}
            onArrastoFim={() => setArrastando(false)}
            fixo={telaPequena}
            escala={escalaFinal}
          >
            {() => (
              <DesviosPainel dados={dadosDp} ativos={["TLT", "IEF", "SHY"]} />
            )}
          </Panel>

          {/* amplitude de mercado (advance/decline + novas maximas/minimas)
              das 100 acoes do Nasdaq-100 — SO na view usatec, ver
              comentario em LAYOUT_PADRAO/idsPaineisExtra/amplitude.py. */}
          <Panel
            id="painel-amplitude-usatec"
            title="Amplitude de Mercado — Nasdaq-100"
            layout={paineis["painel-amplitude-usatec"]}
            onChange={definirPainel}
            onFront={trazerParaFrente}
            onArrastoInicio={() => setArrastando(true)}
            onArrastoFim={() => setArrastando(false)}
            fixo={telaPequena}
            escala={escalaFinal}
          >
            {() => (
              <AmplitudePainel dados={dadosAmplitude} universo="nasdaq" />
            )}
          </Panel>
        </>
      )}
    </>
  );

  const graficosView = viewAtiva === "principal" ? graficos : graficosExtra;

  return (
    <div className="viz-root">
      {/* pedido do usuario: tirar o titulo/subtitulo do cabecalho
          ("Painel INDICE / DOLAR — curvas & cotações" / "corretora nacional · corretora internacional") —
          fica so a faixa de chips (status, relogio, config). */}
      <div className="painel-header">
        <div className="painel-chips">
          {/* chip "Juros (DI1), FRC, ... dados reais" removido do cabecalho —
              pedido do usuario ("tira isso aqui da pagina"). */}
          <span className="chip">
            <span className={`dot ${erroCotacoes ? "dot--erro" : ""}`}></span>
            <span className="mono">{relogio}</span>
          </span>
          {viewsExtra.length > 0 && (
            <div className="menu-ativos" ref={menuAtivosRef}>
              <button
                type="button"
                className="menu-ativos-atual"
                onClick={() => setMenuAtivosAberto((atual) => !atual)}
              >
                {rotuloViewAtiva}
                <span className="menu-ativos-seta">{menuAtivosAberto ? "▴" : "▾"}</span>
              </button>
              {menuAtivosAberto && (
                <div className="menu-ativos-lista">
                  <button
                    type="button"
                    className={`menu-ativos-item ${viewAtiva === "principal" ? "menu-ativos-item--ativo" : ""}`}
                    onClick={() => {
                      setViewAtiva("principal");
                      setMenuAtivosAberto(false);
                    }}
                  >
                    Índice/Dólar
                  </button>
                  {viewsExtra.map((chave) => (
                    <button
                      key={chave}
                      type="button"
                      className={`menu-ativos-item ${viewAtiva === chave ? "menu-ativos-item--ativo" : ""}`}
                      onClick={() => {
                        setViewAtiva(chave);
                        setMenuAtivosAberto(false);
                      }}
                    >
                      {registroViews?.[chave]?.nome ?? chave}
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}
          {/* checkbox "Mostrar pontos" removido do cabecalho — pedido do
              usuario ("acho desnecessario"). O default (mostrarPontos:false,
              ver CONFIG_VISUAL_PADRAO) continua valendo por baixo, so nao
              tem mais toggle visivel pra ligar. Facil de trazer de volta:
              ver App.jsx.bak-antes-remover-mostrarpontos. */}
          {!telaPequena && (
            <button
              type="button"
              className="botao-salvar-layout"
              onClick={salvar}
              disabled={status === "salvando"}
            >
              {status === "idle" ? "Salvar layout" : ROTULO_STATUS[status]}
            </button>
          )}
        </div>
      </div>

      {/* pedido do usuario: "quero mover a grade como podemos mover na
          view do indice e do dolar" — a view de um ativo extra (ex.:
          Nasdaq/usatec) usa exatamente o MESMO canvas livre/Panel.jsx que a
          view principal, so trocando qual JSX entra (graficosView, ver
          acima) — arrastar/redimensionar/zoom funcionam identico nas duas. */}
      {telaPequena ? (
        <div className="dashboard-mobile">{graficosView}</div>
      ) : (
        <div className="dashboard-canvas-viewport" ref={viewportRef}>
          {/* wrapper com o tamanho JA escalado — e ele quem ocupa espaco de
              verdade no fluxo da pagina (altura da rolagem, etc.); o
              transform:scale() no filho so afeta o DESENHO, nao o tamanho
              que o layout externo enxerga, entao precisa desse wrapper com
              a largura/altura final pra nao sobrar/faltar espaco.
              overflow:visible enquanto "arrastando" — o tamanho do canvas
              fica CONGELADO durante o arrasto (ver comentario em
              tamanhoCanvas), entao um redimensionamento que ainda nao
              "assentou" pode passar um pouco do tamanho antigo por um
              instante; visible evita cortar esse pedacinho ate o
              recalculo final (no mouseup) ajustar tudo de novo. */}
          <div
            className="dashboard-canvas-escala"
            style={{
              width: tamanhoCanvas.width * escalaFinal,
              height: tamanhoCanvas.height * escalaFinal,
              overflow: arrastando ? "visible" : "hidden",
            }}
          >
            <div
              className="dashboard-canvas"
              style={{
                width: tamanhoCanvas.width,
                height: tamanhoCanvas.height,
                transform: `scale(${escalaFinal})`,
              }}
            >
              {graficosView}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
