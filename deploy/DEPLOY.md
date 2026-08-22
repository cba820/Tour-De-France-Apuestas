# Desplegar en AWS EC2 (free tier) — guía paso a paso

Servidor: **Amazon Linux 2023** · usuario **`ec2-user`** · región **us-east-2**.
DNS pública de tu instancia: `ec2-18-221-241-6.us-east-2.compute.amazonaws.com`

> La clave `tdf-key.pem` está en `C:\Users\sorellana\source\repos\TDF_apuestas`.
> Los comandos SSH/scp de abajo asumen que ejecutas PowerShell **dentro de esa carpeta**.
> NUNCA subas ese `.pem` a GitHub (ya está en `.gitignore`).

## 1. La instancia EC2 ya está creada ✅

Solo confirma que el **Security group** de la instancia permite entrada en:
- **SSH** (puerto 22) → *My IP* (solo tú).
- **HTTP** (puerto 80) → *Anywhere* (0.0.0.0/0), para que tus amigos entren.

(EC2 → tu instancia → pestaña *Security* → *Security groups* → *Edit inbound rules*.)

## 2. Conectarte por SSH

Desde PowerShell, en la carpeta del proyecto:

```powershell
ssh -i "tdf-key.pem" ec2-user@ec2-18-221-241-6.us-east-2.compute.amazonaws.com
```

> Si da error de permisos de la clave (`UNPROTECTED PRIVATE KEY FILE`):
> ```powershell
> icacls "tdf-key.pem" /inheritance:r /grant:r "$($env:USERNAME):R"
> ```

## 3. Subir el proyecto y ejecutar la instalación

**Opción A — copiando la carpeta con scp** (desde tu PC, en la carpeta del proyecto):
```powershell
scp -i "tdf-key.pem" -r . ec2-user@ec2-18-221-241-6.us-east-2.compute.amazonaws.com:/home/ec2-user/TDF_apuestas
```
Luego, ya conectado por SSH:
```bash
cd /home/ec2-user/TDF_apuestas
bash deploy/setup.sh
```

**Opción B — con git** (si subes el proyecto a GitHub primero):
```bash
sudo dnf install -y git
git clone <URL-de-tu-repo> TDF_apuestas
cd TDF_apuestas
bash deploy/setup.sh
```

El script `setup.sh` instala Python, crea el entorno virtual, instala las dependencias,
registra el servicio y arranca la app en el puerto 80.

## 4. Poner tus claves secretas

Edita el servicio para cambiar `SECRET_KEY` y `ADMIN_PASSWORD`:
```bash
sudo nano /etc/systemd/system/tdf.service
# cambia los valores Environment=..., guarda (Ctrl+O, Enter, Ctrl+X)
sudo systemctl daemon-reload
sudo systemctl restart tdf
```

## 5. ¡Listo! Entra a la app

Abre en el navegador:
**http://ec2-18-221-241-6.us-east-2.compute.amazonaws.com**

Inicia sesión como admin con el usuario/clave que pusiste, o registra tu cuenta.

---

## URL / dominio gratis

- **Gratis e inmediato**: la DNS pública de arriba (funciona ya).
- **IP estable (recomendado)**: EC2 → **Elastic IPs** → *Allocate* → *Associate* a tu
  instancia. Así la IP no cambia si apagas/enciendes la instancia. (Gratis mientras esté
  asociada a una instancia encendida.)
