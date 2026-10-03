Historico de versoes — tree.py (antes gerar_arvore.py)
-------------------------------------------------------------------------
1.0.0 - 2026-09-13 - Julio - Criacao do script (classe GeradorArvore),
                              modo unico (padrao) e modo observador continuo
                              (--watch, via watchdog). Vivia em
                              scripts_py/gerar_arvore.py
1.1.0 - 2026-09-13 - Julio - Renomeado pra tree.py e movido pra raiz do
                              projeto. Corrige self.raiz: antes calculava
                              dois niveis acima do script (certo quando ele
                              vivia em scripts_py/), o que agora que ele esta
                              na raiz apontava pra pasta ACIMA de dashboard —
                              gerava/atualizava o ARQUITETURA_ARVORE.txt no
                              lugar errado e deixava o de dentro do projeto
                              desatualizado (por isso a arvore continuava
                              vindo com o conteudo antigo). Agora usa so um
                              nivel acima (pasta onde o script esta)
-------------------------------------------------------------------------
