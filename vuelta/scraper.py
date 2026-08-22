"""Scraping de La Vuelta a España 2026.

Se usan dos fuentes, cada una para lo que publica de forma más fiable:

1. **cyclingstage.com** (`/vuelta-2026-route/`) para el recorrido: una tabla
   limpia con número, fecha, ciudades, kilómetros y tipo de cada etapa, más las
   imágenes de altimetría en su CDN. Es la misma fuente que ya usaba el Tour.

2. **procyclingstats.com** (`/race/vuelta-a-espana/2026/...`) para la lista de
   inscritos y para los resultados. Su página de etapa trae, en pestañas, la
   clasificación de la etapa y las cuatro clasificaciones que definen los
   maillots (general → rojo, puntos → verde, montaña → lunares azules,
   jóvenes → blanco). cyclingstage no publica esas cuatro para La Vuelta.

Todo es "best effort": si una web cambia de estructura y el parseo falla, las
funciones devuelven listas/valores vacíos y la app sigue funcionando con los
datos del seed y con la carga manual desde el panel de administración.
"""
import re
import unicodedata

import requests
from bs4 import BeautifulSoup

from config import Config

YEAR = Config.VUELTA_YEAR

# --- cyclingstage: recorrido e imágenes ---
CS_BASE = "https://www.cyclingstage.com"
CS_ROUTE_URL = f"{CS_BASE}/vuelta-{YEAR}-route/"
CS_CDN = f"https://cdn.cyclingstage.com/images/vuelta-spain/{YEAR}"

# --- procyclingstats: inscritos y resultados ---
PCS_BASE = "https://www.procyclingstats.com"
PCS_RACE = f"{PCS_BASE}/race/vuelta-a-espana/{YEAR}"
PCS_STARTLIST_URL = f"{PCS_RACE}/startlist"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
}

TIMEOUT = 25

# Partículas que se escriben en minúscula dentro de un apellido compuesto
# («Wout van Aert», «David de la Cruz»).
PARTICLES = {"van", "von", "de", "der", "den", "des", "del", "della", "di",
             "da", "dos", "le", "la", "el", "al", "ter", "'t", "y"}

# Etiqueta de pestaña de procyclingstats -> clave del maillot en nuestros modelos.
PCS_TAB_TO_JERSEY = {
    "GC": "red",
    "POINTS": "green",
    "KOM": "blue",
    "YOUTH": "white",
}


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------

def profile_image_url(stage_number):
    """URL de la imagen de altimetría de una etapa (CDN de cyclingstage)."""
    return f"{CS_CDN}/stage-{stage_number}-profile.jpg"


def route_map_url():
    """URL del mapa general del recorrido."""
    return f"{CS_CDN}/route.jpg"


def _get_soup(url):
    resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    resp.raise_for_status()
    return BeautifulSoup(resp.text, "html.parser")


def _parse_float(text):
    m = re.search(r"\d[\d.]*", (text or "").replace(",", "."))
    return float(m.group().rstrip(".")) if m else None


def _plain(text):
    """Minúsculas sin acentos, para comparar nombres entre fuentes."""
    decomposed = unicodedata.normalize("NFKD", (text or "").lower())
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def _titlecase(token):
    """«ROGLIČ» -> «Roglič» (respetando los acentos ya presentes)."""
    if len(token) > 1 and token.isupper():
        return token[0] + token[1:].lower()
    return token


def _normalize_type(raw):
    """Normaliza el tipo de etapa (la fuente tiene erratas como «hils»)."""
    text = (raw or "").strip().lower()
    if not text:
        return None
    if "ttt" in text or "team time" in text:
        return "TTT"
    if "itt" in text or "individual time" in text or text == "tt":
        return "ITT"
    if text.startswith("mount") or "mtn" in text:
        return "mountains"
    if text.startswith("hil") or text.startswith("hll"):   # hills / «hils»
        return "hills"
    if text.startswith("flat"):
        return "flat"
    return None


def rider_name(href, display):
    """Nombre presentable de un corredor a partir de su enlace en PCS.

    PCS muestra «ROGLIČ Primož» (apellido primero, en mayúsculas) pero su URL
    lleva el orden natural: `rider/primoz-roglic`. Combinamos ambos: el orden
    lo da la URL y los acentos el texto visible, así que obtenemos
    «Primož Roglič». Es importante que sea estable, porque este mismo nombre se
    guarda en la lista de corredores (para el desplegable de la apuesta) y en
    los resultados, y así el acierto se detecta sin ambigüedad.
    """
    display = (display or "").strip()
    slug = (href or "").rstrip("/").rsplit("/", 1)[-1]
    slug_tokens = [t for t in slug.split("-") if t]
    if not slug_tokens:
        return display

    # Los tokens visibles se parten también por guion, para que un apellido como
    # «FISHER-BLACK» empareje con los tokens «fisher» y «black» de la URL.
    pool = []
    for word in re.split(r"\s+", display):
        if not word:
            continue
        parts = word.split("-")
        for i, part in enumerate(parts):
            pool.append({"text": part, "join": "-" if i < len(parts) - 1 else " "})

    ordered = []
    for token in slug_tokens:
        found = None
        for item in pool:
            if _plain(item["text"]) == token:
                found = item
                break
        if found is None:
            ordered.append({"text": token.capitalize(), "join": " "})
        else:
            pool.remove(found)
            ordered.append({"text": _titlecase(found["text"]), "join": found["join"]})

    name = ordered[0]["text"]
    for i in range(1, len(ordered)):
        text = ordered[i]["text"]
        if _plain(text) in PARTICLES:
            text = text.lower()
        name += ordered[i - 1]["join"] + text
    return name.strip()


