@echo off
title Painel SFN - Banco Central
cd /d "%~dp0backend"
where python >nul 2>nul
if %errorlevel%==0 ( set PY=python ) else ( set PY=py )
echo ============================================================
echo   PAINEL SFN - Instituicoes Financeiras do Banco Central
echo ============================================================
echo   Iniciando... o navegador abrira sozinho.
echo   Para FECHAR o painel: feche esta janela.
echo ============================================================
echo.
set BCB_AUTH=0
%PY% app.py
echo.
echo Painel encerrado.
pause
