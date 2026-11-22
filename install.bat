@echo off
REM ==========================================================================
REM  install.bat - Instala el proyecto en un Windows limpio
REM    1. Busca Python 3.12 (py launcher, python del PATH o conda)
REM    2. Crea el entorno virtual .venv
REM    3. Instala requirements.txt
REM    4. Descarga el modelo de MediaPipe
REM    5. Comprueba que todo se importa bien
REM ==========================================================================
setlocal
cd /d "%~dp0"

echo.
echo === [1/5] Buscando Python 3.12 ===
set "PY="

REM a) py launcher (instalador oficial de python.org)
py -3.12 --version >nul 2>&1 && set "PY=py -3.12"

REM b) python del PATH, si es 3.12
if not defined PY (
    python --version 2>nul | findstr /C:"Python 3.12" >nul && set "PY=python"
)

REM c) conda: crea un Python 3.12 local en .conda (sin tocar otros entornos)
if not defined PY (
    where conda >nul 2>&1 && (
        echo No hay Python 3.12, se crea uno con conda en .conda ...
        if not exist ".conda\python.exe" call conda create -y -p "%~dp0.conda" python=3.12
        if exist ".conda\python.exe" set PY="%~dp0.conda\python.exe"
    )
)

if not defined PY (
    echo.
    echo ERROR: No se ha encontrado Python 3.12.
    echo MediaPipe 0.10.21 necesita Python 3.9 - 3.12. Instala Python 3.12 con:
    echo     winget install -e --id Python.Python.3.12
    echo o desde https://www.python.org/downloads/release/python-31210/
    echo y vuelve a ejecutar install.bat
    pause
    exit /b 1
)
%PY% --version

echo.
echo === [2/5] Creando entorno virtual .venv ===
if exist ".venv\Scripts\python.exe" (
    echo .venv ya existe, se reutiliza.
) else (
    %PY% -m venv .venv || goto :error
)
set "VPY=%~dp0.venv\Scripts\python.exe"

echo.
echo === [3/5] Instalando dependencias ===
"%VPY%" -m pip install --upgrade pip || goto :error
"%VPY%" -m pip install -r requirements.txt || goto :error

echo.
echo === [4/5] Descargando modelo de MediaPipe ===
"%VPY%" download_models.py || goto :error

echo.
echo === [5/5] Comprobando la instalacion ===
"%VPY%" -c "import mediapipe, cv2, numpy; print('mediapipe', mediapipe.__version__, '| opencv', cv2.__version__, '| numpy', numpy.__version__)" || goto :error

echo.
echo ==========================================================
echo  Instalacion completada.
echo    Jugar:               jugar.bat
echo    Probar la camara:    .venv\Scripts\python probar_camara.py
echo    Demo de vision:      .venv\Scripts\python vision.py
echo ==========================================================
pause
exit /b 0

:error
echo.
echo ERROR durante la instalacion. Revisa los mensajes de arriba.
pause
exit /b 1
