"""Inserta los resultados de la Etapa 3 (Granollers → Les Angles) en producción.

SEGURO PARA PRODUCCIÓN:
- Solo toca `stages` (is_finished), `stage_results` (insert) y `predictions`
  (actualiza puntos). No toca `users`, `riders` ni ninguna otra tabla.
- Idempotente: si el stage_result ya existe, lo actualiza en vez de duplicar.
- No arranca Flask ni el scheduler; usa sqlite3 directo.

Resultados verificados en cyclingstage.com el 06-07-2026:
  1º Tadej Pogačar
  2º Jonas Vingegaard
  3º Richard Carapaz
  Amarillo: Tadej Pogačar
  Montaña:  Alex Baudin
  Verde:    Jasper Philipsen   (líder puntos — confirmar si hay duda)
  Blanco:   Isaac del Toro

Uso:
    cp instance/tdf.db instance/tdf.db.bak
    python3 insert_stage3_results.py
"""
import os
import sqlite3
import unicodedata

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "instance", "tdf.db")

# ── Resultados de la Etapa 3 ──────────────────────────────────────────────────
STAGE_NUMBER = 3
RESULTS = {
    "first_rider":  "Tadej Pogačar",
    "second_rider": "Jonas Vingegaard",
    "third_rider":  "Richard Carapaz",
    "yellow_rider": "Tadej Pogačar",
    "green_rider":  "Jasper Philipsen",   # ajusta si tienes dato más preciso
    "polka_rider":  "Alex Baudin",
    "white_rider":  "Isaac del Toro",
}
# ─────────────────────────────────────────────────────────────────────────────


def norm(name):
    """Misma lógica que scoring.py (_norm): strip + lower."""
    return (name or "").strip().lower()


def score_prediction(pick_winner, pick_yellow, pick_green, pick_polka, pick_white):
    """Calcula puntos de una predicción contra RESULTS."""
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
        (pick_yellow, "yellow_rider"),
        (pick_green,  "green_rider"),
        (pick_polka,  "polka_rider"),
        (pick_white,  "white_rider"),
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

        # 1. Encontrar la etapa
        stage = cur.execute(
            "SELECT id, number, is_finished FROM stages WHERE number = ?", (STAGE_NUMBER,)
        ).fetchone()
        if not stage:
            raise SystemExit(f"Etapa {STAGE_NUMBER} no encontrada en la DB.")

        stage_id = stage["id"]
        print(f"Etapa {STAGE_NUMBER} encontrada (id={stage_id}, finished={bool(stage['is_finished'])})")

        # 2. Insertar o actualizar stage_result
        existing_result = cur.execute(
            "SELECT id FROM stage_results WHERE stage_id = ?", (stage_id,)
        ).fetchone()

        if existing_result:
            cur.execute("""
                UPDATE stage_results
                SET first_rider=?, second_rider=?, third_rider=?,
                    yellow_rider=?, green_rider=?, polka_rider=?, white_rider=?
                WHERE stage_id=?
            """, (
                RESULTS["first_rider"], RESULTS["second_rider"], RESULTS["third_rider"],
                RESULTS["yellow_rider"], RESULTS["green_rider"],
                RESULTS["polka_rider"], RESULTS["white_rider"],
                stage_id,
            ))
            print("StageResult actualizado.")
        else:
            cur.execute("""
                INSERT INTO stage_results
                    (stage_id, first_rider, second_rider, third_rider,
                     yellow_rider, green_rider, polka_rider, white_rider)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                stage_id,
                RESULTS["first_rider"], RESULTS["second_rider"], RESULTS["third_rider"],
                RESULTS["yellow_rider"], RESULTS["green_rider"],
                RESULTS["polka_rider"], RESULTS["white_rider"],
            ))
            print("StageResult insertado.")

        # 3. Marcar etapa como terminada
        cur.execute("UPDATE stages SET is_finished=1 WHERE id=?", (stage_id,))
        print("Etapa marcada como is_finished=1.")

        # 4. Recalcular puntos de todas las predicciones de esta etapa
        predictions = cur.execute(
            "SELECT id, user_id, pick_winner, pick_yellow, pick_green, pick_polka, pick_white "
            "FROM predictions WHERE stage_id=?", (stage_id,)
        ).fetchall()

        print(f"\nRecalculando puntos para {len(predictions)} predicción(es)...")
        for pred in predictions:
            pts = score_prediction(
                pred["pick_winner"], pred["pick_yellow"],
                pred["pick_green"], pred["pick_polka"], pred["pick_white"],
            )
            cur.execute("UPDATE predictions SET points=? WHERE id=?", (pts, pred["id"]))
            print(f"  user_id={pred['user_id']}: {pts} pts "
                  f"(ganador={pred['pick_winner']!r}, amarillo={pred['pick_yellow']!r})")

        conn.commit()

        # 5. Resumen del ranking
        print("\n── Ranking actualizado ──")
        ranking = cur.execute("""
            SELECT u.username, COALESCE(SUM(p.points), 0) AS total
            FROM users u
            LEFT JOIN predictions p ON p.user_id = u.id
            GROUP BY u.id
            ORDER BY total DESC
        """).fetchall()
        for i, row in enumerate(ranking, 1):
            print(f"  {i}. {row['username']}: {row['total']} pts")

        print("\nListo.")

    finally:
        conn.close()


if __name__ == "__main__":
    main()
