#!/bin/bash

function set_scale() {
  local SCALE="$1"
  local SCALE_FILE="$CONFIG_DIR/scale.ini"
  echo "$SCALE" > "$SCALE_FILE"
}

function get_scale() {
  local SCALE_FILE="$CONFIG_DIR/scale.ini"
  cat "$SCALE_FILE"
}

function is_scale_suspended() {
  local SCALE="$(get_scale)"
  if [[ "$SCALE" == "0" ]]; then
    true
  else
    false
  fi
}

function get_scaled_range() {
  local MIN="$1"
  local MAX="$2"

  local DIFF="$(( MAX - MIN ))"
  local SCALE="$(get_scale)"
  if [ -z "$SCALE" ]; then
    echo "$MAX"
  else
    # Scale is int [0 -> 100]
    local SCALED_DIFF="$(( (SCALE * DIFF) / 100  ))"
    local SCALED="$(( MIN + SCALED_DIFF ))"
    echo "$SCALED"
  fi
}

function get_scaled_value() {
  local VALUE="$1"
  local SCALED="$(get_scaled_range "0" "$VALUE")"
  echo "$SCALED"
}

function get_scaled_inverse_value() {
  local MIN="$1"
  local MAX="$2"
  local SUB="$(get_scaled_range "$MIN" "$MAX")"
  local RESULT="$(( MIN + (MAX - SUB) ))"
  echo "$RESULT"
}