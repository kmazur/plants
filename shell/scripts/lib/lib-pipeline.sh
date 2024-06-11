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
  echo "$(get_orchestrator_dir)/REQUESTS.txt"
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

  log "Requesting '$TOKENS' tokens, waiting on PID: $SLEEP_PID"

  set_config "$PROCESS" "${TOKENS}:${SLEEP_PID}:${DATETIME}" "$REQUESTS_FILE"
  wait
  unset SLEEP_PID

  log "Waking up"
}

function init_sleep() {
  function handle_wakeup() {
      if [ -n "$SLEEP_PID" ]; then
          kill "$SLEEP_PID"
      fi
  }
  trap 'handle_wakeup' SIGUSR1
}