// ModeloSwingCard.jsx — cenario de swing intradiario por ativo: horario mais
// provavel de topo/fundo (diag_sazonalidade_swings.py) + vies MACD M15/IFR M5
// + faixa de oscilacao esperada via GARCH(1,1) (modelo_garch_swing.py) + a
// partir da v3.0.0, sinal/direcao/confianca/alvo/entrada dos classificadores
// LightGBM combinados com o GARCH (cenario_final_swing.py).
//
// v2.0.0 (2026-09-27) - CORRECAO de design: a v1.0.0 tinha um seletor de
// ativo PROPRIO dentro do card (dropdown com as 129 raizes). Pedido do
// usuario: "isso aqui esta errado, o cenario e construido pelo ativo que
// eu escolho no [seletor de VIEW, o mesmo 'Indice/Dolar' / 'Nasdaq' do
// topo da pagina] e os cards com cenario aparecem na pagina escolhida" -
// ou seja, nao e um seletor NOVO e independente, e o mesmo conceito de
// "ativo da view" que ja existe pro resto do app (QuotesTable grupo=/
// simboloFuturo=, DesviosPainel ativos=, etc.). Virou um componente burro:
// recebe a raiz PRONTA via prop (App.jsx decide qual, a partir de
// viewAtiva/registroViews - GET /api/grades-cotacoes desde 2026-09-29,
// ver comentario la), sem estado proprio de selecao.
//
// v3.0.0 (2026-09-27, mesmo dia) - pedido do usuario depois de ver os
// numeros do classificador: "com os numeros gerados por essa fase do
// sistema precisamos de recomendacao de onde o preco pode ir e qual e a
// entrada". O endpoint (GET /api/modelo-swing/{raiz}, api_server.py 1.18.0)
// passou a chamar CenarioFinalSwing em vez de ModeloGarchSwing direto - a
// resposta e um SUPERSET (todo campo antigo continua vindo), entao so
// ACRESCENTAMOS um bloco de destaque (sinal/direcao/confianca/alvo/entradas)
// acima da tabela GARCH que ja existia, sem tirar nada. "indefinido"/"sem
// sinal" e o caso NORMAL (limiar calibrado pra disparar em so ~4,5% dos
// candles) - nao e erro, so significa que o modelo nao tem confianca
// suficiente AGORA pra sugerir direcao.
//
// Unico card do frontend cujo fetch e recalculado (GARCH + classificador) a
// cada chamada - poll longo (5min) de proposito: o endpoint CALCULA na hora
// (nao e leitura de arquivo pronto), e o sinal e baseado em M15 (candle
// fecha a cada 15min) - pollar mais rapido so gastaria CPU sem ganhar
// informacao nova. [raiz] nas deps do usePolling reinicia o polling na hora
// que a raiz muda (troca de view), disparando um fetch imediato pro ativo
// novo.

import { usePolling } from "../hooks/usePolling";
import { api } from "../api/client";

const PAUSA_MODELO_SWING = 5 * 60 * 1000;

function fmtPreco(v) {
  if (v == null || Number.isNaN(v)) return "--";
  // ate 5 casas pra nao esconder a faixa em ativos de preco baixo (forex,
  // ex.: EURUSD ~1.14) - QuotesTable.jsx usa 3 casas fixas, mas aqui a
  // faixa esperada em torno de um preco baixo fica achatada com menos.
  return v.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 5 });
}

function classeVies(vies) {
  if (vies === "alta") return "delta-up";
  if (vies === "baixa") return "delta-down";
  return "";
}

function rotuloVies(vies) {
  if (vies === "alta") return "Alta";
  if (vies === "baixa") return "Baixa";
  if (vies === "neutro") return "Neutro";
  return "--";
}

function rotuloIfrEstado(estado) {
  if (estado === "sobrecomprado") return "Sobrecomprado";
  if (estado === "sobrevendido") return "Sobrevendido";
  if (estado === "neutro") return "Neutro";
  return "--";
}

function classeDirecao(direcao) {
  if (direcao === "compra") return "delta-up";
  if (direcao === "venda") return "delta-down";
  return "";
}

