"""Blueprint principal de La Vuelta: dashboard, etapas, detalle, ranking, reglas."""
from flask import (Blueprint, flash, jsonify, redirect, render_template,
                   request, url_for)
from flask_login import current_user, login_required

from tdf.extensions import db

from .jerseys import JERSEYS, stage_type_label
from .models import (JERSEY_KEYS, VueltaPrediction, VueltaRider, VueltaScoring,
                     VueltaStage)
from .scoring import prediction_detail, ranking

bp = Blueprint("vuelta", __name__)

# Campos del resultado que deben estar completos para habilitar la ceremonia.
_RESULT_FIELDS = (("first_rider", "second_rider", "third_rider")
                  + tuple(f"{k}_rider" for k in JERSEY_KEYS))


def active_stage():
    """Primera etapa no terminada (la etapa «del día»)."""
    return (VueltaStage.query.filter_by(is_finished=False)
            .order_by(VueltaStage.number).first())


def ceremony_ready():
    """¿Está la ceremonia final disponible para todos?

    Se habilita cuando no queda ninguna etapa por cerrar y la última tiene su
    podio y los cuatro maillots completos.
    """
    if active_stage() is not None:
        return False
    last = VueltaStage.query.order_by(VueltaStage.number.desc()).first()
    if last is None or not last.is_finished or last.result is None:
        return False
    return all(getattr(last.result, field) for field in _RESULT_FIELDS)


@bp.app_context_processor
def inject_vuelta_globals():
    """Datos que todas las plantillas de La Vuelta necesitan.

    `vuelta_scoring` permite mostrar en pantalla los puntajes vigentes (que el
    admin puede cambiar en cualquier momento) sin pasarlos vista por vista.
    """
    try:
        ready = ceremony_ready()
    except Exception:  # noqa: BLE001 - nunca romper el render por esto
        ready = False
    try:
        scoring_config = VueltaScoring.get()
    except Exception:  # noqa: BLE001
        scoring_config = None
    # Puntos del usuario en La Vuelta: la barra de navegación no puede usar
    # User.total_points, que suma las apuestas del Tour (competencia archivada).
    my_points = 0
    if current_user.is_authenticated:
        try:
            my_points = sum(p.points for p in current_user.vuelta_predictions)
        except Exception:  # noqa: BLE001
            my_points = 0
    return {
        "vuelta_ceremony_ready": ready,
        "vuelta_scoring": scoring_config,
        "my_vuelta_points": my_points,
        "JERSEYS": JERSEYS,
        "JERSEY_KEYS": JERSEY_KEYS,
        "stage_type_label": stage_type_label,
    }


def _riders():
    """Corredores para los desplegables: favoritos primero, luego alfabético."""
    return (VueltaRider.query
            .order_by(VueltaRider.is_favorite.desc(), VueltaRider.name)
            .all())


@bp.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for("vuelta.dashboard"))
    return redirect(url_for("auth.login"))


@bp.route("/dashboard")
@login_required
def dashboard():
    stage = active_stage()
    prediction = None
    if stage:
        prediction = VueltaPrediction.query.filter_by(
            user_id=current_user.id, stage_id=stage.id).first()
    return render_template("vuelta/dashboard.html", stage=stage,
                           riders=_riders(), prediction=prediction,
                           top_ranking=ranking()[:5])


@bp.route("/apostar/<int:stage_id>", methods=["POST"])
@login_required
def vote(stage_id):
    stage = db.session.get(VueltaStage, stage_id)
    if stage is None:
        flash("Esa etapa no existe.", "danger")
        return redirect(url_for("vuelta.dashboard"))

    if not stage.is_open_for_voting():
        flash("Las apuestas de esta etapa están cerradas.", "warning")
        return redirect(url_for("vuelta.dashboard"))

    prediction = VueltaPrediction.query.filter_by(
        user_id=current_user.id, stage_id=stage.id).first()
    if prediction is None:
        prediction = VueltaPrediction(user_id=current_user.id, stage_id=stage.id)
        db.session.add(prediction)

    prediction.pick_winner = request.form.get("pick_winner", "").strip() or None
    for key in JERSEY_KEYS:
        value = request.form.get(f"pick_{key}", "").strip() or None
        setattr(prediction, f"pick_{key}", value)

    if not prediction.pick_winner:
        db.session.rollback()
        flash("Debes elegir al menos el ganador de la etapa.", "danger")
        return redirect(url_for("vuelta.dashboard"))

    db.session.commit()
    flash("¡Apuesta registrada! Puedes cambiarla hasta el cierre.", "success")
    return redirect(url_for("vuelta.dashboard"))


