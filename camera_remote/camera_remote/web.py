from __future__ import annotations

import argparse
import html
import json
import logging
import mimetypes
import re
import signal
import sys
import threading
import time
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import List, Optional
from urllib.parse import parse_qs, quote, unquote, urlparse

from .camera import LiveCamera
from .config import AppConfig, load_config
from .locking import CameraBusy, CameraLock
from .storage import SnapshotStorage
from .tatry import get_bootstrap

log = logging.getLogger(__name__)
TOKEN_RE = re.compile(r"([?&]token=)[^&\s\"]+")
TOKEN_COOKIE = "camera_token"
TOKEN_COOKIE_MAX_AGE = 60 * 60 * 24 * 365


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


class LiveSession:
    def __init__(self, config: AppConfig):
        self.config = config
        self._state_lock = threading.Lock()
        self._camera_lock_ctx = None
        self._camera = None
        self._clients = 0

    def acquire(self) -> LiveCamera:
        with self._state_lock:
            self._clients += 1
            if self._camera is None:
                self._camera_lock_ctx = CameraLock(self.config.paths.lock_file, blocking=False)
                try:
                    self._camera_lock_ctx.__enter__()
                except CameraBusy:
                    self._clients -= 1
                    self._camera_lock_ctx = None
                    raise
                self._camera = LiveCamera(self.config.camera)
                self._camera.start()
                log.info("live camera started")
            return self._camera

    def release(self) -> None:
        with self._state_lock:
            self._clients = max(0, self._clients - 1)
            if self._clients == 0:
                camera = self._camera
                lock_ctx = self._camera_lock_ctx
                self._camera = None
                self._camera_lock_ctx = None
            else:
                camera = None
                lock_ctx = None
        if camera is not None:
            camera.stop()
            log.info("live camera stopped")
        if lock_ctx is not None:
            lock_ctx.__exit__(None, None, None)

    @property
    def clients(self) -> int:
        with self._state_lock:
            return self._clients


def token_param(token: str) -> str:
    if not token:
        return ""
    return "token=" + quote(token)


def href(path: str, token: str) -> str:
    suffix = token_param(token)
    if not suffix:
        return path
    sep = "&" if "?" in path else "?"
    return f"{path}{sep}{suffix}"


def _clamp(value: int, minimum: int, maximum: int) -> int:
    return max(minimum, min(maximum, value))


