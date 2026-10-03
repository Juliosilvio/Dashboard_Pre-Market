// SelicJurosChart.jsx — grafico de SERIE TEMPORAL (um ponto por dia),
// diferente do JurosChart.jsx (que desenha a curva por VERTICE de
// vencimento, num dia so). Usado pro indice de juros de prazo constante
// (DI 1 ano / DI 2 anos, interpolado da curva do DI1 - ver curva_juros.py)
// comparado com a Meta Selic (dadosgov.py) ao longo do tempo — GET
// /api/curva-juros no api_server.py.
//
// Por que nao reaproveitar o JurosChart direto: o eixo X dele espera um
// rotulo categorico "MM/AAAA" por VERTICE (parseRotulo/ordenarRotulos so
// entendem mes+ano, um ponto por vertice) — aqui o eixo X e uma data REAL,
// um ponto por DIA UTIL, ~500 pontos no total. Forcar isso no JurosChart
// quebraria a ordenacao (dias do mesmo mes colidiriam) e o rotulo por
// vertice (rarear 1 rotulo a cada N vertices) nao faz sentido pra uma
// serie continua — aqui os poucos rotulos do eixo X sao escolhidos
// diretamente por posicao no tempo (N ticks igualmente espacados), nao por
// contagem de pontos.
//
// Reaproveita do design system: a mesma grade Y adaptativa do JurosChart
// (passoGradeAdaptativo — evita o mesmo bug de grade "zebrada" quando o
// range e largo) e as mesmas classes CSS (chart-card, juros-legenda,
// juros-scroll, juros-svg, juros-eixo-label) — ja genericas o bastante,
// sem precisar de nada novo no tokens.css. Paleta: mesmo trio validado
// pelo skill dataviz (--s-juros azul, --s-frc laranja, --s-cupom aqua),
// repassado pelo App.jsx na hora de montar as series (nao fixado aqui
// dentro, pra o componente continuar generico).
//
// Largura/altura: largura sempre = largura real do card vinda do
// Panel.jsx. Altura tambem passou a ser medida REAL em px via
// ResizeObserver (2026-09-24, mesmo fix do JurosChart: viewBox fixo +
// preserveAspectRatio "none" fazia a fonte do eixo esticar junto com o
// card). Como aqui os rotulos do eixo X sao poucos (ticks escolhidos por
// espaco disponivel, nunca um por ponto), nao precisa da rotacao dinamica
// do JurosChart — ticks sempre na horizontal, so a QUANTIDADE deles encolhe
// se o card for estreito.

import { useCallback, useMemo, useRef, useState } from "react";

const PAD_LEFT = 150; // pedido do usuario 2026-09-24 (mesmo ajuste do JurosChart):
// fonte do eixo Y foi pra 30px (.juros-eixo-label em tokens.css) — o rotulo
// (textAnchor="end", cresce pra esquerda a partir de PAD_LEFT-8) estourava o
// card com o PAD_LEFT antigo de 54, e ainda precisa de espaco extra pra nao
// colidir com o primeiro tick do eixo X.
const PAD_RIGHT = 16;
const PAD_TOP = 16;
const PAD_BOTTOM = 55; // sem rotacao de rotulo, mas a fonte do eixo X tambem
// foi pra 30px — o PAD_BOTTOM antigo de 32 (calibrado pra fonte de 10px)
// ficava justo demais pro texto maior.
const ALTURA_FALLBACK = 260; // usado so ANTES do 1o ResizeObserver medir a altura real do card

// grade Y adaptativa — copia exata da logica do JurosChart.jsx (mesma
// motivacao: evitar grade densa demais quando o range e largo). Mantida
// duplicada aqui de proposito (componente pequeno, sem modulo compartilhado
// ainda) em vez de importar do JurosChart — os dois arquivos continuam
// livres pra evoluir cada um do seu jeito sem acoplamento escondido.
// pedido do usuario 2026-09-24 (mesmo ajuste do JurosChart): "aumentar o
// numero de pontos de preco e nao aumentar a distancia" — a densidade da
// grade agora e um espacamento em PX fixo entre linhas, nao mais uma
// contagem fixa; painel mais alto = mais linhas, nao linhas mais afastadas.
const PX_POR_LINHA_GRID = 48; // pedido do usuario 2026-09-24: "a escala do eixo Y quando
// diminuimos o tamanho do grafico ela fica com os precos encavalado um em cima do
// outro" — 32px era o respiro certo pra fonte de 15px, mas o eixo Y foi pra 30px
// (.juros-eixo-label em tokens.css) e quase nao sobrava espaco entre um rotulo e
// outro (30px de letra numa grade de 32px). Subido pra dar folga de verdade.
const PASSO_GRID_MINIMO = 0.01;
const SPAN_MINIMO = 0.1;

