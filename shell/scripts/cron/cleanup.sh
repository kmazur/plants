#!/bin/bash

# shellcheck source=shell/scripts/lib.sh
source "$LIB_INIT_FILE"
ensure_env

MIN_PERIOD="${1:-300}"
MAX_PERIOD="${2:-1800}"
PERIOD="$MIN_PERIOD"

function update_period() {
  PERIOD="$(get_scaled_inverse_value "$MIN_PERIOD" "$MAX_PERIOD")"
}

function remove_dirs() {
  local ROOT_DIR="$1"
  DIRS="$(ls -1thd "$ROOT_DIR"/*/)"
  DIR_COUNT="$(echo "$DIRS" | wc -l)"
  if [[ "$DIR_COUNT" -le "1" ]]; then
    log_warn "Can't cleanup dirs on $ROOT_DIR - only $DIR_COUNT dirs present"
  else
    DIRS_TO_CLEANUP="$(echo "$DIRS" | tail -n 1)"
    for DIR in $DIRS_TO_CLEANUP; do
      log_warn "Removing $DIR"
      rm -rf "$DIR"
    done
  fi
}

function cleanup() {
  local USED_SPACE="$(get_used_space_percent)"
  if [[ "$USED_SPACE" -lt "50" ]]; then
    log "Disk space is ok: $USED_SPACE %"
  elif [[ "$USED_SPACE" -le "80" ]]; then
    log_warn "Disk space is ok still: $USED_SPACE %"
  elif [[ "$USED_SPACE" -gt "85" ]]; then
    log_warn "Low disk space, performing cleanup"

    remove_dirs "$VIDEO_DIR"
    remove_dirs "$AUDIO_DIR"
    remove_dirs "$AUDIO_SEGMENT_DIR"
    remove_dirs "$VIDEO_SEGMENT_DIR"
    remove_dirs "$LOGS_DIR"
    remove_dirs "$PIPELINE_DIR"
  fi
}

while true; do
  if ! is_scale_suspended; then
    log "Cleaning up"
    cleanup
  else
    log_warn "Cleanup check suspended"
  fi

  update_period
  log "Period is: $PERIOD s"
  sleep "$PERIOD"
done
