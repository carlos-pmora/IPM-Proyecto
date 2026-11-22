"""
probar_camara.py - Diagnóstico de cámara.

Prueba los índices 0..4 con cada backend de OpenCV disponible en este sistema y
dice cuál da imagen de verdad. Sirve para el problema de "OpenCV solo recibe
imagen negra" (típico de Windows con el backend MSMF, de cámaras IR de Windows
Hello, de la tapa de privacidad o de no haber dado permiso de cámara en macOS).

    python probar_camara.py            -> tabla de resultados
    python probar_camara.py --ver 1    -> muestra la cámara 1 en una ventana (ESC sale)

Si una combinación funciona, se puede fijar la cámara con la variable de entorno
IPM_CAMARA (por ejemplo: set IPM_CAMARA=1 en Windows / export IPM_CAMARA=1).
"""
import argparse
import os

os.environ.setdefault("OPENCV_VIDEOIO_MSMF_ENABLE_HW_TRANSFORMS", "0")

import cv2  # noqa: E402

from vision import _backends, _probar, abrir_camara, consejos_camara  # noqa: E402


def diagnostico():
    print(f"OpenCV {cv2.__version__}\n")
    print(f"{'cámara':<8}{'backend':<14}{'resultado':<16}{'resolución':<12}brillo medio")
    alguna = False
    for indice in range(5):
        existe = False
        for nombre, backend in _backends():
            cap, motivo = _probar(indice, backend, 640, 480)
            existe = existe or motivo != "no se abre"
            res, brillo = "", ""
            if cap is not None:
                ok, frame = cap.read()
                if ok:
                    res = f"{frame.shape[1]}x{frame.shape[0]}"
                    brillo = f"{frame.mean():.0f}"
                cap.release()
                alguna = True
            print(f"{indice:<8}{nombre:<14}{motivo:<16}{res:<12}{brillo}", flush=True)
        if not existe:
            break  # no hay más cámaras
    print()
    if alguna:
        print("Hay al menos una cámara que funciona: vision.py la elige automáticamente.")
    else:
        print("Ninguna cámara da imagen.\n" + consejos_camara())


def ver(indice):
    cap = abrir_camara(indice)
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        cv2.imshow(f"Camara {indice} (ESC para salir)", cv2.flip(frame, 1))
        if cv2.waitKey(1) & 0xFF == 27:
            break
    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--ver", type=int, help="mostrar en vivo la cámara con este índice")
    args = parser.parse_args()
    if args.ver is not None:
        ver(args.ver)
    else:
        diagnostico()
