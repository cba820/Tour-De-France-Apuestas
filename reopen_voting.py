"""Diagnostica el estado de las etapas y reabre la votación de una etapa.

- Primero IMPRIME el estado real de todas las etapas (hora Chile, cierre, estado)
  y cuál es la etapa "activa" (la que muestra el dashboard).
- Luego fija el cierre de la etapa objetivo a HOURS_OPEN horas DESDE AHORA
  (hora Chile), de modo que la votación quede abierta con seguridad.

Uso:
    python3 reopen_voting.py
"""
import os
import sqlite3
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "instance", "tdf.db")

# ── Config ────────────────────────────────────────────────────────────────────
TARGET_STAGE = 5      # etapa a reabrir
HOURS_OPEN = 0.5        # cuántas horas desde AHORA seguirá abierta la votación
VOTING_CLOSE_HOURS_BEFORE = 1   # igual que en models.py
APPLY = True          # False = solo diagnóstico, no escribe nada
# ─────────────────────────────────────────────────────────────────────────────

LOCAL_TZ = ZoneInfo("America/Santiago")


def now_local():
    return datetime.now(LOCAL_TZ).replace(tzinfo=None)


def parse_dt(s):
    return datetime.fromisoformat(s) if s else None


def main():
    if not os.path.exists(DB_PATH):
        raise SystemExit(f"No se encontró la DB en: {DB_PATH}")

    now = now_local()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.cursor()

        print(f"AHORA (hora Chile): {now}\n")
        print("── Estado de las etapas ──")

        rows = cur.execute(
            "SELECT id, number, date, start_time, is_finished "
            "FROM stages ORDER BY number"
        ).fetchall()

        active_number = None
        for r in rows:
            start = parse_dt(r["start_time"])
            deadline = start - timedelta(hours=VOTING_CLOSE_HOURS_BEFORE) if start else None
            opens = datetime.fromisoformat(r["date"]) - timedelta(days=1) if r["date"] else None

            if r["is_finished"]:
                status = "finished"
            elif opens and now < opens:
                status = "upcoming (bloqueada)"
            elif deadline and now < deadline:
                status = "OPEN ✅"
            else:
                status = "closed (cerrada)"

            if active_number is None and not r["is_finished"]:
                active_number = r["number"]
                status += "  ← ETAPA ACTIVA (dashboard)"

            print(f"  Etapa {r['number']:>2} | start={start} | cierre={deadline} | {status}")

        print(f"\nLa etapa activa (que muestra el dashboard) es la {active_number}.")

        if active_number != TARGET_STAGE:
            print(f"\n⚠  OJO: el dashboard muestra la etapa {active_number}, "
                  f"no la {TARGET_STAGE}.")
            print("   Si la etapa 3 no está marcada como terminada, el dashboard NO")
            print("   mostrará la etapa 4. Revisa el estado de arriba.")

        # ── Reabrir la etapa objetivo ──
        target = cur.execute(
            "SELECT id, number, is_finished, start_time FROM stages WHERE number = ?",
            (TARGET_STAGE,),
        ).fetchone()

        if not target:
            raise SystemExit(f"Etapa {TARGET_STAGE} no encontrada.")
        if target["is_finished"]:
            raise SystemExit(f"La etapa {TARGET_STAGE} está terminada; no se reabre así.")

        new_deadline = now + timedelta(hours=HOURS_OPEN)
        new_start = new_deadline + timedelta(hours=VOTING_CLOSE_HOURS_BEFORE)

        print(f"\n── Reabrir etapa {TARGET_STAGE} ──")
        print(f"  Nuevo cierre de votación: {new_deadline}  (dentro de {HOURS_OPEN} h)")
        print(f"  Nuevo start_time:         {new_start}")

        if APPLY:
            cur.execute(
                "UPDATE stages SET start_time = ? WHERE id = ?",
                (new_start.isoformat(), target["id"]),
            )
            conn.commit()
            print("\n✅ Aplicado. La votación de la etapa "
                  f"{TARGET_STAGE} quedó abierta {HOURS_OPEN} h.")
        else:
            print("\n(APPLY=False — solo diagnóstico, no se escribió nada.)")

    finally:
        conn.close()


if __name__ == "__main__":
    main()
