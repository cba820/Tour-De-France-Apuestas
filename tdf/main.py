"""Blueprint principal: dashboard, etapas, detalle, ranking y votación."""
from flask import (Blueprint, flash, jsonify, redirect, render_template,
                   request, url_for)
from flask_login import current_user, login_required

from .extensions import db
from .models import Prediction, Rider, Stage
from .scoring import ranking

bp = Blueprint("main", __name__)

# Campos de StageResult que deben estar completos para habilitar la ceremonia.
_RESULT_FIELDS = ("first_rider", "second_rider", "third_rider",
                  "yellow_rider", "green_rider", "polka_rider", "white_rider")


def active_stage():
    """Primera etapa no terminada (la etapa 'del día')."""
    return (Stage.query.filter_by(is_finished=False)
            .order_by(Stage.number).first())


def ceremony_ready():
    """¿Está disponible la ceremonia final para todos?

    Se habilita cuando ya no queda ninguna etapa por cerrar (todas finalizadas)
    y la última etapa tiene su podio y los cuatro maillots completos.
    """
    if active_stage() is not None:
        return False
    last = Stage.query.order_by(Stage.number.desc()).first()
    if last is None or not last.is_finished:
        return False
    result = last.result
    if result is None:
        return False
    return all(getattr(result, f) for f in _RESULT_FIELDS)


@bp.app_context_processor
def inject_ceremony():
    """Expone a todas las plantillas si la ceremonia final ya está disponible."""
    try:
        ready = ceremony_ready()
    except Exception:  # noqa: BLE001 - nunca romper el render por esto
        ready = False
    return {"ceremony_ready": ready}


def _ceremony_payload():
    """Datos para la animación final: podio + matriz de puntos por etapa.

    Reutiliza ranking() (orden y posiciones finales) y stats.progression()
    (puntos acumulados por etapa ya guardados). No re-puntúa nada.
    """
    from .stats import progression

    prog = progression()
    labels = prog["labels"]
    cum_by_id = {d["user_id"]: d["data"] for d in prog["datasets"]}
    rows = ranking()

    participants = []
    for row in rows:
        uid = row["user"].id
        cum = cum_by_id.get(uid, [0] * len(labels))
        per_stage, prev = [], 0
        for value in cum:
            per_stage.append(value - prev)
            prev = value
        participants.append({
            "user_id": uid,
            "username": row["user"].username,
            "total": row["points"],
            "position": row["position"],
            "cumulative": cum,
            "perStage": per_stage,
            "isMe": uid == current_user.id,
        })

    podium = [{
        "position": p["position"],
        "username": p["username"],
        "points": p["total"],
        "isMe": p["isMe"],
    } for p in participants[:3]]

    return {"stages": labels, "podium": podium, "participants": participants}


@bp.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    return redirect(url_for("auth.login"))


@bp.route("/dashboard")
@login_required
def dashboard():
    stage = active_stage()
    riders = Rider.query.order_by(Rider.name).all()
    prediction = None
    if stage:
        prediction = Prediction.query.filter_by(
            user_id=current_user.id, stage_id=stage.id).first()
    top_ranking = ranking()[:5]
    return render_template("dashboard.html", stage=stage, riders=riders,
                           prediction=prediction, top_ranking=top_ranking)


@bp.route("/vote/<int:stage_id>", methods=["POST"])
@login_required
def vote(stage_id):
    stage = Stage.query.get_or_404(stage_id)

    if not stage.is_open_for_voting():
        flash("La votación de esta etapa está cerrada.", "warning")
        return redirect(url_for("main.dashboard"))

    prediction = Prediction.query.filter_by(
        user_id=current_user.id, stage_id=stage.id).first()
    if prediction is None:
        prediction = Prediction(user_id=current_user.id, stage_id=stage.id)
        db.session.add(prediction)

    prediction.pick_winner = request.form.get("pick_winner", "").strip() or None
    prediction.pick_yellow = request.form.get("pick_yellow", "").strip() or None
    prediction.pick_green = request.form.get("pick_green", "").strip() or None
    prediction.pick_polka = request.form.get("pick_polka", "").strip() or None
    prediction.pick_white = request.form.get("pick_white", "").strip() or None

    if not prediction.pick_winner:
        flash("Debes elegir al menos el ganador de la etapa.", "danger")
        return redirect(url_for("main.dashboard"))

    db.session.commit()
    flash("¡Tu predicción ha sido registrada! Puedes cambiarla hasta el cierre.",
          "success")
    return redirect(url_for("main.dashboard"))


@bp.route("/past")
@login_required
def past():
    """Etapas ya disputadas, con sus resultados."""
    stages = (Stage.query.filter_by(is_finished=True)
              .order_by(Stage.number.desc()).all())
    return render_template("past.html", stages=stages)


@bp.route("/upcoming")
@login_required
def upcoming():
    """Etapas futuras, bloqueadas (la votación se habilita el día anterior)."""
    active = active_stage()
    query = Stage.query.filter_by(is_finished=False)
    if active:
        query = query.filter(Stage.number > active.number)
    stages = query.order_by(Stage.number).all()
    return render_template("upcoming.html", stages=stages, active=active)


@bp.route("/stages/<int:number>")
@login_required
def stage_detail(number):
    stage = Stage.query.filter_by(number=number).first_or_404()
    predictions = (Prediction.query.filter_by(stage_id=stage.id)
                   .join(Prediction.user).all())
    predictions.sort(key=lambda p: (-p.points, p.user.username.lower()))
    return render_template("stage_detail.html", stage=stage,
                           predictions=predictions)


@bp.route("/ranking")
@login_required
def ranking_view():
    return render_template("ranking.html", rows=ranking())


@bp.route("/ceremony/data")
@login_required
def ceremony_data():
    """JSON para la ceremonia final.

    Los participantes normales solo la reciben cuando ceremony_ready() es True.
    El admin puede pedirla siempre (modo previsualización) aunque falten etapas.
    """
    ready = ceremony_ready()
    if not ready and not current_user.is_admin:
        return jsonify({"ready": False, "preview": False}), 200
    payload = _ceremony_payload()
    payload["ready"] = ready
    payload["preview"] = not ready  # admin viendo antes de tiempo
    return jsonify(payload)


@bp.route("/stats")
@login_required
def stats_view():
    from .stats import group_records, progression, user_badges, user_stats
    return render_template(
        "stats.html",
        stats=user_stats(current_user),
        badges=user_badges(current_user),
        progression=progression(),
        records=group_records(),
    )
