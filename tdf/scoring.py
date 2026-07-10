"""Cálculo de puntos y ranking.

Reglas:
- Ganador de etapa: tu corredor llega 1º -> 3 pts, 2º -> 2 pts, 3º -> 1 pt.
- Cada maillot acertado (líder al terminar la etapa) -> +1 pt (máx 4).
"""
import unicodedata

from .extensions import db
from .models import Prediction, Stage, User


def _norm(name):
    """Normaliza para comparar: sin espacios extra, minúsculas y SIN acentos.

    Necesario porque las fuentes escriben los nombres de forma inconsistente
    (p. ej. «Pogacar» vs «Pogačar», «Traen» vs «Træen»); sin esto, un acierto
    con distinta acentuación puntuaría 0.
    """
    text = (name or "").strip().lower()
    decomposed = unicodedata.normalize("NFKD", text)
    no_accents = "".join(c for c in decomposed if not unicodedata.combining(c))
    return no_accents


def score_prediction(prediction, result):
    """Calcula los puntos de una predicción contra el resultado de la etapa."""
    if result is None:
        return 0

    points = 0
    pick = _norm(prediction.pick_winner)
    if pick:
        if pick == _norm(result.first_rider):
            points += 3
        elif pick == _norm(result.second_rider):
            points += 2
        elif pick == _norm(result.third_rider):
            points += 1

    jersey_pairs = [
        (prediction.pick_yellow, result.yellow_rider),
        (prediction.pick_green, result.green_rider),
        (prediction.pick_polka, result.polka_rider),
        (prediction.pick_white, result.white_rider),
    ]
    for guess, actual in jersey_pairs:
        if guess and actual and _norm(guess) == _norm(actual):
            points += 1

    return points


def recompute_stage_points(stage):
    """Recalcula los puntos de todas las predicciones de una etapa."""
    result = stage.result
    for prediction in stage.predictions:
        prediction.points = score_prediction(prediction, result)
    db.session.commit()


def recompute_all_points():
    """Recalcula los puntos de todas las etapas terminadas."""
    for stage in Stage.query.filter_by(is_finished=True).all():
        recompute_stage_points(stage)


def ranking():
    """Devuelve la lista de usuarios ordenada por puntos totales (desc)."""
    users = User.query.all()
    rows = []
    for user in users:
        preds = [p for p in user.predictions]
        rows.append({
            "user": user,
            "points": sum(p.points for p in preds),
            "played": len([p for p in preds if p.stage.is_finished]),
        })
    rows.sort(key=lambda r: (-r["points"], r["user"].username.lower()))
    # Añadir posición (con empates compartiendo puesto).
    position = 0
    last_points = None
    for i, row in enumerate(rows):
        if row["points"] != last_points:
            position = i + 1
            last_points = row["points"]
        row["position"] = position
    return rows
