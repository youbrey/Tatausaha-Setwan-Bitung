@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" call setup_windows.bat
if not exist ".venv\Scripts\python.exe" exit /b 1
".venv\Scripts\python.exe" -m pip install -e ".[build]"
if errorlevel 1 goto :error
".venv\Scripts\pyinstaller.exe" --noconfirm --clean --windowed ^
  --name SekretariatDPRDBitung ^
  --icon src\sekretariat_app\resources\app_icon.ico ^
  --collect-all sekretariat_app ^
  --collect-all tpp_finger_scan ^
  src\sekretariat_app\main.py
if errorlevel 1 goto :error
echo.
echo Build selesai: dist\SekretariatDPRDBitung\SekretariatDPRDBitung.exe
pause
exit /b 0
:error
echo Build gagal.
pause
exit /b 1
