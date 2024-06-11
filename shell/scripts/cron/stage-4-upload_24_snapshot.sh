#!/bin/bash

# shellcheck source=shell/scripts/lib.sh
source "$LIB_INIT_FILE"
ensure_env

INPUT_STAGE="video/24_snapshot"
OUTPUT_STAGE="video/24_snapshot_upload"
# INPUT:
# - video/24_snapshot/pi4b_24.jpg
# OUTPUT:
# - none

while true; do
  sleep 30

  MACHINE_NAME="$(get_required_config "name")"

  LOCAL_STAGE_DIR="$(ensure_stage_dir "$OUTPUT_STAGE")"
  PROCESSED_PATH="$LOCAL_STAGE_DIR/processed.txt"
  touch "$PROCESSED_PATH"

  NOT_PROCESSED_FILES=$(diff --new-line-format="" --unchanged-line-format="" --old-line-format="%L" <(ls -1 "$INPUT_STAGE") <(cat "$PROCESSED_PATH"))
  LATEST_NOT_PROCESSED_FILE="$(echo "$NOT_PROCESSED_FILES" | tail -n 1)"
  LATEST_NOT_PROCESSED_PATH="$INPUT_STAGE/$LATEST_NOT_PROCESSED_FILE"

  if [ -z "$LATEST_NOT_PROCESSED_PATH" ]; then
    continue
  fi

  FILE_NAME="${MACHINE_NAME}_24.jpg"
  FILE_PATH="$LOCAL_STAGE_DIR/$FILE_NAME"

  # Does not exist or has changed
  if [ ! -f "$FILE_PATH" ] || ! cmp -s "$FILE_PATH" "$LATEST_NOT_PROCESSED_PATH"; then
    if cp -f "$LATEST_NOT_PROCESSED_PATH" "$FILE_PATH"; then
      if [ -f "$FILE_PATH" ]; then
        if upload_file "$FILE_PATH" "image/jpg"; then
          #echo "$LATEST_NOT_PROCESSED_FILE" >> "$PROCESSED_PATH"
          continue
        fi
      fi
    fi
  fi

done