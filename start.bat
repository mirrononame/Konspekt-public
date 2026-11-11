@echo off
chcp 65001 >nul
setlocal EnableExtensions
cd /d "%~dp0"
title Konspekt
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

rem ---- 1. Python
set "PY="
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" -c "import sys" >nul 2>&1 && goto :venv_ok
  echo  Середовище .venv пошкоджене ^(можливо, оновився Python^) - створюю заново...
  rmdir /s /q .venv
)
py -3 --version >nul 2>&1 && set "PY=py -3"
if not defined PY (
  python --version >nul 2>&1 && set "PY=python"
)
if not defined PY (
  echo.
  echo  [!] Python не знайдено. Спробую встановити Python 3.12 через winget...
  winget install -e --id Python.Python.3.12 --scope user --accept-package-agreements --accept-source-agreements
  echo.
  echo  Після встановлення ЗАКРИЙТЕ це вікно і запустіть start.bat ще раз.
  echo  Якщо не вийшло — встановіть Python з https://www.python.org/downloads/
  echo  ^(обов'язково поставте галочку "Add python.exe to PATH"^).
  pause
  exit /b 1
)

%PY% -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
if errorlevel 1 (
  echo  [!] Потрібен Python 3.10 або новіший. Встановіть з https://www.python.org/downloads/
  pause
  exit /b 1
)
echo  Перший запуск: створюю середовище .venv ...
%PY% -m venv .venv
if errorlevel 1 (
  echo  [!] Не вдалося створити .venv
  pause
  exit /b 1
)

:venv_ok
rem ---- 2. Залежності (лише якщо змінилися)
fc /b requirements.txt ".venv\installed.txt" >nul 2>&1
if errorlevel 1 (
  echo  Встановлюю залежності...
  ".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -q -r requirements.txt
  if errorlevel 1 (
    echo  [!] Не вдалося встановити залежності. Перевірте інтернет і спробуйте ще раз.
    pause
    exit /b 1
  )
  copy /y requirements.txt ".venv\installed.txt" >nul
)

rem ---- 3. Запуск
".venv\Scripts\python.exe" -m app.server %*
if errorlevel 1 (
  echo.
  echo  [!] Сервер завершився з помилкою. Дані не втрачено.
  pause
)
endlocal
