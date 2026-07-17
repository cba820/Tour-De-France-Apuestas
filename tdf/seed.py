"""Carga inicial de datos: 21 etapas + resultados de las etapas 1 y 2 + favoritos.

Los datos embebidos actúan como respaldo fiable; el scraper intenta enriquecer
(imágenes/tipos/favoritos) sobre esta base en el primer arranque.
"""
from datetime import date, datetime

from .extensions import db
from .models import Prediction, Rider, Stage, StageResult, User
from . import scraper

# (número, mes, día, salida, meta, distancia_km, tipo)
STAGES_2026 = [
    (1, 7, 4, "Barcelona", "Barcelona", 19.6, "TTT"),
    (2, 7, 5, "Tarragona", "Barcelona", 168.5, "hills"),
    (3, 7, 6, "Granollers", "Les Angles", 195.9, "mountains"),
    (4, 7, 7, "Carcassonne", "Foix", 181.9, "hills"),
    (5, 7, 8, "Lannemezan", "Pau", 158.3, "flat"),
    (6, 7, 9, "Pau", "Gavarnie-Gèdre", 186.2, "mountains"),
    (7, 7, 10, "Hagetmau", "Bordeaux", 175.1, "flat"),
    (8, 7, 11, "Périgueux", "Bergerac", 180.4, "flat"),
    (9, 7, 12, "Malemort", "Ussel", 185.5, "hills"),
    (10, 7, 14, "Aurillac", "Le Lioran", 166.6, "hills"),
    (11, 7, 15, "Vichy", "Nevers", 161.3, "flat"),
    (12, 7, 16, "Magny-Cours", "Châlon-sur-Saône", 179.1, "flat"),
    (13, 7, 17, "Dole", "Belfort", 205.8, "hills"),
    (14, 7, 18, "Mulhouse", "Le Markstein", 155.3, "mountains"),
    (15, 7, 19, "Champagnole", "Plateau de Solaison", 183.9, "mountains"),
    (16, 7, 21, "Evian-les-Bains", "Thonon-les-Bains", 26.1, "ITT"),
    (17, 7, 22, "Chambéry", "Voiron", 174.7, "flat"),
    (18, 7, 23, "Voiron", "Orcières-Merlette", 185.2, "mountains"),
    (19, 7, 24, "Gap", "Alpe d'Huez", 127.9, "mountains"),
    (20, 7, 25, "Bourg d'Oissans", "Alpe d'Huez", 170.9, "mountains"),
    (21, 7, 26, "Thoiry", "Paris", 133.0, "flat"),
]

# Favoritos / candidatos a la general y a etapas (respaldo).
FAVORITES = [
    ("Tadej Pogačar", "UAE Team Emirates"),
    ("Jonas Vingegaard", "Visma | Lease a Bike"),
    ("Remco Evenepoel", "Soudal Quick-Step"),
    ("Isaac del Toro", "UAE Team Emirates"),
    ("Primož Roglič", "Red Bull - BORA - hansgrohe"),
    ("Juan Ayuso", "UAE Team Emirates"),
    ("João Almeida", "UAE Team Emirates"),
    ("Mattias Skjelmose", "Lidl - Trek"),
    ("Carlos Rodríguez", "INEOS Grenadiers"),
    ("Felix Gall", "Decathlon AG2R"),
    ("Jasper Philipsen", "Alpecin - Deceuninck"),
    ("Biniam Girmay", "Intermarché - Wanty"),
    ("Wout van Aert", "Visma | Lease a Bike"),
    ("Mathieu van der Poel", "Alpecin - Deceuninck"),
    ("Jonas Abrahamsen", "Uno-X Mobility"),
    ("Kévin Vauquelin", "Arkéa - B&B Hotels"),
    ("Enric Mas", "Movistar Team"),
    ("Ben O'Connor", "Jayco AlUla"),
]


def _default_start_time(year, month, day):
    # Salida por defecto ~07:00 hora de Chile (≈ 13:00 en Europa); editable en admin.
    from config import Config
    return datetime(year, month, day, Config.DEFAULT_START_HOUR, Config.DEFAULT_START_MINUTE)


