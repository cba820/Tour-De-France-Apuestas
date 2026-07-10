"""Cierra UNA etapa automáticamente: scrapea los resultados y recalcula puntos.

Solo tienes que cambiar STAGE_NUMBER. El script:
  1. Descarga la página de resultados de cyclingstage.com de esa etapa.
  2. Extrae el podio (1º/2º/3º) y el maillot amarillo (líder de la general).
  3. Inserta/actualiza el StageResult, marca la etapa como terminada y
     recalcula los puntos de todas las predicciones de esa etapa.

IDEMPOTENTE: puedes correrlo las veces que quieras. Si el resultado ya existe
lo ACTUALIZA (no duplica) y vuelve a recalcular los puntos.

SEGURO PARA PRODUCCIÓN: solo toca `stages`, `stage_results` y `predictions`.
No toca `users` ni `riders`. Usa sqlite3 directo (no arranca Flask ni scheduler).

Nota: verde/montaña/blanco NO se publican como lista en la página de la etapa,
así que no se scrapean. Si quieres que cuenten, rellénalos en MANUAL_JERSEYS.

Uso:
    cp instance/tdf.db instance/tdf.db.bak
    python3 auto_update_stage.py
"""
import os
import re
import sqlite3
import unicodedata

import requests
from bs4 import BeautifulSoup

# ── EDITA AQUÍ ────────────────────────────────────────────────────────────────
STAGE_NUMBER = 5

# El verde (puntos) y la montaña (lunares) se scrapean solos de sus páginas de
# clasificación. El blanco (jóvenes) NO se publica en la web: ponlo aquí a mano
# si lo sabes, o déjalo en None para que no otorgue puntos.
MANUAL_JERSEYS = {
    "white_rider":  None,   # maillot blanco (joven) — no está en la web
}
# ─────────────────────────────────────────────────────────────────────────────

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "instance", "tdf.db")
BASE = "https://www.cyclingstage.com"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}


# ── Normalización (idéntica a scoring._norm: strip + lower + sin acentos) ──────
def norm(name):
    text = (name or "").strip().lower()
    d = unicodedata.normalize("NFKD", text)
    return "".join(c for c in d if not unicodedata.combining(c))


# ── Scraping ──────────────────────────────────────────────────────────────────
def _parse_result_lines(text):
    """De «1. Nombre (ccc) 4:10:45\n2. …» devuelve los nombres en orden."""
    names = []
    for line in text.split("\n"):
        line = line.strip()
        m = re.match(r"^\d+\.\s*(.+)", line)
        if not m:
            continue
        rest = re.split(r"\s*\([a-z]{2,3}\)", m.group(1), maxsplit=1)[0]
        rest = re.split(r"\s+(?:\+|s\.t\.|\d+:\d{2})", rest, maxsplit=1)[0]
        name = rest.strip(" .")
        if name and re.search(r"[A-Za-zÀ-ÿ]", name):
            names.append(name)
    return names


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


def _classification_leader(url, header_pattern):
    """Líder (1º) de una página de clasificación (puntos/montaña), o None.

    Tolerante: ante 404 o parseo fallido devuelve None (queda para carga manual).
    """
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        if resp.status_code != 200:
            return None
        soup = BeautifulSoup(resp.text, "html.parser")
    except Exception:  # noqa: BLE001
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
            rest = re.sub(r"\s+\d+\s*(?:pts|points)?\.?$", "", rest)
            rest = re.split(r"\s+(?:\+|s\.t\.|\d+:\d{2})", rest, maxsplit=1)[0]
            name = rest.strip(" .")
            if name and re.search(r"[A-Za-zÀ-ÿ]", name):
                return name
    return None


