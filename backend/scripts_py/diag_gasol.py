"""
Nome do script : diag_gasol.py
Descricao      : Diagnostico PONTUAL (nao faz parte do main.py) — pedido do
                  usuario: "o contrato Gasol que salvou foi o de setembro e
                  nao o de outubro que e o que esta valendo, sera que tem
                  erro na logica do script que monta o config.json?".

                  Reproduz EXATAMENTE a checagem que resolver_raiz_americano()
                  (vigente.py) faz pra decidir entre GasolSep26/GasolOct26 —
                  symbol_select + symbol_info (last/time) + copy_rates D1
                  (recencia) — pra descobrir se:
                    a) o symbol GasolOct26 nem existe ainda na corretora internacional
                       (a corretora ainda nao criou o mes novo — comportamento
                       documentado no proprio vigente.py pra essa familia,
                       NAO seria bug), ou
                    b) o symbol existe e tem preco real, mas o
                       _tem_preco_real() do vigente.py falhou por timing de
                       sincronizacao (Gasol e raiz nova, nunca foi
                       selecionada antes — TENTATIVAS_SYNC=3 / PAUSA_SYNC=1s
                       pode nao ser suficiente na PRIMEIRA vez, seria bug/
                       ajuste de parametro).

                  Testa GasolSep26, GasolOct26 e GasolNov26 (por seguranca,
                  caso a corretora ja tenha pulado pra frente). Usa MAIS
                  tentativas de sincronizacao que o vigente.py (10x, 1s cada)
                  pra separar timing de "nao existe mesmo".

                  Grava em backend/json/diag_gasol.json e imprime na tela.
Versao          : 1.0.0 (diagnostico descartavel, sem entrada em versoes/)
"""

import datetime
import json
import sys
import time
from pathlib import Path

import MetaTrader5 as mt5

RAIZ = Path(__file__).resolve().parent.parent
CONFIG_PATH = RAIZ / "json" / "config.json"
SAIDA_PATH = RAIZ / "json" / "diag_gasol.json"

NOME_MES = {1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "May", 6: "Jun",
            7: "Jul", 8: "Aug", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec"}

RECENCIA_MAX_DIAS = 10
TENTATIVAS_SYNC = 10   # bem mais que as 3 do vigente.py, pra separar "nao existe" de "so nao sincronizou a tempo"
PAUSA_SYNC = 1.0

TICKERS = ["GasolSep26", "GasolOct26", "GasolNov26"]


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


def diagnosticar(ticker):
    resultado = {"ticker": ticker, "tentativas": []}

    existe_no_terminal = mt5.symbol_select(ticker, True)
    resultado["symbol_select_ok"] = existe_no_terminal
    if not existe_no_terminal:
        resultado["conclusao"] = "symbol NAO EXISTE no terminal (corretora ainda nao criou / nome errado)"
        return resultado

    for tentativa in range(1, TENTATIVAS_SYNC + 1):
        info = mt5.symbol_info(ticker)
        rates = mt5.copy_rates_from_pos(ticker, mt5.TIMEFRAME_D1, 0, 1)

        tem_last = info is not None and info.last not in (0, 0.0)
        tem_close_recente = False
        candle_time_str = None
        candle_close = None
        if rates is not None and len(rates) > 0:
            candle_time = datetime.datetime.fromtimestamp(int(rates[0]["time"]), tz=datetime.timezone.utc)
            candle_time_str = candle_time.isoformat()
            candle_close = float(rates[0]["close"])
            recente = (datetime.datetime.now(datetime.timezone.utc) - candle_time) <= datetime.timedelta(days=RECENCIA_MAX_DIAS)
            tem_close_recente = recente and rates[0]["close"] not in (0, 0.0)

        tem_preco_real = tem_last and tem_close_recente

        resultado["tentativas"].append(
            {
                "tentativa": tentativa,
                "last": info.last if info is not None else None,
                "bid": info.bid if info is not None else None,
                "ask": info.ask if info is not None else None,
                "session_close": info.session_close if info is not None else None,
                "session_open": info.session_open if info is not None else None,
                "time_tick": info.time if info is not None else None,
                "tem_last": tem_last,
                "candle_d1_time_utc": candle_time_str,
                "candle_d1_close": candle_close,
                "tem_close_recente": tem_close_recente,
                "tem_preco_real (igual ao vigente.py)": tem_preco_real,
            }
        )

        if tem_preco_real:
            resultado["conclusao"] = f"tem preco real na tentativa {tentativa} (vigente.py usa so 3 tentativas — {'BUG de timing' if tentativa > 3 else 'dentro do limite do vigente.py'})"
            return resultado

        time.sleep(PAUSA_SYNC)

    resultado["conclusao"] = f"symbol existe mas NAO teve preco real em {TENTATIVAS_SYNC} tentativas ({TENTATIVAS_SYNC}s) — parece nao estar realmente ativo/negociando ainda"
    return resultado


def main():
    cfg = carregar_config()
    conectar_corretora internacional(cfg)
    try:
        resultados = [diagnosticar(t) for t in TICKERS]
    finally:
        mt5.shutdown()

    saida = {"resultados": resultados}
    SAIDA_PATH.write_text(json.dumps(saida, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(saida, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    sys.exit(main())
