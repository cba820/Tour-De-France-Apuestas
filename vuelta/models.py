"""Modelos de La Vuelta a España 2026.

Todas las tablas llevan el prefijo `vuelta_` y son nuevas, así que
`db.create_all()` las crea sin migración y sin tocar las tablas del Tour de
France (`stages`, `predictions`, `stage_results`…), que quedan archivadas.

La tabla `users` es compartida: las cuentas ya creadas sirven para La Vuelta.
"""
from datetime import datetime, time, timedelta

from config import Config
from tdf.extensions import db

from .timeutils import now_local

# La votación se cierra este nº de horas antes de la salida de la etapa.
VOTING_CLOSE_HOURS_BEFORE = Config.VOTING_CLOSE_HOURS_BEFORE

# Los cuatro maillots de La Vuelta. La clave es el sufijo de columna, tanto en
# VueltaStageResult (`<clave>_rider`) como en VueltaPrediction (`pick_<clave>`)
# y en VueltaScoring (`points_<clave>`).
JERSEY_KEYS = ("red", "green", "blue", "white")


class VueltaStage(db.Model):
    """Una etapa de La Vuelta."""
    __tablename__ = "vuelta_stages"

    id = db.Column(db.Integer, primary_key=True)
    number = db.Column(db.Integer, unique=True, nullable=False, index=True)
    date = db.Column(db.Date, nullable=False)
    start_city = db.Column(db.String(120))
    finish_city = db.Column(db.String(120))
    distance_km = db.Column(db.Float)
    elevation_m = db.Column(db.Integer)
    stage_type = db.Column(db.String(32))  # flat / hills / mountains / ITT / TTT
    profile_image_url = db.Column(db.String(300))
    # Hora de salida en hora de Chile. La votación cierra
    # VOTING_CLOSE_HOURS_BEFORE h antes.
    start_time = db.Column(db.DateTime, nullable=False)
    is_finished = db.Column(db.Boolean, default=False, nullable=False)

    result = db.relationship("VueltaStageResult", backref="stage", uselist=False,
                             cascade="all, delete-orphan")
    predictions = db.relationship("VueltaPrediction", backref="stage", lazy=True,
                                  cascade="all, delete-orphan")

    @property
    def voting_deadline(self):
        return self.start_time - timedelta(hours=VOTING_CLOSE_HOURS_BEFORE)

    @property
    def voting_opens(self):
        """La votación se habilita el día anterior a la etapa (00:00 hora Chile)."""
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
            return "upcoming"
        if now < self.voting_deadline:
            return "open"
        return "closed"


class VueltaStageResult(db.Model):
    """Resultado oficial de una etapa: podio + portadores de los 4 maillots."""
    __tablename__ = "vuelta_stage_results"

    id = db.Column(db.Integer, primary_key=True)
    stage_id = db.Column(db.Integer, db.ForeignKey("vuelta_stages.id"),
                         unique=True, nullable=False)

    first_rider = db.Column(db.String(120))
    second_rider = db.Column(db.String(120))
    third_rider = db.Column(db.String(120))

    red_rider = db.Column(db.String(120))    # maillot rojo · general
    green_rider = db.Column(db.String(120))  # maillot verde · puntos
    blue_rider = db.Column(db.String(120))   # lunares azules · montaña
    white_rider = db.Column(db.String(120))  # maillot blanco · mejor joven


class VueltaRider(db.Model):
    """Corredor inscrito en La Vuelta (start list)."""
    __tablename__ = "vuelta_riders"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    team = db.Column(db.String(120))
    is_favorite = db.Column(db.Boolean, default=False)


class VueltaPrediction(db.Model):
    """Apuesta de un usuario para una etapa: ganador + los cuatro maillots."""
    __tablename__ = "vuelta_predictions"
    __table_args__ = (db.UniqueConstraint("user_id", "stage_id",
                                          name="uq_vuelta_user_stage"),)

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    stage_id = db.Column(db.Integer, db.ForeignKey("vuelta_stages.id"),
                         nullable=False)

    pick_winner = db.Column(db.String(120))
    pick_red = db.Column(db.String(120))
    pick_green = db.Column(db.String(120))
    pick_blue = db.Column(db.String(120))
    pick_white = db.Column(db.String(120))

    points = db.Column(db.Integer, default=0, nullable=False)
    created_at = db.Column(db.DateTime, default=now_local)

    user = db.relationship("User", backref=db.backref(
        "vuelta_predictions", lazy=True, cascade="all, delete-orphan"))


class VueltaScoring(db.Model):
    """Puntajes configurables por el administrador (fila única, id=1).

    Se guarda en base de datos (y no en config) para que el organizador pueda
    cambiar el valor de cada puesto y de cada maillot desde el panel web sin
    tocar código ni reiniciar el servidor. Al guardar se recalculan todos los
    puntos de las etapas ya cerradas.
    """
    __tablename__ = "vuelta_scoring"

    id = db.Column(db.Integer, primary_key=True)

    points_first = db.Column(db.Integer, nullable=False,
                             default=Config.VUELTA_POINTS_FIRST)
    points_second = db.Column(db.Integer, nullable=False,
                              default=Config.VUELTA_POINTS_SECOND)
    points_third = db.Column(db.Integer, nullable=False,
                             default=Config.VUELTA_POINTS_THIRD)

    points_red = db.Column(db.Integer, nullable=False,
                           default=Config.VUELTA_POINTS_RED)
    points_green = db.Column(db.Integer, nullable=False,
                             default=Config.VUELTA_POINTS_GREEN)
    points_blue = db.Column(db.Integer, nullable=False,
                            default=Config.VUELTA_POINTS_BLUE)
    points_white = db.Column(db.Integer, nullable=False,
                             default=Config.VUELTA_POINTS_WHITE)

    updated_at = db.Column(db.DateTime, default=now_local, onupdate=now_local)

    # Campos editables desde el panel, con su etiqueta.
    FIELDS = (
        ("points_first", "Primer lugar de la etapa", "🥇"),
        ("points_second", "Segundo lugar de la etapa", "🥈"),
        ("points_third", "Tercer lugar de la etapa", "🥉"),
        ("points_red", "Maillot rojo · general", "🔴"),
        ("points_green", "Maillot verde · puntos", "🟢"),
        ("points_blue", "Maillot de lunares azules · montaña", "🔵"),
        ("points_white", "Maillot blanco · mejor joven", "⚪"),
    )

    @classmethod
    def get(cls):
        """Configuración vigente; la crea con los valores por defecto si falta."""
        config = db.session.get(cls, 1)
        if config is None:
            config = cls(id=1)
            db.session.add(config)
            db.session.commit()
        return config

    def jersey_points(self, key):
        """Puntos que otorga acertar el maillot `key` ('red', 'green'…)."""
        return getattr(self, f"points_{key}", 0)

    @property
    def max_stage_points(self):
        """Máximo alcanzable en una etapa: ganador exacto + los 4 maillots."""
        return self.points_first + sum(self.jersey_points(k) for k in JERSEY_KEYS)
