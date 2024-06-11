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

PREV_HOUR=""
while true; do
  sleep 30

  MACHINE_NAME="$(get_required_config "name")"

  SEGMENT_DURATION_SECONDS="$(get_or_set_config "video.segment_duration_seconds" "300")"
  IMAGE_CONFIG_FILE="$(get_required_config "image-config-file")"
  TIMELAPSE_IMAGE_WIDTH="$(get_required_config "width" "$IMAGE_CONFIG_FILE")"
  TIMELAPSE_IMAGE_WIDTH="$(get_required_config "height""$IMAGE_CONFIG_FILE")"

  LOCAL_STAGE_DIR="$(ensure_stage_dir "$OUTPUT_STAGE")"
  PROCESSED_PATH="$LOCAL_STAGE_DIR/processed.txt"
  touch "$PROCESSED_PATH"

  NOT_PROCESSED_FILES=$(diff --new-line-format="" --unchanged-line-format="" --old-line-format="%L" <(ls -1 "$INPUT_STAGE") <(cat "$PROCESSED_PATH"))
  LATEST_NOT_PROCESSED_FILE="$(echo "$NOT_PROCESSED_FILES" | head -n 1)"
  LATEST_NOT_PROCESSED_PATH="$INPUT_STAGE/$LATEST_NOT_PROCESSED_FILE"

  if [ -z "$LATEST_NOT_PROCESSED_PATH" ]; then
    continue
  fi

  FILE_NAME="${MACHINE_NAME}_24_timelapse.mp4"
  FILE_PATH="$LOCAL_STAGE_DIR/$FILE_NAME"

  if [[ ! -f "$FILE_PATH" ]]; then
    if ! ffmpeg -framerate 30 -i "$LATEST_NOT_PROCESSED_PATH" -c:v libx264 -r 30 -pix_fmt yuv420p "$FILE_NAME"; then
      continue
    fi
  else
    NEW_FRAME_VIDEO_PATH="$LOCAL_STAGE_DIR/${MACHINE_NAME}_24_timelapse_processing_new_vid.mp4"
    if ! ffmpeg -loop 1 -i "$LATEST_NOT_PROCESSED_PATH" -c:v libx264 -t "0.03333" -pix_fmt yuv420p "$NEW_FRAME_VIDEO_PATH"; then
      rm "$NEW_FRAME_VIDEO_PATH" 2> /dev/null
      continue
    fi

    TMP_OUTPUT_PATH="$LOCAL_STAGE_DIR/${MACHINE_NAME}_24_timelapse_processing_tmp_output.mp4"
    CONCAT_LIST_PATH="$LOCAL_STAGE_DIR/concat_list.txt"
    {
      echo "file '$FILE_PATH'"
      echo "file '$NEW_FRAME_VIDEO_PATH'"
    } > "$CONCAT_LIST_PATH"

    if ffmpeg -f concat -safe 0 -i "$CONCAT_LIST_PATH" -c copy "$TMP_OUTPUT_PATH"; then
      if cp -f "$TMP_OUTPUT_PATH" "$FILE_PATH"; then
        echo "$LATEST_NOT_PROCESSED_FILE" >> "$PROCESSED_PATH"
      fi
    fi

    rm "$NEW_FRAME_VIDEO_PATH" 2> /dev/null
    rm "$TMP_OUTPUT_PATH" 2> /dev/null
    rm "$CONCAT_LIST_PATH" 2> /dev/null
  fi

done