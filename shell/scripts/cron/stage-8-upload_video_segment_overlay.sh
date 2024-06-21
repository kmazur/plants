#!/bin/bash

# shellcheck source=shell/scripts/lib.sh
source "$LIB_INIT_FILE"
ensure_env

INPUT_STAGE="video/video_segments_overlay"
OUTPUT_STAGE="video/upload_video_segments_overlay"
# INPUT:
# - video/video_segments_overlay/video_segment_overlay_20240505_101501_0.3333_5.1000.mp4
# OUTPUT:
# - none

PROCESS="$OUTPUT_STAGE"

while true; do

  request_cpu_time "${PROCESS}-scan" "1"

  MACHINE_NAME="$(get_required_config "name")"

  INPUT_STAGE_DIR="$(ensure_stage_dir "$INPUT_STAGE")"
  OUTPUT_STAGE_DIR="$(ensure_stage_dir "$OUTPUT_STAGE")"
  PROCESSED_PATH="$OUTPUT_STAGE_DIR/processed.txt"

  NOT_PROCESSED_FILES="$(get_not_processed_files "$INPUT_STAGE_DIR" "$OUTPUT_STAGE_DIR" "video_segment_overlay_")"
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

  FILE_NAME="vid_segment_short_${MACHINE_NAME}.mp4"
  FILE_PATH="$OUTPUT_STAGE_DIR/$FILE_NAME"

  # Does not exist or has changed
  if [ ! -f "$FILE_PATH" ] || ! cmp -s "$FILE_PATH" "$LATEST_NOT_PROCESSED_PATH"; then
    log "Processing: $LATEST_NOT_PROCESSED_PATH"
    if cp -f "$LATEST_NOT_PROCESSED_PATH" "$FILE_PATH"; then
      if [ -f "$FILE_PATH" ]; then
        request_cpu_time "${PROCESS}-upload" "3"
        if upload_file "$FILE_PATH" "video/mp4"; then
          echo "$LATEST_NOT_PROCESSED_FILE" >> "$PROCESSED_PATH"
        fi
        notify_work_completed "${PROCESS}-upload"
      fi
    fi
  fi

done
