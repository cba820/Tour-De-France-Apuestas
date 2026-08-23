#!/bin/sh
# Mantiene el dominio de DuckDNS apuntando a la IP publica actual del servidor.
#
# El problema que resuelve: sin Elastic IP, cada vez que la instancia EC2 se para
# y se arranca, AWS le da una IP publica nueva y la URL deja de funcionar. Este
# script le dice a DuckDNS cual es la IP de ahora, asi que el dominio se arregla
# solo sin tocar nada.
#
# Instalacion (ver deploy/DEPLOY.md):
#   mkdir -p ~/duckdns && cp scripts/duckdns-update.sh ~/duckdns/
#   chmod +x ~/duckdns/duckdns-update.sh
#   printf '%s' 'TU-TOKEN' > ~/duckdns/token && chmod 600 ~/duckdns/token
#   ( crontab -l 2>/dev/null; \
#     echo '*/5 * * * * $HOME/duckdns/duckdns-update.sh'; \
#     echo '@reboot sleep 30 && $HOME/duckdns/duckdns-update.sh' ) | crontab -
#
# Mientras el archivo del token este vacio, el script no hace nada (y lo deja
# anotado en el log), asi que se puede instalar antes de tener el token.

set -u

DOMAIN="predicciones-draft-tdf"          # solo el subdominio, sin .duckdns.org
DIR="$HOME/duckdns"
TOKEN_FILE="$DIR/token"
LOG="$DIR/duck.log"
MAX_LOG_BYTES=100000

mkdir -p "$DIR"

log() {
    # Rotacion simple: si el log crece demasiado, se queda con la ultima mitad.
    if [ -f "$LOG" ] && [ "$(wc -c < "$LOG")" -gt "$MAX_LOG_BYTES" ]; then
        tail -n 200 "$LOG" > "$LOG.tmp" && mv "$LOG.tmp" "$LOG"
    fi
    echo "$(date '+%Y-%m-%d %H:%M:%S') $1" >> "$LOG"
}

if [ ! -s "$TOKEN_FILE" ]; then
    log "SIN TOKEN: escribe el token de duckdns.org en $TOKEN_FILE"
    exit 0
fi

TOKEN=$(tr -d ' \t\r\n' < "$TOKEN_FILE")

# ip= vacio significa "usa la IP desde la que te estoy llamando", que es
# justamente la IP publica del servidor. Asi no hay que averiguarla.
RESPONSE=$(curl -sS --max-time 30 \
    "https://www.duckdns.org/update?domains=${DOMAIN}&token=${TOKEN}&ip=" 2>&1)

case "$RESPONSE" in
    OK)
        log "OK  ${DOMAIN}.duckdns.org actualizado"
        ;;
    KO)
        log "KO  DuckDNS rechazo la peticion: revisa que el token y el dominio sean correctos"
        exit 1
        ;;
    *)
        log "ERROR respuesta inesperada: ${RESPONSE}"
        exit 1
        ;;
esac
