"""
Nome do script : verificar_mt5stock.py
Descricao      : Diagnostico PONTUAL (nao faz parte do main.py) — mesmo
                  proposito de verificar_magnificas.py, agora apontado pro
                  terminal MT5 novo instalado direto do MQL5
                  (config.json -> connections.mt5stock, servidor
                  MetaQuotes-Demo) em vez da corretora internacional. Pedido do usuario
                  2026-09-26: "nesse terminal tem as acoes do nasdaq que
                  precisamos para arrumar a view" — antes de mexer em
                  historico.py/amplitude_universos, precisa confirmar QUAIS
                  acoes existem de verdade nesse servidor e com QUE NOME
                  exato (cada broker tem sua convencao de symbol).

                  Mesma logica de verificar_magnificas.py: pede o CATALOGO
                  INTEIRO de symbols (mt5.symbols_get(), sem filtro de
                  group nem de .visible), procura por PALAVRA INTEIRA
                  (nao substring — ver verificar_magnificas.py 1.1.0 pro
                  motivo, evita falso positivo tipo "meta" dentro de
                  "Metals") as 7 magnificas, E grava o catalogo INTEIRO
                  num .txt (mesmo se for muito maior que os 525 da
                  corretora internacional — servidor demo generico do MQL5 costuma ter
                  bem mais simbolo) pra dar pra conferir manualmente quais
                  categorias/paths existem (ex.: alguma pasta "US Shares"/
                  "NASDAQ"/similar) e pegar o nome exato de cada acao do
                  Nasdaq-100 que a gente for adicionar depois em
                  config.json -> amplitude_universos + historico.py.

                  Pedido extra do usuario (2026-09-26, mesma mensagem): "ve
                  se tem alguma acao ou ativo que reflete os juros
                  americanos treasurys tb" — alem das 7 magnificas, o
                  dicionario EMPRESAS ganhou uma entrada "Juros Americanos
                  (Treasury)" (t-bond/t-note/treasury/us10y/us30y/etc) pra
                  ver se esse servidor tem algum instrumento tipo isso.
                  Contexto: o projeto ja tem DUAS fontes de juros americano
                  hoje, nenhuma delas neste terminal novo — yeldcurve.py
                  (curva inteira 1M-30Y, via Excel/Power Query, nao MT5) e
                  UsaTB via corretora internacional (config.json -> ativos ->
                  vencimento_americano, usado por taxa_usatb.py). Este
                  diagnostico so verifica se o mt5stock TAMBEM tem algo do
                  tipo — nao substitui nenhuma das duas fontes atuais.

                  Grava relatorio em backend/json/diag_mt5stock.json e o
                  catalogo inteiro em backend/txt/catalogo_mt5stock.txt
                  (mesmo padrao de pastas do diagnostico da corretora internacional).
Versao          : 1.0.0 (diagnostico descartavel, sem entrada em versoes/)
"""

import json
import re
from pathlib import Path

import MetaTrader5 as mt5

RAIZ = Path(__file__).resolve().parent.parent
CONFIG_PATH = RAIZ / "json" / "config.json"
SAIDA_PATH = RAIZ / "json" / "diag_mt5stock.json"
SAIDA_TXT_PATH = RAIZ / "txt" / "catalogo_mt5stock.txt"

# palavras-chave por empresa — varias por empresa pra cobrir convencoes
# diferentes de nome (ticker curto, nome da empresa, apelido antigo tipo
# "Facebook" pro que hoje e "Meta").
EMPRESAS = {
    "Apple": ["apple", "aapl"],
    "Microsoft": ["microsoft", "msft"],
    "Alphabet / Google": ["alphabet", "google", "googl", "goog"],
    "Amazon": ["amazon", "amzn"],
    "Nvidia": ["nvidia", "nvda"],
    "Meta / Facebook": ["meta", "facebook", "fb.us", " fb "],
    "Tesla": ["tesla", "tsla"],
    # nao e uma das 7 magnificas - pedido extra do usuario (2026-09-26):
    "Juros Americanos (Treasury)": [
        "treasury", "t-bond", "tbond", "t-note", "tnote", "ultra bond",
        "us10y", "us30y", "us05y", "us02y", "usatb", "note", "bond",
    ],
}


