#!/bin/bash

function detect_events_in_mp3_file() {
  local DIR="$1"
  local FILE="$2"

  local STUB="${FILE%.mp3}"

  declare NANOS="$(cat "$DIR/$STUB.txt")"
  declare FILE_START_EPOCH_SECONDS="$(( NANOS / 1000000000 ))"
  declare PTS_FILE="$STUB.influx"

  START_REC=""
  LAST_BUMP=""
  LAST_SECOND=""
  while IFS=' ' read -r LINE; do
    declare -a ARR=($LINE)
    declare SECOND="${ARR[0]}"
    declare MIN_VAL="${ARR[1]}"
    declare MAX_VAL="${ARR[2]}"
    declare MEAN_VAL="${ARR[3]}"
    declare LAST_VAL="${ARR[4]}"
    declare DIFF_VAL="${ARR[5]}"

    declare PRCESSED_EPOCH_SECONDS="$(( FILE_START_EPOCH_SECONDS + SECOND ))"
    declare DIFF_ABS="${DIFF_VAL#-}"
    declare DIFF_INT="${DIFF_ABS%%.*}"
    LAST_SECOND="$SECOND"

    if [[ "$DIFF_INT" -ge "4" ]]; then
      if [[ -z "$START_REC" ]]; then
        START_REC="$SECOND"
        LAST_BUMP="$SECOND"
      else
        LAST_BUMP="$SECOND"
      fi
    elif [[ "$DIFF_INT" -ge "3" ]]; then
      if [[ -n "$START_REC" ]]; then
        LAST_BUMP="$SECOND"
      fi
    fi

    if [[ -n "$START_REC" && "$(( SECOND - LAST_BUMP ))" -gt "5" ]]; then
        START_SECOND="$(( START_REC - 1 < 0 ? 0 : START_REC - 1))"
        EPOCH_START="$(( FILE_START_EPOCH_SECONDS + START_SECOND ))"
        START="$(date -u -d @"$START_SECOND" +'%H:%M:%S')"
        DURATION="$(( SECOND - START_REC ))"
        SEGMENT_FILE="segment_${STUB}_$(epoch_to_date_time_compact "$EPOCH_START").mp3"
        ffmpeg -y -nostdin -i "$DIR/$STUB.mp3" -ss "$START" -t "$DURATION" -c copy "$DIR/$SEGMENT_FILE" &> /dev/null

        log "Detected in $STUB.mp3 -> $START(duration: $DURATION s). Writing to file: $SEGMENT_FILE"
        START_REC=""
        LAST_BUMP=""
    fi

  done < "$DIR/$PTS_FILE"

  if [[ -n "$START_REC" ]]; then
    START_SECOND="$(( START_REC - 1 < 0 ? 0 : START_REC - 1))"
    EPOCH_START="$(( FILE_START_EPOCH_SECONDS + START_SECOND ))"
    START="$(date -u -d @"$START_SECOND" +'%H:%M:%S')"
    DURATION="$(( LAST_SECOND - START_REC ))"
    SEGMENT_FILE="segment_${STUB}_$(epoch_to_date_time_compact "$EPOCH_START").mp3"
    ffmpeg -y -nostdin -i "$DIR/$STUB.mp3" -ss "$START" -t "$DURATION" -c copy "$DIR/$SEGMENT_FILE" &> /dev/null

    log "Detected in $STUB.mp3 -> $START(duration: $DURATION s). Writing to file: $SEGMENT_FILE"
    START_REC=""
    LAST_BUMP=""
  fi

  touch "$DIR/$STUB.audio_detected"
}