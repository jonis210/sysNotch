@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" call install.bat
if errorlevel 1 exit /b 1

echo ============================================================
echo   Mempersiapkan Build Standalone Single-File SysNotch.exe
echo ============================================================

".venv\Scripts\python.exe" -m pip install -r requirements-build.txt
if errorlevel 1 exit /b 1

echo Menghasilkan Icon Maskot Kepala Robot SysNotch.ico...
".venv\Scripts\python.exe" generate_ico.py
if errorlevel 1 exit /b 1

echo Menjalankan PyInstaller Single-File (--onefile)...
".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean --windowed --onefile --name SysNotch --icon=SysNotch.ico --add-data "youtube_extension;youtube_extension" --hidden-import=winrt.windows.foundation --hidden-import=winrt.windows.foundation.collections --hidden-import=winrt.windows.media.control --hidden-import=winrt.windows.storage.streams --hidden-import=psutil dynamic.py
if errorlevel 1 (
    echo.
    echo [X] Gagal melakukan build executable.
    pause
    exit /b 1
)

copy /y "dist\SysNotch.exe" "%~dp0SysNotch.exe" >nul

echo.
echo ============================================================
echo   [V] Build Berhasil! File EXE tunggal tersedia di:
echo       SysNotch.exe (dan dist\SysNotch.exe)
echo ============================================================
echo.
