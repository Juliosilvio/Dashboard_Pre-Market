"""
Nome do script : indicadores_mtf.py
Descricao      : Calcula IFR (RSI), ATR e MACD em cima de TODOS os parquets
                  de preco da pasta de estudo MTF (parquet/historicos/MTF/),
                  pra TODOS os ativos e TODOS os timeframes coletados pelo
                  historico.py (M1, M5, M15, M30, H1, H4, D1, W1) — nao so
                  Indice/Dolar, sem excecao.

                  Estrutura de saida (pedido do usuario 2026-09-20): uma
                  pasta "indicadores/" IRMA dos arquivos de preco, dentro de
                  cada pasta de ativo (ou de vencimento, quando o ativo
                  tiver) — nao mais colunas dentro do proprio parquet de
                  preco (versao 1.0.0 fazia assim; corrigido nesta versao).
                  Exemplo:
                      MTF/Indice/m5.parquet                 (preco, intocado)
                      MTF/Indice/indicadores/m5.parquet     (ifr/atr/macd/...)
                      MTF/Indice/10-2026/m5.parquet             (preco)
                      MTF/Indice/10-2026/indicadores/m5.parquet (indicadores)
                  Cada arquivo de indicadores guarda a serie historica
                  COMPLETA (time + ifr + atr + macd + macd_sinal +
                  macd_hist), candle a candle, nao so o valor mais recente.

                  Formulas usadas (parametros padrao de mercado, ainda nao
                  ajustados/otimizados pro projeto):
                  - IFR (RSI) de Wilder, periodo 14: media movel exponencial
                    de Wilder (alpha=1/14) sobre ganhos e perdas do close.
                  - ATR de Wilder, periodo 14: media movel exponencial de
                    Wilder (alpha=1/14) sobre o True Range (max entre
                    high-low, |high-close anterior|, |low-close anterior|).
                  - MACD padrao 12/26/9: EMA(12) - EMA(26) = linha MACD;
                    EMA(9) da linha MACD = linha de sinal; histograma =
                    MACD - sinal.

                  Formulas vivem em calculo_indicadores.py (modulo
                  compartilhado, extraido desta classe em 2.1.0) — mesma
                  fonte que o last_indicadores_nac.py (tempo real de
                  Indice/Dolar) usa, pra nao duplicar/divergir formula entre o
                  calculo em lote e o em tempo real.

                  Recalculo e sempre TOTAL (a arvore inteira de cada
                  arquivo), nao incremental — os arquivos da MTF sao
                  pequenos o suficiente (milhares a poucas dezenas de
                  milhares de linhas) pra isso ser barato, e evita o risco
                  de indicador desalinhado por causa de candle atualizado
                  fora de ordem.

                  Limpeza automatica: se um parquet de PRECO ainda tiver as
                  colunas de indicador da versao 1.0.0 (embutidas direto
                  nele), esta versao remove essas colunas e resalva o
                  arquivo de preco limpo (so OHLC), antes de gerar o
                  arquivo separado em indicadores/.

                  Script standalone da pasta de estudo MTF, igual o
                  historico.py — nao registrado no main.py por enquanto.
                  Rodar depois de toda coleta do historico.py.

                  Proximo passo depois deste: usar essas series pra estudar
                  correlacao/descorrelacao ENTRE indicadores (nao de preco)
                  e o tempo ate o IFR bater as extremidades 30/70 em
                  M1/M5, condicionado ao ATR.
Autor          : Julio Cesar Silvio Campanhola
Criado em      : 2026-09-20
Ultima edicao  : 2026-09-20
Versao         : 2.1.0
Projeto        : dashboard
Historico      : scripts_py/versoes/indicadores_mtf.md
"""

import importlib
import os

try:
    pd = importlib.import_module("pandas")
except ImportError as exc:
    raise ImportError(
        "A dependencia pandas nao esta instalada. "
        "Instale-a com: pip install pandas pyarrow"
    ) from exc

from calculo_indicadores import calcular_todos

# nomes dos arquivos de timeframe que o historico.py gera — usado pra
# distinguir arquivo de candle (m1.parquet, m5.parquet, ...) do parquet de
# controle (controle_atualizacao_mtf.parquet), que fica na raiz da MTF e
# nao e um arquivo de candle
ARQUIVOS_TF = {"m1.parquet", "m5.parquet", "m15.parquet", "m30.parquet",
               "h1.parquet", "h4.parquet", "d1.parquet", "w1.parquet"}

NOME_PASTA_INDICADORES = "indicadores"
COLUNAS_INDICADOR = ["ifr", "atr", "macd", "macd_sinal", "macd_hist"]

PERIODO_IFR = 14
PERIODO_ATR = 14
MACD_RAPIDA = 12
MACD_LENTA = 26
MACD_SINAL = 9


