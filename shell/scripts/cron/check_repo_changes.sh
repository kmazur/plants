#!/usr/bin/env bash

source "$HOME/.profile"
source "$LIB_INIT_FILE"

while true; do
  cd "$REPO_DIR" || exit 1

  BRANCH="main"
  REMOTE="origin"
  git fetch $REMOTE

  LOCAL=$(git rev-parse $BRANCH)
  REMOTE=$(git rev-parse $REMOTE/$BRANCH)
  if [ $LOCAL != $REMOTE ]; then
    log "Changes detected - restarting all"
    restart_all
  else
    log "No remote changes detected."
  fi

  sleep 10
done