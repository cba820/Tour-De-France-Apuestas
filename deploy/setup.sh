#!/usr/bin/env bash
# Instalación de Predicciones TDF 2026 en un servidor Amazon Linux 2023 (AWS EC2).
# Ejecutar desde la carpeta del proyecto:  bash deploy/setup.sh
set -euo pipefail

PROJECT_DIR="/home/ec2-user/TDF_apuestas"

echo ">> Instalando dependencias del sistema..."
sudo dnf install -y python3 python3-pip

echo ">> Creando entorno virtual e instalando paquetes de Python..."
cd "$PROJECT_DIR"
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt

echo ">> Instalando el servicio systemd..."
sudo cp deploy/tdf.service /etc/systemd/system/tdf.service
sudo systemctl daemon-reload
sudo systemctl enable tdf
sudo systemctl restart tdf

echo ">> Estado del servicio:"
sudo systemctl status tdf --no-pager || true

echo ""
echo ">> Listo. La app está escuchando en el puerto 80."
echo ">> Abre http://ec2-18-221-241-6.us-east-2.compute.amazonaws.com en el navegador."
echo ">> Recuerda editar /etc/systemd/system/tdf.service para poner tu SECRET_KEY"
echo "   y tu ADMIN_PASSWORD, y luego: sudo systemctl daemon-reload && sudo systemctl restart tdf"
