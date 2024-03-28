#!/bin/bash

# shellcheck source=shell/scripts/lib.sh
source "$LIB_INIT_FILE"
ensure_env

log "Initializing '$MACHINE_NAME'"

log "Enabling infrared light"
set_gpio_out "17" "0"