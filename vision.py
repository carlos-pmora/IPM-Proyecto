"""
vision.py - Módulo de visión por computador (MediaPipe Pose).

Cumple el CONTRATO ENTRE MÓDULOS: en cada fotograma, ``Vision.leer()`` devuelve
un diccionario con estos campos (game.py solo lee de él):

    persona   : bool                     -> hay alguien detectado
    mano_izq  : (x, y) | None            -> posición normalizada 0..1 (None si no se ve)
    mano_der  : (x, y) | None
    angulos   : {nombre: grados | None}  -> codo, hombro, cadera, rodilla, tronco
    frame     : np.ndarray (BGR)         -> imagen de la cámara ya volteada (modo espejo)

Campos extra (opcionales, el juego puede ignorarlos):

    puntos    : {nombre: (x, y)}         -> puntos clave visibles (normalizados)
    extension : {'izq': f|None, 'der': f|None}
                -> distancia mano-hombro / alcance calibrado (1.0 = brazo estirado
                   como en la calibración). None si no hay calibración.
    alcance   : dict | None              -> resultado de la calibración (ver Calibracion)
    tiempo    : float                    -> instante del fotograma (time.time())

"izquierda" y "derecha" son SIEMPRE las del jugador. Como la imagen está en modo
espejo, su mano izquierda aparece en la parte izquierda de la pantalla.

Uso mínimo:

    from vision import Vision
    with Vision() as vision:
        while True:
            datos = vision.leer()
            if datos is None:      # se acabó el vídeo / cámara perdida
                break
            ...

Ejecutar ``python vision.py`` abre una demo que muestra el esqueleto, las manos
y los ángulos. ``python vision.py --calibrar`` lanza la calibración.
"""

import json
import math
import os
import sys
import time

# En Windows, el backend MSMF tarda mucho en abrir la cámara si esto está activo.
os.environ.setdefault("OPENCV_VIDEOIO_MSMF_ENABLE_HW_TRANSFORMS", "0")

import cv2  # noqa: E402
import mediapipe as mp  # noqa: E402
import numpy as np  # noqa: E402

from config import config  # noqa: E402


# --------------------------------------------------------------------------- #
#  Puntos clave de MediaPipe Pose (índices del modelo, vista de la persona)    #
# --------------------------------------------------------------------------- #
PUNTOS = {
    "nariz": 0,
    "hombro_izq": 11, "hombro_der": 12,
    "codo_izq": 13, "codo_der": 14,
    "muneca_izq": 15, "muneca_der": 16,
    "menique_izq": 17, "menique_der": 18,
    "indice_izq": 19, "indice_der": 20,
    "cadera_izq": 23, "cadera_der": 24,
    "rodilla_izq": 25, "rodilla_der": 26,
    "tobillo_izq": 27, "tobillo_der": 28,
    "talon_izq": 29, "talon_der": 30,
    "pie_izq": 31, "pie_der": 32,
}

# Ángulos disponibles: nombre -> (punto A, VÉRTICE, punto B)
ANGULOS = {
    "codo_izq": ("hombro_izq", "codo_izq", "muneca_izq"),
    "codo_der": ("hombro_der", "codo_der", "muneca_der"),
    # Hombro: ángulo entre el tronco y el brazo (0 = brazo pegado, 90 = en cruz, 180 = arriba)
    "hombro_izq": ("cadera_izq", "hombro_izq", "codo_izq"),
    "hombro_der": ("cadera_der", "hombro_der", "codo_der"),
    "cadera_izq": ("hombro_izq", "cadera_izq", "rodilla_izq"),
    "cadera_der": ("hombro_der", "cadera_der", "rodilla_der"),
    "rodilla_izq": ("cadera_izq", "rodilla_izq", "tobillo_izq"),
    "rodilla_der": ("cadera_der", "rodilla_der", "tobillo_der"),
}
# Además se calcula "tronco": inclinación del tronco respecto a la vertical (0 = recto).

