// JurosChart.jsx — grafico da curva de juros (DI1), com 3 linhas:
//   - last (DI1): preco corrente de cada contrato da curva
//   - session close (DI1): fechamento oficial de cada contrato
//   - session close (OC1): fechamento oficial da raiz OC1 (que nunca tem
//     last nem candle D1 — so existe via session_close, ver docstring do
//     last_nac.py/vigente.py)
//
// Eixo X: vertice de vencimento de cada contrato, rotulo "MM/AAAA" (decodificado
// no backend a partir do ticker B3, ex "DI1V26" -> "10/2026"). Eixo Y: taxa,
// com grade a cada 10 basis points (0,10 p.p.) — limite superior = maior taxa
// entre as 3 series, limite inferior = menor taxa (sem padding artificial).
//
// Cada serie pode ter vertices que as outras nao tem (curva esparsa — "um mes
// sem contrato e so um buraco", conforme o vigente.py) — o eixo X e a UNIAO
// de todos os vertices das 3 series, ordenado cronologicamente; cada linha so
// desenha nos vertices onde ELA tem dado (conecta reto por cima de um buraco
// se houver).
//
// Paleta: reaproveita os 3 primeiros slots categoricos do design system
// (--s-juros azul, --s-frc laranja, --s-cupom aqua) — esse trio e o unico
// validado pelo skill dataviz pra distincao "todos contra todos" (nao so
// adjacente), que e exatamente o caso aqui (3 linhas simultaneas no mesmo
// grafico). Cada linha vem com um rotulo direto na legenda, entao a cor
// nunca carrega o significado sozinha.
//
// Redimensionamento (painel livre, ver Panel.jsx): a LARGURA sempre foi um
// numero de px de verdade — igual "larguraDisponivel" (a largura de desenho
// real do card, vinda do Panel.jsx). A ALTURA, ate 2026-09-24, era diferente:
// so uma escala LOGICA do viewBox (fixa em 260) — o svg usava height="100%"
// e preserveAspectRatio="none", entao o navegador ESTICAVA o desenho pra
// caber na altura real do painel. Bug reportado pelo usuario: como o texto
// do eixo (font-size) mora no MESMO sistema de coordenadas do viewBox, ele
// esticava junto — card mais alto = letra do eixo Y maior, em vez de mais
// pontos de preco. Corrigido: agora a altura tambem e medida em px reais
// (ResizeObserver no .juros-scroll, ver scrollRef/callback ref abaixo) e o viewBox usa
// essa altura REAL, 1:1, sem preserveAspectRatio nenhum — nada mais estica.
// A fonte do eixo (tokens.css) fica fixa; quem cresce com o card e o numero
// de linhas de grade (ver PX_POR_LINHA_GRID) — "aumentar o numero de pontos
// de preco e nao aumentar a distancia", exatamente como pedido.
//
// Pedido do usuario: "o grafico tem que se adaptar ao card que ele esta" —
// o svg NUNCA e desenhado maior que o card pra depois rolar (sem barra de
// rolagem, sem vazamento); quem se adapta e o CONTEUDO do grafico (passoX,
// angulo do rotulo, quantas linhas de grade e quantos rotulos aparecem —
// ver abaixo).
//
// Escala X — rotulo acompanha o tamanho do grafico (pedido do usuario: "a
// escala x dos graficos deve acompanhar o tamanho do grafico tambem... a
// distancia entre as datas se aproxima e vai ficando vertical conforme o
// tamanho do grafico"). O angulo de rotacao e CALCULADO a cada render a
// partir do espaco real por vertice (passoX): espaco de sobra -> rotulo
// quase deitado; espaco apertado -> rotulo gira progressivamente ate ficar
// 100% vertical (90°), que e o "footprint" horizontal minimo que um texto
// pode ocupar. Se AINDA ASSIM o card for estreito demais pra caber um
// rotulo vertical entre cada vertice (curva longa, tipo 30 vertices de
// DI1, num card bem pequeno), a gente RAREIA o texto do eixo (mostra 1 a
// cada N rotulos, ver "pulo" abaixo) em vez de rolar ou vazar — a curva em
// si (linha + pontos) sempre desenha TODOS os vertices, so o texto que
// pode pular alguns.

import { useCallback, useMemo, useRef, useState } from "react";

