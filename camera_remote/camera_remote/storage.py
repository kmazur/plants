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
        self.movies_dir = self.data_dir / "movies"
        self.thumbs_dir = self.data_dir / "thumbs"
        self.latest_path = self.data_dir / "latest.jpg"
        self.latest_meta_path = self.data_dir / "latest.json"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        from .metricsdb import MetricsDB
        self.metrics = MetricsDB(self.data_dir / "metrics.db")
        try:
            self.metrics.import_jsonl_once(self.history_dir)
        except Exception as exc:
            log.warning("metrics jsonl import failed: %s", exc)

    def ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.history_dir.mkdir(parents=True, exist_ok=True)
        self.burst_dir.mkdir(parents=True, exist_ok=True)
        self.movies_dir.mkdir(parents=True, exist_ok=True)
        self.thumbs_dir.mkdir(parents=True, exist_ok=True)

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
                    shutil.rmtree(self.thumbs_dir / "history" / day_dir.name, ignore_errors=True)
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

        cam_meta = {}
        try:
            with CameraLock(self.config.paths.lock_file, blocking=blocking_lock):
                last_error = None
                for attempt in range(1, self.config.camera.retry_count + 1):
                    try:
                        cam_meta = capture_jpeg_file(file_path, self.config.camera) or {}
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

        # Per-capture metadata time series (SQLite).
        try:
            from . import metadata as md
            record = md.build_record(now, file_path.name, file_path, self.data_dir,
                                     getattr(self.config, "location", None), cam_meta,
                                     canopy_roi=self.canopy_roi())
            self.metrics.insert(record)
            self.record_zones(file_path, int(now.timestamp()), now.strftime("%Y-%m-%d"))
            md.check_reboot(self.metrics, now)
        except Exception as exc:
            log.warning("metadata record failed: %s", exc)

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

    def thumb_for(self, src: Path, key: str, width: int = 400) -> Path:
        """Return a cached small JPEG for ``src`` (generating it on first use).
        ``key`` is the cache-relative path, e.g. ``history/<day>/<file>``."""
        dst = self.thumbs_dir / key
        try:
            if dst.exists() and dst.stat().st_mtime >= src.stat().st_mtime:
                return dst
        except OSError:
            pass
        dst.parent.mkdir(parents=True, exist_ok=True)
        from PIL import Image
        with Image.open(src) as im:
            im = im.convert("RGB")
            im.thumbnail((width, width))
            tmp = dst.with_suffix(".jpg.tmp")
            im.save(tmp, "JPEG", quality=80)
            tmp.replace(dst)
        return dst

    def canopy_roi(self):
        """Normalized (x, y, w, h) plant region for canopy measurement, or None
        for the whole frame. Stored in the shared metrics DB so the capture and
        web processes agree."""
        try:
            raw = self.metrics.kv_get("canopy_roi")
            if not raw:
                return None
            v = json.loads(raw)
            if isinstance(v, list) and len(v) == 4:
                return tuple(float(x) for x in v)
        except Exception:
            pass
        return None

    def set_canopy_roi(self, roi) -> None:
        if roi is None:
            self.metrics.kv_set("canopy_roi", "")
        else:
            self.metrics.kv_set("canopy_roi", json.dumps([round(float(x), 4) for x in roi]))

    def zones(self) -> list:
        """Named measurement zones: [{name, x, y, w, h}, ...] (normalized)."""
        try:
            raw = self.metrics.kv_get("canopy_zones")
            v = json.loads(raw) if raw else []
            return v if isinstance(v, list) else []
        except Exception:
            return []

    def set_zones(self, zones) -> None:
        clean = []
        for z in (zones or [])[:8]:
            try:
                clean.append({"name": str(z["name"])[:24],
                              "x": round(float(z["x"]), 4), "y": round(float(z["y"]), 4),
                              "w": round(float(z["w"]), 4), "h": round(float(z["h"]), 4)})
            except (KeyError, TypeError, ValueError):
                continue
        self.metrics.kv_set("canopy_zones", json.dumps(clean))
        # Zone definitions changed -> drop cached series so backfill recomputes.
        self.metrics.clear_zones()

    def _zone_canopy(self, img, zones) -> dict:
        from . import metadata as md
        return {z["name"]: md.canopy_pct(img, (z["x"], z["y"], z["w"], z["h"])) for z in zones}

    def record_zones(self, file_path, ts: int, day: str) -> None:
        zones = self.zones()
        if zones:
            self.metrics.insert_zones(ts, day, self._zone_canopy(file_path, zones))

    def backfill_zones(self, limit: int = 20000, progress=None) -> int:
        zones = self.zones()
        if not zones:
            return 0
        done = 0
        for row in self.metrics.rows_missing_zones(limit):
            img = self.history_dir / (row.get("day") or "") / (row.get("file") or "")
            if not img.exists():
                continue
            self.metrics.insert_zones(row["ts"], row.get("day") or "", self._zone_canopy(img, zones))
            done += 1
            if progress and done % 20 == 0:
                try:
                    progress(done)
                except Exception:
                    pass
        if progress:
            try:
                progress(done)
            except Exception:
                pass
        return done

    def backfill_image_metrics(self, limit: int = 20000, progress=None) -> int:
        """Compute canopy_pct and sharpness for rows that lack them, reading each
        history image once. Returns rows updated. ``progress`` is optional."""
        from . import metadata as md
        roi = self.canopy_roi()
        done = 0
        for row in self.metrics.rows_missing_image_metrics(limit):
            img = self.history_dir / (row.get("day") or "") / (row.get("file") or "")
            if not img.exists():
                continue
            canopy = md.canopy_pct(img, roi) if row.get("canopy_pct") is None else None
            sharp = md.sharpness(img) if row.get("sharpness") is None else None
            if canopy is not None or sharp is not None:
                self.metrics.update_image_metrics(row["ts"], canopy, sharp)
                done += 1
                if progress and done % 20 == 0:
                    try:
                        progress(done)
                    except Exception:
                        pass
        if progress:
            try:
                progress(done)
            except Exception:
                pass
        return done

    def mask_for(self, src: Path, key: str, roi=None, width: int = 720) -> Path:
        """Cached overlay that tints the pixels counted as vegetation (and draws
        the measurement ROI). ``key`` already encodes the ROI so it re-renders
        when the region changes."""
        dst = self.thumbs_dir / "mask" / key
        try:
            if dst.exists() and dst.stat().st_mtime >= src.stat().st_mtime:
                return dst
        except OSError:
            pass
        dst.parent.mkdir(parents=True, exist_ok=True)
        from PIL import Image, ImageDraw
        import numpy as np
        with Image.open(src) as im:
            im = im.convert("RGB")
            if im.width > width:
                im = im.resize((width, max(1, round(im.height * width / im.width))))
        arr = np.asarray(im, dtype="float32")
        r = arr[..., 0]; g = arr[..., 1]; b = arr[..., 2]
        s = r + g + b + 1e-6
        mask = (2.0 * g - r - b) / s > 0.12
        h, w = mask.shape
        if roi:
            x, y, rw, rh = roi
            x0 = max(0, int(x * w)); y0 = max(0, int(y * h))
            x1 = min(w, int((x + rw) * w)); y1 = min(h, int((y + rh) * h))
            keep = np.zeros_like(mask)
            keep[y0:y1, x0:x1] = True
            mask = mask & keep
        out = arr.copy()
        out[mask] = out[mask] * 0.30 + np.array([60.0, 235.0, 90.0]) * 0.70
        img = Image.fromarray(out.clip(0, 255).astype("uint8"))
        if roi:
            d = ImageDraw.Draw(img)
            d.rectangle([roi[0] * w, roi[1] * h, (roi[0] + roi[2]) * w, (roi[1] + roi[3]) * h],
                        outline=(255, 180, 60), width=3)
        tmp = dst.with_suffix(".jpg.tmp")
        img.save(tmp, "JPEG", quality=82)
        tmp.replace(dst)
        return dst
