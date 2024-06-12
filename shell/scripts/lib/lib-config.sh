#!/bin/bash

function load_config() {
  local FILE="${1:-$CONFIG_INI}"
  cat "$FILE"
}

function set_config() {
  local KEY="$1"
  local VAL="$2"
  local FILE="${3:-$CONFIG_INI}"
  ensure_env

  (
    flock -x 200

    ensure_file_exists "$FILE"

    ESCAPED_KEY=$(echo "$KEY" | sed 's/\//\\\//g')

    if grep "^$ESCAPED_KEY=" "$FILE" &> /dev/null; then
      sed -i "s|^$ESCAPED_KEY=.*|$KEY=$VAL|" "$FILE" &> /dev/null
    else
      echo "$KEY=$VAL" >> "$FILE"
    fi

  ) 200>"$FILE.flock"
  rm "$FILE.flock"
}

function remove_config() {
  local KEY="$1"
  local FILE="${2:-$CONFIG_INI}"
  ensure_env

  (
    flock -x 200

    ensure_file_exists "$FILE"

    ESCAPED_KEY=$(echo "$KEY" | sed 's/\//\\\//g')

    if grep "^$ESCAPED_KEY=" "$FILE" &> /dev/null; then
      sed -i "/^$ESCAPED_KEY=.*/d" "$FILE" &> /dev/null
    fi

  ) 200>"$FILE.flock"
  rm "$FILE.flock"
}

function has_config_key() {
  local KEY="$1"
  local FILE="${3:-$CONFIG_INI}"

  if [ ! -f "$FILE" ]; then
    touch "$FILE"
    return 2
  fi

  local VALUE="$(grep "^$KEY=" "$FILE" | cut -f 2- -d '=' | head -n 1)"
  if [ -n "$VALUE" ]; then
    return 0
  else
    return 1
  fi
}

function get_loaded_config() {
  local CONFIG_CONTENTS="$1"
  local KEY="$2"
  local DEFAULT_VALUE="$3"

  local VALUE="$(grep "^$KEY=" <(echo "$CONFIG_CONTENTS") | cut -f 2- -d '=' | head -n 1)"
  if [ -n "$VALUE" ]; then
    echo "$VALUE"
  elif [ -n "$DEFAULT_VALUE" ]; then
    echo "$DEFAULT_VALUE"
  fi
}

function get_config() {
  local KEY="$1"
  local DEFAULT_VALUE="$2"
  local FILE="${3:-$CONFIG_INI}"

  ensure_file_exists "$FILE"

  local VALUE="$(grep "^$KEY=" "$FILE" | cut -f 2- -d '=' | head -n 1)"
  if [ -n "$VALUE" ]; then
    echo "$VALUE"
  elif [ -n "$DEFAULT_VALUE" ]; then
    echo "$DEFAULT_VALUE"
  fi
}

function get_or_set_config() {
  local KEY="$1"
  local DEFAULT_VALUE="$2"
  local FILE="${3:-$CONFIG_INI}"

  ensure_file_exists "$FILE"

  local VALUE="$(grep "^$KEY=" "$FILE" | cut -f 2- -d '=' | head -n 1)"
  if [ -n "$VALUE" ]; then
    echo "$VALUE"
  else
    set_config "$KEY" "$DEFAULT_VALUE" "$FILE"
    echo "$DEFAULT_VALUE"
  fi
}

function get_required_config() {
  local KEY="$1"
  local FILE="${2:-$CONFIG_INI}"

  ensure_file_exists "$FILE"

  local VALUE="$(get_config "$KEY" "" "$FILE")"
  if [[ -z "$VALUE" ]]; then
    echo "Required config not found! Key='$KEY' in '$FILE'"
    exit 100
  fi
  echo "$VALUE"
}

function get_config_keys() {
  local FILE="${1:-$CONFIG_INI}"

  ensure_file_exists "$FILE"

  local KEYS="$(cat "$FILE" | cut -f 1 -d '=' | sort -ur)"
  echo "$KEYS"
}

