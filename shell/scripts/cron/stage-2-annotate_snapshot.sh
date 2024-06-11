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

while true; do
  sleep 30

  LOCAL_STAGE_DIR="$(ensure_stage_dir "$OUTPUT_STAGE")"
  PROCESSED_PATH="$LOCAL_STAGE_DIR/processed.txt"
  touch "$PROCESSED_PATH"

  NOT_PROCESSED_FILES=$(diff --new-line-format="" --unchanged-line-format="" --old-line-format="%L" <(ls -1 "$INPUT_STAGE") <(cat "$PROCESSED_PATH"))
  LATEST_NOT_PROCESSED_FILE="$(echo "$NOT_PROCESSED_FILES" | head -n 1)"
  LATEST_NOT_PROCESSED_PATH="$INPUT_STAGE/$LATEST_NOT_PROCESSED_FILE"

  if [ -z "$LATEST_NOT_PROCESSED_PATH" ]; then
    continue
  fi

  FILE_DATETIME="$(strip "$LATEST_NOT_PROCESSED_FILE" "snapshot_" ".jpg")"
  FILE_NAME="snapshot_annotated_${FILE_DATETIME}.jpg"
  FILE_PATH="$LOCAL_STAGE_DIR/$FILE_NAME"

  if draw_text_bl "$LATEST_NOT_PROCESSED_PATH" "$FILE_PATH" "$(date_compact_to_dashed "$FILE_DATETIME")" "30" "yellow"; then
    if [ -f "$FILE_PATH" ]; then
      echo "$LATEST_NOT_PROCESSED_FILE" >> "$PROCESSED_PATH"
    fi
  fi

done
