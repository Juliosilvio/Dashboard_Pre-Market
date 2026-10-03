// DesviosPainel.jsx — projecao de desvios de preco (dp.py: MACD/ATR/IFR,
// consenso multi-timeframe), atualiza a cada hora (pedido do usuario
// 2026-09-23: "nao precisa ser rapidao, pode atualizar de hora em hora" —
// ver PAUSA_DP em App.jsx).
//
// v1.1.0 (2026-09-23): o usuario viu a v1.0.0 (12 mini-cards, um por
// combinacao ativo+TF) rodando ao vivo e pediu pra simplificar: "nao
// precisa disso projecao em 5 TF???? pra que faz duas tabelinhas so com
// Indice e Dolar, uma pra cada e usas dentre todos os TF a regressao
// linear pra ver qual o mais provavel dos pontos" -> "o eixo x e a media
// que mais se repetir dentre as 5 tabelas dos TF". dp.py agora entrega
// {"detalhe": [...] (as 12 combinacoes, so pra depuracao), "consolidado":
// [...] (no maximo 2 entradas, uma por ativo — a media consolidada do
// maior grupo de TFs concordando, "a media que mais se repete", com a TF
// mais curta do grupo emprestando ATR/direcao pros desvios)}. Este painel
// consome so "consolidado" e mostra SEMPRE 2 blocos fixos (Indice/Dolar).
//
// Visual = o mesmo card de referencia que o usuario aprovou manualmente
// nesta sessao (fundo preto, sem grade, mu no centro, desvios positivos
// em vermelho empilhados acima, negativos em verde empilhados abaixo,
// colunas coladas, cabecalho so "Índice"/"Dólar" sem sufixo de TF).
//
// Estilo: todo em classes CSS (ver .dp-* em src/styles/tokens.css), sem
// style inline — pedido do usuario (2026-09-23): "voce devia ter jogado
// no css e o DesviosPainel.jsx puxava assim fica mais facil de editar".
// Pra ajustar padding/fonte/espacamento, mexe direto no tokens.css.

// pedido do usuario (depois de replicar este card na view do Nasdaq): "mas
// aqui tem que apresentar os valores apenas para nasdaq" — o card mostrava
// SEMPRE os 2 blocos fixos Indice/Dolar, mesmo dentro de outra view. Virou
// parametrizavel via prop `ativos` (ver export default abaixo); o default
// mantem o comportamento de sempre da view principal.
const ATIVO_LABEL = {
  "Indice": "Índice",
  "Dolar": "Dólar",
  UsaTec: "Nasdaq",
  // card de juros americanos na view Nasdaq (config.json ->
  // dp_ativos_extra, pedido do usuario 2026-09-26) — proxies de
  // treasury via ETF (ver dp.py 1.3.0 pro motivo de nao usar
  // ativos_referencia_extra aqui).
  TLT: "TLT (20+ anos)",
  IEF: "IEF (7-10 anos)",
  SHY: "SHY (1-3 anos)",
};
const ORDEM_ATIVOS_PADRAO = ["Indice", "Dolar"];

// pedido do usuario (2026-09-26, depois de ver o card TLT/IEF/SHY):
// "nao tinha que ter virgulas nos dados?" - Indice/Dolar/UsaTec sao
// pontos de indice/futuro (0 casas decimais, formato ja aprovado pelo
// usuario nesta sessao), mas TLT/IEF/SHY sao ETFs cotados em dolar com
// centavos (ex.: fechamento_atual 79.32) - arredondar pra 0 casas
// escondia justamente a variacao que importa numa faixa de precos tao
// estreita. Ativo fora do mapa cai no padrao de sempre (0 casas).
const CASAS_POR_ATIVO = { TLT: 2, IEF: 2, SHY: 2 };

function fmt(v, casas = 0) {
  if (v == null || Number.isNaN(v)) return "—";
  return v.toLocaleString("pt-BR", { minimumFractionDigits: casas, maximumFractionDigits: casas });
}

function LinhaDesvio({ n, preco, lado, casas }) {
  return (
    <div className={`dp-linha dp-linha--${lado}`}>
      <span className="mono dp-linha-n">{n > 0 ? `+${n} DP` : `${n} DP`}</span>
      <span className="mono dp-linha-preco">{fmt(preco, casas)}</span>
    </div>
  );
}

function BlocoAtivo({ ativo, item }) {
  const titulo = ATIVO_LABEL[ativo] ?? ativo;
  const casas = CASAS_POR_ATIVO[ativo] ?? 0;

  if (!item) {
    return (
      <div className="dp-bloco">
        <div className="mono dp-titulo dp-titulo--vazio">{titulo}</div>
        <div className="mono dp-vazio">sem consenso ainda — nenhuma TF com projeção formada</div>
      </div>
    );
  }

  const centro = item.media_consolidada;
  const acima = [];
  const abaixo = [];
  for (const d of item.desvios ?? []) {
    acima.push({ n: d.n, preco: d.preco_cima });
    abaixo.push({ n: -d.n, preco: d.preco_baixo });
  }
  // ordem visual: do mais perto da media pro mais longe, em ambos os
  // lados (acima desce +1..+4 afastando pra cima; abaixo desce -1..-4
  // afastando pra baixo).
  acima.sort((a, b) => b.n - a.n);
  abaixo.sort((a, b) => b.n - a.n);

  return (
    <div className="dp-bloco">
      <div className="dp-cabecalho">
        <span className="mono dp-titulo">{titulo}</span>
        <span className="mono dp-preco-atual">{fmt(item.fechamento_atual, casas)}</span>
      </div>

      {acima.length > 0 ? (
        <>
          {acima.map((l) => (
            <LinhaDesvio key={"c" + l.n} n={l.n} preco={l.preco} lado="acima" casas={casas} />
          ))}
          <div className="dp-media">
            <span className="mono dp-media-simbolo">μ</span>
            <span className="mono dp-media-valor">{fmt(centro, casas)}</span>
          </div>
          {abaixo.map((l) => (
            <LinhaDesvio key={"b" + l.n} n={l.n} preco={l.preco} lado="abaixo" casas={casas} />
          ))}
        </>
      ) : (
        <div className="mono dp-vazio">sem desvio calculavel ainda</div>
      )}
    </div>
  );
}

export default function DesviosPainel({ titulo, dados, footer, ativos = ORDEM_ATIVOS_PADRAO }) {
  const consolidado = dados?.consolidado ?? [];
  const porAtivo = Object.fromEntries(consolidado.map((item) => [item.ativo, item]));

  return (
    <div className="chart-card">
      {titulo && <div className="chart-title">{titulo}</div>}
      <div className="dp-grid">
        {ativos.map((ativo) => (
          <BlocoAtivo key={ativo} ativo={ativo} item={porAtivo[ativo]} />
        ))}
      </div>
      {footer}
    </div>
  );
}
