from __future__ import annotations

import argparse
import base64
import collections
import html
import json
import logging
import mimetypes
import os
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import List, Optional
from urllib.parse import parse_qs, quote, unquote, urlparse

from .burst import BurstController
from .camera import LiveCamera
from .config import AppConfig, load_config
from .locking import CameraBusy, CameraLock
from .shellsession import ShellManager
from .storage import SnapshotStorage
from .tatry import get_bootstrap
from .timelapse import TIMELAPSE_NAME, build_day, have_ffmpeg

log = logging.getLogger(__name__)
TOKEN_RE = re.compile(r"([?&]token=)[^&\s\"]+")
TOKEN_COOKIE = "camera_token"
TOKEN_COOKIE_MAX_AGE = 60 * 60 * 24 * 365


class RingLogHandler(logging.Handler):
    """Keep the most recent WARNING+ log lines in memory for /api/diag."""

    def __init__(self, capacity: int = 200):
        super().__init__(level=logging.WARNING)
        self.buf = collections.deque(maxlen=capacity)

    def emit(self, record):
        try:
            self.buf.append(TOKEN_RE.sub(r"\1***", self.format(record)))
        except Exception:
            pass


LOG_RING = RingLogHandler()
LOG_RING.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    root = logging.getLogger()
    if LOG_RING not in root.handlers:
        root.addHandler(LOG_RING)


class LiveSession:
    """Shared warm live camera for the MJPEG stream and the pull endpoint.

    A single re-entrant lock serializes start/capture/stop/watchdog so a frame
    can never be captured from a camera the watchdog is tearing down (which
    previously surfaced as intermittent 500s). On any capture/start failure the
    camera is reset so the next request re-initialises cleanly, and the last
    error is recorded for diagnostics.
    """

    def __init__(self, config: AppConfig):
        self.config = config
        self._lock = threading.RLock()
        self._camera_lock_ctx = None
        self._camera = None
        self._clients = 0
        self._idle_deadline = 0.0
        self._idle_timeout = max(1.0, float(getattr(config.camera, "live_idle_timeout", 8.0)))
        self._roi = None  # absolute (nx, ny, nw, nh) in 0..1 of full sensor
        self.last_error = ""
        self.started_count = 0
        self._stop = False
        self._watchdog = threading.Thread(target=self._watchdog_loop, daemon=True)
        self._watchdog.start()

    def _ensure_started(self) -> None:  # call under self._lock
        if self._camera is not None:
            return
        ctx = CameraLock(self.config.paths.lock_file, blocking=False)
        ctx.__enter__()  # raises CameraBusy
        self._camera_lock_ctx = ctx
        try:
            camera = LiveCamera(self.config.camera)
            camera.start()
        except Exception as exc:
            # Record and release the lock so the next attempt retries cleanly.
            self.last_error = f"{type(exc).__name__}: {exc}"
            try:
                ctx.__exit__(None, None, None)
            except Exception:
                pass
            self._camera_lock_ctx = None
            raise
        self._camera = camera
        self.started_count += 1
        if self._roi:
            camera.set_roi(self._roi)
        log.info("live camera started")

    def _teardown(self) -> None:  # call under self._lock
        camera = self._camera
        ctx = self._camera_lock_ctx
        self._camera = None
        self._camera_lock_ctx = None
        if camera is not None:
            try:
                camera.stop()
            except Exception:
                pass
        if ctx is not None:
            try:
                ctx.__exit__(None, None, None)
            except Exception:
                pass

    def _capture(self) -> bytes:  # call under self._lock
        self._ensure_started()  # raises CameraBusy
        self._idle_deadline = time.monotonic() + self._idle_timeout
        try:
            data = self._camera.capture_jpeg_bytes()
            self.last_error = ""
            return data
        except Exception as exc:
            self.last_error = f"{type(exc).__name__}: {exc}"
            self._teardown()  # reset so the next attempt re-initialises
            raise

    def grab_frame(self) -> bytes:
        with self._lock:
            return self._capture()

    def acquire(self) -> "LiveSession":
        with self._lock:
            self._ensure_started()  # raises CameraBusy
            self._clients += 1
            return self

    def release(self) -> None:
        with self._lock:
            self._clients = max(0, self._clients - 1)

    def capture_locked(self) -> bytes:
        with self._lock:
            return self._capture()

    def set_roi(self, nx: float, ny: float, nw: float, nh: float):
        """Zoom into a rectangle given relative to the CURRENT view; composes
        into an absolute ROI so repeated selections zoom further in."""
        with self._lock:
            cx, cy, cw, ch = self._roi or (0.0, 0.0, 1.0, 1.0)
            aw = max(0.05, min(nw * cw, 1.0))
            ah = max(0.05, min(nh * ch, 1.0))
            ax = min(max(0.0, cx + nx * cw), 1.0 - aw)
            ay = min(max(0.0, cy + ny * ch), 1.0 - ah)
            self._roi = (round(ax, 4), round(ay, 4), round(aw, 4), round(ah, 4))
            if self._camera is not None:
                self._camera.set_roi(self._roi)
            return self._roi

    def clear_roi(self):
        with self._lock:
            self._roi = None
            if self._camera is not None:
                self._camera.set_roi(None)

    def _watchdog_loop(self) -> None:
        while not self._stop:
            time.sleep(1.0)
            with self._lock:
                if self._camera is None:
                    continue
                if self._clients > 0 or time.monotonic() < self._idle_deadline:
                    continue
                self._teardown()
                log.info("live camera stopped (idle)")

    @property
    def clients(self) -> int:
        with self._lock:
            return self._clients

    def diag(self) -> dict:
        with self._lock:
            zoom = round(1.0 / self._roi[2], 1) if self._roi else 1.0
            return {
                "camera_open": self._camera is not None,
                "clients": self._clients,
                "starts": self.started_count,
                "roi": list(self._roi) if self._roi else None,
                "zoom": zoom,
                "last_error": self.last_error,
            }


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


_DAY_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _valid_day(day: str) -> bool:
    return bool(_DAY_RE.match(day or ""))


def read_system_stats(data_dir) -> dict:
    """Best-effort Raspberry Pi health snapshot. Every field is optional."""
    stats: dict = {}
    try:
        zone = Path("/sys/class/thermal/thermal_zone0/temp")
        if zone.exists():
            stats["cpu_temp_c"] = round(int(zone.read_text().strip()) / 1000.0, 1)
    except Exception:
        pass
    try:
        stats["load"] = [round(x, 2) for x in os.getloadavg()]
        stats["cpu_count"] = os.cpu_count()
    except Exception:
        pass
    try:
        info = {}
        for line in Path("/proc/meminfo").read_text().splitlines():
            key, _, value = line.partition(":")
            info[key.strip()] = value.strip()
        total = int(info["MemTotal"].split()[0]) * 1024
        avail_raw = info.get("MemAvailable") or info.get("MemFree") or "0 kB"
        avail = int(avail_raw.split()[0]) * 1024
        stats["mem_total"] = total
        stats["mem_used"] = max(0, total - avail)
    except Exception:
        pass
    try:
        usage = shutil.disk_usage(str(data_dir))
        stats["disk_total"] = usage.total
        stats["disk_used"] = usage.used
        stats["disk_free"] = usage.free
    except Exception:
        pass
    try:
        stats["uptime_s"] = int(float(Path("/proc/uptime").read_text().split()[0]))
    except Exception:
        pass
    return stats


PAGE_CSS = """
:root{
  --bg:#f3f6f4; --card:#ffffff; --ink:#1d2b24; --muted:#698075;
  --border:#e4ebe6; --border-strong:#cdd9d1; --primary:#2f6f57; --primary-ink:#ffffff;
  --accent:#ef9b42; --ring:rgba(47,111,87,.35);
  --shadow:0 1px 2px rgba(20,40,30,.05), 0 6px 18px rgba(20,40,30,.05);
}
@media (prefers-color-scheme:dark){
  :root:not([data-theme="light"]){
    --bg:#101a16; --card:#172620; --ink:#e7efe9; --muted:#9bb1a6;
    --border:#243730; --border-strong:#365045; --primary:#4eb389; --primary-ink:#0b1812;
    --accent:#f0a85a; --ring:rgba(78,179,137,.4);
    --shadow:0 1px 2px rgba(0,0,0,.3), 0 8px 22px rgba(0,0,0,.25);
  }
}
:root[data-theme="dark"]{
  --bg:#101a16; --card:#172620; --ink:#e7efe9; --muted:#9bb1a6;
  --border:#243730; --border-strong:#365045; --primary:#4eb389; --primary-ink:#0b1812;
  --accent:#f0a85a; --ring:rgba(78,179,137,.4);
  --shadow:0 1px 2px rgba(0,0,0,.3), 0 8px 22px rgba(0,0,0,.25);
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
.live-frame{background:#050807;position:relative}
.live-frame img{width:100%;display:block}
#roiOverlay{position:absolute;inset:0;cursor:crosshair;touch-action:none}
#roiRect{position:absolute;border:2px solid var(--accent);background:rgba(239,155,66,.18);display:none;pointer-events:none}
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

/* theme toggle button */
.icon-btn{flex:0 0 auto;display:inline-grid;place-items:center;width:34px;height:34px;font-size:1rem;
  border:1px solid var(--border);border-radius:.55rem;background:var(--card);color:var(--ink);cursor:pointer}
.icon-btn:hover{border-color:var(--border-strong)}

/* stale snapshot health on the timestamp badge */
.badge.stale{color:var(--accent)}
.badge.dead{color:#e0533f}

/* system stats strip */
.sysstrip{display:flex;flex-wrap:wrap;gap:.5rem;margin:.8rem 0 0}
.sysstrip:empty{display:none}
.chip{display:flex;flex-direction:column;gap:.05rem;min-width:84px;background:var(--card);
  border:1px solid var(--border);border-left:4px solid var(--border-strong);border-radius:11px;
  padding:.45rem .65rem;box-shadow:var(--shadow)}
.chip-v{font-weight:800;font-size:.95rem;font-variant-numeric:tabular-nums}
.chip-l{font-size:.7rem;color:var(--muted);text-transform:uppercase;letter-spacing:.04em}
.chip.green{border-left-color:#3aa17a}
.chip.amber{border-left-color:var(--accent)}
.chip.red{border-left-color:#e0533f}
.chip.red .chip-v{color:#e0533f}

/* control rows */
.ctrlrow{display:flex;flex-wrap:wrap;align-items:center;gap:.7rem;margin:.8rem 0 0;font-size:.85rem;color:var(--muted)}
.switch{display:inline-flex;align-items:center;gap:.45rem;cursor:pointer;user-select:none}
.mini{font:inherit;font-size:.84rem;color:var(--ink);background:var(--card);
  border:1px solid var(--border-strong);border-radius:.55rem;padding:.4rem .55rem}

/* history scrubber + player */
.scrubber{margin:.7rem 0 .2rem}
.scrubber input[type=range]{width:100%;accent-color:var(--primary);height:26px}
.player{display:flex;align-items:center;gap:.6rem;flex-wrap:wrap;margin:.2rem 0 .4rem}

/* lightbox */
.lightbox{position:fixed;inset:0;z-index:100;display:none;align-items:center;justify-content:center;
  background:rgba(5,10,8,.94);padding:env(safe-area-inset-top) 0 env(safe-area-inset-bottom)}
.lightbox.open{display:flex}
.lightbox img{max-width:96vw;max-height:90vh;width:auto;height:auto;border-radius:8px;object-fit:contain}
.lb-btn{position:absolute;top:50%;transform:translateY(-50%);width:48px;height:48px;border-radius:50%;
  border:0;background:rgba(255,255,255,.14);color:#fff;font-size:1.5rem;cursor:pointer}
.lb-btn:hover{background:rgba(255,255,255,.26)}
.lb-prev{left:12px}.lb-next{right:12px}
.lb-close{position:absolute;top:12px;right:14px;width:40px;height:40px;border-radius:50%;border:0;
  background:rgba(255,255,255,.14);color:#fff;font-size:1.3rem;cursor:pointer}
.lb-hint{position:absolute;bottom:14px;left:0;right:0;text-align:center;color:rgba(255,255,255,.7);font-size:.78rem}

/* admin panel */
.admin-form{display:flex;flex-direction:column;gap:.6rem;margin-top:.7rem}
.admin-form textarea{font:13px/1.45 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;color:var(--ink);
  background:var(--card);border:1px solid var(--border-strong);border-radius:.6rem;padding:.6rem .7rem;min-height:90px;resize:vertical}
.admin-form input[type=password]{font:inherit;color:var(--ink);background:var(--card);
  border:1px solid var(--border-strong);border-radius:.6rem;padding:.5rem .6rem}
.out{white-space:pre-wrap;word-break:break-word;font:12.5px/1.5 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
  background:#0b1410;color:#d6e6dd;border:1px solid var(--border);border-radius:.6rem;padding:.7rem .8rem;margin-top:.7rem;max-height:55vh;overflow:auto}
.out.err{color:#ffb3a6}
.out:empty{display:none}
.danger-note{background:rgba(178,59,46,.12);border:1px solid var(--border);border-radius:.6rem;
  padding:.6rem .8rem;font-size:.84rem;line-height:1.5;color:var(--ink);margin:0 0 .2rem}
.danger-note code{background:rgba(0,0,0,.18);padding:.05rem .3rem;border-radius:5px}
.chart{background:var(--card);border:1px solid var(--border);border-radius:12px;box-shadow:var(--shadow);padding:.5rem .4rem;margin-bottom:.7rem}
.uplot,.u-wrap{width:100%}
.u-legend{font-size:.78rem}
.u-title{font-size:.85rem;color:var(--ink);font-weight:700}
.metarow{display:flex;gap:.8rem;flex-wrap:wrap;align-items:flex-start;margin-top:.6rem}
.metarow img{flex:1 1 320px;max-width:520px;border-radius:10px;background:#050807}
.metarow pre{flex:1 1 240px;margin:0;max-height:320px}
.evnt{font-size:.78rem;color:var(--muted);margin-top:.6rem}
.evnt b{color:#e0533f}
.cond{display:flex;align-items:center;gap:.9rem;flex-wrap:wrap;padding:.7rem 1rem;margin-bottom:.7rem}
.cond .cbig{font-size:2.1rem;line-height:1}
.cond .cmain{display:flex;flex-direction:column;line-height:1.15}
.cond .cmain b{font-size:1.35rem;color:var(--ink)}
.cond .cgrid{display:flex;flex-wrap:wrap;gap:.4rem;flex:1 1 auto}
.cond .pl{background:var(--card-2,rgba(125,140,130,.12));border:1px solid var(--border);border-radius:999px;padding:.18rem .6rem;font-size:.78rem;color:var(--ink);white-space:nowrap}
.cond .pl.warn{color:#e0533f;border-color:rgba(224,83,63,.5)}
.cond .ctime{font-size:.72rem;color:var(--muted);width:100%}
@media (max-width:560px){.cond .cbig{font-size:1.7rem}.cond .cmain b{font-size:1.15rem}.metarow .mimgwrap,.metarow pre{flex:1 1 100%}}
.mimgwrap{position:relative;flex:1 1 320px;max-width:520px}
.mimgwrap img{width:100%;display:block;border-radius:10px;background:#050807}
.roiov{position:absolute;inset:0;cursor:crosshair;touch-action:none}
.roirect{position:absolute;border:2px solid #3da35a;background:rgba(61,163,90,.18);pointer-events:none}
.cmp{position:relative;overflow:hidden;padding:0;background:#050807;touch-action:none;user-select:none}
.cmp-img{display:block;width:100%}
.cmp-over{position:absolute;top:0;left:0;width:100%;height:100%;object-fit:cover}
.cmp-div{position:absolute;top:0;bottom:0;left:50%;width:2px;background:var(--accent);pointer-events:none}
.cmp-div::after{content:"\\21C6";position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);background:var(--accent);color:#10160f;border-radius:999px;width:28px;height:28px;display:flex;align-items:center;justify-content:center;font-size:.85rem;box-shadow:0 1px 4px rgba(0,0,0,.4)}
.term-wrap{background:#0b1410;border:1px solid var(--border);border-radius:12px;padding:8px;box-shadow:var(--shadow);margin-top:.6rem}
#term{height:64vh;width:100%}
.term-bar{display:flex;flex-wrap:wrap;gap:.5rem;align-items:center;margin:.6rem 0 0}
"""

