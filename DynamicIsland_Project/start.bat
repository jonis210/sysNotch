@echo off
setlocal
cd /d "%~dp0"

if exist "dist\SysNotch\SysNotch.exe" (
    start "SysNotch" "dist\SysNotch\SysNotch.exe"
    exit /b 0
)

if not exist ".venv\Scripts\python.exe" (
    call install.bat
    if errorlevel 1 exit /b 1
)
if not exist ".venv\Scripts\pythonw.exe" (
    call install.bat
    if errorlevel 1 exit /b 1
)

".venv\Scripts\python.exe" -c "import PyQt6" >nul 2>&1
if errorlevel 1 (
    echo Dependensi aplikasi belum lengkap. Memasang dependensi yang diperlukan...
    call install.bat
    if errorlevel 1 exit /b 1
)

start "SysNotch" ".venv\Scripts\pythonw.exe" "%~dp0dynamic.py"


