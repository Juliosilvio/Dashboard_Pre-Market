"""
Nome do script : verificar_magnificas.py
Descricao      : Diagnostico PONTUAL (nao faz parte do main.py) — pedido do
                  usuario: "consegue conectar no da corretora internacional ou gerar
                  algum relatorio que verifique se as sete magnificas
                  tambem estao cotadas la?".

                  Conecta na corretora internacional (mesma conexao compartilhada de
                  vigente.py/grade.py/historico.py — config.json ->
                  connections.corretora internacional) e pede o CATALOGO INTEIRO de
                  symbols do broker (mt5.symbols_get(), sem filtro de
                  group nem de .visible — bem mais amplo que a lista
                  curada do config.json ou o que ja esta sincronizado no
                  Market Watch). Pra cada symbol devolvido, junta
                  name + description + path (categoria/pasta do symbol
                  na arvore do broker) numa string e procura, sem
                  distinguir maiusculas/minusculas, palavras-chave de
                  cada uma das "Sete Magnificas": Apple, Microsoft,
                  Alphabet/Google, Amazon, Nvidia, Meta/Facebook, Tesla.

                  Nao precisa saber de antemao o nome exato que a
                  corretora internacional usa pro symbol (pode ser "Apple", "AAPL",
                  "US.APPLE", "Apple.us" etc, cada broker tem sua
                  convencao) — o catalogo INTEIRO e varrido, entao
                  qualquer nome/descricao que bata com a palavra-chave
                  aparece no relatorio.

                  Pra cada empresa das 7, mostra: se encontrou algum
                  symbol candidato (pode ser mais de um — ex: um CFD
                  fracionado E um normal), o name exato, description,
                  path (categoria) e se ja esta "visible" no Market
                  Watch (visible=False so significa que nao esta
                  sincronizado ainda no terminal AGORA — grade.py resolve
                  isso automaticamente se o symbol entrar na lista
                  curada do config.json; nao significa que a corretora
                  nao oferece o ativo).

                  Grava relatorio completo em
                  backend/json/diag_magnificas.json e imprime um resumo
                  legivel na tela.

                  v1.1.0 — pedido do usuario depois de ver o resultado (525
                  symbols, nenhuma das 7 encontrada de verdade): "muda o
                  script, pede pra listar os 525 ativos em um arquivo txt
                  msm salva aqui: D:\escritorio\projetos\dashboard\
                  backend\txt". Nova funcao salvar_catalogo_txt() grava TODO
                  o catalogo (nao so os candidatos das 7 empresas) em
                  backend/txt/catalogo_corretora internacional.txt, uma linha por
                  symbol, ordenado por path (categoria) depois name.

                  Tambem corrigido nesta versao: o matching por substring
                  ("meta" in texto) dava FALSO POSITIVO em "Metals" e
                  "Rheinmetall" (as duas palavras contem a sequencia de
                  letras "meta" no meio, sem ser a empresa Meta/Facebook) —
                  foi isso que fez o relatorio da v1.0.0 mostrar "Meta /
                  Facebook: 5 candidatos" quando na verdade eram so metais
                  (Palladium/GOLD/SILVER/Platinum) e uma acao alema
                  (Rheinmetall) sem relacao nenhuma. Trocado pra checagem
                  de PALAVRA INTEIRA (regex \b.\b), que so bate quando a
                  palavra-chave aparece sozinha no texto, nao dentro de
                  outra palavra maior.
Versao          : 1.1.0 (diagnostico descartavel, sem entrada em versoes/)
"""

import json
import re
from pathlib import Path

import MetaTrader5 as mt5

RAIZ = Path(__file__).resolve().parent.parent
CONFIG_PATH = RAIZ / "json" / "config.json"
SAIDA_PATH = RAIZ / "json" / "diag_magnificas.json"
SAIDA_TXT_PATH = RAIZ / "txt" / "catalogo_corretora internacional.txt"

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
}


def carregar_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def conectar_corretora internacional(cfg):
    c = cfg["connections"]["corretora internacional"]
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
    devolve TODOS os symbols que a corretora oferece, visiveis ou nao no
    Market Watch atual (diferente de last_int.py/_lista_desejada(), que
    filtra so .visible)."""
    todos = mt5.symbols_get()
    if todos is None:
        raise RuntimeError(f"mt5.symbols_get() devolveu None: {mt5.last_error()}")
    return todos


def _bate_palavra_inteira(palavra, texto):
    """True so quando `palavra` aparece como palavra COMPLETA em `texto`
    (\b = fronteira de palavra) — evita falso positivo tipo "meta" dentro
    de "Metals" ou "Rheinmetall" (que contem a sequencia de letras "meta"
    no meio, sem ser a empresa). re.escape() porque algumas palavras-chave
    tem espaco/ponto (" fb ", "fb.us")."""
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
    """Grava TODO o catalogo (os 525 symbols, nao so os candidatos das 7
    empresas) num .txt, uma linha por symbol, ordenado por path (categoria
    do broker) depois name — pedido do usuario depois de ver o relatorio
    resumido, pra poder abrir e conferir a lista inteira manualmente."""
    caminho.parent.mkdir(parents=True, exist_ok=True)
    ordenados = sorted(todos, key=lambda s: (s.path, s.name))
    with open(caminho, "w", encoding="utf-8") as f:
        for s in ordenados:
            visivel = "visible=True" if s.visible else "visible=False"
            f.write(f"{s.name} | {s.description} | path={s.path} | {visivel}\n")


def main():
    cfg = carregar_config()
    conectar_corretora internacional(cfg)
    try:
        todos = varrer_catalogo()
        print(f"[verificar_magnificas] catalogo da corretora internacional: {len(todos)} symbols no total\n")

        candidatos = encontrar_candidatos(todos)

        relatorio = {"total_symbols_broker": len(todos), "empresas": candidatos}
        with open(SAIDA_PATH, "w", encoding="utf-8") as f:
            json.dump(relatorio, f, ensure_ascii=False, indent=2)

        salvar_catalogo_txt(todos, SAIDA_TXT_PATH)

        for empresa, achados in candidatos.items():
            if not achados:
                print(f"{empresa}: NAO encontrado no catalogo da corretora internacional")
                continue
            print(f"{empresa}: {len(achados)} candidato(s)")
            for a in achados:
                visivel = "visible=True (ja no Market Watch)" if a["visible"] else "visible=False (nao sincronizado agora)"
                print(f"   - {a['name']!r}  |  {a['description']}  |  path={a['path']}  |  {visivel}")
            print()

        print(f"[verificar_magnificas] relatorio completo salvo em {SAIDA_PATH}")
        print(f"[verificar_magnificas] catalogo completo ({len(todos)} symbols) salvo em {SAIDA_TXT_PATH}")
    finally:
        mt5.shutdown()


if __name__ == "__main__":
    main()
