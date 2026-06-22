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


def capture_jpeg_file(output_path: Path, config: CameraConfig, size: Optional[Tuple[int, int]] = None,
                      controls: Optional[dict] = None, warmup: Optional[float] = None,
                      image_controls: Optional[dict] = None, quality: Optional[int] = None) -> dict:
    """Capture a full still to ``output_path``. Returns the camera metadata
    (exposure, gain, lux, ...) for that capture, or an empty dict.

    ``controls`` forces exposure/gain (adaptive night mode) and is applied via
    the configuration so it holds from the first frame; ``image_controls``
    (sharpness/contrast/saturation/denoise) is applied best-effort after start;
    ``quality`` sets the JPEG quality; ``warmup`` overrides the settle time."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    width, height = size or (config.snapshot_width, config.snapshot_height)
    tmp_path = output_path.with_suffix(output_path.suffix + ".tmp")

    meta: dict = {}
    picam = _new_picam(config)
    try:
        cfg_kwargs = dict(main={"size": (width, height)}, transform=_transform(config))
        if controls:
            cfg_kwargs["controls"] = dict(controls)
        still_config = picam.create_still_configuration(**cfg_kwargs)
        picam.configure(still_config)
        if quality:
            try:
                picam.options["quality"] = int(quality)
            except Exception as exc:
                log.warning("could not set jpeg quality: %s", exc)
        picam.start()
        if image_controls:
            try:
                picam.set_controls(dict(image_controls))
            except Exception as exc:
                log.warning("could not apply image controls: %s", exc)
        time.sleep(warmup if warmup is not None else config.warmup_seconds)
        picam.capture_file(str(tmp_path), format="jpeg")
        try:
            meta = picam.capture_metadata() or {}
        except Exception:
            meta = {}
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
    return meta


def capture_brackets(config: CameraConfig, exposures, size: Optional[Tuple[int, int]] = None,
                     image_controls: Optional[dict] = None, quality: Optional[int] = None):
    """Capture several exposures from a single camera session (no per-shot
    open/close, which avoids the 'Input/output error' from rapid reopen).
    Returns a list of JPEG byte strings, one per requested exposure (µs)."""
    width, height = size or (config.snapshot_width, config.snapshot_height)
    picam = _new_picam(config)
    out = []
    try:
        still_config = picam.create_still_configuration(
            main={"size": (width, height)}, transform=_transform(config))
        picam.configure(still_config)
        if quality:
            try:
                picam.options["quality"] = int(quality)
            except Exception:
                pass
        picam.start()
        if image_controls:
            try:
                picam.set_controls(dict(image_controls))
            except Exception as exc:
                log.warning("bracket image controls failed: %s", exc)
        for exp in exposures:
            exp = int(exp)
            picam.set_controls({"AeEnable": False, "ExposureTime": exp, "AnalogueGain": 1.0})
            time.sleep(exp / 1_000_000.0 + 0.4)
            buf = io.BytesIO()
            picam.capture_file(buf, format="jpeg")
            out.append(buf.getvalue())
        return out
    finally:
        try:
            picam.stop()
        except Exception:
            pass
        try:
            picam.close()
        except Exception:
            pass


class CaptureSession:
    """Keep one still camera open and capture many frames quickly (no per-shot
    open/configure/warmup), for temporary burst capture."""

    def __init__(self, config: CameraConfig, size: Optional[Tuple[int, int]] = None):
        self.config = config
        self.size = size
        self._picam = None

    def __enter__(self) -> "CaptureSession":
        picam = _new_picam(self.config)
        try:
            if self.size:
                # A scaled video configuration (like the live view) starts
                # reliably at non-native sizes and is fast; full-res uses a
                # still configuration.
                cam_config = picam.create_video_configuration(
                    main={"size": self.size},
                    transform=_transform(self.config),
                )
            else:
                cam_config = picam.create_still_configuration(
                    main={"size": (self.config.snapshot_width, self.config.snapshot_height)},
                    transform=_transform(self.config),
                )
            picam.configure(cam_config)
            if self.size:
                quality = getattr(self.config, "live_quality", 0)
                if quality:
                    try:
                        picam.options["quality"] = int(quality)
                    except Exception:
                        pass
            picam.start()
            time.sleep(self.config.warmup_seconds)
        except Exception:
            try:
                picam.close()
            except Exception:
                pass
            raise
        self._picam = picam
        return self

    def capture_file(self, output_path: Path) -> None:
        if self._picam is None:
            raise RuntimeError("capture session is not started")
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = output_path.with_suffix(output_path.suffix + ".tmp")
        self._picam.capture_file(str(tmp_path), format="jpeg")
        tmp_path.replace(output_path)

    def __exit__(self, *exc) -> None:
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


class LiveCamera:
    def __init__(self, config: CameraConfig):
        self.config = config
        self._picam = None
        self._frame_interval = 1.0 / max(1, config.live_fps)
        self._roi = None  # absolute ROI (nx, ny, nw, nh) in 0..1 of full sensor

    def set_roi(self, roi) -> None:
        """roi = (nx, ny, nw, nh) normalized to the full sensor, or None for full."""
        self._roi = roi
        self._apply_roi()

    def _apply_roi(self) -> None:
        if self._picam is None:
            return
        try:
            full = self._picam.camera_properties.get("ScalerCropMaximum")
            if not full:
                return
            fx, fy, fw, fh = full
            if not self._roi:
                self._picam.set_controls({"ScalerCrop": tuple(full)})
                return
            nx, ny, nw, nh = self._roi
            cw = max(64, int(nw * fw))
            ch = max(64, int(nh * fh))
            cx = int(fx + nx * fw)
            cy = int(fy + ny * fh)
            self._picam.set_controls({"ScalerCrop": (cx, cy, cw, ch)})
        except Exception as exc:
            log.warning("set ScalerCrop failed: %s", exc)

    def start(self) -> None:
        if self._picam is not None:
            return
        picam = _new_picam(self.config)
        try:
            # Raise the auto-exposure ceiling so the preview brightens at night
            # (AE still uses short exposures by day, so daytime fps is unaffected).
            night_max = max(20000, int(getattr(self.config, "live_night_max_us", 500000)))
            video_config = picam.create_video_configuration(
                main={"size": (self.config.live_width, self.config.live_height)},
                transform=_transform(self.config),
                controls={"FrameDurationLimits": (8333, night_max)},
            )
            picam.configure(video_config)
            # Smaller, lighter JPEGs so a constrained Pi/tunnel can keep up.
            quality = getattr(self.config, "live_quality", 0)
            if quality:
                try:
                    picam.options["quality"] = int(quality)
                except Exception as exc:
                    log.warning("could not set live jpeg quality: %s", exc)
            picam.start()
            time.sleep(self.config.warmup_seconds)
        except Exception:
            # Crucial: close the half-open device, otherwise the next
            # Picamera2() fails forever with "__init__ sequence did not
            # complete" until the process restarts.
            try:
                picam.close()
            except Exception:
                pass
            raise
        self._picam = picam
        if self._roi:
            self._apply_roi()

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
        return buf.getvalue()

    @property
    def frame_interval(self) -> float:
        return self._frame_interval

