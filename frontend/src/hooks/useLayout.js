// useLayout.js — guarda a posicao/tamanho (x, y, width, height) de cada
// painel livre (ver Panel.jsx/App.jsx). Grava em DOIS lugares: localStorage
// (sempre, rapido, por navegador) e no backend via POST /api/layout
// (json/layout.json em disco — pedido explicito do usuario: "salve em
// backend tambem", pra sobreviver troca de navegador/maquina). Desde a
// v1.2.0 do client.js, o backend guarda um arquivo POR NAVEGADOR (nao um
// so global) — client.js quem cuida disso (?cliente=<id>), este hook nao
// muda nada. Ao carregar a
// pagina, tenta o backend primeiro (fonte "oficial") e cai pro localStorage
// se a api_server.py estiver fora do ar; se nenhum dos dois tiver nada, cada
// painel fica no layout padrao (ver LAYOUT_PADRAO em App.jsx).
//
// Formato do objeto salvo: { paineis: { <id>: {x, y, width, height, z} } } —
// versao "v2" (posicionamento livre); a versao anterior (so width/height +
// divisor de coluna fixo) foi trocada pelo pedido "quero colocar os
// graficos em qualquer lugar na janela", por isso a chave do localStorage
// mudou (nao tenta migrar layout velho, so comeca do zero no formato novo).
// "z" e a ordem de empilhamento (quem foi arrastado/redimensionado por
// ultimo fica por cima) — ver trazerParaFrente().
//
// AUTOSAVE (pedido do usuario apos perder o arranjo 2x: "não volta não, ja
// fechei a pagina 2 veses e tive que rearanjar ela toda"): ANTES, o layout
// so era gravado quando o usuario clicava no botao "Salvar layout" —
// arrastar/redimensionar um painel so mudava o estado em memoria
// (definirPainel/trazerParaFrente). Fechar a pagina sem lembrar de clicar no
// botao perdia tudo, sem nenhum aviso. Agora QUALQUER mudanca em `paineis`
// (mover, redimensionar, trazer pra frente) dispara um salvamento
// automatico ~900ms depois da ultima mudanca (debounce — evita gravar a
// cada pixel arrastado, so grava quando o usuario para de mexer). O botao
// "Salvar layout" continua existindo — agora serve pra forcar o salvamento
// na hora (sem esperar o debounce), util antes de fechar o navegador rapido.
//
// Detalhes da implementacao do autosave:
//   - carregadoRef trava o autosave ate o carregamento inicial (backend/
//     localStorage) terminar — sem isso, o efeito de autosave rodaria com o
//     layout PADRAO antes do layout salvo chegar, e gravaria o padrao por
//     cima do que o usuario tinha salvo antes (perderia o layout na volta!).
//   - ultimoPersistidoRef guarda um JSON.stringify do ultimo `paineis`
//     efetivamente gravado. Serve pra nao regravar (nem piscar "salvando...")
//     quando o proprio carregamento inicial dispara o efeito de autosave com
//     o MESMO conteudo que acabou de vir do backend/localStorage — so
//     interessa gravar quando algo REALMENTE mudou.
//   - persistir() centraliza a gravacao (localStorage + POST /api/layout) e
//     e usada tanto pelo autosave quanto pelo clique manual em "Salvar
//     layout" (que passa forcar:true pra sempre dar feedback visual, mesmo
//     se por acaso nada tiver mudado desde o ultimo autosave).

import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api/client.js";

const CHAVE_LOCAL = "painel-layout-v2";
const ATRASO_AUTOSAVE_MS = 900;

function lerLocalStorage() {
  try {
    const bruto = localStorage.getItem(CHAVE_LOCAL);
    return bruto ? JSON.parse(bruto) : null;
  } catch {
    return null;
  }
}

function gravarLocalStorage(paineis) {
  try {
    localStorage.setItem(CHAVE_LOCAL, JSON.stringify(paineis));
  } catch {
    // localStorage indisponivel (aba anonima, storage cheio etc.) — sem
    // problema, o backend ainda guarda a copia "oficial" em disco
  }
}