@bp.route("/etapas-pasadas")
@login_required
def past():
    """Etapas ya disputadas, con sus resultados."""
    stages = (VueltaStage.query.filter_by(is_finished=True)
              .order_by(VueltaStage.number.desc()).all())
    return render_template("vuelta/past.html", stages=stages)


@bp.route("/proximas-etapas")
@login_required
def upcoming():
    """Etapas futuras, bloqueadas (las apuestas se abren el día anterior)."""
    active = active_stage()
    query = VueltaStage.query.filter_by(is_finished=False)
    if active:
        query = query.filter(VueltaStage.number > active.number)
    return render_template("vuelta/upcoming.html",
                           stages=query.order_by(VueltaStage.number).all(),
                           active=active)


@bp.route("/etapa/<int:number>")
@login_required
def stage_detail(number):
    stage = VueltaStage.query.filter_by(number=number).first_or_404()
    predictions = [p for p in VueltaPrediction.query.filter_by(stage_id=stage.id)
                   if not p.user.is_blocked]
    predictions.sort(key=lambda p: (-p.points, p.user.username.lower()))

    my_detail = None
    if stage.is_finished and stage.result is not None:
        mine = next((p for p in predictions if p.user_id == current_user.id), None)
        if mine is not None:
            my_detail = prediction_detail(mine, stage.result)

    return render_template("vuelta/stage_detail.html", stage=stage,
                           predictions=predictions, my_detail=my_detail)


@bp.route("/posiciones")
@login_required
def ranking_view():
    return render_template("vuelta/ranking.html", rows=ranking())


@bp.route("/reglas")
@login_required
def rules():
    """Reglas y puntajes vigentes (los define el administrador)."""
    return render_template("vuelta/rules.html")


@bp.route("/estadisticas")
@login_required
def stats_view():
    from .stats import group_records, progression, user_badges, user_stats
    return render_template(
        "vuelta/stats.html",
        stats=user_stats(current_user),
        badges=user_badges(current_user),
        progression=progression(),
        records=group_records(),
    )


def _ceremony_payload():
    """Datos para la animación final: podio + puntos por etapa.

    Reutiliza ranking() (orden y posiciones finales) y stats.progression()
    (acumulado por etapa ya guardado). No re-puntúa nada.
    """
    from .stats import progression

    prog = progression()
    labels = prog["labels"]
    cumulative_by_id = {d["user_id"]: d["data"] for d in prog["datasets"]}

    participants = []
    for row in ranking():
        uid = row["user"].id
        cumulative = cumulative_by_id.get(uid, [0] * len(labels))
        per_stage, previous = [], 0
        for value in cumulative:
            per_stage.append(value - previous)
            previous = value
        participants.append({
            "user_id": uid,
            "username": row["user"].username,
            "total": row["points"],
            "position": row["position"],
            "cumulative": cumulative,
            "perStage": per_stage,
            "isMe": uid == current_user.id,
        })

    podium = [{"position": p["position"], "username": p["username"],
               "points": p["total"], "isMe": p["isMe"]}
              for p in participants[:3]]

    return {"stages": labels, "podium": podium, "participants": participants}


@bp.route("/ceremonia/datos")
@login_required
def ceremony_data():
    """JSON de la ceremonia final.

    Los participantes solo la reciben cuando ceremony_ready() es True; el admin
    puede pedirla siempre (modo previsualización) aunque falten etapas.
    """
    ready = ceremony_ready()
    if not ready and not current_user.is_admin:
        return jsonify({"ready": False, "preview": False}), 200
    payload = _ceremony_payload()
    payload["ready"] = ready
    payload["preview"] = not ready
    return jsonify(payload)
