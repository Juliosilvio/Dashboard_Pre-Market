"""
Nome do script : last_indicadores_nac.py
Descricao      : Fica rodando continuamente (nao termina sozinho) recalculando
                  IFR (RSI), ATR e MACD em tempo real, SO pra Indice e Dolar (os
                  dois ativos-alvo do projeto), nos timeframes M1 e M5.

                  Motivo de existir (pedido do usuario 2026-09-20): o
                  indicadores_mtf.py ja calcula IFR/ATR/MACD pra TODOS os
                  ativos/timeframes da pasta MTF, mas roda dentro do loop em
                  lote do main.py, na FRENTE de uma fila comprida — so comeca
                  depois de vigente/grade/nac/nac_m5/alinhar_d1/retorno/
                  taxa_usatb/correl/descorrel/historico.py (esse ultimo
                  recalculando os 8 timeframes de TODOS os ~35 ativos da
                  MTF), e so entao recalcula os indicadores de TODOS os
                  ~1048 arquivos (indicadores_mtf.py, ordem alfabetica —
                  Indice/Dolar nao sao os primeiros). Isso ja rodou passando de
                  120-180s so nessa etapa. Resultado pratico: mesmo o preco
                  de Indice/Dolar tendo acabado de ser gravado pelo
                  historico.py, o indicador deles so fica pronto depois de
                  esperar a fila inteira de outros ~1000 arquivos.

                  Correcao do usuario (2026-09-21, importante): este script
                  NAO deve abrir conexao com o MT5 pra buscar candle de novo
                  — isso seria coletar a mesma serie duas vezes a toa
                  (nac_m5.py/historico.py ja fazem isso e ja salvam em
                  parquet). Em vez disso, ele LE diretamente os parquets de
                  preco que ja estao em parquet/historicos/MTF/<ativo>/
                  m1.parquet e m5.parquet (a mesma fonte que
                  indicadores_mtf.py usa) — sem MT5, sem terminal, sem
                  conexao nenhuma. O ganho de velocidade nao vem de coletar
                  preco mais novo que o pipeline (a frequencia de coleta
                  continua sendo a do historico.py) — vem de PULAR A FILA:
                  em vez de esperar o indicadores_mtf.py processar os outros
                  ~1000 arquivos primeiro, este script fica de olho SO nos 2
                  arquivos de preco de Indice/Dolar (m1 e m5) e recalcula o
                  indicador deles no segundo em que o proprio arquivo muda —
                  antes, durante ou depois do resto do pipeline rodar, sem
                  depender da ordem/duracao dele.

                  Deteccao de mudanca: compara o mtime (data de modificacao)
                  de cada um dos 4 arquivos (Indice m1/m5, Dolar m1/m5) a cada
                  volta do loop (PAUSA_LOOP) — leitura de metadado do
                  arquivo, praticamente gratis. So abre e le o parquet
                  (pd.read_parquet) quando o mtime mudou de verdade.

                  Formulas: usa o modulo compartilhado calculo_indicadores.py
                  (mesma fonte que o indicadores_mtf.py, pra nao duplicar/
                  divergir formula entre o calculo em lote e este aqui) —
                  Wilder 14 pro IFR e ATR, MACD padrao 12/26/9. Recalcula a
                  serie inteira do arquivo (barato, arquivos MTF sao
                  pequenos) e guarda so a ULTIMA linha (valor corrente) —
                  mesma logica de "tabela de valor corrente" do last_nac.py,
                  nao log de historico (serie historica completa continua
                  sendo papel do indicadores_mtf.py/MTF).

                  Terminal (esclarecimento 2026-09-21): o pedido original do
                  usuario ("certos scripts tem que ter seu proprio terminal"
                  / "Terminal proprio, separado de tudo") era sobre janela
                  de CONSOLE/PowerShell (main.py abrindo cada processo
                  continuo na sua propria janela, pra nao misturar o log de
                  todo mundo junto) — nao sobre terminal MT5. Esse script
                  nem conecta no MT5, entao a questao de terminal MT5
                  simplesmente nao se aplica a ele. A janela de console
                  propria e responsabilidade de main.py (ver _iniciar_last,
                  CREATE_NEW_CONSOLE).

                  Double buffer + escrita atomica + guard de "mudou desde a
                  ultima volta" (_sujo) + parada limpa via
                  parquet/historicos/_stop_last.flag: identico ao padrao de
                  last_nac.py/last_int.py (ver docstring deles pro
                  raciocinio completo). Sai em
                  json/last_json/last_indicadores_nac_a.json e
                  last_indicadores_nac_b.json.
Autor          : Julio Cesar Silvio Campanhola
Criado em      : 2026-09-20
Ultima edicao  : 2026-09-21
Versao         : 2.0.0
Projeto        : dashboard
Historico      : scripts_py/versoes/last_indicadores_nac.md
"""

import importlib
import json
import os
import time

try:
    pd = importlib.import_module("pandas")
except ImportError as exc:
    raise ImportError(
        "A dependencia pandas nao esta instalada. "
        "Instale-a com: pip install pandas pyarrow"
    ) from exc

from calculo_indicadores import calcular_todos

BROKER = "corretora nacional"  # Indice/Dolar sao ativos nativos da corretora nacional neste projeto

ATIVOS_DESEJADOS = ["Indice", "Dolar"]
TIMEFRAMES_DESEJADOS = ["m1", "m5"]

PAUSA_LOOP = 1.0  # segundos entre cada checagem de mtime — so leitura de
                  # metadado do arquivo (os.path.getmtime), praticamente
                  # gratis; o parquet so e aberto de verdade quando mudou


