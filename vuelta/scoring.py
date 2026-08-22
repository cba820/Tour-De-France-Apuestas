"""Cálculo de puntos y ranking de La Vuelta.

Reglas (todas configurables por el administrador en la tabla vuelta_scoring):
- Ganador de etapa: si tu corredor llega 1º, 2º o 3º sumas los puntos definidos
  para ese puesto.
- Cada maillot acertado (quien lo lleva al terminar la etapa) suma los puntos
  definidos para ese maillot.
"""
from tdf.extensions import db
from tdf.scoring import _norm  # comparación sin acentos ni mayúsculas

from .models import JERSEY_KEYS, VueltaPrediction, VueltaScoring, VueltaStage


def score_prediction(prediction, result, config=None):
    """Puntos de una predicción contra el resultado, según la configuración.

    `config` se puede pasar ya cargado para no consultarlo una vez por
    predicción al recalcular etapas completas.
    """
    if result is None:
        return 0
    config = config or VueltaScoring.get()

    points = 0
    pick = _norm(prediction.pick_winner)
    if pick:
        if pick == _norm(result.first_rider):
            points += config.points_first
        elif pick == _norm(result.second_rider):
            points += config.points_second
        elif pick == _norm(result.third_rider):
            points += config.points_third

    for key in JERSEY_KEYS:
        guess = getattr(prediction, f"pick_{key}", None)
        actual = getattr(result, f"{key}_rider", None)
        if guess and actual and _norm(guess) == _norm(actual):
            points += config.jersey_points(key)

    return points


def prediction_detail(prediction, result, config=None):
    """Desglose legible de los puntos de una predicción.

    Devuelve una lista de dicts {label, icon, pick, actual, hit, points} para
    pintar el detalle en pantalla y explicar de dónde salió cada punto.
    """
    config = config or VueltaScoring.get()
    rows = []

    pick = _norm(prediction.pick_winner)
    place, earned = None, 0
    if pick:
        if pick == _norm(result.first_rider if result else None):
            place, earned = "1º", config.points_first
        elif pick == _norm(result.second_rider if result else None):
            place, earned = "2º", config.points_second
        elif pick == _norm(result.third_rider if result else None):
            place, earned = "3º", config.points_third
    rows.append({
        "label": "Ganador de la etapa", "icon": "🏆",
        "pick": prediction.pick_winner, "actual": result.first_rider if result else None,
        "hit": place is not None, "place": place, "points": earned,
    })

    from .jerseys import JERSEYS
    for key in JERSEY_KEYS:
        guess = getattr(prediction, f"pick_{key}", None)
        actual = getattr(result, f"{key}_rider", None) if result else None
        hit = bool(guess and actual and _norm(guess) == _norm(actual))
        rows.append({
            "label": f"{JERSEYS[key]['name']} · {JERSEYS[key]['what']}",
            "icon": JERSEYS[key]["emoji"], "pick": guess, "actual": actual,
            "hit": hit, "place": None,
            "points": config.jersey_points(key) if hit else 0,
        })
    return rows


def recompute_stage_points(stage, config=None):
    """Recalcula los puntos de todas las predicciones de una etapa."""
    config = config or VueltaScoring.get()
    result = stage.result
    for prediction in stage.predictions:
        prediction.points = score_prediction(prediction, result, config)
    db.session.commit()


def recompute_all_points():
    """Recalcula los puntos de todas las etapas terminadas.

    Se llama tras cerrar una etapa y también al cambiar los puntajes desde el
    panel de administración, para que el cambio se aplique retroactivamente.
    """
    config = VueltaScoring.get()
    for stage in VueltaStage.query.filter_by(is_finished=True).all():
        recompute_stage_points(stage, config)


def ranking():
    """Usuarios ordenados por puntos de La Vuelta (desc), con posición y empates."""
    from tdf.models import User

    preds = VueltaPrediction.query.all()
    finished_ids = {s.id for s in
                    VueltaStage.query.filter_by(is_finished=True).all()}

    by_user = {}
    for pred in preds:
        agg = by_user.setdefault(pred.user_id, {"points": 0, "played": 0})
        agg["points"] += pred.points
        if pred.stage_id in finished_ids:
            agg["played"] += 1

    rows = []
    for user in User.query.all():
        agg = by_user.get(user.id, {"points": 0, "played": 0})
        rows.append({"user": user, "points": agg["points"],
                     "played": agg["played"]})

    rows.sort(key=lambda r: (-r["points"], r["user"].username.lower()))
    position, last_points = 0, None
    for i, row in enumerate(rows):
        if row["points"] != last_points:
            position = i + 1
            last_points = row["points"]
        row["position"] = position
    return rows


def user_points(user):
    """Puntos totales de un usuario en La Vuelta."""
    return sum(p.points for p in user.vuelta_predictions)
