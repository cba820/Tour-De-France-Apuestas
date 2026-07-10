"""Punto de entrada WSGI para producción (gunicorn).

En el servidor se ejecuta con:
    gunicorn --workers 1 --threads 4 --bind 0.0.0.0:80 wsgi:app

IMPORTANTE: usar SIEMPRE 1 worker. La app tiene un scheduler interno
(APScheduler); con más de un worker se duplicarían las actualizaciones.
"""
from tdf import create_app

app = create_app()
