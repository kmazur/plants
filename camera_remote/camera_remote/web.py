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


PAGE_CSS = """
:root{
  --bg:#f3f6f4; --card:#ffffff; --ink:#1d2b24; --muted:#698075;
  --border:#e4ebe6; --border-strong:#cdd9d1; --primary:#2f6f57; --primary-ink:#ffffff;
  --accent:#ef9b42; --ring:rgba(47,111,87,.35);
  --shadow:0 1px 2px rgba(20,40,30,.05), 0 6px 18px rgba(20,40,30,.05);
}
@media (prefers-color-scheme:dark){
  :root{
    --bg:#101a16; --card:#172620; --ink:#e7efe9; --muted:#9bb1a6;
    --border:#243730; --border-strong:#365045; --primary:#4eb389; --primary-ink:#0b1812;
    --accent:#f0a85a; --ring:rgba(78,179,137,.4);
    --shadow:0 1px 2px rgba(0,0,0,.3), 0 8px 22px rgba(0,0,0,.25);
  }
}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%;scroll-behavior:smooth}
body{margin:0;background:var(--bg);color:var(--ink);line-height:1.45;
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif}
a{color:var(--primary);text-decoration:none}
img{max-width:100%;height:auto;display:block}
*{-webkit-tap-highlight-color:rgba(47,111,87,.16)}
a:focus-visible,button:focus-visible,select:focus-visible,input:focus-visible{
  outline:2px solid var(--ring);outline-offset:2px;border-radius:8px}

.topbar{position:sticky;top:0;z-index:20;border-bottom:1px solid var(--border);
  background:color-mix(in srgb,var(--card) 86%,transparent);backdrop-filter:saturate(1.4) blur(8px)}
.topbar-in{max-width:1100px;margin:0 auto;display:flex;align-items:center;gap:.7rem;padding:.55rem .8rem}
.brand{display:flex;align-items:center;gap:.5rem;font-weight:800;font-size:.98rem;white-space:nowrap}
.brand .dot{width:9px;height:9px;border-radius:50%;background:var(--accent);box-shadow:0 0 0 4px rgba(239,155,66,.18)}
.nav{display:flex;gap:.4rem;align-items:center;margin-left:auto;overflow-x:auto}
.nav a{flex:0 0 auto;color:var(--ink);background:transparent;border:1px solid var(--border);
  border-radius:.55rem;padding:.42rem .7rem;font-size:.86rem;font-weight:600;white-space:nowrap}
.nav a:hover{border-color:var(--border-strong)}
.nav a[aria-current="page"]{background:var(--primary);color:var(--primary-ink);border-color:var(--primary)}

.wrap{max-width:1100px;margin:0 auto;padding:1rem .8rem 2.5rem}
.card{background:var(--card);border:1px solid var(--border);border-radius:16px;box-shadow:var(--shadow);overflow:hidden}
.pad{padding:1rem 1.1rem}
.h{margin:.2rem 0 .15rem;font-size:1.2rem;letter-spacing:-.01em}
.sub{color:var(--muted);font-size:.85rem;margin:0 0 .2rem}

.hero-card{position:relative}
.hero{width:100%;display:block;background:#050807;aspect-ratio:16/9;object-fit:cover}
.viewer{width:100%;display:block;background:#050807;aspect-ratio:16/9;object-fit:contain}
.live-frame{background:#050807}
.live-frame img{width:100%;display:block}
.hero-bar{display:flex;align-items:center;gap:.6rem;flex-wrap:wrap;padding:.65rem 1rem;border-top:1px solid var(--border)}
.badge{display:inline-flex;align-items:center;gap:.4rem;font-size:.8rem;font-weight:700;color:var(--muted)}
.live-dot{width:8px;height:8px;border-radius:50%;background:#e0533f;animation:pulse 1.6s infinite}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.25}}
.spacer{flex:1}

.actions{display:flex;flex-wrap:wrap;gap:.55rem;margin:1rem 0 0}
.btn{display:inline-flex;align-items:center;gap:.45rem;border:1px solid var(--border);background:var(--card);
  color:var(--ink);font:inherit;font-size:.9rem;font-weight:700;padding:.6rem .9rem;border-radius:.7rem;
  cursor:pointer;box-shadow:var(--shadow)}
.btn:hover{border-color:var(--border-strong)}
.btn:active{transform:translateY(1px)}
.btn[disabled]{opacity:.6;cursor:default}
.btn-primary{background:var(--primary);color:var(--primary-ink);border-color:var(--primary)}
.btn-accent{background:var(--accent);color:#3a2410;border-color:var(--accent)}

.grid-days{display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:.8rem;margin-top:1rem}
.daycard{display:flex;flex-direction:column;background:var(--card);border:1px solid var(--border);
  border-radius:14px;overflow:hidden;box-shadow:var(--shadow);color:var(--ink);transition:transform .15s,border-color .15s}
.daycard:hover{border-color:var(--border-strong);transform:translateY(-2px)}
.daycard img{aspect-ratio:4/3;object-fit:cover;width:100%;background:#050807}
.dc-body{padding:.55rem .7rem;display:flex;justify-content:space-between;align-items:baseline;gap:.4rem}
.dc-day{font-weight:700;font-size:.9rem;font-variant-numeric:tabular-nums}
.dc-n{color:var(--muted);font-size:.76rem;font-variant-numeric:tabular-nums}

.controls{display:flex;flex-wrap:wrap;gap:.7rem;align-items:end;margin:.9rem 0}
.field{display:flex;flex-direction:column;gap:.25rem;font-size:.76rem;color:var(--muted)}
.field select,.field input{font:inherit;font-size:.9rem;color:var(--ink);background:var(--card);
  border:1px solid var(--border-strong);border-radius:.6rem;padding:.5rem .6rem}
.navrow{display:flex;gap:.5rem;flex-wrap:wrap;margin:.2rem 0 1rem}
.thumbs{display:grid;grid-template-columns:repeat(auto-fill,minmax(120px,1fr));gap:.6rem}
.thumb{border:1px solid var(--border);border-radius:11px;overflow:hidden;background:var(--card);color:var(--ink);transition:border-color .15s}
.thumb:hover{border-color:var(--border-strong)}
.thumb img{aspect-ratio:4/3;object-fit:cover}
.thumb span{display:block;padding:.4rem .5rem;font-size:.76rem;color:var(--muted);font-variant-numeric:tabular-nums}
.thumb.active{outline:2px solid var(--accent);outline-offset:-2px}

.empty{color:var(--muted);text-align:center;padding:2.5rem 1rem;font-size:.95rem}
.note{color:var(--muted);font-size:.82rem;margin:.9rem .2rem 0;line-height:1.5}

.toast{position:fixed;left:50%;bottom:18px;transform:translateX(-50%) translateY(20px);
  background:#1f2d27;color:#fff;font-size:.88rem;font-weight:600;padding:.6rem .9rem;border-radius:10px;
  box-shadow:0 8px 24px rgba(0,0,0,.3);opacity:0;pointer-events:none;transition:.25s;z-index:50;max-width:90vw}
.toast.show{opacity:1;transform:translateX(-50%) translateY(0)}
.toast.ok{background:#2f7d5b}
.toast.warn{background:#b2603b}
.foot{text-align:center;color:var(--muted);font-size:.76rem;margin-top:1.8rem}
.foot a{color:var(--muted)}
@media (prefers-reduced-motion:reduce){*{animation-duration:.001ms!important;transition-duration:.001ms!important}}
"""

