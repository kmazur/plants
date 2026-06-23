from __future__ import annotations

import bisect
import json
import logging
import re
import shutil
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from .camera import capture_jpeg_file, capture_brackets
from .config import AppConfig
from .locking import CameraBusy, CameraLock

log = logging.getLogger(__name__)

# libcamera draft NoiseReductionMode values
_NR_MODES = {"off": 0, "fast": 1, "high": 2, "minimal": 3}


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
        """Backwards-compatible entry point: full lifecycle maintenance."""
        self.maintain_storage()

    # ------------------------------------------------------------------
    # Storage lifecycle: age data gracefully and reclaim under disk pressure.
    # ------------------------------------------------------------------
    def _disk_pct(self) -> float:
        u = shutil.disk_usage(str(self.data_dir))
        return 100.0 * u.used / u.total

    def disk_status(self) -> dict:
        u = shutil.disk_usage(str(self.data_dir))
        snap = self.config.snapshot
        return {
            "used_pct": round(100.0 * u.used / u.total, 1),
            "free_gb": round(u.free / 1e9, 1),
            "total_gb": round(u.total / 1e9, 1),
            "high_pct": snap.disk_high_pct,
            "low_pct": snap.disk_low_pct,
            "paused": self.capture_paused(),
        }

    def capture_paused(self) -> bool:
        return self.metrics.kv_get("capture_paused") == "1"

    def _history_day_dirs(self, exclude_today: bool = True) -> list:
        today = datetime.now().strftime("%Y-%m-%d")
        out = []
        if self.history_dir.exists():
            for d in sorted(self.history_dir.iterdir()):
                if not d.is_dir():
                    continue
                try:
                    datetime.strptime(d.name, "%Y-%m-%d")
                except ValueError:
                    continue
                if exclude_today and d.name == today:
                    continue
                out.append(d)
        return out  # ascending: oldest first

    def _ensure_timelapse(self, day_dir: Path) -> bool:
        video = day_dir / "timelapse.mp4"
        try:
            from .timelapse import build_day, have_ffmpeg
            if have_ffmpeg():
                build_day(self.data_dir, day_dir.name)
        except Exception as exc:
            log.warning("timelapse build for %s failed: %s", day_dir.name, exc)
        return video.exists()

    def _thin_day(self, day_dir: Path, minutes: int) -> int:
        """Keep one frame per ``minutes`` window for an older day (after building
        its timelapse). Idempotent via a marker file."""
        if (day_dir / ".tier2").exists() or (day_dir / ".tier3").exists():
            return 0
        self._ensure_timelapse(day_dir)
        keep_best = (self.metrics.best_frame(day_dir.name) or {}).get("file")
        window = max(1, minutes) * 60
        seen, removed = set(), 0
        for f in sorted(day_dir.glob("*.jpg")):
            m = re.match(r"(\d{2})-(\d{2})-(\d{2})", f.name)
            if not m:
                continue
            bucket = (int(m[1]) * 3600 + int(m[2]) * 60 + int(m[3])) // window
            if bucket in seen and f.name != keep_best:
                f.unlink(missing_ok=True)
                removed += 1
            else:
                seen.add(bucket)
        (day_dir / ".tier2").write_text("")
        return removed

    def _video_only_day(self, day_dir: Path) -> int:
        """Keep only the day's timelapse + best frame + metrics; drop the rest.
        Never destroys frames unless the video record exists."""
        if (day_dir / ".tier3").exists():
            return 0
        if not self._ensure_timelapse(day_dir):
            return 0  # no video -> keep frames rather than lose the day
        keep_best = (self.metrics.best_frame(day_dir.name) or {}).get("file")
        removed = 0
        for f in sorted(day_dir.glob("*.jpg")):
            if f.name != keep_best:
                f.unlink(missing_ok=True)
                removed += 1
        shutil.rmtree(self.thumbs_dir / "history" / day_dir.name, ignore_errors=True)
        shutil.rmtree(self.thumbs_dir / "mask" / day_dir.name, ignore_errors=True)
        (day_dir / ".tier3").write_text("")
        return removed

    def _downscale_day(self, day_dir: Path, width: int) -> int:
        try:
            from PIL import Image
        except Exception:
            return 0
        n = 0
        for f in sorted(day_dir.glob("*.jpg")):
            try:
                with Image.open(f) as im:
                    if im.width <= width:
                        continue
                    im = im.convert("RGB").resize((width, max(1, round(im.height * width / im.width))))
                tmp = f.with_suffix(".jpg.ds")
                im.save(tmp, "JPEG", quality=85)
                tmp.replace(f)
                n += 1
            except Exception:
                pass
        return n

    def _drop_caches(self) -> int:
        today = datetime.now().strftime("%Y-%m-%d")
        freed = 0
        for base in ("history", "mask", "burst"):
            d = self.thumbs_dir / base
            if d.exists():
                for sub in d.iterdir():
                    if sub.name != today:
                        shutil.rmtree(sub, ignore_errors=True)
                        freed += 1
        return freed

    def _cleanup_burst(self) -> None:
        retain = self.config.snapshot.retain_days
        if retain <= 0 or not self.burst_dir.exists():
            return
        cutoff = datetime.now().date() - timedelta(days=retain)
        for s in self.burst_dir.iterdir():
            if not s.is_dir():
                continue
            try:
                day = datetime.strptime(s.name[:10], "%Y-%m-%d").date()
            except ValueError:
                continue
            if day < cutoff:
                shutil.rmtree(s, ignore_errors=True)

    def _age_history(self) -> None:
        snap = self.config.snapshot
        today = datetime.now().date()
        for d in self._history_day_dirs():
            try:
                age = (today - datetime.strptime(d.name, "%Y-%m-%d").date()).days
            except ValueError:
                continue
            if snap.retain_days > 0 and age > snap.retain_days:
                self._video_only_day(d)
            elif snap.keep_full_days > 0 and age > snap.keep_full_days:
                self._thin_day(d, snap.thin_minutes)

    def _reclaim(self) -> None:
        snap = self.config.snapshot
        if self._disk_pct() < snap.disk_high_pct:
            if self.capture_paused() and self._disk_pct() < snap.disk_low_pct:
                self.metrics.kv_set("capture_paused", "")
                log.info("disk back below %.0f%%, capture resumed", snap.disk_low_pct)
            return
        log.warning("disk %.1f%% >= %.0f%%: reclaiming", self._disk_pct(), snap.disk_high_pct)
        self.metrics.add_event(int(time.time()), "disk_reclaim", f"{self._disk_pct():.0f}% used")
        today = datetime.now().date()

        def done():
            return self._disk_pct() < snap.disk_low_pct

        self._drop_caches()
        if done():
            return
        # video-only oldest -> newest beyond the full-resolution window
        for d in self._history_day_dirs():
            age = (today - datetime.strptime(d.name, "%Y-%m-%d").date()).days
            if age > snap.keep_full_days:
                self._video_only_day(d)
                if done():
                    return
        # downscale remaining frames (recent non-today days)
        for d in self._history_day_dirs():
            self._downscale_day(d, snap.downscale_width)
            if done():
                return
        # delete whole oldest days as a last resort
        for d in self._history_day_dirs():
            shutil.rmtree(d, ignore_errors=True)
            shutil.rmtree(self.thumbs_dir / "history" / d.name, ignore_errors=True)
            if done():
                return
        if self._disk_pct() >= snap.disk_high_pct:
            self.metrics.kv_set("capture_paused", "1")
            self.metrics.add_event(int(time.time()), "capture_paused", "disk full after reclaim")
            log.error("disk still %.1f%% after reclaim; capture paused", self._disk_pct())

    def maintain_storage(self) -> None:
        """Periodic housekeeping: gentle aging + burst retention + pressure
        reclamation. Safe to run from a background thread (only touches days
        other than today, which the capture writer owns)."""
        for fn in (self._age_history, self._cleanup_burst, self._reclaim):
            try:
                fn()
            except Exception as exc:
                log.warning("maintenance step %s failed: %s", fn.__name__, exc)

    def _post_capture_maintenance(self) -> None:
        """Light, fast housekeeping safe to run inside the capture cycle. Heavy
        work (ffmpeg, thinning, reclaim) is left to the background thread; here
        we only trim bursts and apply an emergency pause if the disk is full."""
        try:
            self._cleanup_burst()
        except Exception as exc:
            log.warning("burst cleanup failed: %s", exc)
        try:
            if self._disk_pct() >= self.config.snapshot.disk_high_pct and not self.capture_paused():
                self.metrics.kv_set("capture_paused", "1")
                self.metrics.add_event(int(time.time()), "capture_paused", "disk high (emergency)")
                log.warning("disk %.1f%% high; capture paused, maintenance will reclaim",
                            self._disk_pct())
        except Exception as exc:
            log.warning("disk pressure check failed: %s", exc)

    def capture_once(self, blocking: bool = True) -> SnapshotResult:
        self.ensure_dirs()
        now = datetime.now()
        day_dir = self.history_dir / now.strftime("%Y-%m-%d")
        file_path = day_dir / f"{now.strftime('%H-%M-%S')}.jpg"
        blocking_lock = blocking or not self.config.snapshot.skip_when_camera_busy

        if self.capture_paused():
            return SnapshotResult(file_path, self.latest_path, now, skipped=True,
                                  message="capture paused (disk full)")

        night = self._is_night()
        controls, warmup, night_exp = self._night_controls() if night else (None, None, None)

        cam_meta = {}
        try:
            with CameraLock(self.config.paths.lock_file, blocking=blocking_lock):
                last_error = None
                for attempt in range(1, self.config.camera.retry_count + 1):
                    try:
                        cam_meta = capture_jpeg_file(
                            file_path, self.config.camera, controls=controls, warmup=warmup,
                            image_controls=self._image_controls(),
                            quality=self.config.camera.jpeg_quality) or {}
                        break
                    except Exception as exc:
                        last_error = exc
                        log.warning("snapshot attempt %s failed: %s", attempt, exc)
                        if attempt < self.config.camera.retry_count:
                            time.sleep(self.config.camera.retry_delay_seconds)
                else:
                    raise RuntimeError(f"snapshot failed after retries: {last_error}")
                # Daytime black-frame guard: auto-exposure occasionally misses at
                # dawn/dusk and produces a near-black frame while the scene is
                # actually bright. Recapture once so it doesn't poison the
                # brightness graph and the timelapse.
                if not night:
                    try:
                        from . import metadata as md
                        b = md.brightness(file_path)
                        lux = float(cam_meta.get("Lux") or 0)
                        if (b is not None and b < self.config.camera.black_frame_floor
                                and lux > 200):
                            log.info("daytime black frame (b=%.0f, lux=%.0f); recapturing", b, lux)
                            cam_meta = capture_jpeg_file(
                                file_path, self.config.camera, controls=controls, warmup=warmup,
                                image_controls=self._image_controls(),
                                quality=self.config.camera.jpeg_quality) or cam_meta
                    except Exception as exc:
                        log.warning("black-frame guard failed: %s", exc)
        except CameraBusy:
            return SnapshotResult(file_path, self.latest_path, now, skipped=True, message="camera busy")
        if night and night_exp:
            self.metrics.kv_set("night_exp", str(night_exp))
        self._maybe_lock_wb(cam_meta)

        # Metrics come from the RAW frame, before any cosmetic post-processing,
        # so canopy/brightness/sharpness stay comparable and the night exposure
        # loop sees the true brightness.
        pp = night and bool(getattr(self.config.camera, "night_postprocess", True))
        try:
            from . import metadata as md
            record = md.build_record(now, file_path.name, file_path, self.data_dir,
                                     getattr(self.config, "location", None), cam_meta,
                                     canopy_roi=self.canopy_roi())
            if night:
                record["night"] = 1
                record["night_mode"] = self.night_mode()
            if pp:
                record["pp"] = 1
            self.metrics.insert(record)
            self.record_zones(file_path, int(now.timestamp()), now.strftime("%Y-%m-%d"))
            md.check_reboot(self.metrics, now)
        except Exception as exc:
            log.warning("metadata record failed: %s", exc)

        # Cosmetic enhancement of dark night frames (auto-contrast + denoise).
        if pp:
            try:
                self._postprocess_night(file_path)
            except Exception as exc:
                log.warning("night post-process failed: %s", exc)

        # latest.jpg reflects the final (possibly enhanced) frame.
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

        self._post_capture_maintenance()
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

    # ---- image quality pipeline ----
    def _image_controls(self) -> dict:
        cam = self.config.camera
        ctrl = {}
        for name, val in (("Sharpness", cam.img_sharpness), ("Contrast", cam.img_contrast),
                          ("Saturation", cam.img_saturation)):
            if val is not None:
                ctrl[name] = float(val)
        nr = _NR_MODES.get((cam.denoise or "").lower())
        if nr is not None:
            ctrl["NoiseReductionMode"] = nr
        gains = self.wb_gains()
        if gains:
            ctrl["ColourGains"] = (float(gains[0]), float(gains[1]))  # disables AWB
        return ctrl

    def image_status(self) -> dict:
        cam = self.config.camera
        return {
            "jpeg_quality": cam.jpeg_quality,
            "resolution": [cam.snapshot_width, cam.snapshot_height],
            "sharpness": cam.img_sharpness,
            "contrast": cam.img_contrast,
            "saturation": cam.img_saturation,
            "denoise": cam.denoise,
            "night_postprocess": bool(getattr(cam, "night_postprocess", True)),
            "wb": self.wb_status(),
        }

    # ---- white-balance lock (flicker-free colour for timelapse) ----
    def wb_gains(self):
        try:
            raw = self.metrics.kv_get("colour_gains")
            if not raw:
                return None
            v = json.loads(raw)
            if isinstance(v, list) and len(v) == 2:
                return (float(v[0]), float(v[1]))
        except Exception:
            pass
        return None

    def set_wb(self, mode: str) -> None:
        if mode == "lock":
            self.metrics.kv_set("awb_lock", "1")
            self.metrics.kv_set("awb_pending", "1")
            self.metrics.kv_set("colour_gains", "")  # re-measure on next frame
        else:  # auto
            self.metrics.kv_set("awb_lock", "")
            self.metrics.kv_set("awb_pending", "")
            self.metrics.kv_set("colour_gains", "")

    def wb_status(self) -> dict:
        locked = self.metrics.kv_get("awb_lock") == "1"
        gains = self.wb_gains()
        return {
            "mode": "locked" if locked else "auto",
            "pending": locked and not gains,
            "gains": list(gains) if gains else None,
        }

    def _maybe_lock_wb(self, cam_meta: dict) -> None:
        """When a WB lock is requested, capture the auto AWB gains from this
        (still auto) frame once, then reuse them for subsequent captures."""
        if self.metrics.kv_get("awb_lock") != "1":
            return
        if self.wb_gains():
            return
        g = (cam_meta or {}).get("ColourGains")
        if g and len(g) == 2:
            self.metrics.kv_set("colour_gains", json.dumps([round(float(g[0]), 3), round(float(g[1]), 3)]))
            self.metrics.kv_set("awb_pending", "")
            log.info("white balance locked at gains %.3f/%.3f", g[0], g[1])

    def _postprocess_night(self, path: Path) -> None:
        """Auto-contrast + mild denoise for dark night frames. Re-encodes once;
        applied only to night frames so daytime quality/metrics are untouched."""
        from PIL import Image, ImageOps, ImageFilter
        with Image.open(path) as im:
            im = im.convert("RGB")
            im = ImageOps.autocontrast(im, cutoff=1)
            im = im.filter(ImageFilter.MedianFilter(size=3))
            tmp = path.with_suffix(".jpg.pp.tmp")
            im.save(tmp, "JPEG", quality=int(getattr(self.config.camera, "jpeg_quality", 92)))
            tmp.replace(path)

    def capture_hdr(self, ev_step: float = 2.0, fuse_width: int = 2028):
        """Capture a 3-shot exposure bracket and merge via exposure fusion
        (more detail in shadows and highlights). Saves to data_dir/hdr and
        returns the path."""
        import io
        import numpy as np
        from PIL import Image
        self.ensure_dirs()
        out_dir = self.data_dir / "hdr"
        out_dir.mkdir(parents=True, exist_ok=True)
        now = datetime.now()
        last = self.metrics.latest() or {}
        base = int((last.get("cam") or {}).get("exposure_us") or 10000)
        base = max(200, min(base, 1_000_000))
        factor = 2.0 ** ev_step
        exposures = [max(60, int(base / factor)), base, min(4_000_000, int(base * factor))]
        image_controls = self._image_controls()
        jpegs = None
        with CameraLock(self.config.paths.lock_file, blocking=True):
            last_error = None
            for attempt in range(1, self.config.camera.retry_count + 1):
                try:
                    jpegs = capture_brackets(self.config.camera, exposures,
                                             image_controls=image_controls, quality=95)
                    break
                except Exception as exc:
                    last_error = exc
                    log.warning("hdr bracket attempt %s failed: %s", attempt, exc)
                    if attempt < self.config.camera.retry_count:
                        time.sleep(self.config.camera.retry_delay_seconds)
            else:
                raise RuntimeError(f"hdr bracket failed after retries: {last_error}")
        arrs, size = [], None
        for data in jpegs:
            with Image.open(io.BytesIO(data)) as im:
                im = im.convert("RGB")
                if im.width > fuse_width:
                    im = im.resize((fuse_width, max(1, round(im.height * fuse_width / im.width))))
                if size is None:
                    size = im.size
                elif im.size != size:
                    im = im.resize(size)
                arrs.append(np.asarray(im, dtype="float32") / 255.0)
        eps = 1e-6
        weights = []
        for a in arrs:
            we = np.exp(-((a - 0.5) ** 2) / (2 * 0.2 * 0.2)).prod(axis=2)   # well-exposedness
            gray = a.mean(axis=2)
            gy, gx = np.gradient(gray)
            contrast = np.abs(gy) + np.abs(gx)
            sat = a.std(axis=2)
            weights.append(we * (1.0 + contrast) * (1.0 + sat) + eps)
        W = np.stack(weights, axis=0)
        W /= W.sum(axis=0, keepdims=True)
        out = np.zeros_like(arrs[0])
        for i, a in enumerate(arrs):
            out += W[i][..., None] * a
        out_path = out_dir / (now.strftime("%Y-%m-%d_%H-%M-%S") + ".jpg")
        Image.fromarray((out.clip(0, 1) * 255).astype("uint8")).save(out_path, "JPEG", quality=95)
        return out_path

    # ---- adaptive night mode ----
    def night_mode(self) -> str:
        """Effective mode: a runtime override (DB) wins over the config default."""
        kv = self.metrics.kv_get("night_mode")
        if kv in ("auto", "on", "off"):
            return kv
        m = getattr(self.config.camera, "night_mode", "auto")
        return m if m in ("auto", "on", "off") else "auto"

    def set_night_mode(self, mode: str) -> None:
        self.metrics.kv_set("night_mode", mode if mode in ("auto", "on", "off") else "auto")

    def _is_night(self) -> bool:
        mode = self.night_mode()
        if mode == "on":
            return True
        if mode == "off":
            return False
        last = self.metrics.latest() or {}
        is_day = last.get("is_day")
        if is_day is not None:
            return int(is_day) == 0
        b = last.get("brightness")
        return b is not None and b < self.config.camera.night_brightness_threshold

    def _night_controls(self):
        """Closed-loop exposure: nudge the previous night exposure toward a
        target brightness so successive frames converge and track the darkness.
        Returns (controls, warmup_seconds, exposure_us)."""
        cam = self.config.camera
        try:
            base = int(self.metrics.kv_get("night_exp") or 0)
        except (TypeError, ValueError):
            base = 0
        last = self.metrics.latest() or {}
        last_bright = last.get("brightness")
        was_day = last.get("is_day") == 1
        if base < 2000:
            exp = min(cam.night_max_exposure_us, 300_000)  # 0.3 s seed
        elif was_day or not last_bright:
            exp = base  # re-entering night: seed from last night's exposure
        else:
            factor = cam.night_target_brightness / max(1.0, float(last_bright))
            factor = max(0.5, min(factor, 2.5))  # damp swings
            exp = int(base * factor)
        exp = max(2000, min(int(exp), cam.night_max_exposure_us))
        controls = {"AeEnable": False, "ExposureTime": exp, "AnalogueGain": cam.night_max_gain}
        warmup = exp / 1_000_000.0 + max(cam.warmup_seconds, 0.4)
        return controls, warmup, exp

    def night_status(self) -> dict:
        last = self.metrics.latest() or {}
        try:
            night_exp = int(self.metrics.kv_get("night_exp") or 0)
        except (TypeError, ValueError):
            night_exp = 0
        return {
            "mode": self.night_mode(),
            "is_night": self._is_night(),
            "night_exp_us": night_exp,
            "last_exposure_us": (last.get("cam") or {}).get("exposure_us"),
            "last_brightness": last.get("brightness"),
            "max_exposure_us": self.config.camera.night_max_exposure_us,
            "max_gain": self.config.camera.night_max_gain,
        }

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
