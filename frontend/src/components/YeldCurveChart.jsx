// YeldCurveChart.jsx — grafico da curva de juros dos treasurys americanos
// (yeldcurve.py, le o xlsx do Excel a cada 5min), com 2 linhas:
//   - Atual: yield_pct de cada vencimento (ultimo preco/leitura)
//   - Fechamento D-1: prev_pct de cada vencimento (fechamento do pregao
//     anterior) — pedido do usuario 2026-09-23 (confirmando o significado
//     dos campos): "o ultimo preco equivale a este yield_pct e o
//     fechamento D1 equivale a este prev_pct"
//
// Praticamente uma copia do JurosChart.jsx (mesma grade Y adaptativa, mesmo
// calculo de angulo/rarefacao do rotulo do eixo X, mesma adaptacao de
// largura ao card — ver comentarios detalhados la) - a UNICA diferenca real
// e o eixo X: o JurosChart ordena vertices por DATA (rotulo "MM/AAAA",
// parseRotulo/ordenarRotulos), enquanto aqui a ordem e uma lista FIXA de
// vencimentos (1M, 2M, 3M, 4M, 6M, 1Y, 2Y, 3Y, 5Y, 7Y, 10Y, 20Y, 30Y — a
// mesma ordem de ORDEM_VENCIMENTOS no yeldcurve.py), ja que o rotulo aqui
// nao e uma data (nao daria pra reusar parseRotulo sem quebrar). Nao virou
// um parametro genérico no JurosChart de proposito (2026-09-23): a logica
// de ordenacao por data e o "footprint" de rotulo tipo "MM/AAAA" (7
// caracteres) sao bem especificos de curva B3 — mais simples manter os dois
// componentes separados (pouca duplicacao, ~330 linhas) do que abstrair uma
// interface de ordenacao configuravel pra um segundo uso so.
//
// Cores: "Atual" usa var(--s-juros) (azul) — mesma cor de "Last"/"valor
// corrente" em todos os outros cards do dashboard (DI1, FRC, Cupom). Segue o mesmo
// padrao: azul = valor vivo, cor 2 (aqui var(--s-frc), laranja) = referencia
// anterior — igual "Session Close" nos outros cards.
//
// Redimensionamento: identico ao JurosChart (ver comentario la) — largura
// SEMPRE = largura real do card (Panel.jsx). Altura tambem passou a ser
// medida REAL em px via ResizeObserver (2026-09-24, mesmo fix do JurosChart:
// viewBox fixo + preserveAspectRatio "none" fazia a fonte do eixo esticar
// junto com o card) — sem mais escala logica que estica via CSS.

import { useCallback, useMemo, useRef, useState } from "react";

const PAD_LEFT = 150; // pedido do usuario 2026-09-24 (mesmo ajuste do JurosChart):
// fonte do eixo Y foi pra 30px (.juros-eixo-label em tokens.css) — o rotulo
// (textAnchor="end", cresce pra esquerda a partir de PAD_LEFT-8) estourava o
// card com o PAD_LEFT antigo de 54, e ainda precisa de espaco extra pra nao
// colidir com o primeiro rotulo do eixo X.
const PAD_RIGHT = 16;
const PAD_TOP = 16;
const PAD_BOTTOM_BASE = 26; // pedido do usuario 2026-09-24: "encolheram dentro
// dos cards" — reservar sempre o PIOR CASO (rotulo 100% vertical) fixo
// desperdicava area de plotagem toda vez que o rotulo NAO estava girado a
// 90° (o caso mais comum). Agora o PAD_BOTTOM e DINAMICO — ver padBottom no
// corpo do componente, calculado a partir do angulo REAL de cada render
// (footprintRotuloVertical) — e essa constante e so a folga fixa (o gap
// baseY+16 do texto ate a linha do eixo, mais uma margem pro descend).
const ALTURA_FALLBACK = 260; // usado so ANTES do 1o ResizeObserver medir a altura real do card

// ordem fixa dos vencimentos — mesma lista/ordem de ORDEM_VENCIMENTOS no
// backend (yeldcurve.py). So entram no eixo os que realmente aparecem em
// pelo menos uma serie (curva pode vir parcial numa leitura com falha).
const ORDEM_VENCIMENTOS = ["1M", "2M", "3M", "4M", "6M", "1Y", "2Y", "3Y", "5Y", "7Y", "10Y", "20Y", "30Y"];

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

// geometria do rotulo pro calculo do angulo de rotacao — ver JurosChart pro
// raciocinio completo. ROTULO_TEXTO_LEN menor aqui (3 = "10Y"/"20Y"/"30Y",
// o maior rotulo da lista) porque o texto e bem mais curto que "MM/AAAA".
const FONTE_TAM = 30; // pedido do usuario 2026-09-24: escala X foi pra 30px
// (.juros-eixo-label-x em tokens.css) — precisa acompanhar aqui, senao o
// angulo de rotacao calculado fica curto e o rotulo estoura/sobrepoe.
const CHAR_LARGURA = FONTE_TAM * 0.62;
const ROTULO_TEXTO_LEN = 3;
const LARGURA_ROTULO = ROTULO_TEXTO_LEN * CHAR_LARGURA;
const ALTURA_ROTULO = FONTE_TAM;
const GAP_ROTULO = 4;
const PASSO_X_MIN = ALTURA_ROTULO + GAP_ROTULO;
const LARGURA_MIN = 240;
const ANGULO_PICO = Math.atan2(ALTURA_ROTULO, LARGURA_ROTULO);

function footprintRotulo(anguloRad) {
  return LARGURA_ROTULO * Math.cos(anguloRad) + ALTURA_ROTULO * Math.sin(anguloRad);
}

