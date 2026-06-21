#!/usr/bin/env bash
set -euo pipefail

echo "== systemd =="
systemctl --no-pager --full status camera-remote.service || true
systemctl --no-pager --full status camera-snapshot.timer || true
systemctl --no-pager --full status camera-remote-update.timer || true

echo
echo "== config =="
sudo sed -E 's/^(auth_token[[:space:]]*=[[:space:]]*).+/\1*** hidden ***/' /etc/camera-remote/config.ini 2>/dev/null || true

echo
echo "== latest =="
ls -l /home/user/camera-remote-data/latest.jpg /home/user/camera-remote-data/latest.json 2>/dev/null || true

echo
echo "== pitunnel =="
pitunnel --list 2>/dev/null | sed -E 's/(--http-auth [^:[:space:]]+:)[^ ]+/\1*** hidden ***/g' || true

echo
echo "== git =="
git -C /home/user/IdeaProjects/plants --no-pager log --oneline -1 2>/dev/null || true
git -C /home/user/IdeaProjects/plants status --short 2>/dev/null || true
