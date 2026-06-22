"""Temporary high-rate snapshot capture ("burst" mode).

Keeps one still camera open for the whole burst so frames are written to the
history as fast as the sensor allows, for a bounded duration. Runs under the
shared camera lock, so it is mutually exclusive with the live view.
"""
from __future__ import annotations

import logging
import threading
import time
from datetime import datetime

from .camera import CaptureSession
from .config import AppConfig
from .locking import CameraBusy, CameraLock

log = logging.getLogger(__name__)

MAX_DURATION = 1800  # hard cap so a burst can never run away


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
        self.started_at = 0.0
        self.error = ""

    def status(self) -> dict:
        with self._lock:
            remaining = max(0.0, self.until - time.monotonic()) if self.active else 0.0
            return {
                "active": self.active,
                "count": self.count,
                "interval": self.interval,
                "remaining": round(remaining),
                "error": self.error,
            }

    def start(self, storage, interval: float, duration: float) -> dict:
        interval = max(0.0, float(interval))
        duration = max(1.0, min(float(duration), MAX_DURATION))
        with self._lock:
            if self.active:
                # extend / retune a running burst
                self.until = time.monotonic() + duration
                self.interval = interval
                return {"ok": True, "updated": True}
            self._stop.clear()
            self.active = True
            self.count = 0
            self.error = ""
            self.interval = interval
            self.until = time.monotonic() + duration
            self.started_at = time.time()
            self._thread = threading.Thread(target=self._run, args=(storage,), daemon=True)
            self._thread.start()
            return {"ok": True}

    def stop(self) -> dict:
        self._stop.set()
        return {"ok": True}

    def _run(self, storage) -> None:
        try:
            with CameraLock(self.config.paths.lock_file, blocking=False):
                with CaptureSession(self.config.camera) as cam:
                    log.info("burst started")
                    while not self._stop.is_set() and time.monotonic() < self.until:
                        t0 = time.monotonic()
                        now = datetime.now()
                        path = storage.burst_path(now)
                        cam.capture_file(path)
                        storage.promote_latest(path, now)
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
            try:
                storage.cleanup_old_history()
            except Exception:
                pass
            with self._lock:
                self.active = False
                count = self.count
            log.info("burst finished (%d frames)", count)
