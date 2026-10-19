@echo off
setlocal
cd /d "%~dp0"
title SysNotch - Push ke GitHub

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" github_push.py
) else (
    python github_push.py
)

if errorlevel 1 (
    echo.
    echo Terjadi kendala saat menjalankan tools.
    pause
)
