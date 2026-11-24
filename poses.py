"""
poses.py - Reconocimiento de posturas para "Simón dice".

detectar_poses(datos) recibe el diccionario de vision.py y devuelve
{nombre_pose: True/False}. vision.py ya lo añade como datos["poses"].

Todas las distancias se miden en "anchos de hombros" (S), así que funciona
igual cerca o lejos de la cámara y con personas de cualquier tamaño.
Izquierda/derecha son siempre las del jugador (en pantalla, modo espejo, su
izquierda está a la izquierda).
"""
import math

import cv2


class Pose:
    def __init__(self, texto, corto, nivel, de_pie=False, figura=None):
        self.texto = texto        # orden que se muestra (sin tildes: OpenCV no las dibuja)
        self.corto = corto        # etiqueta corta (botones del modo ratón)
        self.nivel = nivel        # nivel a partir del cual aparece
        self.de_pie = de_pie      # necesita que se vean las piernas
        self.figura = figura or {}


POSES = {
    "brazo_izq_arriba": Pose("Levanta el brazo izquierdo", "Brazo izq. arriba", 1,
                             figura={"izq": "arriba"}),
    "brazo_der_arriba": Pose("Levanta el brazo derecho", "Brazo der. arriba", 1,
                             figura={"der": "arriba"}),
    "brazos_arriba": Pose("Levanta los dos brazos", "Brazos arriba", 1,
                          figura={"izq": "arriba", "der": "arriba"}),
    "brazos_cruz": Pose("Pon los brazos en cruz", "Brazos en cruz", 1,
                        figura={"izq": "cruz", "der": "cruz"}),
    "manos_cabeza": Pose("Manos a la cabeza", "Manos a la cabeza", 2,
                         figura={"izq": "cabeza", "der": "cabeza"}),
    "manos_juntas": Pose("Junta las manos delante", "Manos juntas", 2,
                         figura={"izq": "juntas", "der": "juntas"}),
    "inclinar_izq": Pose("Inclinate hacia tu izquierda", "Inclinar izq.", 2,
                         figura={"inclinar": -1}),
    "inclinar_der": Pose("Inclinate hacia tu derecha", "Inclinar der.", 2,
                         figura={"inclinar": 1}),
    "mano_izq_hombro_der": Pose("Toca tu hombro derecho con la mano izquierda", "Mano izq. a hombro der.", 3,
                                figura={"izq": "hombro"}),
    "mano_der_hombro_izq": Pose("Toca tu hombro izquierdo con la mano derecha", "Mano der. a hombro izq.", 3,
                                figura={"der": "hombro"}),
    "rodilla_izq_arriba": Pose("Levanta la rodilla izquierda", "Rodilla izq. arriba", 2, de_pie=True,
                               figura={"piernas": "rodilla_izq"}),
    "rodilla_der_arriba": Pose("Levanta la rodilla derecha", "Rodilla der. arriba", 2, de_pie=True,
                               figura={"piernas": "rodilla_der"}),
    "sentadilla": Pose("Haz una sentadilla", "Sentadilla", 3, de_pie=True,
                       figura={"izq": "juntas", "der": "juntas", "piernas": "sentadilla"}),
}

# Umbrales (en anchos de hombros S, o en grados). Ajustables si en pruebas reales fallan.
UMBRAL = {
    "arriba": 1.0,          # mano por encima del hombro al menos 1 S
    "codo_recto": 130,      # codo "estirado" a partir de estos grados
    "cruz_dy": 0.7,         # en cruz: mano a la altura del hombro (±0.7 S)
    "cruz_dx": 1.0,         # ... y separada del hombro hacia fuera al menos 1 S
    "cabeza": 1.0,          # manos a la cabeza: mano a menos de 1 S de la nariz
    "codo_doblado": 120,    # ... con el codo doblado
    "juntas": 0.5,          # manos a menos de 0.5 S entre sí
    "hombro": 0.7,          # mano a menos de 0.7 S del hombro contrario
    "inclinar": 15,         # grados de inclinación de la línea de hombros
    "rodilla": 0.6,         # rodilla a menos de 0.6 S por debajo de la cadera
    "sentadilla": 140,      # ángulo de rodilla por debajo de esto
    "pierna_recta": 150,    # pierna de apoyo estirada al levantar una rodilla
}


