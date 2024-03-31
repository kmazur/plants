#!/bin/bash

# shellcheck source=shell/scripts/lib.sh
source "$LIB_INIT_FILE"
ensure_env

libcamera-still -c video-config-ctrl.txt -o "$TMP_DIR/light_level.jpg" -n -t 1 --mode 2304:1296 &> /dev/null
"$BIN_DIR/light_level" "$TMP_DIR/light_level.jpg"