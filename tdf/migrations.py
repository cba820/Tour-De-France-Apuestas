"""Migraciones mínimas de esquema.

`db.create_all()` crea tablas que falten, pero **no añade columnas** a tablas que
ya existen. Como la base de producción tiene datos reales (usuarios, apuestas y
puntos del Tour y de La Vuelta), no se puede recrear: hay que hacer el ALTER.

El proyecto no usa Alembic —sería desproporcionado para un SQLite de una app
entre amigos—, así que aquí van los ALTER necesarios, escritos para ser
**idempotentes**: comprueban el estado antes de actuar, así que se pueden
ejecutar en cada arranque sin efecto y sin riesgo.

Se ejecuta desde create_app() antes de los seeders, para que los modelos ya
tengan todas sus columnas cuando alguien consulte.
"""
from sqlalchemy import text

from .extensions import db


def _columns(table):
    """Nombres de las columnas actuales de una tabla SQLite."""
    rows = db.session.execute(text(f'PRAGMA table_info("{table}")')).fetchall()
    return {row[1] for row in rows}


def _add_column(table, column, definition):
    """Añade una columna si no existe. Devuelve True si la añadió."""
    if column in _columns(table):
        return False
    db.session.execute(
        text(f'ALTER TABLE "{table}" ADD COLUMN {column} {definition}'))
    db.session.commit()
    print(f"[migración] {table}.{column} añadida.")
    return True


def run_migrations():
    """Aplica los ALTER pendientes. Seguro de llamar en cada arranque."""
    applied = []

    # Bloqueo de cuentas: permite al administrador cerrar el acceso a una cuenta
    # (p. ej. registros de spam) sin borrarla, conservando su historial.
    # NOT NULL con DEFAULT 0 -> las 12 cuentas existentes quedan desbloqueadas.
    if _add_column("users", "is_blocked",
                   "BOOLEAN NOT NULL DEFAULT 0"):
        applied.append("users.is_blocked")

    return applied