const PAD_LEFT = 150; // pedido do usuario 2026-09-24: "a escala tem que andar um pouco
// mais para dentro do card" — a fonte do eixo Y subiu de 15px pra 30px (ver
// .juros-eixo-label em tokens.css) e o rotulo (textAnchor="end", cresce pra
// esquerda a partir de PAD_LEFT-8) comecou a estourar fora do card com o
// PAD_LEFT antigo de 54. Aumentado pra dar espaco de sobra ao texto maior.
const PAD_RIGHT = 16;
const PAD_TOP = 16;
const PAD_BOTTOM_BASE = 26; // pedido do usuario 2026-09-24: "encolheram dentro
// dos cards" — reservar sempre o PIOR CASO (rotulo 100% vertical, ~160px) fixo
// desperdicava area de plotagem toda vez que o rotulo NAO estava girado a
// 90° (o caso mais comum). Agora o PAD_BOTTOM e DINAMICO — ver padBottom no
// corpo do componente, calculado a partir do angulo REAL de cada render
// (footprintRotuloVertical) — e essa constante e so a folga fixa (o gap
// baseY+16 do texto ate a linha do eixo, mais uma margem pro descend).
const ALTURA_FALLBACK = 260; // usado so ANTES do 1o ResizeObserver medir a altura real do card (ver alturaSvg no componente)

// grade Y adaptativa (era um passo FIXO de 0,10pp = 10 basis points): bug
// visto no grafico de Cupom de Inflacao — DAP quando um vertice veio com
// valor fora da curva (session_close de um contrato registrado como 3,5
// quando os vizinhos estao todos entre 6,0 e 7,7): o span (max-min) esticou
// pra 4,21 pontos, e com passo fixo de 0,1 isso vira 42 LINHAS DE GRADE
// espremidas na altura do card — na tela parece um "zebrado"/bloco denso
// (rotulos do eixo Y se atropelando tambem), nao um grafico.
// 1a correcao: em vez de passo fixo, mirar num NUMERO fixo de linhas
// (DESEJADO_LINHAS_GRID = 7), com o passo arredondado pro numero "redondo"
// mais proximo (1, 2 ou 5 vezes uma potencia de 10).
// 2a correcao (2026-09-24, pedido do usuario — ver comentario de
// redimensionamento acima): mirar num NUMERO FIXO de linhas nao bastava,
// porque a altura do svg ainda esticava (viewBox logico) — um card mais
// alto continuava com as mesmas 7 linhas, so que MAIORES e mais espacadas
// (e a fonte junto). Agora que a altura do svg e a altura REAL em px (ver
// alturaSvg/ResizeObserver no componente), o alvo virou um ESPACAMENTO fixo
// em px reais entre linhas (PX_POR_LINHA_GRID) — card mais alto = MAIS
// linhas (mais pontos de preco), sempre com a mesma distancia entre elas e
// a mesma fonte. O numero de linhas alvo (linhasAlvo, calculado no
// componente a partir de plotH) e passado pra ca em vez de vir de uma
// constante — pra um range estreito tipo DI1 numa altura tipica isso da
// perto do mesmo resultado visual de antes; pra um range largo (bug de
// dado, ou curva que varia bastante) o passo ainda cresce sozinho e a grade
// nunca fica mais densa que o previsto.
const PX_POR_LINHA_GRID = 48; // pedido do usuario 2026-09-24: "a escala do eixo Y quando
// diminuimos o tamanho do grafico ela fica com os precos encavalado um em cima do
// outro" — 32px era o respiro certo pra fonte de 15px, mas o eixo Y foi pra 30px
// (.juros-eixo-label em tokens.css) e quase nao sobrava espaco entre um rotulo e
// outro (30px de letra numa grade de 32px). Subido pra dar folga de verdade. // espacamento alvo entre linhas de grade, em PX REAIS — ajuste aqui se quiser mais/menos denso (nao precisa mexer em mais nada)
const PASSO_GRID_MINIMO = 0.01; // piso — nunca deixa o passo sumir/virar 0 num span quase nulo
const SPAN_MINIMO = 0.1; // fallback de span quando a curva e completamente chata (yMax === yMin)

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

// geometria do rotulo "MM/AAAA" (7 caracteres, fonte mono 30px — ver
// .juros-eixo-label-x no tokens.css, atualizado 2026-09-24 junto com o
// eixo Y: "agora a escala X com 30px tambem") usada pra calcular o angulo
// de rotacao: o "footprint" horizontal de um texto rotacionado por um
// angulo (em radianos, 0 = deitado, 90° = em pe) e textWidth*cos(angulo) +
// textHeight*sin(angulo) (a projecao da caixa do texto no eixo X). Esse
// FONTE_TAM tem que acompanhar o font-size real do CSS, senao o angulo
// calculado fica curto e o rotulo estoura/sobrepoe.
const FONTE_TAM = 30;
const CHAR_LARGURA = FONTE_TAM * 0.62; // aproximacao de largura de char pra fonte mono
const ROTULO_TEXTO_LEN = 7; // "MM/AAAA"
const LARGURA_ROTULO = ROTULO_TEXTO_LEN * CHAR_LARGURA;
const ALTURA_ROTULO = FONTE_TAM;
const GAP_ROTULO = 4; // respiro minimo entre rotulos vizinhos