PAGE_JS = """
(function(){
  var tok = window.CAM_TOKEN || "";
  function withTok(path){
    var u = new URL(path, location.origin);
    if(tok) u.searchParams.set("token", tok);
    return u.pathname + u.search;
  }
  function $(s, r){ return (r || document).querySelector(s); }
  function $all(s, r){ return Array.prototype.slice.call((r || document).querySelectorAll(s)); }

  function toast(msg, kind){
    var t = $("#toast");
    if(!t) return;
    t.textContent = msg;
    t.className = "toast show" + (kind ? " " + kind : "");
    clearTimeout(window.__toastT);
    window.__toastT = setTimeout(function(){ t.className = "toast"; }, 2600);
  }

  /* ---- Feature: theme toggle (auto / light / dark) ---- */
  (function(){
    var btn = $("#themeBtn"), KEY = "cam.theme";
    var modes = ["auto", "light", "dark"], icon = { auto: "\\u{1F317}", light: "\\u2600\\uFE0F", dark: "\\u{1F319}" };
    function apply(m){
      if(m === "auto") document.documentElement.removeAttribute("data-theme");
      else document.documentElement.setAttribute("data-theme", m);
      if(btn){ btn.textContent = icon[m]; btn.title = "Motyw: " + m; }
    }
    var cur = localStorage.getItem(KEY) || "auto"; apply(cur);
    if(btn) btn.addEventListener("click", function(){
      cur = modes[(modes.indexOf(cur) + 1) % modes.length];
      localStorage.setItem(KEY, cur); apply(cur); toast("Motyw: " + cur);
    });
  })();

  /* ---- Feature: relative time + stale-snapshot health ---- */
  function fmtAgo(iso){
    var d = new Date(iso); if(isNaN(d.getTime())) return "";
    var s = Math.max(0, Math.round((Date.now() - d.getTime())/1000));
    if(s < 60) return s + " s temu";
    var m = Math.round(s/60); if(m < 60) return m + " min temu";
    var h = Math.round(m/60); if(h < 24) return h + " h temu";
    return Math.round(h/24) + " dni temu";
  }
  function ageSec(iso){ var d = new Date(iso); return isNaN(d.getTime()) ? null : (Date.now() - d.getTime())/1000; }
  function paintAgo(){
    $all("[data-ts]").forEach(function(el){
      var iso = el.getAttribute("data-ts"); var a = fmtAgo(iso); if(a) el.textContent = a;
      var age = ageSec(iso), badge = el.closest(".badge");
      if(badge){ badge.classList.toggle("stale", age != null && age > 180); badge.classList.toggle("dead", age != null && age > 600); }
    });
  }
  paintAgo(); setInterval(paintAgo, 10000);

  /* ---- Feature: fullscreen lightbox ---- */
  var lb = $("#lightbox"), lbImg = lb ? $("#lbImg") : null, lbHint = lb ? $("#lbHint") : null;
  var lbUrls = null, lbIdx = 0;
  function openLB(urls, idx){
    if(!lb) return;
    lbUrls = urls; lbIdx = idx; lbImg.src = urls[idx];
    if(lbHint) lbHint.style.display = urls.length > 1 ? "" : "none";
    lb.classList.add("open"); document.body.style.overflow = "hidden";
  }
  function closeLB(){ if(!lb) return; lb.classList.remove("open"); document.body.style.overflow = ""; }
  function lbStep(d){ if(!lbUrls || lbUrls.length < 2) return; lbIdx = (lbIdx + d + lbUrls.length) % lbUrls.length; lbImg.src = lbUrls[lbIdx]; }
  if(lb){
    lb.addEventListener("click", function(e){ if(e.target === lb || e.target.dataset.close != null) closeLB(); });
    var p = $("#lbPrev"), n = $("#lbNext");
    if(p) p.addEventListener("click", function(e){ e.stopPropagation(); lbStep(-1); });
    if(n) n.addEventListener("click", function(e){ e.stopPropagation(); lbStep(1); });
  }

  /* ---- snapshot refresh + capture ---- */
  function refreshHero(){
    var hero = $("#hero");
    if(!hero) return;
    hero.src = withTok("/latest.jpg?cache=" + Date.now());
    fetch(withTok("/api/status")).then(function(r){ return r.json(); }).then(function(s){
      var ts = s && s.latest && s.latest.timestamp, el = $("#heroTs");
      if(ts && el){ el.setAttribute("data-ts", ts); }
      paintAgo();
    }).catch(function(){});
  }
  $all("[data-capture]").forEach(function(btn){
    btn.addEventListener("click", async function(){
      btn.disabled = true; var old = btn.textContent; btn.textContent = "\\uD83D\\uDCF8 Robi\\u0119\\u2026";
      try{
        var r = await fetch(withTok("/api/capture-now"), { headers: { "Accept": "application/json" } });
        var j = await r.json();
        if(j.ok){ toast("Zdj\\u0119cie zrobione", "ok"); refreshHero(); }
        else { toast(j.message ? ("Pomini\\u0119to: " + j.message) : "Kamera zaj\\u0119ta", "warn"); }
      }catch(e){ toast("Nie uda\\u0142o si\\u0119 zrobi\\u0107 zdj\\u0119cia", "warn"); }
      finally{ btn.disabled = false; btn.textContent = old; }
    });
  });

  /* ---- index page: lightbox + download + auto-refresh controls ---- */
  var hero = $("#hero");
  if(hero){
    hero.style.cursor = "zoom-in";
    hero.addEventListener("click", function(){ openLB([hero.src], 0); });
    var dl = $("#downloadBtn");
    if(dl) dl.addEventListener("click", function(){
      var a = document.createElement("a"); a.href = hero.src; a.download = "kamera-" + Date.now() + ".jpg";
      document.body.appendChild(a); a.click(); a.remove();
    });
    var KEY = "cam.auto";
    var saved; try{ saved = JSON.parse(localStorage.getItem(KEY)); }catch(e){}
    if(!saved) saved = { on: true, ms: 15000 };
    var chk = $("#autoChk"), sel = $("#autoSel"), timer = null;
    function arm(){ if(timer){ clearInterval(timer); timer = null; } if(saved.on) timer = setInterval(function(){ if(!document.hidden) refreshHero(); }, saved.ms); }
    if(chk){ chk.checked = saved.on; chk.addEventListener("change", function(){ saved.on = chk.checked; localStorage.setItem(KEY, JSON.stringify(saved)); arm(); }); }
    if(sel){ sel.value = String(saved.ms); sel.addEventListener("change", function(){ saved.ms = parseInt(sel.value, 10); localStorage.setItem(KEY, JSON.stringify(saved)); arm(); }); }
    arm();
    document.addEventListener("visibilitychange", function(){ if(!document.hidden && saved.on) refreshHero(); });
  }

  /* ---- Feature: temporary burst (fast snapshots) ---- */
  var burstBtn = $("#burstBtn");
  if(burstBtn){
    var burstInt = $("#burstInt"), burstDur = $("#burstDur"), burstRes = $("#burstRes"), burstStat = $("#burstStatus"), pollT = null;
    function renderBurst(s){
      if(s.active){
        burstBtn.textContent = "\\u23F9 Stop"; burstBtn.classList.add("btn-primary");
        burstStat.textContent = "\\u25CF " + s.count + " klatek \\u00B7 " + (s.resolution || "") + " \\u00B7 pozosta\\u0142o " + s.remaining + " s";
      } else {
        burstBtn.textContent = "\\u25B6 Start"; burstBtn.classList.remove("btn-primary");
        if(s.error){ burstStat.textContent = "\\u26A0 " + s.error; }
        else if(s.count){
          var msg = "zrobiono " + s.count + " klatek" + (s.backfilled ? (" \\u00B7 uzupe\\u0142niono " + s.backfilled + " w historii") : "");
          if(s.session){ burstStat.innerHTML = msg + ' \\u00B7 <a href="' + withTok("/burst/" + encodeURIComponent(s.session)) + '">' + (s.video ? "\\u25B6 obejrzyj timelapse" : "otw\\u00f3rz sesj\\u0119") + "</a>"; }
          else { burstStat.textContent = msg; }
        }
        else { burstStat.textContent = ""; }
      }
    }
    async function pollBurst(){
      try{
        var s = await (await fetch(withTok("/api/burst/status"))).json();
        renderBurst(s);
        if(s.active && !pollT){ pollT = setInterval(pollBurst, 1500); }
        if(!s.active && pollT){ clearInterval(pollT); pollT = null; refreshHero(); }
      }catch(e){}
    }
    burstBtn.addEventListener("click", async function(){
      try{
        var s = await (await fetch(withTok("/api/burst/status"))).json();
        if(s.active){ await fetch(withTok("/api/burst/stop"), { method: "POST" }); toast("Szybkie zdj\\u0119cia: stop"); }
        else{
          var res = (burstRes.value || "0x0").split("x");
          await fetch(withTok("/api/burst/start"), { method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ interval: parseFloat(burstInt.value), duration: parseFloat(burstDur.value),
              width: parseInt(res[0], 10) || 0, height: parseInt(res[1], 10) || 0 }) });
          toast("Szybkie zdj\\u0119cia: start", "ok");
        }
      }catch(e){ toast("B\\u0142\\u0105d sieci", "warn"); }
      pollBurst();
    });
    pollBurst();
  }

  /* ---- Feature: live Raspberry Pi system stats ---- */
  var sys = $("#sysStrip");
  if(sys){
    function human(b){ if(b == null) return "\\u2014"; var u = ["B","kB","MB","GB","TB"], i = 0; while(b >= 1024 && i < u.length - 1){ b /= 1024; i++; } return b.toFixed(b < 10 && i > 0 ? 1 : 0) + " " + u[i]; }
    function dur(s){ if(s == null) return "\\u2014"; var d = Math.floor(s/86400), h = Math.floor((s%86400)/3600), m = Math.floor((s%3600)/60); return (d ? d + "d " : "") + (h ? h + "h " : "") + m + "m"; }
    function chip(label, val, cls){ return '<div class="chip ' + (cls || "") + '"><span class="chip-v">' + val + '</span><span class="chip-l">' + label + '</span></div>'; }
    function loadSys(){
      fetch(withTok("/api/system")).then(function(r){ return r.json(); }).then(function(s){
        var out = "";
        if(s.cpu_temp_c != null){ var t = s.cpu_temp_c, cls = t >= 70 ? "red" : (t >= 60 ? "amber" : "green"); out += chip("temp CPU", t.toFixed(1) + "\\u00B0C", cls); }
        if(s.load){ var pct = s.cpu_count ? Math.round(100 * s.load[0] / s.cpu_count) : null; out += chip("obci\\u0105\\u017cenie", pct != null ? pct + "%" : s.load[0]); }
        if(s.mem_total){ out += chip("RAM", human(s.mem_used) + " / " + human(s.mem_total)); }
        if(s.disk_total){ var dp = Math.round(100 * s.disk_used / s.disk_total); out += chip("dysk", dp + "% \\u00B7 " + human(s.disk_free), dp >= 90 ? "red" : (dp >= 75 ? "amber" : "")); }
        if(s.uptime_s != null){ out += chip("uptime", dur(s.uptime_s)); }
        sys.innerHTML = out || '<span class="sub">brak danych systemowych</span>';
      }).catch(function(){ sys.innerHTML = '<span class="sub">brak danych systemowych</span>'; });
    }
    loadSys(); setInterval(function(){ if(!document.hidden) loadSys(); }, 30000);
  }

  /* ---- Feature: latest per-capture metadata strip ---- */
  var meta = $("#metaStrip");
  if(meta){
    function wxEmoji(c){ if(c==null)return "🌡"; if(c===0)return "☀️"; if(c<=2)return "🌤️"; if(c===3)return "☁️"; if(c<=48)return "🌫️"; if(c<=67)return "🌧️"; if(c<=77)return "🌨️"; if(c<=82)return "🌦️"; if(c<=86)return "🌨️"; return "⛈️"; }
    function chip2(label, val){ return '<div class="chip"><span class="chip-v">' + val + '</span><span class="chip-l">' + label + '</span></div>'; }
    function loadMeta(){
      fetch(withTok("/api/metadata/latest")).then(function(r){ return r.json(); }).then(function(m){
        var out = "";
        if(m.outdoor && m.outdoor.temp_c != null){ out += chip2("na zewnątrz", wxEmoji(m.outdoor.code) + " " + m.outdoor.temp_c + "°C" + (m.outdoor.humidity != null ? (" · " + m.outdoor.humidity + "%") : "")); }
        if(m.brightness != null){ out += chip2("jasność", "💡 " + m.brightness); }
        if(m.cam && m.cam.lux != null){ out += chip2("lux", Math.round(m.cam.lux)); }
        if(m.cam && m.cam.exposure_us != null){ out += chip2("ekspozycja", (m.cam.exposure_us/1000).toFixed(1) + " ms"); }
        meta.innerHTML = out;
      }).catch(function(){});
    }
    loadMeta(); setInterval(function(){ if(!document.hidden) loadMeta(); }, 30000);
  }

  /* ---- Feature: build a real timelapse video on demand ---- */
  var buildBtn = $("#buildTl");
  if(buildBtn && window.CAM_DAY){
    buildBtn.addEventListener("click", async function(){
      var d = window.CAM_DAY.day;
      buildBtn.disabled = true; var old = buildBtn.textContent; buildBtn.textContent = "Buduj\\u0119\\u2026";
      try{
        var r = await fetch(withTok("/api/timelapse/build?day=" + encodeURIComponent(d)), { method: "POST" });
        var j = await r.json();
        if(j.error){ toast("B\\u0142\\u0105d: " + j.error, "warn"); buildBtn.disabled = false; buildBtn.textContent = old; return; }
        toast("Buduj\\u0119 timelapse\\u2026", "ok");
        var poll = setInterval(async function(){
          try{
            var s = await (await fetch(withTok("/api/timelapse/status?day=" + encodeURIComponent(d)))).json();
            if(s.exists && !s.building){ clearInterval(poll); toast("Gotowe \\u2014 od\\u015bwie\\u017cam", "ok"); setTimeout(function(){ location.reload(); }, 900); }
          }catch(e){}
        }, 4000);
      }catch(e){ toast("B\\u0142\\u0105d sieci", "warn"); buildBtn.disabled = false; buildBtn.textContent = old; }
    });
  }

  /* ---- Feature: (re)build a burst session timelapse with full error ---- */
  var buildBurstBtn = $("#buildBurst");
  if(buildBurstBtn && window.CAM_DAY){
    buildBurstBtn.addEventListener("click", async function(){
      var sess = window.CAM_DAY.day;
      buildBurstBtn.disabled = true; var old = buildBurstBtn.textContent; buildBurstBtn.textContent = "Buduj\\u0119\\u2026";
      try{
        var r = await fetch(withTok("/api/burst/timelapse?session=" + encodeURIComponent(sess)), { method: "POST" });
        var j = await r.json();
        if(j.error){ toast("B\\u0142\\u0105d: " + j.error, "warn"); buildBurstBtn.disabled = false; buildBurstBtn.textContent = old; return; }
        toast("Buduj\\u0119 timelapse\\u2026", "ok");
        var poll = setInterval(async function(){
          try{
            var s = await (await fetch(withTok("/api/burst/session?session=" + encodeURIComponent(sess)))).json();
            if(!s.building){
              clearInterval(poll);
              if(s.exists){ toast("Gotowe \\u2014 od\\u015bwie\\u017cam", "ok"); setTimeout(function(){ location.reload(); }, 800); }
              else { toast("Nie uda\\u0142o si\\u0119 \\u2014 zobacz log", "warn"); setTimeout(function(){ location.reload(); }, 800); }
            }
          }catch(e){}
        }, 3000);
      }catch(e){ toast("B\\u0142\\u0105d sieci", "warn"); buildBurstBtn.disabled = false; buildBurstBtn.textContent = old; }
    });
  }

  /* ---- Feature: per-day metadata chart (brightness / CPU / outdoor temp) ---- */
  var metaChartEl = $("#metaChart");
  if(metaChartEl && window.CAM_DAY && (window.CAM_DAY.base || "").indexOf("/history/") === 0){
    (async function(){
      try{
        var j = await (await fetch(withTok("/api/metadata?day=" + encodeURIComponent(window.CAM_DAY.day)))).json();
        var recs = j.records || [];
        if(recs.length < 2) return;
        var W = 720, H = 170, pad = 22, n = recs.length;
        function lineFor(get, color){
          var vals = recs.map(get);
          var nums = vals.filter(function(v){ return v != null && !isNaN(v); });
          if(nums.length < 2) return null;
          var mn = Math.min.apply(null, nums), mx = Math.max.apply(null, nums); if(mx === mn) mx = mn + 1;
          var d = "";
          vals.forEach(function(v, i){
            if(v == null || isNaN(v)) return;
            var x = pad + (W - 2 * pad) * i / (n - 1);
            var y = pad + (H - 2 * pad) * (1 - (v - mn) / (mx - mn));
            d += (d ? "L" : "M") + x.toFixed(1) + " " + y.toFixed(1) + " ";
          });
          return { d: d, min: mn, max: mx, color: color };
        }
        var defs = [
          { name: "jasność", color: "#e6b450", get: function(x){ return x.brightness != null ? x.brightness : null; } },
          { name: "temp CPU", color: "#e0533f", get: function(x){ return x.cpu_temp_c != null ? x.cpu_temp_c : null; } },
          { name: "temp zewn.", color: "#4eb389", get: function(x){ return (x.outdoor && x.outdoor.temp_c != null) ? x.outdoor.temp_c : null; } }
        ];
        var paths = "", legend = "";
        defs.forEach(function(s){
          var L = lineFor(s.get, s.color); if(!L) return;
          paths += '<path d="' + L.d + '" fill="none" stroke="' + s.color + '" stroke-width="1.6"/>';
          legend += '<span style="color:' + s.color + ';font-weight:700;margin-right:.9rem;white-space:nowrap">\\u25A0 ' + s.name + ' (' + L.min + '\\u2013' + L.max + ')</span>';
        });
        if(!paths) return;
        var csv = withTok("/api/metadata?day=" + encodeURIComponent(window.CAM_DAY.day) + "&format=csv");
        metaChartEl.style.display = "";
        metaChartEl.innerHTML =
          '<div class="sub" style="margin-bottom:.4rem">Metadane dnia (' + recs.length + ' pkt) \\u00B7 <a href="' + csv + '">CSV</a></div>' +
          '<svg viewBox="0 0 ' + W + ' ' + H + '" preserveAspectRatio="none" style="width:100%;height:auto">' + paths + '</svg>' +
          '<div style="font-size:.76rem;margin-top:.4rem;display:flex;flex-wrap:wrap">' + legend + '</div>';
      }catch(e){}
    })();
  }

  /* ---- Feature: history scrubber + timelapse + client-side nav + keyboard ---- */
  var day = window.CAM_DAY;
  if(day && day.frames && day.frames.length){
    var frames = day.frames, idx = day.index || 0;
    var viewer = $("#viewer"), scrub = $("#scrub"), counter = $("#counter"), frameSel = $("#frameSel");
    var playBtn = $("#playBtn"), speedSel = $("#speedSel"), dlDay = $("#dlDay"), thumbs = $("#thumbs");
    function urlFor(f){ var base = day.base || ("/history/" + encodeURIComponent(day.day) + "/"); return withTok(base + encodeURIComponent(f.n)); }
    var playT = null;
    function stop(){ if(!playT) return; clearInterval(playT); playT = null; if(playBtn) playBtn.textContent = "\\u25B6 Odtw\\u00F3rz"; }
    function play(){ if(playT) return; if(playBtn) playBtn.textContent = "\\u23F8 Pauza"; playT = setInterval(function(){ setIdx(idx + 1); }, speedSel ? parseInt(speedSel.value, 10) : 300); }
    function toggle(){ playT ? stop() : play(); }
    function setIdx(i){
      idx = (i + frames.length) % frames.length;
      var f = frames[idx], u = urlFor(f);
      if(viewer) viewer.src = u;
      if(scrub) scrub.value = String(idx);
      if(counter) counter.textContent = (idx + 1) + "/" + frames.length + " \\u00B7 " + f.l;
      if(frameSel) frameSel.value = f.n;
      if(dlDay){ dlDay.href = u; dlDay.setAttribute("download", f.n); }
      if(thumbs) $all(".thumb", thumbs).forEach(function(t){ t.classList.toggle("active", t.getAttribute("data-name") === f.n); });
      var nx = frames[(idx + 1) % frames.length]; if(nx){ var im = new Image(); im.src = urlFor(nx); }
      if(lb && lb.classList.contains("open")){ lbUrls = frames.map(urlFor); lbIdx = idx; lbImg.src = u; }
    }
    if(scrub){ scrub.max = String(frames.length - 1); scrub.value = String(idx); scrub.addEventListener("input", function(){ stop(); setIdx(parseInt(scrub.value, 10)); }); }
    if(frameSel) frameSel.addEventListener("change", function(){ var i = frames.findIndex(function(f){ return f.n === frameSel.value; }); if(i >= 0){ stop(); setIdx(i); } });
    if(playBtn) playBtn.addEventListener("click", toggle);
    if(speedSel) speedSel.addEventListener("change", function(){ if(playT){ stop(); play(); } });
    if(viewer){ viewer.style.cursor = "zoom-in"; viewer.addEventListener("click", function(){ openLB(frames.map(urlFor), idx); }); }
    if(thumbs) $all(".thumb", thumbs).forEach(function(t){
      t.addEventListener("click", function(e){
        var i = frames.findIndex(function(f){ return f.n === t.getAttribute("data-name"); });
        if(i >= 0){ e.preventDefault(); stop(); setIdx(i); window.scrollTo({ top: 0, behavior: "smooth" }); }
      });
    });
    document.addEventListener("keydown", function(e){
      var tag = e.target.tagName;
      if(tag === "INPUT" || tag === "SELECT" || tag === "TEXTAREA") return;
      if(e.key === "ArrowRight"){ stop(); setIdx(idx + 1); e.preventDefault(); }
      else if(e.key === "ArrowLeft"){ stop(); setIdx(idx - 1); e.preventDefault(); }
      else if(e.key === "Home"){ stop(); setIdx(0); e.preventDefault(); }
      else if(e.key === "End"){ stop(); setIdx(frames.length - 1); e.preventDefault(); }
      else if(e.key === " "){ toggle(); e.preventDefault(); }
      else if(e.key === "f" || e.key === "F"){ if(viewer) openLB(frames.map(urlFor), idx); }
      else if(e.key === "Escape"){ stop(); closeLB(); }
    });
    setIdx(idx);
  } else {
    document.addEventListener("keydown", function(e){
      var tag = e.target.tagName; if(tag === "INPUT" || tag === "SELECT") return;
      if(e.key === "Escape") closeLB();
      if(lb && lb.classList.contains("open")){ if(e.key === "ArrowRight") lbStep(1); if(e.key === "ArrowLeft") lbStep(-1); }
      if(e.key === "c" || e.key === "C"){ var b = $("[data-capture]"); if(b) b.click(); }
      if((e.key === "f" || e.key === "F") && hero){ openLB([hero.src], 0); }
    });
  }
})();
"""