def _d(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def detectar_poses(datos):
    res = {nombre: False for nombre in POSES}
    p = datos.get("puntos") or {}
    if not datos.get("persona") or "hombro_izq" not in p or "hombro_der" not in p:
        return res

    h, w = datos["frame"].shape[:2]
    px = lambda q: None if q is None else (q[0] * w, q[1] * h)  # a píxeles (proporciones reales)
    P = {k: px(v) for k, v in p.items()}
    hi, hd = P["hombro_izq"], P["hombro_der"]
    S = _d(hi, hd)
    if S < 10:  # persona demasiado lejos o de perfil
        return res
    mi, md = px(datos.get("mano_izq")), px(datos.get("mano_der"))
    ang = datos.get("angulos") or {}
    nariz = P.get("nariz")
    U = UMBRAL

    def recto(lado, por_defecto=True):
        a = ang.get(f"codo_{lado}")
        return por_defecto if a is None else a > U["codo_recto"]

    def arriba(mano, hombro, lado):
        return mano is not None and (hombro[1] - mano[1]) > U["arriba"] * S and recto(lado)

    def cruz(mano, hombro, hacia_fuera, lado):
        return (mano is not None and abs(mano[1] - hombro[1]) < U["cruz_dy"] * S
                and hacia_fuera * (mano[0] - hombro[0]) > U["cruz_dx"] * S and recto(lado))

    def en_cabeza(mano, lado):
        if mano is None or nariz is None:
            return False
        a = ang.get(f"codo_{lado}")
        return _d(mano, nariz) < U["cabeza"] * S and (a is None or a < U["codo_doblado"])

    arr_i, arr_d = arriba(mi, hi, "izq"), arriba(md, hd, "der")
    res["brazos_arriba"] = arr_i and arr_d
    res["brazo_izq_arriba"] = arr_i and not arr_d
    res["brazo_der_arriba"] = arr_d and not arr_i
    # en pantalla (espejo) la izquierda del jugador está a la izquierda -> "fuera" es x menor
    res["brazos_cruz"] = cruz(mi, hi, -1, "izq") and cruz(md, hd, +1, "der")
    res["manos_cabeza"] = en_cabeza(mi, "izq") and en_cabeza(md, "der")
    res["manos_juntas"] = (mi is not None and md is not None and _d(mi, md) < U["juntas"] * S
                           and not res["manos_cabeza"])
    res["mano_izq_hombro_der"] = mi is not None and _d(mi, hd) < U["hombro"] * S
    res["mano_der_hombro_izq"] = md is not None and _d(md, hi) < U["hombro"] * S

    # Inclinación lateral: ángulo de la línea de hombros (no necesita ver la cadera).
    # Si el jugador se inclina a su izquierda, su hombro izquierdo baja (y mayor).
    inclinacion = math.degrees(math.atan2(hi[1] - hd[1], hd[0] - hi[0]))
    res["inclinar_izq"] = inclinacion > U["inclinar"]
    res["inclinar_der"] = inclinacion < -U["inclinar"]

    # Piernas (solo jugando de pie)
    ci, cd = P.get("cadera_izq"), P.get("cadera_der")
    ri, rd = P.get("rodilla_izq"), P.get("rodilla_der")
    sube_i = ci is not None and ri is not None and (ri[1] - ci[1]) < U["rodilla"] * S
    sube_d = cd is not None and rd is not None and (rd[1] - cd[1]) < U["rodilla"] * S
    ki, kd = ang.get("rodilla_izq"), ang.get("rodilla_der")
    recta = lambda a: a is None or a > U["pierna_recta"]
    # rodilla arriba: esa rodilla sube y la otra pierna sigue estirada (apoyo)
    res["rodilla_izq_arriba"] = sube_i and not sube_d and recta(kd)
    res["rodilla_der_arriba"] = sube_d and not sube_i and recta(ki)
    # sentadilla: las dos rodillas dobladas
    res["sentadilla"] = (ki is not None and kd is not None
                         and ki < U["sentadilla"] and kd < U["sentadilla"])
    return res


# --------------------------------------------------------------------------- #
#  Pictograma: muñeco que muestra la postura pedida                            #
# --------------------------------------------------------------------------- #
_BRAZOS = {  # (codo, mano) del brazo IZQUIERDO del jugador (lado izquierdo de la pantalla)
    "abajo": ((0.34, 0.45), (0.32, 0.60)),
    "arriba": ((0.35, 0.16), (0.34, 0.03)),
    "cruz": ((0.23, 0.30), (0.08, 0.30)),
    "cabeza": ((0.25, 0.18), (0.42, 0.08)),
    "juntas": ((0.36, 0.45), (0.48, 0.40)),
    "hombro": ((0.42, 0.44), (0.60, 0.32)),
}


def dibujar_pictograma(img, nombre, x, y, tam, color=(255, 255, 255), grosor=4):
    """Dibuja el muñeco de la postura `nombre` en el cuadro (x, y, tam, tam*1.2)."""
    fig = POSES[nombre].figura if nombre in POSES else {}
    alto = tam * 1.2
    piernas = fig.get("piernas")
    bajada = 0.08 if piernas == "sentadilla" else 0.0
    # el tronco gira alrededor de la cadera al inclinarse
    phi = math.radians(18) * fig.get("inclinar", 0)
    cx, cy = x + 0.5 * tam, y + (0.60 + bajada) * alto

    def q(pt, lado=None, superior=True):
        px_, py_ = pt
        if lado == "der":
            px_ = 1.0 - px_
        X, Y = x + px_ * tam, y + (py_ + bajada) * alto
        if superior and phi:
            dx, dy = X - cx, Y - cy
            X = cx + dx * math.cos(phi) - dy * math.sin(phi)
            Y = cy + dx * math.sin(phi) + dy * math.cos(phi)
        return int(X), int(Y)

    def linea(a, b):
        cv2.line(img, a, b, color, grosor, cv2.LINE_AA)

    # cabeza, tronco y hombros
    cv2.circle(img, q((0.5, 0.14)), int(tam * 0.08), color, grosor, cv2.LINE_AA)
    linea(q((0.5, 0.28)), (int(cx), int(cy)))
    linea(q((0.36, 0.29)), q((0.36, 0.29), "der"))
    # brazos
    for lado in ("izq", "der"):
        codo, mano = _BRAZOS[fig.get(lado, "abajo")]
        linea(q((0.36, 0.29), lado), q(codo, lado))
        linea(q(codo, lado), q(mano, lado))
        cv2.circle(img, q(mano, lado), max(3, grosor + 1), color, -1, cv2.LINE_AA)
    # piernas
    for lado in ("izq", "der"):
        if piernas == "sentadilla":
            rod, pie = (0.30, 0.76), (0.40, 0.90)
        elif piernas == f"rodilla_{lado}":
            rod, pie = (0.32, 0.66), (0.40, 0.80)
        else:
            rod, pie = (0.42, 0.78), (0.42, 0.97 - bajada)
        cadera = q((0.43, 0.60), lado, superior=False)
        linea(cadera, q(rod, lado, superior=False))
        linea(q(rod, lado, superior=False), q(pie, lado, superior=False))
    linea(q((0.43, 0.60), superior=False), q((0.43, 0.60), "der", superior=False))
