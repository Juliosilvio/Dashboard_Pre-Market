// ViesDirecionalCard.jsx — card com o vies direcional (alta/baixa/neutro) de
// um ativo de referencia EXTRA (ex.: usatec/Nasdaq — ver
// ativos_referencia_extra em config.json), lido de GET /api/vies-direcional
// (double buffer que vies_direcional.py grava continuamente, mesmo motor
// generico que ja calcula indice/dolar — ver vies_direcional.py 1.4.0/
// api_server.py 1.14.0). Segue o mesmo padrao visual do DolarTeoricoCard:
// sem serie temporal, snapshot do "estado atual" do ativo (score/vies/
// quantos ativos do universo votaram/gatilho de entrada M5).
//
// dado = o objeto de UM ativo dentro da resposta de /api/vies-direcional,
// ex.: { score, vies, ativos_considerados, ifr_m1, ifr_m5, gatilho_entrada }.
// ifr_m1 fica sempre null pra ativos extra (so INDICE/DOLAR tem feed dedicado de
// tempo real via last_indicadores_nac.py — ver calcular_refinamento_extra()
// em vies_direcional.py, que le o IFR M5 direto do parquet do
// indicadores_mtf.py). undefined/null (endpoint ainda nao tem esse ativo —
// processo nao rodou nenhuma volta ainda pra ele, ou nome errado) vira "sem
// dados", igual o padrao do DolarTeoricoCard/JurosChart.

const OPCOES_3_CASAS = { minimumFractionDigits: 3, maximumFractionDigits: 3 };
const OPCOES_2_CASAS = { minimumFractionDigits: 2, maximumFractionDigits: 2 };

function formatar(valor, opcoes) {
  return typeof valor === "number" ? valor.toLocaleString("pt-BR", opcoes) : "--";
}

// mesma paleta delta-up/delta-down ja usada no DolarTeoricoCard (verde/
// vermelho) — "alta" puxa pra cima, "baixa" pra baixo, "neutro" fica sem cor
// (nenhuma das duas classes).
const CLASSE_VIES = {
  alta: "delta-up",
  baixa: "delta-down",
};

export default function ViesDirecionalCard({ dado, titulo = "Viés Direcional" }) {
  if (!dado) {
    return (
      <div className="chart-card chart-card--empty">
        <div className="chart-title">{titulo}</div>
        <div className="chart-empty-msg">
          sem dados — confira se o vies_direcional.py já rodou pelo menos uma volta pra esse ativo
        </div>
      </div>
    );
  }

  const classeVies = CLASSE_VIES[dado.vies] ?? "";

  return (
    <div className="chart-card">
      <div className="chart-title">{titulo}</div>
      <div className="dolar-teorico-linhas">
        <div className="dolar-teorico-linha">
          <span className="muted">Viés</span>
          <span className={`mono dolar-teorico-valor ${classeVies}`}>{(dado.vies ?? "--").toUpperCase()}</span>
        </div>
        <div className="dolar-teorico-linha">
          <span className="muted">Score</span>
          <span className={`mono dolar-teorico-valor ${classeVies}`}>{formatar(dado.score, OPCOES_3_CASAS)}</span>
        </div>
        <div className="dolar-teorico-linha">
          <span className="muted">IFR M5</span>
          <span className="mono dolar-teorico-valor">{formatar(dado.ifr_m5, OPCOES_2_CASAS)}</span>
        </div>
        <div className="dolar-teorico-linha">
          <span className="muted">Gatilho de entrada</span>
          <span className={`mono dolar-teorico-valor ${dado.gatilho_entrada ? "delta-up" : ""}`}>
            {dado.gatilho_entrada ? "SIM" : "não"}
          </span>
        </div>
      </div>
      {/* pedido do usuario: tirou o rodape com "N ativos considerados / IFR
          M1 indisponivel" — achou desnecessario, detalhe interno demais pra
          quem so quer ler o vies. */}
    </div>
  );
}