function passoGradeAdaptativo(span, linhasAlvo) {
  if (!Number.isFinite(span) || span <= 0) return PASSO_GRID_MINIMO;
  const bruto = span / Math.max(1, linhasAlvo);
  const expoente = Math.floor(Math.log10(bruto));
  const base = bruto / 10 ** expoente;
  let multiplicador;
  if (base < 1.5) multiplicador = 1;
  else if (base < 3.5) multiplicador = 2;
  else if (base < 7.5) multiplicador = 5;
  else multiplicador = 10;
  return Math.max(PASSO_GRID_MINIMO, multiplicador * 10 ** expoente);
}

function valoresGradeY(min, max, linhasAlvo) {
  if (!Number.isFinite(min) || !Number.isFinite(max)) return [];
  const passo = passoGradeAdaptativo(max - min, linhasAlvo);
  const inicio = Math.ceil(min / passo) * passo;
  const valores = [];
  for (let v = inicio; v <= max + 1e-9; v += passo) {
    valores.push(Math.round(v * 1000) / 1000);
  }
  return valores;
}

// "MM/AAAA" a partir de uma data "AAAA-MM-DD" (mesmo formato de rotulo do
// JurosChart, pra manter o olho acostumado com o mesmo padrao entre cards).
function formatarMesAno(dataISO) {
  const [ano, mes] = dataISO.split("-");
  return `${mes}/${ano}`;
}

// N ticks igualmente espacados no tempo (nao por contagem de pontos — a
// serie e esparsa, ex: di_1ano so comeca a meio do periodo). ~90px por
// tick e generoso o bastante pra "MM/AAAA" nunca colidir horizontal.
const PX_POR_TICK = 90;

function escolherTicks(minTs, maxTs, plotW) {
  if (!Number.isFinite(minTs) || !Number.isFinite(maxTs) || minTs === maxTs) return [minTs].filter(Number.isFinite);
  const nTicks = Math.max(3, Math.min(8, Math.floor(plotW / PX_POR_TICK) + 1));
  const ticks = [];
  for (let i = 0; i < nTicks; i++) {
    ticks.push(minTs + ((maxTs - minTs) * i) / (nTicks - 1));
  }
  return ticks;
}