CONEXIONES = [
    ("hombro_izq", "hombro_der"), ("hombro_izq", "cadera_izq"), ("hombro_der", "cadera_der"),
    ("cadera_izq", "cadera_der"),
    ("hombro_izq", "codo_izq"), ("codo_izq", "muneca_izq"),
    ("hombro_der", "codo_der"), ("codo_der", "muneca_der"),
    ("cadera_izq", "rodilla_izq"), ("rodilla_izq", "tobillo_izq"),
    ("cadera_der", "rodilla_der"), ("rodilla_der", "tobillo_der"),
    ("tobillo_izq", "talon_izq"), ("talon_izq", "pie_izq"), ("tobillo_izq", "pie_izq"),
    ("tobillo_der", "talon_der"), ("talon_der", "pie_der"), ("tobillo_der", "pie_der"),
]


# --------------------------------------------------------------------------- #
#  Cámara                                                                      #
# --------------------------------------------------------------------------- #
def _es_imagen_negra(frame) -> bool:
    return frame is None or (frame.mean() < 4 and frame.std() < 4)


def _backends():
    """Backends de OpenCV a probar, en orden. En Windows, DirectShow primero:
    es lo que suele arreglar la 'imagen negra' que da MSMF en algunos portátiles.
    En macOS solo AVFoundation (ANY es el mismo backend y repetirlo solo hace perder tiempo)."""
    if sys.platform.startswith("win"):
        return [("DSHOW", cv2.CAP_DSHOW), ("MSMF", cv2.CAP_MSMF)]
    if sys.platform == "darwin":
        return [("AVFOUNDATION", cv2.CAP_AVFOUNDATION)]
    return [("V4L2", cv2.CAP_V4L2), ("ANY", cv2.CAP_ANY)]


def _probar(indice, backend, ancho, alto, espera=3.0):
    """Abre una cámara y comprueba que da imagen de verdad (no negra).
    Al arrancar, muchas cámaras (sobre todo en Mac) dan 1-2 s de imágenes negras,
    así que se espera hasta `espera` segundos. Devuelve (cap, motivo); cap es None si no sirve."""
    cap = cv2.VideoCapture(indice, backend)
    if not cap.isOpened():
        cap.release()
        return None, "no se abre"
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, ancho)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, alto)
    leidos = 0
    limite = time.time() + espera
    while time.time() < limite:
        ok, frame = cap.read()
        if ok:
            leidos += 1
            if not _es_imagen_negra(frame):
                return cap, "ok"
        else:
            time.sleep(0.05)
    cap.release()
    return None, "imagen negra" if leidos else "no da imágenes"


def consejos_camara():
    if sys.platform == "darwin":
        return ("En Mac: Ajustes del Sistema > Privacidad y seguridad > Cámara > activa la\n"
                "Terminal (o VS Code) y vuelve a abrirla. La primera vez macOS pide el permiso\n"
                "y hay que ejecutar el programa otra vez. Cierra FaceTime, Zoom, Teams...")
    if sys.platform.startswith("win"):
        return ("Cierra Teams, Zoom, el navegador u OBS; revisa la tapa o tecla de privacidad y\n"
                "Configuración > Privacidad > Cámara > permitir a las aplicaciones de escritorio.\n"
                "Alternativa: usar el móvil como webcam (Iriun / DroidCam).")
    return "Comprueba que la cámara existe (ls /dev/video*) y que no la usa otra aplicación."


