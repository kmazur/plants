#!/bin/bash

# shellcheck source=shell/scripts/lib.sh
source "$LIB_INIT_FILE"
ensure_env

MIN_PERIOD="${1:-20}"
MAX_PERIOD="${2:-300}"
PERIOD="$MIN_PERIOD"

function update_period() {
  PERIOD="$(get_scaled_inverse_value "$MIN_PERIOD" "$MAX_PERIOD")"
}

function detect_audio_events() {
  local DIR="$1"
  local OUTPUT_DIR="$2"
  local FILES="$(ls -1tr "$DIR" | grep -P '^audio.*\.mp3' | head -n -1)"
  local FILE_COUNT="$(echo -n "$FILES" | grep -c '^')"
  log "Processing $FILE_COUNT mp3 files"

  for FILE in $FILES; do
    if is_scale_suspended; then
      break
    fi

    declare STUB="${FILE%.mp3}"
    if [ -f "$DIR/$STUB.audio_detected" ]; then
      continue
    fi
    if [ ! -f "$DIR/$STUB.txt" ]; then
      continue
    fi

    detect_events_in_mp3_file "$DIR" "$FILE" "$OUTPUT_DIR"
  done
}


while true; do
  if ! is_scale_suspended; then
    log "Processing: MP3"
    detect_audio_events "$(get_audio_dir)" "$(get_audio_segment_dir)"
    detect_audio_events "$(get_audio_dir "$(get_yesterday_date_compact)")" "$(get_audio_segment_dir "$(get_yesterday_date_compact)")"
  else
    log_warn "Audio detection suspended"
  fi

  update_period
  log "Period is: $PERIOD s"
  sleep "$PERIOD"
done
