"""Scraping de cyclingstage.com para el Tour de France 2026.

Todo es "best effort": si la estructura de la web cambia y el parseo falla,
las funciones devuelven listas/valores vacíos y la app sigue funcionando con
los datos del seed y con la entrada manual del panel de administración.
"""
import re

import requests
from bs4 import BeautifulSoup

BASE = "https://www.cyclingstage.com"
ROUTE_URL = f"{BASE}/tour-de-france-2026-route/"
RESULTS_URL = f"{BASE}/tour-de-france-2026-results/"
FAVORITES_URL = f"{BASE}/tour-de-france-2026-favorites/"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}

YEAR = 2026


def profile_image_url(stage_number):
    """URL directa (CDN) de la imagen de perfil/altimetría de una etapa."""
    return f"https://cdn.cyclingstage.com/images/tour-de-france/{YEAR}/stage-{stage_number}-profile.jpg"


def _get_soup(url):
    resp = requests.get(url, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    return BeautifulSoup(resp.text, "html.parser")


def _parse_int(text):
    m = re.search(r"\d[\d\.]*", (text or "").replace(",", ""))
    return int(float(m.group())) if m else None


def _parse_float(text):
    m = re.search(r"\d[\d\.]*", (text or "").replace(",", "."))
    return float(m.group()) if m else None


def scrape_stages():
    """Devuelve una lista de dicts con los datos de las 21 etapas.

    Cada dict: number, start_city, finish_city, distance_km, stage_type,
    profile_image_url. Devuelve [] si el parseo falla.
    """
    try:
        soup = _get_soup(ROUTE_URL)
    except Exception as exc:  # noqa: BLE001
        print(f"[scraper] No se pudo obtener la ruta: {exc}")
        return []

    stages = []
    for row in soup.select("table tr"):
        cells = [c.get_text(" ", strip=True) for c in row.find_all("td")]
        if len(cells) < 3:
            continue
        # Buscamos "Stage N" en alguna celda.
        joined = " ".join(cells)
        m = re.search(r"[Ss]tage\s+(\d+)", joined)
        if not m:
            continue
        number = int(m.group(1))
        # Ciudades: normalmente "A - B".
        route_cell = next((c for c in cells if " - " in c and not re.search(r"km", c)), "")
        start_city, _, finish_city = (route_cell.partition(" - "))
        distance = next((_parse_float(c) for c in cells if "km" in c.lower()), None)
        stage_type = _detect_type(joined)
        stages.append({
            "number": number,
            "start_city": start_city.strip() or None,
            "finish_city": finish_city.strip() or None,
            "distance_km": distance,
            "stage_type": stage_type,
            "profile_image_url": profile_image_url(number),
        })
    # De-duplicar por número.
    seen = {}
    for s in stages:
        seen[s["number"]] = s
    return [seen[n] for n in sorted(seen)]


def _detect_type(text):
    t = text.lower()
    if "ttt" in t or "team time" in t:
        return "TTT"
    if "itt" in t or "individual time" in t:
        return "ITT"
    if "mountain" in t:
        return "mountains"
    if "hill" in t:
        return "hills"
    if "flat" in t:
        return "flat"
    return None


def scrape_favorites():
    """Devuelve una lista de dicts {name, team} con los favoritos. [] si falla."""
    try:
        soup = _get_soup(FAVORITES_URL)
    except Exception as exc:  # noqa: BLE001
        print(f"[scraper] No se pudo obtener favoritos: {exc}")
        return []

    riders = []
    for row in soup.select("table tr"):
        cells = [c.get_text(" ", strip=True) for c in row.find_all("td")]
        if len(cells) >= 2 and cells[0] and not cells[0].lower().startswith("rider"):
            name = cells[0]
            team = cells[1] if len(cells) > 1 else None
            if re.search(r"[A-Za-z]", name):
                riders.append({"name": name, "team": team})
    return riders[:40]


def scrape_results(stage_number):
    """Obtiene top-3 y el líder de la general (maillot amarillo) de una etapa.

    URL: /tour-de-france-2026-results/stage-N-results-tdf-2026/

    La página publica los resultados como encabezados <h2> seguidos de un <p>
    con líneas «N. Nombre (país) tiempo» separadas por <br>. Hay dos secciones
    útiles: «Stage N Results» (podio) y «GC after stage N» (líder general).
    Las clasificaciones de verde/montaña/blanco NO se publican como lista, así
    que se dejan en None para carga manual desde el panel de administración.

    Devuelve dict o None si no encuentra al ganador.
    """
    url = f"{BASE}/tour-de-france-2026-results/stage-{stage_number}-results-tdf-2026/"
    try:
        soup = _get_soup(url)
    except Exception as exc:  # noqa: BLE001
        print(f"[scraper] No se pudo obtener resultados etapa {stage_number}: {exc}")
        return None

    result = {
        "first_rider": None, "second_rider": None, "third_rider": None,
        "yellow_rider": None, "green_rider": None,
        "polka_rider": None, "white_rider": None,
    }

    # Podio de la etapa: sección «Stage N Results».
    podium = _riders_after_heading(soup, rf"stage\s*0*{stage_number}\b.*result")
    if len(podium) >= 1:
        result["first_rider"] = podium[0]
    if len(podium) >= 2:
        result["second_rider"] = podium[1]
    if len(podium) >= 3:
        result["third_rider"] = podium[2]

    # Maillot amarillo = líder de la general: sección «GC after stage N».
    gc = _riders_after_heading(
        soup, rf"(?:gc|general\s+classification)\s*after\s*stage\s*0*{stage_number}\b")
    if not gc:
        gc = _riders_after_heading(soup, r"gc\s+after\s+stage")
    if gc:
        result["yellow_rider"] = gc[0]

    # Maillots verde y montaña: páginas de clasificación dedicadas.
    result["green_rider"] = _classification_leader_backfill(
        f"{BASE}/tour-de-france-2026-points-classification/"
        "stage-{n}-green-jersey-tdf-2026/",
        r"points\s+classification", stage_number)
    result["polka_rider"] = _classification_leader_backfill(
        f"{BASE}/tour-de-france-2026-kom-classification/"
        "stage-{n}-polka-dot-tdf-2026/",
        r"mountains?\s+classification", stage_number)
    # El maillot blanco (jóvenes) no se publica como lista -> queda para admin.

    if not result["first_rider"]:
        return None
    return result


def _classification_leader_backfill(url_template, header_pattern, stage_number, max_back=3):
    """Líder actual de una clasificación con arrastre.

    Algunas etapas (p. ej. llanas) no publican su propia página de montaña. Como
    el maillot se arrastra, si la página de la etapa N no existe, se intenta la
    N-1, N-2… (hasta `max_back`) para obtener el líder vigente con nombre completo.
    `url_template` debe contener «{n}» donde va el número de etapa.
    """
    for n in range(stage_number, max(0, stage_number - max_back - 1), -1):
        leader = _classification_leader(url_template.format(n=n), header_pattern)
        if leader:
            return leader
    return None


def _classification_leader(url, header_pattern):
    """Devuelve el líder (1º) de una página de clasificación, o None.

    Las páginas de puntos/montaña listan «N. Nombre  puntos» bajo un <h2> como
    «Points classification - stage N». Tolerante: ante 404 o parseo fallido,
    devuelve None y la app sigue con carga manual.
    """
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        if resp.status_code != 200:
            return None
        soup = BeautifulSoup(resp.text, "html.parser")
    except Exception as exc:  # noqa: BLE001
        print(f"[scraper] No se pudo obtener clasificación {url}: {exc}")
        return None

    rx = re.compile(header_pattern, re.IGNORECASE)
    for heading in soup.find_all(["h2", "h3"]):
        if not rx.search(heading.get_text(" ", strip=True)):
            continue
        p = heading.find_next("p")
        if p is None:
            continue
        for line in p.get_text("\n", strip=True).split("\n"):
            m = re.match(r"^\d+\.\s*(.+)", line.strip())
            if not m:
                continue
            rest = re.split(r"\s*\([a-z]{2,3}\)", m.group(1), maxsplit=1)[0]
            rest = re.sub(r"\s+\d+\s*(?:pts|points)?\.?$", "", rest)  # puntos finales
            rest = re.split(r"\s+(?:\+|s\.t\.|\d+:\d{2})", rest, maxsplit=1)[0]
            name = rest.strip(" .")
            if name and re.search(r"[A-Za-zÀ-ÿ]", name):
                return name
    return None


def _riders_after_heading(soup, pattern):
    """Nombres del <p> que sigue al primer <h2>/<h3> que casa `pattern`."""
    rx = re.compile(pattern, re.IGNORECASE)
    for heading in soup.find_all(["h2", "h3"]):
        if rx.search(heading.get_text(" ", strip=True)):
            p = heading.find_next("p")
            if p is None:
                continue
            names = _parse_result_lines(p.get_text("\n", strip=True))
            if names:
                return names
    return []


def _parse_result_lines(text):
    """De «1. Nombre (ccc) 4:10:45\n2. …» devuelve los nombres en orden."""
    names = []
    for line in text.split("\n"):
        line = line.strip()
        m = re.match(r"^\d+\.\s*(.+)", line)
        if not m:
            continue
        rest = m.group(1)
        # Cortar en el código de país «(ccc)» …
        rest = re.split(r"\s*\([a-z]{2,3}\)", rest, maxsplit=1)[0]
        # … o, si no hubiera país, en el tiempo/«s.t.»/«+».
        rest = re.split(r"\s+(?:\+|s\.t\.|\d+:\d{2})", rest, maxsplit=1)[0]
        name = rest.strip(" .")
        if name and re.search(r"[A-Za-zÀ-ÿ]", name):
            names.append(name)
    return names