class CalculadorIndicadoresMTF:
    """Calcula IFR, ATR e MACD em cima de todos os parquets de preco da
    pasta MTF — todo ativo, todo timeframe — e salva a serie historica
    completa de cada indicador numa pasta indicadores/ irma do arquivo de
    preco (uma pasta indicadores por ativo/vencimento)."""

    def __init__(self, mtf_dir=None,
                 periodo_ifr=PERIODO_IFR, periodo_atr=PERIODO_ATR,
                 macd_rapida=MACD_RAPIDA, macd_lenta=MACD_LENTA, macd_sinal=MACD_SINAL):
        self.mtf_dir = mtf_dir or os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "parquet", "historicos", "MTF",
        )
        self.periodo_ifr = periodo_ifr
        self.periodo_atr = periodo_atr
        self.macd_rapida = macd_rapida
        self.macd_lenta = macd_lenta
        self.macd_sinal = macd_sinal

    # ---------- indicadores (series completas, nao so o ultimo valor) ----------

    # ---------- arquivo a arquivo ----------

    def listar_arquivos_tf(self):
        """Anda a arvore inteira da MTF e devolve o caminho de todo arquivo
        de PRECO (m1.parquet, m5.parquet, ..., w1.parquet) — em qualquer
        nivel (ativo direto, ou ativo/vencimento) — ignorando o parquet de
        controle na raiz e qualquer coisa ja dentro de uma pasta
        indicadores/ (nao reprocessa a propria saida)."""
        arquivos = []
        for dirpath, _dirnames, filenames in os.walk(self.mtf_dir):
            if os.path.basename(dirpath) == NOME_PASTA_INDICADORES:
                continue
            for nome in filenames:
                if nome in ARQUIVOS_TF:
                    arquivos.append(os.path.join(dirpath, nome))
        return sorted(arquivos)

    def _limpar_colunas_antigas(self, df, caminho_preco):
        """Remove colunas de indicador que a versao 1.0.0 tinha embutido
        direto no parquet de preco, e resalva o arquivo de preco limpo (so
        OHLC) — a partir desta versao, indicador vive so em indicadores/."""
        presentes = [c for c in COLUNAS_INDICADOR if c in df.columns]
        if not presentes:
            return df
        df_limpo = df.drop(columns=presentes)
        df_limpo.to_parquet(caminho_preco, index=False)
        return df_limpo

    def caminho_saida_indicadores(self, caminho_preco):
        """.../<ativo>[/<vencimento>]/<tf>.parquet -> .../<ativo>[/<vencimento>]/indicadores/<tf>.parquet"""
        pasta_ativo = os.path.dirname(caminho_preco)
        nome_tf = os.path.basename(caminho_preco)
        pasta_indicadores = os.path.join(pasta_ativo, NOME_PASTA_INDICADORES)
        return os.path.join(pasta_indicadores, nome_tf)

    def processar_arquivo(self, caminho_preco):
        """Le o parquet de preco, limpa coluna de indicador antiga se
        houver, recalcula os 3 indicadores em cima da serie inteira e salva
        num parquet separado em indicadores/ (time + ifr + atr + macd +
        macd_sinal + macd_hist). Retorna (linhas, ok) — ok=False se o
        arquivo nao tiver candle suficiente ou vier vazio."""
        df = pd.read_parquet(caminho_preco)
        if df.empty:
            return 0, False

        df = df.sort_values("time").reset_index(drop=True)
        df = self._limpar_colunas_antigas(df, caminho_preco)

        resultado = calcular_todos(
            df,
            periodo_ifr=self.periodo_ifr,
            periodo_atr=self.periodo_atr,
            macd_rapida=self.macd_rapida,
            macd_lenta=self.macd_lenta,
            macd_sinal=self.macd_sinal,
        )
        df_indic = pd.DataFrame({"time": df["time"]})
        df_indic["ifr"] = resultado["ifr"]
        df_indic["atr"] = resultado["atr"]
        df_indic["macd"] = resultado["macd"]
        df_indic["macd_sinal"] = resultado["macd_sinal"]
        df_indic["macd_hist"] = resultado["macd_hist"]

        caminho_saida = self.caminho_saida_indicadores(caminho_preco)
        os.makedirs(os.path.dirname(caminho_saida), exist_ok=True)
        df_indic.to_parquet(caminho_saida, index=False)
        return len(df_indic), True

    def executar(self):
        arquivos = self.listar_arquivos_tf()
        print(f"Encontrados {len(arquivos)} arquivos de preco na MTF ({self.mtf_dir})")

        processados = 0
        falhas = []
        total_linhas = 0

        for caminho in arquivos:
            try:
                linhas, ok = self.processar_arquivo(caminho)
                if ok:
                    processados += 1
                    total_linhas += linhas
                else:
                    falhas.append((caminho, "arquivo vazio"))
            except Exception as exc:
                falhas.append((caminho, str(exc)))

        print(f"Indicadores calculados e salvos (em indicadores/) pra {processados}/{len(arquivos)} arquivos "
              f"({total_linhas} candles no total).")
        if falhas:
            print(f"Falhas ({len(falhas)}):")
            for caminho, motivo in falhas[:20]:
                print(f"  - {os.path.relpath(caminho, self.mtf_dir)}: {motivo}")


if __name__ == "__main__":
    CalculadorIndicadoresMTF().executar()
