# Simón dice – juego serio con visión por computador

IPM – Práctica 2. Juego serio controlado con el cuerpo mediante la cámara y
**MediaPipe Pose** (Google), orientado a la rehabilitación física, el
mantenimiento de la movilidad y la estimación de la fragilidad.

## El juego

### Objetivo

Es el clásico **«Simón dice»** jugado con el cuerpo. En pantalla aparece una orden
con un muñeco que la muestra, por ejemplo *«Simón dice: levanta el brazo izquierdo»*.
El jugador tiene que hacer esa postura y mantenerla un momento. Si la orden **no**
empieza por «Simón dice», es una trampa: hay que quedarse quieto. Se trata de
conseguir el máximo de puntos en 90 segundos.

### Utilidad para la salud

- **Movilidad y rango articular**: las posturas trabajan la elevación y apertura de
  hombros, la flexión del codo, la inclinación del tronco y, jugando de pie, la
  flexión de cadera y rodilla (marcha en el sitio, sentadilla).
- **Equilibrio**: levantar una rodilla o inclinarse obliga a mantener el equilibrio
  sobre un apoyo, una de las capacidades que más se relacionan con la fragilidad y
  el riesgo de caídas.
- **Función cognitiva**: el juego combina atención, memoria de trabajo, lateralidad
  (izquierda/derecha, cruzar la línea media del cuerpo) y **control inhibitorio**
  (no moverse cuando Simón no lo dice).
- **Seguimiento**: cada partida guarda métricas objetivas (tiempo de reacción,
  aciertos, ángulo máximo de hombros, extensión del brazo…) en un CSV. Comparando
  partidas, un fisioterapeuta puede ver la evolución del paciente sin aparatos
  especiales, solo con una webcam.
- **Accesible**: se puede jugar **sentado** (por defecto, más seguro para personas
  mayores o con poca movilidad) o **de pie** (añade posturas de piernas).

### Cómo se juega

1. Colócate delante de la cámara de forma que se te vea al menos de cabeza a
   cintura (de pie, que se vea el cuerpo entero), a 1,5 – 2 m.
2. *(Opcional)* Pulsa **C** para calibrar tu alcance.
3. Pulsa **P** para elegir entre jugar sentado o de pie, y **ENTER** para empezar.
4. Haz cada postura en cuanto aparezca la orden y mantenla hasta que se llene la
   barra verde. Si no pone «Simón dice», no te muevas hasta que pase el tiempo.

| Resultado | Puntos |
|---|---|
| Postura correcta | 10 + hasta 5 de bonus por rapidez |
| Trampa evitada (no moverse) | 5 |
| Moverse en una trampa / tiempo agotado | 0 |

**Niveles** (se sube con aciertos seguidos):

| Nivel | Tiempo por orden | Trampas | Posturas nuevas |
|---|---|---|---|
| 1 | 6 s | no | brazo izq./der. arriba, brazos arriba, brazos en cruz |
| 2 | 5 s | 25 % | manos a la cabeza, manos juntas, inclinarse a izq./der. (de pie: rodilla izq./der. arriba) |
| 3 | 4 s | 30 % | tocar el hombro contrario con cada mano (de pie: sentadilla) |

Si el jugador sale de la imagen, el tiempo se detiene hasta que vuelve. **ESC**
termina la partida; al final se muestra un resumen y se guarda en `metricas/`.

### Sin cámara

`python game.py --raton` (o automáticamente si no hay cámara): aparece un botón
por postura y hay que mantener pulsado el de la orden. Sirve para probar el juego,
y usa el mismo diccionario de datos que la visión.

### Métricas guardadas

- `metricas/partidas.csv`: una fila por partida con fecha, modo, puntos, nivel
  máximo, aciertos, fallos, trampas evitadas/falladas, precisión, tiempo de
  reacción medio y mínimo, extensión máxima de cada brazo (respecto a la
  calibración), elevación máxima de cada hombro e inclinación máxima del tronco.
- `metricas/rondas.csv`: una fila por orden (postura, si era trampa, resultado y
  tiempo de reacción), para analizar qué posturas cuestan más.

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
| `jugar.bat` / `python game.py` | Jugar (opciones: `--raton`, `--de-pie`, `--camara N`) |
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
| `poses` | `dict` | *(extra)* Posturas de «Simón dice» detectadas, `True`/`False` (ver `poses.py`) |

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

## Implementación: posturas (`poses.py`) y juego (`game.py`)

`poses.py` convierte los puntos de MediaPipe en posturas (`datos["poses"]`, un
`True`/`False` por postura). Todas las distancias se miden en **anchos de
hombros**, así que funciona igual cerca o lejos de la cámara y con personas de
cualquier talla. Por ejemplo, «brazo arriba» es la mano al menos un ancho de
hombros por encima del hombro con el codo estirado (> 130°), e «inclinarse» es la
línea de hombros inclinada más de 15°. Los umbrales están juntos en `UMBRAL` para
poder ajustarlos.

`game.py` es una máquina de estados (inicio → calibración → cuenta atrás → orden →
resultado → fin) que solo lee el diccionario del contrato. La postura tiene que
mantenerse 0,6 s (`config.tiempo_sostener`) para evitar aciertos por casualidad, y
el tiempo de reacción se mide desde que aparece la orden hasta que se detecta la
postura por primera vez.

## Estructura

```
install.bat / install.sh   instalación en un equipo limpio
jugar.bat                  lanzar el juego (Windows)
requirements.txt           dependencias fijadas
download_models.py         descarga el modelo de MediaPipe
config.py                  configuración (cámara, modelo, juego)
vision.py                  visión: MediaPipe Pose -> diccionario del contrato
poses.py                   reconocimiento de posturas + pictogramas
probar_camara.py           diagnóstico de cámara
game.py                    el juego: Simón dice
metricas/                  CSV con las métricas de cada partida (se crea al jugar)
app.py                     juego de ejemplo original de la asignatura
```
