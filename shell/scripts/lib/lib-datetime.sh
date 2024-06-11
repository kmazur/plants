#!/bin/bash


function get_current_year() {
    date "+%Y"
}
function get_current_month() {
    date "+%m"
}
function get_current_day() {
    date "+%d"
}
function get_current_hour() {
  # TODO: add function with & without leading 0
    date "+%H"
}
function get_current_minute() {
    date "+%M"
}
function get_current_second() {
    date "+%S"
}

function get_current_epoch_seconds() {
    date "+%s"
}

function epoch_to_year() {
  local -i EPOCH_SECONDS="$1"
  date -d@"$EPOCH_SECONDS" "+%Y"
}
function epoch_to_month() {
  local -i EPOCH_SECONDS="$1"
  date -d@"$EPOCH_SECONDS" "+%m"
}
function epoch_to_day() {
  local -i EPOCH_SECONDS="$1"
  date -d@"$EPOCH_SECONDS" "+%d"
}

function get_date_format_compact() {
  echo "%Y%m%d"
}
function get_date_time_format_compact() {
  echo "%Y%m%d_%H%M%S"
}
function get_zoned_date_time_format_compact() {
  echo "%Y%m%d_%H%M%S_%Z"
}
function get_date_time_format_dashed() {
  echo "%Y-%m-%dT%H:%M:%S"
}
function get_zoned_date_time_format_dashed() {
  echo "%Y-%m-%dT%H:%M:%S %Z"
}

function date_compact_to_dashed() {
  local INPUT_DATE="$1"

  local YEAR=${INPUT_DATE:0:4}
  local MONTH=${INPUT_DATE:4:2}
  local DAY=${INPUT_DATE:6:2}
  local HOUR=${INPUT_DATE:9:2}
  local MINUTE=${INPUT_DATE:11:2}
  local SECOND=${INPUT_DATE:13:2}

  local OUTPUT_DATE="${YEAR}-${MONTH}-${DAY}T${HOUR}:${MINUTE}:${SECOND}"

  echo "$OUTPUT_DATE"
}

function get_yesterday_date_compact() {
  date -d @$(( $(date +"%s") - 86400)) +"$(get_date_format_compact)"
}
function get_current_date_compact() {
  date +"$(get_date_format_compact)"
}
function get_current_date_time_compact() {
  date +"$(get_date_time_format_compact)"
}
function get_current_date_time_dashed() {
  date +"$(get_date_time_format_dashed)"
}
function get_current_date_dashed() {
    date +%Y-%m-%d
}
function get_current_date_underscore() {
    date +%Y_%m_%d
}


function epoch_to_date_compact() {
  local -i EPOCH_SECONDS="$1"
  date -d@"$EPOCH_SECONDS" "+%Y%m%d"
}
function epoch_to_date_time_compact() {
  local -i EPOCH_SECONDS="$1"
  date -d@"$EPOCH_SECONDS" "+%Y%m%d_%H%M%S"
}
function epoch_to_date_time_dashed() {
  local -i EPOCH_SECONDS="$1"
  date -d@"$EPOCH_SECONDS" "+%Y-%m-%dT%H:%M:%S"
}
function epoch_to_date_dashed() {
  local -i EPOCH_SECONDS="$1"
  date -d@"$EPOCH_SECONDS" "+%Y-%m-%d"
}
function epoch_to_date_underscore() {
  local -i EPOCH_SECONDS="$1"
  date -d@"$EPOCH_SECONDS" "+%Y_%m_%d"
}