// footprint VERTICAL do rotulo rotacionado — mesma projecao de
// footprintRotulo, so trocando seno/cosseno: deitado (0°) ocupa so
// ALTURA_ROTULO; em pe (90°) ocupa LARGURA_ROTULO inteiro (o pior caso,
// usado antes como PAD_BOTTOM fixo).
function footprintRotuloVertical(anguloRad) {
  return LARGURA_ROTULO * Math.sin(anguloRad) + ALTURA_ROTULO * Math.cos(anguloRad);
}

function anguloParaCaber(passoX) {
  if (!Number.isFinite(passoX) || passoX >= LARGURA_ROTULO) return 0;
  if (passoX <= ALTURA_ROTULO) return Math.PI / 2;
  let baixo = ANGULO_PICO;
  let alto = Math.PI / 2;
  for (let i = 0; i < 20; i++) {
    const meio = (baixo + alto) / 2;
    if (footprintRotulo(meio) > passoX) baixo = meio;
    else alto = meio;
  }
  return alto;
}

// eixo X = subconjunto de ORDEM_VENCIMENTOS que aparece em alguma serie,
// na ordem fixa (nao ordenado por data — ver comentario do topo).
function montarEixoX(series) {
  const vistos = new Set();
  series.forEach((s) => (s.pontos ?? []).forEach((p) => vistos.add(p.rotulo)));
  return ORDEM_VENCIMENTOS.filter((v) => vistos.has(v));
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

export default function YeldCurveChart({ titulo, series, larguraDisponivel, footer, espessuraLinha = 1.5, brilho = false }) {
  const eixoX = useMemo(() => montarEixoX(series), [series]);
  const todosValores = useMemo(
    () => series.flatMap((s) => (s.pontos ?? []).map((p) => p.valor)),
    [series]
  );

  // altura REAL do card em px (nao a logica ALTURA_FALLBACK) — mesmo fix do
  // JurosChart.jsx (ver comentario de redimensionamento no topo do arquivo).
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

  if (eixoX.length === 0 || todosValores.length === 0) {
    return (
      <div className="chart-card chart-card--empty">
        <div className="chart-title">{titulo}</div>
        <div className="chart-empty-msg">
          sem dados — confira se o yeldcurve.py rodou (e se o Excel com yeldcurve.xlsx está aberto com o Power Query atualizando)
        </div>
        {footer}
      </div>
    );
  }

  const yMin = Math.min(...todosValores);
  const yMax = Math.max(...todosValores);
  const span = yMax - yMin || SPAN_MINIMO;

  const largura = larguraDisponivel || LARGURA_MIN;
  const altura = alturaSvg || ALTURA_FALLBACK;
  const plotW = largura - PAD_LEFT - PAD_RIGHT;
  const passoX = eixoX.length > 1 ? plotW / (eixoX.length - 1) : plotW;

  // angulo primeiro (so depende de passoX/plotW) — o padBottom dinamico
  // abaixo depende dele, entao tem que vir antes do plotH/baseY.
  const anguloRad = anguloParaCaber(passoX);
  const anguloGraus = (anguloRad * 180) / Math.PI;
  const rotuloDeitado = anguloGraus < 12;

  // PAD_BOTTOM dinamico — reserva so o espaco que o rotulo REALMENTE ocupa
  // no angulo atual (ver footprintRotuloVertical e PAD_BOTTOM_BASE acima).
  const padBottom = PAD_BOTTOM_BASE + footprintRotuloVertical(anguloRad);
  const plotH = altura - PAD_TOP - padBottom;
  const linhasAlvoY = Math.max(2, Math.round(plotH / PX_POR_LINHA_GRID));

  const indicePorRotulo = new Map(eixoX.map((rotulo, i) => [rotulo, i]));
  const xDoRotulo = (rotulo) => PAD_LEFT + passoX * indicePorRotulo.get(rotulo);
  const yDoValor = (valor) => PAD_TOP + (1 - (valor - yMin) / span) * plotH;
  const baseY = altura - padBottom;

  const gradeY = valoresGradeY(yMin, yMax, linhasAlvoY);

  const pulo = passoX > 0 ? Math.max(1, Math.ceil(PASSO_X_MIN / passoX)) : 1;

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

          {eixoX.map((rotulo, i) => {
            if (i % pulo !== 0) return null;
            const x = xDoRotulo(rotulo);
            const y = baseY + 16;
            return (
              <text
                key={rotulo}
                x={x}
                y={y}
                textAnchor={rotuloDeitado ? "middle" : "end"}
                className="mono juros-eixo-label juros-eixo-label-x"
                transform={rotuloDeitado ? undefined : `rotate(-${anguloGraus.toFixed(1)} ${x} ${y})`}
              >
                {rotulo}
              </text>
            );
          })}

          {series.map((s) => {
            const pontosOrdenados = [...(s.pontos ?? [])]
              .filter((p) => indicePorRotulo.has(p.rotulo))
              .sort((a, b) => indicePorRotulo.get(a.rotulo) - indicePorRotulo.get(b.rotulo));
            const pts = pontosOrdenados
              .map((p) => `${xDoRotulo(p.rotulo).toFixed(1)},${yDoValor(p.valor).toFixed(1)}`)
              .join(" ");
            return (
              <polyline
                key={s.key}
                points={pts}
                fill="none"
                stroke={s.cor}
                strokeWidth={espessuraLinha}
                strokeLinejoin="round"
                strokeLinecap="round"
                vectorEffect="non-scaling-stroke"
                style={brilho ? { filter: `drop-shadow(0 0 2px ${s.cor}) drop-shadow(0 0 6px ${s.cor})` } : undefined}
              />
            );
          })}
        </svg>
      </div>
      {footer}
    </div>
  );
}
