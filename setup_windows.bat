@echo off
setlocal
cd /d "%~dp0"
py -3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)"
if errorlevel 1 goto :python_error
py -3 -m venv .venv
if errorlevel 1 goto :error
".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto :error
".venv\Scripts\python.exe" -m pip install -e .
if errorlevel 1 goto :error
echo.
echo Instalasi selesai. Jalankan run_app.bat.
pause
exit /b 0
:python_error
echo Python 3.11 atau lebih baru tidak ditemukan.
echo Periksa instalasi dengan perintah: py -0p
pause
exit /b 1
:error
echo Instalasi gagal. Pastikan Python 3.11 atau lebih baru dan akses paket tersedia.
pause
exit /b 1
