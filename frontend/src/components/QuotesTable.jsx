// QuotesTable.jsx — tabela de cotacoes do mercado internacional
// (corretora internacional), alimentada por GET /api/last/int (que por sua vez le o
// double buffer last_int_a.json/last_int_b.json). Cada item vem no formato
// { broker, symbol, time, last, session_close } — mesmo shape gravado por
// last_int.py (session_close desde a v1.7.0).
//
// Pedido do usuario: "quero colocar as colunas em ordem, primeiro a coluna
// hora, coluna ativo, adicionar a coluna variação diaria, e por ultimo a
// coluna preço com celula piscante conforme mudança do preço, tambem quero
// organizar os tickers conforme o peso de cada um no indice e no dolar":
//   1) Ordem das colunas mudou de Ativo/Ultimo/Hora pra Hora/Ativo/
//      Variação/Preço.
//   2) Variação diária = (last - session_close) / session_close * 100 —
//      precisou do session_close novo no last_int.py 1.7.0 (antes so tinha
//      "last"). "--" quando faltar session_close (symbol sem esse dado, ou
//      last_int.py ainda rodando a versao antiga sem reiniciar).
//   3) Célula do preço pisca (verde subindo, vermelho descendo) por ~0.7s
//      quando o valor muda entre um poll e outro — anteriorRef guarda o
//      ultimo "last" visto de cada symbol (nao reseta a cada render, so
//      precisa comparar poll a poll); piscando guarda quem esta piscando
//      AGORA (limpo sozinho pelo setTimeout). Sem blink no primeiro
//      carregamento (anteriorRef comeca vazio, so registra o valor).
//   4) Ordenação por "peso" real no índice/dólar: pesos vem de
//      GET /api/peso-mercado (prop `pesos`, dict symbol -> {peso, ...}),
//      calculado pelo correl.py (correlação real contra Indice/Dolar, sem
//      filtro de limiar — ver correl.py 1.1.0/api_server.py 1.5.0). Ativo
//      sem peso calculado ainda (pipeline não rodou, ou correlação
//      não teve pontos suficientes) cai pro fim, ordem alfabética entre si
//      pra não ficar instável a cada poll.
//   5) Badges "Gi"/"Gd" ao lado do nome do ativo (2026-09-30, pedido do
//      usuário: "adicione nas tabelas de risk mesmo já existentes") —
//      causalidade de Granger "só um sentido" (causalidade.py, mesmo dict
//      `pesos`, chaves causa_indice/causa_dolar + _p/_lag). Diferente de
//      correlação: indica que o retorno PASSADO daquele ativo ajuda a
//      prever o Indice/Dolar de hoje, não só que andam juntos agora —
//      candidato a preditor antecedente.
//      2026-09-30 (v2): desacoplado do `grupo` do card — ANTES só
//      mostrava o badge do alvo do próprio card (Risk Dólar → só
//      causa_dolar, Risk Índice → só causa_indice), só que qual card o ativo
//      aparece é decidido por CORRELAÇÃO (correl.py, |correlacao_indice| vs
//      |correlacao_dolar|, ver separarIndiceDolar), uma métrica DIFERENTE e
//      independente da causalidade. Resultado: um ativo podia causar INDICE
//      no Granger mas morar na tabela Dólar por ter correlação mais forte
//      com o dólar — o achado ficava invisível, não aparecia em nenhuma
//      tabela. Agora cada linha checa causa_indice E causa_dolar direto,
//      pesos?.[symbol], independente de qual card/grupo está exibindo —
//      badge "Gi" (azul, --s-juros) quando causa_indice, badge "dg" (laranja,
//      --s-frc) quando causa_dolar, podem aparecer os dois juntos. Tooltip
//      de cada um mostra p-valor e lag. causalidade.py ainda não roda
//      automático no main.py (~1min de execução, D1 não muda a cada
//      5min) — badge só aparece depois de rodar o script manualmente pelo
//      menos uma vez.
//      2026-09-30 (v3): badge de 9px -> 16px (a célula do ativo usa
//      font-size 25px nesse projeto, pedido do usuário pra monitor
//      grande — 9px virava um pontinho ilegível, o usuário achou que a
//      causalidade "não aparecia" quando só estava pequena demais pra
//      ler, ver tokens.css). E o pedido principal dessa rodada: "adicione
//      o ativo na tabela do índice também, além da tabela que já
//      pertence... duplique se necessário" — o badge sozinho (v2) não
//      bastou, o usuário quer o ATIVO em si aparecendo nas duas tabelas
//      quando há causalidade cruzada, não só um indicador pequeno.
//      separarIndiceDolar() agora DUPLICA: além do agrupamento normal por
//      correlação, um ativo com causa_indice=True que mora no Dólar por
//      correlação também aparece no Índice (ordenado pelo p-valor da
//      causalidade, depois dos que estão lá por correlação de verdade) —
//      e vice-versa pra causa_dolar. Também corrigido: o texto "Gd" estava
//      sendo traduzido sozinho pelo tradutor de página do navegador do
//      usuário pra "Deus" ("Gd" é abreviação religiosa conhecida de
//      "God" em inglês) — badges agora têm class="notranslate" +
//      translate="no" (mantido como defesa extra), E o texto do badge de
//      dólar foi renomeado de "Gd" pra "dg" (pedido do usuário: "renomeie
//      Gd para dg assim o tradutor não traduz"), evitando a colisão de
//      vez. "Gi" não mudou (não colide com nada conhecido).
//      Legenda explicando "Gi"/"dg" e as cores: CausalidadeLegenda.jsx
//      (painel-causalidade-legenda em App.jsx), pedido do usuário:
//      "coloque um índice explicando o que é dg e gi... pode ser um card
//      novo".
//
// Pedido do usuario (depois de ver a tabela cortada num painel estreito,
// com barra de rolagem horizontal): "conforme eu estreito o box do painel
// quero que os ativos se empilhem um embaixo do outro" — antes o numero de
// colunas (3) era FIXO (so existia um breakpoint de media query baseado na
// largura da JANELA, @media max-width:900px em tokens.css — inutil aqui,
// porque o painel e redimensionado livremente por dentro da tela, ver
// Panel.jsx, e nao tem relacao nenhuma com o tamanho da janela). Agora o
// numero de colunas vem de `larguraDisponivel` (largura REAL do conteudo do
// painel, em px — o mesmo valor que o JurosChart ja recebe via o padrao de
// children-como-funcao do Panel.jsx, ver App.jsx): cada tabela de 4 colunas
// (Hora/Ativo/Variação/Preço) precisa de uns LARGURA_MIN_COLUNA px pra nao
// espremer, entao calcularNumColunas() divide a largura disponivel por isso
// e limita entre 1 (empilhado, painel estreito) e 3 (largura padrao do
// painel). O CSS grid usa esse numero via style inline (gridTemplateColumns)
// em vez do breakpoint fixo antigo.

