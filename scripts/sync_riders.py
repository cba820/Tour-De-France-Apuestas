"""Sincroniza la lista de corredores con la start list oficial.

Compara los corredores guardados en la base con la lista de inscritos que
publica procyclingstats y deja la tabla igual que la fuente:

  * **añade** los que falten,
  * **elimina** los que ya no estén,
  * **corrige el equipo** de los que hayan cambiado.

Uso:

    python scripts/sync_riders.py            # muestra el plan, NO toca nada
    python scripts/sync_riders.py --apply    # aplica los cambios

Va en seco por defecto a propósito: opera sobre la base de producción, así que
conviene ver primero qué va a pasar.

Diferencia con el botón «Actualizar inscritos» del panel: ese solo **añade**
(nunca borra, para no quitar un corredor que alguien ya eligió). Este script
sincroniza en los tres sentidos, que es lo que hace falta cuando la organización
publica sustituciones.

Sobre las apuestas ya hechas: eliminar un corredor **no** afecta a las apuestas ni
a los puntos. La elección se guarda como texto en la apuesta, no como referencia
a esta tabla, así que sigue puntuando igual. Lo único que cambia es que ese
nombre deja de aparecer en el desplegable. Aun así, el script avisa cuando un
corredor que va a eliminar aparece en alguna apuesta, para que sea una decisión
informada.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Si la fuente devuelve menos corredores que esto, se asume que el scraping falló
# (web caída, estructura cambiada o IP bloqueada) y se aborta. Sin esta guarda,
# una respuesta vacía se interpretaría como «no queda nadie» y borraría la tabla.
MIN_RIDERS = 100


def build_plan(live, existing):
    """Calcula qué añadir, quitar y qué equipos corregir.

    `live` es la lista de la fuente [{name, team}], `existing` los VueltaRider
    actuales. La comparación es por nombre exacto, que es lo que guarda la app:
    el scraper de resultados genera los nombres con la misma función, así que
    coinciden carácter a carácter.
    """
    live_by_name = {}
    for item in live:
        name = (item.get("name") or "").strip()
        if name:
            live_by_name[name] = (item.get("team") or "").strip() or None

    current_by_name = {rider.name: rider for rider in existing}

    to_add = [(name, team) for name, team in sorted(live_by_name.items())
              if name not in current_by_name]
    to_remove = [rider for name, rider in sorted(current_by_name.items())
                 if name not in live_by_name]
    to_move = [(rider, rider.team, live_by_name[name])
               for name, rider in sorted(current_by_name.items())
               if name in live_by_name and rider.team != live_by_name[name]]
    return to_add, to_remove, to_move


def picks_using(name, predictions, norm):
    """Nº de apuestas que eligieron a este corredor, en cualquier casilla."""
    from vuelta.models import JERSEY_KEYS
    target = norm(name)
    fields = ["pick_winner"] + [f"pick_{key}" for key in JERSEY_KEYS]
    return sum(1 for pred in predictions
               for field in fields
               if norm(getattr(pred, field, None)) == target
               and getattr(pred, field, None))


def main():
    parser = argparse.ArgumentParser(
        description="Sincroniza los corredores con la start list oficial.")
    parser.add_argument("--apply", action="store_true",
                        help="aplica los cambios (sin esto solo los muestra)")
    args = parser.parse_args()

    from tdf import create_app
    from tdf.extensions import db
    from tdf.scoring import _norm
    from vuelta import scraper
    from vuelta.models import VueltaPrediction, VueltaRider
    from vuelta.seed import FAVORITES

    app = create_app(start_scheduler=False)

    print("Sincronización de corredores de La Vuelta 2026")
    print("Leyendo la start list oficial…")
    live = scraper.scrape_startlist()

    if len(live) < MIN_RIDERS:
        print(f"\nABORTADO: la fuente devolvió solo {len(live)} corredores "
              f"(se esperaban al menos {MIN_RIDERS}).")
        print("Probablemente el scraping falló; no se toca la base para no "
              "borrar la lista entera. Vuelve a intentarlo más tarde.")
        return 1

    print(f"  {len(live)} corredores en la fuente.")

    with app.app_context():
        existing = VueltaRider.query.order_by(VueltaRider.name).all()
        print(f"  {len(existing)} corredores en la base.\n")

        to_add, to_remove, to_move = build_plan(live, existing)
        predictions = VueltaPrediction.query.all()
        favorites = {name.lower() for name in FAVORITES}

        print(f"=== AÑADIR ({len(to_add)}) ===")
        for name, team in to_add:
            print(f"  + {name}  ({team or 'sin equipo'})")
        if not to_add:
            print("  (ninguno)")

        print(f"\n=== ELIMINAR ({len(to_remove)}) ===")
        for rider in to_remove:
            used = picks_using(rider.name, predictions, _norm)
            aviso = f"  <- OJO: elegido en {used} apuesta(s)" if used else ""
            print(f"  - {rider.name}  ({rider.team or 'sin equipo'}){aviso}")
        if not to_remove:
            print("  (ninguno)")

        print(f"\n=== CAMBIAR DE EQUIPO ({len(to_move)}) ===")
        for rider, old, new in to_move:
            print(f"  ~ {rider.name}: {old or 'sin equipo'} -> {new or 'sin equipo'}")
        if not to_move:
            print("  (ninguno)")

        total = len(to_add) + len(to_remove) + len(to_move)
        if total == 0:
            print("\nLa lista ya está sincronizada: nada que hacer.")
            return 0

        if not args.apply:
            print(f"\n{total} cambio(s) pendiente(s). No se ha modificado nada.")
            print("Para aplicarlos:  python scripts/sync_riders.py --apply")
            return 0

        for name, team in to_add:
            db.session.add(VueltaRider(name=name, team=team,
                                       is_favorite=name.lower() in favorites))
        for rider in to_remove:
            db.session.delete(rider)
        for rider, _old, new in to_move:
            rider.team = new
        db.session.commit()

        print(f"\nAplicado: {len(to_add)} añadido(s), {len(to_remove)} "
              f"eliminado(s), {len(to_move)} cambio(s) de equipo.")
        print(f"Total de corredores ahora: {VueltaRider.query.count()}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
