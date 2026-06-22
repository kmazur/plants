from __future__ import annotations

import bisect
import json
import logging
import shutil
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from .camera import capture_jpeg_file
from .config import AppConfig
from .locking import CameraBusy, CameraLock

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class SnapshotResult:
    path: Path
    latest_path: Path
    timestamp: datetime
    skipped: bool = False
    message: str = ""


class SnapshotStorage:
    def __init__(self, config: AppConfig):
        self.config = config
        self.data_dir = config.paths.data_dir
        self.history_dir = self.data_dir / "history"
        self.burst_dir = self.data_dir / "burst"
        self.latest_path = self.data_dir / "latest.jpg"
        self.latest_meta_path = self.data_dir / "latest.json"

    def ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.history_dir.mkdir(parents=True, exist_ok=True)
        self.burst_dir.mkdir(parents=True, exist_ok=True)

    def date_dirs(self) -> list[Path]:
        if not self.history_dir.exists():
            return []
        return sorted([p for p in self.history_dir.iterdir() if p.is_dir()], reverse=True)

    def images_for_day(self, day: str, newest_first: bool = True) -> list[Path]:
        root = self.history_dir / day
        if not root.exists():
            return []
        return sorted(root.glob("*.jpg"), reverse=newest_first)

    def cleanup_old_history(self) -> None:
        retain_days = self.config.snapshot.retain_days
        if retain_days <= 0:
            return
        cutoff = datetime.now().date() - timedelta(days=retain_days)
        if self.history_dir.exists():
            for day_dir in self.history_dir.iterdir():
                if not day_dir.is_dir():
                    continue
                try:
                    day = datetime.strptime(day_dir.name, "%Y-%m-%d").date()
                except ValueError:
                    continue
                if day < cutoff:
                    log.info("removing old history directory: %s", day_dir)
                    shutil.rmtree(day_dir, ignore_errors=True)
        if self.burst_dir.exists():
            for session_dir in self.burst_dir.iterdir():
                if not session_dir.is_dir():
                    continue
                try:
                    day = datetime.strptime(session_dir.name[:10], "%Y-%m-%d").date()
                except ValueError:
                    continue
                if day < cutoff:
                    log.info("removing old burst session: %s", session_dir)
                    shutil.rmtree(session_dir, ignore_errors=True)

    def capture_once(self, blocking: bool = True) -> SnapshotResult:
        self.ensure_dirs()
        now = datetime.now()
        day_dir = self.history_dir / now.strftime("%Y-%m-%d")
        file_path = day_dir / f"{now.strftime('%H-%M-%S')}.jpg"
        blocking_lock = blocking or not self.config.snapshot.skip_when_camera_busy

        try:
            with CameraLock(self.config.paths.lock_file, blocking=blocking_lock):
                last_error = None
                for attempt in range(1, self.config.camera.retry_count + 1):
                    try:
                        capture_jpeg_file(file_path, self.config.camera)
                        break
                    except Exception as exc:
                        last_error = exc
                        log.warning("snapshot attempt %s failed: %s", attempt, exc)
                        if attempt < self.config.camera.retry_count:
                            time.sleep(self.config.camera.retry_delay_seconds)
                else:
                    raise RuntimeError(f"snapshot failed after retries: {last_error}")
        except CameraBusy:
            return SnapshotResult(file_path, self.latest_path, now, skipped=True, message="camera busy")

        tmp_latest = self.latest_path.with_suffix(".jpg.tmp")
        shutil.copyfile(file_path, tmp_latest)
        tmp_latest.replace(self.latest_path)

        meta = {
            "timestamp": now.isoformat(timespec="seconds"),
            "path": str(file_path),
            "size": file_path.stat().st_size,
        }
        tmp_meta = self.latest_meta_path.with_suffix(".json.tmp")
        tmp_meta.write_text(json.dumps(meta, indent=2), encoding="utf-8")
        tmp_meta.replace(self.latest_meta_path)

        self.cleanup_old_history()
        return SnapshotResult(file_path, self.latest_path, now)

    def burst_sessions(self) -> list[Path]:
        if not self.burst_dir.exists():
            return []
        return sorted([p for p in self.burst_dir.iterdir() if p.is_dir()], reverse=True)

    def burst_frames(self, session: str, newest_first: bool = False) -> list[Path]:
        root = self.burst_dir / session
        if not root.exists():
            return []
        return sorted(root.glob("*.jpg"), reverse=newest_first)

    def new_burst_session(self, now: datetime = None) -> Path:
        """Create and return a dedicated directory for one burst session, kept
        separate from the normal per-minute history."""
        now = now or datetime.now()
        session = self.burst_dir / now.strftime("%Y-%m-%d_%H-%M-%S")
        session.mkdir(parents=True, exist_ok=True)
        return session

    def burst_frame_path(self, session_dir: Path, now: datetime = None) -> Path:
        """Path for one burst frame (millisecond precision) inside its session."""
        now = now or datetime.now()
        name = now.strftime("%H-%M-%S-") + f"{now.microsecond // 1000:03d}"
        return session_dir / f"{name}.jpg"

    def backfill_history(self, frames, start_dt: datetime, end_dt: datetime, interval: int) -> int:
        """Fill the normal per-minute history for the window covered by a burst,
        borrowing the burst frame closest in time to each interval tick. Avoids
        a gap in the normal timeline when the snapshot timer was suppressed.

        ``frames`` is a chronological list of (datetime, Path).
        """
        if not frames or interval <= 0:
            return 0
        times = [f[0] for f in frames]
        count = 0
        tick = start_dt
        while tick <= end_dt:
            idx = bisect.bisect_left(times, tick)
            best = idx
            if idx >= len(times):
                best = len(times) - 1
            elif idx > 0 and abs((times[idx - 1] - tick).total_seconds()) <= abs((times[idx] - tick).total_seconds()):
                best = idx - 1
            src = frames[best][1]
            day_dir = self.history_dir / tick.strftime("%Y-%m-%d")
            day_dir.mkdir(parents=True, exist_ok=True)
            dest = day_dir / (tick.strftime("%H-%M-%S") + ".jpg")
            if not dest.exists() and Path(src).exists():
                shutil.copyfile(src, dest)
                count += 1
            tick += timedelta(seconds=interval)
        return count

    def promote_latest(self, file_path: Path, now: datetime = None) -> None:
        """Copy a freshly captured frame to latest.jpg and update its metadata."""
        now = now or datetime.now()
        tmp_latest = self.latest_path.with_suffix(".jpg.tmp")
        shutil.copyfile(file_path, tmp_latest)
        tmp_latest.replace(self.latest_path)
        meta = {
            "timestamp": now.isoformat(timespec="seconds"),
            "path": str(file_path),
            "size": file_path.stat().st_size,
        }
        tmp_meta = self.latest_meta_path.with_suffix(".json.tmp")
        tmp_meta.write_text(json.dumps(meta, indent=2), encoding="utf-8")
        tmp_meta.replace(self.latest_meta_path)

    def latest_meta(self) -> dict:
        if not self.latest_meta_path.exists():
            return {}
        try:
            return json.loads(self.latest_meta_path.read_text(encoding="utf-8"))
        except Exception:
            return {}
