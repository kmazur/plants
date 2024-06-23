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

  notify_work_completed  "${PROCESS}-scan"
  if [ -z "$NOT_PROCESSED_FILES" ]; then
    continue
  fi

  request_cpu_time "${PROCESS}-publish" "$(echo "$NOT_PROCESSED_FILES" | wc -l)"

  BATCH=""
  echo "$NOT_PROCESSED_FILES" | while IFS= read -r LATEST_NOT_PROCESSED_FILE; do
    LATEST_NOT_PROCESSED_PATH="$INPUT_STAGE_DIR/$LATEST_NOT_PROCESSED_FILE"
    log "Processing: $LATEST_NOT_PROCESSED_PATH"
    FILE_DATETIME="$(strip "$LATEST_NOT_PROCESSED_FILE" "temp_hum_level_" ".txt")"
    VALUES="$(cat "$LATEST_NOT_PROCESSED_PATH")"
    if [ -n "$VALUES" ] && [ -n "$FILE_DATETIME" ]; then
      TEMPERATURE="$(echo "$VALUES" | head -n 1)"
      HUMIDITY="$(echo "$VALUES" | tail -n 1)"
      EPOCH_SECONDS="$(date_compact_to_epoch "$FILE_DATETIME")"

      TIMESTAMP="$EPOCH_SECONDS"
      if [ -n "$TEMPERATURE" ]; then
        DATAPOINT="temp_measurement,machine_name=$MACHINE_NAME temperature=$TEMPERATURE $TIMESTAMP"
        if [[ -z "$BATCH" ]]; then
          BATCH="$DATAPOINT"
        else
          BATCH="$BATCH
$DATAPOINT"
          DATAPOINT="$MEASUREMENT_NAME,$TAGS $FIELD_VALUES $TIMESTAMP"
        fi
      fi
      if [ -n "$HUMIDITY" ]; then
        DATAPOINT="humidity_measurement,machine_name=$MACHINE_NAME humidity=$HUMIDITY $TIMESTAMP"
        if [[ -z "$BATCH" ]]; then
          BATCH="$DATAPOINT"
        else
          BATCH="$BATCH
$DATAPOINT"
          DATAPOINT="$MEASUREMENT_NAME,$TAGS $FIELD_VALUES $TIMESTAMP"
        fi
      fi
    fi

    if [ -n "$BATCH" ]; then
      publish_measurement_batch "$PUBLISHER" "$BATCH"
    fi

    echo "$NOT_PROCESSED_FILES" >> "$PROCESSED_PATH"

    notify_work_completed "${PROCESS}-publish"
  done
done
