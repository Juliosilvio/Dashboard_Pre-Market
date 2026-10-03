// Panel.jsx — janela livre dentro do painel: arrasta pra qualquer lugar
// (pela barrinha de cima) e redimensiona puxando o canto inferior direito.
// Pedido do usuario: "colocar os graficos em qualquer lugar na janela" +
// "os graficos tem que se redimensionar de acordo com o movimento que faço"
// — por isso o layout aqui e por POSICAO LIVRE (x, y, width, height em px,
// posicionamento absoluto dentro do .dashboard-canvas), nao mais uma grade
// fixa, e o onChange dispara a CADA pixel de mousemove durante o arrasto
// (nao so no mouseup) — o conteudo (JurosChart/CurveChart) recebe a largura
// disponivel em tempo real e se redesenha junto, em vez de so esticar a
// caixa por fora com um scroll cortando o grafico.
//
// "layout" e {x, y, width, height, z}; "onChange(id, novoLayout)" e chamado
// a cada frame do arrasto — quem guarda o estado de verdade e o pai
// (useLayout hook). Nada e salvo em disco sozinho aqui: so vira arquivo
// quando o usuario clica em "Salvar layout".
//
// "onFront(id)" e chamado no mousedown (antes mesmo de mover 1px) — traz o
// painel pro topo da pilha (z-index mais alto de todos). Sem isso, o
// z-index seguia so a ordem em que os paineis foram declarados no App.jsx,
// entao arrastar um painel PRA CIMA de outro nao adiantava nada: o de baixo
// (declarado depois) sempre ficava por cima e "engolia" o que acabou de ser
// movido — bug relatado pelo usuario ("quando movo os graficos eles entram
// embaixo de uma parte da tela e somem").
//
// "fixo" (bool): em tela pequena (celular/tablet, ver App.jsx) o painel
// livre vira um bloco normal empilhado (sem arrastar, sem redimensionar
// manual) — arrastar com o dedo numa alcinha de 16px e redimensionar por
// canto nao funciona bem no toque, e telas estreitas nao tem espaco sobrando
// pra espalhar janela nenhuma. Nesse modo o Panel so repassa os children,
// sem cabecalho de arrasto nem posicionamento absoluto.
//
// "escala": o dashboard-canvas inteiro (todos os paineis juntos) e
// redesenhado com um CSS transform:scale() no App.jsx pra caber exatamente
// na largura da janela, em qualquer tamanho — pedido do usuario: "os
// graficos tem que se adaptar a janela principal e a janela principal a
// pagina, independente do tamanho da tela". Isso MUDA a relacao entre
// pixel de tela e pixel de layout: se a escala e 0,5, mover o mouse 10px na
// TELA equivale a mover o painel 20px no sistema de coordenadas do layout
// (que e sempre o mesmo, independente da escala visual). Por isso todo
// dx/dy do mouse e dividido pela escala antes de aplicar no layout — sem
// isso, arrastar ficaria "solto" (o painel andaria mais rapido ou mais
// devagar que o cursor, dependendo de quanto a tela encolheu/esticou o
// canvas). A escala e capturada no INICIO do arrasto (guardada dentro de
// arrastoRef, nao como dependencia do efeito) pra nao precisar reinstalar
// os listeners toda vez que a janela redimensiona.
//
// children pode ser um node normal OU uma funcao (dims) => node — a funcao
// recebe a largura de conteudo disponivel (ja descontando o padding do
// chart-card) pra graficos que precisam saber o tamanho real em px, tipo o
// JurosChart (que decide entre esticar os vertices ou ligar o scroll
// horizontal). Quem nao precisa (CurveChart, QuotesTable) so preenche via
// CSS normal (flex/percent) e ignora o argumento.
//
// "onArrastoInicio"/"onArrastoFim": avisam o App.jsx quando um arrasto (mover
// OU redimensionar) comeca/termina — pedido do usuario: "quando estou
// mexendo nos boxes aumenta ou diminui o zoom, acho que não é normal né?".
// Causa: o canvas inteiro recalcula "escala" (ver comentario acima) toda vez
// que "paineis" muda — e mover/redimensionar UM painel muda "paineis" a
// CADA pixel de mousemove (ver onChange abaixo), entao redimensionar um
// grafico maior fazia o BOUNDING BOX de todos os paineis crescer, o que
// encolhia a escala do canvas INTEIRO em tempo real — parecia um zoom out
// acontecendo sozinho enquanto voce mexia em uma unica caixa. O App.jsx usa
// esses dois callbacks pra CONGELAR o recalculo de escala enquanto
// onArrastoInicio...onArrastoFim estiver "aberto", e so recalcula de vez
// (uma vez so, limpo) quando o mouse solta — as outras caixas na tela
// ficam paradas enquanto voce mexe em uma so.