// piso absoluto de espaco por vertice: o footprint de um rotulo 100%
// vertical (a altura da fonte) mais um respirinho — bem menor que os 56px
// fixos de antes, entao a maioria das curvas de DI1 (~30 vertices) cabe sem
// nunca precisar do scroll horizontal.
const PASSO_X_MIN = ALTURA_ROTULO + GAP_ROTULO;

// piso absoluto do grafico inteiro (painel muito estreito ou largura ainda
// nao medida) — antes era 480px (calibrado pro passo fixo de 56px/vertice);
// como o passo minimo caiu bastante com a rotacao dinamica, esse piso tambem
// cai, senao ele sozinho forcaria scroll num painel que ja caberia soh com
// os rotulos verticais. 240 = PAD_LEFT+PAD_RIGHT + uma area de desenho minima
// razoavel (~170px) pra nao esmagar o grafico quando a largura ainda nao foi
// medida (primeiro render do ResizeObserver, ver App.jsx).
const LARGURA_MIN = 240;

// pico da funcao footprint (onde ela para de crescer e comeca a cair) —
// busca binaria comeca dali pra sempre pegar o ramo decrescente
const ANGULO_PICO = Math.atan2(ALTURA_ROTULO, LARGURA_ROTULO);

function footprintRotulo(anguloRad) {
  return LARGURA_ROTULO * Math.cos(anguloRad) + ALTURA_ROTULO * Math.sin(anguloRad);
}

// footprint VERTICAL do rotulo rotacionado (quanto de altura ele realmente
// ocupa embaixo do eixo no angulo atual) — a mesma projecao de
// footprintRotulo, so trocando seno/cosseno de lugar: deitado (0°) ocupa so
// ALTURA_ROTULO (a altura do texto); em pe (90°) ocupa LARGURA_ROTULO
// inteiro (o pior caso, usado antes como PAD_BOTTOM fixo).
function footprintRotuloVertical(anguloRad) {
  return LARGURA_ROTULO * Math.sin(anguloRad) + ALTURA_ROTULO * Math.cos(anguloRad);
}

// maior espaco disponivel por vertice (passoX) -> menor angulo de rotacao
// necessario (0 = deitado); menor espaco -> angulo cresce ate 90° (vertical).
function anguloParaCaber(passoX) {
  if (!Number.isFinite(passoX) || passoX >= LARGURA_ROTULO) return 0; // sobra espaco, rotulo deitado
  if (passoX <= ALTURA_ROTULO) return Math.PI / 2; // nem vertical cabe direito — fica 90° e deixa o scroll cobrir o resto
  let baixo = ANGULO_PICO;
  let alto = Math.PI / 2;
  for (let i = 0; i < 20; i++) {
    const meio = (baixo + alto) / 2;
    if (footprintRotulo(meio) > passoX) baixo = meio;
    else alto = meio;
  }
  return alto;
}

function parseRotulo(rotulo) {
  const [mes, ano] = rotulo.split("/").map(Number);
  return { ano, mes };
}

function ordenarRotulos(rotulos) {
  return [...rotulos].sort((a, b) => {
    const pa = parseRotulo(a);
    const pb = parseRotulo(b);
    return pa.ano - pb.ano || pa.mes - pb.mes;
  });
}

