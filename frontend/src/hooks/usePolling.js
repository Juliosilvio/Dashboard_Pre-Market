// usePolling.js — hook generico de polling. Chama fetchFn a cada
// intervalMs, sempre esperando a resposta anterior terminar antes de disparar
// a proxima (evita empilhar requests se a rede/API atrasar). Usado tanto pra
// cotacoes (intervalo curto, ~1s) quanto pra curvas (intervalo longo, ~30s,
// ja que ainda nao existe calculo de curva de verdade no backend).
//
// O guard de "requisicao em andamento" (antes um useRef) precisa ser uma
// variavel LOCAL do closure do efeito, nunca algo que sobrevive entre
// invocacoes do efeito (useRef sobrevive). Motivo: em dev, o React
// StrictMode monta cada componente DUAS VEZES de proposito (monta -> limpa
// -> monta de novo), pra pegar efeito mal comportado. Com um useRef
// compartilhado, a 2a montagem (a que realmente fica viva) via o guard
// ainda marcado "true" pela 1a montagem (ja cancelada, mas com fetch em
// voo) e desistia na hora, sem chegar a agendar seu proprio
// setTimeout — o polling morria pra sempre depois da 1a tentativa, mesmo
// com o servidor respondendo 200 normalmente (bug real, encontrado tentando
// consumir /api/curvas/juros do frontend: pedido aparecia OK no log do
// uvicorn, mas a pagina nunca recebia o dado). Com a variavel local, cada
// invocacao do efeito (cada "montagem" do StrictMode) tem seu proprio guard
// independente — a 2a montagem nunca ve o estado da 1a.

import { useEffect, useState } from "react";

export function usePolling(fetchFn, intervalMs, deps = []) {
  const [dado, setDado] = useState(null);
  const [erro, setErro] = useState(null);
  const [carregando, setCarregando] = useState(true);

  useEffect(() => {
    let cancelado = false;
    let emVoo = false;
    let timer;

    async function tick() {
      if (emVoo) return;
      emVoo = true;
      try {
        const resultado = await fetchFn();
        if (!cancelado) {
          setDado(resultado);
          setErro(null);
        }
      } catch (e) {
        if (!cancelado) setErro(e);
      } finally {
        emVoo = false;
        if (!cancelado) {
          setCarregando(false);
          timer = setTimeout(tick, intervalMs);
        }
      }
    }

    tick();

    return () => {
      cancelado = true;
      clearTimeout(timer);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  return { dado, erro, carregando };
}
