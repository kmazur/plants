#!/bin/bash

# shellcheck source=shell/scripts/lib.sh
source "$LIB_INIT_FILE"
ensure_env

MIN_PERIOD="${1:-0}"
MAX_PERIOD="${2:-300}"
PERIOD="$MIN_PERIOD"

function update_period() {
  PERIOD="$(get_scaled_inverse_value "$MIN_PERIOD" "$MAX_PERIOD")"
}


OUTPUT_DIR="$VIDEO_DIR"
SEGMENT_DURATION_SECONDS="600"
MACHINE_NAME="$(get_required_config "name")"
if [[ "$MACHINE_NAME" == "birdbox-ctrl" ]]; then
  VID_CONFIG_FILE="$REPO_DIR/shell/scripts/video/video-config-ctrl.txt"
elif [[ "$MACHIINE_NAME" == "pi4b" ]]; then
  VID_CONFIG_FILE="$REPO_DIR/shell/scripts/video/video-config-pi4b.txt"
else
  VID_CONFIG_FILE="$REPO_DIR/shell/scripts/video/video-config-ir.txt"
fi

while true; do
  if ! is_scale_suspended; then
    START_DATE_TIME="$(get_current_date_time_compact)"

    if [[ "$MACHINE_NAME" != "birdbox-ir" ]]; then
      log "Capturing image for light level"
      LIGHT_LEVEL="$("$REPO_DIR/shell/scripts/video/capture-light-level.sh")"
      update_measurement_single "image_analysis" "light_level=$LIGHT_LEVEL"

      if [ "$(echo "$LIGHT_LEVEL <= 5" | bc)" -eq 1 ]; then
        log "Light level too low to record video: $LIGHT_LEVEL"

        HOUR="$(get_current_hour)"
        if [[ "$HOUR" -le "5" || "$HOUR" -ge "22" ]]; then
          update_period
          MIN_LOW_LIGHT_PERIOD="$(( 20 * 60 ))"
          SLEEP_LOW_LIGHT="$(( PERIOD > MIN_LOW_LIGHT_PERIOD ? PERIOD : MIN_LOW_LIGHT_PERIOD ))"
          sleep "$SLEEP_LOW_LIGHT"
          continue
        fi
      fi
    fi

    FILE_NAME="video_$START_DATE_TIME.h264"
    FILE_PATH="$OUTPUT_DIR/$FILE_NAME"

    log "Recording segment: $FILE_NAME"
    libcamera-vid -c "$VID_CONFIG_FILE" -t "${SEGMENT_DURATION_SECONDS}000" -o "$FILE_PATH"
  else
    log_warn "Video recording suspended"
  fi

  update_period
  log "Period is: $PERIOD s"
  sleep "$PERIOD"

done