function montarEixoX(series) {
  const vistos = new Set();
  series.forEach((s) => (s.pontos ?? []).forEach((p) => vistos.add(p.rotulo)));
  return ordenarRotulos([...vistos]);
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

// "footer" (opcional): node extra desenhado dentro do card, depois do svg —
// pedido do usuario pro card do Trio (DDI x FRC): alem das 2 linhas, mostrar
// o spread numerico por vertice embaixo do grafico. Generico de proposito
// (nao especifico do Trio) pra qualquer card futuro que precise de um resumo
// assim, sem duplicar o componente inteiro so por isso.
export default function JurosChart({ titulo, series, larguraDisponivel, footer, espessuraLinha = 1.5, brilho = false }) {
  const eixoX = useMemo(() => montarEixoX(series), [series]);
  const todosValores = useMemo(
    () => series.flatMap((s) => (s.pontos ?? []).map((p) => p.valor)),
    [series]
  );

  // altura REAL do card em px (nao a logica 260 de antes) — pedido do
  // usuario 2026-09-24: "mesmo que eu aumente ou diminua os graficos as
  // letras da escala tem que permanecer na mesma configuracao". Mede o
  // .juros-scroll (o proprio container do svg, ja sem padding/titulo/
  // legenda) direto pelo navegador, mesmo espirito do ResizeObserver que
  // o App.jsx ja usa pro canvas inteiro (ver comentario de redimensionamento
  // acima). ALTURA_FALLBACK cobre so o instante antes da 1a medida.
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
          sem dados — confira se o main.py (last_nac.py + vigente.py) já rodou pelo menos uma volta
        </div>
        {footer}
      </div>
    );
  }

  const yMin = Math.min(...todosValores);
  const yMax = Math.max(...todosValores);
  const span = yMax - yMin || SPAN_MINIMO;
  const altura = alturaSvg || ALTURA_FALLBACK;

  // largura do grafico = largura REAL do card, sempre — pedido do usuario:
  // "o grafico tem que se adaptar ao card que ele esta" (nao o contrario).
  // Antes, se o numero de vertices exigisse mais espaco que o card tinha, o
  // svg era desenhado MAIOR que o card e o .juros-scroll (CSS) ligava uma
  // barra de rolagem horizontal — o card ficava fixo e o grafico "vazava"
  // pra fora dele. Agora nunca mais: largura = a largura disponivel do
  // card, ponto final. Quem absorve o aperto e o passoX (fica menor) e o
  // angulo do rotulo (gira mais, ate 90°) — e se mesmo assim nao tiver
  // espaco pra TODOS os rotulos em pe, a gente rareia (mostra 1 a cada N),
  // nunca deixa vazar. LARGURA_MIN so entra antes da 1a medida do card.
  const largura = larguraDisponivel || LARGURA_MIN;
  const plotW = largura - PAD_LEFT - PAD_RIGHT;
  const passoX = eixoX.length > 1 ? plotW / (eixoX.length - 1) : plotW;

  // angulo unico pra todos os rotulos (o espaco por vertice e uniforme) —
  // recalculado a cada render, entao acompanha ao vivo o arrasto/resize do
  // painel (ver Panel.jsx -> larguraDisponivel). Espaco sobrando -> deitado
  // (anchor "middle", sem giro, mais facil de ler); espaco apertado -> gira
  // progressivamente ate 90° (anchor "end", pendurado a partir do tick).
  // Vem ANTES do PAD_BOTTOM/plotH de proposito: o padBottom dinamico
  // depende do angulo, entao o angulo tem que estar calculado primeiro
  // (o angulo em si so depende de passoX/plotW, nunca de altura/plotH).
  const anguloRad = anguloParaCaber(passoX);
  const anguloGraus = (anguloRad * 180) / Math.PI;
  const rotuloDeitado = anguloGraus < 12;

  // PAD_BOTTOM dinamico — reserva so o espaco que o rotulo REALMENTE ocupa
  // no angulo atual (ver footprintRotuloVertical e o comentario em
  // PAD_BOTTOM_BASE acima), nao sempre o pior caso de 90°.
  const padBottom = PAD_BOTTOM_BASE + footprintRotuloVertical(anguloRad);
  const plotH = altura - PAD_TOP - padBottom;
  const linhasAlvoY = Math.max(2, Math.round(plotH / PX_POR_LINHA_GRID));

  const indicePorRotulo = new Map(eixoX.map((rotulo, i) => [rotulo, i]));
  const xDoRotulo = (rotulo) => PAD_LEFT + passoX * indicePorRotulo.get(rotulo);
  const yDoValor = (valor) => PAD_TOP + (1 - (valor - yMin) / span) * plotH;
  const baseY = altura - padBottom;

  const gradeY = valoresGradeY(yMin, yMax, linhasAlvoY);

  // mesmo 100% vertical, cada rotulo ainda ocupa ~PASSO_X_MIN de largura —
  // se o card for tao estreito que nem isso caiba entre vertices vizinhos,
  // em vez de deixar sobrepor (ou vazar), mostra 1 a cada "pulo" rotulos
  // (a curva/linha continua desenhando TODOS os vertices normalmente, so o
  // texto do eixo que rareia).
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
            if (i % pulo !== 0) return null; // rareado — ver comentario do "pulo" acima
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
            const pontosOrdenados = [...(s.pontos ?? [])].sort(
              (a, b) => indicePorRotulo.get(a.rotulo) - indicePorRotulo.get(b.rotulo)
            );
            const pts = pontosOrdenados
              .map((p) => `${xDoRotulo(p.rotulo).toFixed(1)},${yDoValor(p.valor).toFixed(1)}`)
              .join(" ");
            return (
              // so a linha — pedido do usuario: "pode tirar essas bolinhas de
              // todas as linhas do grafico ?" (sem <circle> por vertice)
              <polyline
                key={s.key}
                points={pts}
                fill="none"
                stroke={s.cor}
                strokeWidth={espessuraLinha}
                strokeLinejoin="round"
                strokeLinecap="round"
                vectorEffect="non-scaling-stroke"
                // "brilho" (pedido do usuario, so no painel DI1 por enquanto —
                // ver App.jsx): glow com a PROPRIA cor da linha (drop-shadow
                // aceita var() direto), duas camadas (perto/forte + longe/fraca)
                // pra parecer neon em vez de so um brightness() chapado.
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