- **URL bonita y gratis**: crea un subdominio en **DuckDNS** (https://www.duckdns.org, gratis)
  como `predicciones-tdf.duckdns.org` y apúntalo a tu Elastic IP. O usa `sslip.io` sin
  registro: `http://18-221-241-6.sslip.io`.

## HTTPS (opcional pero recomendado, porque hay contraseñas)

Con un dominio (ej. DuckDNS) puedes tener HTTPS automático y gratis con **Caddy**.
En Amazon Linux 2023, instala el binario y déjalo como proxy inverso:
```bash
# 1) Descargar Caddy (amd64)
curl -fsSL "https://caddyserver.com/api/download?os=linux&arch=amd64" -o caddy
sudo mv caddy /usr/bin/caddy && sudo chmod +x /usr/bin/caddy
sudo groupadd --system caddy 2>/dev/null || true
sudo useradd --system --gid caddy --home-dir /var/lib/caddy --shell /usr/sbin/nologin caddy 2>/dev/null || true
```
Cambia gunicorn al puerto 8000 (en `/etc/systemd/system/tdf.service`, pon
`--bind 127.0.0.1:8000`), recarga con `sudo systemctl daemon-reload && sudo systemctl restart tdf`,
y **abre el puerto 443** en el security group. Crea `/etc/caddy/Caddyfile`:
```
predicciones-tdf.duckdns.org {
    reverse_proxy 127.0.0.1:8000
}
```
Ejecuta Caddy como servicio:
```bash
sudo tee /etc/systemd/system/caddy.service >/dev/null <<'EOF'
[Unit]
Description=Caddy
After=network.target
[Service]
User=caddy
Group=caddy
ExecStart=/usr/bin/caddy run --config /etc/caddy/Caddyfile
Restart=always
AmbientCapabilities=CAP_NET_BIND_SERVICE
[Install]
WantedBy=multi-user.target
EOF
sudo systemctl daemon-reload && sudo systemctl enable --now caddy
```
Tendrás `https://predicciones-tdf.duckdns.org` con certificado automático.

---

## Comandos útiles de mantenimiento

```bash
sudo systemctl status tdf        # ver estado
sudo journalctl -u tdf -f        # ver logs en vivo (scheduler, errores)
sudo systemctl restart tdf       # reiniciar la app
```

## Cuidar el free tier / evitar cobros

- Usa **una sola** instancia `t3.micro`/`t2.micro`. El free tier da 750 h/mes (una instancia
  24/7) durante 12 meses.
- Nota: AWS cobra ~USD 3.6/mes por IP pública IPv4, pero el free tier lo cubre el primer año.
- Cuando termine La Vuelta (13 de septiembre), puedes **Stop** o **Terminate** la instancia
  para no gastar nada. (Con *Stop* conservas los datos; con *Terminate* se borra todo, incluidos
  el histórico del Tour y el de La Vuelta.)
- La base de datos SQLite vive en `/home/ec2-user/TDF_apuestas/instance/tdf.db`. Para respaldarla,
  desde tu PC en la carpeta del proyecto:
  ```powershell
  scp -i "tdf-key.pem" ec2-user@ec2-18-221-241-6.us-east-2.compute.amazonaws.com:/home/ec2-user/TDF_apuestas/instance/tdf.db ./backup.db
  ```

---

## Cambio de competencia: del Tour a La Vuelta 2026

El paso a La Vuelta **no necesita migración ni borrar nada**:

1. Las tablas nuevas llevan el prefijo `vuelta_` y las crea `db.create_all()` en el primer
   arranque. Las tablas del Tour (`stages`, `predictions`, `stage_results`, `riders`) y la de
   usuarios (`users`) quedan intactas.
2. En ese primer arranque la app scrapea el recorrido de las 21 etapas y la lista de inscritos,
   así que **el servidor necesita salida a internet** (ya la tiene, la usaba el scraper del Tour).
   Si el scraping falla, arranca igual con los datos embebidos en `vuelta/seed.py`.
3. Las pantallas del Tour pasan a `/archivo/tdf2026/` y solo las ve el administrador.
4. Los **recordatorios por email quedan desactivados** con `REMINDERS_ENABLED=0` en
   `/etc/systemd/system/tdf.service`. Si quieres reactivarlos, pon `REMINDERS_ENABLED=1`,
   completa `MAIL_PASSWORD` con la App Password de Gmail y reinicia el servicio.

Después de desplegar, comprueba en los logs que el seed corrió bien:

```bash
sudo journalctl -u tdf -n 50 --no-pager | grep vuelta
```

Deberías ver `[vuelta/seed] 21 etapas creadas.` y `[vuelta/seed] N corredores cargados.`

> El respaldo automático de la base lo hace el workflow de GitHub Actions antes de cada
> despliegue (`instance/tdf.db.bak`). Aun así, conviene bajarse una copia manual con el `scp`
> de arriba antes del primer despliegue de La Vuelta.

---

## Estado real del servidor (agosto 2026)

La instalación en EC2 no es la de la guía por defecto: hay **Caddy delante**.

```
Internet ──► Caddy (:80 redirige a :443, :443 con HTTPS)
                └──► gunicorn en 127.0.0.1:8000 ──► wsgi:app
```

- El unit `tdf.service` arranca gunicorn con `--bind 127.0.0.1:8000` (no en el :80).
- `/etc/caddy/Caddyfile` define **dos** dominios, ambos hacia `127.0.0.1:8000`:
  - `predicciones-draft-tdf.duckdns.org` — el principal.
  - `<ip-publica>.sslip.io` — respaldo, ver más abajo.
- Caddy no tiene `ExecReload` en su unit, así que para recargar sin cortar:
  ```bash
  sudo caddy reload --config /etc/caddy/Caddyfile
  ```

Consecuencia práctica: para comprobar si la app está viva hay que pedir el
**:8000**. Pedir el `:80` devuelve el 308 de Caddy y da un falso positivo aunque
gunicorn esté caído (el workflow ya lo tiene en cuenta).

## Cuando la instancia cambia de IP pública

Es el fallo que más molesta: al hac*Stop* y *Start*, EC2 asigna una IP nueva y se
rompen tres cosas a la vez.

| Qué se rompe | Cómo se arregla |
|---|---|
| El deploy automático | Actualizar el secret `EC2_HOST` del repo (Settings → Secrets and variables → Actions) |
| La URL pública | Actualizar el registro A en duckdns.org con la IP nueva |
| El enlace de los correos | `SITE_URL` en `/etc/systemd/system/tdf.service` (irrelevante mientras los recordatorios estén apagados) |

**La solución de fondo es una Elastic IP**: AWS Console → EC2 → Elastic IPs →
*Allocate* → *Associate* a la instancia. La IP deja de cambiar y nada de lo
anterior se vuelve a romper. Es gratis mientras esté asociada a una instancia
encendida.

### URL de respaldo sin DuckDNS

`sslip.io` resuelve cualquier IP incrustada en el nombre, sin registro ni tokens:
`18.225.172.13.sslip.io` → `18.225.172.13`. Caddy le emite certificado
automáticamente, así que da HTTPS válido. Sirve para entrar cuando DuckDNS está
caído o no se puede acceder a su panel.

El nombre lleva la IP dentro, así que **cambia si cambia la IP**. Con una Elastic
IP pasa a ser permanente y DuckDNS deja de hacer falta. Para actualizarlo o
quitarlo, edita el bloque en `/etc/caddy/Caddyfile` y recarga con el comando de
arriba. Ten en cuenta que es un servicio gratuito de terceros.

## Comprobar un despliegue

El workflow ya ejecuta el diagnóstico al final y deja la salida en el log de la
Action. A mano:

```bash
cd /home/ec2-user/TDF_apuestas && .venv/bin/python scripts/diagnostico.py
```

Los logs de la app quedan en buffer (el unit no fija `PYTHONUNBUFFERED`), así que
`journalctl` puede no mostrar los mensajes del arranque hasta que el proceso se
reinicia. Para verificar el estado real, fíate del diagnóstico y no del log.
