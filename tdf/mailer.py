"""Recordatorios de votación por email.

Envía un correo a los participantes que aún no han votado la etapa cuya votación
está abierta (la etapa "del día siguiente"), recordándoles hacerlo antes del cierre.

El envío es por SMTP (Gmail por defecto) autenticado con una App Password. Toda la
función queda deshabilitada si no hay credenciales configuradas (ver mail_enabled).
"""
import smtplib
from email.message import EmailMessage

from sqlalchemy.exc import IntegrityError

from .extensions import db
from .models import Prediction, ReminderLog, Stage, User
from .timeutils import now_local

# Timeout de la conexión SMTP (segundos). Evita que una conexión colgada congele
# el hilo del scheduler o de una petición del panel de admin.
SMTP_TIMEOUT = 20


def _cfg(cfg, key, default=None):
    """Lee una clave de config tanto de un dict (app.config) como de una clase."""
    if isinstance(cfg, dict):
        return cfg.get(key, default)
    return getattr(cfg, key, default)


def mail_enabled(cfg):
    """True solo si hay usuario y contraseña SMTP configurados."""
    return bool(_cfg(cfg, "MAIL_USERNAME") and _cfg(cfg, "MAIL_PASSWORD"))


def _open_smtp(cfg):
    """Abre y autentica una conexión SMTP lista para enviar."""
    smtp = smtplib.SMTP(_cfg(cfg, "MAIL_SERVER"), _cfg(cfg, "MAIL_PORT"),
                        timeout=SMTP_TIMEOUT)
    if _cfg(cfg, "MAIL_USE_TLS"):
        smtp.starttls()
    smtp.login(_cfg(cfg, "MAIL_USERNAME"), _cfg(cfg, "MAIL_PASSWORD"))
    return smtp


def send_email(smtp, cfg, to, subject, html, text):
    """Envía un correo por la conexión SMTP ya abierta.

    El remitente se fija a MAIL_FROM o, en su defecto, MAIL_USERNAME: Gmail rechaza
    o reescribe remitentes arbitrarios, así que debe coincidir con la cuenta.
    """
    sender = _cfg(cfg, "MAIL_FROM") or _cfg(cfg, "MAIL_USERNAME")
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = to
    msg.set_content(text)
    msg.add_alternative(html, subtype="html")
    smtp.send_message(msg)


def find_reminder_stage(now=None):
    """Primera etapa no finalizada cuya votación está abierta ahora (o None).

    No basta con "la primera no finalizada" (main.active_stage): esa puede ser la
    etapa de hoy, ya cerrada, cuyos resultados aún no se han scrapeado. Buscamos la
    primera cuya ventana de votación está realmente abierta.
    """
    now = now or now_local()
    stages = Stage.query.filter_by(is_finished=False).order_by(Stage.number).all()
    for stage in stages:
        if stage.is_open_for_voting(now):
            return stage
    return None


def users_without_prediction(stage):
    """Usuarios que aún no han registrado una predicción para esa etapa."""
    voted = (db.session.query(Prediction.user_id)
             .filter(Prediction.stage_id == stage.id))
    return (User.query.filter(~User.id.in_(voted))
            .order_by(User.username).all())


def _build_message(stage, cfg):
    """Devuelve (asunto, html, texto) del recordatorio para una etapa."""
    deadline = stage.voting_deadline.strftime("%d/%m/%Y a las %H:%M")
    url = (_cfg(cfg, "SITE_URL") or "").rstrip("/")
    subject = f"🚴 Recuerda votar la Etapa {stage.number} del Tour"
    text = (
        f"¡Hola!\n\n"
        f"Aún no has votado la {stage.title}.\n"
        f"La votación cierra el {deadline} (hora de Chile).\n\n"
        f"Entra a votar: {url}\n\n"
        f"¡Suerte con tus predicciones! 🚴\n"
    )
    html = (
        f"<div style=\"font-family:Arial,Helvetica,sans-serif;font-size:15px;color:#212529\">"
        f"<p>¡Hola!</p>"
        f"<p>Aún no has votado la <strong>{stage.title}</strong>.</p>"
        f"<p>La votación cierra el <strong>{deadline}</strong> (hora de Chile).</p>"
        f"<p><a href=\"{url}\" "
        f"style=\"display:inline-block;padding:10px 18px;background:#ffd60a;"
        f"color:#212529;text-decoration:none;border-radius:6px;font-weight:bold\">"
        f"Entrar a votar</a></p>"
        f"<p style=\"color:#6c757d;font-size:13px\">¡Suerte con tus predicciones! 🚴</p>"
        f"</div>"
    )
    return subject, html, text


def _run_reminders(app, cfg, test_only=False):
    """Lógica de envío (asume que ya estamos dentro de app_context)."""
    if not mail_enabled(cfg):
        return "Recordatorios por email deshabilitados (faltan credenciales SMTP)."

    stage = find_reminder_stage()
    if stage is None:
        return "No hay ninguna etapa con votación abierta; no se envió nada."

    if not test_only and ReminderLog.query.filter_by(stage_id=stage.id).first():
        return (f"El recordatorio de la Etapa {stage.number} ya se había enviado. "
                f"No se reenvió.")

    if test_only:
        recipients = [_cfg(cfg, "MAIL_USERNAME")]
    else:
        recipients = [u.email for u in users_without_prediction(stage)]

    if not recipients:
        return (f"Todos ya votaron la Etapa {stage.number}; no había a quién avisar.")

    subject, html, text = _build_message(stage, cfg)

    sent, failed = 0, []
    smtp = _open_smtp(cfg)
    try:
        for to in recipients:
            try:
                send_email(smtp, cfg, to, subject, html, text)
                sent += 1
            except Exception as exc:  # noqa: BLE001
                failed.append(f"{to} ({exc})")
    finally:
        try:
            smtp.quit()
        except Exception:  # noqa: BLE001
            pass

    # En modo prueba no marcamos la etapa, para que el envío real siga disparándose.
    if not test_only:
        db.session.add(ReminderLog(stage_id=stage.id))
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()  # otra ejecución ya la registró (carrera)

    prefix = "PRUEBA · " if test_only else ""
    msg = f"{prefix}Etapa {stage.number}: {sent} recordatorio(s) enviado(s)."
    if failed:
        msg += f" Fallaron {len(failed)}: {', '.join(failed)}"
    return msg


def send_vote_reminders(app, test_only=False):
    """Punto de entrada: envuelve la lógica en un app_context (para el scheduler)."""
    with app.app_context():
        return _run_reminders(app, app.config, test_only=test_only)
