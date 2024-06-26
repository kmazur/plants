#!/bin/bash

# shellcheck source=shell/scripts/lib.sh
source "$LIB_INIT_FILE"
ensure_env

INPUT_STAGE="video/snapshot_annotate"
OUTPUT_STAGE="video/24_snapshot"
# INPUT:
# - video/snapshot_annotate/snapshot_annotated_20240505_101501.jpg
# OUTPUT:
# - video/24_snapshot/pi4b_24.jpg

PREV_HOUR=""
PROCESS="$OUTPUT_STAGE"

while true; do

  request_cpu_time "${PROCESS}-scan" "1"

  MACHINE_NAME="$(get_required_config "name")"

  MAX_WIDTH="$(get_or_set_config "video.24_snapshot.max_width" "2000")"
  IMAGE_CONFIG_FILE="$(get_required_config "image-config-file")"
  TIMELAPSE_IMAGE_WIDTH="$(get_required_config "width" "$IMAGE_CONFIG_FILE")"
  TIMELAPSE_IMAGE_HEIGHT="$(get_required_config "height" "$IMAGE_CONFIG_FILE")"

  INPUT_STAGE_DIR="$(ensure_stage_dir "$INPUT_STAGE")"
  OUTPUT_STAGE_DIR="$(ensure_stage_dir "$OUTPUT_STAGE")"
  PROCESSED_PATH="$OUTPUT_STAGE_DIR/processed.txt"

  NOT_PROCESSED_FILES="$(get_not_processed_files "$INPUT_STAGE_DIR" "$OUTPUT_STAGE_DIR" "snapshot_annotated_")"
  notify_work_completed "${PROCESS}-scan"
  if [ -z "$NOT_PROCESSED_FILES" ]; then
    continue
  fi

  echo "$NOT_PROCESSED_FILES" | while IFS= read -r LATEST_NOT_PROCESSED_FILE; do
    LATEST_NOT_PROCESSED_PATH="$INPUT_STAGE_DIR/$LATEST_NOT_PROCESSED_FILE"
    log "Processing: $LATEST_NOT_PROCESSED_PATH"

    FILE_DATETIME="$(strip "$LATEST_NOT_PROCESSED_FILE" "snapshot_annotated_" ".jpg")"

    HOUR="${FILE_DATETIME:9:2}"
    HOUR="$((10#$HOUR))"

    if [[ -z "$PREV_HOUR" || "$PREV_HOUR" != "$HOUR" ]]; then
      FILE_NAME="${MACHINE_NAME}_24.jpg"
      FILE_PATH="$OUTPUT_STAGE_DIR/$FILE_NAME"

      if (( TIMELAPSE_IMAGE_WIDTH > MAX_WIDTH )); then
          NEW_WIDTH=$MAX_WIDTH
          NEW_HEIGHT=$(( TIMELAPSE_IMAGE_HEIGHT * MAX_WIDTH / TIMELAPSE_IMAGE_WIDTH ))
      else
          NEW_WIDTH=$TIMELAPSE_IMAGE_WIDTH
          NEW_HEIGHT=$TIMELAPSE_IMAGE_HEIGHT
      fi

      if [[ ! -f "$FILE_PATH" || "$(stat --printf="%s" "$FILE_PATH")" == "0" ]]; then
        request_cpu_time "${PROCESS}-create-blank-image" "4"
        if ! create_blank_image "$FILE_PATH" "$((NEW_WIDTH * 5))" "$((NEW_HEIGHT * 5))"; then
          notify_work_completed "${PROCESS}-create-blank-image"
          continue
        else
          notify_work_completed "${PROCESS}-create-blank-image"
        fi
      fi

      X="$(( (HOUR % 5) * NEW_WIDTH ))"
      Y="$(( (HOUR / 5) * NEW_HEIGHT ))"

      TMP_OUTPUT="$OUTPUT_STAGE_DIR/${MACHINE_NAME}_24_processing.jpg"

      request_cpu_time "${PROCESS}-embedd-image" "3"
      if ffmpeg -threads 1 -i "$FILE_PATH" -i "$LATEST_NOT_PROCESSED_PATH" -filter_complex \
             "[1:v] scale=$NEW_WIDTH:$NEW_HEIGHT [scaled]; [0:v][scaled] overlay=x=$X:y=$Y" -q:v "3" \
             -y "$TMP_OUTPUT" && cp -f "$TMP_OUTPUT" "$FILE_PATH"; then

        PREV_HOUR="$HOUR"
        echo "$LATEST_NOT_PROCESSED_FILE" >> "$PROCESSED_PATH"
      fi

      notify_work_completed "${PROCESS}-embedd-image"

      rm -f "$TMP_OUTPUT" 2> /dev/null
    else
      echo "$LATEST_NOT_PROCESSED_FILE" >> "$PROCESSED_PATH"
    fi
  done

done
