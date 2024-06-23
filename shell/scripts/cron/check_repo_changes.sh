#!/usr/bin/env bash

source "$HOME/.profile"
source "$LIB_INIT_FILE"

cd "$REPO_DIR" || exit 1

BRANCH="main"
REMOTE="origin"
git fetch $REMOTE

LOCAL=$(git rev-parse $BRANCH)
REMOTE=$(git rev-parse $REMOTE/$BRANCH)
if [ $LOCAL != $REMOTE ]; then
    restart_all
else
    echo "No remote changes detected."
fi
