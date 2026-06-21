from __future__ import annotations

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
        self.latest_path = self.data_dir / "latest.jpg"
        self.latest_meta_path = self.data_dir / "latest.json"

    def ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.history_dir.mkdir(parents=True, exist_ok=True)

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
        if retain_days <= 0 or not self.history_dir.exists():
            return
        cutoff = datetime.now().date() - timedelta(days=retain_days)
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

    def latest_meta(self) -> dict:
        if not self.latest_meta_path.exists():
            return {}
        try:
            return json.loads(self.latest_meta_path.read_text(encoding="utf-8"))
        except Exception:
            return {}
