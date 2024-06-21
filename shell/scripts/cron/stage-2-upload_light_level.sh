#!/bin/bash

# shellcheck source=shell/scripts/lib.sh
source "$LIB_INIT_FILE"
ensure_env

INPUT_STAGE="video/raw"
OUTPUT_STAGE="video/light_level"
# INPUT:
# - video/raw/light_level_20240505_101501.txt
# OUTPUT:
# - none

PUBLISHER="LIGHT_LEVEL"
PROCESS="$OUTPUT_STAGE"

while true; do

  request_cpu_time "${PROCESS}-scan" "1"

  MACHINE_NAME="$(get_required_config "name")"

  INPUT_STAGE_DIR="$(ensure_stage_dir "$INPUT_STAGE")"
  OUTPUT_STAGE_DIR="$(ensure_stage_dir "$OUTPUT_STAGE")"
  PROCESSED_PATH="$OUTPUT_STAGE_DIR/processed.txt"

  NOT_PROCESSED_FILES="$(get_not_processed_files "$INPUT_STAGE_DIR" "$OUTPUT_STAGE_DIR" "light_level_")"

  notify_work_completed "${PROCESS}-scan"
  if [ -z "$NOT_PROCESSED_FILES" ]; then
    continue
  fi

  echo "$NOT_PROCESSED_FILES" | while IFS= read -r LATEST_NOT_PROCESSED_FILE; do
    LATEST_NOT_PROCESSED_PATH="$INPUT_STAGE_DIR/$LATEST_NOT_PROCESSED_FILE"
    log "Processing: $LATEST_NOT_PROCESSED_PATH"

    FILE_DATETIME="$(strip "$LATEST_NOT_PROCESSED_FILE" "light_level_" ".txt")"
    LIGHT_LEVEL="$(cat "$LATEST_NOT_PROCESSED_PATH")"
    if [ -n "$LIGHT_LEVEL" ] && [ -n "$FILE_DATETIME" ]; then
      request_cpu_time "${PROCESS}-publish" "2"

      if publish_measurement_single "$PUBLISHER" "image_analysis" "light_level=$LIGHT_LEVEL" "$(date_compact_to_epoch "$FILE_DATETIME")"; then
        echo "$LATEST_NOT_PROCESSED_FILE" >> "$PROCESSED_PATH"
      fi

      notify_work_completed "${PROCESS}-publish"
    else
      log_warn "Light level ($LIGHT_LEVEL) empty or file dateTime ($FILE_DATETIME) empty"
      echo "$LATEST_NOT_PROCESSED_FILE" >> "$PROCESSED_PATH"
    fi
  done

done
