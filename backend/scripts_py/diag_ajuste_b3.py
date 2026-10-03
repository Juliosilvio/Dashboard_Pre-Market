"""
Nome do script : diag_ajuste_b3.py
Descricao      : Diagnostico PONTUAL (nao faz parte do main.py) — pesquisa
                  feita a pedido do usuario ("veja quais informacoes
                  precisamos pra calcular o ajuste"): o MT5 da corretora nacional NAO
                  publica preco de ajuste (session_price_settlement veio 0.0
                  pra Indice/Dolar, ver diag_ajuste.py/diag_ajuste_b3.md) e a
                  metodologia oficial da B3 (Manual de Aprecamento -
                  Futuros) exige dados de leilao/book que nao vem no feed de
                  varejo — entao a saida NAO e calcular o ajuste do zero, e
                  sim baixar o numero PRONTO que a B3 ja publica de graca.

                  Fonte: API publica "Up2Data" da B3 (mesma usada pelo
                  projeto open-source jmagomez/b3-derivatives-dashboard no
                  GitHub) — arquivo "TradeInformationConsolidatedFile",
                  documentado no PDF oficial da B3
                  "TradeInformationConsolidatedFileV3" (Catalogo UP2DATA).
                  Fluxo em 2 passos (a API nao devolve o CSV direto):
                    1) GET /api/download/requestname?fileName=...&date=...
                       -> JSON com {redirectUrl, token, file:{name,extension}}
                    2) GET a URL de download resolvida (o "~/" da
                       redirectUrl e relativo a /api/download/) -> CSV de
                       verdade.

                  Campos do CSV que interessam (nome oficial no layout):
                    TckrSymb   = ticker (ex: DOLARV26, INDICEV26)
                    AdjstdQt   = preco de ajuste do dia (o "ajuste atual")
                    RefPric    = preco de referencia (o "ajuste anterior",
                                 base pra calcular a variacao do dia — bate
                                 com a coluna "Ajuste de referencia" que
                                 aparece no Boletim Diario do Mercado em PDF)
                    LastPric   = preco de fechamento
                    TradAvrgPric, MinPric, MaxPric = medio/minimo/maximo

                  NAO SEI AINDA se o delimitador e ";" ou "," nem a
                  codificacao exata (a documentacao nao especifica) — o
                  script tenta detectar sozinho (csv.Sniffer) e, se nao
                  conseguir, salva uma amostra bruta em
                  backend/json/diag_ajuste_b3_raw_sample.txt pra
                  diagnosticar manualmente.

                  Filtra so os tickers que comecam com INDICE ou DOLAR (todos os
                  vencimentos em aberto) e grava o resultado em
                  backend/json/diag_ajuste_b3.json.
Versao          : 1.0.0 (diagnostico descartavel, sem entrada em versoes/)
"""

import csv
import io
import json
import sys
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urljoin

import requests

RAIZ = Path(__file__).resolve().parent.parent
SAIDA_JSON = RAIZ / "json" / "diag_ajuste_b3.json"
SAIDA_RAW_AMOSTRA = RAIZ / "json" / "diag_ajuste_b3_raw_sample.txt"

BASE_API = "https://arquivos.b3.com.br/api/download/"
PREFIXOS_INTERESSE = ("INDICE", "DOLAR")


def data_pregao_mais_recente():
    """O arquivo so fica pronto DEPOIS do fechamento do pregao (pedimos
    date=hoje e a B3 devolveu 400 Bad Request as 10h da manha, pregao ainda
    aberto) — entao o padrao e sempre o dia ANTERIOR, e ainda ajusta pra
    tras se cair em fim de semana. Nao considera feriado B3 (se cair em
    feriado, passa a data na mao: python diag_ajuste_b3.py AAAA-MM-DD)."""
    d = date.today() - timedelta(days=1)
    while d.weekday() >= 5:  # 5=sabado, 6=domingo
        d -= timedelta(days=1)
    return d


