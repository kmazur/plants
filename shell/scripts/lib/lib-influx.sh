#!/bin/bash

declare INFLUX_BUCKET="main"
declare INFLUX_ORG="Main"
declare INFLUX_TOKEN="$(get_required_config "influx.token")"
declare INFLUX_MACHINE_NAME="$(get_required_config "name")"
declare INFLUX_URL="$(get_required_config "influx.url")"

function update_measurement_raw() {
  local DATA="$1"

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
function register_publisher() {
  local PUBLISHER_NAME="$1"
  local QUEUE_FILE="$(get_publisher_queue "$PUBLISHER_NAME")"
  local QUEUE_STATE="$(get_publisher_queue_state "$PUBLISHER_NAME")"

  touch "$QUEUE_FILE"

  local EXISTING_PUBLISHER="$(get_config "$PUBLISHER_NAME" "" "$INFLUX_PUBLISHER_REGISTRY_FILE")"
  if [ ! -f "$QUEUE_STATE" ]; then
    echo "0" > "$QUEUE_STATE"
  elif [[ "$EXISTING_PUBLISHER" != "$QUEUE_FILE" ]]; then
    echo "0" > "$QUEUE_STATE"
  fi

  set_config "${PUBLISHER_NAME}" "${QUEUE_FILE}" "$INFLUX_PUBLISHER_REGISTRY_FILE"
}

function publish_measurement_single() {
  local PUBLISHER_NAME="$1"
  local MEASUREMENT_NAME="$2"
  local FIELD_VALUES="$3"

  local TIMESTAMP="$4"
  if [[ -z "$TIMESTAMP" ]]; then
    TIMESTAMP="$(date +%s)"
  fi

  local QUEUE_FILE="$(get_publisher_queue "$PUBLISHER_NAME")"
  local TAGS="machine_name=$INFLUX_MACHINE_NAME"
  echo "$MEASUREMENT_NAME,$TAGS $FIELD_VALUES $TIMESTAMP" >> "$QUEUE_FILE"
}

function publish_measurement_batch() {
  local PUBLISHER_NAME="$1"
  local DATA="$2"

  local CLEANED_DATA="$(echo "$DATA" | grep -v "^$")"
  local QUEUE_FILE="$(get_publisher_queue "$PUBLISHER_NAME")"
  echo "$CLEANED_DATA" >> "$QUEUE_FILE"
}

function collect_publisher_data() {
  local PUBLISHER_NAMES
  local QUEUE_FILE
  local QUEUE_STATE_FILE
  local QUEUE_STATE
  local QUEUE_DATA
  local LINE_COUNT
  local NEW_QUEUE_STATE

  PUBLISHER_NAMES="$(get_config_keys "$INFLUX_PUBLISHER_REGISTRY_FILE")"
  for PUBLISHER_NAME in $PUBLISHER_NAMES; do
    QUEUE_FILE="$(get_publisher_queue "$PUBLISHER_NAME")"
    QUEUE_STATE_FILE="$(get_publisher_queue_state "$PUBLISHER_NAME")"
    QUEUE_STATE="$(cat "$QUEUE_STATE_FILE")"
    QUEUE_DATA="$(tail -n +"$((QUEUE_STATE + 1))" "$QUEUE_FILE")"
    if [ -z "$QUEUE_DATA" ]; then
      continue
    fi

    LINE_COUNT="$(echo "$QUEUE_DATA" | wc -l)"
    NEW_QUEUE_STATE="$((QUEUE_STATE + LINE_COUNT))"
    echo "$QUEUE_DATA" >> "$MAIN_INFLUX_QUEUE_FILE"
    echo "$NEW_QUEUE_STATE" > "$QUEUE_STATE_FILE"
  done
}

function publish_main_queue() {
  local QUEUE_STATE="$(cat "$MAIN_INFLUX_QUEUE_STATE_FILE")"
  local -i PUBLISHED="0"

  local QUEUE_DATA="$(tail -n +"$((QUEUE_STATE + 1))" "$MAIN_INFLUX_QUEUE_FILE")"
  if [ -z "$QUEUE_DATA" ]; then
    return
  fi
  local LINE_COUNT="$(echo "$QUEUE_DATA" | wc -l)"

  local -i BATCH_COUNT="0"
  local BATCH=""

  while read -r LINE; do
    DATAPOINT="$LINE"

    if [[ -z "$BATCH" ]]; then
      BATCH="$DATAPOINT"
    else
      BATCH="$BATCH
$DATAPOINT"
    fi

    BATCH_COUNT="$((BATCH_COUNT + 1))"
    if [[ "$BATCH_COUNT" -ge "5000" ]]; then
      if update_measurement_raw "$BATCH"; then
        PUBLISHED="$((PUBLISHED + BATCH_COUNT))"
        QUEUE_STATE="$((QUEUE_STATE + BATCH_COUNT))"
        echo "$QUEUE_STATE" > "$QUEUE_STATE_FILE"

        BATCH_COUNT="0"
        BATCH=""
      else
        echo "$PUBLISHED"
        return 1
      fi
    fi
  done < <(echo "$QUEUE_DATA")

  if [[ "$BATCH_COUNT" -gt "0" ]]; then
    if update_measurement_raw "$BATCH"; then
      PUBLISHED="$((PUBLISHED + BATCH_COUNT))"
      QUEUE_STATE="$((QUEUE_STATE + BATCH_COUNT))"
      echo "$QUEUE_STATE" > "$QUEUE_STATE_FILE"

      BATCH_COUNT="0"
      BATCH=""
    else
      echo "$PUBLISHED"
      return 1
    fi
  fi

  echo "$PUBLISHED"
}