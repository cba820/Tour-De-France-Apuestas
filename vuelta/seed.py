"""Carga inicial de La Vuelta a España 2026: 21 etapas + lista de inscritos.

Los datos embebidos (STAGES_2026 y STARTLIST) actúan como respaldo fiable: el
scraper intenta primero y, si la web cambió, no hay red o la fuente bloquea la
IP del servidor, se usa la copia local para que la app arranque completa.

Todo es idempotente: cada función comprueba si ya hay datos y no hace nada si es
así, de modo que reiniciar el servicio no duplica ni sobrescribe nada. Ninguna
de estas funciones toca los datos del Tour de France.
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

# Respaldo de la lista de inscritos, tal como la publicaba procyclingstats el
# 22-08-2026 (día de la salida): 184 corredores de 23 equipos. Sirve para que la
# app arranque con el desplegable completo aunque el scraping falle o la fuente
# bloquee la IP del servidor. Al refrescar inscritos desde el panel se completa
# con las sustituciones que haya habido.
STARTLIST = {
    "Alpecin - Premier Tech": [
        "Francesco Busatto", "Gal Glivar", "Hugo Houle", "Kaden Groves",
        "Lindsay de Vylder", "Michael Gogl", "Ramses Debruyne",
        "Sente Sentjens"
    ],
    "Bahrain - Victorious": [
        "Attila Valter", "Jakob Omrzel", "Matevž Govekar",
        "Mathijs Paasschens", "Pau Miquel Delgado", "Pello Bilbao",
        "Roman Ermakov", "Santiago Buitrago Sanchez"
    ],
    "Burgos Burpellet BH": [
        "Clément Alleno", "César Macías Estrada", "Jesús Herrada Lopez",
        "José Luis Faura Asensio", "José Manuel Díaz Gallego",
        "Mario Aparicio Munoz", "Sergio Geovani Chumil Gonzalez",
        "Sinuhé Fernández Rodriguez"
    ],
    "Cofidis": [
        "Alex Kirsch", "Alexis Renard", "Bryan Coquard",
        "Emanuel Buchmann", "Louis Rouland", "Paul Ourselin",
        "Sergio Samitier", "Sylvain Moniquet"
    ],
    "Decathlon CMA CGM Team": [
        "Callum Scotson", "Felix Gall", "Gregor Mühlberger",
        "Jordan Labrosse", "Léo Bisiaux", "Matthew Riccitello",
        "Oscar Chamberlain", "Sander de Pestel"
    ],
    "EF Education - EasyPost": [
        "Alastair Mackellar", "Darren Rafferty", "Georg Steinhauser",
        "James Shaw", "Juan Felipe Rodriguez", "Markel Beloki",
        "Richard Carapaz", "Vincenzo Albanese"
    ],
    "Equipo Kern Pharma": [
        "Diego Uriarte Belzunegi", "Ibon Ruiz", "Iván Cobo Cayon",
        "Iván Ramiro Sosa", "Iñigo Elosegui", "Marc Brustenga Masague",
        "Mats Wenzel", "Urko Berrade Fernandez"
    ],
    "Groupama - FDJ United": [
        "Bastien Tronchon", "Clément Berthet", "Enzo Paleni",
        "Guillaume Martin", "Olivier le Gac", "Rudy Molard", "Rémy Rochas",
        "Valentin Madouas"
    ],
    "Lidl - Trek": [
        "Jacopo Mosca", "Julien Bernard", "Lennard Kämna", "Mads Pedersen",
        "Mathias Norsgaard", "Mattias Skjelmose Jensen", "Patrick Konrad",
        "Thibau Nys"
    ],
    "Lotto Intermarché": [
        "Jarno Widar", "Lars Craps", "Lorenzo Rota", "Luca van Boven",
        "Reuben Thompson", "Roel van Sintmaartensdijk",
        "Steffen de Schuyteneer", "Vito Braet"
    ],
    "Movistar Team": [
        "Carlos Canal", "Cian Uijtdebroeks", "Enric Mas", "Iván Romeo",
        "Jorge Arcas", "Orluis Aular", "Pablo Castrillo Zapater",
        "Raúl García Pierna"
    ],
    "NSN Cycling Team": [
        "Aleksey Lutsenko", "Floris van Tricht", "George Bennett",
        "Hugo Hofstetter", "Jan Hirt", "Moritz Kretschy", "Nick Schultz",
        "Pau Martí Soriano"
    ],
    "Netcompany INEOS": [
        "Axel Laurance", "Ben Turner", "Carlos Rodríguez Cano",
        "Embret Svestad-Bårdseng", "Jack Haig", "Joshua Tarling",
        "Lucas Hamilton", "Oscar Onley"
    ],
    "Pinarello Q36.5 Pro Cycling Team": [
        "David González Lopez", "David de la Cruz", "Edward Irl Dunbar",
        "Marcel Camprubí", "Milan Vader", "Thomas Gloag", "Walter Calzoni",
        "Xabier Mikel Azparren Irurzun"
    ],
    "Red Bull - BORA - hansgrohe": [
        "Callum Thornley", "Finn Fisher-Black", "Frederik Wandahl",
        "Gianni Moscon", "Gianni Vermeersch", "Jordi Meeus",
        "Luke Tuckwell", "Primož Roglič"
    ],
    "Soudal Quick-Step": [
        "Alberto Dainese", "Ethan Hayter", "Fabio van den Bossche",
        "Filippo Zana", "Gianmarco Garofoli", "Mauri Vansevenant",
        "Mikel Landa", "Valentin Paret-Peintre"
    ],
    "Team Jayco AlUla": [
        "Alessandro Covi", "Asbjorn Hellemose", "Finlay Pickering",
        "Hamish Mckenzie", "Jasha Sütterlin", "Koen Bouwman",
        "Paul Double", "Rudy Porter"
    ],
    "Team Picnic PostNL": [
        "Chris Hamilton", "Gijs Leemreize", "Guillermo Juan Martinez",
        "Henri-François Renard-Haquin", "Mattia Gaffuri", "Oliver Peace",
        "Timo Roosen", "Timo de Jong"
    ],
    "Team Visma | Lease a Bike": [
        "Ben Tulett", "Bruno Armirail", "Christophe Laporte",
        "Jorgen Nordhagen", "Matthew Brennan", "Sepp Kuss",
        "Steven Kruijswijk", "Wout van Aert"
    ],
    "Tudor Pro Cycling Team": [
        "Arthur Kluckers", "Fabian Weiss", "Hannes Wilksch",
        "Lawrence Warbasse", "Marco Brenner", "Roland Thalmann",
        "Stefan Küng", "William Barta"
    ],
    "UAE Team Emirates - XRG": [
        "Domen Novak", "Ivo Emanuel Alves", "Jay Vine", "João Almeida",
        "Kevin Vermaerke", "Pablo Torres Arias", "Pavel Sivakov",
        "Tadej Pogačar"
    ],
    "Uno-X Mobility": [
        "Andreas Kron", "Andreas Leknessund", "Fredrik Dversnes",
        "Magnus Cort Nielsen", "Martin Tjotta", "Rasmus Tiller",
        "Simon Dalby", "Tobias Halland Johannessen"
    ],
    "XDS Astana Team": [
        "Alessandro Romele", "Cristián Rodríguez", "Darren van Bekkum",
        "Harold Tejada", "Henok Mulubrhan", "Lorenzo Fortunato",
        "Victor Langellotti", "Yevgeniy Fedorov"
    ],
}

# Candidatos a la general y a etapas: se marcan con estrella en el desplegable.
FAVORITES = [
    "Tadej Pogačar", "Primož Roglič", "João Almeida", "Richard Carapaz",
    "Enric Mas", "Mikel Landa", "Ethan Hayter", "Joshua Tarling",
    "Wout van Aert", "Mads Pedersen", "Jordi Meeus", "Christophe Laporte",
    "Finn Fisher-Black", "Léo Bisiaux", "Santiago Buitrago Sanchez",
    "Cian Uijtdebroeks", "Felix Gall", "Kaden Groves", "Sepp Kuss",
    "Oscar Onley", "Jay Vine", "Pello Bilbao",
]


def backup_riders():
    """La start list de respaldo como lista de dicts {name, team}."""
    return [{"name": name, "team": team}
            for team, names in STARTLIST.items()
            for name in names]


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
    """Puebla la lista de corredores con los inscritos.

    Intenta la fuente en vivo y, si falla (web caída, estructura cambiada o la
    IP del servidor bloqueada), usa la start list embebida: así el desplegable
    de la apuesta nunca queda a medias.
    """
    if VueltaRider.query.count() > 0:
        return

    scraped = scraper.scrape_startlist()
    if scraped:
        source = "fuente en vivo"
    else:
        scraped = backup_riders()
        source = "respaldo embebido"

    favorite_names = {name.lower() for name in FAVORITES}
    seen = set()
    for item in scraped:
        name = (item.get("name") or "").strip()
        if not name or name.lower() in seen:
            continue
        seen.add(name.lower())
        db.session.add(VueltaRider(name=name, team=item.get("team"),
                                   is_favorite=name.lower() in favorite_names))

    # Los favoritos se aseguran siempre, incluso si la fuente los omitió.
    for item in backup_riders():
        name = item["name"]
        if name.lower() in favorite_names and name.lower() not in seen:
            seen.add(name.lower())
            db.session.add(VueltaRider(name=name, team=item["team"],
                                       is_favorite=True))

    db.session.commit()
    print(f"[vuelta/seed] {VueltaRider.query.count()} corredores cargados "
          f"({source}).")


def refresh_riders():
    """Vuelve a leer la lista de inscritos y añade los que falten.

    Pensado para el botón del panel de administración: La Vuelta publica bajas y
    sustituciones durante la carrera. Nunca borra corredores (podrían estar ya
    elegidos en una apuesta), solo agrega y completa el equipo si faltaba.
    """
    scraped = scraper.scrape_startlist()
    if not scraped:
        return ("No se pudo leer la lista de inscritos de la fuente "
                "(¿sin red o IP bloqueada?); no se cambió nada.")

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
