"""
Nome do script : grade.py
Descricao      : Sincroniza a grade de cotacao (Market Watch) dos dois
                  terminais MT5 (corretora nacional e corretora internacional) pra mostrar SOMENTE os
                  tickers definidos em json/config.json — nada a mais, nada a
                  menos. A lista desejada e UNICA (todas as categorias de
                  ativos juntas: curva_br, vencimento_americano, nacionais,
                  indices_continuo, moedas_continuo, commodities_internacionais)
                  e e testada IGUAL nas duas corretoras — nao fica mais
                  fixo qual categoria e de qual broker, quem decide isso e o
                  proprio MT5: cada terminal so aceita (symbol_select) quem
                  existir de fato nele, o resto e reportado como "nao existe
                  nessa corretora" no resumo, sem derrubar o script. Raizes
                  com vencimento (curva_br, vencimento_americano) entram com
                  os tickers ja resolvidos em "vigentes"; as demais entram
                  com o nome literal do config (nacionais ainda nao passa
                  pelo vigente.py). Em cada terminal: symbol_select(nome,
                  False) em todo symbol visivel no Market Watch que NAO
                  estiver na lista desejada (remove); symbol_select(nome,
                  True) em todo ticker da lista desejada que ainda NAO
                  estiver visivel (adiciona). Um ticker que a corretora
                  recusa remover (posicao aberta, ordem pendente ou grafico
                  aberto) tambem so entra no resumo, nao derruba o script.

                  Correcao 1.2.0 (2026-09-24, usuario reparou duplicata na
                  tabela de cotacoes do frontend): curva_br e
                  vencimento_americano NAO usam mais a mesma regra. curva_br
                  continua pegando a lista INTEIRA de "vigentes" (vigente +
                  subsequentes) - sao os vertices da curva de juros, todos
                  tem que estar visiveis ao mesmo tempo. vencimento_americano
                  passa a pegar SO O PRIMEIRO ticker (o vigente/front) - e
                  commodity de contrato unico (Brent, Gasol, Indice, Dolar,
                  UsaVix, UsaRus, UsaTB, USDInd), sem curva nenhuma que
                  precise dos meses subsequentes visiveis; ate aqui pegava a
                  lista inteira igual curva_br, deixando por ex.
                  BrentSep26/Nov26/Dec26 todos visiveis ao mesmo tempo -
                  apareciam como 3 linhas "Brent" diferentes na tabela, cada
                  uma com o preco do seu mes. Nenhum consumidor do projeto usa
                  os meses subsequentes de vencimento_americano (correl.py,
                  p.ex., so usa candidatos[0] no CLUSTER_NACIONAL) - so pegar o
                  vigente resolve sem tirar nada que alguem precisasse.
Autor          : Julio Cesar Silvio Campanhola
Criado em      : 2026-09-15
Ultima edicao  : 2026-09-24
Versao         : 1.2.0
Projeto        : dashboard
Historico      : scripts_py/versoes/grade.md
"""

import importlib
import json
import os
import time

try:
    mt5 = importlib.import_module("MetaTrader5")
except ImportError as exc:
    raise ImportError(
        "A dependencia MetaTrader5 nao esta instalada. "
        "Instale-a com: pip install MetaTrader5"
    ) from exc
try:
    psutil = importlib.import_module("psutil")
except ImportError as exc:
    raise ImportError(
        "A dependencia psutil nao esta instalada. "
        "Instale-a com: pip install psutil"
    ) from exc


