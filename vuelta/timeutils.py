"""Horas de salida de La Vuelta convertidas a hora de Chile.

La Vuelta 2026 corre entre el 22 de agosto y el 13 de septiembre. En ese lapso
Chile cambia de horario (el 6 de septiembre pasa de UTC−4 a UTC−3), así que la
diferencia con España no es constante: 6 h en agosto y 5 h en septiembre. Para
no tener que corregir etapas a mano, la hora de salida por defecto se calcula
convirtiendo la hora europea real de cada fecha a hora de Chile.
"""
from datetime import datetime
from zoneinfo import ZoneInfo

from config import Config
from tdf.timeutils import LOCAL_TZ, now_local  # noqa: F401  (reexport)

EUROPE_TZ = ZoneInfo(Config.VUELTA_EUROPE_TZ)


def europe_to_local(year, month, day, hour=None, minute=None):
    """Convierte una hora de salida europea a hora de Chile (datetime naive)."""
    hour = Config.VUELTA_EUROPE_START_HOUR if hour is None else hour
    minute = Config.VUELTA_EUROPE_START_MINUTE if minute is None else minute
    european = datetime(year, month, day, hour, minute, tzinfo=EUROPE_TZ)
    return european.astimezone(LOCAL_TZ).replace(tzinfo=None)
