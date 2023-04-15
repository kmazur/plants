#!/bin/bash

WORK_DIR="$HOME/WORK"
WORKSPACE_DIR="$WORK_DIR"/workspace
GIT_REPO_DIR="$WORKSPACE_DIR"/plants

git config --global pull.ff only

if [ -d "$GIT_REPO_DIR" ]; then
  echo "Git repo seems to be initialized at: $GIT_REPO_DIR"
  cd "$GIT_REPO_DIR" || exit 1
  git reset --hard HEAD
  git clean -x -f
  git pull
else
  echo "Git repo at $GIT_REPO_DIR not initialized. Initializing..."
  mkdir -p "$WORKSPACE_DIR"
  cd "$WORKSPACE_DIR" || exit 1

  git clone -q https://github.com/kmazur/plants.git
  cd "$GIT_REPO_DIR" || exit 1
fi