def abrir_camara(fuente=None, ancho=None, alto=None, verbose=True):
    """Abre la cámara (o un vídeo) y devuelve un cv2.VideoCapture listo.

    fuente: None -> busca automáticamente (índices 0, 1, 2... hasta que uno no exista)
            int  -> ese índice de cámara
            str  -> ruta a un fichero de vídeo (útil para probar sin cámara)
    """
    ancho = ancho or config.camara_ancho
    alto = alto or config.camara_alto

    if isinstance(fuente, str) and not fuente.isdigit():
        cap = cv2.VideoCapture(fuente)
        if not cap.isOpened():
            raise RuntimeError(f"No se puede abrir el vídeo '{fuente}'")
        return cap

    indices = [int(fuente)] if fuente is not None else range(5)
    informe = []
    for indice in indices:
        existe = False
        for nombre, backend in _backends():
            if verbose:
                print(f"[vision] Probando cámara {indice} ({nombre})...", flush=True)
            cap, motivo = _probar(indice, backend, ancho, alto)
            informe.append(f"  cámara {indice} / {nombre}: {motivo}")
            existe = existe or motivo != "no se abre"
            if cap is not None:
                if verbose:
                    print(f"[vision] Usando cámara {indice} con backend {nombre}")
                return cap
        if not existe:
            break  # las cámaras van seguidas: si esta no existe, las siguientes tampoco
    raise RuntimeError(
        "No se ha encontrado ninguna cámara que dé imagen.\n" + "\n".join(informe) +
        "\n" + consejos_camara() + "\nPara más detalle: python probar_camara.py"
    )


# --------------------------------------------------------------------------- #
#  Geometría                                                                   #
# --------------------------------------------------------------------------- #
def angulo(a, b, c, w=1.0, h=1.0):
    """Ángulo ABC en grados (vértice en b). Los puntos están normalizados; w y h
    corrigen la relación de aspecto para que el ángulo sea el real en la imagen."""
    if a is None or b is None or c is None:
        return None
    v1 = ((a[0] - b[0]) * w, (a[1] - b[1]) * h)
    v2 = ((c[0] - b[0]) * w, (c[1] - b[1]) * h)
    n1, n2 = math.hypot(*v1), math.hypot(*v2)
    if n1 < 1e-6 or n2 < 1e-6:
        return None
    cos = (v1[0] * v2[0] + v1[1] * v2[1]) / (n1 * n2)
    return math.degrees(math.acos(max(-1.0, min(1.0, cos))))


def distancia(p1, p2, w=1.0, h=1.0):
    if p1 is None or p2 is None:
        return None
    return math.hypot((p1[0] - p2[0]) * w, (p1[1] - p2[1]) * h)


