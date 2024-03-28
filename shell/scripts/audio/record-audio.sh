#!/bin/bash

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
  local FILES="$(ls -1tr | grep -P '^audio-\d+\.wav$' | head -n -1)"
  local FILE_COUNT="$(echo -n  "$FILES" | wc -l)"
  echo "Processing raw *.wav files: $FILE_COUNT files"

  for FILE in $FILES; do
    if [ ! -f "$FILE.txt" ]; then
      local -i NANOS="$(get_birth_nanos "$FILE")"
      echo "$NANOS" > "$FILE.txt"
    fi

    if [ ! -f "$FILE.mp3" ]; then
      echo "Converting $FILE to mp3"
      lame -S --bitwidth 32 -r -s 48 --preset standard "$FILE" "$FILE.mp3" && rm "$FILE"
    fi

    if [ ! -f "$FILE.pts" ] && [ -f "$FILE.mp3" ]; then
      echo "Converting $FILE to PTS"
      get_audio_levels "$FILE.mp3" > "$FILE.pts"
    fi

  done
}



function ensure_env() {
  if [[ -z "$ENV_INITIALIZED" ]]; then
    exit 1
  fi
}

function get_config() {
  local KEY="$1"
  ensure_env

  grep "^$KEY=" "$CONFIG_INI" | cut -f 2- -d '='
}

function get_required_config() {
  local KEY="$1"

  VALUE="$(get_config "$KEY")"
  if [[ -z "$VALUE" ]]; then
    echo "Required config not found! Key='$KEY'"
    exit 100
  fi
  echo "$VALUE"
}


declare INFLUX_BUCKET="main"
declare INFLUX_ORG="Main"
declare INFLUX_TOKEN="$(get_required_config "influx.token")"
declare MACHINE_NAME="$(get_required_config "name")"
declare INFLUX_URL="$(get_required_config "influx.url")"

function update_measurement_raw() {
  local DATA="$1"

  local TAGS="location=Warsaw,machine_name=$MACHINE_NAME"
  curl -XPOST "$INFLUX_URL/api/v2/write?org=$INFLUX_ORG&bucket=$INFLUX_BUCKET&precision=s" \
    --header "Authorization: Token $INFLUX_TOKEN" \
    --header "Content-Type: text/plain" \
    --data-raw "$DATA"
}

function update_measurement_single() {
  local MEASUREMENT_NAME="$1"
  local FIELD_VALUES="$2"
  local TIMESTAMP="$3"
  if [[ -z "$TIMESTAMP" ]]; then
    TIMESTAMP="$(date +%s)"
  fi

  update_measurement_raw "$MEASUREMENT_NAME,$TAGS $FIELD_VALUES $TIMESTAMP"
}

function parse_volume_level_files() {
  local FILES="$(ls -1tr | grep -P '^audio-.*\.pts$')"
  local FILE_COUNT="$(echo -n  "$FILES" | wc -l)"
  echo "Parsing volume level files: $FILE_COUNT files"

  for PTS_FILE in $FILES; do
    declare STUB="${PTS_FILE%.pts}"
    if [ -f "$STUB.txt" ]; then
      declare NANOS="$(cat "$STUB.txt")"
      echo "Parsing $STUB.pts"
      ./volume_aggregator "$STUB.pts" "$STUB.influx" && rm "$PTS_FILE"
    fi
  done
}


function publish_volume_levels() {
  local FILES="$(ls -1tr | grep -P '^audio-.*\.influx')"
  local FILE_COUNT="$(echo -n "$FILES" | wc -l)"
  echo "Publishing volume level files: $FILE_COUNT files"

  for INFLUX_FILE in $FILES; do
    declare STUB="${INFLUX_FILE%.influx}"
    if [ -f "$STUB.txt" ]; then
      echo "Publishing data from file: $INFLUX_FILE"
      declare NANOS="$(cat "$STUB.txt")"
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
      done < "$INFLUX_FILE"

      if [[ "$BATCH_COUNT" -gt "0" ]]; then
        update_measurement_raw "$BATCH"
        BATCH_COUNT="0"
        BATCH=""
      fi


      rm "$STUB.txt"
      rm "$STUB.influx"
    fi
  done
}


BITRATE="48000"
BITRATE_K="$((BITRATE / 1000))"

AUDIO_FILE="audio.wav"
DURATION_SECONDS="$((24 * 60 * 60))"
SPLIT_SECONDS="$((10 * 60))"

arecord --max-file-time "$SPLIT_SECONDS" -d "$DURATION_SECONDS" -D dmic_hw -c 2 -r "$BITRATE" -f S32_LE -t wav "$AUDIO_FILE" &


while true; do
  process_raw_audio_files
  parse_volume_level_files
  publish_volume_levels
  sleep 10
done
