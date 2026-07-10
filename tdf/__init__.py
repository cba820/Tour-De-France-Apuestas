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
    """Arranca el job diario de actualización de resultados."""
    from apscheduler.schedulers.background import BackgroundScheduler
    from .updater import update_results

    def job():
        with app.app_context():
            try:
                msg = update_results()
                print(f"[scheduler] {now_local():%Y-%m-%d %H:%M} - {msg}")
            except Exception as exc:  # noqa: BLE001
                print(f"[scheduler] Error: {exc}")

    scheduler = BackgroundScheduler(daemon=True, timezone=config_class.TIMEZONE)
    scheduler.add_job(
        job,
        "cron",
        hour=config_class.DAILY_UPDATE_HOUR,
        minute=config_class.DAILY_UPDATE_MINUTE,
        id="daily_update",
        replace_existing=True,
    )
    scheduler.start()
    print(f"[scheduler] Job diario registrado a las "
          f"{config_class.DAILY_UPDATE_HOUR:02d}:{config_class.DAILY_UPDATE_MINUTE:02d} "
          f"({config_class.TIMEZONE}).")
    atexit.register(lambda: scheduler.shutdown(wait=False))
