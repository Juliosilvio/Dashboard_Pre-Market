// CurveChart.jsx — SEM USO no momento (nenhum painel do App.jsx importa mais
// este componente). Quando FRC e Cupom de Inflacao ainda eram so amostra
// ilustrativa (1 serie, sem session close), FRC/Cupom usavam este
// componente pelo resumo "headline + delta" (numero grande + seta). Pedido
// do usuario ("podemos adicionar aos outros graficos os contratos que neles
// faltam e session close e last?") fez FRC/Cupom passarem a mostrar 2 series
// cada (Last + Session Close) — o App.jsx passou a reusar o JurosChart pra
// esses paineis tambem (ja resolvia multi-serie + rotulo adaptativo + largura
// = card, ver JurosChart.jsx), entao esse arquivo ficou orfao. Nao foi
// apagado (mesma cautela do Resizable.jsx — sem certeza de que
// delete/rm funciona de forma confiavel neste ambiente); se algum grafico
// voltar a precisar so de 1 serie com resumo headline+delta, e so importar
// de novo.
//
// Redimensionamento (painel livre, ver Panel.jsx): VIEW_W/VIEW_H sao so a
// escala LOGICA do viewBox — o svg usa width/height 100% (classe
// curve-chart-svg, ver tokens.css) e preserveAspectRatio="none", entao ele
// estica sozinho pro tamanho real do painel (o navegador faz a conta, sem
// js recalculando coordenada nenhuma).

import { useMemo } from "react";

const VIEW_W = 300;
const VIEW_H = 110;
const PAD_X = 10;
const PAD_TOP = 14;
const PAD_BOTTOM = 10;

function calcularCoordenadas(pontos) {
  const valores = pontos.map((p) => p.valor);
  const min = Math.min(...valores);
  const max = Math.max(...valores);
  const span = max - min || 1; // evita divisao por zero quando todo mundo tem o mesmo valor
  const plotW = VIEW_W - PAD_X * 2;
  const plotH = VIEW_H - PAD_TOP - PAD_BOTTOM;
  const passo = pontos.length > 1 ? plotW / (pontos.length - 1) : 0;

  return pontos.map((p, i) => ({
    ...p,
    x: PAD_X + passo * i,
    y: PAD_TOP + (1 - (p.valor - min) / span) * plotH,
  }));
}

function formatarValor(valor) {
  return valor.toFixed(2).replace(".", ",");
}

export default function CurveChart({ titulo, cor, pontos, amostra = false, mostrarPontos = false }) {
  const coords = useMemo(() => calcularCoordenadas(pontos ?? []), [pontos]);

  if (!pontos || pontos.length === 0) {
    return (
      <div className="chart-card chart-card--empty">
        <div className="chart-title">{titulo}</div>
        <div className="chart-empty-msg">sem dados</div>
      </div>
    );
  }

  const primeiro = coords[0];
  const ultimo = coords[coords.length - 1];
  const delta = ultimo.valor - primeiro.valor;
  const deltaClasse = delta >= 0 ? "delta-up" : "delta-down";
  const seta = delta >= 0 ? "▲" : "▼";
  const pontosPolyline = coords.map((c) => `${c.x.toFixed(1)},${c.y.toFixed(1)}`).join(" ");
  const meioY = (PAD_TOP + (VIEW_H - PAD_BOTTOM)) / 2;

  return (
    <div className="chart-card">
      <div className="chart-title">
        {titulo}
        {amostra && <span className="chip chip--muted" style={{ marginLeft: 8 }}>amostra</span>}
      </div>
      <div className="chart-headline">
        <span className="mono chart-headline-value">{formatarValor(ultimo.valor)}%</span>
        <span className={`mono chart-delta ${deltaClasse}`}>
          {seta} {formatarValor(Math.abs(delta))} p.p.
        </span>
      </div>
      <svg
        viewBox={`0 0 ${VIEW_W} ${VIEW_H}`}
        preserveAspectRatio="none"
        className="curve-chart-svg"
      >
        <line x1={PAD_X} y1={PAD_TOP} x2={VIEW_W - PAD_X} y2={PAD_TOP} stroke="var(--grid)" strokeWidth="1" />
        <line x1={PAD_X} y1={meioY} x2={VIEW_W - PAD_X} y2={meioY} stroke="var(--grid)" strokeWidth="1" />
        <line
          x1={PAD_X}
          y1={VIEW_H - PAD_BOTTOM}
          x2={VIEW_W - PAD_X}
          y2={VIEW_H - PAD_BOTTOM}
          stroke="var(--axis)"
          strokeWidth="1"
        />
        <polyline
          points={pontosPolyline}
          fill="none"
          stroke={cor}
          strokeWidth="1.5"
          strokeLinejoin="round"
          strokeLinecap="round"
          vectorEffect="non-scaling-stroke"
        />
        {/* "mostrarPontos" — mesma config visual persistida do JurosChart
            (ver useConfigVisual.js/App.jsx); padrao false */}
        {mostrarPontos &&
          coords.map((c, i) => {
            const destaque = i === 0 || i === coords.length - 1;
            return destaque ? (
              <circle key={c.rotulo} cx={c.x} cy={c.y} r="4" fill="var(--page)" stroke={cor} strokeWidth="2" />
            ) : (
              <circle key={c.rotulo} cx={c.x} cy={c.y} r="3" fill={cor} />
            );
          })}
      </svg>
      <div className="chart-axis-labels">
        {coords.map((c) => (
          <span key={c.rotulo} className="mono chart-axis-label">
            {c.rotulo}
          </span>
        ))}
      </div>
    </div>
  );
}
