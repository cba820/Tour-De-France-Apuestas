"""Definición de los cuatro maillots de La Vuelta a España.

Un único sitio con nombre, significado, color y emoji de cada maillot, para que
las plantillas, el desglose de puntos y los correos usen siempre lo mismo.

Ojo con el maillot blanco: hasta 2018 era el de la «combinada»; desde 2019 y en
2026 corresponde al mejor corredor joven de la general.
"""
from collections import OrderedDict

JERSEYS = OrderedDict((
    ("red", {
        "name": "Maillot Rojo",
        "what": "General",
        "color": "#d40f28",
        "text": "#ffffff",
        "emoji": "🔴",
        "field": "red_rider",
        "pick": "pick_red",
    }),
    ("green", {
        "name": "Maillot Verde",
        "what": "Puntos",
        "color": "#12a14b",
        "text": "#ffffff",
        "emoji": "🟢",
        "field": "green_rider",
        "pick": "pick_green",
    }),
    ("blue", {
        "name": "Maillot de Lunares Azules",
        "what": "Montaña",
        "color": "#1d4ed8",
        "text": "#ffffff",
        "emoji": "🔵",
        "field": "blue_rider",
        "pick": "pick_blue",
    }),
    ("white", {
        "name": "Maillot Blanco",
        "what": "Mejor joven",
        "color": "#f8f9fa",
        "text": "#212529",
        "emoji": "⚪",
        "field": "white_rider",
        "pick": "pick_white",
    }),
))

# Etiquetas legibles de los tipos de etapa que publica la fuente de la ruta.
STAGE_TYPES = {
    "flat": "Llana",
    "hills": "Media montaña",
    "mountains": "Montaña",
    "ITT": "Contrarreloj individual",
    "TTT": "Contrarreloj por equipos",
}


def stage_type_label(value):
    return STAGE_TYPES.get(value, value or "—")
