#!/bin/bash

LOCK_DIR="$HOME/WORK/tmp/locks"

function is_locked() {
  local PROCESS_NAME="$1"

  mkdir -p "$LOCK_DIR"
  LOCK_FILE="$LOCK_DIR/$PROCESS_NAME.lock"
  if [ -f "$LOCK_FILE" ]; then
    true
  else
    false
  fi
}

function lock_process() {
  local PROCESS_NAME="$1"

  mkdir -p "$LOCK_DIR"
  LOCK_FILE="$LOCK_DIR/$PROCESS_NAME.lock"
  touch "$LOCK_FILE"

  function finally_func() {
    rm -f "$LOCK_FILE"
  }
  trap finally_func EXIT
}



source "$HOME/.profile"

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

cd "$VIDEO_DIR" || exit 1

PROGRAM_AND_ARGS="sudo nice -n -20 libcamerify motion &>> $LOGS_DIR/$PROCESS_NAME.log"
CMD='echo $$>'$PID_FILE' && exec '$PROGRAM_AND_ARGS
echo "Running command: '$CMD'"
/usr/bin/env bash -c "$CMD" &
echo "Done"


