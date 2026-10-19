@echo off
setlocal
cd /d "%~dp0"

echo ============================================================
echo   Memeriksa Lingkungan Sistem Dynamic Island...
echo ============================================================

if not exist ".venv\Scripts\python.exe" (
    set "PY_CMD="

    where py >nul 2>&1
    if not errorlevel 1 (
        py -3 -c "import sys; exit(0 if sys.version_info >= (3, 9) else 1)" >nul 2>&1
        if not errorlevel 1 set "PY_CMD=py -3"
    )

    if not defined PY_CMD (
        where python >nul 2>&1
        if not errorlevel 1 (
            python -c "import sys; exit(0 if sys.version_info >= (3, 9) else 1)" >nul 2>&1
            if not errorlevel 1 set "PY_CMD=python"
        )
    )

    if not defined PY_CMD (
        where python3 >nul 2>&1
        if not errorlevel 1 (
            python3 -c "import sys; exit(0 if sys.version_info >= (3, 9) else 1)" >nul 2>&1
            if not errorlevel 1 set "PY_CMD=python3"
        )
    )

    if not defined PY_CMD (
        echo.
        echo ============================================================
        echo [!] Python 3.9+ belum terpasang di komputer ini.
        echo.
        echo Silakan ikuti 2 langkah mudah ini:
        echo 1. Unduh Python dari: https://www.python.org/downloads/
        echo 2. PENTING: Saat instalasi, centang kotak "Add python.exe to PATH"
        echo 3. Setelah selesai, klik ganda lagi start.bat.
        echo ============================================================
        echo.
        pause
        exit /b 1
    )

    echo [1/3] Membuat lingkungan virtual Python (.venv)...
    %PY_CMD% -m venv .venv
    if errorlevel 1 (
        echo.
        echo [X] Gagal membuat virtual environment .venv.
        echo Pastikan izin folder mencukupi.
        pause
        exit /b 1
    )
)

echo [2/3] Memperbarui pip installer...
".venv\Scripts\python.exe" -m pip install --upgrade pip >nul 2>&1

echo [3/3] Memasang dependensi aplikasi dari requirements.txt...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo ============================================================
    echo [!] Gagal menginstal dependensi.
    echo Pastikan komputer terhubung ke internet saat instalasi pertama kali.
    echo ============================================================
    echo.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo   [V] Instalasi Berhasil! Dynamic Island Siap Dijalankan.
echo ============================================================
echo.
