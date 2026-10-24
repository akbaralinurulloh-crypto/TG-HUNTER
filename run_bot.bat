@echo off
chcp 65001 > nul
title Muhtasham Travel - Telegram Umrah AI Agent
echo ========================================================
echo   MUHTASHAM TRAVEL - TELEGRAM UMRAH CONTENT AGENT (v2.0)
echo ========================================================
echo Tizim ishga tushirilmoqda...
cd /d "%~dp0"

:loop
echo [%date% %time%] Agent ishlamoqda...
.\venv\Scripts\python.exe -m app.main
echo.
echo [%date% %time%] Dastur to'xtadi yoki qayta yuklanmoqda (5 soniyada restart)...
timeout /t 5 /nobreak > nul
goto loop
