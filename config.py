import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


class Config:
    def __init__(self):
        # ----- Modelo de MediaPipe -----
        # 'lite' (rápido), 'full' (equilibrado) o 'heavy' (más preciso, más lento)
        self.modelo = os.environ.get('IPM_MODELO', 'full')
        self.model_path = os.path.join(BASE_DIR, 'models', f'pose_landmarker_{self.modelo}.task')

        # ----- Cámara (vision.py) -----
        # None = buscar automáticamente la primera cámara que dé imagen (no negra).
        # Se puede forzar con la variable de entorno IPM_CAMARA (0, 1, 2...) o con
        # una ruta a un vídeo para probar sin cámara.
        camara = os.environ.get('IPM_CAMARA')
        self.camara = int(camara) if camara and camara.isdigit() else camara
        self.camara_ancho = 640
        self.camara_alto = 480

        # ----- Detección (vision.py) -----
        self.visibilidad_min = 0.5   # por debajo, el punto se considera "no visible"
        self.suavizado = 0.5         # 0 = sin suavizar, 0.9 = muy suave (más retraso)
        self.calibracion_path = os.path.join(BASE_DIR, 'calibracion.json')

        # ----- Simón dice (game.py) -----
        self.duracion_partida = 90      # segundos de juego por partida
        self.tiempo_sostener = 0.6      # segundos que hay que mantener la postura
        self.metricas_dir = os.path.join(BASE_DIR, 'metricas')  # CSV de cada partida

        # ----- Juego de ejemplo (app.py) -----
        self.padding = 100
        self.game_time = 20     # Duración del juego en segundos
        self.circle_time = 1    # Duración de cada circulo azul antes de que desaparezca
        self.circle_time_radius = 15


config = Config()  # Instancia única
