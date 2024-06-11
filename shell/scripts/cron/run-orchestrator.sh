#!/bin/bash

# shellcheck source=shell/scripts/lib.sh
source "$LIB_INIT_FILE"
ensure_env

while true; do
  REQUESTS_FILE="$(get_orchestrator_requests_file)"
  touch "$REQUESTS_FILE"

  REQUESTS="$(cat $REQUESTS_FILE)"


done
