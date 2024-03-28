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

  local TAGS="location=Warsaw,machine_name=$INFLUX_MACHINE_NAME"
  update_measurement_raw "$MEASUREMENT_NAME,$TAGS $FIELD_VALUES $TIMESTAMP"
}