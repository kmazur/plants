#!/bin/bash

# shellcheck source=shell/scripts/lib.sh
source "$LIB_INIT_FILE"
ensure_env

MAX_THRESHOLD="80"
NORMAL_THRESHOLD="50"

MIN_PERIOD="${1:-10}"
MAX_PERIOD="${2:-60}"
PERIOD="$MIN_PERIOD"

function update_period() {
  PERIOD="$(get_scaled_inverse_value "$MIN_PERIOD" "$MAX_PERIOD")"
}

while true; do
  TEMP="$(get_cpu_temp | cut -d'.' -f 1)"

  if [[ "$TEMP" -le "$NORMAL_THRESHOLD" ]]; then
    log "${TEMP} ºC is ok -> NORMAL operation"
    set_scale "100"
  elif [[ "$TEMP" -ge "$MAX_THRESHOLD" ]]; then
    log_error "${TEMP} ºC is too hot! -> CRITICAL (action: reboot)"
    reboot -h now
  else
    SCALE="$(( 100 * (MAX_THRESHOLD - TEMP) / (MAX_THRESHOLD - NORMAL_THRESHOLD) ))"
    log_warn "${TEMP} ºC is warning -> SCALED operation (action: scale=$SCALE)"
    set_scale "$SCALE"
  fi

  update_period
  sleep "$PERIOD"
done