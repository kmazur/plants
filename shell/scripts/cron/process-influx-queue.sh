#!/bin/bash

# shellcheck source=shell/scripts/lib.sh
source "$LIB_INIT_FILE"
ensure_env

MIN_PERIOD="${1:-0}"
MAX_PERIOD="${2:-300}"
PERIOD="$MIN_PERIOD"

PUBLISHER="main"
register_publisher "$PUBLISHER"

function update_period() {
  PERIOD="$(get_scaled_inverse_value "$MIN_PERIOD" "$MAX_PERIOD")"
}

while true; do
  while true; do
    if ! is_scale_suspended; then
      PUBLISHED_COUNT="$(publish_main_queue)"
      log "Published $PUBLISHED_COUNT data points"
      if [[ "$PUBLISHED_COUNT" == "0" ]]; then
        break
      fi
    else
      log_warn "Influx publishing suspended"
      break
    fi
  done

  update_period
  log "Period is: $PERIOD s"
  sleep "$PERIOD"

done
