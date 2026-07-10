"""Utilidades de tiempo ancladas a la zona horaria de Chile.

La app es para usuarios en Chile. En julio (invierno chileno) Chile está en
horario estándar (UTC−4) y Europa en verano (CEST, UTC+2): 6 h de diferencia.
Por eso una etapa que sale ~13:00 en Europa equivale a ~07:00 en Chile.

Todas las comparaciones de "ahora" y los tiempos de cierre de votación usan
`now_local()` para que funcionen correctamente aunque el servidor esté
configurado en otra zona horaria.
"""
from datetime import datetime
from zoneinfo import ZoneInfo

from config import Config

LOCAL_TZ = ZoneInfo(Config.TIMEZONE)


def now_local():
    """Fecha y hora actual en la zona horaria local (Chile), como naive."""
    return datetime.now(LOCAL_TZ).replace(tzinfo=None)