SHELL_JS = """
(function(){
  function withTok(p){ var t = window.CAM_TOKEN || ""; var u = new URL(p, location.origin); if(t) u.searchParams.set("token", t); return u.pathname + u.search; }
  var el = document.getElementById("term");
  if(!el) return;
  if(!window.Terminal){ el.textContent = "Nie udało się załadować xterm.js (sprawdź połączenie z unpkg)."; return; }
  var term = new Terminal({ fontSize: 13, cursorBlink: true, scrollback: 5000,
    theme: { background: "#0b1410", foreground: "#d6e6dd" } });
  var fit = null;
  try{ fit = new FitAddon.FitAddon(); term.loadAddon(fit); }catch(e){}
  try{ if(window.WebLinksAddon) term.loadAddon(new WebLinksAddon.WebLinksAddon()); }catch(e){}
  term.open(el);
  function doFit(){ if(fit){ try{ fit.fit(); }catch(e){} } }
  doFit();
  var sid = null, pos = 0, alive = true;
  function b64ToBytes(b){ var s = atob(b), u = new Uint8Array(s.length); for(var i=0;i<s.length;i++) u[i]=s.charCodeAt(i); return u; }
  function bytesToB64(u){ var s=""; for(var i=0;i<u.length;i++) s+=String.fromCharCode(u[i]); return btoa(s); }
  async function post(path, body){
    var r = await fetch(withTok(path), { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body||{}) });
    return r.json();
  }
  term.onData(function(data){
    if(!sid) return;
    post("/api/shell/input", { sid: sid, data: bytesToB64(new TextEncoder().encode(data)) });
  });
  term.onResize(function(sz){ if(sid) post("/api/shell/resize", { sid: sid, rows: sz.rows, cols: sz.cols }); });
  window.addEventListener("resize", doFit);
  async function loop(){
    while(alive){
      try{
        var r = await fetch(withTok("/api/shell/read?sid=" + sid + "&pos=" + pos));
        var j = await r.json();
        if(j.error){ term.write("\\r\\n[" + j.error + "]\\r\\n"); break; }
        if(j.data) term.write(b64ToBytes(j.data));
        pos = j.pos;
        if(!j.alive){ term.write("\\r\\n[sesja zakończona]\\r\\n"); alive = false; break; }
      }catch(e){ await new Promise(function(res){ setTimeout(res, 1000); }); }
    }
  }
  (async function start(){
    var j = await post("/api/shell/open", { rows: term.rows, cols: term.cols });
    if(j.error){ term.write("\\r\\n[nie można otworzyć sesji: " + j.error + "]\\r\\n"); return; }
    sid = j.sid;
    term.focus();
    loop();
  })();
})();
"""