class SincronizadorGrade:
    """Deixa o Market Watch de cada terminal MT5 com exatamente os tickers do config.json."""

    def __init__(self, base_dir=None):
        self.base_dir = base_dir or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.config_path = os.path.join(self.base_dir, "json", "config.json")
        self.conexao = None

    def _carregar_config(self):
        with open(self.config_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def carregar_conexao(self, broker):
        config = self._carregar_config()
        self.conexao = config["connections"][broker]
        return self.conexao

    def _terminal_esta_aberto(self, exe_path):
        alvo = os.path.normcase(os.path.abspath(exe_path))
        for proc in psutil.process_iter(["exe"]):
            try:
                exe = proc.info.get("exe")
                if exe and os.path.normcase(os.path.abspath(exe)) == alvo:
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
        return False

    def _garantir_terminal_aberto(self, exe_path, espera_max=20):
        if self._terminal_esta_aberto(exe_path):
            return
        os.startfile(exe_path)
        for _ in range(espera_max):
            time.sleep(1)
            if self._terminal_esta_aberto(exe_path):
                time.sleep(3)
                return

    def conectar(self, broker):
        self.carregar_conexao(broker)
        self._garantir_terminal_aberto(self.conexao["path"])
        ok = mt5.initialize(
            path=self.conexao["path"],
            login=self.conexao["login"],
            password=self.conexao["password"],
            server=self.conexao["server"],
        )
        if not ok:
            raise RuntimeError(f"[{broker}] falha ao conectar: {mt5.last_error()}")

    def lista_desejada(self, config):
        """Lista UNICA com todas as categorias de ativos — a mesma pras duas
        corretoras. curva_br usa a lista INTEIRA de "vigentes" (vigente +
        subsequentes) — sao os vertices da curva de juros, todos tem que
        ficar visiveis ao mesmo tempo pros graficos de curva.
        vencimento_americano usa SO O PRIMEIRO ticker de "vigentes" (o
        vigente/front) — commodity de contrato unico, sem curva nenhuma que
        precise dos meses subsequentes (ver Correcao 1.2.0 no cabecalho do
        modulo). As demais categorias entram com o nome literal do config.
        Nao importa se um ticker so existe numa das corretoras: quem filtra
        isso e o symbol_select() dentro de sincronizar()."""
        ativos = config.get("ativos", {})
        vigentes = config.get("vigentes", {})

        desejados = []
        for categoria, raizes in ativos.items():
            if categoria == "curva_br":
                for raiz in raizes:
                    desejados.extend(vigentes.get(raiz, [raiz]))
            elif categoria == "vencimento_americano":
                for raiz in raizes:
                    desejados.append(vigentes.get(raiz, [raiz])[0])
            else:
                desejados.extend(raizes)
        return desejados

    def sincronizar(self, broker, desejados):
        desejados = set(desejados)
        visiveis = {s.name for s in mt5.symbols_get() if s.visible}

        removidos, falha_remover = [], []
        for nome in sorted(visiveis - desejados):
            if mt5.symbol_select(nome, False):
                removidos.append(nome)
            else:
                falha_remover.append(nome)

        adicionados, falha_adicionar = [], []
        for nome in sorted(desejados - visiveis):
            if mt5.symbol_select(nome, True):
                adicionados.append(nome)
            else:
                falha_adicionar.append(nome)

        print(f"[{broker}] grade desejada: {len(desejados)} tickers")
        print(f"[{broker}] removidos: {len(removidos)}"
              + (f" | nao foi possivel remover (posicao/ordem/grafico aberto?): {falha_remover}" if falha_remover else ""))
        print(f"[{broker}] adicionados: {len(adicionados)}"
              + (f" | nao existe nessa corretora: {falha_adicionar}" if falha_adicionar else ""))

        return {
            "removidos": removidos, "falha_remover": falha_remover,
            "adicionados": adicionados, "falha_adicionar": falha_adicionar,
        }

    def executar(self):
        config = self._carregar_config()
        desejados = self.lista_desejada(config)
        resultados = {}

        for broker in ("corretora nacional", "corretora internacional"):
            self.conectar(broker)
            resultados[broker] = self.sincronizar(broker, desejados)
            mt5.shutdown()

        return resultados


if __name__ == "__main__":
    SincronizadorGrade().executar()
