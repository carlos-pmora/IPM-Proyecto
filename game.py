"""
game.py - SIMÓN DICE: juego serio de movilidad y atención controlado con el cuerpo.

El juego muestra una orden ("Simon dice: levanta el brazo izquierdo"). El jugador
tiene que hacer esa postura y mantenerla un momento. Si la orden NO empieza por
"Simon dice", es una trampa y hay que quedarse quieto.

    python game.py            -> con cámara (si no hay cámara, pasa al ratón)
    python game.py --raton    -> con el ratón: se pulsa el botón de la postura
    python game.py --camara 1 -> elegir la cámara

Teclas: ENTER empezar · C calibrar · P jugar de pie / sentado · ESC salir.

Solo lee el diccionario del contrato (persona, mano_izq, mano_der, angulos,
frame) más los extras de vision.py (poses, extension).
Las métricas de cada partida se guardan en metricas/partidas.csv y metricas/rondas.csv.
"""
import argparse
import csv
import math
import os
import random
import time

import cv2
import numpy as np

from config import config
from poses import POSES, dibujar_pictograma

ANCHO, ALTO = 960, 720
VENTANA = "Simon dice"
FUENTE = cv2.FONT_HERSHEY_SIMPLEX

# Niveles: tiempo para responder, probabilidad de orden trampa y aciertos seguidos para subir
NIVELES = {
    1: {"tiempo": 6.0, "trampas": 0.0, "subir": 4},
    2: {"tiempo": 5.0, "trampas": 0.25, "subir": 5},
    3: {"tiempo": 4.0, "trampas": 0.3, "subir": None},
}

BLANCO, NEGRO = (255, 255, 255), (0, 0, 0)
VERDE, ROJO, AMARILLO, AZUL, GRIS = (80, 220, 80), (60, 60, 230), (0, 220, 255), (230, 160, 40), (90, 90, 90)


# --------------------------------------------------------------------------- #
#  Entrada con el ratón (mismo diccionario que vision.py)                      #
# --------------------------------------------------------------------------- #
class FuenteRaton:
    """Rellena el diccionario del contrato con el ratón, para jugar sin cámara.
    La mano derecha es el puntero; las posturas se eligen pulsando su botón."""

    modo = "raton"

    def __init__(self):
        self.pos = None          # en píxeles de la ventana
        self.pulsado = False

    def evento(self, ev, x, y, flags, _param):
        self.pos = (x, y)
        if ev == cv2.EVENT_LBUTTONDOWN:
            self.pulsado = True
        elif ev == cv2.EVENT_LBUTTONUP:
            self.pulsado = False

    def leer(self):
        time.sleep(1 / 60)
        mano = None if self.pos is None else (self.pos[0] / ANCHO, self.pos[1] / ALTO)
        return {
            "persona": True, "mano_izq": None, "mano_der": mano, "angulos": {},
            "frame": np.full((480, 640, 3), (45, 40, 35), np.uint8),
            "puntos": {}, "extension": {"izq": None, "der": None}, "alcance": None,
            "poses": {n: False for n in POSES}, "tiempo": time.time(),
        }

    def cerrar(self):
        pass


# --------------------------------------------------------------------------- #
#  Utilidades de dibujo                                                        #
# --------------------------------------------------------------------------- #
def texto(img, t, x, y, escala=1.0, color=BLANCO, grosor=2, centrado=False, ancho_max=None):
    """Texto con sombra. Si no cabe en ancho_max, se reduce la escala."""
    if ancho_max:
        while escala > 0.4 and cv2.getTextSize(t, FUENTE, escala, grosor)[0][0] > ancho_max:
            escala -= 0.05
    (w, _h), _ = cv2.getTextSize(t, FUENTE, escala, grosor)
    if centrado:
        x = int(x - w / 2)
    cv2.putText(img, t, (x + 2, y + 2), FUENTE, escala, NEGRO, grosor + 2, cv2.LINE_AA)
    cv2.putText(img, t, (x, y), FUENTE, escala, color, grosor, cv2.LINE_AA)


def panel(img, x0, y0, x1, y1, color=NEGRO, alfa=0.6):
    """Rectángulo semitransparente."""
    x0, y0, x1, y1 = max(0, x0), max(0, y0), min(img.shape[1], x1), min(img.shape[0], y1)
    zona = img[y0:y1, x0:x1]
    capa = np.full_like(zona, color)
    img[y0:y1, x0:x1] = cv2.addWeighted(capa, alfa, zona, 1 - alfa, 0)