export default function SelicJurosChart({ titulo, series, larguraDisponivel }) {
  const seriesValidas = useMemo(
    () =>
      series.map((s) => ({
        ...s,
        pontos: (s.pontos ?? [])
          .filter((p) => p.valor !== null && p.valor !== undefined && Number.isFinite(p.valor))
          .map((p) => ({ ts: new Date(p.data + "T00:00:00Z").getTime(), valor: p.valor }))
          .sort((a, b) => a.ts - b.ts),
      })),
    [series]
  );

  const todosTs = useMemo(() => seriesValidas.flatMap((s) => s.pontos.map((p) => p.ts)), [seriesValidas]);
  const todosValores = useMemo(() => seriesValidas.flatMap((s) => s.pontos.map((p) => p.valor)), [seriesValidas]);

  // altura REAL do card em px (nao a logica ALTURA_FALLBACK) — mesmo fix do
  // JurosChart.jsx (ver comentario de largura/altura no topo do arquivo).
  const [alturaSvg, setAlturaSvg] = useState(0);
  const alturaObserverRef = useRef(null);
  // callback ref (nao useRef+useEffect com []) de proposito: esses graficos
  // tem um estado inicial "sem dados" que NAO renderiza a .juros-scroll (ver
  // o "if (...) return" logo abaixo) — um useEffect com [] roda so uma vez,
  // na 1a montagem, e se rodar ENQUANTO ainda esta em "sem dados" a
  // .juros-scroll nem existe ainda (scrollRef.current fica null pra sempre,
  // o ResizeObserver nunca chega a ser criado, e o grafico fica preso no
  // ALTURA_FALLBACK mesmo depois que os dados chegam). O callback ref e
  // chamado de novo toda vez que o NO DOM muda — inclusive quando o card
  // sai do "sem dados" e passa a renderizar a .juros-scroll pela 1a vez —
  // entao sempre acaba pegando o elemento real. Bug reportado pelo usuario
  // 2026-09-24: "quando aperto pra atualizar a pagina usando CTRL+F5 os
  // graficos encolhem novamente... acontecendo com todos os graficos" — um
  // F5 reinicia o componente do zero e sempre passa pelo "sem dados"
  // primeiro (a API ainda nao respondeu), o que a versao com useEffect([])
  // nao sobrevivia (via HMR do Vite o componente as vezes ja montava com
  // dado presente, mascarando o bug durante o desenvolvimento).
  const scrollRef = useCallback((el) => {
    if (alturaObserverRef.current) {
      alturaObserverRef.current.disconnect();
      alturaObserverRef.current = null;
    }
    if (!el) return;
    const observer = new ResizeObserver((entradas) => {
      const h = entradas[0]?.contentRect?.height;
      if (h) setAlturaSvg(h);
    });
    observer.observe(el);
    alturaObserverRef.current = observer;
  }, []);

  if (todosTs.length === 0) {
    return (
      <div className="chart-card chart-card--empty">
        <div className="chart-title">{titulo}</div>
        <div className="chart-empty-msg">
          sem dados — confira se o curva_juros.py já rodou pelo menos uma vez
        </div>
      </div>
    );
  }

  const tsMin = Math.min(...todosTs);
  const tsMax = Math.max(...todosTs);
  const yMin = Math.min(...todosValores);
  const yMax = Math.max(...todosValores);
  const span = yMax - yMin || SPAN_MINIMO;

  const largura = larguraDisponivel || 240;
  const altura = alturaSvg || ALTURA_FALLBACK;
  const plotW = largura - PAD_LEFT - PAD_RIGHT;
  const plotH = altura - PAD_TOP - PAD_BOTTOM;
  const linhasAlvoY = Math.max(2, Math.round(plotH / PX_POR_LINHA_GRID));

  const xDoTs = (ts) => (tsMax === tsMin ? PAD_LEFT + plotW / 2 : PAD_LEFT + ((ts - tsMin) / (tsMax - tsMin)) * plotW);
  const yDoValor = (valor) => PAD_TOP + (1 - (valor - yMin) / span) * plotH;
  const baseY = altura - PAD_BOTTOM;

  const gradeY = valoresGradeY(yMin, yMax, linhasAlvoY);
  const ticksX = escolherTicks(tsMin, tsMax, plotW);

  return (
    <div className="chart-card">
      <div className="chart-title">{titulo}</div>
      <div className="juros-legenda">
        {series.map((s) => (
          <span key={s.key} className="juros-legenda-item">
            <span className="juros-legenda-dot" style={{ background: s.cor }} />
            {s.label}
          </span>
        ))}
      </div>
      <div className="juros-scroll" ref={scrollRef}>
        <svg
          viewBox={`0 0 ${largura} ${altura}`}
          width={largura}
          height={altura}
          className="juros-svg"
        >
          {gradeY.map((v) => (
            <g key={v}>
              <line
                x1={PAD_LEFT}
                y1={yDoValor(v)}
                x2={largura - PAD_RIGHT}
                y2={yDoValor(v)}
                stroke="var(--grid)"
                strokeWidth="1"
              />
              <text
                x={PAD_LEFT - 8}
                y={yDoValor(v)}
                textAnchor="end"
                dominantBaseline="middle"
                className="mono juros-eixo-label"
              >
                {v.toFixed(2).replace(".", ",")}%
              </text>
            </g>
          ))}
          <line x1={PAD_LEFT} y1={baseY} x2={largura - PAD_RIGHT} y2={baseY} stroke="var(--axis)" strokeWidth="1" />

          {ticksX.map((ts) => {
            const x = xDoTs(ts);
            return (
              <text key={ts} x={x} y={baseY + 16} textAnchor="middle" className="mono juros-eixo-label juros-eixo-label-x">
                {formatarMesAno(new Date(ts).toISOString().slice(0, 10))}
              </text>
            );
          })}

          {seriesValidas.map((s) => {
            const pts = s.pontos.map((p) => `${xDoTs(p.ts).toFixed(1)},${yDoValor(p.valor).toFixed(1)}`).join(" ");
            return (
              <polyline
                key={s.key}
                points={pts}
                fill="none"
                stroke={s.cor}
                strokeWidth="1.5"
                strokeLinejoin="round"
                strokeLinecap="round"
                vectorEffect="non-scaling-stroke"
              />
            );
          })}
        </svg>
      </div>
    </div>
  );
}
