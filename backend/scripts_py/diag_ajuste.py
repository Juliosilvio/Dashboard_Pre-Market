"""
Nome do script : diag_ajuste.py
Descricao      : Diagnostico PONTUAL (roda uma vez e termina, nao faz parte
                  do pipeline do main.py) — pedido original do usuario:
                  "consegue verificar se o MT5 da corretora nacional possui precos de
                  ajustes publicados?". A 1.0.0 so checava
                  session_price_settlement (veio 0.0 pros dois — corretora nacional NAO
                  publica ajuste por esse campo) e o usuario pediu, na
                  sequencia, TODOS os campos que a corretora nacional publica pra Indice e
                  Dolar (nomes literais usados pelo grade.py pra "nacionais",
                  ver comentario no grade.py) — em vez de so o recorte
                  session_price_settlement/close/open/bid/ask/last, agora
                  despeja o symbol_info()._asdict() INTEIRO (todos os ~90
                  campos que o MT5 expoe por symbol), sem filtrar nada.

                  Continua trazendo as ultimas barras diarias (D1) via
                  copy_rates_from_pos, so como contexto extra (nao faz parte
                  do que a corretora nacional "publica" no symbol_info em si).

                  Grava o resultado em backend/json/diag_ajuste.json (pra o
                  Claude ler depois, via device_bash, sem precisar que o
                  usuario copie/cole nada) E imprime na tela.
Versao          : 1.1.0 (diagnostico descartavel, sem entrada em versoes/)
"""

import json
import sys
from pathlib import Path

import MetaTrader5 as mt5

RAIZ = Path(__file__).resolve().parent.parent
CONFIG_PATH = RAIZ / "json" / "config.json"
SAIDA_PATH = RAIZ / "json" / "diag_ajuste.json"

SYMBOLS = ["Indice", "Dolar"]


def carregar_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def conectar_corretora_nacional(cfg):
    c = cfg["connections"]["corretora nacional"]
    ok = mt5.initialize(
        path=c["path"],
        server=c["server"],
        login=c["login"],
        password=c["password"],
    )
    if not ok:
        raise RuntimeError(f"mt5.initialize falhou: {mt5.last_error()}")


def diagnosticar_symbol(symbol):
    if not mt5.symbol_select(symbol, True):
        return {"symbol": symbol, "erro": f"symbol_select falhou: {mt5.last_error()}"}

    info = mt5.symbol_info(symbol)
    if info is None:
        return {"symbol": symbol, "erro": f"symbol_info retornou None: {mt5.last_error()}"}

    # TODOS os campos, sem filtrar nada (pedido do usuario) — cada valor
    # convertido pra tipo nativo do Python/JSON (o namedtuple do MT5 ja usa
    # int/float/str, entao na pratica isso so garante que nada de
    # bytes/enum escape pro json.dump).
    info_dict = {k: (v.decode() if isinstance(v, bytes) else v) for k, v in info._asdict().items()}

    d1 = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_D1, 0, 3)
    barras_d1 = []
    if d1 is not None:
        for barra in d1:
            barras_d1.append(
                {
                    "time_unix": int(barra["time"]),
                    "open": float(barra["open"]),
                    "high": float(barra["high"]),
                    "low": float(barra["low"]),
                    "close": float(barra["close"]),
                }
            )

    return {
        "symbol": symbol,
        "todos_os_campos_symbol_info": info_dict,
        "barras_d1_recentes (mais nova por ultimo)": barras_d1,
    }


def main():
    cfg = carregar_config()
    conectar_corretora_nacional(cfg)
    try:
        resultado = {"symbols": [diagnosticar_symbol(s) for s in SYMBOLS]}
    finally:
        mt5.shutdown()

    with open(SAIDA_PATH, "w", encoding="utf-8") as f:
        json.dump(resultado, f, ensure_ascii=False, indent=2)

    print(json.dumps(resultado, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    sys.exit(main())