import { useEffect, useMemo, useRef, useState } from "react";

const DURACAO_PISCA_MS = 700;
// largura minima confortavel pra uma tabela de 4 colunas (Hora/Ativo/
// Variação/Preço) nao espremer texto nem quebrar linha — abaixo disso as
// tabelas empilham (menos colunas) em vez de cortar.
const LARGURA_MIN_COLUNA = 340;
const MAX_COLUNAS = 3;

function calcularNumColunas(larguraDisponivel) {
  if (!larguraDisponivel) return 1; // sem medida ainda (ou modo mobile "fixo") — empilhado por seguranca
  return Math.max(1, Math.min(MAX_COLUNAS, Math.floor(larguraDisponivel / LARGURA_MIN_COLUNA)));
}

function formatarNumero(valor) {
  if (typeof valor !== "number") return String(valor ?? "--");
  // pedido do usuario: "ta sempre depois da virgula apenas 3 casas da pra
  // arrumar?" — antes variava por magnitude (>=1000 vira 2 casas, <1000
  // vira 5), o que so piorava o desalinhamento visual. Fixo em 3 pra TODO
  // ativo: casa com o alinhamento por partes (dividirNumeroFormatado) e
  // ainda da precisao suficiente pros pares de moeda (ex: 1,406).
  const casas = 3;
  return valor.toLocaleString("pt-BR", {
    minimumFractionDigits: casas,
    maximumFractionDigits: casas,
  });
}

