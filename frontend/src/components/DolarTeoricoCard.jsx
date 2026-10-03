// DolarTeoricoCard.jsx — card pequeno com o dolar futuro TEORICO (paridade
// coberta de juros: Spot(USDBRL) x DI1 / Cupom(FRC), ver _dolar_teorico() no
// api_server.py) comparado ao preco REAL negociado do DOLAR vigente (corretora nacional/
// B3). Pedido do usuario: depois de perguntar "onde o dolar deveria fechar,
// da pra saber?", pediu "quero colocar um card pequeno ja com o resultado"
// — diferente do card do Trio (JurosChart reaproveitado, grafico de linha),
// este e so numero: nao tem serie temporal nenhuma, e um snapshot do
// vertice vigente agora. Ate a 1.7.0 do api_server.py o "negociado" era o
// Dolar da corretora internacional — trocado pelo DOLAR da corretora nacional/B3 (pedido do usuario:
// "usa o dolarv26 da corretora nacional pra calcular") pra comparar exatamente no mesmo
// vertice do DI1/FRC, sem descasamento de vencimento.
//
// dado.vertice = vertice do DOLAR/DI1 (ex "10/2026"); dado.vertice_cupom =
// vertice do FRC vigente de verdade (ex "12/2026"). Ate a 1.22.0 do
// api_server.py isso era CALCULADO como "sempre 1 mes a frente do DOLAR"
// (pressuposto fixo); a 1.23.0 corrigiu um bug no vigente.py que escondia
// que o FRC as vezes anda MAIS de 1 mes a frente (2026-09-30: virou 2
// meses) — agora o card so mostra o vertice que o vigente.py realmente
// resolveu, sem assumir distancia nenhuma. Por isso o titulo mostra os
// dois vertices separados em vez de um so.
//
// dado.spot_usdbrl (desde a 1.23.0) NAO e mais o tick ao vivo do USDBRL —
// e um proxy da PTAX do Bacen (media das janelas de 10h/11h/12h/13h ja
// fechadas, horario de Brasilia — ver _ptax_proxy_usdbrl() no
// api_server.py). Pedido do usuario: o DOLAR liquida contra PTAX, entao usar
// PTAX como spot da formula bate melhor com o DI1/FRC do que um tick
// instantaneo. dado.ptax_proxy_janelas_completas mostra quantas das 4
// janelas ja entraram na media (parcial ao longo da manha, trava depois
// das 13h10 BRT).
//
// "erro" no dado (double buffer/historico ainda vazio pra algum dos
// insumos — DI1/FRC/PTAX-proxy/DOLAR — ou DOLAR sem vigente ainda) vira
// mensagem de "sem dados", igual o padrao do JurosChart, em vez de tentar
// desenhar um numero incompleto.
//
// dado.spot_estimado (desde a 1.26.0 do api_server.py) — pedido do
// usuario (2026-10-01): antes das ~10h10 BRT (nenhuma janela de PTAX de
// hoje fechou ainda), em vez de "sem dados" por ~1h toda manha, o backend
// EXTRAPOLA o ultimo PTAX real conhecido (normalmente o de ontem, 4
// janelas) pela variacao D1 do DXY (USDInd vigente) desde o fechamento de
// ontem: anterior * (1 + variacao_dxy) — ver _ptax_proxy_usdbrl_com_
// fallback() no api_server.py. Quando isso acontece, dado.spot_estimado
// vem true e dado.spot_estimado_anterior/spot_estimado_variacao_dxy_pct
// trazem de onde saiu o numero — o card PRECISA deixar visualmente claro
// que e estimado, nunca mostrar como se fosse PTAX real.

const OPCOES_2_CASAS = { minimumFractionDigits: 2, maximumFractionDigits: 2 };

function formatar(valor, opcoes) {
  return valor.toLocaleString("pt-BR", opcoes);
}

export default function DolarTeoricoCard({ dado }) {
  if (!dado || dado.erro) {
    return (
      <div className="chart-card chart-card--empty">
        <div className="chart-title">Dólar Teórico — paridade DI1 × FRC</div>
        <div className="chart-empty-msg">
          {dado?.erro ?? "sem dados — confira se o main.py (last_nac.py + last_int.py + vigente.py) já rodou pelo menos uma volta"}
        </div>
      </div>
    );
  }

  const diferencaPositiva = dado.diferenca_pct >= 0;

  return (
    <div className="chart-card">
      <div className="chart-title">Dólar Teórico — paridade DI1 × FRC ({dado.vertice})</div>
      <div className="dolar-teorico-linhas">
        <div className="dolar-teorico-linha">
          <span className="muted">Teórico</span>
          <span className="mono dolar-teorico-valor">{formatar(dado.dolar_teorico, OPCOES_2_CASAS)}</span>
        </div>
        <div className="dolar-teorico-linha">
          <span className="muted">Negociado ({dado.ticker})</span>
          <span className="mono dolar-teorico-valor">{formatar(dado.dolar_negociado, OPCOES_2_CASAS)}</span>
        </div>
        <div className="dolar-teorico-linha">
          <span className="muted">Diferença</span>
          <span className={`mono dolar-teorico-valor ${diferencaPositiva ? "delta-up" : "delta-down"}`}>
            {diferencaPositiva ? "+" : ""}
            {formatar(dado.diferenca_pct, { minimumFractionDigits: 3, maximumFractionDigits: 3 })}%
          </span>
        </div>
      </div>
      {/* dado.spot_usdbrl vem do backend na escala real (R$ por US$1, ex
          5,1470) — aqui na tela multiplica por 1000 so pra exibir na MESMA
          escala do Teorico/Negociado (R$ por US$1.000, ex "5.147,00"),
          pedido do usuario ("usa o USDBRL mesmo aqui... multiplique por mil
          pra ficar 5.147,..."). O calculo em si (_dolar_teorico() no
          api_server.py) ja usa o spot na escala real — isso e SO exibicao. */}
      <div className="dolar-teorico-detalhe muted">
        {dado.spot_estimado ? (
          <>
            PTAX <span className="dolar-teorico-estimado-tag">ESTIMADO</span> USDBRL{" "}
            {formatar(dado.spot_usdbrl * 1000, OPCOES_2_CASAS)} (ontem {formatar(dado.spot_estimado_anterior?.valor * 1000, OPCOES_2_CASAS)} ×{" "}
            DXY {dado.spot_estimado_variacao_dxy_pct >= 0 ? "+" : ""}
            {formatar(dado.spot_estimado_variacao_dxy_pct, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}%) · DI1{" "}
          </>
        ) : (
          <>
            PTAX aprox. USDBRL {formatar(dado.spot_usdbrl * 1000, OPCOES_2_CASAS)} ({dado.ptax_proxy_janelas_completas ?? 0}/4 janelas) · DI1{" "}
          </>
        )}
        {formatar(dado.di1_pct, OPCOES_2_CASAS)}% · Cupom FRC ({dado.vertice_cupom}) {formatar(dado.cupom_frc_pct, OPCOES_2_CASAS)}% ·{" "}
        {dado.dias_uteis_di1}du / {dado.dias_corridos_cupom}dc até o vencimento (du já com feriados B3; dc é Actual/360, corridos por convenção)
      </div>
    </div>
  );
}
