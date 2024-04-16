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

SEGMENT_DURATION_SECONDS="600"
MACHINE_NAME="$(get_required_config "name")"
VID_CONFIG_FILE="$(get_required_config "video-config-file")"

PUBLISHER="LIGHT_LEVEL"
register_publisher "$PUBLISHER"
create_hour_base_image

while true; do
  if ! is_scale_suspended; then
    START_DATE_TIME="$(get_current_date_time_compact)"

    log "Capturing image for light level"
    LIGHT_LEVEL="$("$REPO_DIR/shell/scripts/video/capture-light-level.sh")"
    log "Light level is: $LIGHT_LEVEL"
    LIGHT_LEVEL_FILE="$TMP_DIR/$MACHINE_NAME.jpg"
    draw_text_bl "$TMP_DIR/light_level.jpg" "$LIGHT_LEVEL_FILE" "$(get_current_date_time_dashed)"
    upload_file "$LIGHT_LEVEL_FILE" "image/jpg"
    publish_measurement_single "$PUBLISHER" "image_analysis" "light_level=$LIGHT_LEVEL"

    log "Capturing image for timelapse image"
    embed_hour_image
    upload_file "$(get_timelapse_image)" "image/jpg"

    declare LIGHT_LEVEL_INT="${LIGHT_LEVEL%%.*}"

    if [[ "$LIGHT_LEVEL_INT" -le "5" ]]; then
      log "Light level too low to record video: $LIGHT_LEVEL"

      if is_night; then
        update_period
        MIN_LOW_LIGHT_PERIOD="$(( 20 * 60 ))"
        SLEEP_LOW_LIGHT="$(( PERIOD > MIN_LOW_LIGHT_PERIOD ? PERIOD : MIN_LOW_LIGHT_PERIOD ))"
        log "Sleeping for $SLEEP_LOW_LIGHT"
        sleep "$SLEEP_LOW_LIGHT"
        continue
      fi
    fi

    FILE_NAME="video_$START_DATE_TIME.h264"
    FILE_PATH="$(get_video_dir)/$FILE_NAME"

    log "Recording segment: $FILE_NAME"
    libcamera-vid -c "$VID_CONFIG_FILE" -t "${SEGMENT_DURATION_SECONDS}000" -o "$FILE_PATH"
  else
    log_warn "Video recording suspended"
  fi

  update_period
  log "Period is: $PERIOD s"
  sleep "$PERIOD"

done
