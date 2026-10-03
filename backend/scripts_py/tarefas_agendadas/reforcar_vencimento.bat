@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul

rem ============================================================
rem  reforcar_vencimento.bat
rem  Reforca o historico M1 dos ativos com VENCIMENTO (Brent/Dolar/
rem  UsaVix - moram em subpasta por mes, parquet/historicos/MTF/<raiz>/
rem  <MM-YYYY>/m1.parquet) rodando historico.py --reforcar --so.
rem
rem  Pedido do usuario (2026-10-01): descobriu que o Brent estava
rem  desatualizado (parado em 2026-09-29 15:30, faltando o dia 30/09
rem  inteiro) comparando com o export direto do MT5 dele -- "sim
rem  resolva, mas deixe de forma automatica". Esses 3 ativos nao fazem
rem  parte do loop de 5min do main.py (so cotacao ao vivo, nao M1
rem  historico fundo) nem tinham reforco agendado -- por isso ficam
rem  pra tras sem ninguem notar.
rem
rem  So funciona com o terminal MT5 (corretora internacional) ABERTO E LOGADO na
rem  hora que rodar -- historico.py precisa da conexao MetaTrader5 pra
rem  resolver o contrato vigente (vigente.py) e baixar o M1. Se o MT5
rem  nao estiver aberto, o historico.py falha e isso fica registrado
rem  no log abaixo (nao trava nem mostra pop-up, pra nao incomodar
rem  quando roda sozinho via Task Scheduler).
rem
rem  Janela de reforco: M1:10 (10 dias) -- so precisa cobrir o gap
rem  desde a ultima rodada (1 dia, normalmente), 10 dias e uma margem
rem  de seguranca caso o agendamento falhe/pule um dia sem ninguem notar.
rem
rem  Agendado via Windows Task Scheduler (schtasks), 1x/dia, de manha
rem  cedo (antes da abertura da B3 as 09h) -- ver instrucoes no
rem  changelog do script (versoes/historico.md ou pedir pro Claude).
rem ============================================================

set PROJETO=D:\escritorio\projetos\dashboard
set SCRIPTS=%PROJETO%\backend\scripts_py
set PYTHON=%SCRIPTS%\venv\Scripts\python.exe
set LOG=%SCRIPTS%\tarefas_agendadas\log_reforco_vencimento.txt

if not exist "%PYTHON%" (
    echo [%date% %time%] ERRO: python.exe da venv nao encontrado em %PYTHON% >> "%LOG%"
    exit /b 1
)

cd /d "%SCRIPTS%"

echo. >> "%LOG%"
echo ============================================================ >> "%LOG%"
echo [%date% %time%] Iniciando reforco Brent/Dolar/UsaVix >> "%LOG%"
echo ============================================================ >> "%LOG%"

"%PYTHON%" historico.py --reforcar M1:10 --so Brent,Dolar,UsaVix >> "%LOG%" 2>&1

if %errorlevel% equ 0 (
    echo [%date% %time%] OK - reforco concluido sem erro >> "%LOG%"
) else (
    echo [%date% %time%] FALHOU - codigo de saida %errorlevel% ^(confira se o MT5 estava aberto/logado^) >> "%LOG%"
)

endlocal
