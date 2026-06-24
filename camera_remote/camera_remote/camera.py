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


def _wait_for_ae(picam, timeout: float) -> bool:
    """Block (up to ``timeout`` seconds) until the auto-exposure loop reports
    AeLocked. ``capture_metadata`` waits for each new frame, so this naturally
    paces at the sensor frame rate and gives AGC/AEC time to converge before a
    still is taken. Returns True if AE locked, False on timeout."""
    deadline = time.monotonic() + max(0.0, timeout)
    while time.monotonic() < deadline:
        try:
            md = picam.capture_metadata() or {}
        except Exception:
            return False
        if md.get("AeLocked"):
            return True
    return False


def _apply_pinned_exposure(picam, et: int, ag: float, settle_frames: int = 6,
                           timeout: float = 2.0) -> None:
    """Lock AE at the converged exposure/gain, then wait until the sensor has
    actually applied it before the caller takes the still.

    picamera2 control changes reach the sensor a few frames later. A still
    grabbed right after pinning can therefore still carry the previous
    (mid-convergence, darker) integration time even though ``capture_metadata``
    already reports the new value -- which shows up as frame-to-frame brightness
    flicker at dawn/dusk where the pre-pin exposure differs a lot from the
    target. Drain frames until the reported exposure matches the pin on two
    consecutive frames (bounded by ``settle_frames`` / ``timeout``)."""
    try:
        picam.set_controls({"AeEnable": False, "ExposureTime": int(et),
                            "AnalogueGain": float(ag)})
    except Exception as exc:
        log.debug("could not pin AE exposure: %s", exc)
        return
    tol = max(50, int(int(et) * 0.04))
    deadline = time.monotonic() + max(0.0, timeout)
    matched = 0
    for _ in range(max(2, settle_frames)):
        if time.monotonic() >= deadline:
            break
        try:
            cur = (picam.capture_metadata() or {}).get("ExposureTime")
        except Exception:
            break
        if cur and abs(int(cur) - int(et)) <= tol:
            matched += 1
            if matched >= 2:
                return
        else:
            matched = 0


def _stack_frames(gain: float, exp_us: float, config: CameraConfig) -> int:
    """How many frames to average for this capture. Noise scales ~1/sqrt(N) and
    sensor noise grows with analogue gain, so we stack roughly proportionally to
    gain (frames ~= gain): none in bright day (gain 1), heavy at night (gain 16).
    This is driven by gain rather than time-of-day so it ramps smoothly at
    dawn/dusk and never stacks a clean daylight frame (avoiding wind ghosting).
    Bounded by a wall-clock budget so long night exposures don't run away."""
    maxf = int(getattr(config, "stack_max_frames", 1))
    thr = float(getattr(config, "stack_gain_threshold", 2.0))
    budget = float(getattr(config, "stack_max_seconds", 8.0))
    if maxf <= 1 or gain <= thr:
        return 1
    n = min(maxf, max(2, int(round(gain))))
    frame_time = exp_us / 1_000_000.0 + 0.15
    if frame_time > 0:
        n = min(n, max(1, int(budget / frame_time)))
    return max(1, n)


def _capture_stacked(picam, tmp_path: Path, frames: int, quality: int, config: CameraConfig) -> None:
    """Capture ``frames`` consecutive stills from the open camera and average
    them to cut noise. Averaging happens in the decoded RGB domain (same proven
    path as the exposure-fusion code), which sidesteps libcamera array colour-
    order quirks. A mild unsharp mask after denoising recovers crisp edges."""
    import numpy as np
    from PIL import Image, ImageFilter

    acc = None
    for _ in range(frames):
        buf = io.BytesIO()
        picam.capture_file(buf, format="jpeg")
        buf.seek(0)
        with Image.open(buf) as im:
            a = np.asarray(im.convert("RGB"), dtype="float32")
        acc = a if acc is None else acc + a
    acc /= frames
    out = Image.fromarray(np.clip(acc, 0, 255).astype("uint8"))
    if getattr(config, "stack_unsharp", True):
        out = out.filter(ImageFilter.UnsharpMask(radius=1.5, percent=80, threshold=2))
    out.save(str(tmp_path), "JPEG", quality=int(quality))


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
        settle = warmup if warmup is not None else config.warmup_seconds
        time.sleep(settle)
        # With a forced exposure (night mode) the frame is deterministic after
        # the settle. In auto mode the AGC/AEC needs several frames to converge,
        # especially at dawn/dusk when light changes fast; capturing too early
        # yields near-black frames. Wait for AE to lock (bounded) before the shot.
        forced_exp = bool(controls and "ExposureTime" in controls)
        if not forced_exp:
            _wait_for_ae(picam, getattr(config, "ae_settle_timeout", 2.5))
        try:
            md = picam.capture_metadata() or {}
        except Exception:
            md = {}
        if not forced_exp:
            # Pin the AE-converged exposure/gain before the shot. picamera2 may
            # otherwise return metadata from a different frame than the captured
            # still, and the still can be grabbed mid-adjustment -> frame-to-frame
            # brightness jitter even when the reported exposure barely moves.
            et, ag = md.get("ExposureTime"), md.get("AnalogueGain")
            if et and ag:
                _apply_pinned_exposure(picam, int(et), float(ag))
                # Re-read so the recorded metadata matches the applied frame.
                try:
                    md = picam.capture_metadata() or md
                except Exception:
                    pass
        # Gain-adaptive multi-frame stacking: average several frames when the
        # gain is high (night) to suppress noise. The scene is static, so this
        # is safe; bright daylight (gain ~1) stays a single frame.
        gain = float(md.get("AnalogueGain") or (controls or {}).get("AnalogueGain") or 1.0)
        exp_us = float(md.get("ExposureTime") or (controls or {}).get("ExposureTime") or 10000)
        frames = _stack_frames(gain, exp_us, config)
        if frames > 1:
            log.info("stacking %d frames (gain=%.1f, exp=%dus)", frames, gain, int(exp_us))
            _capture_stacked(picam, tmp_path, frames, quality or config.jpeg_quality, config)
        else:
            picam.capture_file(str(tmp_path), format="jpeg")
        try:
            meta = picam.capture_metadata() or md or {}
        except Exception:
            meta = md or {}
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
            # The output stream has a fixed aspect ratio; libcamera scales the
            # ScalerCrop region to fill it. A crop of a different aspect ratio is
            # therefore stretched. Expand the drawn box to the output aspect
            # (centered on the selection), so the zoom keeps the correct shape.
            target = self.config.live_width / max(1, self.config.live_height)
            bw = nw * fw
            bh = nh * fh
            bcx = fx + (nx + nw / 2.0) * fw
            bcy = fy + (ny + nh / 2.0) * fh
            if bw / max(1.0, bh) > target:
                bh = bw / target
            else:
                bw = bh * target
            if bw > fw:
                bw, bh = fw, fw / target
            if bh > fh:
                bw, bh = fh * target, fh
            cw = max(64, int(round(bw)))
            ch = max(64, int(round(bh)))
            cx = max(fx, min(int(round(bcx - cw / 2.0)), fx + fw - cw))
            cy = max(fy, min(int(round(bcy - ch / 2.0)), fy + fh - ch))
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