import { useEffect, useRef } from "react";

const LARGURA_MIN = 260;
const ALTURA_MIN = 160;
// padding horizontal do .chart-card (20px de cada lado, ver tokens.css) —
// descontado pra dar pro filho a largura de DESENHO real, nao a da caixa.
const PAD_CONTEUDO_H = 40;

export default function Panel({
  id,
  title,
  layout,
  onChange,
  onFront,
  onArrastoInicio,
  onArrastoFim,
  fixo = false,
  escala = 1,
  children,
}) {
  const arrastoRef = useRef(null); // {tipo, startX, startY, startLayout, escala} enquanto arrasta

  useEffect(() => {
    function mover(e) {
      const arrasto = arrastoRef.current;
      if (!arrasto) return;
      // divide pela escala capturada no inicio do arrasto — ver comentario
      // no topo do arquivo sobre a relacao pixel-de-tela x pixel-de-layout
      const dx = (e.clientX - arrasto.startX) / arrasto.escala;
      const dy = (e.clientY - arrasto.startY) / arrasto.escala;

      if (arrasto.tipo === "mover") {
        onChange(id, {
          ...arrasto.startLayout,
          x: Math.max(0, arrasto.startLayout.x + dx),
          y: Math.max(0, arrasto.startLayout.y + dy),
        });
      } else {
        onChange(id, {
          ...arrasto.startLayout,
          width: Math.max(LARGURA_MIN, arrasto.startLayout.width + dx),
          height: Math.max(ALTURA_MIN, arrasto.startLayout.height + dy),
        });
      }
    }

    function soltar() {
      if (!arrastoRef.current) return;
      arrastoRef.current = null;
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
      onArrastoFim?.(id);
    }

    window.addEventListener("mousemove", mover);
    window.addEventListener("mouseup", soltar);
    return () => {
      window.removeEventListener("mousemove", mover);
      window.removeEventListener("mouseup", soltar);
    };
  }, [id, onChange, onArrastoFim]);

  function iniciarMover(e) {
    e.preventDefault();
    onFront?.(id);
    onArrastoInicio?.(id);
    arrastoRef.current = { tipo: "mover", startX: e.clientX, startY: e.clientY, startLayout: layout, escala };
    document.body.style.cursor = "move";
    document.body.style.userSelect = "none";
  }

  function iniciarRedimensionar(e) {
    e.preventDefault();
    e.stopPropagation();
    onFront?.(id);
    onArrastoInicio?.(id);
    arrastoRef.current = {
      tipo: "redimensionar",
      startX: e.clientX,
      startY: e.clientY,
      startLayout: layout,
      escala,
    };
    document.body.style.cursor = "nwse-resize";
    document.body.style.userSelect = "none";
  }

  // modo fixo (tela pequena): bloco normal, largura de conteudo = 100% do
  // container pai (a propria tela) — o filho recebe undefined e cai no
  // fallback (LARGURA_MIN) do proprio componente, que ja e responsivo via
  // CSS (largura real vem do flex/percent, so o numero de px pro
  // scroll-ou-nao do JurosChart e que fica aproximado).
  if (fixo) {
    return (
      <div className="painel-fixo">
        <div className="painel-conteudo">
          {typeof children === "function" ? children({ width: undefined }) : children}
        </div>
      </div>
    );
  }

  const larguraConteudo = Math.max(0, layout.width - PAD_CONTEUDO_H);

  return (
    <div
      className="painel-livre"
      style={{
        left: layout.x,
        top: layout.y,
        width: layout.width,
        height: layout.height,
        zIndex: layout.z ?? 1,
      }}
    >
      <div className="painel-cabecalho" title={`Arraste pra mover: ${title}`} onMouseDown={iniciarMover}>
        ⠿⠿⠿
      </div>
      <div className="painel-conteudo">
        {typeof children === "function" ? children({ width: larguraConteudo }) : children}
      </div>
      <div className="painel-resize-handle" title="Arraste pra redimensionar" onMouseDown={iniciarRedimensionar} />
    </div>
  );
}