def barra(img, x0, y0, ancho, alto, fraccion, color):
    cv2.rectangle(img, (x0, y0), (x0 + ancho, y0 + alto), GRIS, -1)
    cv2.rectangle(img, (x0, y0), (x0 + int(ancho * max(0.0, min(1.0, fraccion))), y0 + alto), color, -1)


def encajar(frame):
    """Escala la imagen de la cámara a la ventana manteniendo la proporción."""
    h, w = frame.shape[:2]
    escala = min(ANCHO / w, ALTO / h)
    nueva = cv2.resize(frame, (int(w * escala), int(h * escala)))
    lienzo = np.zeros((ALTO, ANCHO, 3), np.uint8)
    y0, x0 = (ALTO - nueva.shape[0]) // 2, (ANCHO - nueva.shape[1]) // 2
    lienzo[y0:y0 + nueva.shape[0], x0:x0 + nueva.shape[1]] = nueva
    return lienzo


# --------------------------------------------------------------------------- #
#  Métricas                                                                    #
# --------------------------------------------------------------------------- #
CAMPOS_PARTIDA = ["partida", "fecha", "modo", "postura", "duracion_s", "puntos", "nivel_max",
                  "rondas", "aciertos", "fallos", "tiempo_agotado", "trampas_superadas",
                  "trampas_falladas", "precision_pct", "reaccion_media_s", "reaccion_min_s",
                  "extension_max_izq", "extension_max_der", "hombro_max_izq", "hombro_max_der",
                  "inclinacion_max"]
CAMPOS_RONDA = ["partida", "ronda", "nivel", "pose", "simon_dice", "resultado", "reaccion_s"]


def _anadir_csv(ruta, campos, filas):
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    nuevo = not os.path.exists(ruta)
    with open(ruta, "a", newline="", encoding="utf-8") as f:
        escritor = csv.DictWriter(f, fieldnames=campos)
        if nuevo:
            escritor.writeheader()
        escritor.writerows(filas)


def record_anterior():
    ruta = os.path.join(config.metricas_dir, "partidas.csv")
    try:
        with open(ruta, encoding="utf-8") as f:
            return max((int(fila["puntos"]) for fila in csv.DictReader(f)), default=0)
    except (OSError, ValueError, KeyError):
        return 0