class ColetorIndicadoresNac:
    """Recalcula IFR/ATR/MACD de Indice e Dolar (M1 e M5) direto dos parquets
    de preco da pasta MTF (mesma fonte do indicadores_mtf.py), assim que o
    arquivo muda — sem conexao com MT5, sem esperar o resto do pipeline em
    lote processar os outros ~1000 arquivos primeiro."""

    def __init__(self, base_dir=None):
        self.base_dir = base_dir or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        mtf_dir = os.path.join(self.base_dir, "parquet", "historicos", "MTF")
        output_dir = os.path.join(self.base_dir, "json", "last_json")
        self.output_path_a = os.path.join(output_dir, "last_indicadores_nac_a.json")
        self.output_path_b = os.path.join(output_dir, "last_indicadores_nac_b.json")
        self.stop_flag_path = os.path.join(self.base_dir, "parquet", "historicos", "_stop_last.flag")
        os.makedirs(output_dir, exist_ok=True)

        # (symbol, timeframe) -> caminho do parquet de preco na MTF
        self.caminhos_preco = {
            (symbol, tf): os.path.join(mtf_dir, symbol, f"{tf}.parquet")
            for symbol in ATIVOS_DESEJADOS
            for tf in TIMEFRAMES_DESEJADOS
        }

        self.ultimo_mtime = {}    # (symbol, timeframe) -> mtime do parquet na ultima leitura
        self.estado_atual = {}    # (symbol, timeframe) -> entrada atual
        self._sujo = False
        self._proximo_arquivo = "a"

    def _calcular_um(self, symbol, timeframe):
        """Le o parquet de preco (ja mantido pelo historico.py), recalcula
        IFR/ATR/MACD com calculo_indicadores.calcular_todos() e devolve so a
        ULTIMA linha (valor corrente), ou None se o arquivo nao existir/
        estiver vazio/nao tiver candle suficiente ainda."""
        caminho = self.caminhos_preco[(symbol, timeframe)]
        if not os.path.exists(caminho):
            return None

        df = pd.read_parquet(caminho)
        if df.empty:
            return None
        df = df.sort_values("time").reset_index(drop=True)

        indicadores = calcular_todos(df)
        ultima = indicadores.iloc[-1]
        if pd.isna(ultima["ifr"]) or pd.isna(ultima["atr"]):
            return None  # ainda dentro do periodo de aquecimento

        return {
            "broker": BROKER,
            "symbol": symbol,
            "timeframe": timeframe.upper(),
            "time": df["time"].iloc[-1],
            "ifr": float(ultima["ifr"]),
            "atr": float(ultima["atr"]),
            "macd": float(ultima["macd"]),
            "macd_sinal": float(ultima["macd_sinal"]),
            "macd_hist": float(ultima["macd_hist"]),
        }

    def _varrer(self):
        """Uma passada pelas 4 combinacoes (Indice/Dolar x m1/m5); so recalcula
        (le o parquet de verdade) quem teve o mtime do arquivo mudando desde
        a ultima volta — o resto e so comparar um numero (getmtime), quase
        gratis."""
        for chave, caminho in self.caminhos_preco.items():
            symbol, timeframe = chave
            try:
                mtime = os.path.getmtime(caminho)
            except OSError:
                continue  # arquivo ainda nao existe (primeira coleta do historico.py nao rodou)

            if self.ultimo_mtime.get(chave) == mtime:
                continue  # arquivo nao mudou desde a ultima volta

            try:
                entrada = self._calcular_um(symbol, timeframe)
            except Exception as exc:
                print(f"[indicadores] erro calculando {symbol}/{timeframe}, seguindo: {exc}")
                continue

            self.ultimo_mtime[chave] = mtime  # marca como visto mesmo se vier None (evita reler todo ciclo)
            if entrada is None:
                continue

            self.estado_atual[chave] = entrada
            self._sujo = True

    def _flush(self):
        """Grava o estado atual inteiro em JSON (uma entrada por combinacao
        symbol+timeframe, sempre SOBRESCREVENDO), double buffer + escrita
        atomica — identico ao padrao de last_nac.py/last_int.py."""
        if not self._sujo:
            return
        registros = [
            {
                "broker": linha["broker"],
                "symbol": linha["symbol"],
                "timeframe": linha["timeframe"],
                "time": linha["time"].isoformat(),
                "ifr": linha["ifr"],
                "atr": linha["atr"],
                "macd": linha["macd"],
                "macd_sinal": linha["macd_sinal"],
                "macd_hist": linha["macd_hist"],
            }
            for linha in self.estado_atual.values()
        ]

        alvo = self.output_path_a if self._proximo_arquivo == "a" else self.output_path_b
        tmp_path = alvo + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(registros, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, alvo)
        self._proximo_arquivo = "b" if self._proximo_arquivo == "a" else "a"

        print(f"[indicadores] atualizados ({len(registros)} combinacoes) -> {os.path.basename(alvo)}")
        self._sujo = False

    def executar(self):
        print("[indicadores] last_indicadores_nac rodando (Ctrl+C pra parar) — le direto da MTF, sem MT5")

        try:
            while not os.path.exists(self.stop_flag_path):
                try:
                    self._varrer()
                except Exception as exc:
                    print(f"[indicadores] erro na varredura, seguindo pro proximo ciclo: {exc}")
                try:
                    self._flush()
                except Exception as exc:
                    print(f"[indicadores] erro no flush, tentando de novo no proximo ciclo: {exc}")
                time.sleep(PAUSA_LOOP)
            print("[indicadores] sinal de parada recebido")
        except KeyboardInterrupt:
            print("[indicadores] Ctrl+C recebido")
        finally:
            self._flush()


if __name__ == "__main__":
    ColetorIndicadoresNac().executar()
