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
  LATEST_NOT_PROCESSED_FILE="$(echo "$NOT_PROCESSED_FILES" | head -n 1)"
  LATEST_NOT_PROCESSED_PATH="$INPUT_STAGE_DIR/$LATEST_NOT_PROCESSED_FILE"

  if [ -z "$LATEST_NOT_PROCESSED_FILE" ]; then
    continue
  fi
  log "Processing: $LATEST_NOT_PROCESSED_PATH"

  FILE_NAME="${MACHINE_NAME}_24_timelapse.mp4"
  FILE_PATH="$OUTPUT_STAGE_DIR/$FILE_NAME"

  if [[ ! -f "$FILE_PATH" ]]; then
    request_cpu_time "${PROCESS}-create-first-frame" "30"
    if ! ffmpeg -y -framerate "$VIDEO_24_TIMELAPSE_FPS" -i "$LATEST_NOT_PROCESSED_PATH" -c:v libx264 -r "$VIDEO_24_TIMELAPSE_FPS" -pix_fmt yuv420p "$FILE_PATH"; then
      continue
    fi
  else
    NEW_FRAME_VIDEO_PATH="$OUTPUT_STAGE_DIR/${MACHINE_NAME}_24_timelapse_processing_new_vid.mp4"
    FRAME_DURATION="0$(echo "scale=4; 1/$VIDEO_24_TIMELAPSE_FPS" | bc)"

    request_cpu_time "${PROCESS}-create-next-frame" "20"
    if ! ffmpeg -y -loop 1 -i "$LATEST_NOT_PROCESSED_PATH" -c:v libx264 -t "$FRAME_DURATION" -pix_fmt yuv420p "$NEW_FRAME_VIDEO_PATH"; then
      rm "$NEW_FRAME_VIDEO_PATH" 2> /dev/null
      continue
    fi

    TMP_OUTPUT_PATH="$OUTPUT_STAGE_DIR/${MACHINE_NAME}_24_timelapse_processing_tmp_output.mp4"
    CONCAT_LIST_PATH="$OUTPUT_STAGE_DIR/concat_list.txt"
    {
      echo "file '$FILE_PATH'"
      echo "file '$NEW_FRAME_VIDEO_PATH'"
    } > "$CONCAT_LIST_PATH"

    request_cpu_time "${PROCESS}-join-next-frame" "40"
    if ffmpeg -y -f concat -safe 0 -i "$CONCAT_LIST_PATH" -c copy "$TMP_OUTPUT_PATH"; then
      if cp -f "$TMP_OUTPUT_PATH" "$FILE_PATH"; then
        echo "$LATEST_NOT_PROCESSED_FILE" >> "$PROCESSED_PATH"
      fi
    fi

    rm "$NEW_FRAME_VIDEO_PATH" 2> /dev/null
    rm "$TMP_OUTPUT_PATH" 2> /dev/null
    rm "$CONCAT_LIST_PATH" 2> /dev/null
  fi

done
