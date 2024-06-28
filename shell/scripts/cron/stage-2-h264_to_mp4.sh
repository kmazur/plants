#!/bin/bash

# shellcheck source=shell/scripts/lib.sh
source "$LIB_INIT_FILE"
ensure_env

INPUT_STAGE="video/raw"
OUTPUT_STAGE="video/mp4"
# INPUT:
# - video/raw/video_20240505_101501.h264
# OUTPUT:
# - video/mp4/video_20240505_101501.mp4

PROCESS="$OUTPUT_STAGE"

while true; do

  request_cpu_time "${PROCESS}-scan" "1"

  INPUT_STAGE_DIR="$(ensure_stage_dir "$INPUT_STAGE")"
  OUTPUT_STAGE_DIR="$(ensure_stage_dir "$OUTPUT_STAGE")"
  PROCESSED_PATH="$OUTPUT_STAGE_DIR/processed.txt"

  NOT_PROCESSED_FILES="$(get_not_processed_files "$INPUT_STAGE_DIR" "$OUTPUT_STAGE_DIR" "video_")"
  notify_work_completed "${PROCESS}-scan"
  if [ -z "$NOT_PROCESSED_FILES" ]; then
    continue
  fi

  echo "$NOT_PROCESSED_FILES" | while IFS= read -r LATEST_NOT_PROCESSED_FILE; do
    request_cpu_time "${PROCESS}-conversion" "8"

    LATEST_NOT_PROCESSED_PATH="$INPUT_STAGE_DIR/$LATEST_NOT_PROCESSED_FILE"
    log "Processing: $LATEST_NOT_PROCESSED_PATH"

    FILE_DATETIME="$(strip "$LATEST_NOT_PROCESSED_FILE" "video_" ".h264")"
    FILE_NAME="video_${FILE_DATETIME}.mp4"
    FILE_PATH="$OUTPUT_STAGE_DIR/$FILE_NAME"


    log "Starting h264 -> mp4 conversion"
    if ffmpeg -nostdin -y -threads 1 -loglevel error -i "$LATEST_NOT_PROCESSED_PATH" -c:v copy -an "$FILE_PATH"; then
      log "Done h264 -> mp4 conversion"
      rm "$LATEST_NOT_PROCESSED_PATH"
      echo "$LATEST_NOT_PROCESSED_FILE" >> "$PROCESSED_PATH"
    fi

    notify_work_completed "${PROCESS}-conversion"
  done

done
