#!/bin/bash

# shellcheck source=shell/scripts/lib.sh
source "$LIB_INIT_FILE"
ensure_env

INPUT_STAGE=""
OUTPUT_STAGE="video/raw"
# INPUT:
# - none
# OUTPUT:
# - video/raw/snapshot_20240505_101501.jpg
# - video/raw/light_level_20240505_101501.txt
# - video/raw/video_20240505_101501.h264

PROCESS="$OUTPUT_STAGE"

while true; do
  SEGMENT_DURATION_SECONDS="$(get_or_set_config "video.segment_duration_seconds" "300")"
  VID_CONFIG_FILE="$(get_required_config "video-config-file")"
  IMAGE_CONFIG_FILE="$(get_required_config "image-config-file")"

  OUTPUT_STAGE_DIR="$(ensure_stage_dir "$OUTPUT_STAGE")"

  log "Capturing image"
  START_DATE_TIME="$(get_current_date_time_compact)"
  IMAGE_CAPTURE_FILE="snapshot_${START_DATE_TIME}.jpg"
  IMAGE_CAPTURE_PATH="$OUTPUT_STAGE_DIR/$IMAGE_CAPTURE_FILE"

  libcamera-still -c "$IMAGE_CONFIG_FILE" -o "$IMAGE_CAPTURE_PATH" -n -t 1 &> /dev/null
  log "Image captured at $START_DATE_TIME"

  LIGHT_LEVEL="$("$BIN_DIR/light_level" "$IMAGE_CAPTURE_PATH")"
  log "Light level is: $LIGHT_LEVEL"
  declare LIGHT_LEVEL_INT="${LIGHT_LEVEL%%.*}"

  LIGHT_LEVEL_FILE="light_level_${START_DATE_TIME}.txt"
  LIGHT_LEVEL_PATH="$OUTPUT_STAGE_DIR/$LIGHT_LEVEL_FILE"
  echo "$LIGHT_LEVEL_INT" > "$LIGHT_LEVEL_PATH"

  if [[ "$LIGHT_LEVEL_INT" -le "5" ]]; then
    log "Light level too low to record video: $LIGHT_LEVEL"

    if is_night; then
      SLEEP_LOW_LIGHT="$(( 20 * 60 ))"
      log "Sleeping for $SLEEP_LOW_LIGHT"
      sleep "$SLEEP_LOW_LIGHT"
      continue
    else
      log "Sleeping for $SEGMENT_DURATION_SECONDS"
      sleep "$SEGMENT_DURATION_SECONDS"
      continue
    fi
  fi

  log "Recording video for ${SEGMENT_DURATION_SECONDS} seconds"
  START_DATE_TIME="$(get_current_date_time_compact)"
  VIDEO_FILE_NAME="video_$START_DATE_TIME.h264"
  VIDEO_FILE_PATH="$OUTPUT_STAGE_DIR/$VIDEO_FILE_NAME"

  libcamera-vid -c "$VID_CONFIG_FILE" -t "${SEGMENT_DURATION_SECONDS}000" -o "$VIDEO_FILE_PATH"
  log "Done recording video"

done
