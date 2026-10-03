// AmplitudePainel.jsx — amplitude de mercado (advance/decline + novas
// maximas/minimas), lido de GET /api/amplitude (double buffer que
// amplitude.py grava continuamente — ver docstring do amplitude.py).
//
// Por enquanto so o universo "nasdaq" tem raizes configuradas em
// config.json -> amplitude_universos (as 100 acoes do Nasdaq-100,
// coletadas via mt5stock/historico.py — ver ExportadorMt5Stock.mq5).
// "indice" (Ibovespa) fica de fora ate o usuario definir a fonte das
// acoes da B3 a vista (ADR so cobre uma fatia pequena e enviesada).
//
// Uma linha por timeframe (M15 a W1, ordem fixa TF_ORDEM), colunas:
// avancos/declinios, novas maximas/minimas, % de avanco e o indice de
// amplitude ((avancos-declinios)/total*100 — positivo = alta ampla,
// negativo = queda ampla, perto de zero = mercado dividido). Cor da
// coluna Amplitude segue o mesmo padrao de Variacao da QuotesTable:
// delta-up (verde) positivo, delta-down (vermelho) negativo.

const TF_ORDEM = ["M15", "M30", "H1", "H4", "D1", "W1"];

function fmtInt(v) {
  return v == null || Number.isNaN(v) ? "--" : v.toLocaleString("pt-BR");
}

function fmtPctAvanco(v) {
  if (v == null || Number.isNaN(v)) return "--";
  return `${v.toLocaleString("pt-BR", { minimumFractionDigits: 1, maximumFractionDigits: 1 })}%`;
}

function fmtAmplitude(v) {
  if (v == null || Number.isNaN(v)) return "--";
  const sinal = v > 0 ? "+" : "";
  return `${sinal}${v.toLocaleString("pt-BR", { minimumFractionDigits: 1, maximumFractionDigits: 1 })}%`;
}

function classeAmplitude(v) {
  if (v == null || Number.isNaN(v) || v === 0) return "";
  return v > 0 ? "delta-up" : "delta-down";
}

export default function AmplitudePainel({
  dados,
  universo = "nasdaq",
  titulo = "Amplitude de Mercado — Nasdaq-100",
}) {
  const consolidado = dados?.consolidado ?? [];
  const porTf = Object.fromEntries(
    consolidado.filter((item) => item.universo === universo).map((item) => [item.tf, item])
  );

  const linhasComDado = TF_ORDEM.map((tf) => porTf[tf]).filter(Boolean);

  if (linhasComDado.length === 0) {
    return (
      <div className="chart-card chart-card--empty">
        <div className="chart-title">{titulo}</div>
        <div className="chart-empty-msg">
          sem dados — confira se o amplitude.py já rodou pelo menos uma volta pra esse universo
        </div>
      </div>
    );
  }

  // subtitulo: total de acoes consideradas (prefere D1, mais estavel; cai
  // pra primeira linha com dado se D1 ainda nao tiver historico suficiente)
  const totalConsiderados = (porTf["D1"] ?? linhasComDado[0]).total_considerados;

  return (
    <div className="chart-card quotes-card">
      <div className="quotes-header">
        <span className="chart-title">{titulo}</span>
        <span className="quotes-subtitle">{fmtInt(totalConsiderados)} ações consideradas</span>
      </div>
      <table>
        <thead>
          <tr>
            <th>TF</th>
            <th className="num">Avanços</th>
            <th className="num">Declínios</th>
            <th className="num">Novas Máx</th>
            <th className="num">Novas Mín</th>
            <th className="num">% Avanço</th>
            <th className="num">Amplitude</th>
          </tr>
        </thead>
        <tbody>
          {TF_ORDEM.map((tf) => {
            const item = porTf[tf];
            if (!item) {
              return (
                <tr key={tf}>
                  <td>{tf}</td>
                  <td className="num" colSpan={6}>--</td>
                </tr>
              );
            }
            return (
              <tr key={tf}>
                <td>{tf}</td>
                <td className="num">{fmtInt(item.avancos)}</td>
                <td className="num">{fmtInt(item.declinios)}</td>
                <td className="num">{fmtInt(item.novas_maximas)}</td>
                <td className="num">{fmtInt(item.novas_minimas)}</td>
                <td className="num">{fmtPctAvanco(item.pct_avanco)}</td>
                <td className={`num ${classeAmplitude(item.indice_amplitude)}`}>
                  {fmtAmplitude(item.indice_amplitude)}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
