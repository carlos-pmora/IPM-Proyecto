@echo off
REM Lanza el juego con el entorno creado por install.bat
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Primero ejecuta install.bat
    pause
    exit /b 1
)
".venv\Scripts\python.exe" game.py %*
if errorlevel 1 pause
