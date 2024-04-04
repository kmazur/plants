#!/bin/bash

function get_daylight_info() {
  local LAT="$1"
  local LNG="$2"

  local URL="https://api.sunrisesunset.io/json?lat=$LAT&lng=$LNG"
  curl -XGET "$URL" 2> /dev/null
}

function get_current_daylight_info() {
  local LAT="$(get_required_config "location.lat")"
  local LNG="$(get_required_config "location.lon")"

  local URL="https://api.sunrisesunset.io/json?lat=$LAT&lng=$LNG"
  curl -XGET "$URL" 2> /dev/null
}