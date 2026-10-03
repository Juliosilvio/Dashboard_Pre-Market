"""
Nome do script : yeldcurve.py
Descricao      : Coleta a curva de juros dos treasurys americanos (yield
                  curve, 1M a 30Y) - insumo do "morning call" automatizado
                  discutido com o usuario (2026-09-23): o trader de
                  referencia usa o ratio 2Y/10Y (e o nivel do 5Y) como
                  leading indicator de forca do dolar, olhando um terminal
                  proprio (tipo Bloomberg). O projeto nao tem acesso a um
                  terminal desses.

                  HISTORICO RESUMIDO 1.0.0 -> 3.0.0 (tudo no mesmo dia,
                  2026-09-23 - cada versao tentou uma forma de ler
                  DIRETO da pagina do Investing.com e esbarrou num
                  bloqueio novo; detalhe completo no changelog):
                  1) v1.0.0 (urllib, GET simples) - HTTP 403 (bloqueio
                     anti-bot, cliente HTTP "seco" nao passa).
                  2) v2.0.0 (Playwright abrindo Chromium sozinho) - ficou
                     preso na tela "Executando verificacao de seguranca"
                     da Cloudflare (navigator.webdriver denuncia
                     automacao).
                  3) v2.1.0 (perfil persistente + Chrome real + flags de
                     disfarce) - nem chegou a carregar, timeout de 45s
                     esperando o evento "load".
                  4) v3.0.0 (conectar via CDP numa aba que o USUARIO ja
                     tinha aberto manualmente no proprio Chrome, ideia do
                     proprio usuario) - travou num problema mais basico
                     ainda: nao foi possivel nem estabelecer a conexao CDP
                     de forma confiavel (ECONNREFUSED persistente mesmo
                     depois de fechar todo processo do Chrome e usar
                     --user-data-dir dedicado) - troubleshooting parou
                     nesse ponto sem resolver.

                  DECISAO 4.0.0 (2026-09-23) - o usuario cortou o
                  problema pela raiz: "o excel pode ficar requisitando
                  la eu usava assim pra criar os graficos, por que nao le
                  o excel". Ele JA TINHA, antes de qualquer uma dessas
                  tentativas, uma solucao que funciona de verdade hoje:
                  `backend/excel/treasurys/yeldcurve.xlsx`, mantido
                  atualizado pelo Power Query do proprio Excel (Get Data),
                  configurado pra atualizar a cada 5 minutos - e o Excel
                  buscando a mesma pagina do Investing.com, mas sem
                  nenhum problema de bloqueio (o motor de rede do Power
                  Query passa numa boa onde Playwright/urllib nao
                  passaram).

                  Solucao: PARAR de tentar ler a pagina direto. Deixar o
                  Excel aberto fazendo o que ele ja faz bem (buscar e
                  atualizar), e o yeldcurve.py so LE o arquivo .xlsx
                  local a cada 5 minutos (mesmo ritmo do Power Query) e
                  republica no mesmo formato double-buffer JSON que o
                  resto do projeto ja usa (last_nac.py/last_int.py) -
                  pra quem consome os dados (o "morning call") nao ver
                  diferenca nenhuma de fonte. Zero requisicao de rede
                  feita pelo Python, zero risco de bloqueio - o Excel
                  continua sendo o unico que fala com a Investing, papel
                  que ele ja exercia direito antes da gente comecar a
                  mexer nisso.

                  REQUISITO (o mesmo de sempre, nao e novo): manter o
                  Excel aberto com yeldcurve.xlsx e o Power Query
                  atualizando (5 em 5 min) enquanto este script estiver
                  rodando. Sem isso, o arquivo para de mudar e o script
                  detecta e avisa (ver _checar_atraso).

                  Estrutura do xlsx (conferida na mao, 2026-09-23):
                  colunas B=Name, C=Yield, D=Prev., E=High, F=Low (todos
                  inteiros escalados por 1000 - ex: 4771 = 4.771% -
                  artefato de como o Power Query grava esses valores,
                  dividido aqui em _ler_planilha), G=Chg. (string tipo
                  "+0.012"), H=Chg. % (string tipo "+0.31%"), I=Time (as
                  vezes datetime.time do dia, as vezes datetime.datetime
                  de um dia anterior quando o instrumento nao negociou
                  hoje - tratado em _formatar_hora). Linhas 2 a 14, uma
                  por vencimento, sempre na mesma ordem (1M a 30Y).

                  IMPORTANTE - identificacao do vencimento por POSICAO,
                  nao pelo texto do nome (2026-09-23): percebemos que o
                  texto da coluna Name pode aparecer em ingles ("U.S.
                  1M") ou em portugues ("EUA a 1 mês") dependendo de qual
                  fonte/config o Power Query esta usando naquele momento -
                  o usuario mostrou print do Excel com nomes em portugues
                  enquanto o arquivo salvo em disco (o que este script le)
                  tinha nomes em ingles. Pra nao depender de qual idioma
                  esta ativo, a identificacao do vencimento usa a ORDEM
                  das linhas (sempre 1M, 2M, 3M, 4M, 6M, 1Y, 2Y, 3Y, 5Y,
                  7Y, 10Y, 20Y, 30Y, nessa sequencia - ver
                  ORDEM_VENCIMENTOS), nao o texto da celula B. O texto
                  original ainda e guardado no campo "nome_planilha" de
                  cada registro, so pra conferencia/depuracao.

                  Checagem de sanidade antes de gravar: yield tem que
                  estar numa faixa plausivel (0% a 20%); linha fora disso
                  e descartada sozinha (nao derruba a leitura inteira) -
                  mesmo espirito das versoes anteriores.

                  Double buffer - MESMO ESQUEMA de last_nac.py/last_int.py
                  (pedido explicito do usuario, 2026-09-23): a cada
                  leitura, grava em SO UM dos dois arquivos
                  (yeldcurve_amostra_a.json / yeldcurve_amostra_b.json),
                  alternando - o outro fica parado e completo, livre pra
                  qualquer leitor abrir sem disputar lock de escrita.
                  Escrita atomica dentro de cada lado (.tmp +
                  os.replace). Cada arquivo e uma "foto" da curva inteira
                  NAQUELE instante, sobrescrita a cada rodada - NAO
                  acumula historico.

                  Roda em loop continuo ate achar o arquivo de parada -
                  MESMO padrao/mesmo arquivo que last_nac.py/last_int.py
                  ja usam (parquet/historicos/_stop_last.flag).
Autor          : Julio Cesar Silvio Campanhola
Criado em      : 2026-09-23
Ultima edicao  : 2026-09-23
Versao         : 4.0.0
Projeto        : dashboard
Historico      : scripts_py/versoes/yeldcurve.md
"""

