// CausalidadeLegenda.jsx — card pequeno explicando os badges de
// causalidade de Granger ("Gi"/"dg") que aparecem do lado do nome dos
// ativos nas tabelas Risk Índice/Risk Dólar (ver QuotesTable.jsx, badge
// desde 2026-09-30). Pedido do usuário: "coloque um índice explicando o
// que é dg e gi, como ambos tem cores diferentes pode ser dois pontinhos
// na mesma cor deles e do lado escrito causalidade com índice e
// causalidade com dólar... pode ser um card novo não tem problema".
//
// Sem dado nenhum vindo do backend — é só texto fixo, as cores dos
// pontinhos batem 1:1 com as classes causalidade-badge-indice/
// causalidade-badge-dolar (tokens.css, --s-juros azul / --s-frc laranja),
// pra ficar óbvio qual pontinho é qual badge na tabela.
//
// 2026-09-30: tirada a nota explicativa embaixo (Teste de Granger vs
// correlação, duplicação entre tabelas) -- pedido do usuário: "pode tirar
// essa anotação". Card ficou só com as duas linhas pontinho+sigla+texto.
export default function CausalidadeLegenda() {
  return (
    <div className="chart-card causalidade-legenda-card">
      <div className="chart-title">Legenda — Causalidade de Granger</div>
      <div className="causalidade-legenda-linhas">
        <div className="causalidade-legenda-linha">
          <span className="causalidade-legenda-ponto causalidade-legenda-ponto-indice" />
          <span className="mono causalidade-legenda-sigla notranslate" translate="no">
            Gi
          </span>
          <span className="muted">— causalidade com Índice: o retorno passado deste ativo ajuda a prever o Indice</span>
        </div>
        <div className="causalidade-legenda-linha">
          <span className="causalidade-legenda-ponto causalidade-legenda-ponto-dolar" />
          <span className="mono causalidade-legenda-sigla notranslate" translate="no">
            dg
          </span>
          <span className="muted">— causalidade com Dólar: o retorno passado deste ativo ajuda a prever o Dolar</span>
        </div>
      </div>
    </div>
  );
}
