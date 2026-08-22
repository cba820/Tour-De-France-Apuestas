"""Blueprint de administración: forzar actualización y editar resultados."""
from functools import wraps

from flask import (Blueprint, abort, current_app, flash, redirect,
                   render_template, request, url_for)
from flask_login import current_user, login_required

from datetime import timedelta

from .extensions import db
from .models import Rider, Stage, VOTING_CLOSE_HOURS_BEFORE
from .timeutils import now_local
from .updater import close_stage_manual, update_results

bp = Blueprint("admin", __name__, url_prefix="/admin")

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
    """Primera etapa no terminada (misma lógica que main.active_stage)."""
    return (Stage.query.filter_by(is_finished=False)
            .order_by(Stage.number).first())


@bp.route("/")
@admin_required
def panel():
    stages = Stage.query.order_by(Stage.number).all()
    riders = Rider.query.order_by(Rider.name).all()
    return render_template("admin.html", stages=stages, riders=riders,
                           active_stage=_active_stage())


@bp.route("/update", methods=["POST"])
@admin_required
def force_update():
    try:
        message = update_results(force=True)
        flash(message, "success")
    except Exception as exc:  # noqa: BLE001
        flash(f"Error al actualizar: {exc}", "danger")
    return redirect(url_for("admin.panel"))


@bp.route("/send-reminders", methods=["POST"])
@admin_required
def send_reminders():
    """Envía los recordatorios de votación a mano.

    Con test=1 manda el correo solo al admin (y no registra el envío), para poder
    verificar la entregabilidad sin molestar a los participantes.
    """
    if not current_app.config.get("REMINDERS_ENABLED"):
        flash("Los recordatorios por email están desactivados "
              "(REMINDERS_ENABLED=0). No se envió nada.", "warning")
        return redirect(url_for("admin.panel"))

    from .mailer import send_vote_reminders
    test = bool(request.form.get("test"))
    try:
        message = send_vote_reminders(current_app._get_current_object(),
                                      test_only=test)
        flash(message, "success")
    except Exception as exc:  # noqa: BLE001
        flash(f"Error al enviar recordatorios: {exc}", "danger")
    return redirect(url_for("admin.panel"))


@bp.route("/reopen-voting", methods=["POST"])
@admin_required
def reopen_voting():
    """Reabre la votación de la etapa activa por 1 hora (casos fortuitos).

    La votación cierra VOTING_CLOSE_HOURS_BEFORE (1 h) antes de start_time, así que
    fijamos start_time = ahora + 2 h para que el cierre quede a 1 h desde ahora.
    """
    stage = _active_stage()
    if stage is None:
        flash("No hay ninguna etapa activa para reabrir.", "warning")
        return redirect(url_for("admin.panel"))

    now = now_local()
    stage.start_time = now + timedelta(hours=REOPEN_VOTING_HOURS + VOTING_CLOSE_HOURS_BEFORE)
    stage.is_finished = False
    db.session.commit()
    deadline = stage.voting_deadline
    flash(f"Votación de la etapa #{stage.number} reabierta por {REOPEN_VOTING_HOURS} h "
          f"(cierra {deadline:%d/%m/%Y %H:%M} h · hora Chile).", "success")
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