PAGE_JS = """
(function(){
  var tok = window.CAM_TOKEN || "";
  function withTok(path){
    var u = new URL(path, location.origin);
    if(tok) u.searchParams.set("token", tok);
    return u.pathname + u.search;
  }
  function toast(msg, kind){
    var t = document.getElementById("toast");
    if(!t) return;
    t.textContent = msg;
    t.className = "toast show" + (kind ? " " + kind : "");
    clearTimeout(window.__toastT);
    window.__toastT = setTimeout(function(){ t.className = "toast"; }, 2600);
  }
  function fmtAgo(iso){
    var d = new Date(iso); if(isNaN(d.getTime())) return "";
    var s = Math.max(0, Math.round((Date.now() - d.getTime())/1000));
    if(s < 60) return s + " s temu";
    var m = Math.round(s/60); if(m < 60) return m + " min temu";
    var h = Math.round(m/60); if(h < 24) return h + " h temu";
    return Math.round(h/24) + " dni temu";
  }
  function paintAgo(){
    document.querySelectorAll("[data-ts]").forEach(function(el){
      var a = fmtAgo(el.getAttribute("data-ts"));
      if(a) el.textContent = a;
    });
  }
  paintAgo(); setInterval(paintAgo, 10000);

  function refreshHero(){
    var hero = document.getElementById("hero");
    if(!hero) return;
    hero.src = withTok("/latest.jpg?cache=" + Date.now());
    fetch(withTok("/api/status")).then(function(r){ return r.json(); }).then(function(s){
      var ts = s && s.latest && s.latest.timestamp;
      var el = document.getElementById("heroTs");
      if(ts && el){ el.setAttribute("data-ts", ts); el.textContent = fmtAgo(ts); }
    }).catch(function(){});
  }

  document.querySelectorAll("[data-capture]").forEach(function(btn){
    btn.addEventListener("click", async function(){
      btn.disabled = true;
      var old = btn.textContent;
      btn.textContent = "📸 Robię…";
      try{
        var r = await fetch(withTok("/api/capture-now"), { headers: { "Accept": "application/json" } });
        var j = await r.json();
        if(j.ok){ toast("Zdjęcie zrobione", "ok"); refreshHero(); }
        else { toast(j.message ? ("Pominięto: " + j.message) : "Kamera zajęta", "warn"); }
      }catch(e){ toast("Nie udało się zrobić zdjęcia", "warn"); }
      finally{ btn.disabled = false; btn.textContent = old; }
    });
  });

  var hero = document.getElementById("hero");
  if(hero && hero.dataset.auto === "1"){ setInterval(refreshHero, 15000); }
})();
"""


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
        elif parsed.path == "/live":
            self._send_html(self._live_html(parsed.query))
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

    def _nav(self, active: str) -> str:
        token = self.app_config.server.auth_token
        items = [
            ("/", "Kamera"),
            ("/live", "Live"),
            ("/history", "Historia"),
            ("/checklista-tatry.html", "Tatry"),
        ]
        links = []
        for path, label in items:
            current = ' aria-current="page"' if path == active else ""
            links.append(f'<a href="{href(path, token)}"{current}>{html.escape(label)}</a>')
        return "".join(links)

    def _layout(self, title: str, body: str, active: str = "") -> str:
        token = self.app_config.server.auth_token
        token_js = json.dumps(token)
        return f"""<!doctype html>
<html lang="pl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="theme-color" content="#2f6f57">
<title>{html.escape(title)}</title>
<style>{PAGE_CSS}</style>
</head>
<body>
<header class="topbar"><div class="topbar-in">
  <span class="brand"><span class="dot"></span>Budka · Kamera</span>
  <nav class="nav">{self._nav(active)}</nav>
</div></header>
<main class="wrap">{body}</main>
<footer class="foot">Plants · kamera Raspberry Pi · <a href="{href('/api/status', token)}">status</a></footer>
<div id="toast" class="toast"></div>
<script>window.CAM_TOKEN={token_js};</script>
<script>{PAGE_JS}</script>
</body>
</html>"""

    def _index_html(self, query: str) -> str:
        token = self.app_config.server.auth_token
        meta = self.storage.latest_meta()
        ts = meta.get("timestamp")
        latest_url = href(f"/latest.jpg?cache={int(time.time())}", token)
        if ts:
            ts_h = html.escape(str(ts))
            stamp = f'🕒 <span id="heroTs" data-ts="{ts_h}">{ts_h}</span>'
        else:
            stamp = "Brak zdjęcia — zrób pierwsze"
        days_n = len(self.storage.date_dirs())
        days_label = f" · {days_n} dni" if days_n else ""
        body = f"""
<div class="card hero-card">
  <img id="hero" class="hero" data-auto="1" src="{latest_url}" alt="Ostatnie zdjęcie z kamery">
  <div class="hero-bar">
    <span class="badge"><span class="live-dot"></span>Ostatnia klatka</span>
    <span class="spacer"></span>
    <span class="badge">{stamp}</span>
  </div>
</div>
<div class="actions">
  <button class="btn btn-accent" data-capture type="button">📸 Zrób zdjęcie</button>
  <a class="btn btn-primary" href="{href('/live', token)}">🔴 Podgląd na żywo</a>
  <a class="btn" href="{href('/history', token)}">🗂️ Historia{days_label}</a>
</div>
"""
        return self._layout("Kamera", body, active="/")

    def _live_html(self, query: str) -> str:
        token = self.app_config.server.auth_token
        stream_url = href("/live.mjpg", token)
        body = f"""
<div class="card hero-card">
  <div class="live-frame"><img src="{stream_url}" alt="Podgląd na żywo"></div>
  <div class="hero-bar">
    <span class="badge"><span class="live-dot"></span>Strumień na żywo</span>
    <span class="spacer"></span>
    <a class="btn" href="{href('/', token)}">← Wróć</a>
  </div>
</div>
<p class="note">Podgląd używa kamery na wyłączność — gdy ta strona jest otwarta, zdjęcia w tle mogą być pomijane. Zamknij ją, gdy skończysz oglądać.</p>
"""
        return self._layout("Na żywo", body, active="/live")

    def _history_index_html(self, query: str) -> str:
        token = self.app_config.server.auth_token
        days = self.storage.date_dirs()
        if not days:
            body = '<div class="card pad empty">Brak historii — jeszcze nic nie zapisano.</div>'
            return self._layout("Historia", body, active="/history")
        cards = []
        for day in days:
            images = self.storage.images_for_day(day.name, newest_first=True)
            day_h = html.escape(day.name)
            day_link = href(f"/history/{quote(day.name)}", token)
            if images:
                thumb_url = href(f"/history/{quote(day.name)}/{quote(images[0].name)}", token)
                thumb = f'<img src="{thumb_url}" alt="{day_h}" loading="lazy">'
            else:
                thumb = ""
            cards.append(
                f'<a class="daycard" href="{day_link}">{thumb}'
                f'<div class="dc-body"><span class="dc-day">{day_h}</span>'
                f'<span class="dc-n">{len(images)}</span></div></a>'
            )
        body = (
            f'<h1 class="h">Historia</h1>'
            f'<p class="sub">{len(days)} dni z zapisanymi klatkami.</p>'
            f'<div class="grid-days">{"".join(cards)}</div>'
        )
        return self._layout("Historia", body, active="/history")

    def _history_day_html(self, day: str, query: str) -> str:
        token = self.app_config.server.auth_token
        images = self.storage.images_for_day(day, newest_first=False)
        if not images:
            body = '<div class="card pad empty">Brak zdjęć dla tego dnia.</div>'
            return self._layout(day, body, active="/history")

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
        selected_label = html.escape(selected_path.stem.replace("-", ":"))
        selected_url = href(f"/history/{quote(day)}/{quote(selected_path.name)}", token)

        options = "\n".join(
            f'<option value="{html.escape(name)}"{" selected" if name == selected_name else ""}>'
            f'{html.escape(name[:-4].replace("-", ":"))}</option>'
            for name in image_names
        )
        prev_link = ""
        next_link = ""
        if selected_index > 0:
            prev_name = images[selected_index - 1].name
            prev_url = href(f"/history/{quote(day)}?at={quote(prev_name)}&around={around}", token)
            prev_link = f'<a class="btn" href="{prev_url}">← Poprzednia</a>'
        if selected_index < len(images) - 1:
            next_name = images[selected_index + 1].name
            next_url = href(f"/history/{quote(day)}?at={quote(next_name)}&around={around}", token)
            next_link = f'<a class="btn" href="{next_url}">Następna →</a>'

        items = []
        for image_path in images[start:end]:
            url = href(f"/history/{quote(day)}/{quote(image_path.name)}", token)
            label = html.escape(image_path.stem.replace("-", ":"))
            active = " active" if image_path.name == selected_name else ""
            select_url = href(
                f"/history/{quote(day)}?at={quote(image_path.name)}&around={around}",
                token,
            )
            items.append(
                f'<a class="thumb{active}" href="{select_url}">'
                f'<img src="{url}" alt="{label}" loading="lazy"><span>{label}</span></a>'
            )

        day_h = html.escape(day)
        body = f"""
<h1 class="h">{day_h}</h1>
<p class="sub">{selected_label} · {selected_index + 1}/{len(images)}</p>
<div class="card hero-card"><img class="viewer" src="{selected_url}" alt="{selected_label}"></div>
<form class="controls" method="get" action="/history/{quote(day)}">
  <input type="hidden" name="token" value="{html.escape(token)}">
  <label class="field">Klatka
    <select name="at" onchange="this.form.submit()">{options}</select>
  </label>
  <label class="field">Przed/po
    <input name="around" type="number" min="1" max="12" value="{around}">
  </label>
  <button class="btn btn-primary" type="submit">Pokaż</button>
</form>
<div class="navrow">{prev_link}{next_link}</div>
<div class="thumbs">{''.join(items)}</div>
"""
        return self._layout(day, body, active="/history")


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