class CameraRequestHandler(BaseHTTPRequestHandler):
    server_version = "CameraRemote/0.1"

    @property
    def app_config(self) -> AppConfig:
        return self.server.app_config  # type: ignore[attr-defined]

    @property
    def storage(self) -> SnapshotStorage:
        return self.server.storage  # type: ignore[attr-defined]

    @property
    def live(self) -> LiveSession:
        return self.server.live  # type: ignore[attr-defined]

    @property
    def tatry_pages(self) -> List[Path]:
        return self.server.tatry_pages  # type: ignore[attr-defined]

    def log_message(self, fmt: str, *args) -> None:
        message = TOKEN_RE.sub(r"\1***", fmt % args)
        log.info("%s - %s", self.address_string(), message)

    def end_headers(self) -> None:
        token = getattr(self, "_cookie_token", None)
        if token:
            self.send_header(
                "Set-Cookie",
                f"{TOKEN_COOKIE}={token}; Path=/; Max-Age={TOKEN_COOKIE_MAX_AGE}; "
                "HttpOnly; SameSite=Lax",
            )
            self._cookie_token = None
        super().end_headers()

    def do_GET(self) -> None:
        self._cookie_token = None
        parsed = urlparse(self.path)
        if parsed.path == "/healthz":
            self._send_text("ok\n", "text/plain")
            return
        if not self._authorized(parsed.query):
            self._send_text("unauthorized\n", "text/plain", HTTPStatus.UNAUTHORIZED)
            return

        if parsed.path == "/":
            self._send_html(self._index_html(parsed.query))
        elif parsed.path == "/latest.jpg":
            self._send_file(self.storage.latest_path)
        elif parsed.path == "/live.mjpg":
            self._send_mjpeg()
        elif parsed.path == "/api/status":
            self._send_json(self._status())
        elif parsed.path == "/api/bootstrap":
            self._send_tatry_bootstrap(parsed.query)
        elif parsed.path == "/api/capture-now":
            self._capture_now()
        elif parsed.path == "/checklista-tatry.html":
            self._send_tatry_page()
        elif parsed.path == "/history":
            self._send_html(self._history_index_html(parsed.query))
        elif parsed.path.startswith("/history/"):
            self._handle_history(parsed.path, parsed.query)
        else:
            self._send_text("not found\n", "text/plain", HTTPStatus.NOT_FOUND)

    def _authorized(self, query: str) -> bool:
        token = self.app_config.server.auth_token
        if not token:
            return True
        params = parse_qs(query)
        if params.get("token", [""])[0] == token:
            self._cookie_token = token
            return True
        if self.headers.get("X-Camera-Token", "") == token:
            self._cookie_token = token
            return True
        raw_cookie = self.headers.get("Cookie")
        if raw_cookie:
            jar = SimpleCookie()
            try:
                jar.load(raw_cookie)
            except Exception:
                jar = SimpleCookie()
            morsel = jar.get(TOKEN_COOKIE)
            if morsel is not None and morsel.value == token:
                return True
        return False

    def _status(self) -> dict:
        meta = self.storage.latest_meta()
        return {
            "latest": meta,
            "live_clients": self.live.clients,
            "data_dir": str(self.app_config.paths.data_dir),
            "history_days": [p.name for p in self.storage.date_dirs()],
        }

    def _capture_now(self) -> None:
        result = self.storage.capture_once(blocking=False)
        if result.skipped:
            self._send_json({"ok": False, "skipped": True, "message": result.message}, HTTPStatus.CONFLICT)
            return
        self._send_json({"ok": True, "path": str(result.path), "timestamp": result.timestamp.isoformat()})

    def _send_tatry_bootstrap(self, query: str) -> None:
        params = parse_qs(query)
        fresh = params.get("fresh", [""])[0] == "1"
        try:
            self._send_json(get_bootstrap(fresh=fresh))
        except Exception as exc:
            log.exception("tatry bootstrap failed: %s", exc)
            self._send_json({"error": str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def _send_tatry_page(self) -> None:
        for path in self.tatry_pages:
            if path.exists() and path.is_file():
                self._send_file(path)
                return
        self._send_text("not found\n", "text/plain", HTTPStatus.NOT_FOUND)

    def _send_json(self, payload: dict, status: HTTPStatus = HTTPStatus.OK) -> None:
        data = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_text(self, text: str, content_type: str, status: HTTPStatus = HTTPStatus.OK) -> None:
        data = text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type + "; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_html(self, text: str, status: HTTPStatus = HTTPStatus.OK) -> None:
        self._send_text(text, "text/html", status)

    def _send_file(self, path: Path) -> None:
        if not path.exists() or not path.is_file():
            self._send_text("not found\n", "text/plain", HTTPStatus.NOT_FOUND)
            return
        content_type = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(path.stat().st_size))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        with path.open("rb") as fh:
            while True:
                chunk = fh.read(1024 * 64)
                if not chunk:
                    break
                self.wfile.write(chunk)

    def _send_mjpeg(self) -> None:
        try:
            camera = self.live.acquire()
        except CameraBusy:
            self._send_text("camera busy\n", "text/plain", HTTPStatus.CONFLICT)
            return
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        try:
            while True:
                frame = camera.capture_jpeg_bytes()
                self.wfile.write(b"--frame\r\n")
                self.wfile.write(b"Content-Type: image/jpeg\r\n")
                self.wfile.write(f"Content-Length: {len(frame)}\r\n\r\n".encode("ascii"))
                self.wfile.write(frame)
                self.wfile.write(b"\r\n")
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as exc:
            log.exception("live stream failed: %s", exc)
        finally:
            self.live.release()

    def _handle_history(self, path: str, query: str) -> None:
        parts = [unquote(p) for p in path.split("/") if p]
        if len(parts) == 2:
            self._send_html(self._history_day_html(parts[1], query))
            return
        if len(parts) == 3:
            day, filename = parts[1], parts[2]
            target = self.storage.history_dir / day / filename
            try:
                target.resolve().relative_to(self.storage.history_dir.resolve())
            except ValueError:
                self._send_text("bad path\n", "text/plain", HTTPStatus.BAD_REQUEST)
                return
            self._send_file(target)
            return
        self._send_text("not found\n", "text/plain", HTTPStatus.NOT_FOUND)

    def _layout(self, title: str, body: str) -> str:
        return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)}</title>
  <style>
    :root {{ color-scheme: dark; font-family: system-ui, -apple-system, Segoe UI, sans-serif; }}
    body {{ margin: 0; background: #111; color: #eee; }}
    header {{ position: sticky; top: 0; z-index: 1; background: #181818; border-bottom: 1px solid #333; }}
    nav {{ display: flex; gap: 8px; align-items: center; padding: 10px 12px; overflow-x: auto; }}
    a, button {{ color: #fff; background: #2b2b2b; border: 1px solid #444; border-radius: 6px; padding: 8px 10px; text-decoration: none; font-size: 14px; }}
    select, input {{ color: #fff; background: #202020; border: 1px solid #444; border-radius: 6px; padding: 8px 10px; font-size: 14px; }}
    label {{ display: grid; gap: 4px; color: #bbb; font-size: 13px; }}
    main {{ max-width: 1100px; margin: 0 auto; padding: 12px; }}
    img {{ max-width: 100%; height: auto; display: block; background: #050505; }}
    .hero {{ width: 100%; border: 1px solid #333; border-radius: 6px; }}
    .meta {{ color: #bbb; font-size: 13px; margin: 8px 0 14px; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(170px, 1fr)); gap: 10px; }}
    .controls {{ display: flex; flex-wrap: wrap; gap: 10px; align-items: end; margin: 0 0 12px; }}
    .navrow {{ display: flex; gap: 8px; flex-wrap: wrap; margin: 10px 0 12px; }}
    .selected {{ outline: 2px solid #e6b450; }}
    .thumb {{ border: 1px solid #333; border-radius: 6px; overflow: hidden; background: #181818; }}
    .thumb span {{ display: block; padding: 7px 8px; font-size: 13px; color: #ccc; }}
    .live {{ width: 100%; border: 1px solid #333; border-radius: 6px; }}
    .warn {{ color: #ffcc66; }}
  </style>
</head>
<body>
  <header><nav>
    <a href="{href('/', self.app_config.server.auth_token)}">Kamera</a>
    <a href="{href('/live.mjpg', self.app_config.server.auth_token)}">Live</a>
    <a href="{href('/history', self.app_config.server.auth_token)}">Historia</a>
    <a href="{href('/checklista-tatry.html', self.app_config.server.auth_token)}">Tatry</a>
    <a href="{href('/api/status', self.app_config.server.auth_token)}">Status</a>
    <a href="{href('/api/capture-now', self.app_config.server.auth_token)}">Zdjęcie</a>
  </nav></header>
  <main>{body}</main>
</body>
</html>"""

    def _index_html(self, query: str) -> str:
        meta = self.storage.latest_meta()
        ts = html.escape(str(meta.get("timestamp", "no snapshot yet")))
        latest_url = href(f"/latest.jpg?cache={int(time.time())}", self.app_config.server.auth_token)
        body = f"""
<img class="hero" src="{latest_url}" alt="latest camera snapshot">
<div class="meta">Latest: {ts}</div>
"""
        return self._layout("Camera", body)

    def _history_index_html(self, query: str) -> str:
        days = self.storage.date_dirs()
        if not days:
            body = '<p class="warn">No history yet.</p>'
        else:
            items = "\n".join(
                f'<a href="{href("/history/" + quote(day.name), self.app_config.server.auth_token)}">{html.escape(day.name)}</a>'
                for day in days
            )
            body = f"<div class=\"grid\">{items}</div>"
        return self._layout("History", body)

    def _history_day_html(self, day: str, query: str) -> str:
        images = self.storage.images_for_day(day, newest_first=False)
        if not images:
            body = '<p class="warn">No images for this day.</p>'
        else:
            params = parse_qs(query)
            selected_name = params.get("at", [""])[0]
            image_names = [p.name for p in images]
            if selected_name not in image_names:
                selected_name = image_names[-1]
            selected_index = image_names.index(selected_name)

            try:
                around = int(params.get("around", ["3"])[0])
            except ValueError:
                around = 3
            around = _clamp(around, 1, 12)

            start = max(0, selected_index - around)
            end = min(len(images), selected_index + around + 1)
            selected_path = images[selected_index]
            selected_url = href(f"/history/{quote(day)}/{quote(selected_path.name)}", self.app_config.server.auth_token)

            options = "\n".join(
                f'<option value="{html.escape(name)}"{" selected" if name == selected_name else ""}>{html.escape(name[:-4].replace("-", ":"))}</option>'
                for name in image_names
            )
            prev_link = ""
            next_link = ""
            if selected_index > 0:
                prev_name = images[selected_index - 1].name
                prev_link = f'<a href="{href(f"/history/{quote(day)}?at={quote(prev_name)}&around={around}", self.app_config.server.auth_token)}">Previous</a>'
            if selected_index < len(images) - 1:
                next_name = images[selected_index + 1].name
                next_link = f'<a href="{href(f"/history/{quote(day)}?at={quote(next_name)}&around={around}", self.app_config.server.auth_token)}">Next</a>'

            items = []
            for image_path in images[start:end]:
                url = href(f"/history/{quote(day)}/{quote(image_path.name)}", self.app_config.server.auth_token)
                label = html.escape(image_path.stem.replace("-", ":"))
                active = " selected" if image_path.name == selected_name else ""
                select_url = href(
                    f"/history/{quote(day)}?at={quote(image_path.name)}&around={around}",
                    self.app_config.server.auth_token,
                )
                items.append(f'<a class="thumb{active}" href="{select_url}"><img src="{url}" alt="{label}"><span>{label}</span></a>')

            body = f"""
<form class="controls" method="get" action="/history/{html.escape(day)}">
  <input type="hidden" name="token" value="{html.escape(self.app_config.server.auth_token)}">
  <label>Snapshot
    <select name="at">{options}</select>
  </label>
  <label>Before/after
    <input name="around" type="number" min="1" max="12" value="{around}">
  </label>
  <button type="submit">Show</button>
</form>
<img class="hero" src="{selected_url}" alt="{html.escape(selected_path.stem.replace("-", ":"))}">
<div class="meta">{html.escape(day)} {html.escape(selected_path.stem.replace("-", ":"))} · {selected_index + 1}/{len(images)}</div>
<div class="navrow">{prev_link}{next_link}</div>
<div class="grid">{''.join(items)}</div>
"""
        return self._layout(day, body)


class CameraServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, server_address, config: AppConfig):
        super().__init__(server_address, CameraRequestHandler)
        self.app_config = config
        self.storage = SnapshotStorage(config)
        self.storage.ensure_dirs()
        self.repo_static_dir = Path(__file__).resolve().parents[1] / "static"
        self.static_dir = config.paths.data_dir / "static"
        self.static_dir.mkdir(parents=True, exist_ok=True)
        self.tatry_pages = [
            self.repo_static_dir / "checklista-tatry.html",
            self.static_dir / "checklista-tatry.html",
        ]
        self.live = LiveSession(config)

    def handle_error(self, request, client_address) -> None:
        exc_type, exc, _ = sys.exc_info()
        if exc_type in (BrokenPipeError, ConnectionResetError):
            log.info("%s - client disconnected: %s", client_address[0], exc)
            return
        super().handle_error(request, client_address)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="/etc/camera-remote/config.ini")
    args = parser.parse_args(argv)

    configure_logging()
    config = load_config(args.config)
    server = CameraServer((config.server.host, config.server.port), config)

    def stop(signum, frame) -> None:
        log.info("stopping camera remote")
        threading.Thread(target=server.shutdown, daemon=True).start()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    log.info("serving on http://%s:%s", config.server.host, config.server.port)
    server.serve_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
