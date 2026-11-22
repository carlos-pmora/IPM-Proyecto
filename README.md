# IPM – Práctica 2: juego serio con visión por computador

Juego serio controlado con el cuerpo mediante la cámara y **MediaPipe Pose**
(Google), orientado a la rehabilitación física y la estimación de la fragilidad.

## El juego

> _Sección del juego: objetivo, utilidad para la salud y cómo se juega (pendiente, Carlos)._

---

## Instalación

Requisitos: **Windows 10/11** (también funciona en Linux y macOS), una **webcam**
y conexión a Internet durante la instalación. Hace falta **Python 3.12**
(MediaPipe 0.10.21 solo admite Python 3.9 – 3.12). Si no lo tienes:

```bash
winget install -e --id Python.Python.3.12
```

o descárgalo de [python.org](https://www.python.org/downloads/release/python-31210/).
Si tienes **conda**, no hace falta: el instalador crea un Python 3.12 propio dentro
de la carpeta del proyecto.

### Windows

1. Descomprime el `.zip` en una carpeta.
2. Haz doble clic en **`install.bat`**. Él solo:
   - busca Python 3.12 (`py -3.12`, `python` o conda),
   - crea un entorno virtual aislado en `.venv`,
   - instala las dependencias de `requirements.txt`,
   - descarga el modelo de MediaPipe en `models/`,
   - comprueba que todo se importa bien.
3. Haz doble clic en **`jugar.bat`** para empezar.

### Linux / macOS

```bash
./install.sh
```

```bash
.venv/bin/python game.py
```

### Instalación manual (equivalente)

```bash
py -3.12 -m venv .venv
```

```bash
.venv\Scripts\python -m pip install -r requirements.txt
```

```bash
.venv\Scripts\python download_models.py
```

```bash
.venv\Scripts\python game.py
```

La instalación se ha probado en un entorno limpio (sin ningún entorno previo de
Python): tarda menos de un minuto y ocupa unos 900 MB.

## Ejecución y herramientas

| Comando | Para qué |
|---|---|
| `jugar.bat` / `python game.py` | Jugar |
| `python vision.py` | Demo de visión: esqueleto, manos y ángulos en vivo (`C` calibra, `ESC` sale) |
| `python vision.py --calibrar` | Hacer la calibración y guardarla en `calibracion.json` |
| `python probar_camara.py` | Diagnóstico de cámara: qué índice/backend da imagen |
| `python download_models.py --todos` | Descargar también los modelos `lite` y `heavy` |

Con `.venv\Scripts\python` delante si no se ha activado el entorno.

### Configuración

En `config.py` o con variables de entorno:

- `IPM_CAMARA=1` → usar la cámara 1 (por defecto se busca sola). También acepta
  la ruta de un vídeo para probar sin cámara.
- `IPM_MODELO=lite|full|heavy` → modelo de MediaPipe (por defecto `full`; `lite`
  va mejor en portátiles lentos, hay que descargarlo con `--todos`).

### Si la cámara se ve negra

Es un problema conocido de OpenCV en algunos portátiles con Windows. `vision.py`
ya lo evita: prueba los backends DirectShow y Media Foundation y los índices 0–4, y
descarta las cámaras que solo dan imagen negra (por ejemplo, la cámara de
infrarrojos de Windows Hello). Si aun así no funciona:

1. Ejecuta `python probar_camara.py` y mira qué combinación da imagen.
2. Cierra Teams, Zoom, el navegador u OBS: Windows solo deja a una aplicación usar la cámara.
3. Comprueba la tapa o tecla de privacidad y *Configuración → Privacidad → Cámara →
   Permitir que las aplicaciones de escritorio accedan a la cámara*.
4. Alternativa: usar el móvil como webcam con **Iriun** o **DroidCam**.

---

## Implementación: módulo de visión (`vision.py`)

`vision.py` y el juego se comunican solo a través de un diccionario (el *contrato
entre módulos*). En cada fotograma `Vision.leer()` devuelve:

| Campo | Tipo | Significado |
|---|---|---|
| `persona` | `bool` | Hay alguien detectado |
| `mano_izq`, `mano_der` | `(x, y)` o `None` | Centro de la mano, normalizado 0–1 (`None` si no se ve) |
| `angulos` | `dict` | Ángulos en grados: `codo_*`, `hombro_*`, `cadera_*`, `rodilla_*` y `tronco` |
| `frame` | imagen BGR | Imagen de la cámara ya volteada (modo espejo), para dibujar encima |
| `puntos` | `dict` | *(extra)* Puntos clave visibles: hombros, codos, muñecas, caderas, rodillas… |
| `extension` | `dict` | *(extra)* Extensión del brazo respecto al alcance calibrado (1.0 = máximo) |
| `alcance` | `dict` o `None` | *(extra)* Resultado de la calibración |

```python
from vision import Vision

with Vision() as vision:
    while True:
        datos = vision.leer()
        if datos is None:
            break
        if datos["mano_der"]:
            x, y = datos["mano_der"]
```

Detalles:

- **Izquierda y derecha** son siempre las del jugador. La detección se hace sobre la
  imagen original y después se reflejan las coordenadas, así que en pantalla (modo
  espejo) la mano izquierda aparece a la izquierda.
- **Centro de la mano**: media de muñeca, índice y meñique, más estable que un solo punto.
- **Suavizado**: media móvil exponencial para quitar el temblor (`config.suavizado`).
- **Visibilidad**: un punto con visibilidad < 0.5 se considera no visible y su valor es `None`.
- **Ángulos**: se calculan en 2D sobre la imagen corrigiendo la relación de aspecto.
  El de hombro es el ángulo entre tronco y brazo (0° pegado, 90° en cruz, 180° arriba).
  `tronco` es la inclinación respecto a la vertical (0° = recto).

### Calibración

Al empezar, el jugador se coloca y se mide su alcance en tres fases:
1. **Colocarse** a unos 2 m hasta que se le vea de cabeza a cadera (2 s quieto).
2. **Brazos en cruz** (4 s): alcance lateral.
3. **Brazos arriba** (4 s): alcance vertical.

El resultado se guarda en `calibracion.json` y contiene la `zona` de la pantalla
a la que llegan las manos (para colocar los objetivos donde el jugador puede
alcanzarlos) y la longitud de cada brazo en anchos de hombros (no depende de la
distancia a la cámara). Se puede lanzar con su propia ventana (`vision.calibrar()`)
o integrarla en el juego con la clase `Calibracion`, que no depende de ninguna
librería gráfica.

## Estructura

```
install.bat / install.sh   instalación en un equipo limpio
jugar.bat                  lanzar el juego (Windows)
requirements.txt           dependencias fijadas
download_models.py         descarga el modelo de MediaPipe
config.py                  configuración (cámara, modelo, juego)
vision.py                  visión: MediaPipe Pose -> diccionario del contrato
probar_camara.py           diagnóstico de cámara
game.py                    el juego
app.py                     juego de ejemplo original de la asignatura
```
