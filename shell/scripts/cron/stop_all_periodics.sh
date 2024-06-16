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
  PID_FILE="$LOCKS_DIR/$PROCESS_NAME.pid"
  if [ -f "$PID_FILE" ]; then
    echo "Pid file exists: $PID_FILE. Checking if the process is running"
    PID=$(cat "$PID_FILE")
    if ps -p "$PID" > /dev/null; then
      kill_tree "$PID"
    fi
  fi
done

PIDS="$(ps aux | grep "^user" | grep -v "\-bash$" | grep -v "grep" | grep -v "ps aux" | grep -v "sshd:" | grep -v "sd-pam" | grep -v "systemd")"
for PID in $PIDS; do
  echo "Killing additional process: pid=$PID, ps='$(ps aux | grep $PID)'"
  kill "$PID"
done