def carregar_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def conectar_mt5stock(cfg):
    c = cfg["connections"]["mt5stock"]
    ok = mt5.initialize(
        path=c["path"],
        server=c["server"],
        login=c["login"],
        password=c["password"],
    )
    if not ok:
        raise RuntimeError(f"mt5.initialize falhou: {mt5.last_error()}")


def varrer_catalogo():
    """Catalogo INTEIRO do broker — mt5.symbols_get() sem argumento nenhum
    devolve TODOS os symbols que o servidor oferece, visiveis ou nao no
    Market Watch atual."""
    todos = mt5.symbols_get()
    if todos is None:
        raise RuntimeError(f"mt5.symbols_get() devolveu None: {mt5.last_error()}")
    return todos


def _bate_palavra_inteira(palavra, texto):
    """True so quando `palavra` aparece como palavra COMPLETA em `texto`
    (\b = fronteira de palavra) — evita falso positivo tipo "meta" dentro
    de "Metals" ou "Rheinmetall" (ver verificar_magnificas.py 1.1.0)."""
    return re.search(r"\b" + re.escape(palavra.strip()) + r"\b", texto) is not None


def encontrar_candidatos(todos):
    resultado = {empresa: [] for empresa in EMPRESAS}
    for s in todos:
        alvo = f"{s.name} {s.description} {s.path}".lower()
        for empresa, palavras in EMPRESAS.items():
            if any(_bate_palavra_inteira(p, alvo) for p in palavras):
                resultado[empresa].append({
                    "name": s.name,
                    "description": s.description,
                    "path": s.path,
                    "visible": bool(s.visible),
                })
    return resultado


def salvar_catalogo_txt(todos, caminho):
    """Grava TODO o catalogo num .txt, uma linha por symbol, ordenado por
    path (categoria do broker) depois name — mesmo padrao de
    verificar_magnificas.py, pra dar pra abrir e conferir a lista inteira
    manualmente (procurar a pasta de acoes americanas)."""
    caminho.parent.mkdir(parents=True, exist_ok=True)
    ordenados = sorted(todos, key=lambda s: (s.path, s.name))
    with open(caminho, "w", encoding="utf-8") as f:
        for s in ordenados:
            visivel = "visible=True" if s.visible else "visible=False"
            f.write(f"{s.name} | {s.description} | path={s.path} | {visivel}\n")


def main():
    cfg = carregar_config()
    conectar_mt5stock(cfg)
    try:
        todos = varrer_catalogo()
        print(f"[verificar_mt5stock] catalogo do MetaQuotes-Demo: {len(todos)} symbols no total\n")

        candidatos = encontrar_candidatos(todos)

        relatorio = {"total_symbols_broker": len(todos), "empresas": candidatos}
        with open(SAIDA_PATH, "w", encoding="utf-8") as f:
            json.dump(relatorio, f, ensure_ascii=False, indent=2)

        salvar_catalogo_txt(todos, SAIDA_TXT_PATH)

        for empresa, achados in candidatos.items():
            if not achados:
                print(f"{empresa}: NAO encontrado no catalogo do mt5stock")
                continue
            print(f"{empresa}: {len(achados)} candidato(s)")
            for a in achados:
                visivel = "visible=True (ja no Market Watch)" if a["visible"] else "visible=False (nao sincronizado agora)"
                print(f"   - {a['name']!r}  |  {a['description']}  |  path={a['path']}  |  {visivel}")
            print()

        print(f"[verificar_mt5stock] relatorio das 7 salvo em {SAIDA_PATH}")
        print(f"[verificar_mt5stock] catalogo completo ({len(todos)} symbols) salvo em {SAIDA_TXT_PATH}")
    finally:
        mt5.shutdown()


if __name__ == "__main__":
    main()