import datetime as dt
import importlib
import json
import os
import time

try:
    openpyxl = importlib.import_module("openpyxl")
except ImportError as exc:
    raise ImportError(
        "A dependencia openpyxl nao esta instalada. "
        "Instale-a com: python -m pip install openpyxl"
    ) from exc


CAMINHO_XLSX_RELATIVO = os.path.join("excel", "treasurys", "yeldcurve.xlsx")

# Mesmo ritmo do Power Query do Excel (5 em 5 minutos) - decisao
# explicita do usuario (2026-09-23): nao adianta ler mais rapido que
# isso, o arquivo so muda quando o Excel atualiza.
INTERVALO_SEGUNDOS = 5 * 60

# Linha onde comecam os vencimentos (linha 1 = cabecalho: Name, Yield,
# Prev., High, Low, Chg., Chg. %, Time - conferido na mao, 2026-09-23).
LINHA_INICIAL = 2
COL_NAME, COL_YIELD, COL_PREV, COL_HIGH, COL_LOW, COL_CHG, COL_CHG_PCT, COL_TIME = 2, 3, 4, 5, 6, 7, 8, 9

# Ordem fixa das linhas na planilha (linha 2 = 1M, linha 3 = 2M, ...) -
# usada pra identificar o vencimento por POSICAO em vez do texto da
# coluna Name, que pode vir em ingles ou portugues dependendo da fonte
# que o Power Query estiver usando (ver docstring do modulo). Se um dia
# aparecer mais linhas que isso, sao ignoradas com aviso (nao quebra).
ORDEM_VENCIMENTOS = ["1M", "2M", "3M", "4M", "6M", "1Y", "2Y", "3Y", "5Y", "7Y", "10Y", "20Y", "30Y"]

YIELD_MIN_PCT = 0.0
YIELD_MAX_PCT = 20.0

