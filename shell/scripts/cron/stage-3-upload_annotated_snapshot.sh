#!/bin/bash

# shellcheck source=shell/scripts/lib.sh
source "$LIB_INIT_FILE"
ensure_env

INPUT_STAGE="video/snapshot_annotate"
OUTPUT_STAGE="video/snapshot_annotated_upload"
# INPUT:
# - video/snapshot_annotate/snapshot_annotated_20240505_101501.jpg
# OUTPUT:
# - none

PROCESS="$OUTPUT_STAGE"

while true; do

  request_cpu_time "${PROCESS}-scan" "1"

  MACHINE_NAME="$(get_required_config "name")"

  INPUT_STAGE_DIR="$(ensure_stage_dir "$INPUT_STAGE")"
  OUTPUT_STAGE_DIR="$(ensure_stage_dir "$OUTPUT_STAGE")"
  PROCESSED_PATH="$OUTPUT_STAGE_DIR/processed.txt"

  NOT_PROCESSED_FILES="$(get_not_processed_files "$INPUT_STAGE_DIR" "$OUTPUT_STAGE_DIR" "snapshot_annotated_")"
  LATEST_NOT_PROCESSED_FILE="$(echo "$NOT_PROCESSED_FILES" | tail -n 1)"
  LATEST_NOT_PROCESSED_PATH="$INPUT_STAGE_DIR/$LATEST_NOT_PROCESSED_FILE"

  notify_work_completed "${PROCESS}-scan"
  if [ -z "$LATEST_NOT_PROCESSED_FILE" ]; then
    continue
  fi

  # Skip earlier files
  FILES_TO_SKIP="$(echo "$NOT_PROCESSED_FILES" | grep -v "$LATEST_NOT_PROCESSED_FILE")"
  if [ -n "$FILES_TO_SKIP" ]; then
    echo "$FILES_TO_SKIP" >> "$PROCESSED_PATH"
  fi

  log "Processing: $LATEST_NOT_PROCESSED_PATH"

  FILE_NAME="${MACHINE_NAME}.jpg"
  FILE_PATH="$OUTPUT_STAGE_DIR/$FILE_NAME"

  if cp -f "$LATEST_NOT_PROCESSED_PATH" "$FILE_PATH"; then
    if [ -f "$FILE_PATH" ]; then
      request_cpu_time "${PROCESS}-upload" "1"
      if upload_file "$FILE_PATH" "image/jpg"; then
        log "Uploaded file: $FILE_PATH successfully"
        echo "$LATEST_NOT_PROCESSED_FILE" >> "$PROCESSED_PATH"
      else
        log "Error uploading file: $FILE_PATH"
      fi
      notify_work_completed "${PROCESS}-upload"
    fi
  fi

done
