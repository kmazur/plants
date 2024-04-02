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

AUDIO_DIR_NOW="$AUDIO_DIR"

function detect_events() {
  local DIR="$1"
  local FILES="$(ls -1tr "$DIR" | grep -P '^audio.*\.mp3' | head -n -1)"
  local FILE_COUNT="$(echo -n "$FILES" | grep -c '^')"
  log "Processing $FILE_COUNT mp3 files"

  for FILE in $FILES; do
    declare STUB="${FILE%.mp3}"
    declare PTS_FILE="$STUB.influx"
    declare NANOS_FILE="$STUB.txt"
    if [ ! -f "$DIR/$NANOS_FILE" ]; then
      continue
    fi
    if [ -f "$DIR/$STUB.audio_detected" ]; then
      continue
    fi

    declare NANOS="$(cat "$DIR/$STUB.txt")"
    declare START_EPOCH_SECONDS="$(( NANOS / 1000000000 ))"

    if is_scale_suspended; then
      break
    fi

    START_REC=""
    LAST_BUMP=""
    while IFS=' ' read -r LINE; do
      declare -a ARR=($LINE)
      declare SECOND="${ARR[0]}"
      declare MIN_VAL="${ARR[1]}"
      declare MAX_VAL="${ARR[2]}"
      declare MEAN_VAL="${ARR[3]}"
      declare LAST_VAL="${ARR[4]}"
      declare DIFF_VAL="${ARR[5]}"

      declare EPOCH_SECONDS="$(( START_EPOCH_SECONDS + SECOND ))"
      declare DIFF_ABS="${DIFF_VAL#-}"
      declare DIFF_INT="${DIFF_ABS%%.*}"

      if [[ "$DIFF_INT" -ge "3" ]]; then
        if [[ -z "$START_REC" ]]; then
          START_REC="$SECOND"
          LAST_BUMP="$SECOND"
        else
          LAST_BUMP="$SECOND"
        fi
      elif [[ "$(( SECOND - LAST_BUMP ))" -gt "5" ]]; then
          START_SECOND="$(( START_REC - 1 < 0 ? 0 : START_REC - 1))"
          EPOCH_START="$(( START_EPOCH_SECONDS + START_SECOND ))"
          START="$(date -u -d @"$START_SECOND" +'%H:%M:%S')"
          DURATION="$(( SECOND - START_REC ))"
          ffmpeg -nostdin -i "$DIR/$FILE" -ss "$START" -t "$DURATION" -c copy "$DIR/segment_${STUB}_$(epoch_to_date_time_compact "$EPOCH_START").mp3"
      fi

      touch "$DIR/$STUB.audio_detected"

    done < "$DIR/$PTS_FILE"

  done
}


while true; do
  if ! is_scale_suspended; then
    log "Processing: MP3"
    detect_events "$AUDIO_DIR_NOW"
    if is_scale_suspended; then
      break
    fi
  else
    log_warn "Audio detection suspended"
  fi

  update_period
  log "Period is: $PERIOD s"
  sleep "$PERIOD"
done
