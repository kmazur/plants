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

VIDEO_DIR_NOW="$VIDEO_DIR"

function detect_video_events() {
  local DIR="$1"
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
    "$BIN_DIR/motion_detector" "$DIR/$FILE"
    AFTER_TIME=$(get_current_epoch_seconds)
    log "Processing $FILE took: $(( AFTER_TIME - BEFORE_TIME )) s"

    touch "$DIR/$STUB.motion_detected"

    update_period
    log "Period is: $PERIOD s"
    sleep "$PERIOD"
  done
}


while true; do
  if ! is_scale_suspended; then
    log "Processing: h264 files"
    detect_video_events "$VIDEO_DIR_NOW"
  else
    log_warn "Video detection suspended"
  fi

  update_period
  log "Period is: $PERIOD s"
  sleep "$PERIOD"
done
