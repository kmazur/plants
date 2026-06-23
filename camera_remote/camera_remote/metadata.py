"""Collect per-capture metadata. Persistence is handled by MetricsDB (SQLite);
this module only gathers the values into a nested record dict."""
from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import time
import urllib.request
from datetime import datetime
from pathlib import Path

log = logging.getLogger(__name__)

WEATHER_CACHE = "weather_cache.json"
WEATHER_TTL = 600  # seconds

_CAM_KEYS = {
    "ExposureTime": "exposure_us",
    "AnalogueGain": "gain",
    "Lux": "lux",
    "ColourTemperature": "colour_temp",
}


def cpu_temp_c():
    try:
        raw = Path("/sys/class/thermal/thermal_zone0/temp").read_text().strip()
        return round(int(raw) / 1000.0, 1)
    except Exception:
        return None


def cpu_freq_mhz():
    try:
        raw = Path("/sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq").read_text().strip()
        return round(int(raw) / 1000)
    except Exception:
        return None


def throttled():
    """Raspberry Pi throttling/undervoltage flags (vcgencmd get_throttled)."""
    try:
        out = subprocess.run(["vcgencmd", "get_throttled"], capture_output=True, text=True, timeout=4).stdout
        return int(out.strip().split("=", 1)[1], 16)
    except Exception:
        return None


def uptime_s():
    try:
        return int(float(Path("/proc/uptime").read_text().split()[0]))
    except Exception:
        return None


def brightness(path):
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


def clip_pct(path):
    """Percentage of blown-out highlight pixels (luma >= 250). A high value in
    daylight means the scene exceeds the sensor's dynamic range (e.g. bright sky
    over shaded plants) and is a good trigger for an HDR exposure bracket."""
    try:
        from PIL import Image
        with Image.open(path) as im:
            gray = im.convert("L")
            gray.thumbnail((160, 160))
            pixels = list(gray.getdata())
        if not pixels:
            return None
        hi = sum(1 for p in pixels if p >= 250)
        return round(100.0 * hi / len(pixels), 2)
    except Exception as exc:
        log.debug("clip_pct failed: %s", exc)
        return None


def canopy_pct(path, roi=None):
    """Fraction of the frame (0..100) covered by green vegetation, using the
    Excess-Green index ExG = (2G - R - B) / (R + G + B). ``roi`` is an optional
    normalized (x, y, w, h) rectangle to measure only the plant region."""
    try:
        from PIL import Image
        import numpy as np
        with Image.open(path) as im:
            im = im.convert("RGB")
            im.thumbnail((160, 160))
            arr = np.asarray(im, dtype="float32")
        if roi:
            h, w = arr.shape[0], arr.shape[1]
            x, y, rw, rh = roi
            x0 = max(0, int(x * w)); y0 = max(0, int(y * h))
            x1 = min(w, int((x + rw) * w)); y1 = min(h, int((y + rh) * h))
            if x1 > x0 and y1 > y0:
                arr = arr[y0:y1, x0:x1]
        r = arr[..., 0]; g = arr[..., 1]; b = arr[..., 2]
        s = r + g + b + 1e-6
        exg = (2.0 * g - r - b) / s
        veg = exg > 0.12
        return round(100.0 * float(veg.mean()), 1)
    except Exception as exc:
        log.debug("canopy failed: %s", exc)
        return None


def sharpness(path, roi=None):
    """Focus/sharpness score = variance of the Laplacian over a grayscale
    thumbnail. Higher means crisper; useful to pick the best frame of a day."""
    try:
        from PIL import Image
        import numpy as np
        with Image.open(path) as im:
            g = im.convert("L")
            g.thumbnail((240, 240))
            arr = np.asarray(g, dtype="float32")
        if roi:
            h, w = arr.shape
            x, y, rw, rh = roi
            x0 = max(0, int(x * w)); y0 = max(0, int(y * h))
            x1 = min(w, int((x + rw) * w)); y1 = min(h, int((y + rh) * h))
            if x1 - x0 > 4 and y1 - y0 > 4:
                arr = arr[y0:y1, x0:x1]
        lap = (-4.0 * arr[1:-1, 1:-1] + arr[:-2, 1:-1] + arr[2:, 1:-1]
               + arr[1:-1, :-2] + arr[1:-1, 2:])
        return round(float(lap.var()), 1)
    except Exception as exc:
        log.debug("sharpness failed: %s", exc)
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
    u = uptime_s()
    if u is not None:
        out["uptime_s"] = u
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
    """Current weather + today's sunrise/sunset (Open-Meteo, file-cached)."""
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
            "&current=temperature_2m,relative_humidity_2m,wind_speed_10m,weather_code,"
            "cloud_cover,precipitation,is_day"
            "&daily=sunrise,sunset&forecast_days=1&timezone=auto"
        )
        with urllib.request.urlopen(url, timeout=8) as resp:
            j = json.loads(resp.read().decode("utf-8"))
        cur = j.get("current") or {}
        daily = j.get("daily") or {}
        data = {
            "temp_c": cur.get("temperature_2m"),
            "humidity": cur.get("relative_humidity_2m"),
            "wind": cur.get("wind_speed_10m"),
            "cloud": cur.get("cloud_cover"),
            "precip": cur.get("precipitation"),
            "code": cur.get("weather_code"),
            "is_day": cur.get("is_day"),
            "sunrise": (daily.get("sunrise") or [None])[0],
            "sunset": (daily.get("sunset") or [None])[0],
        }
        try:
            cache_path.write_text(json.dumps({"ts": now, "data": data}), encoding="utf-8")
        except Exception:
            pass
        return data
    except Exception as exc:
        log.debug("outdoor weather failed: %s", exc)
        return stale or {}


def build_record(now: datetime, file_name: str, file_path, data_dir, location, cam_meta,
                 canopy_roi=None) -> dict:
    record = {"ts": now.isoformat(timespec="seconds"), "file": file_name}
    for key, fn in (("cpu_temp_c", cpu_temp_c), ("cpu_freq_mhz", cpu_freq_mhz), ("throttled", throttled)):
        val = fn()
        if val is not None:
            record[key] = val
    bright = brightness(file_path)
    if bright is not None:
        record["brightness"] = bright
    cap = canopy_pct(file_path, canopy_roi)
    if cap is not None:
        record["canopy_pct"] = cap
    sh = sharpness(file_path)
    if sh is not None:
        record["sharpness"] = sh
    clip = clip_pct(file_path)
    if clip is not None:
        record["clip_hi"] = clip
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
        if od:
            for key in ("is_day", "sunrise", "sunset"):
                if od.get(key) is not None:
                    record[key] = od.pop(key)
                else:
                    od.pop(key, None)
            if any(v is not None for v in od.values()):
                record["outdoor"] = od
    return record


def check_reboot(db, now: datetime) -> None:
    """Record a 'reboot' event when the kernel boot id changes."""
    try:
        boot_id = Path("/proc/sys/kernel/random/boot_id").read_text().strip()
    except Exception:
        return
    try:
        prev = db.kv_get("boot_id")
        if prev and prev != boot_id:
            db.add_event(int(now.timestamp()), "reboot", "boot_id changed")
            log.info("reboot detected")
        if prev != boot_id:
            db.kv_set("boot_id", boot_id)
    except Exception as exc:
        log.debug("reboot check failed: %s", exc)
