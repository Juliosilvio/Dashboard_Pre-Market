"""
Nome do script : diag_symbol_select_mt5stock.py
Descricao      : Diagnostico PONTUAL (nao faz parte do main.py) — o
                  historico.py falhou symbol_select() pra TODAS as 103
                  acoes/ETFs configuradas (config.json ->
                  acoes_nasdaq100/treasury_etf_eua) no terminal mt5stock
                  (MetaQuotes-Demo), mesmo depois de reconectar (descartada
                  a hipotese de sincronizacao lenta) e mesmo com o usuario
                  confirmando manualmente que AAPL seleciona/negocia
                  normal pela propria janela Symbols do terminal
                  (Negociacao: Acesso completo). historico.py so imprime o
                  retorno BOOLEANO de symbol_select() ("symbol_select=
                  False") — nao imprime mt5.last_error(), que e o dado que
                  realmente explica O PORQUE. Este script conecta no
                  mt5stock e, pra uma amostra de symbols (AAPL primeiro —
                  o que o usuario ja confirmou funcionar na GUI — mais
                  alguns espalhados pela lista e os 3 ETFs de treasury),
                  imprime: mt5.account_info() (pra ver se e algo no NIVEL
                  DA CONTA, tipo trade_allowed geral), mt5.symbol_info()
                  ANTES de tentar selecionar (o terminal ja conhece esse
                  symbol? .select? .visible? .trade_mode? .path?), o
                  resultado de mt5.symbol_select(ticker, True),
                  mt5.last_error() IMEDIATAMENTE apos (o pedaco que
                  faltava), e mt5.symbol_info() DEPOIS (selecionou de
                  verdade, apesar do retorno?).
Versao          : 1.0.0 (diagnostico descartavel, sem entrada em versoes/)
"""

import json
from pathlib import Path

import MetaTrader5 as mt5

RAIZ = Path(__file__).resolve().parent.parent
CONFIG_PATH = RAIZ / "json" / "config.json"

# AAPL primeiro (confirmado manualmente pela GUI que funciona), mais
# alguns espalhados pela lista dos 100 (nao so os primeiros, pra ver se
# falha tudo ou so uma faixa) + os 3 ETFs de treasury.
AMOSTRA = ["AAPL", "MSFT", "NVDA", "TSLA", "META", "PEP", "XEL", "TLT", "IEF", "SHY"]


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


def descrever_info(info):
    if info is None:
        return "symbol_info() = None (terminal nao conhece esse symbol ainda)"
    return (
        f"select={info.select} visible={info.visible} "
        f"trade_mode={info.trade_mode} path={info.path!r} "
        f"bid={info.bid} ask={info.ask}"
    )


def main():
    cfg = carregar_config()
    conectar_mt5stock(cfg)
    try:
        print(f"[diag] account_info(): {mt5.account_info()}\n")
        print(f"[diag] terminal_info(): {mt5.terminal_info()}\n")

        for ticker in AMOSTRA:
            print(f"=== {ticker} ===")
            info_antes = mt5.symbol_info(ticker)
            print(f"  antes:  {descrever_info(info_antes)}")

            resultado = mt5.symbol_select(ticker, True)
            erro = mt5.last_error()
            print(f"  symbol_select(...) = {resultado}  |  last_error() = {erro}")

            info_depois = mt5.symbol_info(ticker)
            print(f"  depois: {descrever_info(info_depois)}")
            print()
    finally:
        mt5.shutdown()


if __name__ == "__main__":
    main()
