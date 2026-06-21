"""Build per-day timelapse MP4s from the snapshot history.

Playback of a day by cycling full-resolution JPEGs over a slow link stutters
(one HTTP request and a full decode per frame). Encoding the day's frames into
a single H.264 file once turns playback into a small, smooth, seekable video.

ffmpeg is detected at runtime; a hardware encoder is preferred when present and
the code degrades gracefully when ffmpeg is missing.
"""
from __future__ import annotations

import argparse
import logging
import os
import shutil
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import List, Optional, Tuple

log = logging.getLogger(__name__)

TIMELAPSE_NAME = "timelapse.mp4"
DEFAULT_FPS = 24
DEFAULT_WIDTH = 1280

# Preferred encoders, best first. Hardware h264_v4l2m2m is cheap thermally on a
# Pi; libx264 is the portable software fallback; mpeg4 is a last resort.
_ENCODERS: List[Tuple[str, List[str]]] = [
    ("h264_v4l2m2m", ["-c:v", "h264_v4l2m2m", "-b:v", "6M"]),
    ("libx264", ["-c:v", "libx264", "-preset", "veryfast", "-crf", "28"]),
    ("mpeg4", ["-c:v", "mpeg4", "-q:v", "5"]),
]


def have_ffmpeg() -> bool:
    return shutil.which("ffmpeg") is not None


def _available_encoders() -> str:
    try:
        return subprocess.run(
            ["ffmpeg", "-hide_banner", "-encoders"],
            capture_output=True, text=True, timeout=20,
        ).stdout
    except Exception as exc:  # pragma: no cover - environment dependent
        log.warning("could not list ffmpeg encoders: %s", exc)
        return ""


def pick_encoder(available_text: str) -> Tuple[str, List[str]]:
    for name, args in _ENCODERS:
        if name in available_text:
            return name, args
    # Nothing matched (odd build); try libx264 and let ffmpeg complain if absent.
    return _ENCODERS[1]


def _is_up_to_date(out: Path, frames: List[Path]) -> bool:
    if not out.exists():
        return False
    newest = max(p.stat().st_mtime for p in frames)
    return out.stat().st_mtime >= newest


def build_day(
    data_dir,
    day: str,
    *,
    fps: int = DEFAULT_FPS,
    width: int = DEFAULT_WIDTH,
    force: bool = False,
    timeout: int = 1800,
) -> Optional[Path]:
    """Build ``history/<day>/timelapse.mp4``. Returns the path, or None when the
    day has no frames. Raises RuntimeError on ffmpeg problems."""
    day_dir = Path(data_dir) / "history" / day
    if not day_dir.is_dir():
        return None
    frames = sorted(day_dir.glob("*.jpg"))
    if not frames:
        return None

    out = day_dir / TIMELAPSE_NAME
    if not force and _is_up_to_date(out, frames):
        return out

    if not have_ffmpeg():
        raise RuntimeError("ffmpeg is not installed")

    name, enc_args = pick_encoder(_available_encoders())
    tmp = day_dir / (TIMELAPSE_NAME + ".tmp.mp4")
    cmd = [
        "ffmpeg", "-hide_banner", "-nostdin", "-y",
        "-framerate", str(fps),
        "-pattern_type", "glob", "-i", str(day_dir / "*.jpg"),
        "-vf", f"scale={width}:-2:flags=bicubic",
        "-pix_fmt", "yuv420p",
        *enc_args,
        "-r", str(fps),
        "-movflags", "+faststart",
        str(tmp),
    ]
    log.info("building timelapse for %s with %s (%d frames)", day, name, len(frames))
    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=timeout)
    except subprocess.CalledProcessError as exc:
        tmp.unlink(missing_ok=True)
        tail = (exc.stderr or b"").decode("utf-8", "replace")[-600:]
        raise RuntimeError(f"ffmpeg failed for {day}: {tail}") from exc
    except subprocess.TimeoutExpired as exc:
        tmp.unlink(missing_ok=True)
        raise RuntimeError(f"ffmpeg timed out for {day}") from exc
    os.replace(tmp, out)
    log.info("wrote %s (%d bytes)", out, out.stat().st_size)
    return out


def _all_days(data_dir) -> List[str]:
    history = Path(data_dir) / "history"
    if not history.is_dir():
        return []
    return sorted(p.name for p in history.iterdir() if p.is_dir())


def build_recent(data_dir, days: int = 3, **kwargs) -> List[Path]:
    built: List[Path] = []
    today = date.today()
    for offset in range(days):
        day = (today - timedelta(days=offset)).strftime("%Y-%m-%d")
        try:
            result = build_day(data_dir, day, **kwargs)
            if result is not None:
                built.append(result)
        except Exception as exc:
            log.warning("timelapse build failed for %s: %s", day, exc)
    return built


def main(argv: Optional[List[str]] = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(description="Build snapshot-history timelapse videos")
    parser.add_argument("--config", default="/etc/camera-remote/config.ini")
    parser.add_argument("--day", help="build a single day (YYYY-MM-DD)")
    parser.add_argument("--recent", type=int, metavar="N", help="build the last N days (default action: 3)")
    parser.add_argument("--all", action="store_true", help="build every day in history")
    parser.add_argument("--fps", type=int, default=DEFAULT_FPS)
    parser.add_argument("--width", type=int, default=DEFAULT_WIDTH)
    parser.add_argument("--force", action="store_true", help="rebuild even if up to date")
    args = parser.parse_args(argv)

    # Local import so the module stays importable without the rest of the stack.
    from .config import load_config

    data_dir = load_config(args.config).paths.data_dir
    opts = dict(fps=args.fps, width=args.width, force=args.force)

    if not have_ffmpeg():
        log.error("ffmpeg not found; cannot build timelapses")
        return 2

    if args.day:
        build_day(data_dir, args.day, **opts)
    elif args.all:
        for day in _all_days(data_dir):
            try:
                build_day(data_dir, day, **opts)
            except Exception as exc:
                log.warning("timelapse build failed for %s: %s", day, exc)
    else:
        build_recent(data_dir, days=args.recent or 3, **opts)
    return 0


if __name__ == "__main__":
    sys.exit(main())
