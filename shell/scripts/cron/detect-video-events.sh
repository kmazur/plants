#!/bin/bash

# shellcheck source=shell/scripts/lib.sh
source "$LIB_INIT_FILE"
ensure_env

MIN_PERIOD="${1:-20}"
MAX_PERIOD="${2:-600}"
PERIOD="$MIN_PERIOD"

CAMERA_CONFIG_DIR="$REPO_DIR/shell/scripts/video/config"
MOTION_DETECTION_CONFIG_FILE="$CAMERA_CONFIG_DIR/motion-config-$MACHINE_NAME.txt"

function can_process() {
  local HOUR="$(get_current_hour)"
  if [[ "$HOUR" == "0"* ]]; then
    HOUR="${HOUR:1}"
  fi

  if is_scale_suspended; then
    return 1
  elif [[ "$(get_cpu_temp_int)" -gt "60" ]]; then
    return 2
  else
    return 0
  fi
}

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
    if ! can_process; then
      break
    fi

    declare STUB="${FILE%.h264}"
    if [ -f "$DIR/$STUB.motion_detected" ]; then
      continue
    fi

    BEFORE_TIME=$(get_current_epoch_seconds)
    log "Processing: $FILE"
    "$BIN_DIR/motion_detector" "$DIR/$FILE" "$OUTPUT_DIR" "$MOTION_DETECTION_CONFIG_FILE"
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

  if can_process; then
    PROCESS_VIDEO_DIR="$(get_video_dir)"
    log "Processing video files from: $PROCESS_VIDEO_DIR"
    detect_video_events "$PROCESS_VIDEO_DIR" "$(get_video_segment_dir)"
  else
    log_warn "Video detection suspended"
  fi

  if can_process; then
    PROCESS_VIDEO_DIR="$(get_video_dir "$(get_yesterday_date_compact)")"
    log "Processing video files from: $PROCESS_VIDEO_DIR"
    detect_video_events "$PROCESS_VIDEO_DIR" "$(get_video_segment_dir "$(get_yesterday_date_compact)")"
  else
    log_warn "Video detection suspended"
  fi

  update_period
  log "Period is: $PERIOD s"
  sleep "$PERIOD"
done