// pedido do usuario: "temos precos com X.xxx,xx, XX,xx, X,xxx... como
// organizar pra ficar tudo alinhadinho?" — o problema nao e o alinhamento a
// direita (ja tinha, td.num) nem a fonte (ja e monoespacada, tabular-nums):
// e que cada ativo usa uma quantidade DIFERENTE de casas decimais
// (formatarNumero: >=1000 vira 2 casas, <1000 vira 5), entao a VIRGULA cai
// numa posicao horizontal diferente em cada linha. Solucao classica de mesa
// de operacoes: separar o numero ja formatado em "parte inteira" + "parte
// decimal" (a virgula entra junto da decimal) e renderizar cada pedaco no
// seu proprio <span>, com a parte inteira alinhada a direita numa largura
// minima fixa (ver .preco-parte-inteira em tokens.css) — isso trava a
// virgula sempre na mesma coluna visual, nao importa quantos digitos tem a
// parte inteira nem quantas casas decimais o ativo usa.
function dividirNumeroFormatado(textoFormatado) {
  const indiceVirgula = textoFormatado.lastIndexOf(",");
  if (indiceVirgula === -1) return { inteira: textoFormatado, decimal: "" };
  return {
    inteira: textoFormatado.slice(0, indiceVirgula),
    decimal: textoFormatado.slice(indiceVirgula),
  };
}

