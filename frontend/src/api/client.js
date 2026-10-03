// client.js — wrapper fino sobre fetch() pra falar com o api_server.py local
// (FastAPI, porta 8000). Nenhuma logica alem de montar a URL e tratar erro
// HTTP de forma previsivel (erro.status, erro.detail).
//
// v1.1.0 (2026-09-27) - BASE_URL deixou de ser fixo em
// "http://localhost:8000" e passou a usar o MESMO host que serviu a
// pagina (window.location.hostname). Motivo: pedido do usuario de
// compartilhar o dashboard com um colega via Tailscale (VPN) - quando o
// colega abre http://<ip-tailscale-do-Julio>:5173, o navegador DELE
// precisa buscar a API em http://<mesmo-ip>:8000, nao em "localhost"
// (que apontaria pro proprio PC dele, sem nada rodando la). Continua
// funcionando igual pro proprio Julio (window.location.hostname vira
// "localhost" quando ele abre localhost:5173 normalmente).

const BASE_URL = `http://${window.location.hostname}:8000`;

// v1.2.0 (2026-09-27) - layout e config visual passam a ser POR PESSOA.
// Antes de compartilhar via VPN so existia UM Julio usando o dashboard,
// entao um unico layout.json/config_visual.json compartilhado fazia
// sentido (ate ajudava - mesmo layout em qualquer maquina dele). Com um
// colega acessando too, isso virou problema: pedido do usuario depois de
// perceber a implicacao - "tinha que ser por pessoa" (se o colega
// clicasse 'Salvar layout', ia reescrever o layout do Julio tambem).
// Solucao: cada NAVEGADOR gera um id aleatorio uma vez (guardado no
// localStorage dele, nunca sai do navegador) e manda esse id junto em
// toda chamada de /api/layout e /api/config-visual (?cliente=<id>) - o
// backend (api_server.py 1.20.0) grava um arquivo separado por id.
// Nao usa crypto.randomUUID() puro porque essa funcao SO existe em
// "contexto seguro" (https ou localhost) - o colega acessa por IP puro
// (http://<ip-tailscale>:5173), que o navegador considera inseguro, e a
// funcao nem existe la. Por isso tem um fallback manual abaixo.
const CHAVE_CLIENTE_ID = "painel-cliente-id";

function gerarIdCliente() {
  try {
    if (window.crypto && typeof window.crypto.randomUUID === "function") {
      return window.crypto.randomUUID().replace(/-/g, "");
    }
  } catch {
    // segue pro fallback abaixo
  }
  // fallback pra contexto "inseguro" (http fora de localhost, ex.: IP da
  // VPN) - nao precisa ser criptografico, so precisa ser praticamente
  // unico por navegador
  return `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 10)}`;
}

function clienteId() {
  try {
    let id = localStorage.getItem(CHAVE_CLIENTE_ID);
    if (!id) {
      id = gerarIdCliente();
      localStorage.setItem(CHAVE_CLIENTE_ID, id);
    }
    return id;
  } catch {
    return null; // localStorage indisponivel - cai pro layout/config compartilhado (comportamento anterior a v1.2.0)
  }
}

// anexa ?cliente=<id> (ou &cliente=<id> se o path ja tiver query string) —
// so usado pelos dois endpoints que sao por pessoa (layout/config visual);
// todo o resto (cotacoes, curvas, modelo de swing etc.) continua igual
// pra todo mundo, sem cliente nenhum.
function comCliente(path) {
  const id = clienteId();
  if (!id) return path;
  const separador = path.includes("?") ? "&" : "?";
  return `${path}${separador}cliente=${encodeURIComponent(id)}`;
}

async function getJSON(path) {
  let resposta;
  try {
    resposta = await fetch(`${BASE_URL}${path}`);
  } catch (causa) {
    const erro = new Error(
      `Nao foi possivel falar com a API em ${BASE_URL} — o api_server.py esta rodando?`
    );
    erro.status = 0;
    erro.causa = causa;
    throw erro;
  }

  if (!resposta.ok) {
    const erro = new Error(`HTTP ${resposta.status} em ${path}`);
    erro.status = resposta.status;
    try {
      const corpo = await resposta.json();
      erro.detail = corpo.detail;
    } catch {
      // corpo nao era JSON, ignora — erro.detail fica undefined
    }
    throw erro;
  }

  return resposta.json();
}

