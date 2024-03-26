#!/bin/bash

# depends on lib.sh


function get_cpu_temp() {
  vcgencmd measure_temp | cut -f 2 -d '=' | cut -f 1 -d "'"
}



declare INFLUX_BUCKET="main"
declare INFLUX_ORG="Main"
declare INFLUX_TOKEN="$(get_required_config "influx.token")"
declare MACHINE_NAME="$(get_required_config "name")"
declare INFLUX_URL="$(get_required_config "influx.url")"

function update_measurement() {
        local MEASUREMENT_NAME="$1"
        local FIELD_NAME="$2"
        local VALUE="$3"

        local -i NOW_EPOCH_SECONDS="$(date +%s)"
        local TAGS="location=Warsaw,machine_name=$MACHINE_NAME"
        curl -XPOST "$INFLUX_URL/api/v2/write?org=$INFLUX_ORG&bucket=$INFLUX_BUCKET&precision=s" \
          --header "Authorization: Token $INFLUX_TOKEN" \
          --header "Content-Type: text/plain" \
          --data-raw "$MEASUREMENT_NAME,$TAGS $FIELD_NAME=$VALUE $NOW_EPOCH_SECONDS"
}