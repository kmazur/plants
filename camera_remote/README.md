# Camera Remote

Small standalone camera stack for Raspberry Pi. It is intentionally separate
from the older `WORK/tmp/pipeline` / cron framework.

## What It Does

- Keeps a lightweight snapshot history.
- Serves a mobile-friendly web page with the latest image and a focused
  before/after history selector.
- Provides an on-demand MJPEG live view.
- Uses a camera lock so snapshots and live view do not fight for `libcamera`.
- Runs from systemd and comes back after a Pi reboot or power cycle.

## Layout On The Pi

Default runtime paths:

```text
/etc/camera-remote/config.ini
/home/user/camera-remote-data/latest.jpg
/home/user/camera-remote-data/history/YYYY-MM-DD/HH-MM-SS.jpg
/home/user/IdeaProjects/plants/camera_remote/static/checklista-tatry.html
```

By default the web server binds to `127.0.0.1`, so it is reachable only from
the Pi itself and from local tunnel clients such as PiTunnel. Set
`server.host = 0.0.0.0` only if you intentionally want direct LAN access.

## Install

From this directory on the Raspberry Pi:

```bash
./scripts/install.sh
```

The installer copies systemd units, creates `/etc/camera-remote/config.ini`
if missing, generates an auth token if needed, and enables:

```text
camera-remote.service
camera-snapshot.timer
camera-remote-update.timer
```

Check status:

```bash
./scripts/status.sh
```

## Access

The installer prints a URL like:

```text
http://127.0.0.1:8090/?token=...
```

For remote access, use a private tunnel or the `Custom` host and port shown by
PiTunnel. Do not publish this service directly to the internet without a tunnel
or VPN layer.

The bundled timer captures once per minute. Change `OnUnitInactiveSec` in
`systemd/camera-snapshot.timer` if you need a different cadence.

For PiTunnel free/custom TCP access, expose only this new stack port, not the
old framework:

```bash
pitunnel --port=8090 --host=127.0.0.1 --name=plants-camera --persist
```

Then open the `Custom` host and port shown by PiTunnel:

```text
http://eu1.pitunnel.com:PORT/?token=...
```

Do not use PiTunnel's `HTTP` tunnel type unless the account plan allows it.
If paid HTTP tunnels are enabled, add `--http --http-auth username:password`
to enforce Basic Auth before requests reach the Python app.

## Tatry Checklist

The server exposes `/checklista-tatry.html` from the Git checkout:

```text
/home/user/IdeaProjects/plants/camera_remote/static/checklista-tatry.html
```

The Python app provides the `/api/bootstrap` data endpoint used by the page.
For compatibility, a runtime copy at
`/home/user/camera-remote-data/static/checklista-tatry.html` is still accepted
as a fallback if the repo copy is missing.

## Admin Panel (remote shell)

A token-gated page at `/admin` can run shell commands on the Pi as the service
user. It is **disabled by default**. Enable it by setting a strong, separate
token in `/etc/camera-remote/config.ini`:

```ini
[server]
admin_token = <python3 -c "import secrets;print(secrets.token_hex(24))">
admin_timeout = 60
```

Then restart `camera-remote.service`. The page appears in the nav as `Admin`.

Security model:

- The admin token is **separate** from the view `auth_token` and is sent only
  in the `X-Admin-Token` header (kept in the browser's `localStorage`, never in
  a link). It is compared in constant time.
- `/api/admin/exec` requires **both** the view token (query/cookie) and the
  admin token, and returns 403 when the panel is disabled.
- Every command is logged (`ADMIN exec from <ip>: <cmd>`) and killed after
  `admin_timeout` seconds.
- Keep this behind the local bind/tunnel; do not expose the service directly.

## Services

```bash
sudo systemctl status camera-remote.service
sudo systemctl status camera-snapshot.timer
sudo systemctl status camera-remote-update.timer
sudo journalctl -u camera-remote.service -f
```

## Git Updates

`camera-remote-update.timer` checks `origin/main` every few minutes. When a new
commit is available, it fast-forwards `/home/user/IdeaProjects/plants`, reloads
the systemd units, and restarts `camera-remote.service`.

The updater refuses to run if the Pi working tree has local changes. Commit and
push from another machine; the Pi should only pull.

After each update, the updater validates Python syntax, restarts the stack, and
checks `http://127.0.0.1:8090/healthz`. If the new commit does not pass that
health check, it resets the Pi checkout back to the previous commit and restarts
the last working version.

To trigger a check immediately:

```bash
sudo systemctl start camera-remote-update.service
```

Snapshot now:

```bash
./scripts/capture_once.sh
```

Uninstall systemd units without deleting history:

```bash
./scripts/uninstall.sh
```
