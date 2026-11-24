@echo off
chcp 65001 >nul
title TG Hunter - Railway Session String
color 0A

echo ====================================================
echo   TG Hunter: Railway uchun SESSION STRING olish
echo ====================================================
echo.
echo Bu skript mavjud hunter.session faylidan
echo Railway platformasiga kerakli SESSION_STRING ni chiqaradi.
echo.

cd /d "%~dp0.."

docker compose run --rm hunter python scripts/export_session_string.py

echo.
echo Yuqoridagi SESSION_STRING ni nusxalab oling va Railway da
echo Environment Variables bo'limiga TG_SESSION_STRING nomi bilan kiriting.
echo.
pause
