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

while true; do
  sleep 30

  INPUT_STAGE_DIR="$(ensure_stage_dir "$INPUT_STAGE")"
  OUTPUT_STAGE_DIR="$(ensure_stage_dir "$OUTPUT_STAGE")"
  PROCESSED_PATH="$OUTPUT_STAGE_DIR/processed.txt"
  touch "$PROCESSED_PATH"

  NOT_PROCESSED_FILES=$(diff --new-line-format="" --unchanged-line-format="" --old-line-format="%L" <(ls -1 "$INPUT_STAGE_DIR" | grep "video_") <(cat "$PROCESSED_PATH"))
  LATEST_NOT_PROCESSED_FILE="$(echo "$NOT_PROCESSED_FILES" | head -n 1)"
  LATEST_NOT_PROCESSED_PATH="$INPUT_STAGE_DIR/$LATEST_NOT_PROCESSED_FILE"

  if [ -z "$LATEST_NOT_PROCESSED_FILE" ]; then
    continue
  fi
  log "Processing: $LATEST_NOT_PROCESSED_PATH"

  FILE_DATETIME="$(strip "$LATEST_NOT_PROCESSED_FILE" "video_" ".h264")"
  FILE_NAME="video_${FILE_DATETIME}.mp4"
  FILE_PATH="$OUTPUT_STAGE_DIR/$FILE_NAME"

  if ffmpeg -y -loglevel error -i "$LATEST_NOT_PROCESSED_FILE" -c:v copy -an "$FILE_PATH"; then
    echo "$LATEST_NOT_PROCESSED_FILE" >> "$PROCESSED_PATH"
  fi

done
