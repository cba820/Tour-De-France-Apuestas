"""Modelos de datos (SQLAlchemy)."""
from datetime import datetime, time, timedelta

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db
from .timeutils import now_local

# La votación se cierra este nº de horas antes de la salida de la etapa.
VOTING_CLOSE_HOURS_BEFORE = 1


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    # Cuenta bloqueada por el administrador: no puede iniciar sesión y no aparece
    # en la clasificación ni en las estadísticas, pero su historial se conserva
    # intacto y vuelve a contar si se la desbloquea. La columna la añade
    # tdf/migrations.py, porque db.create_all() no altera tablas existentes.
    is_blocked = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=now_local)

    predictions = db.relationship("Prediction", backref="user", lazy=True,
                                  cascade="all, delete-orphan")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def is_active(self):
        """Flask-Login usa esta propiedad: con False, login_user() rechaza.

        Sobrescribe la de UserMixin (que devuelve True siempre) para que una
        cuenta bloqueada no pueda iniciar sesión por ninguna vía.
        """
        return not self.is_blocked

    @property
    def total_points(self):
        return sum(p.points for p in self.predictions)


class Stage(db.Model):
    __tablename__ = "stages"

    id = db.Column(db.Integer, primary_key=True)
    number = db.Column(db.Integer, unique=True, nullable=False, index=True)
    date = db.Column(db.Date, nullable=False)
    start_city = db.Column(db.String(120))
    finish_city = db.Column(db.String(120))
    distance_km = db.Column(db.Float)
    elevation_m = db.Column(db.Integer)
    stage_type = db.Column(db.String(32))  # flat / hills / mountains / ITT / TTT
    profile_image_url = db.Column(db.String(300))
    # Hora de salida (local). La votación cierra VOTING_CLOSE_HOURS_BEFORE h antes.
    start_time = db.Column(db.DateTime, nullable=False)
    is_finished = db.Column(db.Boolean, default=False, nullable=False)

    result = db.relationship("StageResult", backref="stage", uselist=False,
                             cascade="all, delete-orphan")
    predictions = db.relationship("Prediction", backref="stage", lazy=True,
                                  cascade="all, delete-orphan")

    @property
    def voting_deadline(self):
        """La votación cierra VOTING_CLOSE_HOURS_BEFORE h antes de la salida."""
        return self.start_time - timedelta(hours=VOTING_CLOSE_HOURS_BEFORE)

    @property
    def voting_opens(self):
        """La votación se habilita el día anterior a la carrera (00:00 hora Chile)."""
        return datetime.combine(self.date - timedelta(days=1), time(0, 0))

    def is_open_for_voting(self, now=None):
        now = now or now_local()
        return (not self.is_finished
                and self.voting_opens <= now < self.voting_deadline)

    @property
    def title(self):
        return f"Etapa {self.number}: {self.start_city} → {self.finish_city}"

    def status(self, now=None):
        """Estado legible: 'finished' / 'upcoming' / 'open' / 'closed'."""
        now = now or now_local()
        if self.is_finished:
            return "finished"
        if now < self.voting_opens:
            return "upcoming"      # aún bloqueada (se abre el día anterior)
        if now < self.voting_deadline:
            return "open"
        return "closed"            # votación cerrada, carrera en curso / sin resultados


class StageResult(db.Model):
    __tablename__ = "stage_results"

    id = db.Column(db.Integer, primary_key=True)
    stage_id = db.Column(db.Integer, db.ForeignKey("stages.id"), unique=True, nullable=False)

    first_rider = db.Column(db.String(120))
    second_rider = db.Column(db.String(120))
    third_rider = db.Column(db.String(120))

    yellow_rider = db.Column(db.String(120))  # líder general
    green_rider = db.Column(db.String(120))   # líder por puntos
    polka_rider = db.Column(db.String(120))   # líder montaña
    white_rider = db.Column(db.String(120))   # mejor joven


class Rider(db.Model):
    __tablename__ = "riders"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    team = db.Column(db.String(120))
    is_favorite = db.Column(db.Boolean, default=False)


class Prediction(db.Model):
    __tablename__ = "predictions"
    __table_args__ = (db.UniqueConstraint("user_id", "stage_id", name="uq_user_stage"),)

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    stage_id = db.Column(db.Integer, db.ForeignKey("stages.id"), nullable=False)

    pick_winner = db.Column(db.String(120))
    pick_yellow = db.Column(db.String(120))
    pick_green = db.Column(db.String(120))
    pick_polka = db.Column(db.String(120))
    pick_white = db.Column(db.String(120))

    points = db.Column(db.Integer, default=0, nullable=False)
    created_at = db.Column(db.DateTime, default=now_local)


class ReminderLog(db.Model):
    """Registro de recordatorios de votación ya enviados (uno por etapa).

    Sirve de guardia anti-duplicados: si existe una fila para la etapa, el
    recordatorio ya se envió y no se vuelve a mandar. Es una tabla nueva, así que
    db.create_all() la crea automáticamente sin necesidad de migración.
    """
    __tablename__ = "reminder_logs"

    id = db.Column(db.Integer, primary_key=True)
    stage_id = db.Column(db.Integer, db.ForeignKey("stages.id"),
                         unique=True, nullable=False)
    sent_at = db.Column(db.DateTime, default=now_local)


class StageRecapLog(db.Model):
    """Registro de resúmenes post-etapa ya enviados (uno por etapa).

    Igual que ReminderLog: guardia anti-duplicados para el correo de resumen que
    se manda al cerrar una etapa. Tabla nueva, la crea db.create_all() sin migración.
    """
    __tablename__ = "stage_recap_logs"

    id = db.Column(db.Integer, primary_key=True)
    stage_id = db.Column(db.Integer, db.ForeignKey("stages.id"),
                         unique=True, nullable=False)
    sent_at = db.Column(db.DateTime, default=now_local)
