@echo off
title Testes - Painel SFN
cd /d "%~dp0backend"
where python >nul 2>nul
if %errorlevel%==0 ( set PY=python ) else ( set PY=py )
echo ============================================================
echo   Bateria de testes do Hub do SFN
echo   (valida endpoints, agregacoes e TODOS os tipos de instituicao)
echo ============================================================
echo.
%PY% testes\test_hub.py
echo.
pause
