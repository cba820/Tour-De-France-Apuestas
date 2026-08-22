"""Actualización de resultados: scraping + recálculo de puntos.

Usado por el scheduler (job diario) y por el botón del panel de administración.
"""
from .extensions import db
from .models import Stage, StageResult
from .timeutils import now_local
from . import scraper, scoring


def _notify_recap(stage_id):
    """Dispara el correo de resumen de una etapa recién cerrada.

    El envío nunca debe romper el scraping/scoring, así que se aísla en try/except.
    Ambos callers (admin y scheduler) corren dentro de un app/request context, así
    que current_app resuelve correctamente.
    """
    from flask import current_app
    from .mailer import send_stage_recap
    # El Tour está archivado y los correos están desactivados globalmente
    # (Config.REMINDERS_ENABLED): cerrar una etapa histórica desde el panel no
    # debe disparar correos a los participantes.
    if not current_app.config.get("REMINDERS_ENABLED"):
        return
    try:
        send_stage_recap(current_app._get_current_object(), stage_id)
    except Exception as exc:  # noqa: BLE001
        print(f"[recap] Error al enviar resumen de la etapa {stage_id}: {exc}")


def update_results(force=False):
    """Busca resultados de etapas ya disputadas y sin cerrar; recalcula puntos.

    Devuelve un resumen legible de lo actualizado.
    """
    now = now_local()
    updated = []
    candidates = (Stage.query
                  .filter_by(is_finished=False)
                  .filter(Stage.start_time <= now)
                  .order_by(Stage.number)
                  .all())

    for stage in candidates:
        data = scraper.scrape_results(stage.number)
        if not data or not data.get("first_rider"):
            continue
        result = stage.result or StageResult(stage=stage)
        # Guardamos TODO lo que devuelva el scraper: podio + maillots.
        for field in ("first_rider", "second_rider", "third_rider",
                      "yellow_rider", "green_rider", "polka_rider", "white_rider"):
            value = data.get(field)
            if value:                       # no pisamos con None lo ya existente
                setattr(result, field, value)
        db.session.add(result)
        stage.is_finished = True
        db.session.commit()
        scoring.recompute_stage_points(stage)
        updated.append(stage.number)
        _notify_recap(stage.id)

    # Recalcular todo por si hubo ediciones manuales.
    scoring.recompute_all_points()

    if updated:
        return f"Etapas actualizadas: {', '.join(f'#{n}' for n in updated)}."
    return "No se encontraron nuevos resultados para actualizar."


def close_stage_manual(stage, result_data):
    """Cierra una etapa con resultados ingresados manualmente y recalcula puntos."""
    result = stage.result or StageResult(stage=stage)
    for field in ("first_rider", "second_rider", "third_rider",
                  "yellow_rider", "green_rider", "polka_rider", "white_rider"):
        setattr(result, field, (result_data.get(field) or "").strip() or None)
    db.session.add(result)
    stage.is_finished = True
    db.session.commit()
    scoring.recompute_stage_points(stage)
    _notify_recap(stage.id)
    return f"Etapa #{stage.number} cerrada y puntos recalculados."
