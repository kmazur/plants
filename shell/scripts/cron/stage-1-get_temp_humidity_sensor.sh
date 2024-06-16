#!/bin/bash

# shellcheck source=shell/scripts/lib.sh
source "$LIB_INIT_FILE"
ensure_env

INPUT_STAGE=""
OUTPUT_STAGE="sensor/temp_raw"
# INPUT:
# - none
# OUTPUT:
# - sensor/temp_raw/temp_hum_level_20240505_101501.txt

PROCESS="$OUTPUT_STAGE"

while true; do
  OUTPUT_STAGE_DIR="$(ensure_stage_dir "$OUTPUT_STAGE")"

  request_cpu_time "${PROCESS}-temp_hum_read" "1"
  OUTPUT_STAGE_DIR="$(ensure_stage_dir "$OUTPUT_STAGE")"

  log "Reading temp & humidity sensor"
  START_DATE_TIME="$(get_current_date_time_compact)"
  FILE_NAME="temp_hum_level_$START_DATE_TIME.txt"
  FILE_PATH="$OUTPUT_STAGE_DIR/$FILE_NAME"

  VALUES="$(python "$REPO_DIR/python/scripts/read_temp.py")"
  cat "$VALUES" > "$FILE_PATH"
done
