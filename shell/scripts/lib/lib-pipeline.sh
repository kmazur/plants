#!/bin/bash

# Request token - scheduler distributing / signalling work based on CPU TEMP
# Definition of stages
#

# Raw data save to (SOURCE)_STAGE_RAW

# Video pipeline
# Camera -> VIDEO_STAGE_RAW -> output: video_(date)_(time).h264
# RAW -> convert to mp4
# mp4 -> create annotation srt
# mp4 -> extract first frame

function get_pipeline_stage_dir() {
  local STAGE="$1"
  local DATE="${2:-$(get_current_date_compact)}"
  echo "$(get_pipeline_dir "$DATE")/$STAGE"
}

function ensure_stage_dir() {
  local STAGE="$1"
  local DATE="${2:-$(get_current_date_compact)}"
  local STAGE_DIR="$(get_pipeline_stage_dir "$STAGE" "$DATE")"
  mkdir -p "$STAGE_DIR" &> /dev/null
  echo "$STAGE_DIR"
}

function get_orchestrator_dir() {
  get_pipeline_stage_dir "orchestrator"
}

function get_orchestrator_requests_file() {
  echo "/dev/shm/REQUESTS.txt"
}

SLEEP_PID=""
function request_cpu_time() {
  local PROCESS="$1"
  local TOKENS="$2"
  local TIMEOUT="${3:-60m}"

  local DATETIME="$(get_current_date_time_compact)"
  local REQUESTS_FILE="$(get_orchestrator_requests_file)"

  sleep "$TIMEOUT" &
  SLEEP_PID="$!"

  set_config "$PROCESS" "${TOKENS}:${SLEEP_PID}:${DATETIME}" "$REQUESTS_FILE"
  wait "$SLEEP_PID" 2> /dev/null
  unset SLEEP_PID
}

function notify_work_completed() {
  local PROCESS="$1"
  local TIMEOUT="${2:-60m}"

  local DATETIME="$(get_current_date_time_compact)"
  local REQUESTS_FILE="$(get_orchestrator_requests_file)"

  sleep "$TIMEOUT" &
  SLEEP_PID="$!"

  set_config "${PROCESS}-completed" "0:${SLEEP_PID}:${DATETIME}" "$REQUESTS_FILE"
  wait "$SLEEP_PID" 2> /dev/null
  unset SLEEP_PID
}

function init_sleep() {
  function handle_wakeup() {
      if [ -n "$SLEEP_PID" ]; then
          kill "$SLEEP_PID"
      fi
  }
  trap 'handle_wakeup' SIGUSR1
}

function get_processed_diff() {
  local INPUT_STAGE_DIR="$1"
  local OUTPUT_STAGE_DIR="$2"
  local FILE_PATTERN="$3"

  local PROCESSED_PATH="$OUTPUT_STAGE_DIR/processed.txt"
  touch "$PROCESSED_PATH"


  diff --new-line-format="" --unchanged-line-format="" --old-line-format="%L" \
    <(ls -1 "$INPUT_STAGE_DIR" | grep "$FILE_PATTERN" | sort -u | grep -v "^$") \
    <(sort -u "$PROCESSED_PATH" | grep -v "^$")
}

function get_second_not_processed_file() {
  local INPUT_STAGE_DIR="$1"
  local OUTPUT_STAGE_DIR="$2"
  local FILE_PATTERN="$3"

  local NOT_PROCESSED_FILES
  NOT_PROCESSED_FILES="$(get_not_processed_files "$INPUT_STAGE_DIR" "$OUTPUT_STAGE_DIR" "$FILE_PATTERN")"
  local FILES
  FILES="$(echo "$NOT_PROCESSED_FILES" | head -n 2)"
  if [[ "$(echo "$FILES" | wc -l)" -lt "2" ]]; then
    return 0
  fi
  echo "$FILES" | head -n 1
}

function get_not_processed_files() {
  local INPUT_STAGE_DIR="$1"
  local OUTPUT_STAGE_DIR="$2"
  local FILE_PATTERN="$3"

  local NOT_PROCESSED_FILES
  NOT_PROCESSED_FILES="$(get_processed_diff "$INPUT_STAGE_DIR" "$OUTPUT_STAGE_DIR" "$FILE_PATTERN")"

  [[ -z "$NOT_PROCESSED_FILES" ]] && return 0

  # Get the list of open files in the directory, filter out directories and the header
  local OPEN_FILES
  OPEN_FILES=$(lsof +D "$INPUT_STAGE_DIR" | awk 'NR>1 && $5 == "REG" {print $9}' | grep -oE '[^/]+$')

  local FILTERED_FILES=""
  for file in $NOT_PROCESSED_FILES; do
    if ! echo "$OPEN_FILES" | grep -q "^$file$"; then
      FILTERED_FILES+="$file"$'\n'
    fi
  done

  echo "$FILTERED_FILES" | grep -v "^$"
}