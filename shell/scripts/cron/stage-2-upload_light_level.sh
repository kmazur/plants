#!/bin/bash

# shellcheck source=shell/scripts/lib.sh
source "$LIB_INIT_FILE"
ensure_env

INPUT_STAGE="video/raw"
OUTPUT_STAGE="video/light_level"
# INPUT:
# - video/raw/light_level_20240505_101501.txt
# OUTPUT:
# - none

PUBLISHER="LIGHT_LEVEL"

while true; do
  sleep 30

  MACHINE_NAME="$(get_required_config "name")"

  LOCAL_STAGE_DIR="$(ensure_stage_dir "$OUTPUT_STAGE")"
  PROCESSED_PATH="$LOCAL_STAGE_DIR/processed.txt"
  touch "$PROCESSED_PATH"

  NOT_PROCESSED_FILES=$(diff --new-line-format="" --unchanged-line-format="" --old-line-format="%L" <(ls -1 "$INPUT_STAGE") <(cat "$PROCESSED_PATH"))
  LATEST_NOT_PROCESSED_FILE="$(echo "$NOT_PROCESSED_FILES" | head -n 1)"
  LATEST_NOT_PROCESSED_PATH="$INPUT_STAGE/$LATEST_NOT_PROCESSED_FILE"

  if [ -z "$LATEST_NOT_PROCESSED_PATH" ]; then
    continue
  fi

  LIGHT_LEVEL="$(cat "$LATEST_NOT_PROCESSED_PATH")"
  if publish_measurement_single "$PUBLISHER" "image_analysis" "light_level=$LIGHT_LEVEL"; then
    echo "$LATEST_NOT_PROCESSED_FILE" >> "$PROCESSED_PATH"
  fi

done