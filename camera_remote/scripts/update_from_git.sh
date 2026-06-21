#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="${CAMERA_REMOTE_REPO_DIR:-/home/user/IdeaProjects/plants}"
BRANCH="${CAMERA_REMOTE_BRANCH:-main}"
LOCK_FILE="${CAMERA_REMOTE_UPDATE_LOCK:-/tmp/camera-remote-update.lock}"
STACK_DIR="$REPO_DIR/camera_remote"

exec 9>"$LOCK_FILE"
if ! flock -n 9; then
  echo "another update is already running"
  exit 0
fi

cd "$REPO_DIR"

if [ ! -d .git ]; then
  echo "not a git repository: $REPO_DIR" >&2
  exit 1
fi

current_branch="$(git branch --show-current)"
if [ "$current_branch" != "$BRANCH" ]; then
  echo "unexpected branch: $current_branch; expected: $BRANCH" >&2
  exit 1
fi

if [ -n "$(git status --porcelain)" ]; then
  echo "working tree is not clean; refusing to update" >&2
  git status --short >&2
  exit 1
fi

git fetch --prune origin "+refs/heads/$BRANCH:refs/remotes/origin/$BRANCH"

old_sha="$(git rev-parse HEAD)"
remote_sha="$(git rev-parse "origin/$BRANCH")"

if [ "$old_sha" = "$remote_sha" ]; then
  echo "already up to date: $old_sha"
  exit 0
fi

if ! git merge-base --is-ancestor "$old_sha" "$remote_sha"; then
  echo "remote is not a fast-forward from local HEAD" >&2
  echo "local:  $old_sha" >&2
  echo "remote: $remote_sha" >&2
  exit 1
fi

git merge --ff-only "$remote_sha"

if [ ! -d "$STACK_DIR" ]; then
  echo "missing stack directory after update: $STACK_DIR" >&2
  exit 1
fi

sudo -n install -m 0644 "$STACK_DIR/systemd/camera-remote.service" /etc/systemd/system/camera-remote.service
sudo -n install -m 0644 "$STACK_DIR/systemd/camera-snapshot.service" /etc/systemd/system/camera-snapshot.service
sudo -n install -m 0644 "$STACK_DIR/systemd/camera-snapshot.timer" /etc/systemd/system/camera-snapshot.timer
sudo -n install -m 0644 "$STACK_DIR/systemd/camera-remote-update.service" /etc/systemd/system/camera-remote-update.service
sudo -n install -m 0644 "$STACK_DIR/systemd/camera-remote-update.timer" /etc/systemd/system/camera-remote-update.timer
sudo -n systemctl daemon-reload
sudo -n systemctl enable --now camera-remote.service
sudo -n systemctl enable --now camera-snapshot.timer
sudo -n systemctl enable --now camera-remote-update.timer
sudo -n systemctl restart camera-remote.service
sudo -n systemctl restart camera-snapshot.timer
sudo -n systemctl restart camera-remote-update.timer

echo "updated from $old_sha to $(git rev-parse HEAD)"