def _medio(p1, p2):
    if p1 is None or p2 is None:
        return None
    return ((p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2)


# --------------------------------------------------------------------------- #
#  Visión                                                                      #
# --------------------------------------------------------------------------- #
class Vision:
    """Lee la cámara, ejecuta MediaPipe Pose y devuelve el diccionario del contrato."""

    def __init__(self, fuente=None, modelo_path=None, dibujar=False, angulos=None,
                 visibilidad_min=None, suavizado=None, calibracion=True):
        """
        fuente      : None (auto), índice de cámara o ruta de vídeo. Por defecto config.camara.
        dibujar     : si True, dibuja el esqueleto sobre datos['frame'].
        angulos     : lista de ángulos a calcular (por defecto todos + 'tronco').
        calibracion : True -> carga calibracion.json si existe; False -> no; dict -> usa ese.
        """
        modelo_path = modelo_path or config.model_path
        if not os.path.exists(modelo_path):
            raise FileNotFoundError(
                f"No se encuentra el modelo '{modelo_path}'. Ejecuta: python download_models.py")

        with open(modelo_path, "rb") as f:
            modelo_bytes = f.read()

        self.dibujar = dibujar
        self.nombres_angulos = list(angulos) if angulos else list(ANGULOS) + ["tronco"]
        self.vis_min = config.visibilidad_min if visibilidad_min is None else visibilidad_min
        self.alfa = config.suavizado if suavizado is None else suavizado

        opciones = mp.tasks.vision.PoseLandmarkerOptions(
            # Se pasa el modelo en memoria (no la ruta): en Windows MediaPipe no abre
            # rutas con tildes o símbolos (p. ej. "Interacción Persona-Máquina").
            base_options=mp.tasks.BaseOptions(model_asset_buffer=modelo_bytes),
            running_mode=mp.tasks.vision.RunningMode.VIDEO,
            num_poses=1,
        )
        self.landmarker = mp.tasks.vision.PoseLandmarker.create_from_options(opciones)

        fuente = config.camara if fuente is None else fuente
        self.cap = abrir_camara(fuente) if fuente != "ninguna" else None
        self._t0 = time.time()
        self._ultimo_ts = -1
        self._suave = {}

        if isinstance(calibracion, dict):
            self.alcance = calibracion
        elif calibracion:
            self.alcance = cargar_calibracion()
        else:
            self.alcance = None

    # -- ciclo de vida ------------------------------------------------------ #
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.cerrar()

    def cerrar(self):
        if self.cap is not None:
            self.cap.release()
            self.cap = None
        if self.landmarker is not None:
            self.landmarker.close()
            self.landmarker = None

    # -- lectura ------------------------------------------------------------ #
    def leer(self):
        """Lee un fotograma de la cámara y lo procesa. Devuelve None si no hay más imágenes."""
        if self.cap is None:
            return None
        ok, frame = self.cap.read()
        if not ok or frame is None:
            return None
        return self.procesar(frame)

    def procesar(self, frame_bgr, timestamp_ms=None):
        """Procesa una imagen BGR SIN voltear (tal cual sale de la cámara) y
        devuelve el diccionario del contrato. Útil también para probar con imágenes."""
        h, w = frame_bgr.shape[:2]

        # MediaPipe espera RGB. Se detecta sobre la imagen original (así las etiquetas
        # izquierda/derecha del modelo son correctas) y luego se reflejan las x.
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        imagen = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        if timestamp_ms is None:
            timestamp_ms = int((time.time() - self._t0) * 1000)
        timestamp_ms = max(timestamp_ms, self._ultimo_ts + 1)  # debe ser creciente
        self._ultimo_ts = timestamp_ms
        resultado = self.landmarker.detect_for_video(imagen, timestamp_ms)

        frame = cv2.flip(frame_bgr, 1)  # modo espejo
        puntos = {}
        if resultado.pose_landmarks:
            lm = resultado.pose_landmarks[0]
            for nombre, idx in PUNTOS.items():
                p = lm[idx]
                if p.visibility >= self.vis_min and -0.1 <= p.x <= 1.1 and -0.1 <= p.y <= 1.1:
                    puntos[nombre] = self._suavizar(nombre, (1.0 - p.x, p.y))
                else:
                    self._suave.pop(nombre, None)
        else:
            self._suave.clear()

        persona = bool(resultado.pose_landmarks) and (
            "hombro_izq" in puntos or "hombro_der" in puntos or "nariz" in puntos)

        datos = {
            "persona": persona,
            "mano_izq": self._mano(puntos, "izq"),
            "mano_der": self._mano(puntos, "der"),
            "angulos": self._angulos(puntos, w, h),
            "frame": frame,
            # extras
            "puntos": puntos,
            "extension": {"izq": self._extension(puntos, "izq", w, h),
                          "der": self._extension(puntos, "der", w, h)},
            "alcance": self.alcance,
            "tiempo": time.time(),
        }
        if self.dibujar:
            dibujar_esqueleto(frame, datos)
        return datos

    # -- cálculos internos -------------------------------------------------- #
    def _suavizar(self, nombre, p):
        """Media móvil exponencial para quitar el temblor de los puntos."""
        anterior = self._suave.get(nombre)
        if anterior is not None and self.alfa > 0:
            p = (anterior[0] * self.alfa + p[0] * (1 - self.alfa),
                 anterior[1] * self.alfa + p[1] * (1 - self.alfa))
        self._suave[nombre] = p
        return p

    @staticmethod
    def _mano(puntos, lado):
        """Centro de la mano = media de muñeca, índice y meñique (lo que se vea)."""
        if f"muneca_{lado}" not in puntos:
            return None
        ps = [puntos[f"{n}_{lado}"] for n in ("muneca", "indice", "menique") if f"{n}_{lado}" in puntos]
        x = sum(p[0] for p in ps) / len(ps)
        y = sum(p[1] for p in ps) / len(ps)
        return (min(max(x, 0.0), 1.0), min(max(y, 0.0), 1.0))

    def _angulos(self, puntos, w, h):
        resultado = {}
        for nombre in self.nombres_angulos:
            if nombre == "tronco":
                hombros = _medio(puntos.get("hombro_izq"), puntos.get("hombro_der"))
                caderas = _medio(puntos.get("cadera_izq"), puntos.get("cadera_der"))
                arriba = (caderas[0], caderas[1] - 1.0) if caderas else None
                resultado[nombre] = angulo(hombros, caderas, arriba, w, h)
            elif nombre in ANGULOS:
                a, b, c = ANGULOS[nombre]
                resultado[nombre] = angulo(puntos.get(a), puntos.get(b), puntos.get(c), w, h)
        return resultado

    def _extension(self, puntos, lado, w, h):
        """Distancia mano-hombro relativa al alcance calibrado (1.0 = máximo calibrado)."""
        if not self.alcance:
            return None
        ancho_hombros = distancia(puntos.get("hombro_izq"), puntos.get("hombro_der"), w, h)
        d = distancia(self._mano(puntos, lado), puntos.get(f"hombro_{lado}"), w, h)
        brazo = self.alcance.get(f"brazo_{lado}")
        if not ancho_hombros or d is None or not brazo:
            return None
        return (d / ancho_hombros) / brazo

    # -- calibración -------------------------------------------------------- #
    def calibrar(self, ventana="Calibracion", guardar=True):
        """Calibración con su propia ventana de OpenCV. Devuelve el resultado (o None
        si se cancela con ESC). Si el juego usa otra librería gráfica, usar la clase
        Calibracion directamente (ver su docstring)."""
        cal = Calibracion()
        while not cal.terminada:
            datos = self.leer()
            if datos is None:
                break
            cal.actualizar(datos)
            dibujar_esqueleto(datos["frame"], datos)
            cal.dibujar(datos["frame"])
            cv2.imshow(ventana, datos["frame"])
            if cal.fase == 0 and cal.t_fase == 0:
                cv2.setWindowProperty(ventana, cv2.WND_PROP_TOPMOST, 1)
            if cv2.waitKey(1) & 0xFF == 27:
                break
        cv2.destroyWindow(ventana)
        if cal.terminada:
            self.alcance = cal.resultado
            if guardar:
                guardar_calibracion(cal.resultado)
        return cal.resultado if cal.terminada else None


# --------------------------------------------------------------------------- #
#  Calibración                                                                 #
# --------------------------------------------------------------------------- #
class Calibracion:
    """Mide el alcance del jugador en tres fases:

      1. colocarse : esperar a que se le vea de cabeza a cadera, quieto.
      2. cruz      : brazos estirados en cruz (alcance lateral).
      3. arriba    : brazos estirados por encima de la cabeza (alcance vertical).

    No depende de ninguna librería gráfica. En cada fotograma:

        cal.actualizar(datos)        # datos = vision.leer()
        cal.mensaje, cal.progreso    # texto a mostrar y progreso 0..1 de la fase
        cal.terminada                # True al acabar -> cal.resultado

    Resultado (todo normalizado 0..1 respecto a la imagen):
        zona          : (x_min, y_min, x_max, y_max) donde llegan las manos -> poner
                        aquí los objetivos para que sean alcanzables.
        centro        : (x, y) centro de los hombros.
        ancho_hombros : en coordenadas normalizadas (x).
        brazo_izq/der : longitud del brazo en "anchos de hombros" (independiente
                        de la distancia a la cámara).
        alcance_arriba: y mínima alcanzada con las manos.
    """

    FASES = [
        ("colocarse", 2.0, "Colocate a unos 2 m: que se te vea de cabeza a cadera"),
        ("cruz", 4.0, "Estira los brazos en cruz"),
        ("arriba", 4.0, "Sube los brazos por encima de la cabeza"),
    ]

    def __init__(self):
        self.fase = 0
        self.t_fase = 0.0
        self._t_anterior = None
        self.muestras = {"brazo_izq": [], "brazo_der": [], "x": [], "y": [],
                         "centro": [], "hombros": [], "caderas_y": []}
        self.resultado = None

    @property
    def terminada(self):
        return self.resultado is not None

    @property
    def nombre_fase(self):
        return "listo" if self.terminada else self.FASES[self.fase][0]

    @property
    def mensaje(self):
        return "Calibracion completada" if self.terminada else self.FASES[self.fase][2]

    @property
    def progreso(self):
        return 1.0 if self.terminada else min(self.t_fase / self.FASES[self.fase][1], 1.0)

    def actualizar(self, datos):
        if self.terminada:
            return self.nombre_fase
        ahora = datos.get("tiempo", time.time())
        dt = 0.0 if self._t_anterior is None else min(ahora - self._t_anterior, 0.2)
        self._t_anterior = ahora

        p = datos["puntos"]
        h, w = datos["frame"].shape[:2]
        visible = all(k in p for k in ("hombro_izq", "hombro_der", "cadera_izq", "cadera_der"))
        if not (datos["persona"] and visible):
            if self.FASES[self.fase][0] == "colocarse":
                self.t_fase = 0.0  # tiene que estar visible de forma continuada
            return self.nombre_fase

        fase = self.FASES[self.fase][0]
        if fase != "colocarse":
            manos = {"izq": datos["mano_izq"], "der": datos["mano_der"]}
            ancho = distancia(p["hombro_izq"], p["hombro_der"], w, h)
            # el tiempo solo avanza si se ven las dos manos
            if manos["izq"] is None or manos["der"] is None or not ancho:
                return self.nombre_fase
            for lado, mano in manos.items():
                self.muestras[f"brazo_{lado}"].append(
                    distancia(mano, p[f"hombro_{lado}"], w, h) / ancho)
                self.muestras["x"].append(mano[0])
                self.muestras["y"].append(mano[1])
            self.muestras["centro"].append(_medio(p["hombro_izq"], p["hombro_der"]))
            self.muestras["hombros"].append(abs(p["hombro_izq"][0] - p["hombro_der"][0]))
            self.muestras["caderas_y"].append((p["cadera_izq"][1] + p["cadera_der"][1]) / 2)

        self.t_fase += dt
        if self.t_fase >= self.FASES[self.fase][1]:
            self.fase += 1
            self.t_fase = 0.0
            if self.fase >= len(self.FASES):
                self._calcular()
        return self.nombre_fase

    def _calcular(self):
        m = self.muestras
        pct = lambda v, q: float(np.percentile(v, q))  # percentiles: ignora picos raros
        centro = np.mean(np.array(m["centro"]), axis=0)
        self.resultado = {
            "zona": (pct(m["x"], 3), pct(m["y"], 3),
                     pct(m["x"], 97), max(pct(m["y"], 97), pct(m["caderas_y"], 50))),
            "centro": (float(centro[0]), float(centro[1])),
            "ancho_hombros": pct(m["hombros"], 50),
            "brazo_izq": pct(m["brazo_izq"], 95),
            "brazo_der": pct(m["brazo_der"], 95),
            "alcance_arriba": pct(m["y"], 3),
            "fecha": time.strftime("%Y-%m-%d %H:%M:%S"),
        }

    def dibujar(self, frame):
        """Dibuja el mensaje, la barra de progreso y (al final) la zona alcanzable."""
        h, w = frame.shape[:2]
        cv2.rectangle(frame, (0, 0), (w, 70), (0, 0, 0), -1)
        cv2.putText(frame, self.mensaje, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        cv2.rectangle(frame, (10, 45), (w - 10, 60), (80, 80, 80), 1)
        cv2.rectangle(frame, (10, 45), (10 + int((w - 20) * self.progreso), 60), (0, 200, 0), -1)
        if self.terminada:
            x0, y0, x1, y1 = self.resultado["zona"]
            cv2.rectangle(frame, (int(x0 * w), int(y0 * h)), (int(x1 * w), int(y1 * h)), (0, 255, 255), 2)


def guardar_calibracion(resultado, ruta=None):
    with open(ruta or config.calibracion_path, "w", encoding="utf-8") as f:
        json.dump(resultado, f, indent=2)


def cargar_calibracion(ruta=None):
    ruta = ruta or config.calibracion_path
    if not os.path.exists(ruta):
        return None
    try:
        with open(ruta, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


# --------------------------------------------------------------------------- #
#  Dibujo (opcional)                                                           #
# --------------------------------------------------------------------------- #
def dibujar_esqueleto(frame, datos, angulos=True):
    """Dibuja huesos, puntos, manos y ángulos sobre el frame (in situ)."""
    h, w = frame.shape[:2]
    p = datos["puntos"]
    px = lambda q: (int(q[0] * w), int(q[1] * h))
    for a, b in CONEXIONES:
        if a in p and b in p:
            cv2.line(frame, px(p[a]), px(p[b]), (255, 200, 0), 2)
    for q in p.values():
        cv2.circle(frame, px(q), 4, (0, 255, 0), -1)
    for lado, color in (("izq", (0, 140, 255)), ("der", (255, 0, 255))):
        mano = datos[f"mano_{lado}"]
        if mano is not None:
            cv2.circle(frame, px(mano), 14, color, 3)
    if angulos:
        for nombre, valor in datos["angulos"].items():
            if valor is not None and nombre in p:
                x, y = px(p[nombre])
                cv2.putText(frame, f"{valor:.0f}", (x + 8, y - 8),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
    return frame


# --------------------------------------------------------------------------- #
#  Demo: python vision.py [--calibrar] [--camara N | --video ruta]             #
# --------------------------------------------------------------------------- #
def _demo():
    import argparse
    parser = argparse.ArgumentParser(description="Demo del módulo de visión")
    parser.add_argument("--camara", type=int, help="índice de la cámara (por defecto: automático)")
    parser.add_argument("--video", help="usar un fichero de vídeo en vez de la cámara")
    parser.add_argument("--calibrar", action="store_true", help="hacer la calibración antes")
    args = parser.parse_args()

    fuente = args.video if args.video else args.camara
    with Vision(fuente=fuente, dibujar=True) as vision:
        if args.calibrar:
            resultado = vision.calibrar()
            print("Calibración:", json.dumps(resultado, indent=2) if resultado else "cancelada")
        t_prev, fps, primera = time.time(), 0.0, True
        while True:
            datos = vision.leer()
            if datos is None:
                break
            ahora = time.time()
            fps = 0.9 * fps + 0.1 / max(ahora - t_prev, 1e-3)
            t_prev = ahora
            frame = datos["frame"]
            if datos["alcance"]:
                h, w = frame.shape[:2]
                x0, y0, x1, y1 = datos["alcance"]["zona"]
                cv2.rectangle(frame, (int(x0 * w), int(y0 * h)), (int(x1 * w), int(y1 * h)), (0, 255, 255), 1)
            ext = datos["extension"]
            texto = f"FPS {fps:.0f} | persona: {datos['persona']}"
            if ext["izq"] is not None or ext["der"] is not None:
                texto += f" | ext izq {ext['izq'] or 0:.2f} der {ext['der'] or 0:.2f}"
            cv2.putText(frame, texto, (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
            cv2.putText(frame, "ESC: salir  C: calibrar", (10, frame.shape[0] - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            cv2.imshow("Vision - demo", frame)
            if primera:  # traer la ventana al frente (en Mac se abre detrás de la Terminal)
                cv2.setWindowProperty("Vision - demo", cv2.WND_PROP_TOPMOST, 1)
                primera = False
            tecla = cv2.waitKey(1) & 0xFF
            if tecla == 27:
                break
            if tecla in (ord("c"), ord("C")):
                vision.calibrar()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    try:
        _demo()
    except KeyboardInterrupt:  # Ctrl+C en la Terminal: salir sin traza de error
        cv2.destroyAllWindows()