# --------------------------------------------------------------------------- #
#  Juego                                                                       #
# --------------------------------------------------------------------------- #
class Juego:
    """Máquina de estados: inicio -> (calibrando) -> cuenta -> jugando <-> resultado -> fin."""

    def __init__(self, fuente, de_pie=False):
        self.fuente = fuente
        self.modo = getattr(fuente, "modo", "camara")
        self.de_pie = de_pie
        self.estado = "inicio"
        self.salir = False
        self.calibracion = None
        self.t_prev = None
        self.botones = {}
        self.record = record_anterior()

    # ----------------------------------------------------------------- partida
    def empezar(self, ahora):
        self.partida = time.strftime("%Y%m%d-%H%M%S")
        self.t_inicio = ahora
        self.restante = float(config.duracion_partida)
        self.puntos = 0
        self.nivel = 1
        self.nivel_max = 1
        self.racha = 0
        self.rondas = []
        self.pose = None
        self.max = {"extension_izq": 0.0, "extension_der": 0.0, "hombro_izq": 0.0,
                    "hombro_der": 0.0, "tronco": 0.0}
        self.estado = "cuenta"
        self.t_estado = 3.0

    def disponibles(self):
        return [n for n, p in POSES.items() if p.nivel <= self.nivel and (self.de_pie or not p.de_pie)]

    def nueva_ronda(self):
        opciones = [n for n in self.disponibles() if n != self.pose]
        self.pose = random.choice(opciones)
        # nunca dos trampas seguidas, y la primera ronda de cada nivel siempre es "Simón dice"
        trampa_previa = bool(self.rondas) and not self.rondas[-1]["simon_dice"]
        self.simon = (trampa_previa or random.random() >= NIVELES[self.nivel]["trampas"])
        self.t_ronda = 0.0
        self.t_sostenido = 0.0
        self.reaccion = None
        self.estado = "jugando"

    def resolver(self, resultado):
        lim = NIVELES[self.nivel]["tiempo"]
        ganados = 0
        if resultado == "acierto":
            ganados = 10 + int(5 * max(0.0, 1 - (self.reaccion or lim) / lim))  # bonus por rapidez
        elif resultado == "trampa_superada":
            ganados = 5
        self.puntos += ganados
        bueno = resultado in ("acierto", "trampa_superada")
        self.racha = self.racha + 1 if bueno else 0
        self.rondas.append({"partida": self.partida, "ronda": len(self.rondas) + 1, "nivel": self.nivel,
                            "pose": self.pose, "simon_dice": self.simon, "resultado": resultado,
                            "reaccion_s": "" if self.reaccion is None else round(self.reaccion, 3)})
        mensajes = {
            "acierto": (f"Muy bien!  +{ganados}", VERDE),
            "trampa_superada": ("Bien! Simon no lo dijo  +5", VERDE),
            "trampa_fallada": ("Simon no lo dijo!", ROJO),
            "tiempo_agotado": ("Se acabo el tiempo", AMARILLO),
        }
        self.mensaje, self.color_mensaje = mensajes[resultado]
        subir = NIVELES[self.nivel]["subir"]
        if subir and self.racha >= subir:
            self.nivel += 1
            self.nivel_max = max(self.nivel_max, self.nivel)
            self.racha = 0
            self.mensaje += f"   NIVEL {self.nivel}!"
        self.estado = "resultado"
        self.t_estado = 1.6

    def terminar(self, ahora):
        r = self.rondas
        cuenta = lambda res: sum(1 for x in r if x["resultado"] == res)
        reacciones = [x["reaccion_s"] for x in r if x["resultado"] == "acierto" and x["reaccion_s"] != ""]
        buenas = cuenta("acierto") + cuenta("trampa_superada")
        self.resumen = {
            "partida": self.partida, "fecha": time.strftime("%Y-%m-%d %H:%M:%S"), "modo": self.modo,
            "postura": "de pie" if self.de_pie else "sentado",
            "duracion_s": round(ahora - self.t_inicio, 1), "puntos": self.puntos, "nivel_max": self.nivel_max,
            "rondas": len(r), "aciertos": cuenta("acierto"),
            "fallos": cuenta("trampa_fallada") + cuenta("tiempo_agotado"),
            "tiempo_agotado": cuenta("tiempo_agotado"),
            "trampas_superadas": cuenta("trampa_superada"), "trampas_falladas": cuenta("trampa_fallada"),
            "precision_pct": round(100 * buenas / len(r), 1) if r else 0,
            "reaccion_media_s": round(sum(reacciones) / len(reacciones), 3) if reacciones else "",
            "reaccion_min_s": round(min(reacciones), 3) if reacciones else "",
            "extension_max_izq": round(self.max["extension_izq"], 2) or "",
            "extension_max_der": round(self.max["extension_der"], 2) or "",
            "hombro_max_izq": round(self.max["hombro_izq"], 1) or "",
            "hombro_max_der": round(self.max["hombro_der"], 1) or "",
            "inclinacion_max": round(self.max["tronco"], 1) or "",
        }
        _anadir_csv(os.path.join(config.metricas_dir, "partidas.csv"), CAMPOS_PARTIDA, [self.resumen])
        if r:
            _anadir_csv(os.path.join(config.metricas_dir, "rondas.csv"), CAMPOS_RONDA, r)
        self.nuevo_record = self.puntos > self.record
        self.record = max(self.record, self.puntos)
        self.estado = "fin"

    def medir(self, datos):
        """Máximos de movilidad durante la partida (para el CSV)."""
        ext, ang = datos.get("extension") or {}, datos.get("angulos") or {}
        for clave, valor in (("extension_izq", ext.get("izq")), ("extension_der", ext.get("der")),
                             ("hombro_izq", ang.get("hombro_izq")), ("hombro_der", ang.get("hombro_der")),
                             ("tronco", ang.get("tronco"))):
            if valor is not None:
                self.max[clave] = max(self.max[clave], valor)

    # ------------------------------------------------------------- cada frame
    def paso(self, datos, tecla, ahora):
        dt = 0.0 if self.t_prev is None else min(ahora - self.t_prev, 0.2)
        self.t_prev = ahora
        if self.modo == "raton":
            self._poses_raton(datos)

        if tecla == 27:  # ESC
            if self.estado in ("cuenta", "jugando", "resultado"):
                self.terminar(ahora)
            elif self.estado == "calibrando":
                self.estado = "inicio"
            else:
                self.salir = True

        estado = self.estado
        if estado == "inicio":
            if tecla in (13, 10, 32):
                self.empezar(ahora)
            elif tecla in (ord("p"), ord("P")):
                self.de_pie = not self.de_pie
            elif tecla in (ord("c"), ord("C")) and self.modo == "camara":
                from vision import Calibracion
                self.calibracion = Calibracion()
                self.estado = "calibrando"
        elif estado == "calibrando":
            self.calibracion.actualizar(datos)
            if self.calibracion.terminada:
                from vision import guardar_calibracion
                guardar_calibracion(self.calibracion.resultado)
                self.fuente.alcance = self.calibracion.resultado
                self.estado = "inicio"
        elif estado == "cuenta":
            self.t_estado -= dt
            if self.t_estado <= 0:
                self.nueva_ronda()
        elif estado == "jugando":
            if datos["persona"]:  # si no se ve al jugador, el tiempo se para
                self.medir(datos)
                self.restante -= dt
                self.t_ronda += dt
                if datos["poses"].get(self.pose):
                    if self.reaccion is None:
                        self.reaccion = self.t_ronda
                    self.t_sostenido += dt
                else:
                    self.t_sostenido = 0.0
                if self.t_sostenido >= config.tiempo_sostener:
                    self.resolver("acierto" if self.simon else "trampa_fallada")
                elif self.t_ronda >= NIVELES[self.nivel]["tiempo"]:
                    self.resolver("tiempo_agotado" if self.simon else "trampa_superada")
                elif self.restante <= 0:
                    self.terminar(ahora)
        elif estado == "resultado":
            self.t_estado -= dt
            if self.t_estado <= 0:
                if self.restante <= 0:
                    self.terminar(ahora)
                else:
                    self.nueva_ronda()
        elif estado == "fin":
            if tecla in (13, 10, 32):
                self.empezar(ahora)

        return self.dibujar(datos)

    def _poses_raton(self, datos):
        pos, pulsado = self.fuente.pos, self.fuente.pulsado
        for nombre, (x0, y0, x1, y1) in self.botones.items():
            datos["poses"][nombre] = bool(pulsado and pos and x0 <= pos[0] <= x1 and y0 <= pos[1] <= y1)

    # ------------------------------------------------------------- pantallas
    def dibujar(self, datos):
        frame = datos["frame"].copy()
        if self.modo == "camara" and self.estado != "fin":
            from vision import dibujar_esqueleto
            dibujar_esqueleto(frame, datos, angulos=False)
        if self.estado == "calibrando":
            self.calibracion.dibujar(frame)
        img = encajar(frame)
        getattr(self, f"_pantalla_{self.estado}")(img, datos)
        return img

    def _pantalla_inicio(self, img, datos):
        panel(img, 0, 0, ANCHO, ALTO, alfa=0.55)
        texto(img, "SIMON DICE", ANCHO // 2, 130, 2.6, AMARILLO, 5, centrado=True)
        texto(img, "Haz la postura solo si la orden empieza por \"Simon dice\"",
              ANCHO // 2, 190, 0.8, BLANCO, 2, centrado=True, ancho_max=ANCHO - 60)
        for i, n in enumerate(["brazos_arriba", "brazos_cruz", "manos_cabeza", "inclinar_izq"]):
            dibujar_pictograma(img, n, 200 + i * 150, 230, 100, BLANCO, 3)
        lineas = [
            ("ENTER", "empezar a jugar"),
            ("P", f"jugar {'sentado' if self.de_pie else 'de pie'} (ahora: {'DE PIE' if self.de_pie else 'SENTADO'})"),
            ("ESC", "salir"),
        ]
        if self.modo == "camara":
            lineas.insert(1, ("C", "calibrar mi alcance"))
        for i, (tecla, desc) in enumerate(lineas):
            y = 430 + i * 45
            texto(img, tecla, 250, y, 0.9, AMARILLO, 2)
            texto(img, desc, 370, y, 0.9, BLANCO, 2)
        if self.modo == "raton":
            estado = "Modo raton: pulsa el boton de la postura que se pide"
        elif not datos["persona"]:
            estado = "No te veo: colocate delante de la camara"
        else:
            estado = "Te veo!" + ("  (calibrado)" if datos.get("alcance") else "  (sin calibrar)")
        texto(img, estado, ANCHO // 2, 650, 0.8, VERDE if datos["persona"] else ROJO, 2, centrado=True)
        if self.record:
            texto(img, f"Record: {self.record}", ANCHO - 200, 40, 0.8, AMARILLO, 2)

    def _pantalla_calibrando(self, img, datos):
        texto(img, "ESC: cancelar", ANCHO - 200, ALTO - 20, 0.6, BLANCO, 1)

    def _barra_superior(self, img):
        panel(img, 0, 0, ANCHO, 55, alfa=0.6)
        texto(img, f"Puntos: {self.puntos}", 20, 38, 1.0, BLANCO, 2)
        texto(img, f"Nivel {self.nivel}", ANCHO // 2, 38, 1.0, AMARILLO, 2, centrado=True)
        texto(img, f"{max(0, int(self.restante))} s", ANCHO - 110, 38, 1.0, BLANCO, 2)

    def _pantalla_cuenta(self, img, datos):
        self._barra_superior(img)
        panel(img, 0, 0, ANCHO, ALTO, alfa=0.3)
        texto(img, "Preparado...", ANCHO // 2, 280, 1.4, BLANCO, 3, centrado=True)
        texto(img, str(max(1, math.ceil(self.t_estado))), ANCHO // 2, 430, 4.0, AMARILLO, 8, centrado=True)

    def _orden(self, img, datos, color_borde=None):
        """Panel de la orden: pictograma + texto + barra de tiempo."""
        pose = POSES[self.pose]
        # pictograma arriba a la derecha
        x0, y0, tam = ANCHO - 200, 70, 170
        panel(img, x0 - 10, y0 - 5, ANCHO - 10, y0 + int(tam * 1.2) + 10, alfa=0.6)
        if color_borde:
            cv2.rectangle(img, (x0 - 10, y0 - 5), (ANCHO - 10, y0 + int(tam * 1.2) + 10), color_borde, 4)
        dibujar_pictograma(img, self.pose, x0, y0, tam, BLANCO, 4)
        # orden abajo
        panel(img, 0, ALTO - 150, ANCHO, ALTO, alfa=0.65)
        if self.simon:
            texto(img, "SIMON DICE:", ANCHO // 2, ALTO - 105, 1.1, AMARILLO, 3, centrado=True)
        texto(img, pose.texto, ANCHO // 2, ALTO - 50, 1.3, BLANCO, 3, centrado=True, ancho_max=ANCHO - 40)

    def _pantalla_jugando(self, img, datos):
        self._barra_superior(img)
        activa = datos["poses"].get(self.pose)
        self._orden(img, datos, VERDE if activa else None)
        lim = NIVELES[self.nivel]["tiempo"]
        barra(img, 20, ALTO - 20, ANCHO - 40, 10, 1 - self.t_ronda / lim, AZUL)
        if activa:
            barra(img, ANCHO - 210, 70 + 215, 200, 12, self.t_sostenido / config.tiempo_sostener, VERDE)
        if not datos["persona"]:
            panel(img, 0, 280, ANCHO, 360, ROJO, 0.6)
            texto(img, "No te veo: colocate delante de la camara", ANCHO // 2, 330, 1.0, BLANCO, 2, centrado=True)
        if self.modo == "raton":
            self._dibujar_botones(img)

    def _pantalla_resultado(self, img, datos):
        self._barra_superior(img)
        self._orden(img, datos)
        panel(img, 0, 250, ANCHO, 350, self.color_mensaje, 0.75)
        texto(img, self.mensaje, ANCHO // 2, 315, 1.3, BLANCO, 3, centrado=True, ancho_max=ANCHO - 40)

    def _pantalla_fin(self, img, datos):
        panel(img, 0, 0, ANCHO, ALTO, alfa=0.8)
        r = self.resumen
        texto(img, "FIN DE LA PARTIDA", ANCHO // 2, 90, 1.8, AMARILLO, 4, centrado=True)
        texto(img, f"{r['puntos']} puntos", ANCHO // 2, 170, 1.6, BLANCO, 3, centrado=True)
        if self.nuevo_record and r["puntos"] > 0:
            texto(img, "NUEVO RECORD!", ANCHO // 2, 215, 1.0, VERDE, 2, centrado=True)
        filas = [
            ("Nivel alcanzado", r["nivel_max"]),
            ("Aciertos", f"{r['aciertos'] + r['trampas_superadas']} de {r['rondas']} ({r['precision_pct']}%)"),
            ("Trampas evitadas", f"{r['trampas_superadas']} de {r['trampas_superadas'] + r['trampas_falladas']}"),
            ("Tiempo de reaccion medio", f"{r['reaccion_media_s']} s" if r["reaccion_media_s"] != "" else "-"),
        ]
        if self.modo == "camara":
            filas.append(("Elevacion max. hombros",
                          f"izq {r['hombro_max_izq'] or '-'}  der {r['hombro_max_der'] or '-'} grados"))
        for i, (k, v) in enumerate(filas):
            y = 290 + i * 50
            texto(img, k, 110, y, 0.85, BLANCO, 2)
            texto(img, str(v), 520, y, 0.85, AMARILLO, 2, ancho_max=ANCHO - 540)
        texto(img, "Guardado en metricas/partidas.csv", ANCHO // 2, 580, 0.6, (170, 170, 170), 1, centrado=True)
        texto(img, "ENTER: jugar otra vez     ESC: salir", ANCHO // 2, 650, 0.9, BLANCO, 2, centrado=True)

    def _dibujar_botones(self, img):
        """Modo ratón: un botón por postura disponible."""
        nombres = self.disponibles()
        cols, ancho_b, alto_b, sep = 4, 220, 48, 10
        x_ini = (ANCHO - (cols * ancho_b + (cols - 1) * sep)) // 2
        filas = (len(nombres) + cols - 1) // cols
        y_ini = ALTO - 160 - filas * (alto_b + sep)
        self.botones = {}
        for i, n in enumerate(nombres):
            x0 = x_ini + (i % cols) * (ancho_b + sep)
            y0 = y_ini + (i // cols) * (alto_b + sep)
            self.botones[n] = (x0, y0, x0 + ancho_b, y0 + alto_b)
            pulsado = self.fuente.pulsado and self.fuente.pos and \
                x0 <= self.fuente.pos[0] <= x0 + ancho_b and y0 <= self.fuente.pos[1] <= y0 + alto_b
            cv2.rectangle(img, (x0, y0), (x0 + ancho_b, y0 + alto_b), VERDE if pulsado else (70, 70, 70), -1)
            cv2.rectangle(img, (x0, y0), (x0 + ancho_b, y0 + alto_b), BLANCO, 1)
            texto(img, POSES[n].corto, x0 + ancho_b // 2, y0 + 31, 0.55, BLANCO, 1, centrado=True,
                  ancho_max=ancho_b - 10)
        texto(img, "Manten pulsado el boton de la postura", ANCHO // 2, y_ini - 15, 0.6, BLANCO, 1, centrado=True)


# --------------------------------------------------------------------------- #
#  Programa principal                                                          #
# --------------------------------------------------------------------------- #
def main():
    parser = argparse.ArgumentParser(description="Simon dice - juego serio con visión por computador")
    parser.add_argument("--raton", action="store_true", help="jugar con el ratón (sin cámara)")
    parser.add_argument("--camara", type=int, help="índice de la cámara")
    parser.add_argument("--video", help="usar un vídeo en vez de la cámara (pruebas)")
    parser.add_argument("--de-pie", action="store_true", help="incluir posturas de piernas")
    args = parser.parse_args()

    fuente = None
    if not args.raton:
        try:
            from vision import Vision
            fuente = Vision(fuente=args.video if args.video else args.camara)
        except Exception as e:  # sin cámara o sin modelo: se juega con el ratón
            print(f"[game] No se puede usar la cámara ({e}).\n[game] Se juega con el ratón.")
    if fuente is None:
        fuente = FuenteRaton()

    juego = Juego(fuente, de_pie=args.de_pie)
    cv2.namedWindow(VENTANA)
    if isinstance(fuente, FuenteRaton):
        cv2.setMouseCallback(VENTANA, fuente.evento)

    tecla, primera = -1, True
    try:
        while not juego.salir:
            datos = fuente.leer()
            if datos is None:
                print("[game] Se ha perdido la imagen de la cámara.")
                break
            img = juego.paso(datos, tecla, time.time())
            cv2.imshow(VENTANA, img)
            if primera:  # traer la ventana al frente (en Mac se abre detrás)
                cv2.setWindowProperty(VENTANA, cv2.WND_PROP_TOPMOST, 1)
                primera = False
            tecla = cv2.waitKey(1) & 0xFF
            if tecla == 255:
                tecla = -1
            if cv2.getWindowProperty(VENTANA, cv2.WND_PROP_VISIBLE) < 1:  # cerrada con la X
                break
    except KeyboardInterrupt:
        pass
    finally:
        if juego.estado in ("jugando", "resultado", "cuenta"):
            juego.terminar(time.time())
        fuente.cerrar()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
