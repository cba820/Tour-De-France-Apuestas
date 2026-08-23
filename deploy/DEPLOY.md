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

Es el fallo que más molesta: al hacer *Stop* y *Start*, EC2 asigna una IP nueva y se
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

## Claves SSH: la trampa al crear una nueva

Crear un par de claves en AWS **no** lo instala en una instancia que ya está
corriendo: eso solo ocurre al lanzarla. Si generas una clave nueva y la pones en
el secret `EC2_SSH_KEY`, el deploy falla con
`Permission denied (publickey)` hasta que autorices su clave **pública** en el
servidor.

Para autorizar una clave nueva, entrando con una que ya funcione:

```bash
# 1) En tu PC: derivar la publica de la privada (no expone la privada)
ssh-keygen -y -f la-vuelta-apuestas.pem > nueva.pub

# 2) Subirla y anadirla a authorized_keys
scp -i tdf-key.pem nueva.pub ec2-user@<host>:/tmp/nueva.pub
ssh -i tdf-key.pem ec2-user@<host>   'cat /tmp/nueva.pub >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys && rm /tmp/nueva.pub'
```

Conviene **dejar la clave anterior autorizada** como respaldo: si el secret se
rompe o se pega mal, sigues teniendo acceso al servidor para arreglarlo.

Claves autorizadas actualmente en `~/.ssh/authorized_keys` de `ec2-user`:

| Clave | Fingerprint | Uso |
|---|---|---|
| `tdf-key` | `SHA256:nOcBagi2A9Bu…S+aYXo` | Acceso manual de respaldo |
| `la-vuelta-apuestas` | `SHA256:HMRBGY0rAS0n…t5Ious` | La del secret `EC2_SSH_KEY` (deploy automático) |

Para comprobar cuál acepta el servidor:

```bash
ssh-keygen -lf ~/.ssh/authorized_keys
```

Y para saber cuál lleva el secret, el workflow publica su fingerprint al
desplegar (el fingerprint identifica la clave sin revelarla). Si no coinciden,
ese es el problema.

## URL estable sin Elastic IP: DuckDNS + actualizador automático

Sin Elastic IP, la IP pública cambia **cada vez que la instancia se para y se
arranca** (no en un reboot, y no mientras está encendida). Eso rompe cualquier URL
que lleve la IP dentro, como las de `sslip.io`.

La solución gratis es un dominio de DuckDNS con un cron que le avise de la IP
nueva. El dominio no cambia nunca, así que se puede repartir a los participantes
sin miedo.

### 1. Conseguir el token (una sola vez)

Entra a <https://www.duckdns.org> con cualquiera de sus botones de login. El
**token** es un UUID que aparece arriba del panel; no caduca y no cambia aunque
añadas o quites dominios.

Si el login falla con `reCaptcha too low`: prueba en una ventana de incógnito, con
el bloqueador de anuncios desactivado, o desde otra red (datos del móvil). Es un
servicio de voluntarios y su captcha falla a ratos.

### 2. Instalar el actualizador en el servidor

```bash
cd /home/ec2-user/TDF_apuestas
mkdir -p ~/duckdns && cp scripts/duckdns-update.sh ~/duckdns/
chmod +x ~/duckdns/duckdns-update.sh
printf '%s' 'TU-TOKEN-AQUI' > ~/duckdns/token && chmod 600 ~/duckdns/token
( crontab -l 2>/dev/null;   echo '*/5 * * * * $HOME/duckdns/duckdns-update.sh';   echo '@reboot sleep 30 && $HOME/duckdns/duckdns-update.sh' ) | crontab -
~/duckdns/duckdns-update.sh && tail -2 ~/duckdns/duck.log
```

Debe registrar `OK predicciones-draft-tdf.duckdns.org actualizado`. El cron lo
repite cada 5 minutos y al arrancar la instancia, así que tras un Stop/Start la
URL se arregla sola en menos de un minuto.

Mientras el archivo `~/duckdns/token` esté vacío el script no hace nada y lo anota
en `~/duckdns/duck.log`, así que se puede instalar antes de tener el token.

### 3. Comprobar

```bash
nslookup predicciones-draft-tdf.duckdns.org     # debe dar la IP actual
curl -sI https://predicciones-draft-tdf.duckdns.org/login | head -1
```

El vhost ya está en el Caddyfile, así que en cuanto el DNS apunte bien funciona
sin tocar Caddy.
