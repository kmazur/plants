#!/usr/bin/env bash

PROCESS_NAME="temperatures"

mkdir -p "$HOME/WORK/tmp/locks"
LOCK_FILE="$HOME/WORK/tmp/locks/$PROCESS_NAME.lock"
if [ -f "$LOCK_FILE" ]; then
  echo "Lock file exists: $LOCK_FILE. Exiting!"
  exit 0
fi
touch "$LOCK_FILE"

function finally_func() {
  echo "Cleaning up the lock file: $LOCK_FILE"
  rm -f "$LOCK_FILE"
}
trap finally_func EXIT

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

cd "$LOGS_DIR" || exit 1

PROGRAM_AND_ARGS="python $REPO_DIR/python/reporting/w1therm-push.py &>> $LOGS_DIR/$PROCESS_NAME.log"
CMD='echo $$>'$PID_FILE' && exec '$PROGRAM_AND_ARGS
echo "Running command: '$CMD'"
/usr/bin/env bash -c "$CMD" &
echo "Done"



