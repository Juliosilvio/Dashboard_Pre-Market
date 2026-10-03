"""
Nome do script : tree.py
Descricao      : Gera um mapa em formato arvore (tree) da estrutura de pastas
                  e arquivos do projeto dashboard, salvando em
                  tree.txt na raiz do projeto (a mesma pasta
                  onde o script fica). Modo padrao gera uma unica vez; com
                  --watch fica observando a pasta e regenera a arvore
                  automaticamente a cada mudanca (arquivo ou pasta criado,
                  apagado ou renomeado).
Autor          : Julio Cesar Silvio Campanhola
Criado em      : 2026-09-13
Ultima edicao  : 2026-09-13
Versao         : 1.1.0
Projeto        : dashboard
Historico      : scripts_py/versoes/tree.md
"""

import os
import sys
import time
from importlib import import_module

IGNORAR = {"venv", ".venv", "__pycache__", ".git", ".idea", ".vscode", "node_modules"}


class GeradorArvore:
    """
    Constroi e mantem atualizado um mapa em arvore (tree) da estrutura de
    pastas e arquivos do projeto.
    """

    def __init__(self, raiz=None, saida=None):
        # raiz padrao = pasta onde o proprio script esta (raiz do projeto)
        self.raiz = raiz or os.path.dirname(os.path.abspath(__file__))
        self.saida = saida or os.path.join(self.raiz, "tree.txt")

    def _listar(self, caminho):
        """Lista entradas de um diretorio, pastas primeiro, ordenado."""
        entradas = os.listdir(caminho)
        pastas = sorted(e for e in entradas if os.path.isdir(os.path.join(caminho, e)))
        arquivos = sorted(e for e in entradas if os.path.isfile(os.path.join(caminho, e)))
        return pastas, arquivos

    def _montar(self, caminho, prefixo=""):
        linhas = []
        pastas, arquivos = self._listar(caminho)
        itens = [(p, True) for p in pastas] + [(a, False) for a in arquivos]

        for i, (nome, eh_pasta) in enumerate(itens):
            ultimo = i == len(itens) - 1
            conector = "└── " if ultimo else "├── "
            sufixo = "/" if eh_pasta else ""
            linhas.append(f"{prefixo}{conector}{nome}{sufixo}")

            if eh_pasta:
                if nome in IGNORAR:
                    extensao = "    " if ultimo else "│   "
                    linhas.append(f"{prefixo}{extensao}└── (conteudo omitido)")
                    continue
                extensao = "    " if ultimo else "│   "
                linhas.extend(self._montar(os.path.join(caminho, nome), prefixo + extensao))

        return linhas

    def gerar(self):
        """Monta a arvore completa e retorna como string."""
        nome_raiz = os.path.basename(self.raiz.rstrip("\\/")) + "/"
        linhas = [nome_raiz] + self._montar(self.raiz)
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        cabecalho = f"Arquitetura do projeto — gerado automaticamente em {timestamp}\n\n"
        return cabecalho + "\n".join(linhas) + "\n"

    def salvar(self):
        """Gera a arvore e grava em disco."""
        conteudo = self.gerar()
        with open(self.saida, "w", encoding="utf-8") as f:
            f.write(conteudo)
        print(f"Arquitetura atualizada: {self.saida}")
        return conteudo

    def observar(self, intervalo_minimo=1.0):
        """
        Fica de olho na pasta do projeto e regenera a arvore sempre que algo
        muda. Requer a lib 'watchdog' (pip install watchdog).
        """
        try:
            watchdog_events = import_module("watchdog.events")
            watchdog_observers = import_module("watchdog.observers")
            FileSystemEventHandler = watchdog_events.FileSystemEventHandler
            Observer = watchdog_observers.Observer
        except ImportError as exc:
            raise ImportError(
                "O modo --watch precisa da lib watchdog. "
                "Instale com: pip install watchdog"
            ) from exc

        gerador = self
        saida_abs = os.path.abspath(self.saida)

        class Handler(FileSystemEventHandler):
            def __init__(self):
                self.ultima_execucao = 0.0

            def on_any_event(self, event):
                # ignora o proprio arquivo de saida, senao entra em loop
                if os.path.abspath(event.src_path) == saida_abs:
                    return
                agora = time.time()
                if agora - self.ultima_execucao < intervalo_minimo:
                    return
                self.ultima_execucao = agora
                gerador.salvar()

        self.salvar()
        observer = Observer()
        observer.schedule(Handler(), self.raiz, recursive=True)
        observer.start()
        print(f"Observando {self.raiz} — Ctrl+C para parar.")

        try:
            while True:
                time.sleep(intervalo_minimo)
        except KeyboardInterrupt:
            observer.stop()
        observer.join()


if __name__ == "__main__":
    gerador = GeradorArvore()

    if "--watch" in sys.argv:
        gerador.observar()
    else:
        gerador.salvar()