LIVE_JS = """
(function(){
  function withTok(p){ var t = window.CAM_TOKEN || ""; var u = new URL(p, location.origin); if(t) u.searchParams.set("token", t); return u.pathname + u.search; }
  function $(id){ return document.getElementById(id); }
  var img = $("liveImg");
  if(!img) return;
  var statusEl = $("liveStatus"), fpsEl = $("liveFps"), pauseBtn = $("livePause"), rateSel = $("liveRate");
  var diagBtn = $("diagBtn"), diagPanel = $("diagPanel"), diagOut = $("diagOut");
  var running = true, minInterval = parseInt((rateSel && rateSel.value) || "200", 10);
  var frames = 0, fpsWindow = performance.now(), curURL = null;
  var clientLog = [];
  function logc(s){ clientLog.push(new Date().toISOString().substr(11,12) + " " + s); if(clientLog.length > 40) clientLog.shift(); }
  function setStatus(text, cls){ if(statusEl){ statusEl.textContent = text; statusEl.className = "badge " + (cls || ""); } }
  function schedule(d){ if(running) setTimeout(loadNext, Math.max(0, d)); }
  async function loadNext(){
    if(!running) return;
    if(document.hidden){ schedule(500); return; }
    var t0 = performance.now();
    try{
      var r = await fetch(withTok("/live.jpg?t=" + Date.now()), { cache: "no-store" });
      if(!r.ok){
        var body = ""; try{ body = (await r.text()).trim(); }catch(e){}
        logc("GET /live.jpg -> " + r.status + (body ? (" " + body) : ""));
        var hint = r.status === 409 ? "kamera zajęta" : (r.status === 502 ? "serwer niedostępny" : (r.status === 500 ? "błąd serwera" : ""));
        setStatus("\\u26A0 " + r.status + (hint ? (" \\u00B7 " + hint) : "") + (body ? (" \\u00B7 " + body) : ""), "dead");
        schedule(r.status === 409 ? 1500 : 1200);
        return;
      }
      var blob = await r.blob();
      var url = URL.createObjectURL(blob);
      img.onload = function(){ if(curURL) URL.revokeObjectURL(curURL); curURL = url; };
      img.src = url;
      frames++;
      var now = performance.now();
      if(now - fpsWindow >= 1000){ if(fpsEl) fpsEl.textContent = (frames * 1000 / (now - fpsWindow)).toFixed(1) + " fps"; frames = 0; fpsWindow = now; }
      setStatus("\\u25CF na \\u017cywo", "");
      schedule(minInterval - (performance.now() - t0));
    }catch(e){
      logc("fetch error: " + ((e && e.message) || e));
      setStatus("\\u26A0 brak po\\u0142\\u0105czenia \\u2014 ponawiam", "dead");
      schedule(1500);
    }
  }
  if(pauseBtn) pauseBtn.addEventListener("click", function(){
    running = !running;
    pauseBtn.textContent = running ? "\\u23F8 Pauza" : "\\u25B6 Wzn\\u00F3w";
    if(running) loadNext(); else setStatus("\\u23F8 pauza", "");
  });
  if(rateSel) rateSel.addEventListener("change", function(){ minInterval = parseInt(rateSel.value, 10); });

  async function buildDiag(){
    var dump = {
      when: new Date().toISOString(),
      page: location.href.replace(/token=[^&]+/, "token=***"),
      userAgent: navigator.userAgent,
      online: navigator.onLine,
      clientLog: clientLog.slice()
    };
    try{
      var r = await fetch(withTok("/api/diag"));
      dump.serverHttp = r.status;
      dump.server = await r.json();
    }catch(e){ dump.serverFetchError = String(e); }
    return JSON.stringify(dump, null, 2);
  }
  if(diagBtn) diagBtn.addEventListener("click", async function(){
    diagPanel.style.display = "";
    diagOut.textContent = "\\u2026"; diagOut.textContent = await buildDiag();
  });
  if($("diagRefresh")) $("diagRefresh").addEventListener("click", async function(){ diagOut.textContent = await buildDiag(); });
  if($("diagCopy")) $("diagCopy").addEventListener("click", function(){
    var txt = diagOut.textContent;
    if(navigator.clipboard){ navigator.clipboard.writeText(txt).then(function(){}, function(){}); }
    var sel = window.getSelection(); var range = document.createRange(); range.selectNodeContents(diagOut); sel.removeAllRanges(); sel.addRange(range);
  });
  window.addEventListener("error", function(e){ logc("JS error: " + (e.message || "")); });
  window.addEventListener("unhandledrejection", function(e){ logc("promise: " + ((e.reason && e.reason.message) || e.reason)); });

  /* ---- Feature: draw a rectangle to hardware-zoom (ScalerCrop) ---- */
  var overlay = $("roiOverlay"), rectEl = $("roiRect"), zoomEl = $("liveZoom"), resetBtn = $("liveReset");
  function setZoom(z){ if(zoomEl) zoomEl.textContent = (z && z > 1) ? ("\\uD83D\\uDD0D " + z + "\\u00D7") : ""; }
  async function postRoi(b){
    try{
      var r = await fetch(withTok("/api/live/roi"), { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(b) });
      var j = await r.json();
      if(j.zoom != null) setZoom(j.zoom);
    }catch(e){ logc("roi post error"); }
  }
  if(overlay){
    var drag = null;
    function draw(e){
      if(!drag) return;
      var x = Math.min(e.clientX, drag.x0), y = Math.min(e.clientY, drag.y0);
      rectEl.style.left = (x - drag.r.left) + "px"; rectEl.style.top = (y - drag.r.top) + "px";
      rectEl.style.width = Math.abs(e.clientX - drag.x0) + "px"; rectEl.style.height = Math.abs(e.clientY - drag.y0) + "px";
    }
    overlay.addEventListener("pointerdown", function(e){
      try{ overlay.setPointerCapture(e.pointerId); }catch(_){}
      drag = { r: overlay.getBoundingClientRect(), x0: e.clientX, y0: e.clientY };
      rectEl.style.display = "block"; draw(e);
    });
    overlay.addEventListener("pointermove", draw);
    overlay.addEventListener("pointerup", function(e){
      if(!drag) return;
      var r = drag.r, x = Math.min(e.clientX, drag.x0), y = Math.min(e.clientY, drag.y0);
      var w = Math.abs(e.clientX - drag.x0), h = Math.abs(e.clientY - drag.y0);
      rectEl.style.display = "none"; drag = null;
      if(w < 10 || h < 10) return;  // ignore tiny/taps
      postRoi({ x: (x - r.left) / r.width, y: (y - r.top) / r.height, w: w / r.width, h: h / r.height });
    });
  }
  if(resetBtn) resetBtn.addEventListener("click", function(){ postRoi({ reset: true }); });
  fetch(withTok("/api/live/roi"), { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" }).catch(function(){});

  loadNext();
})();
"""


METRICS_JS = """
(function(){
  function $(id){ return document.getElementById(id); }
  function withTok(p){ var t=window.CAM_TOKEN||""; var u=new URL(p,location.origin); if(t)u.searchParams.set("token",t); return u.pathname+u.search; }
  if(!$("dayCharts")) return;
  if(!window.uPlot){ $("dayCharts").innerHTML='<div class="card pad">Nie udało się załadować uPlot (sieć?).</div>'; return; }
  var charts=[], recs=[], curDay=null, histChart=null;
  var SUN={rise:null,set:null}, REBOOTS=[];
  function num(r, path){ var ps=path.split("."), v=r; for(var i=0;i<ps.length;i++){ if(v==null)return null; v=v[ps[i]]; } return (typeof v==="number")?v:null; }
  function destroyCharts(){ charts.forEach(function(c){ try{c.destroy();}catch(e){} }); charts=[]; }
  function tsec(s){ var t=Date.parse(s); return isNaN(t)?null:t/1000; }

  var WMO={0:["\\u2600\\uFE0F","bezchmurnie"],1:["\\uD83C\\uDF24\\uFE0F","przejaśnienia"],2:["\\u26C5","częśc. zachmurzenie"],3:["\\u2601\\uFE0F","zachmurzenie"],45:["\\uD83C\\uDF2B\\uFE0F","mgła"],48:["\\uD83C\\uDF2B\\uFE0F","szadź"],51:["\\uD83C\\uDF26\\uFE0F","mżawka"],53:["\\uD83C\\uDF26\\uFE0F","mżawka"],55:["\\uD83C\\uDF26\\uFE0F","mżawka"],61:["\\uD83C\\uDF27\\uFE0F","deszcz"],63:["\\uD83C\\uDF27\\uFE0F","deszcz"],65:["\\uD83C\\uDF27\\uFE0F","ulewa"],71:["\\uD83C\\uDF28\\uFE0F","śnieg"],73:["\\uD83C\\uDF28\\uFE0F","śnieg"],75:["\\u2744\\uFE0F","śnieg"],80:["\\uD83C\\uDF26\\uFE0F","przelotny deszcz"],81:["\\uD83C\\uDF27\\uFE0F","przelotny deszcz"],82:["\\u26C8\\uFE0F","ulewa"],95:["\\u26C8\\uFE0F","burza"],96:["\\u26C8\\uFE0F","burza"],99:["\\u26C8\\uFE0F","burza"]};
  function wmo(c){ return WMO[c]||["\\uD83C\\uDF21\\uFE0F",""]; }
  function thr(v){ if(v==null)return ""; if(v===0)return "\\u2713 zasilanie OK"; var s=[]; if(v&1)s.push("under-volt"); if(v&8)s.push("throttling"); if(v&0x20000)s.push("było throttling"); if(v&0x10000)s.push("był under-volt"); return "\\u26A0 "+(s.join(", ")||("0x"+v.toString(16))); }
  function pill(txt,warn){ return txt?('<span class="pl'+(warn?" warn":"")+'">'+txt+'</span>'):""; }
  function renderCond(r){
    var el=$("mCond"); if(!el||!r){ if(el)el.style.display="none"; return; }
    var o=r.outdoor||{}, w=wmo(o.code), day=r.is_day?"\\uD83C\\uDF1E dzień":"\\uD83C\\uDF19 noc";
    var tv=thr(r.throttled), warn=tv.indexOf("\\u26A0")===0;
    el.style.display="";
    el.innerHTML='<span class="cbig">'+w[0]+'</span>'+
      '<span class="cmain"><b>'+(o.temp_c!=null?o.temp_c.toFixed(1)+"\\u00B0C":"\\u2013")+'</b><span class="sub">'+w[1]+'</span></span>'+
      '<span class="cgrid">'+
        pill(r.canopy_pct!=null?("\\uD83C\\uDF3F zieleń "+r.canopy_pct+"%"):"")+
        pill("\\u2601\\uFE0F "+(o.cloud!=null?Math.round(o.cloud)+"%":"\\u2013"))+
        pill("\\uD83D\\uDCA8 "+(o.wind!=null?o.wind+" km/h":"\\u2013"))+
        pill("\\uD83D\\uDCA7 "+(o.precip!=null?o.precip+" mm":"\\u2013"))+
        pill(day)+
        pill("CPU "+(r.cpu_temp_c!=null?r.cpu_temp_c+"\\u00B0C":"\\u2013"))+
        pill(r.cpu_freq_mhz!=null?(r.cpu_freq_mhz+" MHz"):"")+
        pill(tv,warn)+
      '</span>'+
      '<span class="ctime">'+(SUN.rise?("\\uD83C\\uDF05 "+(r.sunrise||"").slice(11)+"  \\uD83C\\uDF07 "+(r.sunset||"").slice(11)+"   \\u00B7   "):"")+(r.ts||"").replace("T"," ")+'</span>';
  }

  function bandHook(u){
    var ctx=u.ctx, x0=u.scales.x.min, x1=u.scales.x.max;
    if(x0==null||x1==null) return;
    var L=u.bbox.left, T=u.bbox.top, H=u.bbox.height, W=u.bbox.width;
    ctx.save();
    function px(v){ return u.valToPos(v,"x",true); }
    ctx.fillStyle="rgba(70,90,130,0.16)";
    function band(a,b){ if(b<=x0||a>=x1)return; a=Math.max(a,x0); b=Math.min(b,x1); var pa=px(a),pb=px(b); ctx.fillRect(pa,T,pb-pa,H); }
    if(SUN.rise) band(x0,SUN.rise);
    if(SUN.set) band(SUN.set,x1);
    function vline(t,color,dash){ if(t==null||t<x0||t>x1)return; var p=px(t); ctx.beginPath(); ctx.setLineDash(dash||[]); ctx.strokeStyle=color; ctx.lineWidth=1.4; ctx.moveTo(p,T); ctx.lineTo(p,T+H); ctx.stroke(); ctx.setLineDash([]); }
    vline(SUN.rise,"rgba(230,180,80,0.85)");
    vline(SUN.set,"rgba(120,140,210,0.85)");
    REBOOTS.forEach(function(t){ vline(t,"rgba(224,83,63,0.85)",[4,3]); });
    ctx.restore();
  }

  var slider=$("mSlider"), img=$("mImg"), vals=$("mVals");
  function setSlider(i, withImage){
    if(i==null||i<0||i>=recs.length) return;
    if(slider) slider.value=String(i);
    var r=recs[i];
    if(withImage && img && r.file) img.src=withTok("/history/"+encodeURIComponent(curDay)+"/"+encodeURIComponent(r.file));
    if(vals) vals.textContent=JSON.stringify(r,null,2);
    renderCond(r);
  }
  if(slider) slider.addEventListener("input", function(){ setSlider(parseInt(slider.value,10), true); });

  function makeChart(el, title, defs){
    var xs=recs.map(function(r){ return Date.parse(r.ts)/1000; });
    var data=[xs];
    defs.forEach(function(d){ data.push(recs.map(function(r){ return num(r,d.path); })); });
    var usesRight=defs.some(function(d){return d.right;});
    var series=[{}];
    defs.forEach(function(d){ series.push({label:d.label, stroke:d.color, width:1.6, scale:(d.right?"y2":"y"), spanGaps:true}); });
    var axes=[{}, {scale:"y"}];
    if(usesRight) axes.push({scale:"y2", side:1, grid:{show:false}});
    var opts={ title:title, width:(el.clientWidth||700), height:170, legend:{live:true},
      cursor:{sync:{key:"m"}, focus:{prox:20}}, series:series, axes:axes,
      hooks:{ drawClear:[bandHook], setCursor:[function(u){ if(u.cursor.idx!=null) setSlider(u.cursor.idx, false); }] } };
    charts.push(new uPlot(opts, data, el));
  }

  async function loadDay(day){
    curDay=day; destroyCharts();
    try{ recs=((await (await fetch(withTok("/api/metadata?day="+encodeURIComponent(day)))).json()).records)||[]; }
    catch(e){ recs=[]; }
    var host=$("dayCharts"); host.innerHTML="";
    if(!recs.length){ host.innerHTML='<div class="card pad sub">Brak danych dla tego dnia.</div>'; renderCond(null); return; }
    var s0=recs[0]||{};
    SUN={ rise:tsec(s0.sunrise), set:tsec(s0.sunset) };
    await loadDayReboots(day);
    ["chCanopy","chTemp","chWx","chLight","chSys"].forEach(function(id){ var d=document.createElement("div"); d.className="chart"; d.id=id; host.appendChild(d); });
    makeChart($("chCanopy"),"Wzrost — zieleń (canopy %)",[{label:"zieleń %",path:"canopy_pct",color:"#3da35a"}]);
    makeChart($("chTemp"),"Temperatura (°C)",[{label:"CPU",path:"cpu_temp_c",color:"#e0533f"},{label:"zewn.",path:"outdoor.temp_c",color:"#4eb389"}]);
    makeChart($("chWx"),"Pogoda",[{label:"zachmurzenie %",path:"outdoor.cloud",color:"#7d93b5"},{label:"opad mm",path:"outdoor.precip",color:"#5b9bd8",right:true},{label:"wiatr km/h",path:"outdoor.wind",color:"#9aa7a0",right:true}]);
    makeChart($("chLight"),"Światło",[{label:"jasność",path:"brightness",color:"#e6b450"},{label:"lux",path:"cam.lux",color:"#5b9bd8",right:true}]);
    makeChart($("chSys"),"System",[{label:"RAM %",path:"mem_used_pct",color:"#a585d0"},{label:"dysk %",path:"disk_used_pct",color:"#698075"},{label:"load",path:"load1",color:"#ef9b42",right:true}]);
    if(slider){ slider.max=String(recs.length-1); }
    setSlider(recs.length-1, true);
    var csv=$("mCsv"); if(csv) csv.href=withTok("/api/metadata?day="+encodeURIComponent(day)+"&format=csv");
    loadEvents();
  }
  async function loadDayReboots(day){
    REBOOTS=[];
    try{
      var ev=(await (await fetch(withTok("/api/metadata/events"))).json()).events||[];
      ev.forEach(function(e){ if(e.type==="reboot" && (e.ts||"").slice(0,10)===day){ var t=tsec(e.ts); if(t)REBOOTS.push(t); } });
    }catch(e){}
  }
  async function loadEvents(){
    var el=$("mEvents"); if(!el) return;
    try{
      var ev=((await (await fetch(withTok("/api/metadata/events"))).json()).events||[]).slice(0,8);
      el.innerHTML = ev.length ? ("Zdarzenia: " + ev.map(function(e){ return (e.type==="reboot"?"<b>reboot</b>":e.type)+" "+e.ts.replace("T"," "); }).join(" · ")) : "";
    }catch(e){}
  }
  async function loadHist(){
    try{
      var s=((await (await fetch(withTok("/api/metadata/summary?days=30"))).json()).summary)||[];
      var el=$("chHist"); el.innerHTML="";
      if(!s.length){ el.innerHTML='<div class="sub">Brak danych historycznych.</div>'; return; }
      var xs=s.map(function(d){ return Date.parse(d.day+"T12:00:00")/1000; });
      var data=[xs,
        s.map(function(d){ return d.canopy?d.canopy.avg:null; }),
        s.map(function(d){ return d.cpu_temp?d.cpu_temp.avg:null; }),
        s.map(function(d){ return d.outdoor_temp?d.outdoor_temp.max:null; }),
        s.map(function(d){ return d.outdoor_temp?d.outdoor_temp.min:null; }),
        s.map(function(d){ return d.brightness?d.brightness.avg:null; })];
      if(histChart){ try{histChart.destroy();}catch(e){} }
      histChart=new uPlot({ title:"Historia (dzienne) — wzrost i klimat", width:(el.clientWidth||700), height:280, legend:{live:true},
        series:[{},{label:"zieleń avg %",stroke:"#3da35a",width:2.4,scale:"y"},{label:"CPU avg",stroke:"#e0533f",scale:"y2"},{label:"zewn. max",stroke:"#4eb389",scale:"y2"},{label:"zewn. min",stroke:"#5b9bd8",scale:"y2"},{label:"jasność avg",stroke:"#e6b450",scale:"y3",show:false}],
        axes:[{},{scale:"y"},{scale:"y2",side:1,grid:{show:false}}] }, data, el);
    }catch(e){}
  }
  function show(tab){
    $("dayView").style.display = tab==="day"?"":"none";
    $("histView").style.display = tab==="hist"?"":"none";
    $("mTabDay").classList.toggle("btn-primary", tab==="day");
    $("mTabHist").classList.toggle("btn-primary", tab==="hist");
    if(tab==="hist") loadHist();
  }
  $("mTabDay").addEventListener("click", function(){ show("day"); });
  $("mTabHist").addEventListener("click", function(){ show("hist"); });
  var sel=$("mDay");
  if(sel) sel.addEventListener("change", function(){ loadDay(sel.value); });
  window.addEventListener("resize", function(){
    charts.forEach(function(u){ try{ u.setSize({width:u.root.parentNode.clientWidth, height:170}); }catch(e){} });
    if(histChart){ try{ histChart.setSize({width:histChart.root.parentNode.clientWidth, height:280}); }catch(e){} }
  });

  /* ---- Feature: plant region (canopy ROI) + backfill ---- */
  var ov=$("mRoiOv"), rect=$("mRoiRect"), regionBtn=$("mRegion"), backBtn=$("mBackfill"), cstat=$("mCanopyStat");
  var regionOn=false;
  function showRect(roi){
    if(!rect||!img) return;
    if(!roi){ rect.style.display="none"; return; }
    rect.style.display="block";
    rect.style.left=(roi[0]*100)+"%"; rect.style.top=(roi[1]*100)+"%";
    rect.style.width=(roi[2]*100)+"%"; rect.style.height=(roi[3]*100)+"%";
  }
  async function refreshCanopyStat(){
    try{
      var s=await (await fetch(withTok("/api/canopy/status"))).json();
      showRect(s.roi);
      var t="";
      if(s.roi) t+="region ustawiony · ";
      if(s.running) t+="przeliczanie "+(s.done||0)+"/"+(s.total||0)+"…";
      else if(s.missing) t+=s.missing+" klatek bez zieleni";
      else t+="zieleń policzona";
      if(cstat) cstat.textContent=t;
      return s;
    }catch(e){ return {}; }
  }
  if(regionBtn) regionBtn.addEventListener("click", function(){
    regionOn=!regionOn;
    regionBtn.classList.toggle("btn-primary", regionOn);
    if(ov) ov.style.display=regionOn?"block":"none";
  });
  if(ov){
    var drag=null;
    function draw(e){ if(!drag)return; var x=Math.min(e.clientX,drag.x0),y=Math.min(e.clientY,drag.y0);
      rect.style.display="block"; rect.style.left=(x-drag.r.left)+"px"; rect.style.top=(y-drag.r.top)+"px";
      rect.style.width=Math.abs(e.clientX-drag.x0)+"px"; rect.style.height=Math.abs(e.clientY-drag.y0)+"px"; }
    ov.addEventListener("pointerdown", function(e){ try{ov.setPointerCapture(e.pointerId);}catch(_){}
      drag={r:ov.getBoundingClientRect(),x0:e.clientX,y0:e.clientY}; draw(e); });
    ov.addEventListener("pointermove", draw);
    ov.addEventListener("pointerup", async function(e){
      if(!drag)return; var r=drag.r, x=Math.min(e.clientX,drag.x0),y=Math.min(e.clientY,drag.y0);
      var w=Math.abs(e.clientX-drag.x0),h=Math.abs(e.clientY-drag.y0); drag=null;
      if(w<10||h<10){ // tiny = clear region
        await fetch(withTok("/api/canopy/roi"),{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({reset:true})});
      } else {
        await fetch(withTok("/api/canopy/roi"),{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({x:(x-r.left)/r.width,y:(y-r.top)/r.height,w:w/r.width,h:h/r.height})});
      }
      refreshCanopyStat();
    });
  }
  if(backBtn) backBtn.addEventListener("click", async function(){
    try{ await fetch(withTok("/api/canopy/backfill"),{method:"POST",headers:{"Content-Type":"application/json"},body:"{}"}); }catch(e){}
    var poll=setInterval(async function(){ var s=await refreshCanopyStat(); if(!s.running){ clearInterval(poll); if(curDay) loadDay(curDay); } }, 1500);
  });

  (async function(){
    var days=[];
    try{ days=((await (await fetch(withTok("/api/metadata/days"))).json()).days)||[]; }catch(e){}
    if(!days.length){ $("dayCharts").innerHTML='<div class="card pad sub">Brak danych metadanych jeszcze (poczekaj na snapshot).</div>'; return; }
    if(sel) sel.innerHTML=days.map(function(d){ return '<option>'+d+'</option>'; }).join("");
    show("day");
    loadDay(days[0]);
    refreshCanopyStat();
  })();
})();
"""


