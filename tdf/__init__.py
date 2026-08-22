"""Fábrica de la aplicación Flask.

La competencia activa es **La Vuelta a España 2026** (paquete `vuelta`), que se
sirve en la raíz del sitio. El **Tour de France 2026** (este paquete) queda
archivado: sus datos —etapas, apuestas, resultados y puntos— se conservan
intactos en sus tablas y sus pantallas siguen existiendo, pero movidas bajo
Config.ARCHIVE_URL_PREFIX y visibles solo para administradores. Así el próximo
año se puede reactivar sin haber perdido nada.

Las cuentas de usuario (tabla `users`) y el login son compartidos por ambas.
"""
import atexit

from flask import Flask

from config import Config
from .extensions import db, login_manager
from .timeutils import now_local


def create_app(config_class=Config, start_scheduler=True):
    app = Flask(
        __name__,
        template_folder="../templates",
        static_folder="../static",
    )
    app.config.from_object(config_class)

    db.init_app(app)
    login_manager.init_app(app)

    from .models import User

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    _register_blueprints(app, config_class)
    _register_template_helpers(app)

    # Crear tablas y cargar datos iniciales de ambas competencias.
    with app.app_context():
        db.create_all()
        from .seed import run_seed
        run_seed(config_class)
        from vuelta.seed import run_seed as run_vuelta_seed
        run_vuelta_seed()

    if start_scheduler:
        _start_scheduler(app, config_class)

    return app


def _register_blueprints(app, config_class):
    """Registra La Vuelta en la raíz y el Tour bajo el prefijo de archivo."""
    from .auth import bp as auth_bp
    from .main import bp as tdf_main_bp
    from .admin import bp as tdf_admin_bp
    from vuelta.main import bp as vuelta_bp
    from vuelta.admin import bp as vuelta_admin_bp

    # Autenticación: compartida, sin prefijo.
    app.register_blueprint(auth_bp)

    # Competencia activa: La Vuelta a España 2026.
    app.register_blueprint(vuelta_bp)
    app.register_blueprint(vuelta_admin_bp)

    # Archivo del Tour de France 2026: mismas vistas, movidas bajo el prefijo de
    # archivo. La guarda que las restringe a administradores la instalan los
    # propios blueprints al importarse (ver tdf/archive.py).
    prefix = config_class.ARCHIVE_URL_PREFIX.rstrip("/")
    app.register_blueprint(tdf_main_bp, url_prefix=prefix)
    app.register_blueprint(tdf_admin_bp, url_prefix=f"{prefix}/admin")


def _register_template_helpers(app):
    # Maillots del Tour, para las plantillas archivadas. Se llama TDF_JERSEYS
    # para no chocar con JERSEYS, que son los cuatro maillots de La Vuelta.
    tdf_jerseys = {
        "yellow": ("Maillot Amarillo", "General", "#ffd60a", "🟡"),
        "green": ("Maillot Verde", "Puntos", "#38b000", "🟢"),
        "polka": ("Maillot de Puntos Rojos", "Montaña", "#e5383b", "🔴"),
        "white": ("Maillot Blanco", "Joven", "#f8f9fa", "⚪"),
    }

    @app.template_filter("fdate")
    def fdate(value):
        if not value:
            return ""
        return value.strftime("%d/%m/%Y")

    @app.template_filter("fdatetime")
    def fdatetime(value):
        if not value:
            return ""
        return value.strftime("%d/%m/%Y %H:%M")

    @app.template_filter("pts")
    def pts(value):
        """Formatea una cantidad de puntos con el singular/plural correcto."""
        number = value or 0
        return f"{number} pt" if number == 1 else f"{number} pts"

    @app.context_processor
    def inject_globals():
        return {"now": now_local(), "TDF_JERSEYS": tdf_jerseys}


def _start_scheduler(app, config_class):
    """Arranca el poller de resultados de La Vuelta.

    Revisa cada N minutos y solo scrapea cuando la etapa activa ya debería haber
    terminado (salida + duración esperada), hasta obtener resultados. El Tour
    está archivado, así que ya no se consulta.
    """
    from datetime import timedelta

    from apscheduler.schedulers.background import BackgroundScheduler
    from vuelta.models import VueltaStage
    from vuelta.updater import update_results

    interval = config_class.RESULTS_POLL_INTERVAL_MINUTES
    duration = config_class.STAGE_EXPECTED_DURATION_HOURS

    def job():
        with app.app_context():
            try:
                now = now_local()
                active = (VueltaStage.query.filter_by(is_finished=False)
                          .order_by(VueltaStage.number).first())
                if active is None or now < active.start_time + timedelta(hours=duration):
                    return
                print(f"[scheduler] {now:%Y-%m-%d %H:%M} - {update_results()}")
            except Exception as exc:  # noqa: BLE001
                print(f"[scheduler] Error: {exc}")

    scheduler = BackgroundScheduler(daemon=True, timezone=config_class.TIMEZONE)
    scheduler.add_job(
        job,
        "interval",
        minutes=interval,
        id="vuelta_results_poller",
        replace_existing=True,
        max_instances=1,
        misfire_grace_time=300,
        coalesce=True,
    )

    # Recordatorio diario de votación por email: DESACTIVADO por configuración
    # (Config.REMINDERS_ENABLED). Para volver a activarlo basta con poner la
    # variable de entorno REMINDERS_ENABLED=1 y tener credenciales SMTP.
    if getattr(config_class, "REMINDERS_ENABLED", False):
        from .mailer import mail_enabled, send_vote_reminders
        if mail_enabled(config_class):
            scheduler.add_job(
                lambda: send_vote_reminders(app),
                "cron",
                hour=config_class.REMINDER_HOUR,
                minute=config_class.REMINDER_MINUTE,
                id="vote_reminder",
                replace_existing=True,
                max_instances=1,
                misfire_grace_time=3600,
                coalesce=True,
            )
            print(f"[scheduler] Recordatorio de votación a las "
                  f"{config_class.REMINDER_HOUR:02d}:"
                  f"{config_class.REMINDER_MINUTE:02d} "
                  f"· {config_class.TIMEZONE}.")
        else:
            print("[scheduler] Recordatorios por email deshabilitados "
                  "(faltan MAIL_USERNAME/MAIL_PASSWORD).")
    else:
        print("[scheduler] Recordatorios por email DESACTIVADOS "
              "(REMINDERS_ENABLED=0).")

    scheduler.start()
    print(f"[scheduler] Poller de resultados de La Vuelta cada {interval} min "
          f"(intenta desde salida + {duration} h) · {config_class.TIMEZONE}.")
    atexit.register(lambda: scheduler.shutdown(wait=False))
