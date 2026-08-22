"""Guarda de acceso al archivo del Tour de France 2026.

El Tour está archivado: sus datos se conservan intactos y sus pantallas siguen
existiendo, pero solo para administradores. Los participantes no ven ningún
enlace a ellas; esta guarda evita además que lleguen escribiendo la URL a mano.

Vive en su propio módulo porque la registran `tdf/main.py` y `tdf/admin.py` con
`@bp.before_request` **al importarse**, no dentro de create_app(): Flask prohíbe
llamar métodos de configuración de un blueprint que ya fue registrado, así que
hacerlo en la fábrica rompería cualquier segunda llamada a create_app() en el
mismo proceso (tests, scripts de mantenimiento).
"""
from flask import abort, redirect, url_for
from flask_login import current_user


def archive_guard():
    """Deja pasar solo a los administradores; 404 para el resto."""
    if not current_user.is_authenticated:
        return redirect(url_for("auth.login"))
    if not current_user.is_admin:
        abort(404)
    return None
