"""Per-capture metadata recorded at the same granularity as the snapshots.

Each normal snapshot appends one JSON line to ``history/<day>/metadata.jsonl``
with CPU temperature, frame brightness, file size, a brief system snapshot,
camera exposure metadata, and (cached) outdoor weather for the Pi's location.
"""
from __future__ import annotations

import json
import logging
import os
import shutil
import time
import urllib.request
from datetime import datetime
from pathlib import Path

log = logging.getLogger(__name__)

METADATA_NAME = "metadata.jsonl"
WEATHER_CACHE = "weather_cache.json"
WEATHER_TTL = 600  # seconds

# Picamera2 metadata key -> our short name
_CAM_KEYS = {
    "ExposureTime": "exposure_us",
    "AnalogueGain": "gain",
    "DigitalGain": "digital_gain",
    "Lux": "lux",
    "ColourTemperature": "colour_temp",
    "FrameDuration": "frame_us",
}


def cpu_temp_c():
    try:
        raw = Path("/sys/class/thermal/thermal_zone0/temp").read_text().strip()
        return round(int(raw) / 1000.0, 1)
    except Exception:
        return None


def brightness(path) -> "float | None":
    """Mean luma 0-255 (downsampled). Needs Pillow; returns None if unavailable."""
    try:
        from PIL import Image
        with Image.open(path) as im:
            gray = im.convert("L")
            gray.thumbnail((128, 128))
            pixels = list(gray.getdata())
        return round(sum(pixels) / len(pixels), 1) if pixels else None
    except Exception as exc:
        log.debug("brightness failed: %s", exc)
        return None


def system_brief(data_dir) -> dict:
    out = {}
    try:
        out["load1"] = round(os.getloadavg()[0], 2)
    except Exception:
        pass
    try:
        info = {}
        for line in Path("/proc/meminfo").read_text().splitlines():
            key, _, value = line.partition(":")
            info[key.strip()] = value.strip()
        total = int(info["MemTotal"].split()[0])
        avail = int((info.get("MemAvailable") or "0 kB").split()[0])
        if total:
            out["mem_used_pct"] = round(100 * (total - avail) / total, 1)
    except Exception:
        pass
    try:
        usage = shutil.disk_usage(str(data_dir))
        out["disk_used_pct"] = round(100 * usage.used / usage.total, 1)
    except Exception:
        pass
    return out


def camera_brief(meta) -> dict:
    out = {}
    if not meta:
        return out
    for key, name in _CAM_KEYS.items():
        value = meta.get(key)
        if value is None:
            continue
        out[name] = round(value, 1) if isinstance(value, float) else value
    return out


def outdoor(latitude, longitude, cache_path, ttl: int = WEATHER_TTL) -> dict:
    cache_path = Path(cache_path)
    now = time.time()
    stale = None
    try:
        cached = json.loads(cache_path.read_text(encoding="utf-8"))
        if now - cached.get("ts", 0) < ttl:
            return cached.get("data") or {}
        stale = cached.get("data")
    except Exception:
        pass
    try:
        url = (
            f"https://api.open-meteo.com/v1/forecast?latitude={latitude}&longitude={longitude}"
            "&current=temperature_2m,relative_humidity_2m,wind_speed_10m,weather_code&timezone=auto"
        )
        with urllib.request.urlopen(url, timeout=8) as resp:
            current = (json.loads(resp.read().decode("utf-8")).get("current") or {})
        data = {
            "temp_c": current.get("temperature_2m"),
            "humidity": current.get("relative_humidity_2m"),
            "wind": current.get("wind_speed_10m"),
            "code": current.get("weather_code"),
        }
        try:
            cache_path.write_text(json.dumps({"ts": now, "data": data}), encoding="utf-8")
        except Exception:
            pass
        return data
    except Exception as exc:
        log.debug("outdoor weather failed: %s", exc)
        return stale or {}


def build_record(now: datetime, file_name: str, file_path, data_dir, location, cam_meta) -> dict:
    record = {"ts": now.isoformat(timespec="seconds"), "file": file_name}
    temp = cpu_temp_c()
    if temp is not None:
        record["cpu_temp_c"] = temp
    bright = brightness(file_path)
    if bright is not None:
        record["brightness"] = bright
    try:
        record["size"] = Path(file_path).stat().st_size
    except Exception:
        pass
    record.update(system_brief(data_dir))
    cam = camera_brief(cam_meta)
    if cam:
        record["cam"] = cam
    if location is not None and getattr(location, "weather", False):
        od = outdoor(location.latitude, location.longitude, Path(data_dir) / WEATHER_CACHE)
        if od and any(v is not None for v in od.values()):
            record["outdoor"] = od
    return record


def append(day_dir, record: dict) -> None:
    try:
        with open(Path(day_dir) / METADATA_NAME, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")
    except Exception as exc:
        log.warning("metadata append failed: %s", exc)


def read_day(day_dir) -> list:
    path = Path(day_dir) / METADATA_NAME
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except Exception:
            pass
    return out
