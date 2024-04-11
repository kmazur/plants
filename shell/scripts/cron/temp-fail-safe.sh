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

MIN_CPU_FREQ=600
MAX_CPU_FREQ=1000

PUBLISHER="TEMP_FAIL_SAFE"
register_publisher "$PUBLISHER"

SCALE=""
while true; do
  TEMP="$(get_cpu_temp | cut -d'.' -f 1)"

  PREV_SCALE="$SCALE"
  if [[ "$TEMP" -le "$NORMAL_THRESHOLD" ]]; then
    log "${TEMP} ºC is ok -> NORMAL operation"
    SCALE="100"
    if [[ "$PREV_SCALE" != "$SCALE" ]]; then
      set_scale "$SCALE"
      log "Setting cpu frequency to: 'ondemand'"
      sudo cpufreq-set -g ondemand
    fi
  elif [[ "$TEMP" -ge "$MAX_THRESHOLD" ]]; then
    set_scale "0"

    log "Setting cpu frequency to: 'powersave'"
    sudo cpufreq-set -g powersave
    log_error "${TEMP} ºC is too hot! -> CRITICAL (action: reboot)"
    sudo reboot -h now
  else
    SCALE="$(( 100 * (MAX_THRESHOLD - TEMP) / (MAX_THRESHOLD - NORMAL_THRESHOLD) ))"
    log_warn "${TEMP} ºC is warning -> SCALED operation (action: scale=$SCALE)"
    if [[ "$PREV_SCALE" != "$SCALE" ]]; then
      set_scale "$SCALE"
      CPU_FREQ="$(get_scaled_range "$MIN_CPU_FREQ" "$MAX_CPU_FREQ")"
      log "Setting cpu frequency to: '${CPU_FREQ}MHz'"
      sudo cpufreq-set -f "${CPU_FREQ}MHz"
    fi
  fi

  declare EPOCH_SECONDS="$(get_current_epoch_seconds)"
  declare BATCH=""
  for cpu in /sys/devices/system/cpu/cpu*/cpufreq/scaling_cur_freq; do
    CORE="${cpu:27:1}"
    FREQ="$(cat "$cpu")"
    MHZ="$((FREQ/1000))"

    declare MEASUREMENT_NAME="cpu"
    declare FIELD_VALUES="frequency=$MHZ"
    declare TAGS="machine_name=$MACHINE_NAME,core=$CORE"
    declare TIMESTAMP="$EPOCH_SECONDS"

    DATAPOINT="$MEASUREMENT_NAME,$TAGS $FIELD_VALUES $TIMESTAMP"
    if [[ -z "$BATCH" ]]; then
      BATCH="$DATAPOINT"
    else
      BATCH="$BATCH
$DATAPOINT"
    fi

  done
  publish_measurement_raw "$PUBLISHER" "$BATCH"

  update_period
  log "Period is: $PERIOD s"
  sleep "$PERIOD"
done