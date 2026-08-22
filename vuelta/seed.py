"""Carga inicial de La Vuelta a España 2026: 21 etapas + lista de inscritos.

Los datos embebidos (STAGES_2026 y FAVORITES) actúan como respaldo fiable: el
scraper intenta primero y, si la web cambió o no hay red, se usa la copia local
para que la app arranque igual. Nada de esto toca los datos del Tour de France.
"""
from datetime import date

from tdf.extensions import db

from . import scraper
from .models import VueltaRider, VueltaScoring, VueltaStage
from .timeutils import europe_to_local

YEAR = 2026

# Respaldo del recorrido: (número, mes, día, salida, meta, km, tipo).
# 22 de agosto → 13 de septiembre de 2026, con descanso el 31-8 y el 7-9.
STAGES_2026 = [
    (1, 8, 22, "Monaco", "Monaco", 9.4, "ITT"),
    (2, 8, 23, "Monaco", "Manosque", 204.0, "hills"),
    (3, 8, 24, "Gruisan", "Font Romeu", 174.0, "mountains"),
    (4, 8, 25, "Andorra La Vella", "Andorra La Vella", 104.8, "mountains"),
    (5, 8, 26, "Falset", "Roquetes", 173.3, "flat"),
    (6, 8, 27, "Alcossebre", "Castellón", 177.4, "hills"),
    (7, 8, 28, "Vall d'Alba", "Valdelinares", 149.8, "mountains"),
    (8, 8, 29, "Puçol", "Xeraco", 171.0, "flat"),
    (9, 8, 30, "La Villa Joiosa", "Alto de Aitana", 187.4, "mountains"),
    (10, 9, 1, "Alcaraz", "Elche de la Sierra", 184.7, "hills"),
    (11, 9, 2, "Cartagena", "Lorca", 151.3, "flat"),
    (12, 9, 3, "Vera", "Calar Alto", 166.6, "mountains"),
    (13, 9, 4, "Almuñécar", "Loja", 192.8, "hills"),
    (14, 9, 5, "Jaén", "Sierra de la Pandera", 154.5, "mountains"),
    (15, 9, 6, "Palma del Río", "Córdoba", 189.7, "hills"),
    (16, 9, 8, "Cortegana", "La Rábida", 181.1, "flat"),
    (17, 9, 9, "Dos Hermanas", "Sevilla", 185.0, "flat"),
    (18, 9, 10, "El Puerto de Santa María", "Jerez de la Frontera", 32.1, "ITT"),
    (19, 9, 11, "Vélez-Málaga", "Peñas Blancas", 210.8, "mountains"),
    (20, 9, 12, "La Calahorra", "Collado del Alguacil", 186.8, "mountains"),
    (21, 9, 13, "Granada", "Granada", 112.0, "hills"),
]

# Respaldo mínimo de corredores (candidatos a la general y a etapas), por si la
# lista de inscritos no se puede scrapear en el primer arranque.
FAVORITES = [
    ("Tadej Pogačar", "UAE Team Emirates - XRG"),
    ("Primož Roglič", "Red Bull - BORA - hansgrohe"),
    ("João Almeida", "UAE Team Emirates - XRG"),
    ("Juan Ayuso", "Lidl - Trek"),
    ("Enric Mas", "Movistar Team"),
    ("Mikel Landa", "Soudal Quick-Step"),
    ("Ethan Hayter", "Soudal Quick-Step"),
    ("Joshua Tarling", "Netcompany INEOS"),
    ("Wout van Aert", "Team Visma | Lease a Bike"),
    ("Mads Pedersen", "Lidl - Trek"),
    ("Jordi Meeus", "Red Bull - BORA - hansgrohe"),
    ("Christophe Laporte", "Team Visma | Lease a Bike"),
    ("Finn Fisher-Black", "Red Bull - BORA - hansgrohe"),
    ("Léo Bisiaux", "Decathlon CMA CGM Team"),
    ("Callum Thornley", "Red Bull - BORA - hansgrohe"),
    ("Gianni Vermeersch", "Red Bull - BORA - hansgrohe"),
]


def seed_stages():
    """Inserta las 21 etapas si la tabla está vacía.

    Se prioriza lo scrapeado (fechas, ciudades, distancia y tipo actualizados) y
    se cae al respaldo embebido campo por campo.
    """
    if VueltaStage.query.count() > 0:
        return

    scraped = {s["number"]: s for s in scraper.scrape_stages()}

    for number, month, day, start, finish, dist, stype in STAGES_2026:
        info = scraped.get(number, {})
        stage_month = info.get("month") or month
        stage_day = info.get("day") or day
        db.session.add(VueltaStage(
            number=number,
            date=date(YEAR, stage_month, stage_day),
            start_city=info.get("start_city") or start,
            finish_city=info.get("finish_city") or finish,
            distance_km=info.get("distance_km") or dist,
            stage_type=info.get("stage_type") or stype,
            profile_image_url=scraper.profile_image_url(number),
            start_time=europe_to_local(YEAR, stage_month, stage_day),
            is_finished=False,
        ))
    db.session.commit()
    print(f"[vuelta/seed] {VueltaStage.query.count()} etapas creadas.")


def seed_riders():
    """Puebla la lista de corredores con los inscritos (o con el respaldo)."""
    if VueltaRider.query.count() > 0:
        return

    scraped = scraper.scrape_startlist()
    favorite_names = {name.lower() for name, _ in FAVORITES}

    seen = set()
    for item in scraped:
        name = (item.get("name") or "").strip()
        if not name or name.lower() in seen:
            continue
        seen.add(name.lower())
        db.session.add(VueltaRider(name=name, team=item.get("team"),
                                   is_favorite=name.lower() in favorite_names))

    # El respaldo se añade siempre: garantiza que los nombres más buscados estén
    # en el desplegable aunque el scraping de inscritos haya fallado.
    for name, team in FAVORITES:
        if name.lower() not in seen:
            seen.add(name.lower())
            db.session.add(VueltaRider(name=name, team=team, is_favorite=True))

    db.session.commit()
    print(f"[vuelta/seed] {VueltaRider.query.count()} corredores cargados.")


def refresh_riders():
    """Vuelve a leer la lista de inscritos y añade los que falten.

    Pensado para el botón del panel de administración: La Vuelta publica bajas y
    sustituciones durante la carrera. Nunca borra corredores (podrían estar ya
    elegidos en una apuesta), solo agrega y completa el equipo si faltaba.
    """
    scraped = scraper.scrape_startlist()
    if not scraped:
        return "No se pudo obtener la lista de inscritos; nada que actualizar."

    existing = {r.name.lower(): r for r in VueltaRider.query.all()}
    added, updated = 0, 0
    for item in scraped:
        name = (item.get("name") or "").strip()
        if not name:
            continue
        rider = existing.get(name.lower())
        if rider is None:
            rider = VueltaRider(name=name, team=item.get("team"))
            db.session.add(rider)
            existing[name.lower()] = rider
            added += 1
        elif not rider.team and item.get("team"):
            rider.team = item["team"]
            updated += 1
    db.session.commit()
    return (f"Lista de inscritos actualizada: {added} corredor(es) nuevo(s), "
            f"{updated} con equipo completado. Total: {len(existing)}.")


def seed_scoring():
    """Crea la fila de puntajes con los valores por defecto si no existe."""
    VueltaScoring.get()


def run_seed():
    seed_stages()
    seed_riders()
    seed_scoring()