// postJSON — usado pelos endpoints de escrita da API ("Salvar layout" e a
// config visual dos graficos, ver useLayout.js/useConfigVisual.js). Mesmo
// tratamento de erro do getJSON, so muda o metodo/corpo.
async function postJSON(path, corpo) {
  let resposta;
  try {
    resposta = await fetch(`${BASE_URL}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(corpo),
    });
  } catch (causa) {
    const erro = new Error(
      `Nao foi possivel falar com a API em ${BASE_URL} — o api_server.py esta rodando?`
    );
    erro.status = 0;
    erro.causa = causa;
    throw erro;
  }

  if (!resposta.ok) {
    const erro = new Error(`HTTP ${resposta.status} em ${path}`);
    erro.status = resposta.status;
    try {
      const corpoErro = await resposta.json();
      erro.detail = corpoErro.detail;
    } catch {
      // ignora
    }
    throw erro;
  }

  return resposta.json();
}

// v1.3.0 (2026-09-29) - registro declarativo de cada pagina/view do
// frontend (nome, raiz de referencia, quais feeds compoem a grade de
// cotacoes daquela pagina) - config.json -> ativos_referencia_extra +
// grades_cotacoes, servido por GET /api/grades-cotacoes (api_server.py
// 1.21.0). Pedido do usuario: "controller" pra quando uma pagina nova
// for criada o sistema ja saber quais ativos entram na grade dela, sem
// editar App.jsx - mesmo espirito do client.js 1.2.0 acima (por-cliente),
// so que aqui o dado veio do config.json, nao gerado no navegador.

// v1.4.0 (2026-09-29) - lastSentimentoEm: cotacao + variacao intradiaria
// de EWZ/EEM (sentimento de risco Brasil/emergentes) - mesmo padrao de
// lastMagnificas acima, GET /api/last/sentimento-em (api_server.py
// 1.22.0). Pedido do usuario: "colocar o EWZ no Risk indice" (ampliado
// pra EEM). Pra esses dois ativos aparecerem na grade, config.json ->
// grades_cotacoes.principal.feeds precisa incluir "sentimento_em" (ver
// App.jsx).

export const api = {
  lastNac: () => getJSON("/api/last/nac"),
  lastInt: () => getJSON("/api/last/int"),
  // cotacao + variacao intradiaria das 7 magnificas (Apple/Microsoft/
  // Alphabet/Amazon/Nvidia/Meta/Tesla) - mesmo formato de lastInt (pra
  // concatenar direto na mesma lista `cotacoes`, ver App.jsx). []
  // enquanto o magnificas.py nao tiver rodado.
  lastMagnificas: () => getJSON("/api/last/magnificas"),
  // cotacao + variacao intradiaria de EWZ/EEM (sentimento de risco
  // Brasil/emergentes) - mesmo formato de lastInt/lastMagnificas. []
  // enquanto o sentimento_em.py nao tiver rodado.
  lastSentimentoEm: () => getJSON("/api/last/sentimento-em"),
  lastMerged: () => getJSON("/api/last"),
  vigentes: () => getJSON("/api/vigentes"),
  // ver nota v1.3.0 acima. {} enquanto o config.json nao tiver a chave
  // grades_cotacoes (fallback do App.jsx cobre esse caso).
  gradesCotacoes: () => getJSON("/api/grades-cotacoes"),
  curva: (tipo) => getJSON(`/api/curvas/${tipo}`),
  // ranking de "peso" (correlacao real com Indice/Dolar) de cada ativo — usado
  // pra ordenar a tabela de cotacoes "conforme o peso no indice e no dolar"
  // (ver QuotesTable.jsx/App.jsx). {} enquanto o backend nao rodou correl.py.
  pesoMercado: () => getJSON("/api/peso-mercado"),
  // dolar futuro TEORICO (paridade DI1 x cupom FRC) x negociado (DOLAR
  // vigente, corretora nacional/B3) — ver card "Dólar Teórico" no App.jsx /
  // _dolar_teorico() no api_server.py.
  dolarTeorico: () => getJSON("/api/dolar-teorico"),
  // indice de juros de prazo constante (DI 1 ano/2 anos, interpolado da
  // curva do DI1) x Meta Selic — SERIE TEMPORAL (um ponto por dia,
  // diferente de curva() acima que e por vertice num dia so). Ver
  // curva_juros.py / SelicJurosChart.jsx. [] enquanto curva_juros.py nao
  // tiver rodado (ainda nao esta no pipeline automatico do main.py).
  curvaJuros: () => getJSON("/api/curva-juros"),
  // curva de juros dos treasurys americanos (1M-30Y) - ver
  // YeldCurveChart.jsx / /api/yeldcurve no api_server.py. [] enquanto o
  // yeldcurve.py nao tiver rodado.
  yeldcurve: () => getJSON("/api/yeldcurve"),
  // vies direcional (indice/dolar + cada ativo extra de ativos_referencia_extra
  // no config.json, ex.: usatec/Nasdaq) — le o double buffer que
  // vies_direcional.py grava continuamente (ver ViesDirecionalCard.jsx /
  // api_server.py 1.14.0). {} enquanto o vies_direcional.py nao tiver
  // rodado ainda nesta sessao.
  viesDirecional: () => getJSON("/api/vies-direcional"),
  dp: () => getJSON("/api/dp"),
  // amplitude de mercado (advance/decline + novas maximas/minimas) por
  // universo (config.json -> amplitude_universos) e timeframe - ver
  // AmplitudePainel.jsx / amplitude.py / api_server.py 1.15.0.
  // {"consolidado": []} enquanto o amplitude.py nao tiver rodado.
  amplitude: () => getJSON("/api/amplitude"),
  // manchetes em tempo real do canal publico do Telegram fonte de noticias
  // (agregador de noticias) - ver noticias.py / NoticiasPainel.jsx. [] enquanto
  // o noticias.py nao tiver rodado.
  noticias: () => getJSON("/api/noticias"),
  // primeiro modelo de "quando/a que preco" um proximo topo/fundo deve
  // ocorrer, por ativo, SOB DEMANDA (calcula na hora - ver
  // modelo_garch_swing.py / api_server.py 1.17.0, ModeloSwingCard.jsx).
  // universo() e a lista de raizes pro seletor; analisar(raiz) roda o
  // modelo pro ativo escolhido.
  modeloSwing: {
    universo: () => getJSON("/api/modelo-swing/universo"),
    analisar: (raiz) => getJSON(`/api/modelo-swing/${encodeURIComponent(raiz)}`),
  },
  layout: {
    obter: () => getJSON(comCliente("/api/layout")),
    salvar: (layout) => postJSON(comCliente("/api/layout"), layout),
  },
  // configuracoes de ESTILO do grafico (ex: mostrar/esconder pontos) —
  // separado do layout (posicao/tamanho) de proposito, ver useConfigVisual.js
  configVisual: {
    obter: () => getJSON(comCliente("/api/config-visual")),
    salvar: (config) => postJSON(comCliente("/api/config-visual"), config),
  },
};