def scrape_results(stage_number):
    """Devuelve dict con podio + amarillo, o None si no encuentra al ganador."""
    url = f"{BASE}/tour-de-france-2026-results/stage-{stage_number}-results-tdf-2026/"
    resp = requests.get(url, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    result = {k: None for k in (
        "first_rider", "second_rider", "third_rider",
        "yellow_rider", "green_rider", "polka_rider", "white_rider")}

    podium = _riders_after_heading(soup, rf"stage\s*0*{stage_number}\b.*result")
    if len(podium) >= 1:
        result["first_rider"] = podium[0]
    if len(podium) >= 2:
        result["second_rider"] = podium[1]
    if len(podium) >= 3:
        result["third_rider"] = podium[2]

    gc = _riders_after_heading(
        soup, rf"(?:gc|general\s+classification)\s*after\s*stage\s*0*{stage_number}\b")
    if not gc:
        gc = _riders_after_heading(soup, r"gc\s+after\s+stage")
    if gc:
        result["yellow_rider"] = gc[0]

    # Verde y montaña: páginas de clasificación dedicadas.
    result["green_rider"] = _classification_leader(
        f"{BASE}/tour-de-france-2026-points-classification/"
        f"stage-{stage_number}-green-jersey-tdf-2026/",
        r"points\s+classification")
    result["polka_rider"] = _classification_leader(
        f"{BASE}/tour-de-france-2026-kom-classification/"
        f"stage-{stage_number}-polka-dot-tdf-2026/",
        r"mountains?\s+classification")

    # Blanco (y cualquier override manual): solo si se indicó a mano.
    for k, v in MANUAL_JERSEYS.items():
        if v:
            result[k] = v

    if not result["first_rider"]:
        return None
    return result


# ── Puntuación ────────────────────────────────────────────────────────────────
def score_prediction(res, pick_winner, pick_yellow, pick_green, pick_polka, pick_white):
    points = 0
    pw = norm(pick_winner)
    if pw:
        if pw == norm(res["first_rider"]):
            points += 3
        elif pw == norm(res["second_rider"]):
            points += 2
        elif pw == norm(res["third_rider"]):
            points += 1
    for guess, key in [
        (pick_yellow, "yellow_rider"), (pick_green, "green_rider"),
        (pick_polka, "polka_rider"), (pick_white, "white_rider"),
    ]:
        if guess and res[key] and norm(guess) == norm(res[key]):
            points += 1
    return points


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    if not os.path.exists(DB_PATH):
        raise SystemExit(f"No se encontró la DB en: {DB_PATH}")

    print(f"Buscando resultados de la etapa {STAGE_NUMBER} en cyclingstage.com…")
    try:
        res = scrape_results(STAGE_NUMBER)
    except Exception as exc:  # noqa: BLE001
        raise SystemExit(f"Error al descargar/parsear la página: {exc}")

    if not res:
        raise SystemExit(
            f"No se encontraron resultados de la etapa {STAGE_NUMBER} todavía. "
            "Prueba más tarde o cárgalos a mano en el panel admin.")

    print("\nResultados detectados:")
    for label, key in [("1º", "first_rider"), ("2º", "second_rider"), ("3º", "third_rider"),
                       ("Amarillo", "yellow_rider"), ("Verde", "green_rider"),
                       ("Montaña", "polka_rider"), ("Blanco", "white_rider")]:
        print(f"  {label:>9}: {res[key] or '—'}")

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.cursor()
        stage = cur.execute(
            "SELECT id FROM stages WHERE number = ?", (STAGE_NUMBER,)).fetchone()
        if not stage:
            raise SystemExit(f"Etapa {STAGE_NUMBER} no encontrada en la DB.")
        stage_id = stage["id"]

        fields = ("first_rider", "second_rider", "third_rider",
                  "yellow_rider", "green_rider", "polka_rider", "white_rider")
        values = [res[f] for f in fields]

        existing = cur.execute(
            "SELECT id FROM stage_results WHERE stage_id = ?", (stage_id,)).fetchone()
        if existing:
            cur.execute(
                f"UPDATE stage_results SET {', '.join(f'{f}=?' for f in fields)} "
                "WHERE stage_id=?", values + [stage_id])
            print("\nStageResult actualizado.")
        else:
            cur.execute(
                f"INSERT INTO stage_results (stage_id, {', '.join(fields)}) "
                f"VALUES ({', '.join(['?'] * (len(fields) + 1))})",
                [stage_id] + values)
            print("\nStageResult insertado.")

        cur.execute("UPDATE stages SET is_finished=1 WHERE id=?", (stage_id,))

        preds = cur.execute(
            "SELECT id, user_id, pick_winner, pick_yellow, pick_green, pick_polka, pick_white "
            "FROM predictions WHERE stage_id=?", (stage_id,)).fetchall()
        print(f"Recalculando {len(preds)} predicción(es)…")
        for p in preds:
            pts = score_prediction(res, p["pick_winner"], p["pick_yellow"],
                                   p["pick_green"], p["pick_polka"], p["pick_white"])
            cur.execute("UPDATE predictions SET points=? WHERE id=?", (pts, p["id"]))

        conn.commit()

        print("\n── Ranking acumulado ──")
        for i, row in enumerate(cur.execute("""
            SELECT u.username, COALESCE(SUM(p.points),0) AS total
            FROM users u LEFT JOIN predictions p ON p.user_id=u.id
            GROUP BY u.id ORDER BY total DESC
        """).fetchall(), 1):
            print(f"  {i}. {row['username']}: {row['total']} pts")
        print("\nListo.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
