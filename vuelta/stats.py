"""Estadísticas personales, progresión del ranking e insignias de La Vuelta.

Todo se deriva de datos ya guardados (apuestas, resultados y puntos), así que no
requiere columnas nuevas. Los aciertos se cuentan comparando nombres, porque no
se pueden inferir de VueltaPrediction.points: con puntajes configurables, un
mismo total puede venir de combinaciones distintas.
"""
from collections import Counter

from tdf.models import User
from tdf.scoring import _norm

from .jerseys import JERSEYS
from .models import (JERSEY_KEYS, VueltaPrediction, VueltaScoring,
                     VueltaStage)
from .scoring import ranking


def _finished_preds(user):
    """Lista de (prediction, result) del usuario en etapas ya finalizadas."""
    return [(p, p.stage.result) for p in user.vuelta_predictions
            if p.stage.is_finished and p.stage.result is not None]


def _jersey_breakdown(user):
    """Cuenta de maillots acertados por color y total, en etapas finalizadas."""
    counts = {key: 0 for key in JERSEY_KEYS}
    for pred, result in _finished_preds(user):
        for key in JERSEY_KEYS:
            guess = getattr(pred, f"pick_{key}", None)
            actual = getattr(result, f"{key}_rider", None)
            if guess and actual and _norm(guess) == _norm(actual):
                counts[key] += 1
    counts["total"] = sum(counts.values())
    return counts


def _current_streak(user):
    """Etapas finalizadas consecutivas (de la más reciente hacia atrás) en las
    que el usuario votó y sumó puntos. Se corta en la primera sin puntos."""
    finished = (VueltaStage.query.filter_by(is_finished=True)
                .order_by(VueltaStage.number.desc()).all())
    by_stage = {p.stage_id: p for p in user.vuelta_predictions}
    streak = 0
    for stage in finished:
        pred = by_stage.get(stage.id)
        if pred is not None and pred.points > 0:
            streak += 1
        else:
            break
    return streak


def _exact_winners(user):
    """Veces que acertó el ganador exacto (1º) de la etapa."""
    return sum(1 for pred, result in _finished_preds(user)
               if pred.pick_winner
               and _norm(pred.pick_winner) == _norm(result.first_rider))


def _podiums(user):
    """Veces que su elegido terminó en el podio (1º/2º/3º)."""
    total = 0
    for pred, result in _finished_preds(user):
        if not pred.pick_winner:
            continue
        pick = _norm(pred.pick_winner)
        if pick in (_norm(result.first_rider), _norm(result.second_rider),
                    _norm(result.third_rider)):
            total += 1
    return total


def _ranking_row(user, rows=None):
    for row in (rows if rows is not None else ranking()):
        if row["user"].id == user.id:
            return row
    return None


def user_stats(user):
    """Diccionario con las estadísticas personales del usuario."""
    preds = _finished_preds(user)
    played = len(preds)
    rows = ranking()
    row = _ranking_row(user, rows)
    points = row["points"] if row else 0

    total_points = sum(r["points"] for r in rows)
    total_played = sum(r["played"] for r in rows)
    jerseys = _jersey_breakdown(user)

    return {
        "points": points,
        "position": row["position"] if row else None,
        "total_players": len(rows),
        "played": played,
        "exact_winners": _exact_winners(user),
        "podiums": _podiums(user),
        "jersey_hits": jerseys["total"],
        "jersey_breakdown": jerseys,
        "best_stage": max((p.points for p, _ in preds), default=0),
        "streak": _current_streak(user),
        "avg": round(points / played, 2) if played else 0.0,
        "group_avg": round(total_points / total_played, 2) if total_played else 0.0,
    }


def progression():
    """Puntos acumulados por etapa finalizada, para el gráfico de evolución.

    Usa VueltaPrediction.points ya guardados (no re-puntúa) y una sola consulta
    para evitar el problema N+1.
    """
    finished = (VueltaStage.query.filter_by(is_finished=True)
                .order_by(VueltaStage.number).all())
    labels = [s.number for s in finished]
    stage_number = {s.id: s.number for s in finished}

    points_map = {}
    for pred in VueltaPrediction.query.all():
        number = stage_number.get(pred.stage_id)
        if number is not None:
            points_map[(pred.user_id, number)] = pred.points

    datasets = []
    users = (User.query.filter_by(is_blocked=False)
             .order_by(User.username).all())
    for user in users:
        cumulative, data = 0, []
        for number in labels:
            cumulative += points_map.get((user.id, number), 0)
            data.append(cumulative)
        datasets.append({"user_id": user.id, "username": user.username,
                         "data": data})

    return {"labels": labels, "datasets": datasets}


def group_records():
    """Récords del grupo, para mostrar en la página de estadísticas."""
    finished_ids = {s.id for s in
                    VueltaStage.query.filter_by(is_finished=True).all()}
    # Las cuentas bloqueadas no participan: sus apuestas no deben salir en los
    # records ni en el corredor mas elegido.
    blocked_ids = {u.id for u in User.query.filter_by(is_blocked=True).all()}

    best_record, best_points = None, 0
    winners = []
    for pred in VueltaPrediction.query.all():
        if pred.user_id in blocked_ids:
            continue
        if pred.pick_winner:
            winners.append(pred.pick_winner)
        if pred.stage_id in finished_ids and pred.points > best_points:
            best_points = pred.points
            best_record = {"username": pred.user.username,
                           "points": pred.points,
                           "stage": pred.stage.number}

    top_pick = None
    if winners:
        name, count = Counter(winners).most_common(1)[0]
        top_pick = {"name": name, "count": count}

    return {"best_record": best_record, "top_pick": top_pick}


def user_badges(user):
    """Insignias con su estado (conseguida o no) para el usuario."""
    stats = user_stats(user)
    jerseys = stats["jersey_breakdown"]
    finished_count = VueltaStage.query.filter_by(is_finished=True).count()
    config = VueltaScoring.get()

    # El «pleno» se compara con el máximo vigente (ganador exacto + 4 maillots),
    # así la insignia sigue siendo correcta si el admin cambia los puntajes.
    maximum = config.max_stage_points
    pleno = maximum > 0 and any(p.points >= maximum
                                for p, _ in _finished_preds(user))
    constante = finished_count > 0 and stats["played"] == finished_count
    lider = stats["points"] > 0 and stats["position"] == 1

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
         "description": f"Saca el máximo de una etapa ({maximum} pts): "
                        "ganador y los 4 maillots."},
        {"key": "montana", "name": "Rey de la montaña", "icon": "🔵",
         "earned": jerseys["blue"] >= 3,
         "description": f"Acierta el {JERSEYS['blue']['name']} 3 veces."},
        {"key": "maillots", "name": "Sabio de maillots", "icon": "🎽",
         "earned": jerseys["total"] >= 5,
         "description": "Acierta 5 maillots en total."},
        {"key": "constante", "name": "Constante", "icon": "📅",
         "earned": constante,
         "description": "Apuesta en todas las etapas disputadas."},
        {"key": "rojo", "name": "Maillot rojo", "icon": "🔴",
         "earned": lider,
         "description": "Lidera la clasificación general de apostadores."},
    ]
