#!/bin/bash

# shellcheck source=shell/scripts/lib.sh
source "$LIB_INIT_FILE"
ensure_env

INPUT_STAGE="sensor/cputemp_raw"
OUTPUT_STAGE="sensor/cputemp_raw_publish"
# INPUT:
# - sensor/cputemp_raw/cpu_temp_level_20240505_101501.txt
# OUTPUT:
# - none

PUBLISHER="CPU_TEMP"
PROCESS="$OUTPUT_STAGE"

while true; do
  request_cpu_time "${PROCESS}-scan" "1"

  INPUT_STAGE_DIR="$(ensure_stage_dir "$INPUT_STAGE")"
  OUTPUT_STAGE_DIR="$(ensure_stage_dir "$OUTPUT_STAGE")"
  PROCESSED_PATH="$OUTPUT_STAGE_DIR/processed.txt"

  NOT_PROCESSED_FILES="$(get_not_processed_files "$INPUT_STAGE_DIR" "$OUTPUT_STAGE_DIR" "cpu_temp_level_")"

  notify_work_completed  "${PROCESS}-scan"
  if [ -z "$NOT_PROCESSED_FILES" ]; then
    continue
  fi

  echo "$NOT_PROCESSED_FILES" | while IFS= read -r LATEST_NOT_PROCESSED_FILE; do
    LATEST_NOT_PROCESSED_PATH="$INPUT_STAGE_DIR/$LATEST_NOT_PROCESSED_FILE"
    log "Processing: $LATEST_NOT_PROCESSED_PATH"

    FILE_DATETIME="$(strip "$LATEST_NOT_PROCESSED_FILE" "cpu_temp_level_" ".txt")"
    VALUES="$(cat "$LATEST_NOT_PROCESSED_PATH")"
    if [ -n "$VALUES" ] && [ -n "$FILE_DATETIME" ]; then

      TEMPERATURE="$(echo "$VALUES" | head -n 1)"
      CPU_FREQENCIES="$(echo "$VALUES" | tail -n +2)"

      request_cpu_time "${PROCESS}-publish" "1"

      if [[ -n "$TEMPERATURE" ]]; then
        publish_measurement_single "$PUBLISHER" "cpu_measurement" "temperature=$TEMPERATURE" "$(date_compact_to_epoch "$FILE_DATETIME")"
      fi
      if [[ -n "$CPU_FREQUENCIES" ]]; then
        EPOCH_SECONDS="$(date_compact_to_epoch "$FILE_DATETIME")"
        BATCH=""
        for KV in $CPU_FREQUENCIES; do
          CORE="$(echo "$KV" | cut -d'=' -f 1)"
          MHZ="$(echo "$KV" | cut -d'=' -f 2)"

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
            DATAPOINT="$MEASUREMENT_NAME,$TAGS $FIELD_VALUES $TIMESTAMP"
          fi
        done

        publish_measurement_batch "$PUBLISHER" "$BATCH"
      fi

      echo "$LATEST_NOT_PROCESSED_FILE" >> "$PROCESSED_PATH"

      notify_work_completed "${PROCESS}-publish"
    fi
  done
done
