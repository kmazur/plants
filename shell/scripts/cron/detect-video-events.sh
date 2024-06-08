#!/bin/bash

# shellcheck source=shell/scripts/lib.sh
source "$LIB_INIT_FILE"
ensure_env

MIN_PERIOD="${1:-20}"
MAX_PERIOD="${2:-600}"
PERIOD="$MIN_PERIOD"

CAMERA_CONFIG_DIR="$REPO_DIR/shell/scripts/video/config"
MOTION_DETECTION_CONFIG_FILE="$CAMERA_CONFIG_DIR/motion-config-$MACHINE_NAME.txt"

function create_last_segment_animation() {
  log "Creating last segment animation"
  local DATE="$(get_current_date_compact)"
  local HOUR="$(get_current_hour)"
  if [[ "$HOUR" == "0"* ]]; then
    HOUR="${HOUR:1}"
  fi

  local VIDEO_OUTPUT_DIR="$(get_video_segment_dir)"
  local LAST_FILE="$(ls -1 "${VIDEO_OUTPUT_DIR}/"*with_overlay.mp4 | tail -n 1)"
  local LAST_UPLOADED_FILE="$([ -f "$TMP_DIR/vid_segment_file.txt" ] && cat "$TMP_DIR/vid_segment_file.txt" )"

  if [[ "$LAST_FILE" == "$LAST_UPLOADED_FILE" ]]; then
    log "Last file was already uploaded"
    return 0
  fi

  local ANIMATION_FILE="$TMP_DIR/vid_segment_short_${MACHINE_NAME}.mp4"
  rm "$ANIMATION_FILE" &> /dev/null

  local POLYGON="$(get_config "polygon" "" "$MOTION_DETECTION_CONFIG_FILE")"
#  if [ -z "$POLYGON" ]; then
#    log "No polygon defined in $MOTION_DETECTION_CONFIG_FILE! -> skipping cropping"
  if true; then
    log "No croppipng - skipping crop"
    # crop=out_w:out_h:x:y
    ffmpeg -y -i "$LAST_FILE" -filter_complex "[0:v]setpts=PTS/2[v]" -map "[v]" -an -c:v libx264 -crf 23 -preset veryfast "$ANIMATION_FILE"
  else
    local BOUNDING_BOX="$(get_bounding_box_from_polygon "$POLYGON")"
    log "Cropping to: $BOUNDING_BOX"
    local CROP_X="$(echo "$BOUNDING_BOX" | cut -d ',' -f 1)"
    local CROP_Y="$(echo "$BOUNDING_BOX" | cut -d ',' -f 2)"
    local CROP_X2="$(echo "$BOUNDING_BOX" | cut -d ',' -f 3)"
    local CROP_Y2="$(echo "$BOUNDING_BOX" | cut -d ',' -f 4)"
    local CROP_W="$((CROP_X2 - CROP_X))"
    local CROP_H="$((CROP_Y2 - CROP_Y))"

    log "Complex filter for ffmpeg: [0:v]setpts=PTS/8,crop=${CROP_W}:${CROP_H}:${CROP_X}:${CROP_Y}[v]"

    # crop=out_w:out_h:x:y
    ffmpeg -y -i "$LAST_FILE" -filter_complex "[0:v]setpts=PTS/2,crop=${CROP_W}:${CROP_H}:${CROP_X}:${CROP_Y}[v]" -map "[v]" -an -c:v libx264 -crf 23 -preset veryfast "$ANIMATION_FILE"

  fi

  if [ -f "$ANIMATION_FILE" ]; then
    log "Uploading $ANIMATION_FILE"
    upload_file "$ANIMATION_FILE" "video/mp4" && echo "$LAST_FILE" > "$TMP_DIR/vid_segment_file.txt"
  fi
}

function can_process() {
  local HOUR="$(get_current_hour)"
  if [[ "$HOUR" == "0"* ]]; then
    HOUR="${HOUR:1}"
  fi

  if is_scale_suspended; then
    return 1
  elif [[ "$(get_cpu_temp_int)" -gt "70" ]]; then
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
    create_last_segment_animation
  fi

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
