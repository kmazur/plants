"""Temporary high-rate snapshot capture ("burst" mode).

Keeps one still camera open for the whole burst so frames are written as fast
as the sensor allows, for a bounded duration, at a chosen resolution. Frames
are stored in a dedicated burst session directory (kept separate from the
normal per-minute history). When the burst ends, the normal history is
backfilled for the covered window by borrowing the burst frame closest to each
normal-interval tick, so the regular timeline has no gap.

Runs under the shared camera lock, so it is mutually exclusive with the live
view.
"""
from __future__ import annotations

import logging
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

from .camera import CaptureSession
from .config import AppConfig
from .locking import CameraBusy, CameraLock
from .timelapse import TIMELAPSE_NAME, build_dir, have_ffmpeg

log = logging.getLogger(__name__)

MAX_DURATION = 1800  # hard cap so a burst can never run away
TIMELAPSE_ERROR = "timelapse.error.txt"


def build_session_timelapse(session_dir, width: int = 1280, fps: int = 30):
    """Build a burst session's timelapse, persisting the full error on failure
    so the viewer can show exactly what ffmpeg did. Returns (ok, error)."""
    session_dir = Path(session_dir)
    err_file = session_dir / TIMELAPSE_ERROR
    try:
        if not have_ffmpeg():
            raise RuntimeError("ffmpeg not installed (which ffmpeg found nothing)")
        out = build_dir(session_dir, session_dir / TIMELAPSE_NAME, fps=fps, width=width, force=True)
        if out is None:
            raise RuntimeError(f"no *.jpg frames found in {session_dir}")
        try:
            err_file.unlink()
        except FileNotFoundError:
            pass
        return True, ""
    except Exception as exc:
        detail = f"{datetime.now().isoformat()}\n{exc}"
        try:
            err_file.write_text(detail, encoding="utf-8")
        except Exception:
            pass
        log.warning("burst timelapse build failed for %s: %s", session_dir, exc)
        return False, str(exc)


class BurstController:
    def __init__(self, config: AppConfig):
        self.config = config
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = None
        self.active = False
        self.count = 0
        self.interval = 0.0
        self.until = 0.0
        self.resolution = ""
        self.backfilled = 0
        self.session = ""
        self.video = False
        self.error = ""

    def status(self) -> dict:
        with self._lock:
            remaining = max(0.0, self.until - time.monotonic()) if self.active else 0.0
            return {
                "active": self.active,
                "count": self.count,
                "interval": self.interval,
                "resolution": self.resolution,
                "remaining": round(remaining),
                "backfilled": self.backfilled,
                "session": self.session,
                "video": self.video,
                "error": self.error,
            }

    def start(self, storage, interval: float, duration: float,
              width: int = 0, height: int = 0) -> dict:
        interval = max(0.0, float(interval))
        duration = max(1.0, min(float(duration), MAX_DURATION))
        size: Optional[Tuple[int, int]] = (int(width), int(height)) if width and height else None
        with self._lock:
            if self.active:
                self.until = time.monotonic() + duration
                self.interval = interval
                return {"ok": True, "updated": True}
            self._stop.clear()
            self.active = True
            self.count = 0
            self.backfilled = 0
            self.session = ""
            self.video = False
            self.error = ""
            self.interval = interval
            self.until = time.monotonic() + duration
            self.resolution = (f"{size[0]}x{size[1]}" if size else "pełna")
            self._thread = threading.Thread(target=self._run, args=(storage, size), daemon=True)
            self._thread.start()
            return {"ok": True}

    def stop(self) -> dict:
        self._stop.set()
        return {"ok": True}

    def _run(self, storage, size) -> None:
        frames: List[Tuple[datetime, "object"]] = []
        start_dt = datetime.now()
        try:
            with CameraLock(self.config.paths.lock_file, blocking=False):
                session_dir = storage.new_burst_session(start_dt)
                with CaptureSession(self.config.camera, size=size) as cam:
                    log.info("burst started (%s) -> %s", self.resolution, session_dir)
                    while not self._stop.is_set() and time.monotonic() < self.until:
                        t0 = time.monotonic()
                        now = datetime.now()
                        path = storage.burst_frame_path(session_dir, now)
                        cam.capture_file(path)
                        storage.promote_latest(path, now)
                        frames.append((now, path))
                        with self._lock:
                            self.count += 1
                        wait = self.interval - (time.monotonic() - t0)
                        if wait > 0:
                            self._stop.wait(wait)
        except CameraBusy:
            with self._lock:
                self.error = "kamera zajęta (podgląd na żywo?)"
            log.info("burst aborted: camera busy")
        except Exception as exc:
            with self._lock:
                self.error = str(exc)
            log.exception("burst failed: %s", exc)
        finally:
            # Camera lock is released here; backfill + encode need no camera.
            backfilled = 0
            if frames:
                try:
                    backfilled = storage.backfill_history(
                        frames, start_dt, datetime.now(),
                        self.config.snapshot.interval_seconds,
                    )
                except Exception as exc:
                    log.warning("burst backfill failed: %s", exc)
            video_ok = False
            if frames and session_dir is not None:
                width = min(1280, size[0]) if size else 1280
                video_ok, _ = build_session_timelapse(session_dir, width=width)
            try:
                storage.cleanup_old_history()
            except Exception:
                pass
            with self._lock:
                self.active = False
                self.backfilled = backfilled
                self.session = session_dir.name if session_dir is not None else ""
                self.video = video_ok
                count = self.count
            log.info("burst finished (%d frames, backfilled %d, video=%s)", count, backfilled, video_ok)
