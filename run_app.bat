@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Virtual environment belum tersedia.
  echo Jalankan setup_windows.bat terlebih dahulu.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -m sekretariat_app.main
endlocal
