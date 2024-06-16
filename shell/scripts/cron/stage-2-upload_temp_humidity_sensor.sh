#!/bin/bash

# shellcheck source=shell/scripts/lib.sh
source "$LIB_INIT_FILE"
ensure_env

INPUT_STAGE="sensor/temp_raw"
OUTPUT_STAGE="sensor/temp_raw_publish"
# INPUT:
# - sensor/temp_raw/temp_hum_level_20240505_101501.txt
# OUTPUT:
# - none

PUBLISHER="TEMP_HUM"
PROCESS="$OUTPUT_STAGE"

while true; do
  request_cpu_time "${PROCESS}-scan" "1"

  INPUT_STAGE_DIR="$(ensure_stage_dir "$INPUT_STAGE")"
  OUTPUT_STAGE_DIR="$(ensure_stage_dir "$OUTPUT_STAGE")"
  PROCESSED_PATH="$OUTPUT_STAGE_DIR/processed.txt"

  NOT_PROCESSED_FILES="$(get_not_processed_files "$INPUT_STAGE_DIR" "$OUTPUT_STAGE_DIR" "temp_hum_level_")"
  if [ -z "$NOT_PROCESSED_FILES" ]; then
    continue
  fi

  echo "$NOT_PROCESSED_FILES" | while IFS= read -r LATEST_NOT_PROCESSED_FILE; do
    LATEST_NOT_PROCESSED_PATH="$INPUT_STAGE_DIR/$LATEST_NOT_PROCESSED_FILE"
    log "Processing: $LATEST_NOT_PROCESSED_PATH"

    FILE_DATETIME="$(strip "$LATEST_NOT_PROCESSED_FILE" "temp_hum_level_" ".txt")"
    VALUES="$(cat "$LATEST_NOT_PROCESSED_PATH")"
    if [ -n "$VALUES" ] && [ -n "$FILE_DATETIME" ]; then

      TEMPERATURE="$(echo "$VALUES" | head -n 1)"
      HUMIDITY="$(echo "$VALUES" | tail -n 1)"

      if [[ -n "$TEMPERATURE" && -n "$HUMIDITY" ]]; then
        request_cpu_time "${PROCESS}-publish" "4"
        if publish_measurement_single "$PUBLISHER" "temp_measurement" "temperature=$TEMPERATURE" "$(date_compact_to_epoch "$FILE_DATETIME")"; then
          if publish_measurement_single "$PUBLISHER" "humidity_measurement" "humidity=$HUMIDITY" "$(date_compact_to_epoch "$FILE_DATETIME")"; then
            echo "$LATEST_NOT_PROCESSED_FILE" >> "$PROCESSED_PATH"
          fi
        fi
      else
        echo "$LATEST_NOT_PROCESSED_FILE" >> "$PROCESSED_PATH"
      fi
    fi
  done
done
