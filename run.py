"""Punto de entrada de la aplicación.

Uso:  python run.py
Abre http://localhost:5000
"""
from tdf import create_app

app = create_app()

if __name__ == "__main__":
    # use_reloader=False para no arrancar el scheduler dos veces.
    app.run(host="0.0.0.0", port=5000, debug=True, use_reloader=False)
