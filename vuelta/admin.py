"""Blueprint de administración de La Vuelta.

Mantiene todo lo que ya existía para el Tour (forzar actualización de
resultados, editar el resultado de cualquier etapa, ajustar la hora de salida,
reabrir la votación, previsualizar la ceremonia) y añade lo nuevo: configurar
los puntos de cada puesto y de cada maillot, refrescar la lista de inscritos y
entrar al archivo del Tour de France 2026.
"""
from datetime import datetime, timedelta
from functools import wraps

from flask import (Blueprint, abort, flash, redirect, render_template, request,
                   url_for)
from flask_login import current_user, login_required

from tdf.extensions import db

from .models import (VOTING_CLOSE_HOURS_BEFORE, VueltaRider, VueltaScoring,
                     VueltaStage)
from .timeutils import now_local
from .updater import (close_stage_manual, reopen_stage, save_scoring,
                      update_results)

bp = Blueprint("vuelta_admin", __name__, url_prefix="/admin")

# Al reabrir la votación de forma fortuita, se abre durante esta cantidad de horas.
REOPEN_VOTING_HOURS = 1


def admin_required(view):
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if not current_user.is_admin:
            abort(403)
        return view(*args, **kwargs)
    return wrapped


def _active_stage():
    return (VueltaStage.query.filter_by(is_finished=False)
            .order_by(VueltaStage.number).first())


@bp.route("/")
@admin_required
def panel():
    return render_template(
        "vuelta/admin.html",
        stages=VueltaStage.query.order_by(VueltaStage.number).all(),
        riders=VueltaRider.query.order_by(VueltaRider.name).all(),
        active_stage=_active_stage(),
        scoring_fields=VueltaScoring.FIELDS,
    )


@bp.route("/puntajes", methods=["POST"])
@admin_required
def edit_scoring():
    """Guarda los puntos de cada puesto y maillot, y recalcula todo."""
    message, ok = save_scoring(request.form)
    flash(message, "success" if ok else "danger")
    return redirect(url_for("vuelta_admin.panel"))


@bp.route("/actualizar", methods=["POST"])
@admin_required
def force_update():
    try:
        flash(update_results(), "success")
    except Exception as exc:  # noqa: BLE001
        flash(f"Error al actualizar: {exc}", "danger")
    return redirect(url_for("vuelta_admin.panel"))


@bp.route("/inscritos", methods=["POST"])
@admin_required
def refresh_riders():
    """Vuelve a leer la lista de inscritos (bajas y sustituciones)."""
    from .seed import refresh_riders as do_refresh
    try:
        flash(do_refresh(), "success")
    except Exception as exc:  # noqa: BLE001
        flash(f"Error al actualizar la lista de inscritos: {exc}", "danger")
    return redirect(url_for("vuelta_admin.panel"))


@bp.route("/reabrir-votacion", methods=["POST"])
@admin_required
def reopen_voting():
    """Reabre las apuestas de la etapa activa por 1 hora (casos fortuitos).

    Las apuestas cierran VOTING_CLOSE_HOURS_BEFORE antes de start_time, así que
    fijamos start_time = ahora + (1 + cierre) para que el cierre quede a 1 h.
    """
    stage = _active_stage()
    if stage is None:
        flash("No hay ninguna etapa activa para reabrir.", "warning")
        return redirect(url_for("vuelta_admin.panel"))

    stage.start_time = now_local() + timedelta(
        hours=REOPEN_VOTING_HOURS + VOTING_CLOSE_HOURS_BEFORE)
    stage.is_finished = False
    db.session.commit()
    flash(f"Apuestas de la etapa #{stage.number} reabiertas por "
          f"{REOPEN_VOTING_HOURS} h (cierran "
          f"{stage.voting_deadline:%d/%m/%Y %H:%M} h · hora Chile).", "success")
    return redirect(url_for("vuelta_admin.panel"))


@bp.route("/etapa/<int:number>", methods=["POST"])
@admin_required
def edit_stage(number):
    stage = VueltaStage.query.filter_by(number=number).first_or_404()

    if request.form.get("reopen_stage"):
        flash(reopen_stage(stage), "info")
        return redirect(url_for("vuelta_admin.panel"))

    start_time = request.form.get("start_time")
    if start_time:
        try:
            stage.start_time = datetime.fromisoformat(start_time)
            db.session.commit()
        except ValueError:
            flash("Formato de hora inválido.", "danger")
            return redirect(url_for("vuelta_admin.panel"))

    if request.form.get("save_results"):
        flash(close_stage_manual(stage, request.form), "success")
    else:
        flash(f"Etapa #{stage.number} actualizada.", "info")

    return redirect(url_for("vuelta_admin.panel"))
