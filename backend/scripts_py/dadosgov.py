"""
Nome do script : dadosgov.py
Descricao      : Coleta serie temporal de dados publicos do GOVERNO (fora do
                  MT5) - hoje: API do Banco Central do Brasil (SGS - Sistema
                  Gerenciador de Series Temporais), publica, sem
                  autenticacao. Nome generico de proposito ("dadosgov", nao
                  "bcb" ou "selic") — se um dia precisar de outra fonte de
                  dado publico do governo (ex: IBGE, Tesouro Direto), entra
                  aqui, num script novo so se for pedido, nao por fonte.

                  Pedido do usuario (2026-09-21): comparar a expectativa de
                  juros embutida no DI1 (curva ja coletada) contra a taxa
                  livre de risco definida pelo Copom — pra isso precisa da
                  Selic, que o projeto nao tinha. Colhe DUAS series:
                  - 432 (Meta Selic definida pelo Copom) — a que interessa
                    de fato pra comparar com o DI1 (e o que o Copom decide).
                  - 11 (Selic efetiva diaria, o "over") — colhida tambem a
                    pedido do usuario, fica registrada; NAO e o alvo da
                    comparacao com DI1 (essa e a 432), so guardada pra nao
                    precisar voltar aqui se um dia fizer falta.

                  Coleta incremental, 1x por rodada do pipeline em lote
                  (chamada e minuscula — roda junto com vigente.py no
                  inicio do ciclo, main.py). Decisao explicita do usuario:
                  NAO tenta adivinhar quando o Copom se reune (um
                  calendario proprio ia exigir manutencao e pode furar —
                  ja teve reuniao extraordinaria) — so pergunta pra API o
                  que tem de novo desde a ultima data salva ate hoje, mesma
                  logica incremental de nac.py/int.py. A Selic muda raro
                  (so nas datas de decisao do Copom), entao a maioria das
                  rodadas nao acha nada novo — custo desprezivel de rede.

                  Tratamento de erro TOLERANTE (nao a logica pesada de 3
                  passadas dos coletores MT5 — dado nao urgente, nao
                  intraday): se a rede cair ou a API do BC falhar/mudar,
                  loga um aviso e segue pras proximas series, nunca derruba
                  o pipeline em lote.

                  Escopo explicito: NAO faz nenhum cruzamento com o DI1
                  (o spread DI1-Selic que motivou trazer esse dado) — isso
                  fica pra um passo separado, depois, quando tiver o dado
                  bruto salvo aqui (a Selic vem em "degrau", muda so de vez
                  em quando; o DI1 e intraday continuo — vai precisar de
                  merge as-of pra alinhar os dois antes de calcular o
                  spread, mesmo padrao ja usado nos backtests do vies
                  direcional).

                  Series configuradas em config.json -> dados_gov -> bcb
                  (chave -> {serie: codigo SGS, nome: rotulo}). Salva uma
                  serie por arquivo em
                  parquet/historicos/dadosgov/<chave>.parquet, colunas
                  data (date) e valor (float).
Autor          : Julio Cesar Silvio Campanhola
Criado em      : 2026-09-21
Ultima edicao  : 2026-09-21
Versao         : 1.0.5
Projeto        : dashboard
Historico      : scripts_py/versoes/dadosgov.md
"""

import importlib
import json
import os
import socket
import urllib.error
import urllib.request

try:
    pd = importlib.import_module("pandas")
except ImportError as exc:
    raise ImportError(
        "A dependencia pandas nao esta instalada. "
        "Instale-a com: pip install pandas pyarrow"
    ) from exc


URL_SGS = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados"

