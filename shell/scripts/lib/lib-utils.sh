#!/bin/bash

function ensure_env() {
  if [[ -z "$ENV_INITIALIZED" ]]; then
    exit 1
  fi
}

function ensure_directory_exists() {
  local DIR="$1"
  if [ ! -d "$DIR" ]; then
    mkdir -p "$DIR";
  fi
}





function get_wlan_ip() {
    /usr/sbin/ifconfig wlan0 | grep inet | tr ' ' "\n" | grep 192 | head -n 1
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



function add_crontab_entry() {
  local ENTRY="$1"
  (crontab -l | grep "^#"; (crontab -l;  echo "$ENTRY") | grep -v "^#" | sort -u;) | crontab -
}

