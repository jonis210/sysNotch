@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" call install.bat
if errorlevel 1 exit /b 1

echo ============================================================
echo   Mempersiapkan Build Standalone SysNotch.exe
echo ============================================================

".venv\Scripts\python.exe" -m pip install -r requirements-build.txt
if errorlevel 1 exit /b 1

echo Menjalankan PyInstaller...
".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean --windowed --onedir --name SysNotch --hidden-import=winrt.windows.foundation --hidden-import=winrt.windows.foundation.collections --hidden-import=winrt.windows.media.control --hidden-import=winrt.windows.storage.streams --hidden-import=psutil dynamic.py
if errorlevel 1 (
    echo.
    echo [X] Gagal melakukan build executable.
    pause
    exit /b 1
)

echo.
echo Menyiapkan folder ekstensi YouTube...
if not exist "dist\SysNotch\youtube_extension" mkdir "dist\SysNotch\youtube_extension"
xcopy "youtube_extension\*" "dist\SysNotch\youtube_extension\" /E /I /Y >nul

echo.
echo ============================================================
echo   [V] Build Berhasil! File EXE tersedia di:
echo       dist\SysNotch\SysNotch.exe
echo ============================================================
echo.

