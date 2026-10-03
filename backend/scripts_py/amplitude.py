"""
Nome do script : amplitude.py
Descricao      : Amplitude de mercado (advance/decline + novas maximas/
                  minimas) pras duas views do dashboard (Indice/B3 e
                  Nasdaq) — pedido do usuario 2026-09-26, depois de
                  discutir que amplitude de verdade precisa do preco
                  INDIVIDUAL de cada acao do universo (nao da so com o
                  indice/futuro agregado, tipo UsaTec ou Indice).

                  IMPORTANTE - ainda sem dado: este script SO calcula algo
                  quando config.json -> amplitude_universos tiver raizes
                  de acoes individuais listadas (ver formato abaixo) E
                  essas raizes ja estiverem sendo coletadas em
                  parquet/historicos/MTF/<raiz>/<tf>.parquet pelo
                  historico.py. Nenhuma das duas coisas existe ainda —
                  o usuario vai atras das acoes (B3 direto pro Indice, ja
                  que ADR so cobre uma fatia pequena e enviesada do
                  Ibovespa; e do universo do Nasdaq-100 pro Nasdaq) e
                  decide a fonte/corretora. Ate la, o script roda sem
                  quebrar, so com "total_considerados": 0 em tudo.

                  Formato esperado em config.json (novo, ainda vazio):
                      "amplitude_universos": {
                          "indice": {"raizes": []},
                          "nasdaq": {"raizes": []}
                      }
                  Cada raiz precisa ser o nome exato da pasta em
                  parquet/historicos/MTF/ (mesma convencao de
                  ativos_referencia_extra em correl.py/vies_direcional.py/
                  dp.py — aqui tambem sem vencimento pra resolver, acao a
                  vista nao tem vigente). NAO confundir com config.json ->
                  ativos: aquele e o que o historico.py efetivamente vai
                  buscar no MT5 (categorias fixas, cada uma amarrada a uma
                  corretora - ver historico.py). Ou seja, adicionar uma
                  acao aqui em amplitude_universos so faz sentido DEPOIS
                  dela tambem entrar numa categoria nova em config.json ->
                  ativos (com a corretora certa) e o historico.py estar
                  coletando ela — esse segundo passo ainda nao existe no
                  projeto e fica pra quando o usuario tiver a fonte
                  definida (fora do escopo deste script).

                  Metricas calculadas, por universo (indice/nasdaq) e por
                  timeframe (M15 a W1), a partir do ULTIMO candle fechado
                  de cada raiz do universo:
                  - avanco/declinio/inalterado: fechamento do candle atual
                    vs fechamento do candle anterior, POR ACAO, depois
                    contado (quantas avancaram, quantas cairam).
                  - nova_maxima/nova_minima: maxima (high) ou minima (low)
                    do candle atual bate a maior/menor da janela dos
                    ultimos JANELA_MAXMIN_PADRAO candles daquele TF (20 por
                    padrao — NAO e "52 semanas", que so faz sentido fixo
                    pra D1; aqui e generico por timeframe, documentado
                    explicitamente no proprio campo pra nao confundir).
                  - pct_avanco: % de acoes do universo que avancaram.
                  - indice_amplitude: (avancos - declinios) / total * 100
                    — positivo = alta ampla, negativo = queda ampla, perto
                    de zero = mercado dividido (ou movimento concentrado
                    em poucos nomes, mesmo que o indice/futuro agregado
                    tenha andado bastante).

                  Por que NAO uma linha de avanco/declinio CUMULATIVA
                  (a "AD Line" classica, soma dia a dia desde sempre): o
                  projeto inteiro roda no padrao "recalculo sempre total,
                  sem estado incremental persistido" (ver docstring do
                  indicadores_mtf.py) — uma AD Line de verdade precisa
                  acumular entre reinicios do script, o que quebraria esse
                  padrao. Fica de fora nesta v1.0.0; se o usuario quiser
                  depois, da pra evoluir persistindo o net (avancos-
                  declinios) de cada dia num arquivo a parte.

                  Le direto dos parquets de preco em MTF (mesma fonte de
                  dp.py), recalcula so quando o mtime de algum parquet do
                  universo muda, grava double buffer — mesmo padrao de
                  todo o resto do projeto (last_nac.py, dp.py, etc.).
Autor          : Julio Cesar Silvio Campanhola
Criado em      : 2026-09-26
Ultima edicao  : 2026-09-26
Versao         : 1.0.0
Projeto        : dashboard
Historico      : scripts_py/versoes/amplitude.md
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

TIMEFRAMES_DESEJADOS = ["m15", "m30", "h1", "h4", "d1", "w1"]

# candles pra considerar "nova maxima/minima" — generico por timeframe (ver
# docstring do modulo pra explicacao de por que nao e um numero fixo tipo
# "52 semanas").
JANELA_MAXMIN_PADRAO = 20

PAUSA_LOOP = 1.0  # segundos entre cada checagem de mtime, mesmo padrao de dp.py


class ColetorAmplitude:
    """Conta avanco/declinio e novas maximas/minimas por universo
    (indice/nasdaq) e por timeframe, direto dos parquets de preco em MTF —
    mesmo padrao de mtime-watch + double buffer de dp.py."""

    def __init__(self, base_dir=None):
        self.base_dir = base_dir or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.mtf_dir = os.path.join(self.base_dir, "parquet", "historicos", "MTF")
        output_dir = os.path.join(self.base_dir, "json", "last_json")
        self.output_path_a = os.path.join(output_dir, "amplitude_amostra_a.json")
        self.output_path_b = os.path.join(output_dir, "amplitude_amostra_b.json")
        self.stop_flag_path = os.path.join(self.base_dir, "parquet", "historicos", "_stop_last.flag")
        self.config_path = os.path.join(self.base_dir, "json", "config.json")
        os.makedirs(output_dir, exist_ok=True)

        self.universos = self._resolver_universos()
        self.caminhos_preco = {
            (universo, raiz, tf): os.path.join(self.mtf_dir, raiz, f"{tf}.parquet")
            for universo, raizes in self.universos.items()
            for raiz in raizes
            for tf in TIMEFRAMES_DESEJADOS
        }

        self.ultimo_mtime = {}
        self.estado_atual = {}  # (universo, raiz, tf) -> {"direcao", "nova_maxima", "nova_minima"}
        self._sujo = False
        self._proximo_arquivo = "a"

    def _resolver_universos(self):
        """Le config.json -> amplitude_universos (ver docstring do
        modulo pro formato). Universo sem entrada no config, ou sem
        "raizes", vira lista vazia — o script roda normal, so sem nada
        pra contar ainda."""
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
        except (OSError, json.JSONDecodeError):
            config = {}
        universos_config = config.get("amplitude_universos", {})
        return {
            nome: list(info.get("raizes", []))
            for nome, info in universos_config.items()
        }

    # ---------- calculo por acao+tf ----------

    def _calcular_um(self, caminho, janela=JANELA_MAXMIN_PADRAO):
        df = pd.read_parquet(caminho)
        if df.empty or len(df) < 2:
            return None
        df = df.sort_values("time").reset_index(drop=True)

        fechamento_atual = float(df["close"].iloc[-1])
        fechamento_anterior = float(df["close"].iloc[-2])
        if fechamento_atual > fechamento_anterior:
            direcao = "avanco"
        elif fechamento_atual < fechamento_anterior:
            direcao = "declinio"
        else:
            direcao = "inalterado"

        janela_df = df.tail(janela)
        maxima_janela = float(janela_df["high"].max())
        minima_janela = float(janela_df["low"].min())

        return {
            "direcao": direcao,
            "nova_maxima": float(df["high"].iloc[-1]) >= maxima_janela,
            "nova_minima": float(df["low"].iloc[-1]) <= minima_janela,
        }

    # ---------- varredura (so mtime mudou) + agregacao + flush (double buffer) ----------

    def _varrer(self):
        for chave, caminho in self.caminhos_preco.items():
            try:
                mtime = os.path.getmtime(caminho)
            except OSError:
                continue  # raiz ainda sem parquet coletado (historico.py nao cobre ela ainda)

            if self.ultimo_mtime.get(chave) == mtime:
                continue

            try:
                entrada = self._calcular_um(caminho)
            except Exception as exc:
                universo, raiz, tf = chave
                print(f"[amplitude] erro calculando {raiz}/{tf} ({universo}), seguindo: {exc}")
                continue

            self.ultimo_mtime[chave] = mtime
            if entrada is None:
                continue

            self.estado_atual[chave] = entrada
            self._sujo = True

    def _agregar(self, universo, tf):
        """Conta avanco/declinio/novas maximas-minimas de todas as raizes
        desse universo, nesse TF, a partir do que ja foi calculado. So
        entram acoes com dado valido (parquet existe e ja tem historico
        suficiente) — total_considerados reflete isso, nao o tamanho da
        lista configurada."""
        linhas = [
            valor
            for (u, _raiz, t), valor in self.estado_atual.items()
            if u == universo and t == tf
        ]
        total = len(linhas)
        if total == 0:
            return None

        avancos = sum(1 for l in linhas if l["direcao"] == "avanco")
        declinios = sum(1 for l in linhas if l["direcao"] == "declinio")
        inalterados = total - avancos - declinios

        return {
            "universo": universo,
            "tf": tf.upper(),
            "total_considerados": total,
            "avancos": avancos,
            "declinios": declinios,
            "inalterados": inalterados,
            "novas_maximas": sum(1 for l in linhas if l["nova_maxima"]),
            "novas_minimas": sum(1 for l in linhas if l["nova_minima"]),
            "janela_maxmin_candles": JANELA_MAXMIN_PADRAO,
            "pct_avanco": round(avancos / total * 100.0, 1),
            "indice_amplitude": round((avancos - declinios) / total * 100.0, 1),
        }

    def _flush(self):
        if not self._sujo:
            return

        consolidado = []
        for universo in self.universos:
            for tf in TIMEFRAMES_DESEJADOS:
                item = self._agregar(universo, tf)
                if item is not None:
                    consolidado.append(item)

        saida = {"consolidado": consolidado}

        alvo = self.output_path_a if self._proximo_arquivo == "a" else self.output_path_b
        tmp_path = alvo + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(saida, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, alvo)
        self._proximo_arquivo = "b" if self._proximo_arquivo == "a" else "a"

        print(f"[amplitude] atualizado ({len(consolidado)} combinacoes universo+tf) -> {os.path.basename(alvo)}")
        self._sujo = False

    def executar(self):
        resumo = ", ".join(f"{nome} ({len(raizes)} ativos configurados)" for nome, raizes in self.universos.items())
        resumo = resumo or "nenhum universo configurado ainda em config.json -> amplitude_universos"
        print(f"[amplitude] amplitude.py rodando (Ctrl+C pra parar) — {resumo}")

        try:
            while not os.path.exists(self.stop_flag_path):
                try:
                    self._varrer()
                except Exception as exc:
                    print(f"[amplitude] erro na varredura, seguindo pro proximo ciclo: {exc}")
                try:
                    self._flush()
                except Exception as exc:
                    print(f"[amplitude] erro no flush, tentando de novo no proximo ciclo: {exc}")
                time.sleep(PAUSA_LOOP)
            print("[amplitude] sinal de parada recebido")
        except KeyboardInterrupt:
            print("[amplitude] Ctrl+C recebido")
        finally:
            self._flush()


if __name__ == "__main__":
    ColetorAmplitude().executar()
