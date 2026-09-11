@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" call setup_windows.bat
if not exist ".venv\Scripts\python.exe" exit /b 1
".venv\Scripts\python.exe" -m pip install -e ".[build]"
if errorlevel 1 goto :error
set TESSDATA_DIR=
if exist "%~dp0eng.traineddata" set "TESSDATA_DIR=%~dp0"
if defined TESSDATA_PREFIX if exist "%TESSDATA_PREFIX%\eng.traineddata" set "TESSDATA_DIR=%TESSDATA_PREFIX%"
if not defined TESSDATA_DIR if exist "%ProgramFiles%\Tesseract-OCR\tessdata\eng.traineddata" set "TESSDATA_DIR=%ProgramFiles%\Tesseract-OCR\tessdata"
if not defined TESSDATA_DIR if exist "%LOCALAPPDATA%\Programs\Tesseract-OCR\tessdata\eng.traineddata" set "TESSDATA_DIR=%LOCALAPPDATA%\Programs\Tesseract-OCR\tessdata"
set TESSDATA_OPTION=
if defined TESSDATA_DIR set TESSDATA_OPTION=--add-data "%TESSDATA_DIR%\eng.traineddata;tpp_finger_scan\resources\tessdata"
if not defined TESSDATA_DIR echo PERINGATAN: eng.traineddata tidak ditemukan. PDF finger scan berbentuk gambar memerlukan Tesseract OCR lokal.
".venv\Scripts\pyinstaller.exe" --noconfirm --clean --windowed ^
  --name SekretariatDPRDBitung ^
  --icon src\sekretariat_app\resources\app_icon.ico ^
  --collect-all sekretariat_app ^
  --collect-all tpp_finger_scan ^
  --collect-all pymupdf ^
  --collect-all reportlab ^
  %TESSDATA_OPTION% ^
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
