#!/usr/bin/env bash
set -euo pipefail

STACK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG_DIR="/etc/camera-remote"
CONFIG_FILE="$CONFIG_DIR/config.ini"

sudo install -d -m 0755 "$CONFIG_DIR"
if [ ! -f "$CONFIG_FILE" ]; then
  sudo install -m 0644 "$STACK_DIR/config.example.ini" "$CONFIG_FILE"
fi

TOKEN="$(sudo env PYTHONPATH="$STACK_DIR" python3 - "$CONFIG_FILE" <<'PY'
import sys
from camera_remote.config import ensure_auth_token
print(ensure_auth_token(sys.argv[1]))
PY
)"

sudo chown root:user "$CONFIG_FILE"
sudo chmod 0640 "$CONFIG_FILE"

sudo install -m 0644 "$STACK_DIR/systemd/camera-remote.service" /etc/systemd/system/camera-remote.service
sudo install -m 0644 "$STACK_DIR/systemd/camera-snapshot.service" /etc/systemd/system/camera-snapshot.service
sudo install -m 0644 "$STACK_DIR/systemd/camera-snapshot.timer" /etc/systemd/system/camera-snapshot.timer
sudo install -m 0644 "$STACK_DIR/systemd/camera-remote-update.service" /etc/systemd/system/camera-remote-update.service
sudo install -m 0644 "$STACK_DIR/systemd/camera-remote-update.timer" /etc/systemd/system/camera-remote-update.timer

sudo systemctl daemon-reload
sudo systemctl enable --now camera-remote.service
sudo systemctl enable --now camera-snapshot.timer
sudo systemctl enable --now camera-remote-update.timer
sudo systemctl restart camera-remote.service
sudo systemctl restart camera-snapshot.timer

IP="$(hostname -I | awk '{print $1}')"
echo "Camera Remote installed."
echo "Config: $CONFIG_FILE"
echo "Local URL on the Pi: http://127.0.0.1:8090/?token=$TOKEN"
echo "For PiTunnel Custom TCP, open: http://<available-at-host>:<available-at-port>/?token=$TOKEN"
echo "LAN URL, if you intentionally set server.host=0.0.0.0: http://${IP:-raspberrypi.local}:8090/?token=$TOKEN"