// pedido do usuario: "coluna variação com no máximo 3 casas após a vírgula"
// — separado do formatarNumero() do Preço (que usa 5 casas pra ativos com
// preço baixo tipo 1,14598) porque a Variação e sempre uma % pequena
// (tipicamente < 10%). Reduzido pra 2 casas em 2026-09-24 (pedido do
// usuario) — 3 casas deixava a string "+ 0,058%" comprida demais pra
// coluna, o que here em certas larguras de card dava espaco pro navegador
// quebrar linha bem no espaco entre o sinal e o numero (ver
// textoVariacao/textoVariacaoFuturo abaixo, que agora tambem usam espaco
// nao-quebravel pra isso nunca mais acontecer, e a classe .num que agora
// forca white-space: nowrap).
function formatarVariacao(valor) {
  if (typeof valor !== "number") return String(valor ?? "--");
  return valor.toLocaleString("pt-BR", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

// Correcao 2026-09-21 (pedido do usuario: "por que a coluna hora do display
// de cotacao nao aparece a hora daqui de Sao Paulo?"): a versao anterior so
// recortava o texto bruto do ISO (isoString.split("T")[1].slice(0,8)) — como
// o backend grava tudo em UTC (ver historico.py/fuso_horario.py), isso
// mostrava a hora UTC crua, 3h a frente do horario real de Sao Paulo (Brasil
// nao tem horario de verao desde 2019, entao o offset e sempre -3h fixo).
// Agora converte de verdade pro fuso America/Sao_Paulo via Intl, fixo
// independente do fuso do navegador de quem esta olhando a tela.
function formatarHora(isoString) {
  if (!isoString) return "--:--:--";
  const data = new Date(isoString);
  if (Number.isNaN(data.getTime())) return "--:--:--";
  return data.toLocaleTimeString("pt-BR", {
    timeZone: "America/Sao_Paulo",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

// variação diária em % — precisa de last E session_close numericos; sessao
// sem fechamento anterior (symbol novo, ou session_close ainda null) vira
// "--" no lugar de dividir por algo que nao existe.
function calcularVariacao(last, sessionClose) {
  if (typeof last !== "number" || typeof sessionClose !== "number" || sessionClose === 0) {
    return null;
  }
  return ((last - sessionClose) / sessionClose) * 100;
}

function dividirEmColunas(lista, numColunas) {
  const colunas = Array.from({ length: numColunas }, () => []);
  const porColuna = Math.ceil(lista.length / numColunas) || 1;
  lista.forEach((item, i) => {
    const idx = Math.min(Math.floor(i / porColuna), numColunas - 1);
    colunas[idx].push(item);
  });
  return colunas;
}

// pedido do usuario: "organizar os tickers conforme o peso de cada um no
// indice e no dolar" — peso vem do /api/peso-mercado (correlacao real,
// ver correl.py). Sem peso calculado ainda = -1 (vai pro fim), desempate
// alfabetico pra ordem ficar estavel entre polls.
// pedido do usuario: "mexer na coluna ativo pra ficar mais dentro do jargão
// de mercado" — a corretora internacional usa nomes proprios (UsaInd, UsaTec, Usa500,
// UsaVixOct26...) que ninguem do mercado fala assim. Mapeia por PREFIXO
// (startsWith, nao symbol exato) pra sobreviver ao rollover mensal dos
// futuros com vencimento (IndiceOct26 -> IndiceNov26 etc.), igual o
// simboloFuturo ja fazia. Symbol que nao bate com nenhum prefixo (a maioria
// dos pares de moeda, ouro etc.) fica como esta, sem apelido.
const APELIDOS_ATIVO = [
  { prefixo: "UsaInd", nome: "Dow Jones" },
  { prefixo: "UsaVix", nome: "VIX" },
  { prefixo: "UsaTec", nome: "Nasdaq" },
  { prefixo: "Usa500", nome: "S&P500" },
  { prefixo: "UsaRus", nome: "Russell" },
  { prefixo: "USDInd", nome: "DXY" },
  { prefixo: "Gasol", nome: "Gasolina" },
  // Brent tem DOIS instrumentos na grade: o continuo/CFD ("Brent", sem
  // vencimento — ver ATIVOS_EXATOS abaixo, pega antes deste prefixo) e o
  // contrato futuro com vencimento (ex: "BrentSep26" — cai aqui, ja que
  // symbol.startsWith("Brent") tambem bate nele). Pedido do usuario
  // (2026-09-24, depois de tirar a duplicata de meses no grade.py): "para a
  // tabela especifique o contrato vigente sempre como Brentfut e o spot CFD
  // como Brent" — pra nao confundir os dois na coluna Ativo.
  { prefixo: "Brent", nome: "Brentfut" },
  { prefixo: "Dolar", nome: "DolFut" },
  { prefixo: "Indice", nome: "IndFut" },
  // pedido do usuario: confirmou pela especificacao do contrato na
  // corretora ("UsaTBDec26, US Treasury Long Bond December 2026 CFD") que
  // NAO e T-Bill (juros curto prazo) — e o futuro classico de 30 anos do
  // Tesouro americano (CBOT/CME ticker ZB, apelidado no mercado de "the
  // Long Bond"). "T-Bond30Y" escolhido em vez de "ZB30Y" pra manter o
  // padrao dos outros apelidos (nome de mercado, nao ticker de bolsa).
  { prefixo: "UsaTB", nome: "T-Bond30Y" },
];

// symbol EXATO (nao prefixo) que tem apelido proprio, mesmo sem vencimento
// nenhum — hoje so o Brent spot/CFD continuo (ver comentario acima do
// Brentfut em APELIDOS_ATIVO). Checado ANTES da lista de prefixos: sem
// isso, "Brent" bateria no proprio startsWith("Brent") do Brentfut.
const APELIDOS_EXATOS = {
  Brent: "Brent",
};

function apelidoAtivo(symbol) {
  if (APELIDOS_EXATOS[symbol]) return APELIDOS_EXATOS[symbol];
  const encontrado = APELIDOS_ATIVO.find((a) => symbol.startsWith(a.prefixo));
  return encontrado ? encontrado.nome : symbol;
}

function ordenarPorPeso(cotacoes, pesos) {
  return [...cotacoes].sort((a, b) => {
    const pesoA = pesos?.[a.symbol]?.peso ?? -1;
    const pesoB = pesos?.[b.symbol]?.peso ?? -1;
    if (pesoB !== pesoA) return pesoB - pesoA;
    return a.symbol.localeCompare(b.symbol);
  });
}

// pedido do usuario: "quero configurar a coluna preço de forma que a leitura
// de risk on/off pra índice e dólar fique confortável" — na pratica pediu
// pra REORGANIZAR os ativos (nao colorir a celula), separando em dois
// grupos fixos "Puxa Índice" e "Puxa Dólar", usando a mesma correlacao real
// que ja alimentava ordenarPorPeso() (correlacao_indice/correlacao_dolar do
// /api/peso-mercado, ver correl.py). Cada ativo entra no grupo onde a
// correlacao ABSOLUTA e maior (ex: DXY correlaciona mais forte com DOLAR que
// com INDICE -> vai pro grupo Dolar; nao importa se a correlacao e positiva ou
// negativa, so a forca), ordenado dentro do grupo pela forca daquela
// correlacao (maior primeiro). Ativo sem peso calculado ainda (pipeline nao
// rodou / sem pontos suficientes) cai num terceiro grupo "Sem peso
// calculado", alfabetico — mesmo fallback que ja existia em ordenarPorPeso().
function separarIndiceDolar(cotacoes, pesos) {
  const indice = [];
  const dolar = [];
  const semPeso = [];

  (cotacoes ?? []).forEach((item) => {
    const p = pesos?.[item.symbol];
    const corIndice = p?.correlacao_indice;
    const corDolar = p?.correlacao_dolar;
    const temIndice = typeof corIndice === "number";
    const temDolar = typeof corDolar === "number";

    if (!temIndice && !temDolar) {
      semPeso.push(item);
      return;
    }

    const absIndice = temIndice ? Math.abs(corIndice) : -1;
    const absDolar = temDolar ? Math.abs(corDolar) : -1;

    if (absIndice >= absDolar) {
      indice.push({ item, forca: absIndice });
    } else {
      dolar.push({ item, forca: absDolar });
    }
  });

  indice.sort((a, b) => b.forca - a.forca);
  dolar.sort((a, b) => b.forca - a.forca);

  // pedido do usuario (2026-09-30, depois de ver o badge Gi no S&P500/
  // Nasdaq/VIX/Dow Jones sentados na tabela Dolar: "adicione o ativo na
  // tabela do indice tambem, alem da tabela que ja pertence... duplique
  // se necessario") — antes disso o ativo que Granger-causa o alvo do
  // OUTRO card (ex: S&P500 mora no Dolar por correlacao mas causa_indice=
  // True) so ganhava um badge "Gi" ali dentro, sem aparecer de verdade
  // na tabela Indice. Agora DUPLICA: o ativo passa a aparecer nas DUAS
  // tabelas -- a que ja pertence por correlacao (ordem normal, por
  // forca) E a do alvo que ele causa (ordem por p-valor da causalidade,
  // mais significativo primeiro, sempre DEPOIS dos que moram la por
  // correlacao de verdade). So duplica quem NAO esta la por correlacao
  // (jaNoIndice/jaNoDolar evita duplicar o USDRUB, que ja mora no Indice
  // E tem causa_dolar=True -- ele so aparece uma vez no Indice, com os
  // dois badges Gi+Gd, nao duplicado pro Dolar tambem). O badge Gi/Gd
  // continua aparecendo nas linhas duplicadas tambem, pra deixar claro
  // que a presenca ali e por causalidade, nao correlacao.
  const jaNoIndice = new Set(indice.map((x) => x.item.symbol));
  const jaNoDolar = new Set(dolar.map((x) => x.item.symbol));
  const duplicadosIndice = [];
  const duplicadosDolar = [];

  (cotacoes ?? []).forEach((item) => {
    const p = pesos?.[item.symbol];
    if (!p) return;
    if (p.causa_indice && !jaNoIndice.has(item.symbol)) {
      duplicadosIndice.push({ item, pValor: p.causa_indice_p ?? 1 });
    }
    if (p.causa_dolar && !jaNoDolar.has(item.symbol)) {
      duplicadosDolar.push({ item, pValor: p.causa_dolar_p ?? 1 });
    }
  });

  duplicadosIndice.sort((a, b) => a.pValor - b.pValor);
  duplicadosDolar.sort((a, b) => a.pValor - b.pValor);
  semPeso.sort((a, b) => a.symbol.localeCompare(b.symbol));

  return {
    indice: [...indice.map((x) => x.item), ...duplicadosIndice.map((x) => x.item)],
    dolar: [...dolar.map((x) => x.item), ...duplicadosDolar.map((x) => x.item)],
    semPeso,
  };
}

// generaliza a ideia acima pra um ativo de referencia EXTRA (fora do par
// indice/dolar, ex.: usatec/Nasdaq, ver ativos_referencia_extra em
// config.json). Aqui nao ha "dois grupos" pra separar, so UM ranking pela
// forca (absoluta) da correlacao daquele ativo contra o universo inteiro —
// coluna `correlacao_<nome>` que correl.py grava (self-exclusao do proprio
// ativo ja vem como null/NaN do backend, cai no fallback alfabetico junto
// dos que ainda nao tem correlacao calculada).
function ordenarPorCorrelacaoAbsoluta(cotacoes, pesos, coluna) {
  return [...(cotacoes ?? [])].sort((a, b) => {
    const corA = pesos?.[a.symbol]?.[coluna];
    const corB = pesos?.[b.symbol]?.[coluna];
    const temA = typeof corA === "number";
    const temB = typeof corB === "number";
    if (!temA && !temB) return a.symbol.localeCompare(b.symbol);
    if (!temA) return 1;
    if (!temB) return -1;
    const absA = Math.abs(corA);
    const absB = Math.abs(corB);
    if (absB !== absA) return absB - absA;
    return a.symbol.localeCompare(b.symbol);
  });
}

// pedido do usuario (depois de ver o card unico com 2 secoes empilhadas):
// "não gostei dessa configuração, pode montar duas tabelas ao invés de
// escrever Puxa em cada uma das tabelas? vou colocar uma ao lado da outra
// então a configuração de um card pode ser clonado pro outro mudando só os
// ativos" — em vez de UM QuotesTable com 2 grupos dentro, agora o
// componente vira parametrizavel: cada instancia mostra SO um grupo
// (`grupo="indice"` ou `grupo="dolar"`), com titulo proprio ("Risk Índice"/
// "Risk Dólar" por padrao, sobrescrevivel via `titulo`) — 2 cards/paineis
// separados no App.jsx, cada um arrastavel/redimensionavel
// independentemente (ver "painel-cotacoes" e "painel-cotacoes-dolar" la).
// Ativo "sem peso calculado" ainda (pipeline nao rodou / sem pontos
// suficientes pra correlacao) cai por padrao dentro do card Índice, pra nao
// sumir da tela sem precisar de um 3o card so pra isso.
// pedido do usuario: "ao lado de risk índice coloque futuro e coloque o
// valor que estiver no Indice, exclua da tabela risk índice a linha de
// cotação do indice" — o simbolo do Indice muda de mes em mes (rollover, ex.
// "IndiceOct26" -> "IndiceNov26", igual o Dolar ja fazia), entao o match e
// por PREFIXO (startsWith) em vez do symbol exato, pra nao quebrar no mes
// que vem. Generico via prop `simboloFuturo` (prefixo) + `rotuloFuturo`
// (texto do rotulo) pra poder reusar no card Risk Dólar com "Dolar" no
// futuro, se o usuario pedir.
export default function QuotesTable({
  cotacoes,
  pesos,
  larguraDisponivel,
  grupo = "indice",
  titulo,
  simboloFuturo,
  rotuloFuturo = "Futuro",
}) {
  const anteriorRef = useRef({}); // symbol -> ultimo "last" visto (entre polls)
  const [piscando, setPiscando] = useState({}); // symbol -> "up" | "down" enquanto pisca

  useEffect(() => {
    const mudancas = {};
    (cotacoes ?? []).forEach((item) => {
      const anterior = anteriorRef.current[item.symbol];
      if (anterior !== undefined && anterior !== item.last) {
        mudancas[item.symbol] = item.last > anterior ? "up" : "down";
      }
      anteriorRef.current[item.symbol] = item.last;
    });

    const symbols = Object.keys(mudancas);
    if (symbols.length === 0) return undefined;

    setPiscando((atual) => ({ ...atual, ...mudancas }));
    const timer = setTimeout(() => {
      setPiscando((atual) => {
        const copia = { ...atual };
        symbols.forEach((s) => delete copia[s]);
        return copia;
      });
    }, DURACAO_PISCA_MS);

    return () => clearTimeout(timer);
  }, [cotacoes]);

  const numColunas = useMemo(() => calcularNumColunas(larguraDisponivel), [larguraDisponivel]);
  const grupos = useMemo(() => separarIndiceDolar(cotacoes ?? [], pesos), [cotacoes, pesos]);
  const ativoFuturo = useMemo(() => {
    if (!simboloFuturo) return null;
    return (cotacoes ?? []).find((item) => item.symbol.startsWith(simboloFuturo)) ?? null;
  }, [cotacoes, simboloFuturo]);
  // pedido do usuario: expandir pra alem de indice/dolar (ex.: "usatec" pro
  // Nasdaq, ver ativos_referencia_extra em config.json) — grupo="indice" e
  // grupo="dolar" continuam usando a separacao mutuamente exclusiva de
  // sempre (2 paineis simultaneos, mesmo universo); qualquer OUTRO valor de
  // `grupo` vira um ranking simples pela correlacao_<grupo> daquele ativo,
  // sem precisar de nenhum codigo novo pro proximo ativo extra.
  const listaDoCard = useMemo(() => {
    let base;
    if (grupo === "dolar") {
      base = grupos.dolar;
    } else if (grupo === "indice") {
      base = [...grupos.indice, ...grupos.semPeso];
    } else {
      base = ordenarPorCorrelacaoAbsoluta(cotacoes ?? [], pesos, `correlacao_${grupo}`);
    }
    if (!simboloFuturo) return base;
    // tira da tabela o(s) ativo(s) que casam com o prefixo do futuro — ja
    // aparece destacado no cabecalho (ativoFuturo acima), nao precisa
    // duplicar como linha da tabela tambem. Pro caso "usatec", passar
    // simboloFuturo="UsaTec" tem o mesmo efeito: tira o proprio ativo alvo
    // da lista ranqueada (ele ja aparece em destaque no cabecalho).
    return base.filter((item) => !item.symbol.startsWith(simboloFuturo));
  }, [grupo, grupos, cotacoes, pesos, simboloFuturo]);
  const colunas = useMemo(() => dividirEmColunas(listaDoCard, numColunas), [listaDoCard, numColunas]);
  const tituloFinal =
    titulo ?? (grupo === "dolar" ? "Risk Dólar" : grupo === "indice" ? "Risk Índice" : grupo);

  // pedido do usuario: "adicione a variação também" — mesma conta de
  // variacao diaria (last vs session_close) que ja existe pra cada linha da
  // tabela, só que aplicada no ativoFuturo pra aparecer junto do badge do
  // cabecalho.
  const variacaoFuturo = ativoFuturo
    ? calcularVariacao(ativoFuturo.last, ativoFuturo.session_close)
    : null;
  const classeVariacaoFuturo =
    variacaoFuturo == null ? "muted" : variacaoFuturo >= 0 ? "delta-up" : "delta-down";
  const textoVariacaoFuturo =
    variacaoFuturo == null
      ? "--"
      : `${variacaoFuturo >= 0 ? "+" : "-"}\u00A0${formatarVariacao(Math.abs(variacaoFuturo))}%`;

  // titulo + badge "Futuro: <valor> <variação>" (quando simboloFuturo casar
  // com algum ativo) — extraido pra nao duplicar entre o estado vazio e o
  // normal.
  const linhaTitulo = (
    <div className="quotes-titulo-linha">
      <div className="chart-title">{tituloFinal}</div>
      {ativoFuturo && (
        <div className="quotes-futuro">
          <span className="quotes-futuro-label">{rotuloFuturo}</span>
          <span className="quotes-futuro-valor mono">{formatarNumero(ativoFuturo.last)}</span>
          <span className={`quotes-futuro-variacao mono ${classeVariacaoFuturo}`}>{textoVariacaoFuturo}</span>
        </div>
      )}
    </div>
  );

  if (!cotacoes || cotacoes.length === 0) {
    return (
      <div className="chart-card quotes-card">
        {linhaTitulo}
        <div className="chart-empty-msg" style={{ marginTop: 10 }}>
          sem dados — verifique se o last_int.py e o api_server.py estão rodando
        </div>
      </div>
    );
  }

  return (
    <div className="chart-card quotes-card">
      {linhaTitulo}
      <div className="quotes-grid" style={{ gridTemplateColumns: `repeat(${numColunas}, 1fr)`, marginTop: 16 }}>
        {colunas.map((coluna, i) => (
          <table key={i}>
            <thead>
              <tr>
                <th>Hora</th>
                <th>Ativo</th>
                <th className="num">Variação</th>
                <th className="num">Preço</th>
              </tr>
            </thead>
            <tbody>
              {coluna.map((item) => {
                const variacao = calcularVariacao(item.last, item.session_close);
                const classeVariacao = variacao == null ? "muted" : variacao >= 0 ? "delta-up" : "delta-down";
                const textoVariacao =
                  variacao == null ? "--" : `${variacao >= 0 ? "+" : "-"}\u00A0${formatarVariacao(Math.abs(variacao))}%`;
                const direcaoPisca = piscando[item.symbol];

                return (
                  <tr key={item.symbol}>
                    <td className="mono hora-muted">{formatarHora(item.time)}</td>
                    <td className="ativo-nome" title={item.symbol}>
                      {apelidoAtivo(item.symbol)}
                      {pesos?.[item.symbol]?.causa_indice && (
                        <span
                          className="causalidade-badge causalidade-badge-indice notranslate"
                          translate="no"
                          title={`Causalidade de Granger: o retorno passado deste ativo ajuda a prever o de Indice (p=${pesos[item.symbol].causa_indice_p}, lag=${pesos[item.symbol].causa_indice_lag} dia(s)) — so nesse sentido, nao o contrario. Nao e correlacao: e precedencia temporal (ver causalidade.py). Ainda experimental, revisar antes de confiar cegamente.`}
                        >
                          Gi
                        </span>
                      )}
                      {pesos?.[item.symbol]?.causa_dolar && (
                        <span
                          className="causalidade-badge causalidade-badge-dolar notranslate"
                          translate="no"
                          title={`Causalidade de Granger: o retorno passado deste ativo ajuda a prever o de Dolar (p=${pesos[item.symbol].causa_dolar_p}, lag=${pesos[item.symbol].causa_dolar_lag} dia(s)) — so nesse sentido, nao o contrario. Nao e correlacao: e precedencia temporal (ver causalidade.py). Ainda experimental, revisar antes de confiar cegamente.`}
                        >
                          dg
                        </span>
                      )}
                    </td>
                    <td className={`num mono ${classeVariacao}`}>{textoVariacao}</td>
                    {(() => {
                      const { inteira, decimal } = dividirNumeroFormatado(formatarNumero(item.last));
                      return (
                        <td
                          className={`num mono preco-celula ${
                            direcaoPisca ? `preco-pisca-${direcaoPisca}` : ""
                          }`}
                        >
                          <span className="preco-parte-inteira">{inteira}</span>
                          <span className="preco-parte-decimal">{decimal}</span>
                        </td>
                      );
                    })()}
                  </tr>
                );
              })}
            </tbody>
          </table>
        ))}
      </div>
    </div>
  );
}
