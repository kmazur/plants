#!/usr/bin/env bash

source "$HOME/.profile"
source "$LIB_INIT_FILE"

declare CRON_FILE="$REPO_DIR/shell/scripts/cron/$MACHINE_NAME.cron"
if [ ! -f "$CRON_FILE" ]; then
  log_warn "Cron file for '$MACHINE_NAME' not found"
  exit 1
fi

COMMANDS="$(cat "$CRON_FILE" | grep "run_periodic_check.sh" | grep -v "^#" | cut -d ' ' -f 6-)"
PROCESS_NAMES="$(echo "$COMMANDS" | cut -d' ' -f 2 | xargs -I {} echo "$(strip "{}")")"

for NAME in $PROCESS_NAMES; do
  PROCESS_NAME="$NAME"
  LOCK_FILE="$LOCKS_DIR/$PROCESS_NAME.lock"
  if [ -f "$LOCK_FILE" ]; then
    continue
  fi

  PID_FILE="$LOCKS_DIR/$PROCESS_NAME.pid"
  if [ -f "$PID_FILE" ]; then
    echo "Pid file exists: $PID_FILE. Checking if the process is running"
    PID=$(cat "$PID_FILE")
    if ps -p "$PID" > /dev/null
    then
      continue
    fi
  fi

  COMMAND="$(echo "$COMMANDS" | grep "$PROCESS_NAME" | head -n 1)"
  eval "$COMMAND"

done
