#!/bin/bash

# shellcheck source=shell/scripts/lib.sh
source "$LIB_INIT_FILE"
ensure_env


CONFIG_FILE="$(get_required_config "image-config-file")"

libcamera-still -c "$CONFIG_FILE" -o "$TMP_DIR/light_level.jpg" -n -t 1 &> /dev/null
"$BIN_DIR/light_level" "$TMP_DIR/light_level.jpg"