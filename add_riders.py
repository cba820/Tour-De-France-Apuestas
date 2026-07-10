"""Inserta la startlist completa del Tour de France 2026 en la tabla `riders`.

SEGURO PARA PRODUCCIÓN:
- Solo hace INSERT en la tabla `riders`. No toca `users`, `predictions`,
  `stages` ni `stage_results`.
- Es idempotente: se puede correr varias veces. Salta a los corredores que ya
  existen (comparando sin distinguir mayúsculas ni acentos), así que no crea
  duplicados ni pisa a los favoritos ya cargados.
- No arranca la app ni el scheduler; usa sqlite3 directo.

Uso (desde la carpeta del proyecto):
    python3 add_riders.py

Recomendación: respalda la base antes, por si acaso:
    cp instance/tdf.db instance/tdf.db.bak
"""
import os
import sqlite3
import unicodedata

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "instance", "tdf.db")

# Startlist oficial TdF 2026 (23 equipos, 8 corredores c/u).
STARTLIST = {
    "UAE Team Emirates - XRG": [
        "Tadej Pogačar", "Isaac del Toro", "Brandon McNulty", "Adam Yates",
        "Tim Wellens", "Florian Vermeersch", "Nils Politt", "Felix Großschartner",
    ],
    "Visma | Lease a Bike": [
        "Jonas Vingegaard", "Matteo Jorgenson", "Sepp Kuss", "Victor Campenaerts",
        "Bruno Armirail", "Davide Piganzoli", "Edoardo Affini", "Per Strand Hagenes",
    ],
    "Red Bull - BORA - hansgrohe": [
        "Remco Evenepoel", "Florian Lipowitz", "Mattia Cattaneo", "Maxim Van Gils",
        "Jai Hindley", "Nico Denz", "Jan Tratnik", "Tim van Dijke",
    ],
    "Lidl - Trek": [
        "Juan Ayuso", "Mattias Skjelmose", "Mads Pedersen", "Mathias Vacek",
        "Quinn Simmons", "Derek Gee-West", "Carlos Verona", "Toms Skujins",
    ],
    "Decathlon CMA CGM": [
        "Paul Seixas", "Olav Kooij", "Tiesj Benoot", "Daan Hoole",
        "Matthew Riccitello", "Nicolas Prodhomme", "Aurélien Paret-Peintre", "Cees Bol",
    ],
    "Netcompany INEOS": [
        "Thymen Arensman", "Egan Bernal", "Tobias Foss", "Filippo Ganna",
        "Dorian Godon", "Michał Kwiatkowski", "Joshua Tarling", "Kévin Vauquelin",
    ],
    "Alpecin - Premier Tech": [
        "Jasper Philipsen", "Mathieu van der Poel", "Emiel Verstrynge", "Jonas Rickaert",
        "Tim Marsman", "Ramses Debruyne", "Edward Planckaert", "Silvan Dillier",
    ],
    "Bahrain Victorious": [
        "Antonio Tiberi", "Lenny Martinez", "Matej Mohorič", "Phil Bauhaus",
        "Damiano Caruso", "Kamil Gradek", "Robert Stannard", "Vlad Van Mechelen",
    ],
    "EF Education - EasyPost": [
        "Ben Healy", "Kasper Asgreen", "Richard Carapaz", "Alex Baudin",
        "Sean Quinn", "Georg Steinhauser", "Max Walker", "Michael Valgren",
    ],
    "Groupama - FDJ": [
        "Guillaume Martin", "Romain Grégoire", "Clément Berthet", "Clément Braz Afonso",
        "Lorenzo Germani", "Quentin Pacher", "Clément Russo", "Ewen Costiou",
    ],
    "Team Jayco AlUla": [
        "Michael Matthews", "Luke Plapp", "Pascal Ackermann", "Ben O'Connor",
        "Mauro Schmid", "Felix Engelhardt", "Kelland O'Brien", "Luke Durbridge",
    ],
    "Lotto Intermarché": [
        "Arnaud De Lie", "Lennert Van Eetvelt", "Georg Zimmermann", "Huub Artz",
        "Jenno Berckmoes", "Liam Slock", "Lars Craps", "Baptiste Veistroffer",
    ],
    "Movistar Team": [
        "Cian Uijtdebroeks", "Raúl García Pierna", "Pablo Castrillo", "Einer Rubio",
        "Javier Romo", "Nelson Oliveira", "Jefferson Alveiro Cepeda", "Michel Heßmann",
    ],
    "NSN Cycling": [
        "Biniam Girmay", "Jake Stewart", "Lewis Askey", "Krists Neilands",
        "Marco Frigo", "Matis Louvel", "George Bennett", "Tom Van Asbroeck",
    ],
    "Team Picnic PostNL": [
        "Pavel Bittner", "Warren Barguil", "Frank van den Broek", "Robbe Dhondt",
        "Julius van den Berg", "Niklas Märkl", "Frits Biesterbos", "John Degenkolb",
    ],
    "Soudal Quick-Step": [
        "Valentin Paret-Peintre", "Tim Merlier", "Jasper Stuyven", "Ilan Van Wilder",
        "Louis Vervaeke", "Dylan Van Baarle", "Bert Van Lerberghe", "Pascal Eenkhoorn",
    ],
    "Uno-X Mobility": [
        "Tobias Halland Johannessen", "Magnus Cort", "Jonas Abrahamsen", "Anders Skaarseth",
        "Søren Wærenskjold", "Anthon Charmig", "Torstein Træen", "Andreas Kron",
    ],
    "XDS Astana Team": [
        "Mike Teunissen", "Sergio Higuita", "Harold Tejada", "Max Kanter",
        "Nicolas Vinokurov", "Davide Ballerini", "Aaron Gate", "Simone Velasco",
    ],
    "Cofidis": [
        "Ion Izagirre", "Piet Allegaert", "Jenthe Biermans", "Milan Fretin",
        "Alex Kirsch", "Hugo Page", "Alex Aranburu", "Benjamin Thomas",
    ],
    "Tudor": [
        "Julian Alaphilippe", "Matteo Trentin", "Michael Storer", "Rick Pluimers",
        "Arvid de Kleijn", "Marco Haller", "Marc Hirschi", "Yannis Voisard",
    ],
    "TotalEnergies": [
        "Jordan Jegat", "Alexandre Delettre", "Anthony Turgis", "Mattéo Vercher",
        "Mathis Le Berre", "Nicolas Breuillard", "Joris Delbove", "Thibault Guernalec",
    ],
    "Caja Rural - Seguros RGA": [
        "Alex Molenaar", "Joel Nicolau", "Abel Balderstone", "Sebastian Berwick",
        "Fernando Gaviria", "Stefano Oldani", "Jakub Otruba", "José Félix Parra",
    ],
    "Pinarello Q36.5": [
        "Tom Pidcock", "Xabier Mikel Azparren", "Chris Harper", "Quinten Hermans",
        "Damien Howson", "Xandro Meurisse", "Brent Van Moer", "Fred Wright",
    ],
}


def normalize(name):
    """Minúsculas y sin acentos, para comparar sin crear duplicados."""
    decomposed = unicodedata.normalize("NFKD", name)
    no_accents = "".join(c for c in decomposed if not unicodedata.combining(c))
    return no_accents.strip().lower()


def main():
    if not os.path.exists(DB_PATH):
        raise SystemExit(f"No se encontró la base de datos en: {DB_PATH}")

    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()

        existing = {normalize(row[0]) for row in cur.execute("SELECT name FROM riders")}
        before = cur.execute("SELECT COUNT(*) FROM riders").fetchone()[0]

        added = 0
        for team, riders in STARTLIST.items():
            for name in riders:
                key = normalize(name)
                if key in existing:
                    continue
                cur.execute(
                    "INSERT INTO riders (name, team, is_favorite) VALUES (?, ?, 0)",
                    (name, team),
                )
                existing.add(key)
                added += 1

        conn.commit()
        after = cur.execute("SELECT COUNT(*) FROM riders").fetchone()[0]

        print(f"Corredores en la startlist:   {sum(len(v) for v in STARTLIST.values())}")
        print(f"Corredores antes en la DB:    {before}")
        print(f"Corredores agregados:         {added}")
        print(f"Total corredores ahora:       {after}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
