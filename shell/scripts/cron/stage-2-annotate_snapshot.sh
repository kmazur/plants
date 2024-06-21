#!/bin/bash

# shellcheck source=shell/scripts/lib.sh
source "$LIB_INIT_FILE"
ensure_env

INPUT_STAGE="video/raw"
OUTPUT_STAGE="video/snapshot_annotate"
# INPUT:
# - video/raw/snapshot_20240505_101501.jpg
# OUTPUT:
# - video/snapshot_annotate/snapshot_annotated_20240505_101501.jpg

PROCESS="$OUTPUT_STAGE"

while true; do

  request_cpu_time "${PROCESS}-scan" "1"

  IMAGE_CONFIG_FILE="$(get_required_config "image-config-file")"
  IMAGE_WIDTH="$(get_required_config "width" "$IMAGE_CONFIG_FILE")"

  INPUT_STAGE_DIR="$(ensure_stage_dir "$INPUT_STAGE")"
  OUTPUT_STAGE_DIR="$(ensure_stage_dir "$OUTPUT_STAGE")"
  PROCESSED_PATH="$OUTPUT_STAGE_DIR/processed.txt"

  NOT_PROCESSED_FILES="$(get_not_processed_files "$INPUT_STAGE_DIR" "$OUTPUT_STAGE_DIR" "snapshot_")"
  notify_work_completed "${PROCESS}-scan"
  if [ -z "$NOT_PROCESSED_FILES" ]; then
    continue
  fi

  echo "$NOT_PROCESSED_FILES" | while IFS= read -r LATEST_NOT_PROCESSED_FILE; do
    request_cpu_time "${PROCESS}-draw-text" "2"

    LATEST_NOT_PROCESSED_PATH="$INPUT_STAGE_DIR/$LATEST_NOT_PROCESSED_FILE"
    log "Processing: $LATEST_NOT_PROCESSED_PATH"

    FILE_DATETIME="$(strip "$LATEST_NOT_PROCESSED_FILE" "snapshot_" ".jpg")"
    FILE_NAME="snapshot_annotated_${FILE_DATETIME}.jpg"
    FILE_PATH="$OUTPUT_STAGE_DIR/$FILE_NAME"


    FONT_SIZE="$(( IMAGE_WIDTH / 35))"
    if draw_text_bl "$LATEST_NOT_PROCESSED_PATH" "$FILE_PATH" "$(date_compact_to_dashed "$FILE_DATETIME")" "$FONT_SIZE" "yellow" "3"; then
      if [ -f "$FILE_PATH" ]; then
        echo "$LATEST_NOT_PROCESSED_FILE" >> "$PROCESSED_PATH"
      fi
    fi
    notify_work_completed "${PROCESS}-draw-text"
  done

done