def seed_stages():
    """Inserta las 21 etapas si no existen. Intenta enriquecer con el scraper."""
    if Stage.query.count() > 0:
        return

    scraped = {s["number"]: s for s in scraper.scrape_stages()}

    for number, month, day, start, finish, dist, stype in STAGES_2026:
        info = scraped.get(number, {})
        stage = Stage(
            number=number,
            date=date(2026, month, day),
            start_city=info.get("start_city") or start,
            finish_city=info.get("finish_city") or finish,
            distance_km=info.get("distance_km") or dist,
            stage_type=info.get("stage_type") or stype,
            profile_image_url=scraper.profile_image_url(number),
            start_time=_default_start_time(2026, month, day),
            is_finished=False,
        )
        db.session.add(stage)
    db.session.commit()
    print(f"[seed] {Stage.query.count()} etapas creadas.")


def seed_results():
    """Marca como terminadas las etapas 1 y 2 con sus resultados reales."""
    stage1 = Stage.query.filter_by(number=1).first()
    if stage1 and not stage1.is_finished:
        stage1.is_finished = True
        db.session.add(StageResult(
            stage=stage1,
            first_rider="Jonas Vingegaard",   # CRE: ganó Visma; maillot para Vingegaard
            second_rider="Tadej Pogačar",
            third_rider="Remco Evenepoel",
            yellow_rider="Jonas Vingegaard",
            green_rider="Jonas Vingegaard",
            polka_rider="Jonas Vingegaard",
            white_rider="Remco Evenepoel",
        ))

    stage2 = Stage.query.filter_by(number=2).first()
    if stage2 and not stage2.is_finished:
        stage2.is_finished = True
        db.session.add(StageResult(
            stage=stage2,
            first_rider="Isaac del Toro",
            second_rider="Tadej Pogačar",
            third_rider="Remco Evenepoel",
            yellow_rider="Jonas Vingegaard",
            green_rider="Isaac del Toro",
            polka_rider="Jonas Vingegaard",
            white_rider="Isaac del Toro",
        ))
    db.session.commit()


def seed_favorites():
    """Puebla la tabla de corredores (favoritos). Intenta el scraper primero."""
    if Rider.query.count() > 0:
        return
    scraped = scraper.scrape_favorites()
    data = scraped if scraped else [{"name": n, "team": t} for n, t in FAVORITES]
    names = set()
    for item in data:
        name = item["name"].strip()
        if name and name.lower() not in names:
            names.add(name.lower())
            db.session.add(Rider(name=name, team=item.get("team"), is_favorite=True))
    # Aseguramos que los favoritos de respaldo siempre estén disponibles.
    for name, team in FAVORITES:
        if name.lower() not in names:
            names.add(name.lower())
            db.session.add(Rider(name=name, team=team, is_favorite=True))
    db.session.commit()
    print(f"[seed] {Rider.query.count()} corredores cargados.")


def seed_admin(config):
    """Crea el usuario administrador inicial si no existe."""
    if User.query.filter_by(is_admin=True).first():
        return
    admin = User(username=config.ADMIN_USERNAME, email=config.ADMIN_EMAIL, is_admin=True)
    admin.set_password(config.ADMIN_PASSWORD)
    db.session.add(admin)
    db.session.commit()
    print(f"[seed] Admin creado: {config.ADMIN_USERNAME} / {config.ADMIN_PASSWORD}")


def promote_admins(config):
    """Promueve a admin cualquier cuenta cuyo email esté en config.ADMIN_EMAILS.

    Idempotente: se ejecuta en cada arranque, así estas cuentas siempre tienen
    rol de administrador aunque la base se recree o se registren más tarde.
    """
    emails = getattr(config, "ADMIN_EMAILS", []) or []
    if not emails:
        return
    promoted = []
    for user in User.query.filter(User.email.in_(emails)).all():
        if not user.is_admin:
            user.is_admin = True
            promoted.append(user.email)
    if promoted:
        db.session.commit()
        print(f"[seed] Promovidos a admin: {', '.join(promoted)}")


def run_seed(config):
    seed_stages()
    seed_results()
    seed_favorites()
    seed_admin(config)
    promote_admins(config)
