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
else
  VID_CONFIG_FILE="$REPO_DIR/shell/scripts/video/video-config-ir.txt"
fi

while true; do
  if ! is_scale_suspended; then
    START_DATE_TIME="$(get_current_date_time_compact)"

    FILE_NAME="video_$START_DATE_TIME.h264"
    FILE_PATH="$OUTPUT_DIR/$FILE_NAME"

    log "Recording segment: $FILE_NAME"
    libcamera-vid -c "$VID_CONFIG_FILE" -t "${SEGMENT_DURATION}000" -o "$FILE_PATH"
  else
    log_warn "Video recording suspended"
  fi

  update_period
  log "Period is: $PERIOD s"
  sleep "$PERIOD"

done
