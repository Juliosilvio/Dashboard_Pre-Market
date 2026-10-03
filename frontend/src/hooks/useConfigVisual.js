// useConfigVisual.js — guarda preferencias de ESTILO dos graficos (nao
// confundir com useLayout.js, que guarda POSICAO/TAMANHO dos paineis). Nasceu
// do pedido do usuario: depois de tirar as bolinhas de cada vertice do
// JurosChart ("pode tirar essas bolinhas de todas as linhas do grafico?"),
// ele perguntou "como podemos salvar esse tipo de formato... um controller
// pra frontend tambem?" — ou seja, quer que essa escolha visual vire uma
// CONFIGURACAO persistida (nao so um valor fixo no codigo), do mesmo jeito
// que o layout dos paineis ja e.
//
// Mesmo padrao do useLayout.js: salva em DOIS lugares — localStorage (sempre,
// por navegador) e no backend via GET/POST /api/config-visual (json/config_
// visual.json em disco, ver api_server.py), pra sobreviver troca de
// navegador/maquina. Desde a v1.2.0 do client.js, o arquivo no backend e
// POR NAVEGADOR (?cliente=<id>), nao mais um so global — ver client.js.
// Ao carregar a pagina, tenta o backend primeiro e cai pro
// localStorage se a api_server.py estiver fora do ar; sem nenhum dos dois,
// fica no CONFIG_PADRAO (ver App.jsx).
//
// Diferenca de useLayout.js: aqui NAO tem botao "Salvar" explicito — cada
// campo e um toggle simples (ex: checkbox "Mostrar pontos" no cabecalho), sem
// o volume de eventos de um arrasto de mouse, entao "definir()" ja salva na
// hora (auto-save) em vez de exigir um clique separado.
//
// Formato do objeto salvo: { mostrarPontos: bool, ... } — qualquer novo
// campo de estilo (cor, espessura de linha, etc.) entra aqui do mesmo jeito,
// sem precisar de outro hook/endpoint.

import { useCallback, useEffect, useState } from "react";
import { api } from "../api/client.js";

const CHAVE_LOCAL = "config-visual-v1";

function lerLocalStorage() {
  try {
    const bruto = localStorage.getItem(CHAVE_LOCAL);
    return bruto ? JSON.parse(bruto) : null;
  } catch {
    return null;
  }
}

function gravarLocalStorage(config) {
  try {
    localStorage.setItem(CHAVE_LOCAL, JSON.stringify(config));
  } catch {
    // localStorage indisponivel (aba anonima, storage cheio etc.) — sem
    // problema, o backend ainda guarda a copia "oficial" em disco
  }
}

export function useConfigVisual(configPadrao) {
  const [config, setConfig] = useState(configPadrao);
  const [status, setStatus] = useState("idle"); // idle | salvando | salvo | erro

  useEffect(() => {
    let cancelado = false;
    (async () => {
      let salvo = null;
      try {
        const doBackend = await api.configVisual.obter();
        if (doBackend && Object.keys(doBackend).length > 0) {
          salvo = doBackend;
        }
      } catch {
        // api_server.py fora do ar — segue pro fallback local sem quebrar
      }
      if (!salvo) salvo = lerLocalStorage();
      if (!cancelado && salvo) {
        // mescla com o padrao: um campo novo (adicionado depois de uma
        // config salva antiga) nasce no valor padrao em vez de undefined
        setConfig((atual) => ({ ...atual, ...salvo }));
      }
    })();
    return () => {
      cancelado = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // muda UM campo e ja salva sozinho (local + backend) — sem botao "Salvar"
  // separado, porque cada campo aqui e um toggle discreto (um clique), nao
  // um arrasto continuo como o layout dos paineis.
  const definir = useCallback((chave, valor) => {
    setConfig((atual) => {
      const novo = { ...atual, [chave]: valor };
      gravarLocalStorage(novo);
      setStatus("salvando");
      api.configVisual
        .salvar(novo)
        .then(() => setStatus("salvo"))
        .catch(() => setStatus("erro")) // local ja gravou — so o backend falhou
        .finally(() => setTimeout(() => setStatus("idle"), 2000));
      return novo;
    });
  }, []);

  return { config, definir, status };
}
