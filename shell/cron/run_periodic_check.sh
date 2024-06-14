#!/usr/bin/env bash

# Enable error handling
set -e
trap 'catch_error $LINENO' ERR

catch_error() {
  echo "Error occurred at line $1. Exiting." >> /home/user/cron_error.log
}

echo "Wrapper started with parameters: $@"
echo "Current directory: $(pwd)"
echo "I am: $(whoami)"
echo "Environment variables: $(printenv)"
echo "Sourcing the profile from $HOME/.profile"
source "$HOME/.profile"
echo "Sourcing $LIB_INIT_FILE"
source "$LIB_INIT_FILE"

PROCESS_NAME="$1"
LOCK_FILE="$LOCKS_DIR/$PROCESS_NAME.lock"
if [ -f "$LOCK_FILE" ]; then
  echo "Lock file exists: $LOCK_FILE. Exiting!"
  exit 0
fi
touch "$LOCK_FILE" || exit 1

function finally_func() {
  echo "Cleaning up the lock file: $LOCK_FILE"
  rm -f "$LOCK_FILE"
}
trap finally_func EXIT


PID_FILE="$LOCKS_DIR/$PROCESS_NAME.pid"
if [ -f "$PID_FILE" ]; then
  echo "Pid file exists: $PID_FILE. Checking if the process is running"
  PID=$(cat "$PID_FILE")
  if ps -p "$PID" > /dev/null
  then
     echo "$PROCESS_NAME with $PID is running"
     exit 0
  fi
fi

echo "Pid file does not exist or there is no process with pid! Running process: $PROCESS_NAME"

cd "$LOGS_DIR" || exit 1

LOG_FILE="$(get_logs_dir)/$PROCESS_NAME.log"
ensure_file_exists "$LOG_FILE"

{
  echo "# ========="
  echo "# Starting '$PROCESS_NAME' at $(get_current_date_time_dashed)"
  echo "# ---------"
} >> "$LOG_FILE"

shift

CRON_SCRIPTS_DIR="$REPO_DIR/shell/scripts/cron"
PROGRAM_AND_ARGS="$CRON_SCRIPTS_DIR/$PROCESS_NAME.sh $* &>> $LOG_FILE"
CMD='echo $$>'$PID_FILE' && exec '$PROGRAM_AND_ARGS
echo "# Running command: '$CMD'" >> "$LOG_FILE"
/usr/bin/env bash -c "$CMD" &

echo "# PROCESS: '$PROCESS_NAME' is running on PID: $(cat "$PID_FILE")" >> "$LOG_FILE"