export function useLayout(layoutPadrao) {
  const [paineis, setPaineis] = useState(layoutPadrao);
  const [status, setStatus] = useState("idle"); // idle | salvando | salvo | erro

  // refs (nao disparam re-render) usados so pelo mecanismo de autosave —
  // ver comentario no topo do arquivo.
  const carregadoRef = useRef(false);
  const ultimoPersistidoRef = useRef(null);

  useEffect(() => {
    let cancelado = false;
    (async () => {
      let salvo = null;
      try {
        const doBackend = await api.layout.obter();
        if (doBackend && doBackend.paineis && Object.keys(doBackend.paineis).length > 0) {
          salvo = doBackend.paineis;
        }
      } catch {
        // api_server.py fora do ar — segue pro fallback local sem quebrar
      }
      if (!salvo) salvo = lerLocalStorage();
      if (cancelado) return;

      // mescla com o padrao: um painel novo (adicionado depois de um layout
      // salvo antigo) nasce na posicao padrao em vez de sumir da tela por
      // nao ter entrada salva
      const final = salvo ? { ...layoutPadrao, ...salvo } : layoutPadrao;
      if (salvo) setPaineis(final);

      // marca esse `final` como "ja salvo" ANTES de liberar o autosave, pra
      // ele nao regravar o mesmo conteudo que acabou de ser carregado (ver
      // comentario no topo do arquivo)
      ultimoPersistidoRef.current = JSON.stringify(final);
      carregadoRef.current = true;
    })();
    return () => {
      cancelado = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const definirPainel = useCallback((id, valor) => {
    setPaineis((atual) => ({ ...atual, [id]: valor }));
  }, []);

  // traz o painel pro topo da pilha visual (z-index maior que todos os
  // outros) — chamado no mousedown do Panel.jsx, antes mesmo de mover 1px,
  // pra ele nunca ficar "preso atras" de um painel declarado depois dele.
  const trazerParaFrente = useCallback((id) => {
    setPaineis((atual) => {
      const maiorZ = Math.max(0, ...Object.values(atual).map((p) => p.z || 0));
      if ((atual[id]?.z || 0) === maiorZ && maiorZ > 0) return atual; // ja esta no topo
      return { ...atual, [id]: { ...atual[id], z: maiorZ + 1 } };
    });
  }, []);

  // grava paineis em localStorage + backend. `forcar` ignora a deduplicacao
  // (usado pelo clique manual em "Salvar layout" — o usuario clicou, espera
  // ver "salvando... / salvo", mesmo que nada tenha mudado desde o ultimo
  // autosave).
  const persistir = useCallback((atual, { forcar = false } = {}) => {
    const chave = JSON.stringify(atual);
    if (!forcar && chave === ultimoPersistidoRef.current) return; // nada mudou de fato — evita post e piscada de status a toa
    ultimoPersistidoRef.current = chave;
    setStatus("salvando");
    gravarLocalStorage(atual);
    api.layout
      .salvar({ paineis: atual })
      .then(() => setStatus("salvo"))
      .catch(() => setStatus("erro")) // local ja gravou — so o backend falhou
      .finally(() => setTimeout(() => setStatus("idle"), 2500));
  }, []);

  const salvar = useCallback(() => {
    setPaineis((atual) => {
      persistir(atual, { forcar: true });
      return atual;
    });
  }, [persistir]);

  // autosave: qualquer mudanca em `paineis` (mover, redimensionar, trazer
  // pra frente) agenda uma gravacao ~900ms depois da ultima mudanca. Trava
  // ate o carregamento inicial terminar (carregadoRef) — ver comentario no
  // topo do arquivo.
  useEffect(() => {
    if (!carregadoRef.current) return undefined;
    const timer = setTimeout(() => persistir(paineis), ATRASO_AUTOSAVE_MS);
    return () => clearTimeout(timer);
  }, [paineis, persistir]);

  return { paineis, definirPainel, trazerParaFrente, salvar, status };
}