MOVIE_JS = """
(function(){
  function withTok(p){ var t=window.CAM_TOKEN||""; var u=new URL(p,location.origin); if(t)u.searchParams.set("token",t); return u.pathname+u.search; }
  var b=document.getElementById("mvBuild"), st=document.getElementById("mvStat"), vid=document.getElementById("mvVid"), dl=document.getElementById("mvDl");
  if(!b) return;
  function showVid(s){ var u=withTok("/movies/growth.mp4")+"&t="+(s.mtime||0); if(vid.dataset.t!=String(s.mtime)){ vid.src=u; vid.dataset.t=String(s.mtime); } vid.style.display=""; dl.href=u; dl.style.display=""; }
  async function status(){ try{ return await (await fetch(withTok("/api/movie/status"))).json(); }catch(e){ return {}; } }
  async function refresh(){ var s=await status();
    if(s.building){ st.textContent="buduję film…"; b.disabled=true; }
    else { b.disabled=false; if(s.exists){ st.textContent="gotowe ("+Math.round((s.size||0)/1048576)+" MB)"; showVid(s); } else { st.textContent = s.ffmpeg? "" : "ffmpeg niedostępny"; } }
    return s; }
  b.addEventListener("click", async function(){ st.textContent="startuję…"; b.disabled=true;
    try{ await fetch(withTok("/api/movie/build"),{method:"POST",headers:{"Content-Type":"application/json"},body:"{}"}); }catch(e){}
    var poll=setInterval(async function(){ var s=await refresh(); if(!s.building){ clearInterval(poll); } }, 2500); });
  refresh();
})();
"""


COMPARE_JS = """
(function(){
  function $(id){ return document.getElementById(id); }
  function withTok(p){ var t=window.CAM_TOKEN||""; var u=new URL(p,location.origin); if(t)u.searchParams.set("token",t); return u.pathname+u.search; }
  if(!$("cmpRange")) return;
  var A={day:null,frames:[]}, B={day:null,frames:[]};
  var over=$("cmpA"), base=$("cmpB"), divEl=$("cmpDiv"), range=$("cmpRange"), wrap=$("cmpWrap");
  function setDiv(v){ var ins="inset(0 "+(100-v)+"% 0 0)"; over.style.clipPath=ins; over.style.webkitClipPath=ins; divEl.style.left=v+"%"; }
  function url(day,file){ return withTok("/history/"+encodeURIComponent(day)+"/"+encodeURIComponent(file)); }
  function fill(sel, items, val){ sel.innerHTML=items.map(function(i){ return '<option'+(i===val?' selected':'')+'>'+i+'</option>'; }).join(""); }
  async function days(){ try{ return (await (await fetch(withTok("/api/metadata/days"))).json()).days||[]; }catch(e){ return []; } }
  async function framesFor(day){ try{ var r=(await (await fetch(withTok("/api/metadata?day="+encodeURIComponent(day)))).json()).records||[]; return r.map(function(x){return x.file;}).filter(Boolean); }catch(e){ return []; } }
  async function loadSide(side){
    var S=side==="A"?A:B, daySel=$("day"+side), frSel=$("fr"+side), img=side==="A"?over:base;
    S.day=daySel.value; S.frames=await framesFor(S.day);
    var def = side==="A"? S.frames[0] : S.frames[S.frames.length-1];
    fill(frSel, S.frames, def);
    if(def) img.src=url(S.day, def);
  }
  $("dayA").addEventListener("change", function(){ loadSide("A"); });
  $("dayB").addEventListener("change", function(){ loadSide("B"); });
  $("frA").addEventListener("change", function(){ over.src=url(A.day,$("frA").value); });
  $("frB").addEventListener("change", function(){ base.src=url(B.day,$("frB").value); });
  range.addEventListener("input", function(){ setDiv(parseFloat(range.value)); });
  base.addEventListener("load", function(){ setDiv(parseFloat(range.value)); });
  function pctAt(e){ var r=base.getBoundingClientRect(); return Math.max(0,Math.min(100,(e.clientX-r.left)/r.width*100)); }
  var dragging=false;
  wrap.addEventListener("pointerdown", function(e){ dragging=true; var v=pctAt(e); range.value=v; setDiv(v); });
  wrap.addEventListener("pointermove", function(e){ if(dragging){ var v=pctAt(e); range.value=v; setDiv(v); } });
  window.addEventListener("pointerup", function(){ dragging=false; });
  (async function(){
    var ds=await days();
    if(!ds.length){ wrap.innerHTML='<div class="pad sub">Brak historii do porównania.</div>'; return; }
    fill($("dayA"), ds, ds[ds.length-1]);
    fill($("dayB"), ds, ds[0]);
    await loadSide("A"); await loadSide("B");
    setDiv(50);
  })();
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
        if parsed.path.startswith("/vendor/"):
            self._send_vendor(parsed.path)
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
        elif parsed.path == "/live.jpg":
            self._send_live_frame()
        elif parsed.path == "/live.mjpg":
            self._send_mjpeg()
        elif parsed.path == "/api/status":
            self._send_json(self._status())
        elif parsed.path == "/api/system":
            self._send_json(read_system_stats(self.storage.data_dir))
        elif parsed.path == "/api/metadata":
            self._metadata(parsed.query)
        elif parsed.path == "/api/metadata/latest":
            self._metadata_latest(parsed.query)
        elif parsed.path == "/api/metadata/days":
            self._metadata_days(parsed.query)
        elif parsed.path == "/api/metadata/summary":
            self._metadata_summary(parsed.query)
        elif parsed.path == "/api/metadata/events":
            self._metadata_events(parsed.query)
        elif parsed.path == "/metrics":
            self._send_html(self._metrics_html(parsed.query))
        elif parsed.path == "/admin":
            self._send_html(self._admin_page(parsed.query))
        elif parsed.path == "/api/shell/read":
            self._shell_read(parsed.query)
        elif parsed.path == "/api/timelapse/status":
            self._timelapse_status(parsed.query)
        elif parsed.path == "/api/canopy/status":
            self._canopy_status(parsed.query)
        elif parsed.path == "/api/movie/status":
            self._movie_status(parsed.query)
        elif parsed.path == "/compare":
            self._send_html(self._compare_html(parsed.query))
        elif parsed.path.startswith("/movies/"):
            self._handle_movie(parsed.path, parsed.query)
        elif parsed.path == "/api/burst/status":
            self._burst_status(parsed.query)
        elif parsed.path == "/api/burst/session":
            self._burst_session_status(parsed.query)
        elif parsed.path == "/api/diag":
            self._diag(parsed.query)
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
        elif parsed.path == "/burst":
            self._send_html(self._burst_index_html(parsed.query))
        elif parsed.path.startswith("/burst/"):
            self._handle_burst(parsed.path, parsed.query)
        else:
            self._send_text("not found\n", "text/plain", HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        self._cookie_token = None
        parsed = urlparse(self.path)
        if parsed.path == "/api/admin/exec":
            self._admin_exec(parsed.query)
        elif parsed.path == "/api/shell/open":
            self._shell_open(parsed.query)
        elif parsed.path == "/api/shell/input":
            self._shell_input(parsed.query)
        elif parsed.path == "/api/shell/resize":
            self._shell_resize(parsed.query)
        elif parsed.path == "/api/shell/close":
            self._shell_close(parsed.query)
        elif parsed.path == "/api/timelapse/build":
            self._timelapse_build(parsed.query)
        elif parsed.path == "/api/canopy/roi":
            self._canopy_roi(parsed.query)
        elif parsed.path == "/api/canopy/backfill":
            self._canopy_backfill(parsed.query)
        elif parsed.path == "/api/movie/build":
            self._movie_build(parsed.query)
        elif parsed.path == "/api/burst/start":
            self._burst_start(parsed.query)
        elif parsed.path == "/api/burst/stop":
            self._burst_stop(parsed.query)
        elif parsed.path == "/api/burst/timelapse":
            self._burst_timelapse(parsed.query)
        elif parsed.path == "/api/live/roi":
            self._live_roi(parsed.query)
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

    def _live_roi(self, query: str) -> None:
        if not self._authorized(query):
            self._send_json({"error": "unauthorized"}, HTTPStatus.UNAUTHORIZED)
            return
        body = self._read_json_body() or {}
        if body.get("reset"):
            self.live.clear_roi()
            self._send_json({"ok": True, "roi": None, "zoom": 1.0})
            return
        if "x" not in body:  # query current state
            d = self.live.diag()
            self._send_json({"ok": True, "roi": d.get("roi"), "zoom": d.get("zoom", 1.0)})
            return
        try:
            x = float(body["x"]); y = float(body["y"]); w = float(body["w"]); h = float(body["h"])
        except (KeyError, TypeError, ValueError):
            self._send_json({"error": "bad roi"}, HTTPStatus.BAD_REQUEST)
            return
        roi = self.live.set_roi(x, y, w, h)
        self._send_json({"ok": True, "roi": list(roi), "zoom": round(1.0 / roi[2], 1)})

    def _burst_status(self, query: str) -> None:
        if not self._authorized(query):
            self._send_json({"error": "unauthorized"}, HTTPStatus.UNAUTHORIZED)
            return
        self._send_json(self.server.burst.status())  # type: ignore[attr-defined]

    def _burst_start(self, query: str) -> None:
        if not self._authorized(query):
            self._send_json({"error": "unauthorized"}, HTTPStatus.UNAUTHORIZED)
            return
        body = self._read_json_body() or {}
        try:
            interval = float(body.get("interval", 0))
            duration = float(body.get("duration", 60))
            width = int(body.get("width", 0) or 0)
            height = int(body.get("height", 0) or 0)
        except (TypeError, ValueError):
            self._send_json({"error": "bad params"}, HTTPStatus.BAD_REQUEST)
            return
        result = self.server.burst.start(self.storage, interval, duration, width, height)  # type: ignore[attr-defined]
        self._send_json(result)

    def _burst_stop(self, query: str) -> None:
        if not self._authorized(query):
            self._send_json({"error": "unauthorized"}, HTTPStatus.UNAUTHORIZED)
            return
        self._send_json(self.server.burst.stop())  # type: ignore[attr-defined]

    def _burst_session_status(self, query: str) -> None:
        if not self._authorized(query):
            self._send_json({"error": "unauthorized"}, HTTPStatus.UNAUTHORIZED)
            return
        session = parse_qs(query).get("session", [""])[0]
        sess_dir = self.storage.burst_dir / session
        if "/" in session or ".." in session or not sess_dir.is_dir():
            self._send_json({"error": "unknown session"}, HTTPStatus.NOT_FOUND)
            return
        video = sess_dir / TIMELAPSE_NAME
        err_file = sess_dir / "timelapse.error.txt"
        with self.server.timelapse_lock:  # type: ignore[attr-defined]
            building = session in self.server.burst_building  # type: ignore[attr-defined]
        self._send_json({
            "exists": video.exists(),
            "building": building,
            "size": video.stat().st_size if video.exists() else 0,
            "frames": len(self.storage.burst_frames(session)),
            "ffmpeg": have_ffmpeg(),
            "error": err_file.read_text(encoding="utf-8") if err_file.exists() else "",
        })

    def _burst_timelapse(self, query: str) -> None:
        if not self._authorized(query):
            self._send_json({"error": "unauthorized"}, HTTPStatus.UNAUTHORIZED)
            return
        session = parse_qs(query).get("session", [""])[0]
        sess_dir = self.storage.burst_dir / session
        if "/" in session or ".." in session or not sess_dir.is_dir():
            self._send_json({"error": "unknown session"}, HTTPStatus.NOT_FOUND)
            return
        server = self.server
        with server.timelapse_lock:  # type: ignore[attr-defined]
            if session in server.burst_building:  # type: ignore[attr-defined]
                self._send_json({"ok": True, "building": True, "already": True})
                return
            server.burst_building.add(session)  # type: ignore[attr-defined]

        def worker():
            try:
                from .burst import build_session_timelapse
                build_session_timelapse(sess_dir)
            finally:
                with server.timelapse_lock:  # type: ignore[attr-defined]
                    server.burst_building.discard(session)  # type: ignore[attr-defined]

        threading.Thread(target=worker, daemon=True).start()
        log.info("burst timelapse rebuild started for %s", session)
        self._send_json({"ok": True, "building": True})

    def _metadata(self, query: str) -> None:
        if not self._authorized(query):
            self._send_json({"error": "unauthorized"}, HTTPStatus.UNAUTHORIZED)
            return
        params = parse_qs(query)
        day = params.get("day", [""])[0]
        if not _valid_day(day):
            self._send_json({"error": "bad day"}, HTTPStatus.BAD_REQUEST)
            return
        records = self.storage.metrics.query_day(day)
        if params.get("format", [""])[0] == "csv":
            cols = ["ts", "file", "cpu_temp_c", "brightness", "size", "load1",
                    "mem_used_pct", "disk_used_pct", "outdoor.temp_c", "outdoor.humidity",
                    "outdoor.wind", "outdoor.code", "cam.exposure_us", "cam.gain",
                    "cam.lux", "cam.colour_temp"]

            def cell(rec, col):
                if "." in col:
                    a, b = col.split(".", 1)
                    return rec.get(a, {}).get(b, "")
                return rec.get(col, "")

            lines = [",".join(cols)]
            for rec in records:
                lines.append(",".join(str(cell(rec, c)) for c in cols))
            self._send_text("\n".join(lines) + "\n", "text/csv")
            return
        self._send_json({"day": day, "count": len(records), "records": records})

    def _metadata_days(self, query: str) -> None:
        if not self._authorized(query):
            self._send_json({"error": "unauthorized"}, HTTPStatus.UNAUTHORIZED)
            return
        self._send_json({"days": self.storage.metrics.days()})

    def _metadata_summary(self, query: str) -> None:
        if not self._authorized(query):
            self._send_json({"error": "unauthorized"}, HTTPStatus.UNAUTHORIZED)
            return
        try:
            limit = int(parse_qs(query).get("days", ["30"])[0])
        except ValueError:
            limit = 30
        self._send_json({"summary": self.storage.metrics.summary(max(1, limit))})

    def _metadata_events(self, query: str) -> None:
        if not self._authorized(query):
            self._send_json({"error": "unauthorized"}, HTTPStatus.UNAUTHORIZED)
            return
        self._send_json({"events": self.storage.metrics.events(50)})

    def _metadata_latest(self, query: str) -> None:
        if not self._authorized(query):
            self._send_json({"error": "unauthorized"}, HTTPStatus.UNAUTHORIZED)
            return
        self._send_json(self.storage.metrics.latest())

    def _metrics_html(self, query: str) -> str:
        token = self.app_config.server.auth_token
        token_js = json.dumps(token)
        body = f"""