function rotuloDirecao(direcao) {
  if (direcao === "compra") return "Compra";
  if (direcao === "venda") return "Venda";
  return "Sem sinal";
}

export default function ModeloSwingCard({ raiz }) {
  const { dado, erro, carregando } = usePolling(
    () => api.modeloSwing.analisar(raiz),
    PAUSA_MODELO_SWING,
    [raiz]
  );

  const temSinal = dado && dado.sinal && dado.sinal !== "indefinido";

  return (
    <div className="chart-card quotes-card">
      {erro && (
        <div className="chart-empty-msg">
          {erro.status === 404
            ? `sem amostra suficiente pra ${raiz}`
            : erro.status === 500
            ? "modelo indisponível — confira se `arch`/`lightgbm`/`scikit-learn` foram instalados no venv e se modelo_classificador_swing.py já rodou"
            : `erro ao consultar o modelo: ${erro.message}`}
        </div>
      )}

      {!erro && carregando && <div className="chart-empty-msg">calculando…</div>}

      {!erro && !carregando && dado && (
        <div className="modelo-swing-corpo">
          <div className="chart-headline">
            <span className="chart-headline-value">{fmtPreco(dado.preco_atual)}</span>
            <span className={`chart-delta ${classeVies(dado.vies_macd_m15)}`}>
              viés {rotuloVies(dado.vies_macd_m15)}
            </span>
          </div>

          <div className="modelo-swing-sinal">
            <span className={`chart-delta ${classeDirecao(dado.direcao_sugerida)}`}>
              {rotuloDirecao(dado.direcao_sugerida)}
            </span>
            {temSinal && (
              <span className="quotes-subtitle">
                {" "}
                confiança: {dado.confianca}
              </span>
            )}
          </div>

          <table>
            <tbody>
              <tr>
                <td>Prob. topo / fundo</td>
                <td className="num">
                  {dado.probabilidade_topo_pct ?? "--"}% / {dado.probabilidade_fundo_pct ?? "--"}%
                </td>
              </tr>
              {temSinal && (
                <>
                  <tr>
                    <td>Alvo sugerido</td>
                    <td className="num">{fmtPreco(dado.alvo_sugerido)}</td>
                  </tr>
                  <tr>
                    <td>Entrada — a mercado</td>
                    <td className="num">{fmtPreco(dado.entrada_a_mercado)}</td>
                  </tr>
                  <tr>
                    <td>Entrada — zona de pullback</td>
                    <td className="num">{fmtPreco(dado.entrada_zona_pullback)}</td>
                  </tr>
                </>
              )}
              <tr>
                <td>IFR M5</td>
                <td className="num">
                  {dado.ifr_m5 == null ? "--" : dado.ifr_m5.toFixed(1)} ({rotuloIfrEstado(dado.ifr_m5_estado)})
                </td>
              </tr>
              <tr>
                <td>Horário mais provável — topo</td>
                <td className="num">{dado.horario_mais_provavel_topo ?? "--"}</td>
              </tr>
              <tr>
                <td>Horário mais provável — fundo</td>
                <td className="num">{dado.horario_mais_provavel_fundo ?? "--"}</td>
              </tr>
              <tr>
                <td>Faixa esperada (GARCH, ±1σ)</td>
                <td className="num">
                  {fmtPreco(dado.faixa_esperada_min)} – {fmtPreco(dado.faixa_esperada_max)}
                </td>
              </tr>
              <tr>
                <td>σ (1 candle M15)</td>
                <td className="num">{dado.sigma_garch_1passo_pct}%</td>
              </tr>
            </tbody>
          </table>

          {/* 2026-09-30: tirada tambem a linha "amostra: N candles M15" --
              pedido do usuario: "tire o numero de amostras e desnecessario
              deixe so no backend". dado.candles_m15_amostra continua
              vindo da API (cenario_final_swing.py), so parou de renderizar
              aqui -- card ficou so com a tabela (vies/faixa/zona/sigma). */}
        </div>
      )}
    </div>
  );
}
