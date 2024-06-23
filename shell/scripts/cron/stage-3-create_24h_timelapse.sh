#!/bin/bash

# shellcheck source=shell/scripts/lib.sh
source "$LIB_INIT_FILE"
ensure_env

INPUT_STAGE="video/snapshot_annotate"
OUTPUT_STAGE="video/24_timelapse"
# INPUT:
# - video/snapshot_annotate/snapshot_annotated_20240505_101501.jpg
# OUTPUT:
# - video/24_timelapse/pi4b_24_timelapse.mp4

PROCESS="$OUTPUT_STAGE"

while true; do

  request_cpu_time "${PROCESS}-scan" "1"

  VIDEO_24_TIMELAPSE_FPS="$(get_or_set_config "video.24_timelapse.fps" "4")"

  MACHINE_NAME="$(get_required_config "name")"

  INPUT_STAGE_DIR="$(ensure_stage_dir "$INPUT_STAGE")"
  OUTPUT_STAGE_DIR="$(ensure_stage_dir "$OUTPUT_STAGE")"
  PROCESSED_PATH="$OUTPUT_STAGE_DIR/processed.txt"

  NOT_PROCESSED_FILES="$(get_not_processed_files "$INPUT_STAGE_DIR" "$OUTPUT_STAGE_DIR" "snapshot_annotated_")"
  notify_work_completed "${PROCESS}-scan"
  if [ -z "$NOT_PROCESSED_FILES" ]; then
    continue
  fi

  LATEST_NOT_PROCESSED_FILE="$(echo "$NOT_PROCESSED_FILES" | tail -n 1)"
  LATEST_NOT_PROCESSED_PATH="$INPUT_STAGE_DIR/$LATEST_NOT_PROCESSED_FILE"

  # Skip earlier files
  FILES_TO_SKIP="$(echo "$NOT_PROCESSED_FILES" | grep -v "$LATEST_NOT_PROCESSED_FILE")"
  if [ -n "$FILES_TO_SKIP" ]; then
    echo "$FILES_TO_SKIP" >> "$PROCESSED_PATH"
  fi

  log "Processing: $LATEST_NOT_PROCESSED_PATH"
  FILE_NAME="${MACHINE_NAME}_24_timelapse.mp4"
  FILE_PATH="$OUTPUT_STAGE_DIR/$FILE_NAME"

  request_cpu_time "${PROCESS}-create-timelapse" "$(ls -1 "$INPUT_STAGE_DIR/"*.jpg | wc -l)"
  ffmpeg -threads 1 -y -nostdin -pattern_type glob -i "$INPUT_STAGE_DIR/*.jpg" -framerate 1 -r 30 -c:v libx264 -pix_fmt yuv420p "$FILE_PATH"
  echo "$LATEST_NOT_PROCESSED_FILE" >> "$PROCESSED_PATH"
  notify_work_completed "${PROCESS}-create-timelapse"

done
