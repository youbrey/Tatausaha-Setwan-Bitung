@echo off
REM ============================================================
REM Build SIPS.exe untuk Windows (menggunakan uv)
REM Jalankan file ini di Command Prompt / double-click, dari
REM folder root sips_app (tempat main.py dan build.spec berada).
REM ============================================================

echo [1/5] Membuat virtual environment (venv) via uv...
uv venv
if errorlevel 1 (
    echo ERROR: uv tidak ditemukan. Install uv dulu:
    echo   powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
    pause
    exit /b 1
)

echo [2/5] Mengaktifkan venv...
call .venv\Scripts\activate.bat
if errorlevel 1 (
    echo ERROR: Gagal mengaktifkan virtual environment.
    pause
    exit /b 1
)

echo [3/5] Meng-install dependencies...
uv pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: Gagal install dependencies.
    pause
    exit /b 1
)

echo [4/5] Membersihkan build lama (jika ada)...
rmdir /s /q build 2>nul
rmdir /s /q dist 2>nul

echo [5/5] Build executable dengan PyInstaller...
uv run pyinstaller build.spec
if errorlevel 1 (
    echo ERROR: Build PyInstaller gagal.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo  SELESAI! Hasil build ada di folder: dist\SIPS\
echo  Jalankan dist\SIPS\SIPS.exe untuk mencoba aplikasinya.
echo  Untuk distribusi, copy SELURUH folder dist\SIPS\ (bukan
echo  cuma file .exe-nya saja), karena resources dan DLL
echo  pendukung ada di dalam folder itu.
echo ============================================================
pause
