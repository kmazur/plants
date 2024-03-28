#!/bin/bash

# shellcheck source=shell/scripts/lib.sh
source "$LIB_INIT_FILE"
ensure_env

MIN_PERIOD="${1:-20}"
MAX_PERIOD="${2:-120}"
PERIOD="$MIN_PERIOD"

function update_period() {
  PERIOD="$(get_scaled_inverse_value "$MIN_PERIOD" "$MAX_PERIOD")"
}

while true; do
  if ! is_scale_suspended; then
    CPU_TEMPERATURE="$(get_cpu_temp)"
    log "CPU temperature is: $CPU_TEMPERATURE"

    update_measurement_single "cpu_measurement" "cpu_temperature=$CPU_TEMPERATURE"
  else
    log_warn "CPU measurments suspended"
  fi

  update_period
  log "Period is: $PERIOD s"
  sleep "$PERIOD"

done