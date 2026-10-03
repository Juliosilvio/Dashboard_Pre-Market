"""
Nome do script: fuso_horario.py
Descricao: Modulo compartilhado de correcao de fuso horario entre corretoras.
           A corretora internacional grava o horario dos candles no relogio do proprio
           servidor, que segue o horario de verao europeu (DST): -5h em
           relacao ao horario real (UTC/B3) durante o horario de verao
           europeu (ultimo domingo de marco a ultimo domingo de outubro,
           01:00 UTC) e -4h fora dele (horario de inverno europeu).
           A corretora nacional ja grava em horario correto (referencia = 0h de correcao).
           Descoberto e validado comparando Indice (corretora nacional) com Indice (corretora internacional):
           - correcao fixa de -5h o ano todo: correlacao M5 = 0,636 (errado,
             pois so bate nos meses de horario de verao europeu)
           - correcao DST-aware (-5h verao / -4h inverno): correlacao M5 = 0,953
           - abertura do pregao do Indice (corrigido) bate 09:00 UTC (= Indice)
             em >97% dos dias de pregao, so divergindo em feriados/half-days.
Autor: Julio Cesar Silvio Campanhola
Criado em: 2026-09-20
Ultima edicao: 2026-09-20
Versao: 1.0.0
Projeto: dashboard
Historico:
  1.0.0 - Criacao do modulo. Substitui a correcao fixa de config.json
          (fuso_horario.correcao_horas), que estava incorreta por nao
          considerar o horario de verao europeu do servidor da corretora internacional.
"""

import pandas as pd

# Correcao em horas por regime, para o broker corretora internacional.
# corretora nacional nao precisa de correcao (Brasil nao tem horario de verao desde 2019).
CORRECAO_DST_ATIVO = -5   # horario de verao europeu (ultimo dom mar -> ultimo dom out)
CORRECAO_DST_INATIVO = -4  # horario de inverno europeu (resto do ano)


def _ultimo_domingo(ano: int, mes: int) -> pd.Timestamp:
    """Retorna o ultimo domingo do mes/ano informado, 00:00, naive."""
    ultimo_dia = pd.Timestamp(year=ano, month=mes, day=1) + pd.offsets.MonthEnd(1)
    offset = (ultimo_dia.weekday() - 6) % 7  # weekday: Monday=0 ... Sunday=6
    return ultimo_dia - pd.Timedelta(days=offset)


def _limites_dst(ano: int):
    """Inicio e fim do horario de verao europeu (DST) para o ano informado,
    como Timestamps tz-aware UTC. Transicao as 01:00 UTC, regra padrao da UE."""
    inicio = (_ultimo_domingo(ano, 3) + pd.Timedelta(hours=1)).tz_localize("UTC")
    fim = (_ultimo_domingo(ano, 10) + pd.Timedelta(hours=1)).tz_localize("UTC")
    return inicio, fim


def eu_dst_ativo(ts_series: pd.Series) -> pd.Series:
    """Recebe uma Series datetime64 tz-aware (UTC) e retorna uma Series bool
    indicando se cada timestamp cai dentro do horario de verao europeu.
    Funciona tanto para horario cru (nao corrigido) quanto ja corrigido —
    o erro de poucas horas possivel na fronteira exata da troca de horario
    nao muda o resultado pratico (a troca ocorre de madrugada, fora do
    pregao)."""
    anos = ts_series.dt.year
    resultado = pd.Series(False, index=ts_series.index)
    for ano in anos.unique():
        inicio_dst, fim_dst = _limites_dst(int(ano))
        mask_ano = anos == ano
        resultado.loc[mask_ano] = (ts_series.loc[mask_ano] >= inicio_dst) & (
            ts_series.loc[mask_ano] < fim_dst
        )
    return resultado


def corrigir_horario_corretora internacional(ts_series: pd.Series) -> pd.Series:
    """Converte uma Series de horario CRU do servidor corretora internacional (rotulado
    como UTC sem correcao) para o horario real (UTC / referencia corretora nacional)."""
    dst = eu_dst_ativo(ts_series)
    correcao_h = dst.map({True: CORRECAO_DST_ATIVO, False: CORRECAO_DST_INATIVO})
    return ts_series + pd.to_timedelta(correcao_h, unit="h")


def reverter_horario_corretora internacional(ts_series: pd.Series) -> pd.Series:
    """Converte uma Series de horario JA CORRIGIDO (real/UTC) de volta para o
    horario cru do servidor corretora internacional — necessario para parametros como
    `data_de` do mt5.copy_rates_range, que esperam horario de servidor."""
    dst = eu_dst_ativo(ts_series)  # aproximacao: usa o proprio horario corrigido
    correcao_h = dst.map({True: CORRECAO_DST_ATIVO, False: CORRECAO_DST_INATIVO})
    return ts_series - pd.to_timedelta(correcao_h, unit="h")


def corrigir_horario_corretora internacional_escalar(ts) -> object:
    """Versao escalar de corrigir_horario_corretora internacional, para um unico
    pandas.Timestamp tz-aware (UTC)."""
    serie = pd.Series([ts])
    return corrigir_horario_corretora internacional(serie).iloc[0]


def reverter_horario_corretora internacional_escalar(ts) -> object:
    """Versao escalar de reverter_horario_corretora internacional, para um unico
    pandas.Timestamp tz-aware (UTC)."""
    serie = pd.Series([ts])
    return reverter_horario_corretora internacional(serie).iloc[0]
