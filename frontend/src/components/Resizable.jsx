// Resizable.jsx — envelope fino que deixa QUALQUER card (grafico, tabela)
// redimensionavel arrastando o canto inferior direito — resize NATIVO do
// navegador (CSS "resize: both"), sem biblioteca nenhuma. O tamanho salvo
// (localStorage/backend, ver useLayout.js) e aplicado como estilo inline na
// primeira vez que ele chega (o carregamento e assincrono, entao o painel
// nasce no tamanho padrao e "pula" pro tamanho salvo assim que a resposta
// chega). Cada resize do usuario e reportado pro pai via ResizeObserver —
// isso so atualiza uma ref em memoria, nao grava nada em disco sozinho; so
// vira arquivo de verdade quando o usuario clica em "Salvar layout".

import { useEffect, useRef } from "react";

export default function Resizable({ id, tamanhoInicial, onResize, children }) {
  const ref = useRef(null);
  const aplicadoRef = useRef(false);

  useEffect(() => {
    const el = ref.current;
    if (!el || aplicadoRef.current || !tamanhoInicial) return;
    if (tamanhoInicial.width) el.style.width = `${tamanhoInicial.width}px`;
    if (tamanhoInicial.height) el.style.height = `${tamanhoInicial.height}px`;
    aplicadoRef.current = true;
  }, [tamanhoInicial]);

  useEffect(() => {
    const el = ref.current;
    if (!el) return undefined;
    const observer = new ResizeObserver((entradas) => {
      const { width, height } = entradas[0].contentRect;
      onResize(id, { width: Math.round(width), height: Math.round(height) });
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, [id, onResize]);

  return (
    <div ref={ref} className="resizable-panel">
      {children}
    </div>
  );
}
