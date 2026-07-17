"""Estadísticas personales, progresión del ranking e insignias.

Todo se deriva de datos ya guardados (predicciones, resultados, puntos), así que
no requiere cambios en la base de datos. Los aciertos se calculan comparando
nombres con scoring._norm (no se pueden inferir de Prediction.points, porque el
bono de maillots se confunde con el del podio).
"""
from collections import Counter

from .models import Prediction, Stage, User
from .scoring import _norm, ranking


def _finished_preds(user):
    """Lista de (prediction, result) del usuario en etapas ya finalizadas."""
    out = []
    for p in user.predictions:
        if p.stage.is_finished and p.stage.result is not None:
            out.append((p, p.stage.result))
    return out


def _jersey_breakdown(user):
    """Cuenta de maillots acertados por color y total, en etapas finalizadas."""
    counts = {"yellow": 0, "green": 0, "polka": 0, "white": 0}
    for pred, result in _finished_preds(user):
        pairs = [
            ("yellow", pred.pick_yellow, result.yellow_rider),
            ("green", pred.pick_green, result.green_rider),
            ("polka", pred.pick_polka, result.polka_rider),
            ("white", pred.pick_white, result.white_rider),
        ]
        for key, guess, actual in pairs:
            if guess and actual and _norm(guess) == _norm(actual):
                counts[key] += 1
    counts["total"] = sum(counts.values())
    return counts


def _jersey_hits(user):
    """Total de maillots acertados en etapas finalizadas."""
    return _jersey_breakdown(user)["total"]


def _current_streak(user):
    """Racha actual: etapas finalizadas consecutivas (de la más reciente hacia
    atrás) en las que el usuario votó y sumó puntos. Se corta en la primera
    etapa finalizada sin predicción o con 0 puntos."""
    finished = (Stage.query.filter_by(is_finished=True)
                .order_by(Stage.number.desc()).all())
    by_stage = {p.stage_id: p for p in user.predictions}
    streak = 0
    for stage in finished:
        pred = by_stage.get(stage.id)
        if pred is not None and pred.points > 0:
            streak += 1
        else:
            break
    return streak


def _exact_winners(user):
    """Nº de veces que acertó el ganador exacto (1º) de la etapa."""
    n = 0
    for pred, result in _finished_preds(user):
        if pred.pick_winner and _norm(pred.pick_winner) == _norm(result.first_rider):
            n += 1
    return n


def _podiums(user):
    """Nº de veces que su ganador terminó en el podio (1º/2º/3º)."""
    n = 0
    for pred, result in _finished_preds(user):
        if not pred.pick_winner:
            continue
        pick = _norm(pred.pick_winner)
        if pick in (_norm(result.first_rider), _norm(result.second_rider),
                    _norm(result.third_rider)):
            n += 1
    return n


def _ranking_row(user):
    """Fila de ranking() correspondiente al usuario (o None)."""
    for row in ranking():
        if row["user"].id == user.id:
            return row
    return None


def user_stats(user):
    """Diccionario con las estadísticas personales del usuario."""
    preds = _finished_preds(user)
    played = len(preds)
    row = _ranking_row(user)
    points = row["points"] if row else 0
    position = row["position"] if row else None

    best_stage = max((p.points for p, _ in preds), default=0)
    avg = round(points / played, 2) if played else 0.0

    # Media del grupo: puntos por etapa jugada de todos los participantes.
    rows = ranking()
    total_points = sum(r["points"] for r in rows)
    total_played = sum(r["played"] for r in rows)
    group_avg = round(total_points / total_played, 2) if total_played else 0.0

    jerseys = _jersey_breakdown(user)
    return {
        "points": points,
        "position": position,
        "total_players": len(rows),
        "played": played,
        "exact_winners": _exact_winners(user),
        "podiums": _podiums(user),
        "jersey_hits": jerseys["total"],
        "jersey_breakdown": jerseys,
        "best_stage": best_stage,
        "streak": _current_streak(user),
        "avg": avg,
        "group_avg": group_avg,
    }


