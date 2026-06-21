#!/usr/bin/env bash
set -euo pipefail

if [ "${CAMERA_REMOTE_UPDATE_REEXEC:-0}" != "1" ]; then
  tmp_script="$(mktemp /tmp/camera-remote-update.XXXXXX)"
  cp "$0" "$tmp_script"
  chmod 0755 "$tmp_script"
  CAMERA_REMOTE_UPDATE_REEXEC=1 CAMERA_REMOTE_UPDATE_TMP="$tmp_script" exec "$tmp_script" "$@"
fi

if [ -n "${CAMERA_REMOTE_UPDATE_TMP:-}" ]; then
  trap 'rm -f "$CAMERA_REMOTE_UPDATE_TMP"' EXIT
fi

REPO_DIR="${CAMERA_REMOTE_REPO_DIR:-/home/user/IdeaProjects/plants}"
BRANCH="${CAMERA_REMOTE_BRANCH:-main}"
LOCK_FILE="${CAMERA_REMOTE_UPDATE_LOCK:-/tmp/camera-remote-update.lock}"
STACK_DIR="$REPO_DIR/camera_remote"
HEALTH_URL="${CAMERA_REMOTE_HEALTH_URL:-http://127.0.0.1:8090/healthz}"
HEALTH_ATTEMPTS="${CAMERA_REMOTE_HEALTH_ATTEMPTS:-30}"
HEALTH_DELAY="${CAMERA_REMOTE_HEALTH_DELAY:-1}"

require_stack() {
  if [ ! -d "$STACK_DIR" ]; then
    echo "missing stack directory: $STACK_DIR" >&2
    return 1
  fi
}

validate_stack() {
  require_stack
  bash -n "$STACK_DIR/scripts/update_from_git.sh"
  python3 -m compileall -q "$STACK_DIR/camera_remote"
}

install_units() {
  sudo -n install -m 0644 "$STACK_DIR/systemd/camera-remote.service" /etc/systemd/system/camera-remote.service
  sudo -n install -m 0644 "$STACK_DIR/systemd/camera-snapshot.service" /etc/systemd/system/camera-snapshot.service
  sudo -n install -m 0644 "$STACK_DIR/systemd/camera-snapshot.timer" /etc/systemd/system/camera-snapshot.timer
  sudo -n install -m 0644 "$STACK_DIR/systemd/camera-remote-update.service" /etc/systemd/system/camera-remote-update.service
  sudo -n install -m 0644 "$STACK_DIR/systemd/camera-remote-update.timer" /etc/systemd/system/camera-remote-update.timer
  sudo -n systemctl daemon-reload
  sudo -n systemctl enable --now camera-remote.service
  sudo -n systemctl enable --now camera-snapshot.timer
  sudo -n systemctl enable --now camera-remote-update.timer
}

restart_units() {
  sudo -n systemctl restart camera-remote.service
  sudo -n systemctl restart camera-snapshot.timer
  sudo -n systemctl restart camera-remote-update.timer
}

wait_for_health() {
  python3 - "$HEALTH_URL" "$HEALTH_ATTEMPTS" "$HEALTH_DELAY" <<'PY'
import sys
import time
import urllib.request

url = sys.argv[1]
attempts = int(sys.argv[2])
delay = float(sys.argv[3])
last = "not checked"

for _ in range(attempts):
    try:
        with urllib.request.urlopen(url, timeout=3) as response:
            body = response.read(16)
            status = getattr(response, "status", 200)
            if status == 200 and body.startswith(b"ok"):
                print("health check ok")
                sys.exit(0)
            last = f"HTTP {status}: {body!r}"
    except Exception as exc:
        last = str(exc)
    time.sleep(delay)

print(f"health check failed for {url}: {last}", file=sys.stderr)
sys.exit(1)
PY
}

deploy_stack() {
  validate_stack
  install_units
  restart_units
  wait_for_health
}

rollback_to() {
  local old_sha="$1"
  echo "deploy failed; rolling back to $old_sha" >&2
  git reset --hard "$old_sha"
  deploy_stack
  echo "rolled back to $(git rev-parse HEAD)"
}

ensure_current_health() {
  if wait_for_health; then
    return 0
  fi
  echo "current service failed health check; redeploying current checkout" >&2
  deploy_stack
}

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

ensure_current_health

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

if ! deploy_stack; then
  rollback_to "$old_sha"
  exit 1
fi

echo "updated from $old_sha to $(git rev-parse HEAD)"
