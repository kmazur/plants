#!/bin/bash

declare INFLUX_BUCKET="main"
declare INFLUX_ORG="Main"
declare INFLUX_TOKEN="$(get_required_config "influx.token")"
declare INFLUX_MACHINE_NAME="$(get_required_config "name")"
declare INFLUX_URL="$(get_required_config "influx.url")"

function update_measurement_raw() {
  local DATA="$1"

  local TMP_FILE=$(mktemp "$TMP_DIR/influx_batch.XXX")
  echo "$DATA" > "$TMP_FILE"

  curl -XPOST "$INFLUX_URL/api/v2/write?org=$INFLUX_ORG&bucket=$INFLUX_BUCKET&precision=s" \
    --header "Authorization: Token $INFLUX_TOKEN" \
    --header "Content-Type: text/plain" \
    --data-binary "@$TMP_FILE"

  local EXIT_CODE="$?"

  rm "$TMP_FILE"
  return "$EXIT_CODE"
}

function update_measurement_single() {
  local MEASUREMENT_NAME="$1"
  local FIELD_VALUES="$2"

  local TIMESTAMP="$3"
  if [[ -z "$TIMESTAMP" ]]; then
    TIMESTAMP="$(date +%s)"
  fi

  local TAGS="machine_name=$INFLUX_MACHINE_NAME"
  update_measurement_raw "$MEASUREMENT_NAME,$TAGS $FIELD_VALUES $TIMESTAMP"
}




function get_publisher_queue() {
  local PUBLISHER_NAME="$1"
  echo "$INFLUX_DIR/${PUBLISHER_NAME}.queue"
}
function get_publisher_queue_state() {
  local PUBLISHER_NAME="$1"
  echo "$INFLUX_DIR/${PUBLISHER_NAME}.processed"
}


declare MAIN_INFLUX_QUEUE_FILE="$(get_publisher_queue "main")"
declare MAIN_INFLUX_QUEUE_STATE_FILE="$(get_publisher_queue_state "main")"

declare INFLUX_PUBLISHER_REGISTRY_FILE="$INFLUX_DIR/registry.txt"
function get_publisher_name() {
  local PUBLISHER_NAME="$1"
  local TODAY="$(get_current_date_compact)"
  echo "${PUBLISHER_NAME}_${TODAY}"
}

function register_publisher() {
  local PUBLISHER_NAME="$(get_publisher_name "$1")"
  local QUEUE_FILE="$(get_publisher_queue "$PUBLISHER_NAME")"
  set_config "${PUBLISHER_NAME}" "${QUEUE_FILE}" "$INFLUX_PUBLISHER_REGISTRY_FILE"
}

function publish_measurement_single() {
  local PUBLISHER_NAME="$(get_publisher_name "$1")"
  local MEASUREMENT_NAME="$2"
  local FIELD_VALUES="$3"

  local TIMESTAMP="$4"
  if [[ -z "$TIMESTAMP" ]]; then
    TIMESTAMP="$(date +%s)"
  fi

  local QUEUE_FILE="$(get_publisher_queue "$PUBLISHER_NAME")"
  local TAGS="machine_name=$INFLUX_MACHINE_NAME"
  local DATAPOINT="$MEASUREMENT_NAME,$TAGS $FIELD_VALUES $TIMESTAMP"

  local FILE="$MAIN_INFLUX_QUEUE_FILE"

  (
      flock -x 200

      if [ ! -f "$FILE" ]; then
        touch "$FILE"
      fi
      echo "$DATAPOINT" >> "$FILE"

    ) 200>"$FILE.flock"
}

function publish_measurement_batch() {
  local PUBLISHER_NAME="$(get_publisher_name "$1")"
  local DATA="$2"

  local CLEANED_DATA="$(echo "$DATA" | grep -v "^$")"

  local FILE="$MAIN_INFLUX_QUEUE_FILE"
  (
      flock -x 200

      if [ ! -f "$FILE" ]; then
        touch "$FILE"
      fi
      echo "$CLEANED_DATA" >> "$FILE"

    ) 200>"$FILE.flock"
}

function publish_main_queue() {
  local FILE="$MAIN_INFLUX_QUEUE_FILE"
  local BATCH_SIZE="5000"
  {
    flock -x 200

    if [ ! -f "$FILE" ]; then
      touch "$FILE"
    fi
    local QUEUE_DATA="$(head -n "$BATCH_SIZE" "$FILE")"
    local LINE_COUNT="$(echo -n "$QUEUE_DATA" | grep -c '^')"
    if [ "$LINE_COUNT" != "0" ]; then
      if update_measurement_raw "$QUEUE_DATA"; then
        sed -i -e "1,${LINE_COUNT}d" "$FILE"
      fi
    fi

  } 200>"$FILE.flock"

  echo "$LINE_COUNT"
}