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

    # --- Recordatorios de votación por email ---
    # Envío por SMTP (Gmail por defecto) autenticado con una App Password.
    # La función queda deshabilitada si MAIL_USERNAME o MAIL_PASSWORD están vacíos.
    MAIL_SERVER = os.environ.get("MAIL_SERVER", "smtp.gmail.com")
    MAIL_PORT = int(os.environ.get("MAIL_PORT", 587))
    MAIL_USE_TLS = os.environ.get("MAIL_USE_TLS", "1") in ("1", "true", "yes")
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME")   # p.ej. sebastianorellana820@gmail.com
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD")   # App Password de Google (16 caracteres)
    MAIL_FROM = os.environ.get("MAIL_FROM")           # remitente; por defecto = MAIL_USERNAME

    # Hora (Chile) a la que se envía el recordatorio diario de votación. A las 20:00
    # del día anterior, la votación de la etapa de mañana está abierta (abre 00:00 del
    # día anterior, cierra ~06:00 del día de la etapa).
    REMINDER_HOUR = int(os.environ.get("REMINDER_HOUR", 20))
    REMINDER_MINUTE = int(os.environ.get("REMINDER_MINUTE", 0))

    # URL pública del sitio, usada para el enlace dentro del correo.
    SITE_URL = os.environ.get("SITE_URL", "http://localhost")

    # Interruptor global de los recordatorios de votación por email. Desactivado
    # a petición del organizador: el scheduler no programa el envío diario y el
    # panel de administración oculta los botones de envío.
    REMINDERS_ENABLED = os.environ.get("REMINDERS_ENABLED", "0") in ("1", "true", "yes")

    # ------------------------------------------------------------------
    # La Vuelta a España 2026 (competencia activa)
    # ------------------------------------------------------------------
    VUELTA_YEAR = 2026

    # Las etapas de La Vuelta salen ~13:00 hora de España. Guardamos la hora de
    # salida en hora de Chile, convertida desde esta hora europea: así el cambio
    # de horario chileno del 6 de septiembre se aplica solo (agosto = 6 h de
    # diferencia, septiembre = 5 h). El admin puede ajustar cada etapa a mano.
    VUELTA_EUROPE_TZ = "Europe/Madrid"
    VUELTA_EUROPE_START_HOUR = 13
    VUELTA_EUROPE_START_MINUTE = 0

    # Puntajes POR DEFECTO de La Vuelta. Solo se usan para crear la fila de
    # configuración la primera vez; después manda lo que el admin guarde en el
    # panel (tabla vuelta_scoring).
    VUELTA_POINTS_FIRST = 3
    VUELTA_POINTS_SECOND = 2
    VUELTA_POINTS_THIRD = 1
    VUELTA_POINTS_RED = 1
    VUELTA_POINTS_GREEN = 1
    VUELTA_POINTS_BLUE = 1
    VUELTA_POINTS_WHITE = 1

    # ------------------------------------------------------------------
    # Archivo del Tour de France 2026
    # ------------------------------------------------------------------
    # Las pantallas del Tour quedan archivadas bajo este prefijo y visibles solo
    # para administradores. Los datos (etapas, apuestas, resultados y puntos) se
    # conservan intactos en sus tablas originales.
    ARCHIVE_URL_PREFIX = "/archivo/tdf2026"
