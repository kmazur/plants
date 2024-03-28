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


BITRATE="48000"
BITRATE_K="$((BITRATE / 1000))"

AUDIO_FILE="audio.wav"
AUDIO_DIR_NOW="$AUDIO_DIR/$(get_current_date_time_compact)"
mkdir -p "$AUDIO_DIR_NOW"
AUDIO_PATH="$AUDIO_DIR_NOW/$AUDIO_FILE"

DURATION_SECONDS="$((24 * 60 * 60))"
SPLIT_SECONDS="$((10 * 60))"

arecord --max-file-time "$SPLIT_SECONDS" -d "$DURATION_SECONDS" -D dmic_hw -c 2 -r "$BITRATE" -f S32_LE -t wav "$AUDIO_PATH" &




function get_audio_levels() {
  local INPUT="$1"
  ffprobe -f lavfi -i amovie=$INPUT,astats=metadata=1:reset=1 -show_entries frame=pkt_pts_time:frame_tags=lavfi.astats.Overall.RMS_level -of default=noprint_wrappers=1:nokey=1 2> /dev/null
}

function get_birth_txt() {
        local FILE="$1"
        stat "$FILE" | grep "Birth" | cut -c 9-
}

function get_birth_nanos() {
        local FILE="$1"
        local TXT="$(get_birth_txt "$FILE")"
        local NANOS=$(date -d "$TXT" +%s.%N | tr -d '.')
        echo "$NANOS"
}





function process_raw_audio_files() {
  local DIR="$1"
  local FILES="$(ls -1tr "$DIR" | grep -P '^audio-\d+\.wav$' | head -n -1)"
  local FILE_COUNT="$(echo -n  "$FILES" | wc -l)"
  log "Processing raw *.wav files: $FILE_COUNT files"

  for FILE in $FILES; do
    if [ ! -f "$DIR/$FILE.txt" ]; then
      local -i NANOS="$(get_birth_nanos "$DIR/$FILE")"
      log "$NANOS" > "$DIR/$FILE.txt"
    fi

    if [ ! -f "$DIR/$FILE.mp3" ]; then
      log "Converting $FILE to mp3"
      lame -S --bitwidth 32 -r -s 48 --preset standard "$DIR/$FILE" "$DIR/$FILE.mp3" && rm "$DIR/$FILE"
    fi

    if [ ! -f "$DIR/$FILE.pts" ] && [ -f "$DIR/$FILE.mp3" ]; then
      log "Converting $FILE to PTS"
      get_audio_levels "$DIR/$FILE.mp3" > "$DIR/$FILE.pts"
    fi

  done
}



function parse_volume_level_files() {
  local DIR="$1"
  local FILES="$(ls -1tr "$DIR" | grep -P '^audio-.*\.pts$')"
  local FILE_COUNT="$(echo -n  "$FILES" | wc -l)"
  log "Parsing volume level files: $FILE_COUNT files"

  for PTS_FILE in $FILES; do
    declare STUB="${PTS_FILE%.pts}"
    if [ -f "$DIR/$STUB.txt" ]; then
      declare NANOS="$(cat "$DIR/$STUB.txt")"
      log "Parsing $STUB.pts"
      ./volume_aggregator "$DIR/$STUB.pts" "$DIR/$STUB.influx" && rm "$DIR/$PTS_FILE"
    fi
  done
}


function publish_volume_levels() {
  local DIR="$1"
  local FILES="$(ls -1tr "$DIR" | grep -P '^audio-.*\.influx')"
  local FILE_COUNT="$(echo -n "$FILES" | wc -l)"
  log "Publishing volume level files: $FILE_COUNT files"

  for INFLUX_FILE in $FILES; do
    declare STUB="${INFLUX_FILE%.influx}"
    if [ -f "$DIR/$STUB.txt" ]; then
      log "Publishing data from file: $INFLUX_FILE"
      declare NANOS="$(cat "$DIR/$STUB.txt")"
      declare MILLIS="$((NANOS / 1000000))"
      declare START_EPOCH_SECONDS="$((MILLIS / 1000))"

      declare BATCH_COUNT="0"
      declare BATCH=""
      while read -r LINE; do
        declare -a ARR=($LINE)

        declare SECOND="${ARR[0]}"
        declare MIN_VAL="${ARR[1]}"
        declare MAX_VAL="${ARR[2]}"
        declare MEAN_VAL="${ARR[3]}"
        declare LAST_VAL="${ARR[4]}"

        declare EPOCH_SECONDS="$((START_EPOCH_SECONDS + SECOND))"

        local MEASUREMENT_NAME="audio_analysis"
        local FIELD_VALUES="min_volume_level=$MIN_VAL,max_volume_level=$MAX_VAL,mean_volume_level=$MEAN_VAL,volume_level=$LAST_VAL"
        local TAGS="location=Warsaw,machine_name=$MACHINE_NAME"
        local TIMESTAMP="$EPOCH_SECONDS"

        DATAPOINT="$MEASUREMENT_NAME,$TAGS $FIELD_VALUES $TIMESTAMP"
        if [[ -z "$BATCH" ]]; then
          BATCH="$DATAPOINT"
        else
          BATCH="$BATCH
$DATAPOINT"
        fi

        BATCH_COUNT="$((BATCH_COUNT + 1))"
        if [[ "$BATCH_COUNT" -ge "5000" ]]; then
          update_measurement_raw "$BATCH"
          BATCH_COUNT="0"
          BATCH=""
        fi
      done < "$DIR/$INFLUX_FILE"

      if [[ "$BATCH_COUNT" -gt "0" ]]; then
        update_measurement_raw "$BATCH"
        BATCH_COUNT="0"
        BATCH=""
      fi


      rm "$DIR/$STUB.txt"
      rm "$DIR/$STUB.influx"
    fi
  done
}




while true; do
  if ! is_scale_suspended; then
    log "Processing: WAV -> MP3"
    process_raw_audio_files "$AUDIO_DIR_NOW"
    log "Processing: MP3 -> PTS"
    parse_volume_level_files "$AUDIO_DIR_NOW"
    log "Processing: PTS -> InfluxDB"
    publish_volume_levels "$AUDIO_DIR_NOW"
  else
    log_warn "Audio measurements suspended"
  fi

  update_period
  log "Period is: $PERIOD s"
  sleep "$PERIOD"
done
