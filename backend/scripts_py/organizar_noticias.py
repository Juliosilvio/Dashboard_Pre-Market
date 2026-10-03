"""
Nome do script : organizar_noticias.py
Descricao      : Organiza a analise de noticias em uma arvore de pastas por
                  data, dentro de backend/analise_noticias/, no formato
                  pedido pelo usuario (2026-09-27):

                      analise_noticias/AAAA/<mes por extenso>/Nasemana/
                          diaDD-MM-AAAA_<diadasemana>.csv

                  Exemplo: analise_noticias/2026/setembro/1asemana/
                           dia01-09-2026_segundafeira.csv

                  Definicao de "semana" (decisao explicita do usuario,
                  entre 3 opcoes oferecidas): BLOCOS FIXOS DE 7 DIAS
                  CORRIDOS do mes (1-7, 8-14, 15-21, 22-28, 29-31) — nao e
                  semana civil nem blocos de dias uteis. Motivo dado pelo
                  usuario: a analise vai cruzar o IMPACTO de noticias de
                  1/2/3/4/5 dias atras no intraday (day trade), com o que
                  ja existe no projeto, pra formar vies direcional — o
                  recorte por blocos fixos de 7 dias facilita esse tipo de
                  janela de lookback.

                  Formato do arquivo do dia: CSV (decisao do Claude, pedido
                  do usuario foi "voce decide, o que for mais leve e
                  atraente") — CSV foi escolhido por ser leve, legivel a
                  olho nu/Excel E facil de carregar depois com pandas pra
                  cruzar com as series MTF do projeto (parquet so compensa
                  em volume grande; um CSV por dia de noticias e pequeno).

                  Uma segunda etapa, ainda NAO implementada aqui (pedido do
                  usuario, 2026-09-27): importar um arquivo de historico de
                  conversas/noticias ja separado por data e reorganiza-lo
                  automaticamente nessa mesma arvore. Isso depende do
                  formato real desse arquivo (como as datas sao marcadas
                  nele) — ver aviso em importar_historico() abaixo.
Autor          : Julio Cesar Silvio Campanhola
Criado em      : 2026-09-27
Ultima edicao  : 2026-09-27
Versao         : 1.0.0
Projeto        : dashboard
Historico      : scripts_py/versoes/organizar_noticias.md
"""

import csv
import os
from datetime import date, datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ANALISE_NOTICIAS_DIR = os.path.join(BASE_DIR, "analise_noticias")

MESES_PT = {
    1: "janeiro", 2: "fevereiro", 3: "marco", 4: "abril",
    5: "maio", 6: "junho", 7: "julho", 8: "agosto",
    9: "setembro", 10: "outubro", 11: "novembro", 12: "dezembro",
}

DIAS_SEMANA_PT = {
    0: "segundafeira", 1: "tercafeira", 2: "quartafeira", 3: "quintafeira",
    4: "sextafeira", 5: "sabado", 6: "domingo",
}

EXTENSAO_PADRAO = "csv"
CABECALHO_CSV = ["data", "hora", "ativo_relacionado", "fonte", "manchete", "resumo", "impacto"]


def _para_date(data_ref):
    """Aceita date/datetime ou string 'AAAA-MM-DD' e devolve um date."""
    if isinstance(data_ref, datetime):
        return data_ref.date()
    if isinstance(data_ref, date):
        return data_ref
    if isinstance(data_ref, str):
        return datetime.strptime(data_ref, "%Y-%m-%d").date()
    raise TypeError(f"data_ref precisa ser date/datetime/str 'AAAA-MM-DD', recebi {type(data_ref)!r}")


def _bloco_semana(dia_do_mes: int) -> str:
    """Bloco fixo de 7 dias corridos do mes: 1-7, 8-14, 15-21, 22-28, 29-31."""
    indice = (dia_do_mes - 1) // 7 + 1  # 1..5
    return f"{indice}asemana"


def pasta_do_dia(data_ref) -> str:
    """
    Monta (e cria, se ainda nao existir) o caminho da pasta
    analise_noticias/AAAA/<mes>/Nasemana/ para a data informada.
    """
    data_ref = _para_date(data_ref)
    ano = str(data_ref.year)
    mes = MESES_PT[data_ref.month]
    semana = _bloco_semana(data_ref.day)
    caminho = os.path.join(ANALISE_NOTICIAS_DIR, ano, mes, semana)
    os.makedirs(caminho, exist_ok=True)
    return caminho


def caminho_arquivo_dia(data_ref, extensao: str = EXTENSAO_PADRAO) -> str:
    """
    Caminho completo do arquivo do dia (cria as pastas no caminho, mas nao
    cria o arquivo em si):
    analise_noticias/AAAA/<mes>/Nasemana/diaDD-MM-AAAA_<diadasemana>.<ext>
    """
    data_ref = _para_date(data_ref)
    pasta = pasta_do_dia(data_ref)
    data_str = data_ref.strftime("%d-%m-%Y")
    dia_semana = DIAS_SEMANA_PT[data_ref.weekday()]
    nome_arquivo = f"dia{data_str}_{dia_semana}.{extensao}"
    return os.path.join(pasta, nome_arquivo)


def adicionar_noticia(data_ref, hora="", ativo_relacionado="", fonte="", manchete="", resumo="", impacto=""):
    """
    Acrescenta uma linha de noticia ao CSV do dia (cria o arquivo com
    cabecalho se ainda nao existir). Uma noticia por linha — pode chamar
    varias vezes pro mesmo dia.
    """
    caminho = caminho_arquivo_dia(data_ref, "csv")
    arquivo_novo = not os.path.exists(caminho)
    data_ref_norm = _para_date(data_ref).strftime("%Y-%m-%d")
    with open(caminho, "a", newline="", encoding="utf-8") as f:
        escritor = csv.writer(f, delimiter=";")
        if arquivo_novo:
            escritor.writerow(CABECALHO_CSV)
        escritor.writerow([data_ref_norm, hora, ativo_relacionado, fonte, manchete, resumo, impacto])
    return caminho


def importar_historico(caminho_arquivo_origem, **kwargs):
    """
    AINDA NAO IMPLEMENTADO DE VERDADE.

    Ideia (pedido do usuario, 2026-09-27): receber um arquivo com um
    historico de conversas/noticias onde as series ja estao separadas por
    data, e reorganizar automaticamente cada trecho no arquivo do dia
    correto (via caminho_arquivo_dia). Isso e perfeitamente possivel, mas
    o jeito de separar por data varia demais de um arquivo pra outro
    (linha marcadora tipo "## 01/09/2026", coluna de data num CSV/JSON,
    timestamp no inicio de cada bloco, etc.) pra eu adivinhar sem ver o
    arquivo real — implementar isso "no escuro" arriscaria cortar as
    datas no lugar errado.

    Assim que o usuario mandar o arquivo (ou um trecho de exemplo), este
    corpo sera escrito pra reconhecer o padrao real e popular a arvore de
    pastas automaticamente.
    """
    raise NotImplementedError(
        "importar_historico() ainda depende de ver o arquivo real de "
        "exemplo pra saber como as datas estao marcadas nele."
    )
