#!/bin/bash

function set_terminal_title() {
  local PROMPT="$1"
  echo -ne "\033]0;$PROMPT\007"
}

function restart_cron_process() {
  local PROCESS_SUBSTRING="$1"
  if [ -z "$PROCESS_SUBSTRING" ]; then
    return 1
  fi

  local ENTRY_CMD="$(crontab -l | grep -v "^#" | sort -u | grep "$PROCESS_SUBSTRING" | cut -d ' ' -f 6-)"
  local ENTRY="$(crontab -l | grep -v "^#" | sort -u | grep "$PROCESS_SUBSTRING" | cut -d ' ' -f 7)"
  ENTRY="${ENTRY%\"}"
  ENTRY="${ENTRY#\"}"
  local LINES="$(echo -n "$ENTRY" | grep -c '^')"
  if [[ "$LINES" -ne "1" ]]; then
    return 2
  fi
  local PID="$(ps aux | grep "$ENTRY" | grep -v "grep.*$ENTRY" | tr -s ' ' | cut -f 2 -d ' ')"
  local PLINES="$(echo -n "$PID" | grep -c "^")"
  if [[ "$PLINES" -ne "1" ]]; then
    return 3
  fi
  kill "$PID" && "$ENTRY_CMD"
}