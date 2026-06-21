#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."
exec /usr/bin/python3 -m camera_remote.capture --config /etc/camera-remote/config.ini --once --blocking