# Forca resolucao DNS so em IPv4 pras chamadas deste script - diagnostico
# 2026-09-21: a mesma URL abriu na hora no navegador do usuario, mas deu
# timeout toda vez via Python (urllib) na mesma maquina. Padrao classico de
# rota IPv6 quebrada/lenta: navegador tenta IPv4 e IPv6 em paralelo (Happy
# Eyeballs) e fica com quem responde primeiro; o socket do Python tenta os
# enderecos na ordem que o DNS devolve (normalmente IPv6 primeiro) e espera
# o timeout inteiro antes de cair pro IPv4. Escopo: so o getaddrinfo do
# processo deste script (dadosgov.py e single-purpose, so fala com essa
# API) - nao mexe em nada fora daqui.
_getaddrinfo_original = socket.getaddrinfo


def _getaddrinfo_somente_ipv4(host, port, family=0, type=0, proto=0, flags=0):
    return _getaddrinfo_original(host, port, socket.AF_INET, type, proto, flags)


socket.getaddrinfo = _getaddrinfo_somente_ipv4
# 3 anos (nao os 10 que a API permite) - decisao 2026-09-21: a serie 432
# (Meta Selic) deu timeout pedindo 10 anos de uma vez (mesmo com 30s de
# timeout), enquanto a 11 (Selic efetiva) com a MESMA janela de 10 anos
# funcionou normal - nao da pra confirmar a causa exata sem acesso de rede
# daqui, mas pedir uma janela menor reduz o trabalho do servidor pra
# gerar a resposta e o tamanho dela, e 3 anos ja cobre com folga o
# historico real de D1 do DI1 (2 anos, ver arquitetura.md) que e o que
# esse dado vai ser comparado - nao precisa dos 10 anos inteiros.
JANELA_INICIAL_ANOS = 3


