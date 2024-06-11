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

SLEEP_PID=""
# Signal handlers
handle_wakeup() {
    log "Waking up"
    if [ -n "$SLEEP_PID" ]; then
        kill "$SLEEP_PID"
    fi
}

trap 'handle_wakeup' SIGUSR1

SLEEP_INTERVAL="60m"

while true; do
  log "Going to sleep for $SLEEP_INTERVAL"

  sleep "$SLEEP_INTERVAL" &
  SLEEP_PID="$!"
  log "Sleeping PID: $SLEEP_PID"
  wait
  unset sleep_pid

  IMAGE_CONFIG_FILE="$(get_required_config "image-config-file")"
  IMAGE_WIDTH="$(get_required_config "width" "$IMAGE_CONFIG_FILE")"

  INPUT_STAGE_DIR="$(ensure_stage_dir "$INPUT_STAGE")"
  OUTPUT_STAGE_DIR="$(ensure_stage_dir "$OUTPUT_STAGE")"
  PROCESSED_PATH="$OUTPUT_STAGE_DIR/processed.txt"
  touch "$PROCESSED_PATH"

  NOT_PROCESSED_FILES=$(diff --new-line-format="" --unchanged-line-format="" --old-line-format="%L" <(ls -1 "$INPUT_STAGE_DIR" | grep "snapshot_") <(cat "$PROCESSED_PATH"))
  LATEST_NOT_PROCESSED_FILE="$(echo "$NOT_PROCESSED_FILES" | head -n 1)"
  LATEST_NOT_PROCESSED_PATH="$INPUT_STAGE_DIR/$LATEST_NOT_PROCESSED_FILE"

  if [ -z "$LATEST_NOT_PROCESSED_FILE" ]; then
    continue
  fi
  log "Processing: $LATEST_NOT_PROCESSED_PATH"

  FILE_DATETIME="$(strip "$LATEST_NOT_PROCESSED_FILE" "snapshot_" ".jpg")"
  FILE_NAME="snapshot_annotated_${FILE_DATETIME}.jpg"
  FILE_PATH="$OUTPUT_STAGE_DIR/$FILE_NAME"

  FONT_SIZE="$(( IMAGE_WIDTH / 35))"
  if draw_text_bl "$LATEST_NOT_PROCESSED_PATH" "$FILE_PATH" "$(date_compact_to_dashed "$FILE_DATETIME")" "120" "yellow" "3"; then
    if [ -f "$FILE_PATH" ]; then
      echo "$LATEST_NOT_PROCESSED_FILE" >> "$PROCESSED_PATH"
    fi
  fi

done
