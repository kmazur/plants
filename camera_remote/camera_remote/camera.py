from __future__ import annotations

import io
import logging
import time
from pathlib import Path
from typing import Optional, Tuple

from .config import CameraConfig

log = logging.getLogger(__name__)


def _load_camera_modules():
    from picamera2 import Picamera2
    import libcamera

    return Picamera2, libcamera


def _load_tuning(Picamera2, tuning_file: str):
    if not tuning_file:
        return None
    path = Path(tuning_file)
    if not path.exists():
        log.warning("tuning file does not exist: %s", tuning_file)
        return None
    try:
        return Picamera2.load_tuning_file(str(path))
    except Exception as exc:
        log.warning("failed to load tuning file %s: %s", tuning_file, exc)
        return None


def _new_picam(config: CameraConfig):
    Picamera2, _ = _load_camera_modules()
    tuning = _load_tuning(Picamera2, config.tuning_file)
    if tuning is not None:
        try:
            return Picamera2(tuning=tuning)
        except TypeError:
            log.warning("this Picamera2 version does not accept tuning=; using defaults")
    return Picamera2()


def _transform(config: CameraConfig):
    _, libcamera = _load_camera_modules()
    return libcamera.Transform(hflip=config.hflip, vflip=config.vflip)


def capture_jpeg_file(output_path: Path, config: CameraConfig, size: Optional[Tuple[int, int]] = None) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    width, height = size or (config.snapshot_width, config.snapshot_height)
    tmp_path = output_path.with_suffix(output_path.suffix + ".tmp")

    picam = _new_picam(config)
    try:
        still_config = picam.create_still_configuration(
            main={"size": (width, height)},
            transform=_transform(config),
        )
        picam.configure(still_config)
        picam.start()
        time.sleep(config.warmup_seconds)
        picam.capture_file(str(tmp_path), format="jpeg")
        tmp_path.replace(output_path)
    finally:
        try:
            picam.stop()
        except Exception:
            pass
        try:
            picam.close()
        except Exception:
            pass
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)


class LiveCamera:
    def __init__(self, config: CameraConfig):
        self.config = config
        self._picam = None
        self._frame_interval = 1.0 / max(1, config.live_fps)

    def start(self) -> None:
        if self._picam is not None:
            return
        picam = _new_picam(self.config)
        video_config = picam.create_video_configuration(
            main={"size": (self.config.live_width, self.config.live_height)},
            transform=_transform(self.config),
        )
        picam.configure(video_config)
        picam.start()
        time.sleep(self.config.warmup_seconds)
        self._picam = picam

    def stop(self) -> None:
        picam = self._picam
        self._picam = None
        if picam is None:
            return
        try:
            picam.stop()
        except Exception:
            pass
        try:
            picam.close()
        except Exception:
            pass

    def capture_jpeg_bytes(self) -> bytes:
        if self._picam is None:
            raise RuntimeError("live camera is not started")
        buf = io.BytesIO()
        self._picam.capture_file(buf, format="jpeg")
        time.sleep(self._frame_interval)
        return buf.getvalue()

