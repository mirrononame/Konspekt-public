@echo off
chcp 65001 >nul
setlocal EnableExtensions
cd /d "%~dp0"
title Konspekt - Tailscale
echo.
echo  === Доступ до «Конспекту» з телефона через Tailscale ===
echo.

set "TS=%ProgramFiles%\Tailscale\tailscale.exe"
if not exist "%TS%" (
  echo  [1/3] Встановлюю Tailscale...
  winget install -e --id Tailscale.Tailscale --accept-package-agreements --accept-source-agreements
)
if not exist "%TS%" (
  echo.
  echo  [!] Не вдалося встановити автоматично.
  echo      Завантажте вручну: https://tailscale.com/download/windows
  echo      Після встановлення запустіть цей файл ще раз.
  start "" "https://tailscale.com/download/windows"
  pause
  exit /b 1
)
echo  [1/3] Tailscale встановлено.

"%TS%" status >nul 2>&1
if errorlevel 1 (
  echo  [2/3] Увійдіть в акаунт Tailscale ^(Google / Microsoft / GitHub^) у вікні браузера...
  "%TS%" up
  if errorlevel 1 (
    echo  [!] Вхід не завершено. Увійдіть через іконку Tailscale в треї і запустіть файл ще раз.
    pause
    exit /b 1
  )
)
echo  [2/3] Tailscale підключено.

echo  [3/3] Відкриваю «Конспект» для ваших пристроїв...
"%TS%" serve --bg 8765
if errorlevel 1 (
  echo.
  echo  [!] Не вдалося. Якщо вище є посилання — відкрийте його, дозвольте HTTPS/Serve і запустіть файл ще раз.
  echo      Якщо написано "access denied" — запустіть файл від імені адміністратора ^(ПКМ на файлі^).
  pause
  exit /b 1
)
echo.
"%TS%" serve status
echo.
echo  ГОТОВО. На телефоні:
echo    1. Встановіть застосунок Tailscale і увійдіть ТИМ САМИМ акаунтом.
echo    2. Відкрийте адресу https://....ts.net з рядка вище
echo       ^(вона також є в «Конспекті»: Налаштування -^> Доступ з телефона^).
echo    3. Додайте сторінку на головний екран.
echo.
echo  Порада: запустіть create-shortcut.bat і ввімкніть автозапуск,
echo  щоб «Конспект» завжди працював, коли ПК увімкнений.
pause
