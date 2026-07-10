# 🚴 Predicciones TDF 2026

Sitio web para predecir los ganadores de cada etapa del **Tour de France 2026** y los
líderes de los 4 maillots, para jugar con amigos. Sin dinero de por medio, solo por diversión.

## Cómo ejecutar

```bash
pip install -r requirements.txt
python run.py
```

Abre **http://localhost:5000** (accesible también en la red local por la IP del PC).

En el primer arranque se crea la base de datos SQLite (`instance/tdf.db`), se cargan las 21
etapas, se marcan las etapas 1 y 2 como finalizadas con sus resultados, y se crea el usuario
administrador.

### Usuario administrador inicial
- Usuario: `admin`
- Contraseña: `admin1234`

(Configurable con las variables de entorno `ADMIN_USERNAME`, `ADMIN_PASSWORD`, `ADMIN_EMAIL`.)

## Cómo funciona

- **Horario**: toda la app funciona en **hora de Chile** (`America/Santiago`). Las etapas del
  Tour salen por la tarde en Europa (~13:00 CEST), lo que equivale a **~07:00 en Chile** (6 h de
  diferencia en julio). La hora de salida por defecto es 07:00 Chile, editable por etapa en admin.
- **Cuentas**: cada amigo se registra con usuario, email y contraseña.
- **Votación del día**: se **habilita el día anterior** a la carrera y se **cierra 1 hora antes**
  de la salida (con salida ~07:00 Chile, el cierre queda ~06:00 Chile). Solo la etapa activa
  (la siguiente no finalizada) es votable; las futuras aparecen bloqueadas.
- **Puntos**:
  - Ganador de etapa: tu corredor llega 1º → **3 pts**, 2º → **2 pts**, 3º → **1 pt**.
  - Cada maillot acertado (amarillo/verde/puntos/blanco) → **+1 pt**.
- **Ranking**: tabla ordenada por puntos totales.
- **Actualización automática**: un job diario a las **15:00 hora de Chile** (las carreras terminan
  ~12:00 Chile) scrapea los resultados de las etapas disputadas y recalcula puntos y ranking. El
  **panel de admin** tiene además un botón "Actualizar resultados ahora" y permite ingresar/corregir
  resultados a mano.

## Datos e imágenes

Los datos de etapas, imágenes de perfil (distancia y desnivel) y favoritos provienen de
`cyclingstage.com` (el sitio oficial letour.fr usa JavaScript y bloquea el scraping). Si el
scraping falla en algún momento, la app sigue funcionando con los datos embebidos y el admin
puede introducir los resultados manualmente.

## Estructura

```
run.py            Punto de entrada
config.py         Configuración (clave, DB, hora del job, admin)
tdf/              Paquete de la app (modelos, blueprints, scraper, scoring, scheduler, seed)
templates/        Vistas Jinja2 + Bootstrap 5
static/css/       Estilos
instance/tdf.db   Base de datos SQLite (se crea sola)
```

> **Nota**: para que la actualización automática funcione, la app debe estar en ejecución
> (el scheduler corre dentro del proceso de Flask).
