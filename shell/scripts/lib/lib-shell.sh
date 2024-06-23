#!/bin/bash

function set_terminal_title() {
  local PROMPT="$1"
  echo -ne "\033]0;$PROMPT\007"
}


function stop_cron_process() {
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
  if [[ "$PLINES" -eq "0" ]]; then
    return 0
  fi

  if [[ "$PLINES" -ne "1" ]]; then
    return 3
  fi
  kill "$PID"
}

function restart_cron_process() {
  local PROCESS_SUBSTRING="$1"
  local ENTRY_CMD="$(crontab -l | grep -v "^#" | sort -u | grep "$PROCESS_SUBSTRING" | cut -d ' ' -f 6-)"
  stop_cron_process "$1" && $ENTRY_CMD
}


function update_repo() {
    "$REPO_DIR/meta/git-update.sh"
    cp -f "$WORK_DIR/workspace/plants/shell/.profile" "$HOME"
    cp -f "$REPO_DIR/meta/files/vim/.vimrc" "$HOME"
    source "$HOME/.profile"
}

function compile_native() {
    "$REPO_DIR/meta/compile.sh" "$1"
}

function start_periodic_checks() {
    "$REPO_DIR/shell/scripts/cron/run_all_periodics.sh" &>> /home/user/cron.log
}

function stop_periodic_checks() {
    "$REPO_DIR/shell/scripts/cron/stop_all_periodics.sh" &>> /home/user/cron.log
}

function restart_scheduler() {
    local PID="$(ps aux | grep run-scheduler.sh | grep -v grep | tr -s ' ' | cut -d' ' -f 2)"
    if [ -n "$PID" ]; then
        kill_tree "$PID"
    fi
    "$REPO_DIR/shell/cron/run_periodic_check.sh" "run-scheduler" &>> /home/user/cron.log
}

function restart_all() {
    stop_periodic_checks
    rm /dev/shm/REQUESTS.txt &> /dev/null
    update_repo
    compile_native
    start_periodic_checks
}