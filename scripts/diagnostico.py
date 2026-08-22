"""Diagnóstico de la instalación: base de datos y fuentes de scraping.

Pensado para correr en el servidor después de desplegar, y comprobar de un
vistazo que todo quedó bien sin tener que abrir el navegador:

    cd /home/ec2-user/TDF_apuestas && .venv/bin/python scripts/diagnostico.py

No modifica nada: solo lee la base y hace peticiones GET a las fuentes. Es
especialmente útil para detectar si la IP del servidor está bloqueada por
procyclingstats (los datacenters como EC2 a veces lo están): en ese caso el
scraping de resultados cae al respaldo de cyclingstage y los maillots verde,
azul y blanco hay que cargarlos a mano desde el panel.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

OK = "  [OK] "
WARN = "  [!!] "
FAIL = "  [XX] "


def _line(status, text):
    print(status + text)


def check_database():
    print("\n=== BASE DE DATOS ===")
    from tdf import create_app
    from tdf.models import Prediction, Stage, User
    from vuelta.models import (VueltaPrediction, VueltaRider, VueltaScoring,
                               VueltaStage)
    from vuelta.timeutils import now_local

    app = create_app(start_scheduler=False)
    problems = 0
    with app.app_context():
        print(f"  archivo: {app.config['SQLALCHEMY_DATABASE_URI']}")

        users = User.query.count()
        admins = User.query.filter_by(is_admin=True).all()
        _line(OK if users else FAIL, f"usuarios: {users}")
        if not admins:
            _line(FAIL, "no hay ningún administrador")
            problems += 1
        else:
            _line(OK, "administradores: "
                      + ", ".join(f"{u.username} <{u.email}>" for u in admins))

        expected_admins = [e.lower() for e in app.config.get("ADMIN_EMAILS", [])]
        for email in expected_admins:
            user = User.query.filter_by(email=email).first()
            if user is None:
                _line(WARN, f"{email} aún no tiene cuenta creada "
                            "(se promoverá en cuanto se registre)")
            elif not user.is_admin:
                _line(FAIL, f"{email} existe pero NO es admin")
                problems += 1
            else:
                _line(OK, f"{email} es admin")

        # --- La Vuelta (competencia activa) ---
        stages = VueltaStage.query.count()
        riders = VueltaRider.query.count()
        _line(OK if stages == 21 else FAIL, f"La Vuelta · etapas: {stages}/21")
        problems += stages != 21
        _line(OK if riders >= 100 else WARN,
              f"La Vuelta · corredores: {riders}"
              + ("" if riders >= 100 else "  <- pocos; usa «Actualizar inscritos»"))
        _line(OK, f"La Vuelta · apuestas registradas: "
                  f"{VueltaPrediction.query.count()}")

        finished = VueltaStage.query.filter_by(is_finished=True).count()
        _line(OK, f"La Vuelta · etapas cerradas: {finished}")

        config = VueltaScoring.get()
        _line(OK, f"puntajes: 1º={config.points_first} 2º={config.points_second} "
                  f"3º={config.points_third} · maillots "
                  f"rojo={config.points_red} verde={config.points_green} "
                  f"azul={config.points_blue} blanco={config.points_white} "
                  f"· máximo por etapa={config.max_stage_points}")

        # --- Tour de France (archivado): comprobar que sigue intacto ---
        tdf_stages = Stage.query.count()
        tdf_preds = Prediction.query.count()
        tdf_points = sum(p.points for p in Prediction.query.all())
        _line(OK if tdf_stages else WARN,
              f"Archivo TDF · etapas: {tdf_stages} · apuestas: {tdf_preds} "
              f"· puntos: {tdf_points}")

        # Etapas ya disputadas pero sin cerrar: candidatas a carga manual
        now = now_local()
        pending = [s.number for s in VueltaStage.query
                   .filter_by(is_finished=False)
                   .order_by(VueltaStage.number).all()
                   if s.start_time < now]
        if pending:
            _line(WARN, "etapas ya disputadas y aún sin cerrar: "
                        + ", ".join(f"#{n}" for n in pending)
                        + "  <- usa «Actualizar resultados ahora»")
    return problems


def check_sources():
    print("\n=== FUENTES DE SCRAPING ===")
    from vuelta import scraper
    problems = 0

    stages = scraper.scrape_stages()
    _line(OK if len(stages) == 21 else FAIL,
          f"cyclingstage · recorrido: {len(stages)} etapas leídas")
    problems += len(stages) != 21

    startlist = scraper.scrape_startlist()
    if startlist:
        _line(OK, f"procyclingstats · inscritos: {len(startlist)} corredores")
    else:
        _line(WARN, "procyclingstats · inscritos: SIN RESPUESTA "
                    "(se usa el respaldo embebido de vuelta/seed.py)")

    # Resultados: probar con la última etapa que ya debería tener resultado.
    from tdf import create_app
    from vuelta.models import VueltaStage
    app = create_app(start_scheduler=False)
    with app.app_context():
        done = (VueltaStage.query.filter_by(is_finished=True)
                .order_by(VueltaStage.number.desc()).first())
        number = done.number if done else 1

    pcs = scraper._pcs_results(number)
    if pcs:
        jerseys = sum(1 for k in ("red", "green", "blue", "white")
                      if pcs.get(f"{k}_rider"))
        _line(OK, f"procyclingstats · resultados etapa {number}: "
                  f"«{pcs['first_rider']}» + {jerseys}/4 maillots")
    else:
        _line(WARN, f"procyclingstats · resultados etapa {number}: SIN RESPUESTA")
        fallback = scraper._cyclingstage_results(number)
        if fallback:
            _line(WARN, f"  respaldo cyclingstage OK: «{fallback['first_rider']}» "
                        "(solo podio + maillot rojo; los otros 3 a mano)")
        else:
            _line(FAIL, "  el respaldo de cyclingstage tampoco respondió: "
                        "los resultados habrá que cargarlos a mano")
            problems += 1

    image = scraper.profile_image_url(number)
    try:
        import requests
        resp = requests.head(image, headers=scraper.HEADERS, timeout=15)
        _line(OK if resp.status_code == 200 else WARN,
              f"CDN de altimetrías: HTTP {resp.status_code}")
    except Exception as exc:  # noqa: BLE001
        _line(WARN, f"CDN de altimetrías: {exc}")

    return problems


def check_config():
    print("\n=== CONFIGURACIÓN ===")
    from config import Config
    reminders = getattr(Config, "REMINDERS_ENABLED", False)
    _line(OK, f"recordatorios por email: {'ACTIVADOS' if reminders else 'desactivados'}")
    _line(OK, f"zona horaria: {Config.TIMEZONE}")
    _line(OK, f"archivo del Tour en: {Config.ARCHIVE_URL_PREFIX} (solo admins)")
    if Config.SECRET_KEY.startswith("cambia-esta-clave"):
        _line(WARN, "SECRET_KEY es la de por defecto: pon una propia en "
                    "SECRET_KEY del systemd unit")
    else:
        _line(OK, "SECRET_KEY personalizada")
    return 0


def main():
    print("Diagnóstico de Apuestas La Vuelta 2026")
    problems = check_config() + check_database() + check_sources()
    print()
    if problems:
        print(f"TERMINADO CON {problems} PROBLEMA(S). Revisa las líneas [XX].")
    else:
        print("TODO EN ORDEN. Las líneas [!!] son avisos, no fallos.")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
