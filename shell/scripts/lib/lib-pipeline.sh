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
