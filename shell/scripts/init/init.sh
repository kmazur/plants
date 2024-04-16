#!/bin/bash

source "/home/user/WORK/workspace/plants/shell/.profile"
# shellcheck source=shell/scripts/lib.sh
source "$LIB_INIT_FILE"
ensure_env

log "Starting init"
"$INIT_DIR/init-general.sh"
"$INIT_DIR/init-env-refresh.sh"
"$INIT_DIR/init-daylight.sh"
"$INIT_DIR/init-cron.sh"

declare INIT_FILE="$REPO_DIR/shell/scripts/init/$MACHINE_NAME.sh"
if [ -f "$INIT_FILE" ]; then
  "$INIT_FILE"
else
  log_warn "Init file for '$MACHINE_NAME' not found"
fi
