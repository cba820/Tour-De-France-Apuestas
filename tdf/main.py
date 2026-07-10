"""Blueprint principal: dashboard, etapas, detalle, ranking y votación."""
from flask import (Blueprint, flash, redirect, render_template,
                   request, url_for)
from flask_login import current_user, login_required

from .extensions import db
from .models import Prediction, Rider, Stage
from .scoring import ranking

bp = Blueprint("main", __name__)


def active_stage():
    """Primera etapa no terminada (la etapa 'del día')."""
    return (Stage.query.filter_by(is_finished=False)
            .order_by(Stage.number).first())


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
