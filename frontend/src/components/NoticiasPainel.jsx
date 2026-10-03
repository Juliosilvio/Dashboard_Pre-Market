// NoticiasPainel.jsx — manchetes em tempo real do canal publico do
// Telegram fonte de noticias (agrega agregador de noticias), ver noticias.py / GET
// /api/noticias. Pedido do usuario (2026-09-23): "noticias em tempo
// real!!!".
//
// Lista simples, mais recente no topo, hora convertida pro fuso de Sao
// Paulo (mesmo padrao de QuotesTable.jsx/formatarHora — o backend grava
// o horario em UTC). Cada linha e um link pro post original no Telegram.
//
// Estilo todo em classes CSS (.noticias-*, ver tokens.css) — nada de
// style inline (mesmo pedido do usuario aplicado em DesviosPainel.jsx:
// "voce devia ter jogado no css... fica mais facil de editar").
//
// Traducao (2026-09-30, pedido do usuario: "precisamos de tradutor nas
// atualizacoes das noticias") — a fonte (agregador de noticias) publica em
// ingles; noticias.py 1.1.0 traduz cada manchete NOVA e grava os dois
// textos (item.texto = original ingles, item.texto_pt = traduzido). Aqui
// mostra texto_pt quando existe, cai pro texto original quando a traducao
// falhou daquela vez (rede, endpoint fora do ar — ver _traduzir() no
// noticias.py, nunca derruba o coletor) — pra nunca mostrar manchete em
// branco por causa de tradutor de terceiro fora do ar.

// quantas manchetes aparecem no card - pedido do usuario (2026-09-23):
// "coloque no maximo 4 ou 5 noticias no card" (backend guarda ate 40 pra
// nunca perder nada entre polls, o corte pra exibicao e so aqui no front).
const MAX_EXIBIDAS = 5;

function formatarHoraSP(isoString) {
  if (!isoString) return "--:--";
  const data = new Date(isoString);
  if (Number.isNaN(data.getTime())) return "--:--";
  return data.toLocaleTimeString("pt-BR", {
    timeZone: "America/Sao_Paulo",
    hour: "2-digit",
    minute: "2-digit",
  });
}

// pedido do usuario (2026-09-23): "nao precisa de emojis" - o canal
// (agregador de noticias) costuma vir com bandeira/emoji no comeco da manchete;
// tira aqui na exibicao (o texto cru continua intacto no JSON, so a view
// filtra).
function removerEmojis(texto) {
  if (!texto) return texto;
  return texto
    .replace(/\p{Extended_Pictographic}/gu, "")
    .replace(/[\u{1F1E6}-\u{1F1FF}]/gu, "")
    .replace(/\uFE0F/gu, "")
    .replace(/\s{2,}/g, " ")
    .trim();
}

function ItemNoticia({ item }) {
  const textoExibido = item.texto_pt ?? item.texto;
  return (
    <div className="noticias-item">
      <span className="mono noticias-hora">{formatarHoraSP(item.hora_iso)}</span>
      <span className="noticias-texto" title={item.texto_pt ? item.texto : undefined}>
        {removerEmojis(textoExibido)}
      </span>
    </div>
  );
}

export default function NoticiasPainel({ titulo, dados, footer }) {
  const lista = (dados ?? []).slice(0, MAX_EXIBIDAS);

  return (
    <div className="chart-card">
      {titulo && <div className="chart-title">{titulo}</div>}
      {lista.length === 0 ? (
        <div className="mono noticias-vazio">sem notícia ainda — confira se o noticias.py rodou</div>
      ) : (
        <div className="noticias-lista">
          {lista.map((item) => (
            <ItemNoticia key={item.id} item={item} />
          ))}
        </div>
      )}
      {footer}
    </div>
  );
}
