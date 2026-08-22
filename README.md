# 🚴 Apuestas La Vuelta a España 2026

Sitio web para apostar quién gana cada etapa de **La Vuelta a España 2026** y quién viste
cada uno de los cuatro maillots, para jugar con amigos. Sin dinero de por medio, solo por
entretención.

La ronda anterior, **Tour de France 2026**, queda **archivada**: sus datos se conservan
intactos y sus pantallas siguen accesibles, pero solo para el administrador
(ver [Archivo del Tour](#archivo-del-tour-de-france-2026)).

## Cómo ejecutar

```bash
pip install -r requirements.txt
python run.py
```

Abre **http://localhost:5000** (accesible también en la red local por la IP del PC).

En el primer arranque se crea/actualiza la base de datos SQLite (`instance/tdf.db`) y se
cargan las 21 etapas de La Vuelta, la lista de inscritos y los puntajes por defecto. Las
tablas nuevas llevan el prefijo `vuelta_`, así que **no hay migración ni pérdida de datos**:
las cuentas de usuario y todo lo del Tour siguen donde estaban.

### Usuario administrador

El administrador es **sebastianorellana820@gmail.com**: cualquier cuenta con ese email se
promueve a admin automáticamente en cada arranque y al iniciar sesión (configurable con la
variable de entorno `ADMIN_EMAILS`, separando por comas).

Además, en una base vacía se crea un admin inicial `admin` / `admin1234` (configurable con
`ADMIN_USERNAME`, `ADMIN_PASSWORD`, `ADMIN_EMAIL`).

## Cómo funciona

- **Horario**: toda la app funciona en **hora de Chile** (`America/Santiago`). Las etapas de
  La Vuelta salen ~13:00 hora de España; la hora de salida por defecto se calcula convirtiendo
  esa hora europea a hora de Chile **fecha por fecha**, así que el cambio de horario chileno
  del 6 de septiembre se aplica solo (agosto → 07:00 Chile, septiembre → 08:00 Chile). El admin
  puede ajustar cada etapa a mano.
- **Cuentas**: las mismas del Tour. Quien ya jugó entra con su usuario y contraseña de siempre.
- **Apuesta del día**: se **abre el día anterior a las 00:00** y se **cierra 1 hora antes** de
  la salida. Solo la etapa activa (la siguiente no finalizada) es apostable; las futuras
  aparecen bloqueadas. La apuesta se puede cambiar cuantas veces se quiera hasta el cierre.
- **Qué se apuesta**: el **ganador de la etapa** (obligatorio) y quién viste cada uno de los
  cuatro maillots al terminar la etapa (opcional):

  | Maillot | Clasificación |
  |---|---|
  | 🔴 Rojo | General |
  | 🟢 Verde | Puntos |
  | 🔵 Blanco con lunares azules | Montaña |
  | ⚪ Blanco | Mejor joven |

- **Puntos configurables**: el administrador define desde el panel web cuántos puntos vale
  llegar 1º, 2º y 3º, y cuánto vale acertar cada maillot (rango 0–99; `0` desactiva ese premio).
  Los valores por defecto son 3 / 2 / 1 y +1 por maillot. **Al guardar se recalculan todas las
  etapas ya disputadas**, para que la clasificación quede coherente de principio a fin. Los
  puntajes vigentes se muestran siempre en la pestaña **Reglas y puntajes**.
- **Comparación de nombres**: sin distinguir acentos ni mayúsculas, así que «Pogačar» y
  «Pogacar» cuentan igual.
- **Actualización automática**: un poller corre cada 10 minutos y, en cuanto la etapa activa ya
  debería haber terminado (salida + 4,5 h), busca el resultado; al encontrarlo cierra la etapa y
  recalcula puntos y clasificación. El **panel de admin** tiene además un botón «Actualizar
  resultados ahora» y permite cargar o corregir cualquier resultado a mano.
- **Ceremonia final**: al cerrarse la última etapa con el podio y los cuatro maillots completos
  se habilita para todos la animación de cierre (podio + fuegos artificiales + evolución de
  puntos etapa a etapa). El admin puede previsualizarla antes desde su panel.

### Pantallas

| Pestaña | Ruta | Qué muestra |
|---|---|---|
| Apostar | `/dashboard` | Etapa del día, altimetría, cuenta atrás y formulario de apuesta |
| Etapas pasadas | `/etapas-pasadas` | Resultados oficiales de lo ya disputado |
| Próximas etapas | `/proximas-etapas` | Etapas bloqueadas y cuándo se abren |
| Posiciones | `/posiciones` | Clasificación general de apostadores |
| Estadísticas | `/estadisticas` | Métricas personales, evolución, récords e insignias |
| Reglas y puntajes | `/reglas` | Reglas y los puntajes vigentes |
| Detalle de etapa | `/etapa/<n>` | Resultado, apuestas de todos y desglose de tus puntos |
| Administración | `/admin/` | Puntajes, etapas, resultados, inscritos y archivo del Tour |

## Datos e imágenes

Se usan dos fuentes, cada una para lo que publica de forma más fiable:

- **[cyclingstage.com](https://www.cyclingstage.com/vuelta-2026-route/)** — recorrido de las 21
  etapas (fechas, ciudades, kilómetros, tipo) e imágenes de altimetría desde su CDN. Es la misma
  fuente que ya usaba el Tour.
- **[procyclingstats.com](https://www.procyclingstats.com/race/vuelta-a-espana/2026/startlist)** —
  lista de inscritos y resultados. Su página de etapa trae en pestañas la clasificación de la
  etapa y las cuatro clasificaciones que definen los maillots (general, puntos, montaña,
  jóvenes), que cyclingstage no publica para La Vuelta.

Los nombres de los corredores se reconstruyen combinando el orden que da la URL de
procyclingstats (`rider/primoz-roglic`) con los acentos del texto visible (`ROGLIČ Primož`), de
modo que salga siempre igual —«Primož Roglič»— tanto en el desplegable de la apuesta como en el
resultado, y el acierto se detecte sin ambigüedad.

Todo el scraping es *best effort*: si una web cambia de estructura, la app sigue funcionando con
los datos embebidos en `vuelta/seed.py` y el admin puede cargar los resultados a mano.

## Recordatorios por email

**Desactivados** por configuración (`REMINDERS_ENABLED=0`): el scheduler no programa el envío
diario y el panel de administración no muestra los botones de envío. Para reactivarlos hay que
poner `REMINDERS_ENABLED=1` y configurar `MAIL_USERNAME` / `MAIL_PASSWORD` (App Password de
Gmail de 16 caracteres).

## Archivo del Tour de France 2026

Los datos del Tour —21 etapas, apuestas, resultados y puntos— **no se han tocado**: siguen en
sus tablas originales (`stages`, `predictions`, `stage_results`, `riders`). Sus pantallas se
movieron bajo `/archivo/tdf2026/` y son **visibles solo para administradores**: los
participantes no ven ningún enlace y, si escriben la URL, reciben un 404. Se entra desde el
botón **«Archivo TDF 2026»** del panel de administración de La Vuelta.

El archivo está en modo consulta: cerrar una etapa histórica desde ahí no envía correos.

Para reactivar el Tour el próximo año basta con volver a registrar sus blueprints en la raíz
(`tdf/__init__.py`) y quitar la guarda de administrador.

## Estructura

```
run.py                  Punto de entrada
config.py               Configuración (clave, DB, horarios, admin, puntajes por defecto)
tdf/                    Fábrica de la app + Tour de France 2026 (archivado) + auth compartida
  __init__.py           create_app: registra La Vuelta en la raíz y el Tour bajo /archivo
  auth.py               Registro / login / logout (compartidos)
  extensions.py         db y login_manager
  models.py             User + modelos del Tour
  main.py, admin.py     Pantallas del Tour (archivadas, solo admin)
  scraper.py, scoring.py, seed.py, updater.py, stats.py, mailer.py
vuelta/                 La Vuelta a España 2026 (competencia activa)
  models.py             VueltaStage, VueltaStageResult, VueltaRider,
                        VueltaPrediction, VueltaScoring
  jerseys.py            Definición de los cuatro maillots
  scoring.py            Puntos configurables, desglose y ranking
  scraper.py            cyclingstage (recorrido) + procyclingstats (inscritos y resultados)
  seed.py               Carga inicial y refresco de inscritos
  updater.py            Cierre de etapas, recálculo y guardado de puntajes
  stats.py              Estadísticas, evolución e insignias
  main.py, admin.py     Pantallas de participante y de administración
  timeutils.py          Conversión hora de España → hora de Chile
templates/
  vuelta/               Pantallas de La Vuelta
  auth/                 Login y registro
  *.html                Pantallas archivadas del Tour
static/css/vuelta.css   Estilos de La Vuelta (rojo/granate/oro)
static/css/style.css    Estilos del Tour archivado
static/js/ceremony.js   Ceremonia final (reutilizada por ambas competencias)
instance/tdf.db         Base de datos SQLite (se crea sola)
```

> **Nota**: para que la actualización automática funcione, la app debe estar en ejecución
> (el scheduler corre dentro del proceso de Flask) y con **un solo worker**.