<link rel="stylesheet" href="/vendor/uPlot.min.css"/>
<script src="/vendor/uPlot.iife.min.js"></script>
<h1 class="h">Dane</h1>
<div class="ctrlrow">
  <label class="switch">Dzień <select id="mDay" class="mini"></select></label>
  <button id="mTabDay" class="btn btn-primary" type="button">Dzień</button>
  <button id="mTabHist" class="btn" type="button">Historia</button>
  <button id="mRegion" class="btn" type="button">🌿 Region rośliny</button>
  <button id="mBackfill" class="btn" type="button">↻ Przelicz zieleń</button>
  <a id="mCsv" class="btn" href="#">⬇️ CSV</a>
  <span id="mCanopyStat" class="sub"></span>
</div>
<div id="dayView">
  <div id="mCond" class="cond card" style="display:none"></div>
  <div id="dayCharts"></div>
  <div class="card pad">
    <div class="scrubber"><input id="mSlider" type="range" min="0" max="0" value="0" aria-label="Przewijaj próbki"></div>
    <div class="metarow">
      <div class="mimgwrap"><img id="mImg" alt="klatka"><div id="mRoiOv" class="roiov" style="display:none"></div><div id="mRoiRect" class="roirect" style="display:none"></div></div>
      <pre id="mVals" class="out"></pre>
    </div>
    <div id="mEvents" class="evnt"></div>
  </div>
</div>
<div id="histView" style="display:none"><div id="chHist" class="chart"></div></div>
<script>window.CAM_TOKEN={token_js};</script>
<script>{METRICS_JS}</script>
"""
        return self._layout("Dane", body, active="/metrics")

    def _compare_html(self, query: str) -> str:
        token = self.app_config.server.auth_token
        token_js = json.dumps(token)
        body = f"""
<h1 class="h">Porównaj</h1>
<p class="sub">Przeciągnij linię (lub suwak), by porównać tę samą roślinę w dwóch momentach. Lewa strona = „przed", prawa = „po".</p>
<div class="ctrlrow">
  <label class="switch">Przed <select id="dayA" class="mini"></select> <select id="frA" class="mini"></select></label>
  <label class="switch">Po <select id="dayB" class="mini"></select> <select id="frB" class="mini"></select></label>
</div>
<div id="cmpWrap" class="card hero-card cmp">
  <img id="cmpB" class="cmp-img" alt="po">
  <img id="cmpA" class="cmp-img cmp-over" alt="przed">
  <div id="cmpDiv" class="cmp-div"></div>
