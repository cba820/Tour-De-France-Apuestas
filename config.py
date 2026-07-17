"""Configuración de la aplicación."""
import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
INSTANCE_DIR = os.path.join(BASE_DIR, "instance")
os.makedirs(INSTANCE_DIR, exist_ok=True)


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "cambia-esta-clave-en-produccion-tdf-2026")
    SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.join(INSTANCE_DIR, "tdf.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Zona horaria de la app: usuarios en Chile.
    # En julio Chile está en UTC−4 (horario estándar de invierno).
    TIMEZONE = "America/Santiago"

    # Hora de salida por defecto de cada etapa, en hora de Chile.
    # Las etapas del Tour salen por la tarde en Europa (~13:00 CEST),
    # lo que equivale a ~07:00 en Chile (6 h de diferencia en julio).
    DEFAULT_START_HOUR = 7
    DEFAULT_START_MINUTE = 0

    # Hora (Chile) a la que el scheduler actualiza resultados cada día.
    # Las carreras empiezan ~07:00 y terminan ~12:00 (hora Chile); a las 15:00
    # ya hay resultados publicados con margen de sobra.
    DAILY_UPDATE_HOUR = 15
    DAILY_UPDATE_MINUTE = 0

    # El poller de resultados corre cada N minutos, pero solo intenta scrapear
    # una etapa cuando ya debería haber terminado: start_time + esta duración.
    # Salida ~07:00 Chile + 4.5 h ≈ 11:30, cuando ya hay resultados publicados.
    RESULTS_POLL_INTERVAL_MINUTES = 10
    STAGE_EXPECTED_DURATION_HOURS = 4.5

    # La votación se cierra este número de horas antes de la salida de la etapa
    # (con salida ~07:00 Chile, el cierre queda ~06:00 Chile).
    VOTING_CLOSE_HOURS_BEFORE = 1

    # Credenciales del admin inicial (creado en el primer arranque).
    ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
    ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@tdf.local")
    ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin1234")

    # Emails que siempre deben tener rol de administrador. Cualquier cuenta con
    # uno de estos emails se promueve a admin automáticamente (al arrancar la app
    # y al registrarse/iniciar sesión), sin tener que cambiar de cuenta a mano.
    # Configurable con la variable de entorno ADMIN_EMAILS (separados por comas).
    ADMIN_EMAILS = [
        e.strip().lower()
        for e in os.environ.get(
            "ADMIN_EMAILS", "sebastianorellana820@gmail.com"
        ).split(",")
        if e.strip()
    ]