# ---------------------------------------------------------------------------
# Recorrido (cyclingstage)
# ---------------------------------------------------------------------------

def scrape_stages():
    """Lista de dicts con las etapas del recorrido. [] si el parseo falla.

    Cada dict: number, month, day, start_city, finish_city, distance_km,
    stage_type, profile_image_url. Las filas de día de descanso se ignoran
    (vienen sin número de etapa).
    """
    try:
        soup = _get_soup(CS_ROUTE_URL)
    except Exception as exc:  # noqa: BLE001
        print(f"[vuelta/scraper] No se pudo obtener el recorrido: {exc}")
        return []

    stages = {}
    for row in soup.select("table tr"):
        cells = [c.get_text(" ", strip=True) for c in row.find_all("td")]
        if len(cells) < 4:
            continue
        if not re.fullmatch(r"\d{1,2}", cells[0] or ""):
            continue  # encabezado o día de descanso
        number = int(cells[0])

        date_match = re.match(r"(\d{1,2})\s*-\s*(\d{1,2})", cells[1] or "")
        if not date_match:
            continue
        day, month = int(date_match.group(1)), int(date_match.group(2))

        start_city, _, finish_city = (cells[2] or "").partition(" - ")
        stages[number] = {
            "number": number,
            "month": month,
            "day": day,
            "start_city": start_city.strip() or None,
            "finish_city": finish_city.strip() or start_city.strip() or None,
            "distance_km": _parse_float(cells[3]),
            "stage_type": _normalize_type(cells[4] if len(cells) > 4 else None),
            "profile_image_url": profile_image_url(number),
        }
    return [stages[n] for n in sorted(stages)]


# ---------------------------------------------------------------------------
# Inscritos (procyclingstats)
# ---------------------------------------------------------------------------

def scrape_startlist():
    """Lista de dicts {name, team} con los corredores inscritos. [] si falla."""
    try:
        soup = _get_soup(PCS_STARTLIST_URL)
    except Exception as exc:  # noqa: BLE001
        print(f"[vuelta/scraper] No se pudo obtener la lista de inscritos: {exc}")
        return []

    riders = []
    for team_block in soup.select("ul.startlist_v4 > li"):
        riders_box = team_block.select_one("div.ridersCont")
        if riders_box is None:
            continue
        team_link = riders_box.select_one("a.team")
        team = team_link.get_text(" ", strip=True) if team_link else None
        if team:
            # PCS añade la categoría al final: «Movistar Team (WT)».
            team = re.sub(r"\s*\((?:WT|PRT|PCT|CT|NAT)\)\s*$", "", team).strip()
        for link in riders_box.select('a[href^="rider/"]'):
            name = rider_name(link.get("href"), link.get_text(" ", strip=True))
            if name:
                riders.append({"name": name, "team": team})
    return riders


# ---------------------------------------------------------------------------
# Resultados (procyclingstats)
# ---------------------------------------------------------------------------

def _tab_leaders(soup, top=3):
    """Primeros clasificados de cada pestaña de una página de etapa de PCS.

    La página trae un `ul.resultTabs` con las etiquetas (STAGE, GC, POINTS,
    KOM, YOUTH, TEAMS) y, en el mismo orden, un `div.resTab` por pestaña con la
    tabla de la clasificación acumulada (`div.general`). Emparejamos por
    posición: es lo único estable, porque los contenedores no llevan etiqueta.
    Las pestañas que aún no existen (p. ej. KOM tras una contrarreloj sin
    puertos) simplemente no aparecen.
    """
    labels = [li.get_text(" ", strip=True).upper()
              for li in soup.select("ul.resultTabs li")]
    containers = soup.select("div.resTab")
    out = {}
    for label, container in zip(labels, containers):
        table = container.select_one("div.general table.results") \
            or container.select_one("table.results")
        if table is None:
            continue
        names = []
        for row in table.select("tbody tr"):
            link = row.select_one('a[href^="rider/"]')
            if link is None:
                continue
            names.append(rider_name(link.get("href"),
                                    link.get_text(" ", strip=True)))
            if len(names) >= top:
                break
        if names:
            out[label] = names
    return out


def scrape_results(stage_number):
    """Podio y portadores de los cuatro maillots tras una etapa.

    Devuelve un dict con first/second/third_rider y red/green/blue/white_rider,
    o None si no se pudo determinar al ganador de la etapa (por ejemplo porque
    todavía no ha terminado). Los maillots que la fuente aún no publica quedan
    en None y no sobrescriben nada: se cargan a mano desde el panel.
    """
    url = f"{PCS_RACE}/stage-{stage_number}"
    try:
        soup = _get_soup(url)
    except Exception as exc:  # noqa: BLE001
        print(f"[vuelta/scraper] No se pudo obtener la etapa "
              f"{stage_number}: {exc}")
        return None

    tabs = _tab_leaders(soup)
    podium = tabs.get("STAGE", [])
    if not podium:
        return None

    result = {
        "first_rider": podium[0] if len(podium) > 0 else None,
        "second_rider": podium[1] if len(podium) > 1 else None,
        "third_rider": podium[2] if len(podium) > 2 else None,
    }
    for tab, key in PCS_TAB_TO_JERSEY.items():
        leaders = tabs.get(tab)
        result[f"{key}_rider"] = leaders[0] if leaders else None
    return result