</div>
<div class="scrubber"><input id="cmpRange" type="range" min="0" max="100" value="50" aria-label="Suwak porównania"></div>
<script>window.CAM_TOKEN={token_js};</script>
<script>{COMPARE_JS}</script>
"""
        return self._layout("Porównaj", body, active="/compare")

    def _diag(self, query: str) -> None:
        if not self._authorized(query):
            self._send_json({"error": "unauthorized"}, HTTPStatus.UNAUTHORIZED)
            return
        s = self.app_config.server
        c = self.app_config.camera
        payload = {
            "time": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "ffmpeg": have_ffmpeg(),
            "live": self.server.live.diag(),  # type: ignore[attr-defined]
            "burst": self.server.burst.status(),  # type: ignore[attr-defined]
            "system": read_system_stats(self.storage.data_dir),
            "server": {
                "version": self.server_version,
                "host": s.host,
                "port": s.port,
                "live_fps": c.live_fps,
                "live_size": [c.live_width, c.live_height],
                "live_quality": c.live_quality,
                "live_idle_timeout": c.live_idle_timeout,
                "snapshot_interval": self.app_config.snapshot.interval_seconds,
            },
            "log_tail": list(LOG_RING.buf),
        }
        self._send_json(payload)

    def _timelapse_status(self, query: str) -> None:
        if not self._authorized(query):
            self._send_json({"error": "unauthorized"}, HTTPStatus.UNAUTHORIZED)
            return
        day = parse_qs(query).get("day", [""])[0]
        if not _valid_day(day):
            self._send_json({"error": "bad day"}, HTTPStatus.BAD_REQUEST)
            return
        video = self.storage.history_dir / day / TIMELAPSE_NAME
        exists = video.exists()
        with self.server.timelapse_lock:  # type: ignore[attr-defined]
            building = day in self.server.timelapse_building  # type: ignore[attr-defined]
        self._send_json({
            "exists": exists,
            "building": building,
            "size": video.stat().st_size if exists else 0,
            "ffmpeg": have_ffmpeg(),
        })

    def _timelapse_build(self, query: str) -> None:
        if not self._authorized(query):
            self._send_json({"error": "unauthorized"}, HTTPStatus.UNAUTHORIZED)
            return
        day = parse_qs(query).get("day", [""])[0]
        if not _valid_day(day):
            self._send_json({"error": "bad day"}, HTTPStatus.BAD_REQUEST)
            return
        if not (self.storage.history_dir / day).is_dir():
            self._send_json({"error": "unknown day"}, HTTPStatus.NOT_FOUND)
            return
        if not have_ffmpeg():
            self._send_json({"error": "ffmpeg not installed"}, HTTPStatus.NOT_IMPLEMENTED)
            return
        server = self.server
        with server.timelapse_lock:  # type: ignore[attr-defined]
            if day in server.timelapse_building:  # type: ignore[attr-defined]
                self._send_json({"ok": True, "building": True, "already": True})
                return
            server.timelapse_building.add(day)  # type: ignore[attr-defined]
        data_dir = self.storage.data_dir

        def worker():
            try:
                build_day(data_dir, day, force=True)
            except Exception as exc:
                log.warning("timelapse build failed for %s: %s", day, exc)
            finally:
                with server.timelapse_lock:  # type: ignore[attr-defined]
                    server.timelapse_building.discard(day)  # type: ignore[attr-defined]

        threading.Thread(target=worker, daemon=True).start()
        log.info("timelapse build started for %s", day)
        self._send_json({"ok": True, "building": True})

    # ---- Feature: canopy (plant green coverage) ----
    def _canopy_roi(self, query: str) -> None:
        if not self._authorized(query):
            self._send_json({"error": "unauthorized"}, HTTPStatus.UNAUTHORIZED)
            return
        body = self._read_json_body() or {}
        if body.get("reset"):
            self.storage.set_canopy_roi(None)
            self._send_json({"ok": True, "roi": None})
            return
        if "x" not in body:
            roi = self.storage.canopy_roi()
            self._send_json({"ok": True, "roi": list(roi) if roi else None})
            return
        try:
            x = float(body["x"]); y = float(body["y"]); w = float(body["w"]); h = float(body["h"])
        except (KeyError, TypeError, ValueError):
            self._send_json({"error": "bad roi"}, HTTPStatus.BAD_REQUEST)
            return
        w = max(0.02, min(w, 1.0)); h = max(0.02, min(h, 1.0))
        x = min(max(0.0, x), 1.0 - w); y = min(max(0.0, y), 1.0 - h)
        roi = (x, y, w, h)
        self.storage.set_canopy_roi(roi)
        self._send_json({"ok": True, "roi": [round(v, 4) for v in roi]})

    def _canopy_status(self, query: str) -> None:
        if not self._authorized(query):
            self._send_json({"error": "unauthorized"}, HTTPStatus.UNAUTHORIZED)
            return
        st = dict(self.server.canopy_backfill)  # type: ignore[attr-defined]
        st["missing"] = self.storage.metrics.count_missing_canopy()
        roi = self.storage.canopy_roi()
        st["roi"] = list(roi) if roi else None
        self._send_json(st)

    def _canopy_backfill(self, query: str) -> None:
        if not self._authorized(query):
            self._send_json({"error": "unauthorized"}, HTTPStatus.UNAUTHORIZED)
            return
        server = self.server
        with server.timelapse_lock:  # type: ignore[attr-defined]
            if server.canopy_backfill["running"]:  # type: ignore[attr-defined]
                self._send_json({"ok": True, "running": True, "already": True})
                return
            total = self.storage.metrics.count_missing_canopy()
            server.canopy_backfill = {"running": True, "done": 0, "total": total}  # type: ignore[attr-defined]
        storage = self.storage

        def worker():
            try:
                storage.backfill_canopy(progress=lambda d: server.canopy_backfill.__setitem__("done", d))  # type: ignore[attr-defined]
            except Exception as exc:
                log.warning("canopy backfill failed: %s", exc)
            finally:
                server.canopy_backfill["running"] = False  # type: ignore[attr-defined]

        threading.Thread(target=worker, daemon=True).start()
        log.info("canopy backfill started (%d rows)", total)
        self._send_json({"ok": True, "running": True, "total": total})

    # ---- Feature: multi-day "growth movie" with burned-in captions ----
    def _movie_build(self, query: str) -> None:
        if not self._authorized(query):
            self._send_json({"error": "unauthorized"}, HTTPStatus.UNAUTHORIZED)
            return
        if not have_ffmpeg():
            self._send_json({"error": "ffmpeg not installed"}, HTTPStatus.NOT_IMPLEMENTED)
            return
        try:
            days = int(parse_qs(query).get("days", ["0"])[0])
        except ValueError:
            days = 0
        server = self.server
        with server.movie_lock:  # type: ignore[attr-defined]
            if server.movie_building:  # type: ignore[attr-defined]
                self._send_json({"ok": True, "building": True, "already": True})
                return
            server.movie_building = True  # type: ignore[attr-defined]
        storage = self.storage

        def worker():
            try:
                from . import timelapse as tl
                sel = sorted(storage.metrics.days())
                if days > 0:
                    sel = sel[-days:]
                if not sel:
                    return
                frames = tl.gather_frames(storage.data_dir, sel[0], sel[-1])
                capmap = {}
                for d in sel:
                    for rec in storage.metrics.query_day(d):
                        capmap[(d, rec.get("file"))] = rec

                def caption(p):
                    rec = capmap.get((p.parent.name, p.name)) or {}
                    parts = [p.parent.name + " " + p.stem.replace("-", ":")[:5]]
                    od = rec.get("outdoor") or {}
                    if od.get("temp_c") is not None:
                        parts.append(f"{od['temp_c']}°C")
                    if rec.get("canopy_pct") is not None:
                        parts.append(f"zielen {rec['canopy_pct']}%")
                    return "   ".join(parts)

                tl.build_movie(frames, storage.movies_dir / "growth.mp4",
                               caption=caption, max_frames=900, force=True)
            except Exception as exc:
                log.warning("growth movie failed: %s", exc)
            finally:
                server.movie_building = False  # type: ignore[attr-defined]

        threading.Thread(target=worker, daemon=True).start()
        log.info("growth movie build started (days=%s)", days or "all")
        self._send_json({"ok": True, "building": True})

    def _movie_status(self, query: str) -> None:
        if not self._authorized(query):
            self._send_json({"error": "unauthorized"}, HTTPStatus.UNAUTHORIZED)
            return
        out = self.storage.movies_dir / "growth.mp4"
        exists = out.exists()
        self._send_json({
            "exists": exists,
            "building": self.server.movie_building,  # type: ignore[attr-defined]
            "size": out.stat().st_size if exists else 0,
            "mtime": int(out.stat().st_mtime) if exists else 0,
            "ffmpeg": have_ffmpeg(),
        })

    def _handle_movie(self, path: str, query: str) -> None:
        if not self._authorized(query):
            self._send_text("unauthorized\n", "text/plain", HTTPStatus.UNAUTHORIZED)
            return
        parts = [unquote(p) for p in path.split("/") if p]
        if len(parts) == 2:
            target = self.storage.movies_dir / parts[1]
            try:
                target.resolve().relative_to(self.storage.movies_dir.resolve())
            except ValueError:
                self._send_text("bad path\n", "text/plain", HTTPStatus.BAD_REQUEST)
                return
            self._send_file(target)
            return
        self._send_text("not found\n", "text/plain", HTTPStatus.NOT_FOUND)

    def _admin_enabled(self) -> bool:
        return bool(self.app_config.server.admin_enabled)

    def _admin_guard(self, query: str) -> bool:
        if not self._admin_enabled():
            self._send_json({"error": "admin panel disabled"}, HTTPStatus.FORBIDDEN)
            return False
        if not self._authorized(query):
            self._send_json({"error": "unauthorized"}, HTTPStatus.UNAUTHORIZED)
            return False
        return True

    def _read_json_body(self, limit: int = 64 * 1024) -> Optional[dict]:
        try:
            length = int(self.headers.get("Content-Length", "0") or "0")
        except ValueError:
            return None
        if length <= 0 or length > limit:
            return None
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            return payload if isinstance(payload, dict) else None
        except Exception:
            return None

    @property
    def shell(self) -> ShellManager:
        return self.server.shell  # type: ignore[attr-defined]

    def _shell_open(self, query: str) -> None:
        if not self._admin_guard(query):
            return
        body = self._read_json_body() or {}
        try:
            rows, cols = int(body.get("rows", 24)), int(body.get("cols", 80))
        except (TypeError, ValueError):
            rows, cols = 24, 80
        try:
            session = self.shell.open(rows=rows, cols=cols)
        except RuntimeError as exc:
            self._send_json({"error": str(exc)}, HTTPStatus.CONFLICT)
            return
        except Exception as exc:
            log.exception("shell open failed: %s", exc)
            self._send_json({"error": "shell open failed"}, HTTPStatus.INTERNAL_SERVER_ERROR)
            return
        log.warning("SHELL session %s opened from %s", session.sid, self.address_string())
        self._send_json({"sid": session.sid})

    def _shell_input(self, query: str) -> None:
        if not self._admin_guard(query):
            return
        body = self._read_json_body() or {}
        session = self.shell.get(body.get("sid", ""))
        if session is None:
            self._send_json({"error": "no session"}, HTTPStatus.NOT_FOUND)
            return
        try:
            data = base64.b64decode(body.get("data", "")) if body.get("data") else b""
        except Exception:
            self._send_json({"error": "bad data"}, HTTPStatus.BAD_REQUEST)
            return
        session.write(data)
        self._send_json({"ok": True})

    def _shell_resize(self, query: str) -> None:
        if not self._admin_guard(query):
            return
        body = self._read_json_body() or {}
        session = self.shell.get(body.get("sid", ""))
        if session is None:
            self._send_json({"error": "no session"}, HTTPStatus.NOT_FOUND)
            return
        try:
            session.resize(int(body.get("rows", 24)), int(body.get("cols", 80)))
        except (TypeError, ValueError):
            pass
        self._send_json({"ok": True})

    def _shell_close(self, query: str) -> None:
        if not self._admin_guard(query):
            return
        body = self._read_json_body() or {}
        self.shell.close(body.get("sid", ""))
        self._send_json({"ok": True})

    def _shell_read(self, query: str) -> None:
        if not self._admin_guard(query):
            return
        params = parse_qs(query)
        sid = params.get("sid", [""])[0]
        try:
            pos = int(params.get("pos", ["0"])[0])
        except ValueError:
            pos = 0
        session = self.shell.get(sid)
        if session is None:
            self._send_json({"error": "no session"}, HTTPStatus.NOT_FOUND)
            return
        data, new_pos, alive = session.read_since(pos)
        self._send_json({
            "data": base64.b64encode(data).decode("ascii"),
            "pos": new_pos,
            "alive": alive,
        })

    def _admin_exec(self, query: str) -> None:
        if not self._admin_enabled():
            self._send_json({"error": "admin panel disabled"}, HTTPStatus.FORBIDDEN)
            return
        # Same token / cookie as the rest of the site.
        if not self._authorized(query):
            self._send_json({"error": "unauthorized"}, HTTPStatus.UNAUTHORIZED)
            return
        try:
            length = int(self.headers.get("Content-Length", "0") or "0")
        except ValueError:
            length = 0
        if length <= 0 or length > 64 * 1024:
            self._send_json({"error": "missing or oversized body"}, HTTPStatus.BAD_REQUEST)
            return
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            cmd = payload.get("cmd", "")
        except Exception:
            self._send_json({"error": "invalid json"}, HTTPStatus.BAD_REQUEST)
            return
        if not isinstance(cmd, str) or not cmd.strip():
            self._send_json({"error": "empty command"}, HTTPStatus.BAD_REQUEST)
            return

        timeout = max(1, int(self.app_config.server.admin_timeout))
        log.warning("ADMIN exec from %s: %s", self.address_string(), cmd)
        started = time.time()
        timed_out = False
        try:
            proc = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            stdout, stderr, code = proc.stdout, proc.stderr, proc.returncode
        except subprocess.TimeoutExpired as exc:
            timed_out = True
            code = 124
            stdout = exc.stdout if isinstance(exc.stdout, str) else (exc.stdout or b"").decode("utf-8", "replace")
            stderr = exc.stderr if isinstance(exc.stderr, str) else (exc.stderr or b"").decode("utf-8", "replace")
        except Exception as exc:
            self._send_json({"error": f"exec failed: {exc}"}, HTTPStatus.INTERNAL_SERVER_ERROR)
            return

        cap = 200_000
        self._send_json({
            "ok": code == 0 and not timed_out,
            "code": code,
            "timed_out": timed_out,
            "duration": round(time.time() - started, 2),
            "stdout": (stdout or "")[-cap:],
            "stderr": (stderr or "")[-cap:],
        })

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

    def _send_file(self, path: Path, cache: bool = False) -> None:
        if not path.exists() or not path.is_file():
            self._send_text("not found\n", "text/plain", HTTPStatus.NOT_FOUND)
            return
        content_type = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
        size = path.stat().st_size
        start, end = 0, size - 1
        partial = False
        rng = self.headers.get("Range")
        if rng and rng.startswith("bytes="):
            spec = rng.split("=", 1)[1].split(",")[0].strip()
            lo, _, hi = spec.partition("-")
            try:
                if lo == "":
                    start = max(0, size - int(hi))
                else:
                    start = int(lo)
                    end = int(hi) if hi else size - 1
                end = min(end, size - 1)
                if start > end or start >= size:
                    raise ValueError
                partial = True
            except ValueError:
                self.send_response(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
                self.send_header("Content-Range", f"bytes */{size}")
                self.end_headers()
                return
        length = end - start + 1
        self.send_response(HTTPStatus.PARTIAL_CONTENT if partial else HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(length))
        self.send_header("Accept-Ranges", "bytes")
        if partial:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.send_header("Cache-Control", "public, max-age=86400" if cache else "no-store")
        self.end_headers()
        try:
            with path.open("rb") as fh:
                fh.seek(start)
                remaining = length
                while remaining > 0:
                    chunk = fh.read(min(64 * 1024, remaining))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    remaining -= len(chunk)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _send_vendor(self, path: str) -> None:
        """Serve vendored static assets (xterm.js, ...) without auth — they
        contain no secrets and must load before any token cookie is set."""
        rel = path[len("/vendor/"):]
        vendor_dir = self.server.vendor_dir  # type: ignore[attr-defined]
        target = vendor_dir / rel
        try:
            target.resolve().relative_to(vendor_dir.resolve())
        except ValueError:
            self._send_text("bad path\n", "text/plain", HTTPStatus.BAD_REQUEST)
            return
        self._send_file(target, cache=True)

    def _send_live_frame(self) -> None:
        """Single current frame for the adaptive pull-based live view."""
        try:
            frame = self.live.grab_frame()
        except CameraBusy:
            self._send_text("camera busy (live/snapshot/burst in use)\n", "text/plain", HTTPStatus.CONFLICT)
            return
        except Exception as exc:
            log.warning("live frame failed: %s", exc)
            self._send_text(f"live error: {type(exc).__name__}: {exc}\n", "text/plain",
                            HTTPStatus.INTERNAL_SERVER_ERROR)
            return
        try:
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "image/jpeg")
            self.send_header("Content-Length", str(len(frame)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(frame)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _send_mjpeg(self) -> None:
        try:
            self.live.acquire()
        except CameraBusy:
            self._send_text("camera busy\n", "text/plain", HTTPStatus.CONFLICT)
            return
        interval = 1.0 / max(1, self.app_config.camera.live_fps)
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        try:
            while True:
                try:
                    frame = self.live.capture_locked()
                except CameraBusy:
                    break
                except Exception as exc:
                    log.warning("live mjpeg frame failed: %s", exc)
                    break
                self.wfile.write(b"--frame\r\n")
                self.wfile.write(b"Content-Type: image/jpeg\r\n")
                self.wfile.write(f"Content-Length: {len(frame)}\r\n\r\n".encode("ascii"))
                self.wfile.write(frame)
                self.wfile.write(b"\r\n")
                self.wfile.flush()
                time.sleep(interval)
        except (BrokenPipeError, ConnectionResetError):
            pass
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

    def _handle_burst(self, path: str, query: str) -> None:
        parts = [unquote(p) for p in path.split("/") if p]
        if len(parts) == 2:
            self._send_html(self._burst_session_html(parts[1], query))
            return
        if len(parts) == 3:
            session, filename = parts[1], parts[2]
            target = self.storage.burst_dir / session / filename
            try:
                target.resolve().relative_to(self.storage.burst_dir.resolve())
            except ValueError:
                self._send_text("bad path\n", "text/plain", HTTPStatus.BAD_REQUEST)
                return
            self._send_file(target)
            return
        self._send_text("not found\n", "text/plain", HTTPStatus.NOT_FOUND)

    def _burst_index_html(self, query: str) -> str:
        token = self.app_config.server.auth_token
        sessions = self.storage.burst_sessions()
        if not sessions:
            body = '<div class="card pad empty">Brak sesji burst — uruchom „Szybkie zdjęcia" na stronie Kamera.</div>'
            return self._layout("Burst", body, active="/burst")
        cards = []
        for s in sessions:
            frames = self.storage.burst_frames(s.name)
            has_video = (s / TIMELAPSE_NAME).exists()
            link = href(f"/burst/{quote(s.name)}", token)
            label = html.escape(s.name.replace("_", " "))
            if frames:
                thumb_url = href(f"/burst/{quote(s.name)}/{quote(frames[0].name)}", token)
                thumb = f'<img src="{thumb_url}" alt="{label}" loading="lazy">'
            else:
                thumb = ""
            tag = "🎞️ " if has_video else ""
            cards.append(
                f'<a class="daycard" href="{link}">{thumb}'
                f'<div class="dc-body"><span class="dc-day">{tag}{label}</span>'
                f'<span class="dc-n">{len(frames)}</span></div></a>'
            )
        body = (
            f'<h1 class="h">Burst</h1>'
            f'<p class="sub">{len(sessions)} sesji. Każda to osobny zestaw gęstych klatek + auto-timelapse.</p>'
            f'<div class="grid-days">{"".join(cards)}</div>'
        )
        return self._layout("Burst", body, active="/burst")

    def _burst_session_html(self, session: str, query: str) -> str:
        token = self.app_config.server.auth_token
        frames = self.storage.burst_frames(session)
        if not frames:
            body = '<div class="card pad empty">Pusta lub nieznana sesja burst.</div>'
            return self._layout("Burst", body, active="/burst")
        total = len(frames)
        # bound the in-page frame list (the video covers full playback)
        step = max(1, total // 2000)
        sample = frames[::step]
        first_url = href(f"/burst/{quote(session)}/{quote(sample[0].name)}", token)
        base = "/burst/" + quote(session) + "/"
        day_data = json.dumps({
            "day": session,
            "base": base,
            "index": 0,
            "frames": [{"n": p.name, "l": p.stem.replace("-", ":")} for p in sample],
        })
        video_path = self.storage.burst_dir / session / TIMELAPSE_NAME
        if video_path.exists():
            video_url = href(f"/burst/{quote(session)}/{quote(TIMELAPSE_NAME)}", token)
            video_block = (
                f'<div class="card hero-card">'
                f'<video class="viewer" controls preload="metadata" playsinline poster="{first_url}">'
                f'<source src="{video_url}" type="video/mp4"></video>'
                f'<div class="hero-bar"><span class="badge">🎞️ Timelapse ({total} klatek)</span>'
                f'<span class="spacer"></span>'
                f'<a class="btn" href="{video_url}" download="{html.escape(session)}.mp4">⬇️ MP4</a></div></div>'
            )
        else:
            err_file = self.storage.burst_dir / session / "timelapse.error.txt"
            if err_file.exists():
                note = (
                    '<p class="sub" style="margin:0 0 .5rem">Build timelapse nie powiódł się — pełny log:</p>'
                    f'<pre class="out err">{html.escape(err_file.read_text(encoding="utf-8"))}</pre>'
                )
            else:
                note = '<p class="sub" style="margin:0">Timelapse jeszcze nie zbudowany dla tej sesji.</p>'
            video_block = (
                f'<div class="card pad">{note}'
                '<div class="actions" style="margin-top:.6rem">'
                '<button class="btn btn-primary" id="buildBurst" type="button">▶ Zbuduj timelapse</button></div></div>'
            )
        label = html.escape(session.replace("_", " "))
        body = f"""
