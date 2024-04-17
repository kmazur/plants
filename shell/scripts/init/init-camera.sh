#!/bin/bash

source "/home/user/WORK/workspace/plants/shell/.profile"
# shellcheck source=shell/scripts/lib.sh
source "$LIB_INIT_FILE"
ensure_env

CAMERA_CONFIG_DIR="$REPO_DIR/shell/scripts/video/config"

set_config "video-config-file" "$CAMERA_CONFIG_DIR/video-config-$MACHINE_NAME.txt"
set_config "image-config-file" "$CAMERA_CONFIG_DIR/image-config-$MACHINE_NAME.txt"