"""
Nome do script : alinhar_d1.py
Descricao      : Normaliza o D1 da corretora internacional pra ficar comparavel com o D1
                  da corretora nacional (Indice/Dolar), de uma vez por todas — sem precisar
                  de ajuste manual daqui pra frente.

                  Problema encontrado (2026-09-20): mesmo com o horario de
                  cada candle corrigido (fuso_horario.py, DST-aware), o D1
                  NATIVO do MT5 pra corretora internacional continua incomparavel com o
                  da corretora nacional, porque o BARRAMENTO do candle diario (o range de
                  24h que cada corretora agrega) segue o "dia" do proprio
                  servidor, nao o dia calendario UTC. A corretora nacional (sem DST, sem
                  correcao) ja agrega exatamente o pregao da B3 (09:00 as
                  ~18:30 UTC) rotulado com o timestamp 00:00 UTC do mesmo
                  dia — confirmado comparando o D1 nativo do Indice com o M5
                  do mesmo dia (open/high/low/close batem exatamente). Ja o
                  D1 nativo da corretora internacional, mesmo corrigido candle a candle,
                  tem o BARRAMENTO cruzando dois dias UTC (ex: Usa500 abre
                  19h/20h UTC e fecha 24h depois) — comparar "mesma data"
                  mistura dois pregoes diferentes.

                  Solucao definitiva: em vez de usar o D1 nativo da
                  corretora internacional, RECALCULA o D1 dela a partir do M5 (que ja
                  vem com horario real, corrigido candle a candle),
                  agrupando por DIA CALENDARIO UTC (00:00-24:00) — a mesma
                  janela que a corretora nacional ja usa.

                  Reescrito 2026-09-21 (consolidacao MTF, pedido do
                  usuario: "isso e o que precisamos: serie historica em MTF
                  e preco em tempo real, de forma centralizada"). Antes esta
                  correcao rodava so em cima de historico_d1.parquet/
                  historico_m5.parquet (o pipeline "antigo" alimentado por
                  nac.py/int.py). Agora que a MTF (historico.py) virou a
                  UNICA fonte de coleta (nac.py/nac_m5.py/int.py/int_m5.py
                  saem do pipeline — ver main.py), o D1 nativo salvo em
                  parquet/historicos/MTF/<ativo>/[<vencimento>/]d1.parquet
                  pra ativos da corretora internacional tem o MESMO bug (confirmado:
                  MTF/Indice/10-2026/d1.parquet ainda abria 19h UTC antes
                  desta correcao) — e so tinha sido consertado na copia
                  antiga, nunca aqui, que e a fonte de verdade agora. Este
                  script passa a corrigir o D1 DENTRO DA PROPRIA MTF: pra
                  cada alvo da corretora internacional (mesma lista de historico.py,
                  via montar_alvos()), resample o m5.parquet da MTF
                  (agrupado por dia calendario UTC) e SOBRESCREVE o
                  d1.parquet daquele mesmo alvo. Roda logo apos
                  historico.py e antes de flat_mtf.py — assim quem deriva o
                  historico_d1.parquet "achatado" (flat_mtf.py) e quem
                  consome a MTF direto (indicadores_mtf.py,
                  last_indicadores_nac.py) ja pegam o D1 certo.

                  Contrapartida aceita (igual antes): como o M5 da MTF cobre
                  so a profundidade padrao de coleta (historico.py,
                  DIAS_HISTORICO M5 = 90 dias na primeira coleta), o D1
                  recalculado cobre so esse periodo — nao ha mais D1 nativo
                  "antigo" de anos atras pra descartar, porque a MTF nunca
                  guardou isso pra alem da profundidade configurada.
Autor          : Julio Cesar Silvio Campanhola
Criado em      : 2026-09-20
Ultima edicao  : 2026-09-21
Versao         : 2.0.0
Projeto        : dashboard
Historico      : scripts_py/versoes/alinhar_d1.md
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

from historico import ColetorHistoricoMTF

BROKER_corretora internacional = "corretora internacional"


class AlinhadorD1:
    """Recalcula o D1 dos alvos da corretora internacional, DENTRO da propria MTF, a
    partir do m5.parquet do mesmo alvo, agrupado por dia calendario UTC —
    deixa comparavel com o D1 nativo da corretora nacional (que ja usa essa mesma janela)
    sem precisar de ajuste manual."""

    def __init__(self, mtf_dir=None, config_path=None):
        self.coletor = ColetorHistoricoMTF(base_dir=None)
        if mtf_dir is not None:
            self.coletor.mtf_dir = mtf_dir
        if config_path is not None:
            self.coletor.config_path = config_path
        self.mtf_dir = self.coletor.mtf_dir

    def resample_d1_de_m5(self, df_m5):
        """Agrupa candles M5 de um unico alvo em barras D1 por dia
        calendario UTC (00:00-24:00) — mesma janela que a corretora nacional ja usa
        nativamente pro D1 (confirmado: open/high/low/close do D1 nativo do
        Indice batem exatamente com o M5 daquele dia calendario)."""
        df = df_m5.sort_values("time").copy()
        df["dia"] = df["time"].dt.floor("D")

        agregado = (
            df.groupby("dia", as_index=False)
            .agg(
                open=("open", "first"),
                high=("high", "max"),
                low=("low", "min"),
                close=("close", "last"),
                tick_volume=("tick_volume", "sum"),
                real_volume=("real_volume", "sum"),
                spread=("spread", "mean"),
            )
        )
        agregado = agregado.rename(columns={"dia": "time"})
        return agregado

    def executar(self):
        self.coletor.carregar_config()
        alvos = self.coletor.montar_alvos()
        alvos_corretora internacional = [a for a in alvos if a["broker"] == BROKER_corretora internacional]

        corrigidos = 0
        total_linhas = 0
        falhas = []

        for alvo in alvos_corretora internacional:
            pasta = os.path.join(self.mtf_dir, *alvo["pasta_rel"].split("/"))
            caminho_m5 = os.path.join(pasta, "m5.parquet")
            caminho_d1 = os.path.join(pasta, "d1.parquet")

            if not os.path.exists(caminho_m5):
                continue  # historico.py ainda nao coletou m5 desse alvo

            try:
                df_m5 = pd.read_parquet(caminho_m5)
                if df_m5.empty:
                    continue
                d1_novo = self.resample_d1_de_m5(df_m5)
                d1_novo.to_parquet(caminho_d1, index=False)
                corrigidos += 1
                total_linhas += len(d1_novo)
            except Exception as exc:
                falhas.append((alvo["pasta_rel"], str(exc)))

        print(
            f"D1 da corretora internacional realinhado por dia calendario UTC, dentro da MTF: "
            f"{corrigidos}/{len(alvos_corretora internacional)} alvos ({total_linhas} barras no total)."
        )
        if falhas:
            print(f"Falhas ({len(falhas)}):")
            for pasta_rel, motivo in falhas[:20]:
                print(f"  - {pasta_rel}: {motivo}")


if __name__ == "__main__":
    AlinhadorD1().executar()
