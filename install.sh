#!/usr/bin/env bash
# install.sh - Instalación en Linux / macOS (equivalente a install.bat)
set -euo pipefail
cd "$(dirname "$0")"

echo "=== [1/5] Buscando Python 3.12 ==="
PY=""
for candidato in python3.12 python3 python; do
    if command -v "$candidato" >/dev/null 2>&1 && "$candidato" --version 2>&1 | grep -q "Python 3.12"; then
        PY="$candidato"; break
    fi
done
if [ -z "$PY" ] && command -v conda >/dev/null 2>&1; then
    echo "No hay Python 3.12, se crea uno con conda en .conda ..."
    [ -x .conda/bin/python ] || conda create -y -p "$PWD/.conda" python=3.12
    PY="$PWD/.conda/bin/python"
fi
if [ -z "$PY" ]; then
    echo "ERROR: hace falta Python 3.12 (MediaPipe 0.10.21 admite 3.9 - 3.12)." >&2
    exit 1
fi
"$PY" --version

echo "=== [2/5] Creando entorno virtual .venv ==="
[ -x .venv/bin/python ] || "$PY" -m venv .venv

echo "=== [3/5] Instalando dependencias ==="
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt

echo "=== [4/5] Descargando modelo de MediaPipe ==="
.venv/bin/python download_models.py

echo "=== [5/5] Comprobando la instalación ==="
.venv/bin/python -c "import mediapipe, cv2, numpy; print('mediapipe', mediapipe.__version__, '| opencv', cv2.__version__, '| numpy', numpy.__version__)"

echo
echo "Instalación completada. Jugar: .venv/bin/python game.py"
