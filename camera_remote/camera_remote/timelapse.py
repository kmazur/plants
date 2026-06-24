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
import time
from datetime import date, timedelta
from pathlib import Path
from typing import List, Optional, Tuple

log = logging.getLogger(__name__)

TIMELAPSE_NAME = "timelapse.mp4"
DEFAULT_FPS = 24
DEFAULT_WIDTH = 1280

_FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]

# Preferred encoders, best first. Hardware h264_v4l2m2m is cheap thermally on a
# Pi; libx264 is the portable software fallback; mpeg4 is a last resort.
_ENCODERS: List[Tuple[str, List[str]]] = [
    ("h264_v4l2m2m", ["-c:v", "h264_v4l2m2m", "-b:v", "4M"]),
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


def build_dir(
    frames_dir,
    out_path,
    *,
    fps: int = DEFAULT_FPS,
    width: int = DEFAULT_WIDTH,
    force: bool = False,
    timeout: int = 1800,
    progress=None,
) -> Optional[Path]:
    """Encode all ``*.jpg`` in ``frames_dir`` into the H.264 file ``out_path``.
    Returns the path, None when there are no frames, raises on ffmpeg errors.
    ``progress`` is an optional callable(stage:str, current:int, total:int) used
    to report live encode progress."""
    frames_dir = Path(frames_dir)
    out_path = Path(out_path)
    frames = sorted(frames_dir.glob("*.jpg"))
    if not frames:
        return None
    if not force and _is_up_to_date(out_path, frames):
        return out_path
    if not have_ffmpeg():
        raise RuntimeError("ffmpeg is not installed")

    name, enc_args = pick_encoder(_available_encoders())
    tmp = out_path.with_suffix(out_path.suffix + ".tmp.mp4")
    total = len(frames)
    cmd = [
        "ffmpeg", "-hide_banner", "-nostdin", "-y",
        "-framerate", str(fps),
        "-pattern_type", "glob", "-i", str(frames_dir / "*.jpg"),
        "-vf", f"scale={width}:-2:flags=bicubic",
        "-pix_fmt", "yuv420p",
        *enc_args,
        "-r", str(fps),
        "-movflags", "+faststart",
        "-progress", "pipe:1", "-nostats",
        str(tmp),
    ]
    log.info("building timelapse %s with %s (%d frames)", out_path, name, total)
    if progress:
        progress("Kodowanie", 0, total)
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    deadline = time.monotonic() + timeout
    try:
        for line in proc.stdout:  # ffmpeg -progress emits key=value lines
            if progress and line.startswith("frame="):
                try:
                    progress("Kodowanie", min(int(line.split("=", 1)[1]), total), total)
                except ValueError:
                    pass
            if time.monotonic() > deadline:
                proc.kill()
                tmp.unlink(missing_ok=True)
                raise RuntimeError(f"ffmpeg timed out after {timeout}s\ncommand: {' '.join(cmd)}")
        stderr = proc.stderr.read()
        rc = proc.wait()
    finally:
        proc.stdout.close()
        proc.stderr.close()
    if rc != 0:
        tmp.unlink(missing_ok=True)
        raise RuntimeError(
            f"ffmpeg exited {rc}\nencoder: {name}\n"
            f"frames: {total} in {frames_dir}\ncommand: {' '.join(cmd)}\n"
            f"--- stderr ---\n{stderr[-4000:]}")
    if progress:
        progress("Kodowanie", total, total)
    os.replace(tmp, out_path)
    log.info("wrote %s (%d bytes)", out_path, out_path.stat().st_size)
    return out_path


def _font(size: int):
    from PIL import ImageFont
    for path in _FONT_CANDIDATES:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    return ImageFont.load_default()


def _annotate(src: Path, dst: Path, text: str, width: int) -> None:
    """Render ``src`` scaled to ``width`` with a caption bar at the bottom."""
    from PIL import Image, ImageDraw
    text = text or ""
    with Image.open(src) as raw:
        im = raw.convert("RGBA")
    if im.width != width:
        im = im.resize((width, max(1, round(im.height * width / im.width))))
    size = max(14, width // 48)
    font = _font(size)
    pad = max(4, size // 3)
    draw = ImageDraw.Draw(im)
    try:
        box = draw.textbbox((0, 0), text or " ", font=font)
        tw, th = box[2] - box[0], box[3] - box[1]
        oy = box[1]
    except Exception:
        tw, th, oy = len(text) * size // 2, size, 0
    bar = th + 2 * pad
    overlay = Image.new("RGBA", im.size, (0, 0, 0, 0))
    ImageDraw.Draw(overlay).rectangle(
        [0, im.height - bar, im.width, im.height], fill=(0, 0, 0, 140))
    im = Image.alpha_composite(im, overlay)
    ImageDraw.Draw(im).text((pad, im.height - bar + pad - oy), text, fill=(255, 255, 255), font=font)
    im.convert("RGB").save(dst, "JPEG", quality=88)


def gather_frames(data_dir, start_day: str, end_day: str) -> List[Path]:
    """All history JPEGs between ``start_day`` and ``end_day`` (inclusive), in
    chronological order across day directories."""
    history = Path(data_dir) / "history"
    if not history.is_dir():
        return []
    frames: List[Path] = []
    for d in sorted(p.name for p in history.iterdir() if p.is_dir()):
        if start_day <= d <= end_day:
            frames.extend(sorted((history / d).glob("*.jpg")))
    return frames


def build_movie(
    frames: List[Path],
    out_path,
    *,
    fps: int = DEFAULT_FPS,
    width: int = DEFAULT_WIDTH,
    caption=None,
    max_frames: int = 0,
    force: bool = False,
    timeout: int = 3600,
    progress=None,
) -> Optional[Path]:
    """Encode an arbitrary ordered list of frames into ``out_path``. When
    ``caption`` (a callable frame_path -> str) is given, each frame is
    re-rendered with a burned-in caption first. ``max_frames`` downsamples
    evenly so long ranges stay quick to build and small to download.
    ``progress`` is an optional callable(stage, current, total) reporting the
    render and encode phases."""
    import tempfile
    frames = [Path(f) for f in frames if Path(f).exists()]
    if not frames:
        return None
    if max_frames and len(frames) > max_frames:
        step = (len(frames) + max_frames - 1) // max_frames
        frames = frames[::step]
    if not have_ffmpeg():
        raise RuntimeError("ffmpeg is not installed")
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_dir = Path(tempfile.mkdtemp(prefix="movie_"))
    total = len(frames)
    try:
        for i, f in enumerate(frames):
            dst = tmp_dir / f"{i:06d}.jpg"
            if caption is not None:
                try:
                    _annotate(f, dst, caption(f), width)
                    if progress:
                        progress("Renderowanie napisow", i + 1, total)
                    continue
                except Exception as exc:
                    log.debug("annotate failed for %s: %s", f, exc)
            try:
                os.symlink(f.resolve(), dst)
            except Exception:
                shutil.copyfile(f, dst)
            if progress:
                progress("Renderowanie napisow", i + 1, total)
        return build_dir(tmp_dir, out_path, fps=fps, width=width, force=True,
                         timeout=timeout, progress=progress)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def build_day(
    data_dir,
    day: str,
    *,
    fps: int = DEFAULT_FPS,
    width: int = DEFAULT_WIDTH,
    force: bool = False,
    timeout: int = 1800,
) -> Optional[Path]:
    """Build ``history/<day>/timelapse.mp4``."""
    day_dir = Path(data_dir) / "history" / day
    if not day_dir.is_dir():
        return None
    return build_dir(day_dir, day_dir / TIMELAPSE_NAME, fps=fps, width=width, force=force, timeout=timeout)


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
