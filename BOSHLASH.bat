@echo off
chcp 65001 >nul
cd /d "%~dp0"
title TG Hunter
echo.
echo ===== TG Hunter: ishga tushirish =====
echo.
docker info >nul 2>&1
if errorlevel 1 (
  echo XATO: Docker Desktop ishlamayapti.
  echo Docker Desktop ni oching, "Engine running" bo'lguncha kuting va BOSHLASH.bat ni qayta ishga tushiring.
  pause
  exit /b 1
)
if not exist ".env" (
  echo XATO: .env fayli topilmadi. U shu papkada bo'lishi kerak.
  pause
  exit /b 1
)
if not exist "data" mkdir data

echo [1/4] Dastur quriladi (birinchi marta 5-10 daqiqa oladi)...
docker compose build
if errorlevel 1 goto err

if exist "data\hunter.session" (
  echo [2/4] Telegram sessiyasi bor, o'tkazib yuborildi.
) else (
  echo [2/4] Telegramga kirish: telefon raqamingiz (+998...) va Telegramga kelgan kod so'raladi.
  docker compose run --rm hunter python -m scripts.login
  if errorlevel 1 goto err
)

echo [3/4] Tekshiruv...
docker compose run --rm hunter python -m scripts.check --online
if errorlevel 1 (
  echo.
  echo Ba'zi tekshiruvlar muvaffaqiyatsiz. Yuqoridagi ro'yxatni o'qing.
  choice /m "Baribir ishga tushiraymi"
  if errorlevel 2 goto end
)

echo [4/4] Agent ishga tushirilmoqda...
docker compose up -d
if errorlevel 1 goto err
echo.
echo TAYYOR. Bir necha soniyadan keyin bot sizga "TG Hunter ishga tushdi" deb yozadi.
echo Rejim: DRY-RUN (kanalga hech narsa joylanmaydi, postlar sizga ko'rsatiladi).
echo Loglar: LOGLAR.bat   To'xtatish: TOXTATISH.bat
goto end

:err
echo.
echo XATO yuz berdi. Yuqoridagi xabarni skrinshot qilib yuboring.
:end
pause
