#!/usr/bin/env bash

source "$HOME/.profile"
source "$LIB_INIT_FILE"

while true; do
  cd "$REPO_DIR" || exit 1

  BRANCH="main"
  REMOTE="origin"
  git fetch $REMOTE
  update_repo

  sleep 3600
done