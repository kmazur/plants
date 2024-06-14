#!/bin/bash

# shellcheck source=shell/scripts/lib.sh
source "$LIB_INIT_FILE"
ensure_env

INPUT_STAGE="video/segments"
OUTPUT_STAGE="video/video_segments"
# INPUT:
# - video/segments/scores_20240505_101501_0.3333_5.1000.txt
# - video/mp4/video_20240505_101501.mp4
# OUTPUT:
# - video/video_segments/video_segment_20240505_101501_0.3333_5.1000.mp4

PROCESS="$OUTPUT_STAGE"

while true; do

  request_cpu_time "${PROCESS}-scan" "1"

  INPUT_STAGE_DIR="$(ensure_stage_dir "$INPUT_STAGE")"
  OUTPUT_STAGE_DIR="$(ensure_stage_dir "$OUTPUT_STAGE")"
  PROCESSED_PATH="$OUTPUT_STAGE_DIR/processed.txt"

  NOT_PROCESSED_FILES="$(get_not_processed_files "$INPUT_STAGE_DIR" "$OUTPUT_STAGE_DIR" "scores_")"
  LATEST_NOT_PROCESSED_FILE="$(echo "$NOT_PROCESSED_FILES" | head -n 1)"
  LATEST_NOT_PROCESSED_PATH="$INPUT_STAGE_DIR/$LATEST_NOT_PROCESSED_FILE"

  if [ -z "$LATEST_NOT_PROCESSED_FILE" ]; then
    continue
  fi
  log "Processing: $LATEST_NOT_PROCESSED_PATH"

  FILE_DATETIME_AND_SEGMENT="$(strip "$LATEST_NOT_PROCESSED_FILE" "scores_" ".txt")"
  FILE_DATETIME="$(echo "$FILE_DATETIME_AND_SEGMENT" | cut -d '_' -f 1,2)"
  SEGMENT_START="$(echo "$FILE_DATETIME_AND_SEGMENT" | cut -d '_' -f 3)"
  SEGMENT_END="$(echo "$FILE_DATETIME_AND_SEGMENT" | cut -d '_' -f 4)"

  FILE_NAME="video_segment_${FILE_DATETIME_AND_SEGMENT}.mp4"
  FILE_PATH="$OUTPUT_STAGE_DIR/$FILE_NAME"

  DURATION=$(calc "$SEGMENT_END - $SEGMENT_START")

  log "Starting motion segment extraction"
  request_cpu_time "${PROCESS}-motion-segments" "40"

  if ffmpeg -i "$LATEST_NOT_PROCESSED_PATH" -ss "$SEGMENT_START" -t "$DURATION" -c copy -an "$FILE_PATH"; then
    log "Done motion segment extraction"
    echo "$LATEST_NOT_PROCESSED_FILE" >> "$PROCESSED_PATH"
  fi
done
