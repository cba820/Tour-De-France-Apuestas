"""Blueprint de administración: forzar actualización y editar resultados."""
from functools import wraps

from flask import (Blueprint, abort, flash, redirect, render_template,
                   request, url_for)
from flask_login import current_user, login_required

from .extensions import db
from .models import Stage
from .updater import close_stage_manual, update_results

bp = Blueprint("admin", __name__, url_prefix="/admin")


def admin_required(view):
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if not current_user.is_admin:
            abort(403)
        return view(*args, **kwargs)
    return wrapped


@bp.route("/")
@admin_required
def panel():
    stages = Stage.query.order_by(Stage.number).all()
    return render_template("admin.html", stages=stages)


@bp.route("/update", methods=["POST"])
@admin_required
def force_update():
    try:
        message = update_results(force=True)
        flash(message, "success")
    except Exception as exc:  # noqa: BLE001
        flash(f"Error al actualizar: {exc}", "danger")
    return redirect(url_for("admin.panel"))


@bp.route("/stage/<int:number>", methods=["POST"])
@admin_required
def edit_stage(number):
    stage = Stage.query.filter_by(number=number).first_or_404()

    # Actualizar hora de salida si se proporciona.
    start_time = request.form.get("start_time")
    if start_time:
        from datetime import datetime
        try:
            stage.start_time = datetime.fromisoformat(start_time)
            db.session.commit()
        except ValueError:
            flash("Formato de hora inválido.", "danger")
            return redirect(url_for("admin.panel"))

    # Si se enviaron resultados, cerrar la etapa.
    if request.form.get("save_results"):
        message = close_stage_manual(stage, request.form)
        flash(message, "success")
    else:
        flash(f"Etapa #{stage.number} actualizada.", "info")

    return redirect(url_for("admin.panel"))
