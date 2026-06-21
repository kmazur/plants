#!/usr/bin/env bash
set -euo pipefail

sudo systemctl disable --now camera-snapshot.timer 2>/dev/null || true
sudo systemctl disable --now camera-remote-update.timer 2>/dev/null || true
sudo systemctl disable --now camera-remote.service 2>/dev/null || true
sudo rm -f /etc/systemd/system/camera-remote.service
sudo rm -f /etc/systemd/system/camera-snapshot.service
sudo rm -f /etc/systemd/system/camera-snapshot.timer
sudo rm -f /etc/systemd/system/camera-remote-update.service
sudo rm -f /etc/systemd/system/camera-remote-update.timer
sudo systemctl daemon-reload

echo "Camera Remote systemd units removed. History and /etc/camera-remote/config.ini were left intact."
