#!/bin/bash

function ensure_env() {
  if [[ -z "$ENV_INITIALIZED" ]]; then
    exit 1
  fi
}



function get_current_year() {
    date +%Y
}
function get_current_month() {
    date +%m
}
function get_current_day() {
    date +%d
}


function get_current_date_compact() {
    date +%Y%m%d
}
function get_current_date_time_compact() {
  date +%Y%m%d%H%M%S
}
function get_current_date_dashed() {
    date +%Y-%m-%d
}
function get_current_date_underscore() {
    date +%Y_%m_%d
}


function get_wlan_ip() {
    /usr/sbin/ifconfig wlan0 | grep inet | tr ' ' "\n" | grep 192 | head -n 1
}


function ensure_directory_exists() {
  local DIR="$1"
  if [ ! -d "$DIR" ]; then
    mkdir -p "$DIR";
  fi
}


function set_gpio_out() {
  local -i PIN="$1"
  local -i VALUE="$2"

  if [[ -z "$PIN" ]]; then
    false
  elif [[ -z "$VALUE" ]]; then
    false
  else
    echo "$PIN" > /sys/class/gpio/export
    echo out > /sys/class/gpio/gpio17/direction
    echo "$VALUE" > /sys/class/gpio/gpio17/value
    true
  fi
}

function unexport_pin() {
  local -i PIN="$1"

  if [[ -z "$PIN" ]]; then
    false
  else
    echo "$PIN" > /sys/class/gpio/unexport
    true
  fi
}





function is_locked() {
  local PROCESS_NAME="$1"
  ensure_env

  mkdir -p "$LOCKS_DIR"
  LOCK_FILE="$LOCKS_DIR/$PROCESS_NAME.lock"
  if [ -f "$LOCK_FILE" ]; then
    true
  else
    false
  fi
}

function lock_process() {
  local PROCESS_NAME="$1"
  ensure_env

  mkdir -p "$LOCKS_DIR"
  LOCK_FILE="$LOCKS_DIR/$PROCESS_NAME.lock"
  touch "$LOCK_FILE"

  function finally_func() {
    rm -f "$LOCK_FILE"
  }
  trap finally_func EXIT
}

function is_pid_running() {
  local PID="$1"

  if ps -p "$PID" &> /dev/null; then
    true
  else
    false
  fi
}

function is_locked_process_running() {
  local PROCESS_NAME="$1"
  ensure_env

  local PID_FILE="$LOCKS_DIR/$PROCESS_NAME.pid"
  if [ -f "$PID_FILE" ]; then
    PID="$(cat "$PID_FILE")"
    if is_pid_running "$PID"; then
      true
    else
      false
    fi
  else
    false
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








function extract_year_from_date() {
    DATE=$1
    DELIMITER=$2
    echo $DATE | cut -d "$DELIMITER" -f 1
}

function extract_month_from_date() {
    DATE=$1
    DELIMITER=$2
    echo $DATE | cut -d "$DELIMITER" -f 2
}

function extract_day_from_date() {
    DATE=$1
    DELIMITER=$2
    echo $DATE | cut -d "$DELIMITER" -f 3
}

function join_date() {
    YEAR=$1
    MONTH=$2
    DAY=$3
    DELIMITER=$4
    echo "$YEAR$DELIMITER$MONTH$DELIMITER$DAY"
}



function get_machine_name() {
    MY_IP=$(get_wlan_ip)
    if [ "$MY_IP" = "192.168.0.45" ]; then
        echo "PiZero"
    elif [ "$MY_IP" = "192.168.0.206" ]; then
        echo "RaspberryPi2"
    elif [ "$MY_IP" = "192.168.0.80" ]; then
        echo "RaspberryPi4"
    else
        echo "Unknown"
    fi
}





