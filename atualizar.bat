@echo off
title Atualizar dados - Painel SFN
cd /d "%~dp0backend"
where python >nul 2>nul
if %errorlevel%==0 ( set PY=python ) else ( set PY=py )
echo ============================================================
echo   Baixando dados mais recentes do Banco Central...
echo   (pode levar alguns minutos)
echo ============================================================
echo.
%PY% pipeline.py
echo.
echo Pronto! Abra o painel com start.bat
pause
