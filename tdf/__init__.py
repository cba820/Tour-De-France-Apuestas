"""Fábrica de la aplicación Flask."""
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

    # Blueprints
    from .auth import bp as auth_bp
    from .main import bp as main_bp
    from .admin import bp as admin_bp
    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(admin_bp)

    _register_template_helpers(app)

    # Crear tablas y cargar datos iniciales.
    with app.app_context():
        db.create_all()
        from .seed import run_seed
        run_seed(config_class)

    if start_scheduler:
        _start_scheduler(app, config_class)

    return app


def _register_template_helpers(app):
    jerseys = {
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

    @app.context_processor
    def inject_globals():
        return {"now": now_local(), "JERSEYS": jerseys}


def _start_scheduler(app, config_class):
    """Arranca el poller de resultados: revisa cada N minutos y solo scrapea
    cuando la etapa activa ya debería haber terminado, hasta obtener resultados."""
    from datetime import timedelta

    from apscheduler.schedulers.background import BackgroundScheduler
    from .models import Stage
    from .updater import update_results

    interval = config_class.RESULTS_POLL_INTERVAL_MINUTES
    duration = config_class.STAGE_EXPECTED_DURATION_HOURS

    def job():
        with app.app_context():
            try:
                now = now_local()
                # Etapa activa = primera no terminada.
                active = (Stage.query.filter_by(is_finished=False)
                          .order_by(Stage.number).first())
                # Solo intentar cuando la etapa activa ya debería haber terminado.
                if active is None or now < active.start_time + timedelta(hours=duration):
                    return
                msg = update_results()
                print(f"[scheduler] {now:%Y-%m-%d %H:%M} - {msg}")
            except Exception as exc:  # noqa: BLE001
                print(f"[scheduler] Error: {exc}")

    scheduler = BackgroundScheduler(daemon=True, timezone=config_class.TIMEZONE)
    scheduler.add_job(
        job,
        "interval",
        minutes=interval,
        id="results_poller",
        replace_existing=True,
        max_instances=1,
        misfire_grace_time=300,
        coalesce=True,
    )

    # Recordatorio diario de votación por email (solo si hay credenciales SMTP).
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
              f"{config_class.REMINDER_HOUR:02d}:{config_class.REMINDER_MINUTE:02d} "
              f"· {config_class.TIMEZONE}.")
    else:
        print("[scheduler] Recordatorios por email deshabilitados "
              "(faltan MAIL_USERNAME/MAIL_PASSWORD).")

    scheduler.start()
    print(f"[scheduler] Poller de resultados cada {interval} min "
          f"(intenta desde salida + {duration} h) · {config_class.TIMEZONE}.")
    atexit.register(lambda: scheduler.shutdown(wait=False))
