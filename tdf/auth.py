"""Blueprint de autenticación: registro, login, logout."""
from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from .extensions import db
from .models import User

bp = Blueprint("auth", __name__)


def _apply_admin_email(user):
    """Marca al usuario como admin si su email está en ADMIN_EMAILS."""
    admin_emails = current_app.config.get("ADMIN_EMAILS", [])
    if user.email in admin_emails and not user.is_admin:
        user.is_admin = True
        db.session.commit()


@bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("vuelta.dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        password2 = request.form.get("password2", "")

        errors = []
        if len(username) < 3:
            errors.append("El nombre de usuario debe tener al menos 3 caracteres.")
        if "@" not in email:
            errors.append("Introduce un email válido.")
        if len(password) < 6:
            errors.append("La contraseña debe tener al menos 6 caracteres.")
        if password != password2:
            errors.append("Las contraseñas no coinciden.")
        if User.query.filter_by(username=username).first():
            errors.append("Ese nombre de usuario ya está en uso.")
        if User.query.filter_by(email=email).first():
            errors.append("Ese email ya está registrado.")

        if errors:
            for e in errors:
                flash(e, "danger")
            return render_template("auth/register.html", username=username, email=email)

        user = User(username=username, email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        _apply_admin_email(user)
        login_user(user)
        flash(f"¡Bienvenido, {username}! Tu cuenta ha sido creada.", "success")
        return redirect(url_for("vuelta.dashboard"))

    return render_template("auth/register.html")


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("vuelta.dashboard"))

    if request.method == "POST":
        identifier = request.form.get("identifier", "").strip()
        password = request.form.get("password", "")
        user = (User.query.filter_by(username=identifier).first()
                or User.query.filter_by(email=identifier.lower()).first())
        if user and user.check_password(password):
            _apply_admin_email(user)
            login_user(user, remember=True)
            flash(f"Sesión iniciada. ¡A por los puntos, {user.username}!", "success")
            next_page = request.args.get("next")
            return redirect(next_page or url_for("vuelta.dashboard"))
        flash("Usuario o contraseña incorrectos.", "danger")

    return render_template("auth/login.html")


@bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Sesión cerrada. ¡Hasta la próxima etapa!", "info")
    return redirect(url_for("auth.login"))
