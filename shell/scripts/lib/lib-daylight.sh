#!/bin/bash

function get_daylight_info() {
  local LAT="$1"
  local LNG="$2"

  local URL="https://api.sunrisesunset.io/json?lat=$LAT&lng=$LNG"
  curl -XGET "$URL" 2> /dev/null
}

function get_current_daylight_info() {
  local LAT="$(get_required_config "location.lat")"
  local LNG="$(get_required_config "location.lng")"

  local URL="https://api.sunrisesunset.io/json?lat=$LAT&lng=$LNG"
  curl -XGET "$URL" 2> /dev/null
}

function convert_to_zoned_date_time() {
  local DATE_PART="$1"
  local TIME_PART="$2"
  local TIMEZONE="$3"
  local FULL_DATE_TIME="$DATE_PART $TIME_PART"
  local CONVERTED_DATE_TIME="$(TZ=$TIMEZONE date -d "$FULL_DATE_TIME" +"$(get_zoned_date_time_format_compact)" )"
  echo "$CONVERTED_DATE_TIME"
}

function update_daylight_info() {
  local JSON_PAYLOAD="$(get_current_daylight_info)"

  local STATUS="$(echo "$JSON_PAYLOAD" | jq -r '.status')"
  if [[ "$STATUS" == "OK" ]]; then
    local DATE="$(echo "$JSON_PAYLOAD" | jq -r '.results.date')"
    local SUNRISE="$(echo "$JSON_PAYLOAD" | jq -r '.results.sunrise')"
    local SUNSET="$(echo "$JSON_PAYLOAD" | jq -r '.results.sunset')"
    local FIRST_LIGHT="$(echo "$JSON_PAYLOAD" | jq -r '.results.first_light')"
    local LAST_LIGHT="$(echo "$JSON_PAYLOAD" | jq -r '.results.last_light')"
    local DAWN="$(echo "$JSON_PAYLOAD" | jq -r '.results.dawn')"
    local DUSK="$(echo "$JSON_PAYLOAD" | jq -r '.results.dusk')"
    local SOLAR_NOON="$(echo "$JSON_PAYLOAD" | jq -r '.results.solar_noon')"
    local GOLDEN_HOUR="$(echo "$JSON_PAYLOAD" | jq -r '.results.golden_hour')"
    local DAY_LENGTH="$(echo "$JSON_PAYLOAD" | jq -r '.results.day_length')"
    local TIMEZONE="$(echo "$JSON_PAYLOAD" | jq -r '.results.timezone')"

    #"sunrise": "6:04:13 AM",
    #"sunset": "7:15:26 PM",
    #"first_light": "4:01:30 AM",
    #"last_light": "9:18:09 PM",
    #"dawn": "5:29:28 AM",
    #"dusk": "7:50:11 PM",
    #"solar_noon": "12:39:50 PM",
    #"golden_hour": "6:30:35 PM",
    #"day_length": "13:11:13",

    set_config "daylight.sunrise" "$(convert_to_zoned_date_time "$DATE" "$SUNRISE" "$TIMEZONE")"
    set_config "daylight.sunset" "$(convert_to_zoned_date_time "$DATE" "$SUNSET" "$TIMEZONE")"
    set_config "daylight.first_light" "$(convert_to_zoned_date_time "$DATE" "$FIRST_LIGHT" "$TIMEZONE")"
    set_config "daylight.last_light" "$(convert_to_zoned_date_time "$DATE" "$LAST_LIGHT" "$TIMEZONE")"
    set_config "daylight.dawn" "$(convert_to_zoned_date_time "$DATE" "$DAWN" "$TIMEZONE")"
    set_config "daylight.dusk" "$(convert_to_zoned_date_time "$DATE" "$DUSK" "$TIMEZONE")"
    set_config "daylight.solar_noon" "$(convert_to_zoned_date_time "$DATE" "$SOLAR_NOON" "$TIMEZONE")"
    set_config "daylight.golden_hour" "$(convert_to_zoned_date_time "$DATE" "$GOLDEN_HOUR" "$TIMEZONE")"
    set_config "daylight.day_length" "$DAY_LENGTH"
  fi
}

function is_night() {
  local HOUR="$(get_current_hour)"
  local SUNRISE="$(get_config "daylight.sunrise" "6")"
  local SUNSET="$(get_config "daylight.sunset" "21")"
  local SUNRISE_HOUR="${SUNRISE:9:2}"
  local SUNSET_HOUR="${SUNSET:9:2}"

  if [[ "$HOUR" == "0"* ]]; then
    HOUR="${HOUR:1}"
  fi

  [[ "$HOUR" -le "$SUNRISE_HOUR" || "$HOUR" -ge "$SUNSET_HOUR" ]]
}

function is_day() {
  ! is_night
}