class ColetorDadosGov:
    """Coleta series publicas do governo, hoje so BCB/SGS (Selic) — pensado
    pra crescer com outras fontes/series no futuro sem precisar de script
    novo por fonte."""

    def __init__(self, base_dir=None, config_path=None):
        self.base_dir = base_dir or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.config_path = config_path or os.path.join(self.base_dir, "json", "config.json")
        self.saida_dir = os.path.join(self.base_dir, "parquet", "historicos", "dadosgov")
        os.makedirs(self.saida_dir, exist_ok=True)

    # ---------- config ----------

    def _carregar_series(self):
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
        except (OSError, json.JSONDecodeError) as exc:
            print(f"dadosgov: erro lendo config.json ({exc}) - nada a coletar nesta rodada")
            return {}
        return config.get("dados_gov", {}).get("bcb", {})

    # ---------- leitura/escrita local ----------

    def _caminho(self, chave):
        return os.path.join(self.saida_dir, f"{chave}.parquet")

    def _ultima_data_salva(self, chave):
        caminho = self._caminho(chave)
        if not os.path.exists(caminho):
            return None
        try:
            df = pd.read_parquet(caminho, columns=["data"])
        except Exception:
            return None
        if df.empty:
            return None
        return pd.to_datetime(df["data"]).max().date()

    # ---------- API SGS/BCB ----------

    def _buscar_bcb(self, codigo, data_inicial, data_final):
        """Chama a API publica do SGS/BCB pra um intervalo (a propria API
        limita a no maximo 10 anos por chamada). Tolerante a falha de
        rede/API - devolve lista vazia em vez de derrubar o pipeline."""
        url = (
            f"{URL_SGS.format(codigo=codigo)}?formato=json"
            f"&dataInicial={data_inicial.strftime('%d/%m/%Y')}"
            f"&dataFinal={data_final.strftime('%d/%m/%Y')}"
        )
        try:
            with urllib.request.urlopen(url, timeout=45) as resposta:
                bruto = json.loads(resposta.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError, ValueError) as exc:
            print(
                f"dadosgov: falha buscando serie {codigo} ({exc}) - "
                f"intervalo pedido {data_inicial:%d/%m/%Y} a {data_final:%d/%m/%Y} - "
                f"segue sem atualizar nesta rodada"
            )
            return []
        return bruto

    # ---------- coleta incremental de uma serie ----------

    @staticmethod
    def _ultimo_dia_util(agora):
        """Anda pra tras a partir de um pd.Timestamp (exclusive) ate cair
        num dia de semana (seg-sex) - sem calendario de feriados B3, mesma
        aproximacao ja usada em api_server.py (_ultimo_dia_util) pro
        "Dolar Teorico". Selic (432 e 11) so tem valor em dia util. Devolve
        sempre datetime.date puro (nunca pd.Timestamp) - comparar date com
        Timestamp direto (ultima_data_salva() tambem devolve date) daria
        TypeError."""
        dia = (agora - pd.Timedelta(days=1)).date()
        while dia.weekday() >= 5:  # 5=sabado, 6=domingo
            dia -= pd.Timedelta(days=1)
        return dia

    def coletar_serie(self, chave, codigo, nome):
        """Le a ultima data ja salva e busca so o que falta ate o ULTIMO
        DIA UTIL (sem calendario do Copom — a propria API ja sabe quando a
        serie mudou). Primeira coleta (sem historico ainda) pede a janela
        maxima permitida pela API (10 anos) pra tras. Devolve quantos
        pontos novos entraram.

        Ate o ultimo dia util, nao so "ontem" (2026-09-21, 2a rodada apos
        o fix de fuso: a serie 11 ainda deu "HTTP Error 404" pedindo
        19/09 a 20/09/2026 - sabado e domingo, nenhum dos dois dia util).
        Selic (432 e 11) so existe em dia de semana - pedir um intervalo
        caindo inteiro num fim de semana faz a API devolver 404 em vez de
        lista vazia. Parar sempre no ultimo dia util evita a borda: numa
        segunda-feira o limite fica cravado na sexta anterior ate a
        segunda de verdade terminar, entao sabado/domingo nunca chegam a
        virar pedido de rede."""
        limite = self._ultimo_dia_util(pd.Timestamp.now(tz="America/Sao_Paulo"))
        ultima = self._ultima_data_salva(chave)

        if ultima is None:
            data_inicial = limite - pd.Timedelta(days=365 * JANELA_INICIAL_ANOS)
        else:
            data_inicial = ultima + pd.Timedelta(days=1)
            if data_inicial > limite:
                return 0  # ja atualizado ate o ultimo dia util, nada novo pra buscar

        bruto = self._buscar_bcb(codigo, data_inicial, limite)
        if not bruto:
            return 0

        novo_df = pd.DataFrame(bruto)
        if novo_df.empty or "data" not in novo_df.columns or "valor" not in novo_df.columns:
            print(f"dadosgov: resposta da API pra serie {codigo} veio sem os campos esperados - ignorada nesta rodada")
            return 0

        novo_df["data"] = pd.to_datetime(novo_df["data"], format="%d/%m/%Y").dt.date
        novo_df["valor"] = pd.to_numeric(novo_df["valor"], errors="coerce")
        novo_df = novo_df.dropna(subset=["valor"])[["data", "valor"]]
        if novo_df.empty:
            return 0

        caminho = self._caminho(chave)
        if os.path.exists(caminho):
            existente = pd.read_parquet(caminho)
            combinado = pd.concat([existente, novo_df], ignore_index=True)
            combinado = combinado.drop_duplicates(subset="data", keep="last")
        else:
            combinado = novo_df
        combinado = combinado.sort_values("data").reset_index(drop=True)

        combinado.to_parquet(caminho, index=False)
        return len(novo_df)

    def executar(self):
        series = self._carregar_series()
        if not series:
            print("dadosgov: nenhuma serie configurada em config.json -> dados_gov -> bcb")
            return
        for chave, info in series.items():
            try:
                n_novos = self.coletar_serie(chave, info["serie"], info.get("nome", chave))
            except Exception as exc:
                print(f"dadosgov: erro inesperado coletando {chave} ({exc}) - segue pras proximas series")
                continue
            if n_novos:
                print(f"dadosgov: {chave} ({info.get('nome', chave)}) - {n_novos} ponto(s) novo(s)")


if __name__ == "__main__":
    ColetorDadosGov().executar()
