"""Actualiza los resultados de UNA etapa en producción (manual, seguro).

Reutilizable: cambia STAGE_NUMBER y RESULTS y sirve para cualquier etapa que el
scraper no haya logrado cerrar.

SEGURO PARA PRODUCCIÓN:
- Solo toca `stages` (is_finished), `stage_results` (insert/update) y
  `predictions` (recalcula puntos). No toca `users` ni `riders`.
- Idempotente: si el resultado ya existe, lo ACTUALIZA (no duplica).
- No arranca Flask ni el scheduler; usa sqlite3 directo.

Uso:
    cp instance/tdf.db instance/tdf.db.bak
    python3 update_stage_results.py
"""
import os
import sqlite3
import unicodedata

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "instance", "tdf.db")

# ── EDITA AQUÍ ────────────────────────────────────────────────────────────────
STAGE_NUMBER = 5
RESULTS = {
    "first_rider":  "Olav Kooij",
    "second_rider": "Max Kanter",
    "third_rider":  "Tim Merlier",
    "yellow_rider": "Torstein Træen",     # líder general tras la etapa 5
    "green_rider":  "Mads Pedersen",       # líder por puntos
    "polka_rider":  "Alex Baudin",         # líder montaña
    "white_rider":  "Mathias Vacek",       # mejor joven
}
# Deja un campo en None si no lo sabes (nadie ganará punto por ese maillot):
#   "polka_rider": None,
# ─────────────────────────────────────────────────────────────────────────────


def norm(name):
    """Igual que scoring.py (_norm): strip + lower + sin acentos."""
    text = (name or "").strip().lower()
    d = unicodedata.normalize("NFKD", text)
    return "".join(c for c in d if not unicodedata.combining(c))


def score_prediction(pick_winner, pick_yellow, pick_green, pick_polka, pick_white):
    points = 0
    pw = norm(pick_winner)
    if pw:
        if pw == norm(RESULTS["first_rider"]):
            points += 3
        elif pw == norm(RESULTS["second_rider"]):
            points += 2
        elif pw == norm(RESULTS["third_rider"]):
            points += 1
    for guess, key in [
        (pick_yellow, "yellow_rider"), (pick_green, "green_rider"),
        (pick_polka, "polka_rider"), (pick_white, "white_rider"),
    ]:
        if guess and RESULTS[key] and norm(guess) == norm(RESULTS[key]):
            points += 1
    return points


def main():
    if not os.path.exists(DB_PATH):
        raise SystemExit(f"No se encontró la DB en: {DB_PATH}")

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.cursor()

        stage = cur.execute(
            "SELECT id, is_finished FROM stages WHERE number = ?", (STAGE_NUMBER,)
        ).fetchone()
        if not stage:
            raise SystemExit(f"Etapa {STAGE_NUMBER} no encontrada.")
        stage_id = stage["id"]
        print(f"Etapa {STAGE_NUMBER} (id={stage_id}, finished={bool(stage['is_finished'])})")

        fields = ("first_rider", "second_rider", "third_rider",
                  "yellow_rider", "green_rider", "polka_rider", "white_rider")
        values = [RESULTS[f] for f in fields]

        existing = cur.execute(
            "SELECT id FROM stage_results WHERE stage_id = ?", (stage_id,)
        ).fetchone()
        if existing:
            cur.execute(
                f"UPDATE stage_results SET {', '.join(f'{f}=?' for f in fields)} "
                "WHERE stage_id=?", values + [stage_id],
            )
            print("StageResult actualizado.")
        else:
            cur.execute(
                f"INSERT INTO stage_results (stage_id, {', '.join(fields)}) "
                f"VALUES ({', '.join(['?'] * (len(fields) + 1))})",
                [stage_id] + values,
            )
            print("StageResult insertado.")

        cur.execute("UPDATE stages SET is_finished=1 WHERE id=?", (stage_id,))
        print("Etapa marcada como terminada.")

        preds = cur.execute(
            "SELECT id, user_id, pick_winner, pick_yellow, pick_green, pick_polka, pick_white "
            "FROM predictions WHERE stage_id=?", (stage_id,)
        ).fetchall()
        print(f"\nRecalculando {len(preds)} predicción(es)...")
        for p in preds:
            pts = score_prediction(p["pick_winner"], p["pick_yellow"],
                                   p["pick_green"], p["pick_polka"], p["pick_white"])
            cur.execute("UPDATE predictions SET points=? WHERE id=?", (pts, p["id"]))
            print(f"  user_id={p['user_id']}: {pts} pts (ganador={p['pick_winner']!r})")

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
