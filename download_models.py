"""
Descarga los modelos de MediaPipe Pose Landmarker en la carpeta models/.

    python download_models.py           -> descarga el modelo 'full' (el que se usa)
    python download_models.py --todos   -> descarga lite, full y heavy
"""
import os
import sys

import requests
import tqdm

URLS = {
    "pose_landmarker_lite.task": "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/latest/pose_landmarker_lite.task",
    "pose_landmarker_full.task": "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_full/float16/latest/pose_landmarker_full.task",
    "pose_landmarker_heavy.task": "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_heavy/float16/latest/pose_landmarker_heavy.task",
}
CARPETA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models")


def descargar(nombre, url):
    destino = os.path.join(CARPETA, nombre)
    if os.path.exists(destino) and os.path.getsize(destino) > 0:
        print(f"{nombre}: ya existe, se omite.")
        return True
    print(f"Descargando {nombre}...")
    temporal = destino + ".part"
    try:
        with requests.get(url, stream=True, timeout=30) as r:
            r.raise_for_status()
            total = int(r.headers.get("content-length", 0))
            with open(temporal, "wb") as f, tqdm.tqdm(total=total, unit="iB", unit_scale=True) as barra:
                for trozo in r.iter_content(chunk_size=65536):
                    f.write(trozo)
                    barra.update(len(trozo))
        os.replace(temporal, destino)  # así nunca queda un modelo a medias
        return True
    except requests.RequestException as e:
        print(f"ERROR al descargar {nombre}: {e}")
        if os.path.exists(temporal):
            os.remove(temporal)
        return False


if __name__ == "__main__":
    os.makedirs(CARPETA, exist_ok=True)
    nombres = list(URLS) if "--todos" in sys.argv else ["pose_landmarker_full.task"]
    ok = all([descargar(n, URLS[n]) for n in nombres])
    sys.exit(0 if ok else 1)