def pedir_url_download(data_str):
    resp = requests.get(
        urljoin(BASE_API, "requestname"),
        params={"fileName": "TradeInformationConsolidatedFile", "date": data_str},
        timeout=30,
    )
    resp.raise_for_status()
    dados = resp.json()
    redirect = dados.get("redirectUrl") or dados.get("token")
    if not redirect:
        raise RuntimeError(f"resposta sem redirectUrl/token: {dados}")
    redirect = redirect.lstrip("~/")
    return redirect, dados


def baixar_csv(caminho_redirect):
    """A doc nao deixa claro se o '~/' da redirectUrl e relativo a
    /api/download/ ou a raiz do site — primeira tentativa (BASE_API +
    caminho) deu 404, entao tenta uma lista de bases candidatas, na ordem,
    e usa a primeira que responder 200."""
    candidatas = [
        urljoin(BASE_API, caminho_redirect),
        urljoin("https://arquivos.b3.com.br/api/", caminho_redirect),
        urljoin("https://arquivos.b3.com.br/", caminho_redirect),
    ]
    erros = []
    for url in candidatas:
        try:
            resp = requests.get(url, timeout=60, allow_redirects=True)
            if resp.status_code == 200:
                print(f"(baixou de: {url})")
                return resp.content
            erros.append(f"{resp.status_code} em {url}")
        except requests.RequestException as e:
            erros.append(f"{e} em {url}")
    raise RuntimeError("nenhuma URL de download funcionou:\n" + "\n".join(erros))


def detectar_dialeto_e_ler(conteudo_bytes):
    for encoding in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            texto = conteudo_bytes.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise RuntimeError("nao consegui decodificar o CSV em nenhuma codificacao testada")

    amostra = texto[:2000]
    try:
        dialeto = csv.Sniffer().sniff(amostra, delimiters=";,|\t")
    except csv.Error:
        dialeto = csv.excel
        dialeto.delimiter = ";"

    leitor = csv.DictReader(io.StringIO(texto), dialect=dialeto)
    return leitor, texto, dialeto.delimiter


def num(valor):
    if valor is None or valor == "":
        return None
    try:
        return float(str(valor).replace(",", "."))
    except ValueError:
        return valor


def main():
    data_str = sys.argv[1] if len(sys.argv) > 1 else data_pregao_mais_recente().isoformat()

    caminho_redirect, resposta_pedido = pedir_url_download(data_str)
    conteudo = baixar_csv(caminho_redirect)

    try:
        leitor, texto_completo, delimitador = detectar_dialeto_e_ler(conteudo)
        linhas = list(leitor)
    except Exception as e:
        SAIDA_RAW_AMOSTRA.write_bytes(conteudo[:5000])
        print(f"ERRO ao interpretar o CSV ({e}); salvei uma amostra bruta em {SAIDA_RAW_AMOSTRA}")
        print(f"tamanho do arquivo baixado: {len(conteudo)} bytes")
        return 1

    campo_ticker = next((c for c in (linhas[0].keys() if linhas else []) if c and "Tckr" in c), "TckrSymb")

    encontrados = []
    for linha in linhas:
        ticker = (linha.get(campo_ticker) or "").strip()
        if ticker.startswith(PREFIXOS_INTERESSE):
            encontrados.append(
                {
                    "ticker": ticker,
                    "ajuste_atual (AdjstdQt)": num(linha.get("AdjstdQt")),
                    "ajuste_referencia_anterior (RefPric)": num(linha.get("RefPric")),
                    "fechamento (LastPric)": num(linha.get("LastPric")),
                    "medio (TradAvrgPric)": num(linha.get("TradAvrgPric")),
                    "minimo (MinPric)": num(linha.get("MinPric")),
                    "maximo (MaxPric)": num(linha.get("MaxPric")),
                    "linha_completa": linha,
                }
            )

    resultado = {
        "data_pedida": data_str,
        "arquivo_b3": resposta_pedido.get("file"),
        "delimitador_detectado": delimitador,
        "total_linhas_no_csv": len(linhas),
        "colunas_disponiveis": list(linhas[0].keys()) if linhas else [],
        "encontrados_indice_dolar": encontrados,
    }

    SAIDA_JSON.write_text(json.dumps(resultado, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(resultado, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