<h1 class="h">Burst — {label}</h1>
<p class="sub" id="counter">{total} klatek</p>
{video_block}
<h2 class="h" style="font-size:1rem;margin-top:1.3rem">Klatki (przegląd)</h2>
<div class="card hero-card"><img id="viewer" class="viewer" src="{first_url}" alt="klatka"></div>
<div class="scrubber"><input id="scrub" type="range" min="0" max="{len(sample) - 1}" value="0" aria-label="Przewijaj klatki"></div>
<div class="player">
  <button class="btn btn-primary" id="playBtn" type="button">▶ Odtwórz</button>
  <select id="speedSel" class="mini" aria-label="Prędkość">
    <option value="300">wolno</option>
    <option value="120" selected>normalnie</option>
    <option value="60">szybko</option>
  </select>
  <span class="spacer"></span>
  <a class="btn" id="dlDay" href="{first_url}" download="{html.escape(sample[0].name)}">⬇️ Klatka</a>
</div>
<script>window.CAM_DAY={day_data};</script>
"""
        return self._layout("Burst", body, active="/burst")

    def _nav(self, active: str) -> str:
        token = self.app_config.server.auth_token
        items = [
            ("/", "Kamera"),
            ("/live", "Live"),
            ("/history", "Historia"),
            ("/compare", "Porównaj"),
            ("/burst", "Burst"),
            ("/metrics", "Dane"),
            ("/checklista-tatry.html", "Tatry"),
        ]
        if self.app_config.server.admin_enabled:
            items.append(("/admin", "Shell"))
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
  <button id="themeBtn" class="icon-btn" type="button" aria-label="Zmień motyw">🌗</button>
</div></header>
<main class="wrap">{body}</main>
<footer class="foot">Plants · kamera Raspberry Pi · <a href="{href('/api/status', token)}">status</a></footer>
<div id="lightbox" class="lightbox" aria-hidden="true">
  <button id="lbClose" class="lb-close" type="button" data-close aria-label="Zamknij">✕</button>
  <button id="lbPrev" class="lb-btn lb-prev" type="button" aria-label="Poprzednie">‹</button>
  <img id="lbImg" alt="Podgląd pełnoekranowy">
  <button id="lbNext" class="lb-btn lb-next" type="button" aria-label="Następne">›</button>
  <div id="lbHint" class="lb-hint">← → klawisze · Esc zamyka</div>
</div>
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
<div id="sysStrip" class="sysstrip"></div>
<div id="metaStrip" class="sysstrip"></div>
<div class="actions">
  <button class="btn btn-accent" data-capture type="button">📸 Zrób zdjęcie</button>
  <a class="btn btn-primary" href="{href('/live', token)}">🔴 Podgląd na żywo</a>
  <a class="btn" href="{href('/history', token)}">🗂️ Historia{days_label}</a>
  <button id="downloadBtn" class="btn" type="button">⬇️ Pobierz</button>
</div>
<div class="ctrlrow">
  <label class="switch"><input type="checkbox" id="autoChk"> Auto-odświeżanie</label>
  <select id="autoSel" class="mini" aria-label="Częstotliwość odświeżania">
    <option value="5000">co 5 s</option>
    <option value="15000">co 15 s</option>
    <option value="30000">co 30 s</option>
    <option value="60000">co 60 s</option>
  </select>
  <span class="sub">· kliknij zdjęcie, by powiększyć</span>
</div>
<div class="card pad" style="margin-top:.9rem">
  <div class="ctrlrow" style="margin:0">
    <strong style="color:var(--ink)">⚡ Szybkie zdjęcia</strong>
    <label class="switch">jakość
      <select id="burstRes" class="mini" aria-label="Rozdzielczość">
        <option value="0x0">pełna</option>
        <option value="1280x720" selected>1280×720</option>
        <option value="854x480">854×480</option>
        <option value="640x360">640×360 (najszybciej)</option>
      </select>
    </label>
    <label class="switch">co
      <select id="burstInt" class="mini" aria-label="Odstęp">
        <option value="0">jak najszybciej</option>
        <option value="1">1 s</option>
        <option value="2">2 s</option>
        <option value="5">5 s</option>
      </select>
    </label>
    <label class="switch">przez
      <select id="burstDur" class="mini" aria-label="Czas trwania">
        <option value="30">30 s</option>
        <option value="120" selected>2 min</option>
        <option value="300">5 min</option>
        <option value="600">10 min</option>
      </select>
    </label>
    <button id="burstBtn" class="btn btn-accent" type="button">▶ Start</button>
    <span id="burstStatus" class="sub"></span>
  </div>
</div>
"""
        return self._layout("Kamera", body, active="/")

    def _live_html(self, query: str) -> str:
        token = self.app_config.server.auth_token
        token_js = json.dumps(token)
        body = f"""
<div class="card hero-card">
  <div class="live-frame"><img id="liveImg" alt="Podgląd na żywo"><div id="roiOverlay"></div><div id="roiRect"></div></div>
  <div class="hero-bar">
    <span id="liveStatus" class="badge"><span class="live-dot"></span>Na żywo</span>
    <span id="liveFps" class="badge">… fps</span>
    <span id="liveZoom" class="badge"></span>
    <span class="spacer"></span>
    <a class="btn" href="{href('/', token)}">← Wróć</a>
  </div>
</div>
<div class="ctrlrow">
  <button id="livePause" class="btn" type="button">⏸ Pauza</button>
  <button id="liveReset" class="btn" type="button">🔍 Reset zoom</button>
  <label class="switch">Płynność
    <select id="liveRate" class="mini" aria-label="Płynność podglądu">
      <option value="500">~2 fps (oszczędnie)</option>
      <option value="200" selected>~5 fps</option>
      <option value="100">~10 fps (płynnie)</option>
      <option value="0">maks (ile łącze da)</option>
    </select>
  </label>
  <a class="btn" href="{href('/live.mjpg', token)}">Tryb MJPEG</a>
  <span class="spacer"></span>
  <button id="diagBtn" class="btn" type="button">🩺 Diagnostyka</button>
</div>
<p class="note">Podgląd pobiera klatki pojedynczo i sam dopasowuje tempo do łącza. <b>Zaznacz prostokąt na obrazie, aby przybliżyć</b> (sprzętowy zoom = pełna ostrość sensora na tym wycinku, bez wzrostu transferu); zaznaczaj dalej, by przybliżać głębiej, „Reset zoom" wraca do pełnego kadru. „Diagnostyka" zbiera pełny zrzut do skopiowania.</p>
<div id="diagPanel" class="card pad" style="display:none">
  <div class="ctrlrow" style="margin:0 0 .5rem">
    <strong style="color:var(--ink)">Diagnostyka</strong>
    <button id="diagRefresh" class="btn" type="button">↻ Odśwież</button>
    <button id="diagCopy" class="btn" type="button">⧉ Kopiuj</button>
  </div>
  <pre id="diagOut" class="out"></pre>
</div>
<script>window.CAM_TOKEN={token_js};</script>
<script>{LIVE_JS}</script>
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
        movie_block = (
            '<div class="card pad" id="movieCard">'
            '<div class="ctrlrow" style="margin:0">'
            '<b>🎬 Film wzrostu</b>'
            '<span class="sub">wszystkie dni, z datą/temp./zielenią wypaloną w kadrze</span>'
            '<span class="spacer"></span>'
            '<button id="mvBuild" class="btn btn-primary" type="button">▶ Zbuduj film</button>'
            '<a id="mvDl" class="btn" style="display:none" download="growth.mp4">⬇️ MP4</a>'
            '<span id="mvStat" class="sub"></span></div>'
            '<video id="mvVid" class="viewer" controls preload="metadata" playsinline '
            'style="display:none;margin-top:.6rem"></video>'
            '</div>'
        )
        body = (
            f'<h1 class="h">Historia</h1>'
            f'<p class="sub">{len(days)} dni z zapisanymi klatkami.</p>'
            f'{movie_block}'
            f'<div class="grid-days">{"".join(cards)}</div>'
            f'<script>{MOVIE_JS}</script>'
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
                f'<a class="thumb{active}" href="{select_url}" data-name="{html.escape(image_path.name)}">'
                f'<img src="{url}" alt="{label}" loading="lazy"><span>{label}</span></a>'
            )

        day_data = json.dumps({
            "day": day,
            "base": "/history/" + quote(day) + "/",
            "index": selected_index,
            "frames": [{"n": p.name, "l": p.stem.replace("-", ":")} for p in images],
        })

        video_path = self.storage.history_dir / day / TIMELAPSE_NAME
        video_url = href(f"/history/{quote(day)}/{quote(TIMELAPSE_NAME)}", token)
        if video_path.exists():
            video_block = (
                f'<div class="card hero-card">'
                f'<video class="viewer" controls preload="metadata" playsinline poster="{selected_url}">'
                f'<source src="{video_url}" type="video/mp4"></video>'
                f'<div class="hero-bar"><span class="badge">🎞️ Timelapse</span><span class="spacer"></span>'
                f'<a class="btn" href="{video_url}" download="{html.escape(day)}-timelapse.mp4">⬇️ MP4</a>'
                f'<button class="btn" id="buildTl" type="button">↻ Odśwież</button></div></div>'
            )
        else:
            video_block = (
                '<div class="card pad"><p class="sub" style="margin:0">Brak timelapse dla tego dnia — '
                'odtwarzanie poniżej składa pełne klatki (wolniej przez sieć). '
                '<button class="btn btn-primary" id="buildTl" type="button">▶ Zbuduj timelapse</button></p></div>'
            )

        day_h = html.escape(day)
        body = f"""
<h1 class="h">{day_h}</h1>
<p class="sub" id="counter">{selected_label} · {selected_index + 1}/{len(images)}</p>
{video_block}
<div id="metaChart" class="card pad" style="display:none"></div>
<h2 class="h" style="font-size:1rem;margin-top:1.3rem">Klatki</h2>
<div class="card hero-card"><img id="viewer" class="viewer" src="{selected_url}" alt="{selected_label}"></div>
<div class="scrubber">
  <input id="scrub" type="range" min="0" max="{len(images) - 1}" value="{selected_index}" aria-label="Przewijaj klatki">
</div>
<div class="player">
  <button class="btn btn-primary" id="playBtn" type="button">▶ Odtwórz</button>
  <select id="speedSel" class="mini" aria-label="Prędkość">
    <option value="600">wolno</option>
    <option value="300" selected>normalnie</option>
    <option value="120">szybko</option>
  </select>
  <span class="spacer"></span>
  <a class="btn" id="dlDay" href="{selected_url}" download="{html.escape(selected_path.name)}">⬇️ Pobierz</a>
</div>
<form class="controls" method="get" action="/history/{quote(day)}">
  <input type="hidden" name="token" value="{html.escape(token)}">
  <label class="field">Klatka
    <select id="frameSel" name="at">{options}</select>
  </label>
  <label class="field">Przed/po (miniatury)
    <input name="around" type="number" min="1" max="12" value="{around}">
  </label>
  <button class="btn" type="submit">Pokaż więcej</button>
</form>
<div class="navrow">{prev_link}{next_link}</div>
<div class="thumbs" id="thumbs">{''.join(items)}</div>
<script>window.CAM_DAY={day_data};</script>
"""
        return self._layout(day, body, active="/history")

    def _admin_page(self, query: str) -> str:
        if not self._admin_enabled():
            body = (
                '<h1 class="h">Shell</h1>'
                '<div class="card pad"><p class="danger-note">Panel jest wyłączony. '
                'Ustaw <code>admin_enabled = true</code> w sekcji <code>[server]</code> pliku '
                '<code>/etc/camera-remote/config.ini</code> i zrestartuj usługę '
                '<code>camera-remote.service</code>.</p></div>'
            )
            return self._layout("Shell", body, active="/admin")
        token_js = json.dumps(self.app_config.server.auth_token)
        body = f"""
<h1 class="h">Shell — terminal</h1>
<p class="danger-note">⚠️ Pełny, interaktywny terminal (PTY) na Pi jako użytkownik usługi. Autoryzacja tym samym tokenem co reszta strony.</p>
<link rel="stylesheet" href="/vendor/xterm.css"/>
<script src="/vendor/xterm.js"></script>
<script src="/vendor/xterm-addon-fit.js"></script>
<script src="/vendor/xterm-addon-web-links.js"></script>
<div class="term-wrap"><div id="term"></div></div>
<div class="term-bar"><span class="sub">Sesja jest trwała (PTY); obsługuje sudo, debconf i długie procesy. Linki (np. logowania Tailscale) są klikalne — stuknij, by otworzyć. Wygasa po ~15 min bezczynności.</span></div>
<script>window.CAM_TOKEN={token_js};</script>
<script>{SHELL_JS}</script>
"""
        return self._layout("Shell", body, active="/admin")


class CameraServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, server_address, config: AppConfig):
        super().__init__(server_address, CameraRequestHandler)
        self.app_config = config
        self.storage = SnapshotStorage(config)
        self.storage.ensure_dirs()
        self.repo_static_dir = Path(__file__).resolve().parents[1] / "static"
        self.vendor_dir = self.repo_static_dir / "vendor"
        self.static_dir = config.paths.data_dir / "static"
        self.static_dir.mkdir(parents=True, exist_ok=True)
        self.tatry_pages = [
            self.repo_static_dir / "checklista-tatry.html",
            self.static_dir / "checklista-tatry.html",
        ]
        self.live = LiveSession(config)
        self.shell = ShellManager()
        self.burst = BurstController(config)
        self.timelapse_lock = threading.Lock()
        self.timelapse_building: set = set()
        self.burst_building: set = set()
        self.canopy_backfill = {"running": False, "done": 0, "total": 0}
        self.movie_lock = threading.Lock()
        self.movie_building = False

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