def progression():
    """Datos para el gráfico de líneas: puntos acumulados por etapa finalizada.

    Devuelve {labels, datasets}. Usa Prediction.points ya guardados (no re-puntúa)
    y una sola consulta para evitar N+1.
    """
    finished = (Stage.query.filter_by(is_finished=True)
                .order_by(Stage.number).all())
    labels = [s.number for s in finished]
    stage_numbers = labels[:]  # copia para iterar

    users = User.query.order_by(User.username).all()

    # (user_id, stage_number) -> puntos, en una sola pasada.
    preds = (Prediction.query.join(Stage)
             .filter(Stage.is_finished == True).all())  # noqa: E712
    points_map = {}
    for p in preds:
        points_map[(p.user_id, p.stage.number)] = p.points

    datasets = []
    for u in users:
        cum = 0
        data = []
        for num in stage_numbers:
            cum += points_map.get((u.id, num), 0)
            data.append(cum)
        datasets.append({"user_id": u.id, "username": u.username, "data": data})

    return {"labels": labels, "datasets": datasets}


def group_records():
    """Récords del grupo (datos livianos para mostrar en la página de stats)."""
    # Mejor puntaje individual en una sola etapa finalizada.
    best = (Prediction.query.join(Stage)
            .filter(Stage.is_finished == True)  # noqa: E712
            .order_by(Prediction.points.desc()).first())
    best_record = None
    if best and best.points > 0:
        best_record = {
            "username": best.user.username,
            "points": best.points,
            "stage": best.stage.number,
        }

    # Corredor más elegido como ganador de etapa (todas las predicciones).
    winners = [p.pick_winner for p in Prediction.query.all() if p.pick_winner]
    top_pick = None
    if winners:
        name, count = Counter(winners).most_common(1)[0]
        top_pick = {"name": name, "count": count}

    return {"best_record": best_record, "top_pick": top_pick}


def user_badges(user):
    """Lista de insignias con estado (ganada o no) para el usuario."""
    stats = user_stats(user)
    jerseys = stats["jersey_breakdown"]
    finished_count = Stage.query.filter_by(is_finished=True).count()

    # Pleno = 7 pts en una etapa (ganador exacto + 4 maillots). El 7 está atado al
    # tope actual de score_prediction (3 + 4); si cambia el scoring, revisar.
    pleno = any(p.points == 7 for p, _ in _finished_preds(user))
    constante = finished_count > 0 and stats["played"] == finished_count
    amarillo = stats["points"] > 0 and stats["position"] == 1

    return [
        {"key": "halcon", "name": "Ojo de halcón", "icon": "🎯",
         "earned": stats["exact_winners"] >= 1,
         "description": "Acierta el ganador exacto de una etapa."},
        {"key": "francotirador", "name": "Francotirador", "icon": "🔫",
         "earned": stats["exact_winners"] >= 3,
         "description": "Acierta el ganador exacto en 3 etapas."},
        {"key": "racha", "name": "En racha", "icon": "🔥",
         "earned": stats["streak"] >= 3,
         "description": "Suma puntos en 3 etapas seguidas."},
        {"key": "pleno", "name": "Pleno", "icon": "💯",
         "earned": pleno,
         "description": "Acierta ganador y los 4 maillots en una misma etapa."},
        {"key": "montana", "name": "Rey de la montaña", "icon": "🔴",
         "earned": jerseys["polka"] >= 3,
         "description": "Acierta el maillot de la montaña 3 veces."},
        {"key": "maillots", "name": "Sabio de maillots", "icon": "🎽",
         "earned": jerseys["total"] >= 5,
         "description": "Acierta 5 maillots en total."},
        {"key": "constante", "name": "Constante", "icon": "📅",
         "earned": constante,
         "description": "Vota en todas las etapas disputadas."},
        {"key": "amarillo", "name": "Maillot amarillo", "icon": "🟡",
         "earned": amarillo,
         "description": "Lidera la clasificación general."},
    ]
