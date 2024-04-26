#!/bin/bash

# shellcheck source=shell/scripts/lib.sh
source "$LIB_INIT_FILE"
ensure_env

MIN_PERIOD="${1:-20}"
MAX_PERIOD="${2:-600}"
PERIOD="$MIN_PERIOD"

function update_period() {
  PERIOD="$(get_scaled_inverse_value "$MIN_PERIOD" "$MAX_PERIOD")"
}

function detect_video_events() {
  local DIR="$1"
  local OUTPUT_DIR="$2"
  local FILES="$(ls -1tr "$DIR" | grep -P '^video_.*\.h264' | head -n -1)"
  local FILE_COUNT="$(echo -n "$FILES" | grep -c '^')"
  log "Processing $FILE_COUNT h264 files"

  for FILE in $FILES; do
    if is_scale_suspended; then
      break
    fi

    declare STUB="${FILE%.h264}"
    if [ -f "$DIR/$STUB.motion_detected" ]; then
      continue
    fi

    BEFORE_TIME=$(get_current_epoch_seconds)
    log "Processing: $FILE"
    "$BIN_DIR/motion_detector" "$DIR/$FILE" "$OUTPUT_DIR"
    EXIT_STATUS="$?"
    AFTER_TIME=$(get_current_epoch_seconds)
    log "Processing $FILE took: $(( AFTER_TIME - BEFORE_TIME )) s"

    if [[ "$EXIT_STATUS" == "0" ]]; then
      touch "$DIR/$STUB.motion_detected"
    else
      log_error "Processing failed with exit status: $EXIT_STATUS"
    fi

    update_period
    log "Period is: $PERIOD s"
    sleep "$PERIOD"
  done
}

while true; do

  HOUR="$(get_current_hour)"
  SUNRISE="$(get_config "daylight.sunrise" "6")"
  SUNSET="$(get_config "daylight.sunset" "21")"
  SUNRISE_HOUR="${SUNRISE:9:2}"
  SUNSET_HOUR="${SUNSET:9:2}"

  if is_day; then
    log "It's not night: $SUNRISE_HOUR <= $HOUR <= $SUNSET_HOUR"
    update_period
    log "Period is: $PERIOD s"
    sleep "$PERIOD"
    continue
  fi

  if ! is_scale_suspended; then
    log "Processing: h264 files"
    detect_video_events "$(get_video_dir)" "$(get_video_segment_dir)"
    detect_video_events "$(get_video_dir "$(get_yesterday_date_compact)")" "$(get_video_segment_dir "$(get_yesterday_date_compact)")"
  else
    log_warn "Video detection suspended"
  fi

  update_period
  log "Period is: $PERIOD s"
  sleep "$PERIOD"
done
