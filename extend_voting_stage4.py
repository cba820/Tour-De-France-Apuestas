"""Extiende la votación de la Etapa 4 sumando 1 hora al start_time.

Como la votación cierra 1h antes del start_time, adelantar el start_time
1 hora más reabre la ventana de votación.

Uso:
    python3 extend_voting_stage4.py
"""
import os
import sqlite3
from datetime import datetime, timedelta

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "instance", "tdf.db")

STAGE_NUMBER = 4
EXTRA_HOURS = 1


def main():
    if not os.path.exists(DB_PATH):
        raise SystemExit(f"No se encontró la DB en: {DB_PATH}")

    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()

        row = cur.execute(
            "SELECT id, start_time, is_finished FROM stages WHERE number = ?",
            (STAGE_NUMBER,),
        ).fetchone()

        if not row:
            raise SystemExit(f"Etapa {STAGE_NUMBER} no encontrada.")

        stage_id, start_time_str, is_finished = row

        if is_finished:
            raise SystemExit(f"La etapa {STAGE_NUMBER} ya está marcada como terminada. No se puede reabrir así.")

        current_start = datetime.fromisoformat(start_time_str)
        new_start = current_start + timedelta(hours=EXTRA_HOURS)

        print(f"Etapa {STAGE_NUMBER} (id={stage_id})")
        print(f"  start_time actual:  {current_start}  → votación cerraba a las {current_start - timedelta(hours=1)}")
        print(f"  start_time nuevo:   {new_start}      → votación cierra ahora a las {new_start - timedelta(hours=1)}")

        cur.execute("UPDATE stages SET start_time = ? WHERE id = ?", (new_start.isoformat(), stage_id))
        conn.commit()
        print("\nListo. Votación reabierta por 1 hora más.")

    finally:
        conn.close()


if __name__ == "__main__":
    main()
