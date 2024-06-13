#!/bin/bash

# shellcheck source=shell/scripts/lib.sh
source "$LIB_INIT_FILE"
ensure_env

INPUT_STAGE="video/24_timelapse"
OUTPUT_STAGE="video/24_timelapse_upload"
# INPUT:
# - video/24_timelapse/pi4b_24_timelapse.mp4
# OUTPUT:
# - none


PROCESS="$OUTPUT_STAGE"

while true; do

  request_cpu_time "${PROCESS}-scan" "1"

  MACHINE_NAME="$(get_required_config "name")"

  INPUT_STAGE_DIR="$(ensure_stage_dir "$INPUT_STAGE")"
  OUTPUT_STAGE_DIR="$(ensure_stage_dir "$OUTPUT_STAGE")"
  PROCESSED_PATH="$OUTPUT_STAGE_DIR/processed.txt"

  NOT_PROCESSED_FILES="$(get_processed_diff "$INPUT_STAGE_DIR" "$OUTPUT_STAGE_DIR" "_timelapse.mp4")"
  LATEST_NOT_PROCESSED_FILE="$(echo "$NOT_PROCESSED_FILES" | head -n 1)"
  LATEST_NOT_PROCESSED_PATH="$INPUT_STAGE_DIR/$LATEST_NOT_PROCESSED_FILE"

  if [ -z "$LATEST_NOT_PROCESSED_FILE" ]; then
    continue
  fi

  FILE_NAME="${MACHINE_NAME}_24_timelapse.mp4"
  FILE_PATH="$OUTPUT_STAGE_DIR/$FILE_NAME"

  # Does not exist or has changed
  if [ ! -f "$FILE_PATH" ] || ! cmp -s "$FILE_PATH" "$LATEST_NOT_PROCESSED_PATH"; then
    log "Processing: $LATEST_NOT_PROCESSED_PATH"
    if cp -f "$LATEST_NOT_PROCESSED_PATH" "$FILE_PATH"; then
      if [ -f "$FILE_PATH" ]; then
        request_cpu_time "${PROCESS}-upload" "5"
        if upload_file "$FILE_PATH" "image/jpg"; then
          #echo "$LATEST_NOT_PROCESSED_FILE" >> "$PROCESSED_PATH"
          continue
        fi
      fi
    fi
  fi

done