# Se o arquivo xlsx nao mudar de mtime por mais que isso, o Excel
# provavelmente parou de atualizar (fechado, Power Query travado, etc.) -
# so avisa uma vez ate voltar a mudar, nao fica repetindo toda rodada.
ATRASO_AVISO_SEGUNDOS = 20 * 60


class ColetorYeldCurve:
    """Le periodicamente o arquivo excel/treasurys/yeldcurve.xlsx
    (mantido atualizado pelo Power Query do proprio Excel, que o usuario
    deixa aberto) e republica a leitura mais recente em double buffer
    (amostra_a/amostra_b), igual last_nac.py/last_int.py. Nao faz NENHUMA
    requisicao de rede - ver docstring do modulo pra racional completo
    (por que abandonamos ler a pagina direto)."""

    def __init__(self, base_dir=None):
        self.base_dir = base_dir or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.caminho_xlsx = os.path.join(self.base_dir, CAMINHO_XLSX_RELATIVO)
        saida_dir = os.path.join(self.base_dir, "json", "last_json")
        self.saida_path_a = os.path.join(saida_dir, "yeldcurve_amostra_a.json")
        self.saida_path_b = os.path.join(saida_dir, "yeldcurve_amostra_b.json")
        self.stop_flag_path = os.path.join(self.base_dir, "parquet", "historicos", "_stop_last.flag")
        os.makedirs(saida_dir, exist_ok=True)
        self._proximo_arquivo = "a"
        self._ultimo_mtime = None
        self._momento_ultimo_mtime = None
        self._avisado_atraso = False

    # ---------- leitura do xlsx ----------

    @staticmethod
    def _numero_escalado(valor):
        """Colunas Yield/Prev./High/Low vem como inteiro escalado por
        1000 (ex: 4771 -> 4.771%) - artefato de como o Power Query grava
        esses valores neste arquivo especifico. Devolve None se nao for
        numero."""
        if valor is None:
            return None
        try:
            return float(valor) / 1000.0
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _numero_texto(valor):
        """Converte texto tipo '+0.012' ou '-0.31%' num float. Aceita
        tambem o valor ja vir como numero (caso a formatacao da celula
        mude no futuro)."""
        if valor is None:
            return None
        if isinstance(valor, (int, float)):
            return float(valor)
        texto = str(valor).strip().replace("%", "")
        if texto in ("", "-", "—"):
            return None
        try:
            return float(texto)
        except ValueError:
            return None

    @staticmethod
    def _formatar_hora(valor):
        """Coluna Time vem as vezes como horario do dia (datetime.time),
        as vezes como um datetime completo representando um dia anterior
        (quando o instrumento nao negociou hoje - o Excel/Investing
        mostra so a data nesse caso, tipo '22-set')."""
        if isinstance(valor, dt.datetime):
            return valor.strftime("%Y-%m-%d")
        if isinstance(valor, dt.time):
            return valor.strftime("%H:%M:%S")
        return str(valor) if valor is not None else ""

    def _ler_planilha(self):
        """Abre o xlsx (so leitura, data_only=True pra pegar o valor
        calculado e nao a formula) e devolve uma lista de linhas
        validadas. Tolerante: pagina/arquivo ausente ou corrompido nao
        derruba o processo, so avisa e devolve lista vazia."""
        if not os.path.exists(self.caminho_xlsx):
            print(f"yeldcurve: arquivo nao encontrado ({self.caminho_xlsx}) - Excel esta aberto e salvando nesse caminho?")
            return []

        try:
            wb = openpyxl.load_workbook(self.caminho_xlsx, data_only=True, read_only=True)
            ws = wb.active
        except Exception as exc:
            print(f"yeldcurve: nao consegui abrir o xlsx ({exc}) - pode estar sendo salvo agora pelo Excel, tento de novo no proximo ciclo")
            return []

        linhas = []
        try:
            for offset, vencimento in enumerate(ORDEM_VENCIMENTOS):
                linha_idx = LINHA_INICIAL + offset
                nome_planilha = ws.cell(row=linha_idx, column=COL_NAME).value
                if nome_planilha is None or str(nome_planilha).strip() == "":
                    print(f"yeldcurve: linha {linha_idx} (esperava {vencimento}) esta vazia - parando leitura aqui")
                    break

                yield_pct = self._numero_escalado(ws.cell(row=linha_idx, column=COL_YIELD).value)
                if yield_pct is None:
                    print(f"yeldcurve: nao consegui ler o yield de {vencimento} (linha {linha_idx}, '{nome_planilha}') - linha ignorada")
                    continue
                if not (YIELD_MIN_PCT <= yield_pct <= YIELD_MAX_PCT):
                    print(f"yeldcurve: yield de {vencimento} fora da faixa plausivel ({yield_pct}) - linha descartada")
                    continue

                linhas.append({
                    "vencimento": vencimento,
                    "nome_planilha": str(nome_planilha).strip(),
                    "yield_pct": yield_pct,
                    "prev_pct": self._numero_escalado(ws.cell(row=linha_idx, column=COL_PREV).value),
                    "high_pct": self._numero_escalado(ws.cell(row=linha_idx, column=COL_HIGH).value),
                    "low_pct": self._numero_escalado(ws.cell(row=linha_idx, column=COL_LOW).value),
                    "chg": self._numero_texto(ws.cell(row=linha_idx, column=COL_CHG).value),
                    "chg_pct": self._numero_texto(ws.cell(row=linha_idx, column=COL_CHG_PCT).value),
                    "hora_pagina_raw": self._formatar_hora(ws.cell(row=linha_idx, column=COL_TIME).value),
                })

            faltando = set(ORDEM_VENCIMENTOS) - {linha["vencimento"] for linha in linhas}
            if faltando:
                print(f"yeldcurve: vencimentos nao lidos nesta rodada: {sorted(faltando)}")
        finally:
            wb.close()

        if not linhas:
            print("yeldcurve: nenhuma linha valida encontrada no xlsx nesta leitura")

        return linhas

    def _checar_atraso(self):
        """Compara o mtime atual do xlsx com o ultimo visto - se ficar
        parado por mais que ATRASO_AVISO_SEGUNDOS, avisa (uma vez so,
        ate o arquivo voltar a mudar) que o Excel pode ter parado de
        atualizar."""
        try:
            mtime_atual = os.path.getmtime(self.caminho_xlsx)
        except OSError:
            return

        agora = time.time()
        if self._ultimo_mtime is None or mtime_atual != self._ultimo_mtime:
            self._ultimo_mtime = mtime_atual
            self._momento_ultimo_mtime = agora
            self._avisado_atraso = False
            return

        if not self._avisado_atraso and (agora - self._momento_ultimo_mtime) > ATRASO_AVISO_SEGUNDOS:
            minutos = int((agora - self._momento_ultimo_mtime) / 60)
            print(f"yeldcurve: o xlsx nao muda ha {minutos} min - o Excel/Power Query pode ter parado de atualizar")
            self._avisado_atraso = True

    # ---------- persistencia (double buffer, igual last_nac.py) ----------

    def _flush_atual(self, linhas, momento):
        """Grava a foto da curva inteira (uma entrada por vencimento) no
        lado 'a' ou 'b', alternando - nunca no mesmo lado que acabou de
        gravar. Escrita atomica (.tmp + os.replace) dentro de cada lado.
        Nao acumula historico - ver docstring do modulo."""
        if not linhas:
            print("yeldcurve: nenhuma linha valida nesta leitura - nada gravado")
            return 0

        registros = [dict(linha, timestamp_coleta=momento.isoformat()) for linha in linhas]

        alvo = self.saida_path_a if self._proximo_arquivo == "a" else self.saida_path_b
        tmp_path = alvo + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(registros, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, alvo)
        self._proximo_arquivo = "b" if self._proximo_arquivo == "a" else "a"

        print(f"yeldcurve: {len(registros)} vencimento(s) atualizados -> {os.path.basename(alvo)}")
        return len(registros)

    # ---------- orquestracao ----------

    def executar(self):
        print(f"yeldcurve: lendo {self.caminho_xlsx} a cada {INTERVALO_SEGUNDOS // 60}min")
        print(f"yeldcurve: rodando continuamente (crie {self.stop_flag_path} pra encerrar)")

        try:
            while not os.path.exists(self.stop_flag_path):
                momento = dt.datetime.now()

                self._checar_atraso()
                linhas = self._ler_planilha()
                self._flush_atual(linhas, momento)

                time.sleep(INTERVALO_SEGUNDOS)
            print("yeldcurve: sinal de parada recebido")
        except KeyboardInterrupt:
            print("yeldcurve: Ctrl+C recebido")


if __name__ == "__main__":
    ColetorYeldCurve().executar()
