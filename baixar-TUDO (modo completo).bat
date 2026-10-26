@echo off
title Modo COMPLETO - Painel SFN
cd /d "%~dp0backend"
where python >nul 2>nul
if %errorlevel%==0 ( set PY=python ) else ( set PY=py )
set BCB_MODO=completo
echo ============================================================
echo   MODO COMPLETO: 5 anos de historico + os 16 relatorios
echo   (carteira de credito por risco, modalidade, CNAE, regiao,
echo    cambio, etc). A primeira coleta pode levar 10-20 minutos.
echo ============================================================
echo.
%PY% pipeline.py
echo.
echo Pronto! Agora abra o painel com start.bat
pause
