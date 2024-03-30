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
    date "+%H"
}
function get_current_minute() {
    date "+%M"
}
function get_current_second() {
    date "+%S"
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


function get_current_date_compact() {
    date +%Y%m%d
}
function get_current_date_time_compact() {
  date +%Y%m%d_%H%M%S
}
function get_current_date_time_dashed() {
  date +%Y-%m-%dT%H:%M:%S
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


