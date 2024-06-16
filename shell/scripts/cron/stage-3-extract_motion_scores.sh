#!/bin/bash

# shellcheck source=shell/scripts/lib.sh
source "$LIB_INIT_FILE"
ensure_env

INPUT_STAGE="video/mp4"
OUTPUT_STAGE="video/motion_scores"
# INPUT:
# - video/mp4/video_20240505_101501.mp4
# OUTPUT:
# - video/motion_scores/scores_20240505_101501.txt

PROCESS="$OUTPUT_STAGE"

while true; do

  request_cpu_time "${PROCESS}-scan" "0.2"

  CAMERA_CONFIG_DIR="$REPO_DIR/shell/scripts/video/config"
  MOTION_DETECTION_CONFIG_FILE="$CAMERA_CONFIG_DIR/motion-config-$MACHINE_NAME.txt"

  INPUT_STAGE_DIR="$(ensure_stage_dir "$INPUT_STAGE")"
  OUTPUT_STAGE_DIR="$(ensure_stage_dir "$OUTPUT_STAGE")"
  PROCESSED_PATH="$OUTPUT_STAGE_DIR/processed.txt"

  NOT_PROCESSED_FILES="$(get_not_processed_files "$INPUT_STAGE_DIR" "$OUTPUT_STAGE_DIR" "video_")"
  LATEST_NOT_PROCESSED_FILE="$(echo "$NOT_PROCESSED_FILES" | head -n 1)"
  LATEST_NOT_PROCESSED_PATH="$INPUT_STAGE_DIR/$LATEST_NOT_PROCESSED_FILE"

  if [ -z "$LATEST_NOT_PROCESSED_FILE" ]; then
    continue
  fi
  log "Processing: $LATEST_NOT_PROCESSED_PATH"

  FILE_DATETIME="$(strip "$LATEST_NOT_PROCESSED_FILE" "video_" ".mp4")"
  FILE_NAME="scores_${FILE_DATETIME}.txt"
  FILE_PATH="$OUTPUT_STAGE_DIR/$FILE_NAME"

  log "Starting motion score detection"

  request_cpu_time "${PROCESS}-motion-score" "8"
  if "$BIN_DIR/motion_scorer" "$LATEST_NOT_PROCESSED_PATH" "$FILE_PATH" "$MOTION_DETECTION_CONFIG_FILE"; then
    if [ -f "$FILE_PATH" ]; then
      log "Done motion score detection"
      echo "$LATEST_NOT_PROCESSED_FILE" >> "$PROCESSED_PATH"
    fi
  fi

done
