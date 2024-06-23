#!/bin/bash

# shellcheck source=shell/scripts/lib.sh
source "$LIB_INIT_FILE"
ensure_env

INPUT_STAGE=""
OUTPUT_STAGE="sensor/cputemp_raw"
# INPUT:
# - none
# OUTPUT:
# - sensor/cputemp_raw/cpu_temp_level_20240505_101501.txt

PROCESS="$OUTPUT_STAGE"

while true; do
  OUTPUT_STAGE_DIR="$(ensure_stage_dir "$OUTPUT_STAGE")"

  request_cpu_time "${PROCESS}-temp_read" "2"

  log "Reading cpu temp sensor"
  START_DATE_TIME="$(get_current_date_time_compact)"
  FILE_NAME="cpu_temp_level_$START_DATE_TIME.txt"
  FILE_PATH="$OUTPUT_STAGE_DIR/$FILE_NAME"

  CPU_TEMP="$(get_cpu_temp)"
  echo "$CPU_TEMP" > "$FILE_PATH"

  for cpu in /sys/devices/system/cpu/cpu*/cpufreq/scaling_cur_freq; do
    CORE="${cpu:27:1}"
    FREQ="$(cat "$cpu")"
    MHZ="$((FREQ/1000))"

    echo "${CORE}=${MHZ}" >> "$FILE_PATH"
  done

  notify_work_completed "${PROCESS}-temp_read"
done
