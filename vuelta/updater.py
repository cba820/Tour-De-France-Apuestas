"""Actualización de resultados de La Vuelta: scraping + recálculo de puntos.

Lo usan el poller del scheduler y el botón «Actualizar resultados» del panel de
administración.
"""
from tdf.extensions import db

from . import scoring, scraper
from .models import VueltaScoring, VueltaStage, VueltaStageResult
from .timeutils import now_local

# Campos del resultado que se copian desde el scraper / el formulario del panel.
RESULT_FIELDS = ("first_rider", "second_rider", "third_rider",
                 "red_rider", "green_rider", "blue_rider", "white_rider")


def update_results():
    """Busca resultados de etapas ya disputadas y sin cerrar; recalcula puntos.

    Devuelve un resumen legible de lo actualizado.
    """
    now = now_local()
    updated = []
    candidates = (VueltaStage.query
                  .filter_by(is_finished=False)
                  .filter(VueltaStage.start_time <= now)
                  .order_by(VueltaStage.number)
                  .all())

    for stage in candidates:
        data = scraper.scrape_results(stage.number)
        if not data or not data.get("first_rider"):
            continue
        result = stage.result or VueltaStageResult(stage=stage)
        for field in RESULT_FIELDS:
            value = data.get(field)
            if value:            # no pisamos con None lo que ya estuviera cargado
                setattr(result, field, value)
        db.session.add(result)
        stage.is_finished = True
        db.session.commit()
        scoring.recompute_stage_points(stage)
        updated.append(stage.number)

    # Recalcular todo por si hubo ediciones manuales o cambios de puntaje.
    scoring.recompute_all_points()

    if updated:
        return ("Etapas actualizadas: "
                + ", ".join(f"#{n}" for n in updated) + ".")
    return "No se encontraron nuevos resultados para actualizar."


def close_stage_manual(stage, form):
    """Cierra una etapa con los resultados escritos a mano y recalcula puntos."""
    result = stage.result or VueltaStageResult(stage=stage)
    for field in RESULT_FIELDS:
        setattr(result, field, (form.get(field) or "").strip() or None)
    db.session.add(result)
    stage.is_finished = True
    db.session.commit()
    scoring.recompute_stage_points(stage)
    return f"Etapa #{stage.number} cerrada y puntos recalculados."


def reopen_stage(stage):
    """Vuelve a marcar una etapa como no finalizada (sin borrar su resultado)."""
    stage.is_finished = False
    db.session.commit()
    return (f"Etapa #{stage.number} reabierta. Sus resultados se conservan; "
            f"vuelve a guardarlos para cerrarla de nuevo.")


def save_scoring(form):
    """Guarda los puntajes del panel y recalcula todo retroactivamente.

    Devuelve (mensaje, ok). Los valores se limitan a 0..99 para que un dedazo no
    genere puntajes absurdos; 0 es válido (desactiva ese premio).
    """
    config = VueltaScoring.get()
    errors = []
    for field, label, _icon in VueltaScoring.FIELDS:
        raw = (form.get(field) or "").strip()
        if raw == "":
            continue
        try:
            value = int(raw)
        except ValueError:
            errors.append(f"«{label}»: «{raw}» no es un número entero.")
            continue
        if not 0 <= value <= 99:
            errors.append(f"«{label}»: {value} está fuera del rango 0–99.")
            continue
        setattr(config, field, value)

    if errors:
        db.session.rollback()
        return "No se guardó nada. " + " ".join(errors), False

    db.session.commit()
    scoring.recompute_all_points()
    return ("Puntajes guardados y aplicados a todas las etapas ya disputadas "
            f"(máximo por etapa: {config.max_stage_points} pts)."), True
