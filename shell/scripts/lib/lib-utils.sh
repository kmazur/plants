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

function ensure_file_exists() {
  local FILE_PATH="$1"

  local DIR_PATH=$(dirname "$FILE_PATH")
  if [ ! -d "$DIR_PATH" ]; then
      mkdir -p "$DIR_PATH"
  fi

  if [ ! -f "$FILE_PATH" ]; then
    touch "$FILE_PATH"
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

function add_crontab_entry() {
  local ENTRY="$1"
  (crontab -l | grep "^#"; (crontab -l;  echo "$ENTRY") | grep -v "^#" | sort -u;) | crontab -
}


function get_output_dir() {
  local ROOT_DIR="$1"
  local DATE="${2:-$(get_current_date_compact)}"
  local OUTPUT_DIR="$ROOT_DIR/$DATE"
  echo "$OUTPUT_DIR"
}

function get_video_dir() {
  local DATE="$1"
  get_output_dir "$VIDEO_DIR" "$DATE"
}

function get_audio_dir() {
  local DATE="$1"
  get_output_dir "$AUDIO_DIR" "$DATE"
}

function get_logs_dir() {
  local DATE="$1"
  get_output_dir "$LOGS_DIR" "$DATE"
}

function get_audio_segment_dir() {
  local DATE="$1"
  get_output_dir "$AUDIO_SEGMENT_DIR" "$DATE"
}

function get_video_segment_dir() {
  local DATE="$1"
  get_output_dir "$VIDEO_SEGMENT_DIR" "$DATE"
}

function get_pipeline_dir() {
  local DATE="$1"
  get_output_dir "$PIPELINE_DIR" "$DATE"
}

function get_used_space_percent() {
  df -h | grep root | cut -d '%' -f 1 | rev | cut -d ' ' -f 1 | rev
}

function get_bounding_box_from_polygon() {
  local POLYGON_STR="$1"

  local MIN_X="10000"
  local MAX_X="-10000"
  local MIN_Y="10000"
  local MAX_Y="-10000"

  local -a COORDS
  # Split the input string by ';' to get individual coordinates
  IFS=';' read -ra COORDS <<< "$POLYGON_STR"

  local coord
  local xy
  # Loop through each coordinate pair
  for coord in "${COORDS[@]}"; do
    # Split each pair by ',' to get x and y
    IFS=',' read -ra xy <<< "$coord"

    x=${xy[0]}
    y=${xy[1]}

    if [ -n "$x" ] && [ -n "$y" ]; then
      # Update the min and max values
      if [ "$x" -lt "$MIN_X" ]; then MIN_X=$x; fi
      if [ "$x" -gt "$MAX_X" ]; then MAX_X=$x; fi
      if [ "$y" -lt "$MIN_Y" ]; then MIN_Y=$y; fi
      if [ "$y" -gt "$MAX_Y" ]; then MAX_Y=$y; fi
    fi
  done

  echo "$MIN_X,$MIN_Y,$MAX_X,$MAX_Y"
}

function calc() {
  local OPERATION="$1"
  printf "%.4f" "$(echo "$OPERATION" | bc)"
}