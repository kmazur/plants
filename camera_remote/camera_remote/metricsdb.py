"""SQLite-backed metrics store (replaces the metadata.jsonl text files).

One row per capture in ``metadata`` and discrete ``events`` (reboots, etc.).
WAL mode + busy_timeout so the separate snapshot process and the web process
can read/write concurrently. The API reconstructs the nested record shape the
frontend already expects.
"""
from __future__ import annotations

import json
import logging
import sqlite3
import time
from datetime import datetime
from pathlib import Path

log = logging.getLogger(__name__)

_COLUMNS = [
    "ts", "day", "file",
    "cpu_temp", "cpu_freq_mhz", "throttled",
    "brightness", "canopy_pct", "sharpness", "size",
    "load1", "mem_used_pct", "disk_used_pct", "uptime_s",
    "exposure_us", "gain", "lux", "colour_temp",
    "out_temp", "out_humidity", "out_wind", "out_cloud", "out_precip", "out_code",
    "is_day", "sunrise", "sunset", "night", "night_mode", "pp", "clip_hi",
]

# Columns exposed to the time-of-day heatmap / "average day" view.
HOURLY_METRICS = {
    "brightness": "brightness", "canopy_pct": "canopy_pct", "sharpness": "sharpness",
    "cpu_temp": "cpu_temp", "out_temp": "out_temp", "lux": "lux",
}

_SCHEMA = """
CREATE TABLE IF NOT EXISTS metadata (
  ts INTEGER PRIMARY KEY,
  day TEXT, file TEXT,
  cpu_temp REAL, cpu_freq_mhz INTEGER, throttled INTEGER,
  brightness REAL, canopy_pct REAL, sharpness REAL, size INTEGER,
  load1 REAL, mem_used_pct REAL, disk_used_pct REAL, uptime_s INTEGER,
  exposure_us INTEGER, gain REAL, lux REAL, colour_temp INTEGER,
  out_temp REAL, out_humidity REAL, out_wind REAL, out_cloud REAL, out_precip REAL, out_code INTEGER,
  is_day INTEGER, sunrise TEXT, sunset TEXT, night INTEGER, night_mode TEXT, pp INTEGER,
  clip_hi REAL
);
CREATE INDEX IF NOT EXISTS idx_metadata_day ON metadata(day);
CREATE TABLE IF NOT EXISTS events (
  ts INTEGER, type TEXT, detail TEXT
);
CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts);
CREATE TABLE IF NOT EXISTS meta_kv (k TEXT PRIMARY KEY, v TEXT);
CREATE TABLE IF NOT EXISTS zone_metrics (
  ts INTEGER, day TEXT, zone TEXT, canopy REAL,
  PRIMARY KEY (ts, zone)
);
CREATE INDEX IF NOT EXISTS idx_zone_day ON zone_metrics(day);
"""


def _flatten(record: dict) -> dict:
    """Nested capture record -> flat row dict."""
    cam = record.get("cam") or {}
    out = record.get("outdoor") or {}
    ts = record.get("ts")
    try:
        unix = int(datetime.fromisoformat(ts).timestamp()) if ts else int(time.time())
    except Exception:
        unix = int(time.time())
    return {
        "ts": unix, "day": (ts or "")[:10], "file": record.get("file"),
        "cpu_temp": record.get("cpu_temp_c"), "cpu_freq_mhz": record.get("cpu_freq_mhz"),
        "throttled": record.get("throttled"),
        "brightness": record.get("brightness"), "canopy_pct": record.get("canopy_pct"),
        "sharpness": record.get("sharpness"), "size": record.get("size"),
        "load1": record.get("load1"), "mem_used_pct": record.get("mem_used_pct"),
        "disk_used_pct": record.get("disk_used_pct"), "uptime_s": record.get("uptime_s"),
        "exposure_us": cam.get("exposure_us"), "gain": cam.get("gain"),
        "lux": cam.get("lux"), "colour_temp": cam.get("colour_temp"),
        "out_temp": out.get("temp_c"), "out_humidity": out.get("humidity"),
        "out_wind": out.get("wind"), "out_cloud": out.get("cloud"),
        "out_precip": out.get("precip"), "out_code": out.get("code"),
        "is_day": record.get("is_day"), "sunrise": record.get("sunrise"), "sunset": record.get("sunset"),
        "night": record.get("night"), "night_mode": record.get("night_mode"),
        "pp": record.get("pp"), "clip_hi": record.get("clip_hi"),
    }


def _nest(row: sqlite3.Row) -> dict:
    """Flat DB row -> nested record (shape the frontend expects)."""
    r = dict(row)
    rec = {
        "ts": datetime.fromtimestamp(r["ts"]).isoformat(timespec="seconds"),
        "unix": r["ts"], "file": r.get("file"),
    }
    for key, col in (("cpu_temp_c", "cpu_temp"), ("cpu_freq_mhz", "cpu_freq_mhz"),
                     ("throttled", "throttled"), ("brightness", "brightness"),
                     ("canopy_pct", "canopy_pct"), ("sharpness", "sharpness"), ("size", "size"),
                     ("load1", "load1"), ("mem_used_pct", "mem_used_pct"),
                     ("disk_used_pct", "disk_used_pct"), ("uptime_s", "uptime_s"),
                     ("is_day", "is_day"), ("sunrise", "sunrise"), ("sunset", "sunset"),
                     ("night", "night"), ("night_mode", "night_mode"), ("pp", "pp"),
                     ("clip_hi", "clip_hi")):
        if r.get(col) is not None:
            rec[key] = r[col]
    cam = {k: r[c] for k, c in (("exposure_us", "exposure_us"), ("gain", "gain"),
                                ("lux", "lux"), ("colour_temp", "colour_temp")) if r.get(c) is not None}
    if cam:
        rec["cam"] = cam
    out = {k: r[c] for k, c in (("temp_c", "out_temp"), ("humidity", "out_humidity"),
                                ("wind", "out_wind"), ("cloud", "out_cloud"),
                                ("precip", "out_precip"), ("code", "out_code")) if r.get(c) is not None}
    if out:
        rec["outdoor"] = out
    return rec


class MetricsDB:
    def __init__(self, path):
        self.path = str(path)
        self._init()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=5.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.execute("PRAGMA synchronous=NORMAL")
        return conn

    def _init(self) -> None:
        with self._conn() as conn:
            conn.executescript(_SCHEMA)
            # Migrate older databases that predate added columns.
            have = {r["name"] for r in conn.execute("PRAGMA table_info(metadata)").fetchall()}
            for col, decl in (("canopy_pct", "REAL"), ("sharpness", "REAL"),
                              ("night", "INTEGER"), ("night_mode", "TEXT"), ("pp", "INTEGER"),
                              ("clip_hi", "REAL")):
                if col not in have:
                    conn.execute(f"ALTER TABLE metadata ADD COLUMN {col} {decl}")

    def insert(self, record: dict) -> None:
        row = _flatten(record)
        cols = ",".join(_COLUMNS)
        ph = ",".join(":" + c for c in _COLUMNS)
        with self._conn() as conn:
            conn.execute(f"INSERT OR REPLACE INTO metadata ({cols}) VALUES ({ph})", row)

    def query_day(self, day: str) -> list:
        with self._conn() as conn:
            rows = conn.execute("SELECT * FROM metadata WHERE day=? ORDER BY ts", (day,)).fetchall()
        return [_nest(r) for r in rows]

    def latest(self) -> dict:
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM metadata ORDER BY ts DESC LIMIT 1").fetchone()
        return _nest(row) if row else {}

    def recent_brightness(self, limit: int = 15) -> list:
        """Brightness of the most recent daytime frames (newest first), for the
        relative dark-frame guard. Night frames are excluded because their
        post-processed brightness lives in a different regime."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT brightness FROM metadata WHERE brightness IS NOT NULL "
                "AND (night IS NULL OR night=0) ORDER BY ts DESC LIMIT ?",
                (int(limit),)).fetchall()
        return [r["brightness"] for r in rows]

    def days(self) -> list:
        with self._conn() as conn:
            rows = conn.execute("SELECT DISTINCT day FROM metadata ORDER BY day DESC").fetchall()
        return [r["day"] for r in rows if r["day"]]

    def summary(self, limit: int = 30) -> list:
        with self._conn() as conn:
            rows = conn.execute(
                """SELECT day, COUNT(*) n,
                          AVG(cpu_temp) cpu_avg, MIN(cpu_temp) cpu_min, MAX(cpu_temp) cpu_max,
                          AVG(out_temp) out_avg, MIN(out_temp) out_min, MAX(out_temp) out_max,
                          AVG(brightness) br_avg, MIN(brightness) br_min, MAX(brightness) br_max,
                          AVG(canopy_pct) cn_avg, MIN(canopy_pct) cn_min, MAX(canopy_pct) cn_max,
                          SUM(CASE WHEN night=1 THEN 1 ELSE 0 END) nights
                   FROM metadata GROUP BY day ORDER BY day DESC LIMIT ?""", (limit,)).fetchall()
        def agg(r, p):
            if r[p + "_avg"] is None:
                return None
            return {"avg": round(r[p + "_avg"], 1), "min": round(r[p + "_min"], 1), "max": round(r[p + "_max"], 1)}
        out = [{"day": r["day"], "n": r["n"], "cpu_temp": agg(r, "cpu"),
                "outdoor_temp": agg(r, "out"), "brightness": agg(r, "br"),
                "canopy": agg(r, "cn"), "nights": int(r["nights"] or 0)} for r in rows]
        out.reverse()
        return out

    def rows_missing_image_metrics(self, limit: int = 20000) -> list:
        """Rows still missing canopy and/or sharpness (computed from the image)."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT ts, day, file, canopy_pct, sharpness FROM metadata "
                "WHERE (canopy_pct IS NULL OR sharpness IS NULL) AND file IS NOT NULL "
                "ORDER BY ts LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]

    def count_missing_image_metrics(self) -> int:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT COUNT(*) c FROM metadata WHERE canopy_pct IS NULL OR sharpness IS NULL"
            ).fetchone()
        return int(row["c"]) if row else 0

    def update_image_metrics(self, ts: int, canopy=None, sharpness=None) -> None:
        sets, vals = [], []
        if canopy is not None:
            sets.append("canopy_pct=?"); vals.append(canopy)
        if sharpness is not None:
            sets.append("sharpness=?"); vals.append(sharpness)
        if not sets:
            return
        vals.append(int(ts))
        with self._conn() as conn:
            conn.execute(f"UPDATE metadata SET {', '.join(sets)} WHERE ts=?", vals)

    def best_frame(self, day: str) -> dict:
        """Sharpest reasonably-exposed frame of a day (for thumbnails/posters)."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT file, ts, sharpness, brightness FROM metadata "
                "WHERE day=? AND sharpness IS NOT NULL AND brightness BETWEEN 40 AND 235 "
                "ORDER BY sharpness DESC LIMIT 1", (day,)).fetchone()
        return dict(row) if row else {}

    def hourly_matrix(self, metric: str, days: int = 30) -> dict:
        """Per-(day, hour-of-day) averages of a metric, plus an across-days
        'average day' profile. Drives the calendar heatmap + typical-day view."""
        col = HOURLY_METRICS.get(metric)
        if not col:
            return {"metric": metric, "matrix": [], "avgday": []}
        with self._conn() as conn:
            rows = conn.execute(
                f"SELECT day, CAST(strftime('%H', ts, 'unixepoch', 'localtime') AS INTEGER) h, "
                f"AVG({col}) v FROM metadata WHERE {col} IS NOT NULL "
                f"GROUP BY day, h ORDER BY day", ()).fetchall()
        by_day = {}
        for r in rows:
            by_day.setdefault(r["day"], {})[r["h"]] = r["v"]
        sel_days = sorted(by_day)[-days:]
        matrix = [{"day": d,
                   "hours": [round(by_day[d][h], 1) if h in by_day[d] else None for h in range(24)]}
                  for d in sel_days]
        avgday = []
        for h in range(24):
            vals = [by_day[d][h] for d in sel_days if h in by_day[d]]
            if vals:
                avgday.append({"h": h, "avg": round(sum(vals) / len(vals), 1),
                               "min": round(min(vals), 1), "max": round(max(vals), 1)})
            else:
                avgday.append({"h": h, "avg": None, "min": None, "max": None})
        return {"metric": metric, "matrix": matrix, "avgday": avgday}

    # ---- multi-zone canopy ----
    def insert_zones(self, ts: int, day: str, values: dict) -> None:
        rows = [(int(ts), day, name, val) for name, val in values.items() if val is not None]
        if not rows:
            return
        with self._conn() as conn:
            conn.executemany(
                "INSERT OR REPLACE INTO zone_metrics (ts, day, zone, canopy) VALUES (?,?,?,?)", rows)

    def clear_zones(self) -> None:
        with self._conn() as conn:
            conn.execute("DELETE FROM zone_metrics")

    def rows_missing_zones(self, limit: int = 20000) -> list:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT ts, day, file FROM metadata WHERE file IS NOT NULL "
                "AND ts NOT IN (SELECT DISTINCT ts FROM zone_metrics) ORDER BY ts LIMIT ?",
                (limit,)).fetchall()
        return [{"ts": r["ts"], "day": r["day"], "file": r["file"]} for r in rows]

    def count_missing_zones(self) -> int:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT COUNT(*) c FROM metadata WHERE file IS NOT NULL "
                "AND ts NOT IN (SELECT DISTINCT ts FROM zone_metrics)").fetchone()
        return int(row["c"]) if row else 0

    def zones_day(self, day: str) -> dict:
        """Per-zone canopy series for a day: {names:[...], rows:[{ts, <zone>:v}]}."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT ts, zone, canopy FROM zone_metrics WHERE day=? ORDER BY ts", (day,)).fetchall()
        names, by_ts = [], {}
        for r in rows:
            if r["zone"] not in names:
                names.append(r["zone"])
            by_ts.setdefault(r["ts"], {})[r["zone"]] = r["canopy"]
        out_rows = []
        for ts in sorted(by_ts):
            rec = {"ts": datetime.fromtimestamp(ts).isoformat(timespec="seconds")}
            rec.update(by_ts[ts])
            out_rows.append(rec)
        return {"names": sorted(names), "rows": out_rows}

    def add_event(self, ts: int, etype: str, detail: str = "") -> None:
        with self._conn() as conn:
            conn.execute("INSERT INTO events (ts, type, detail) VALUES (?,?,?)", (int(ts), etype, detail))

    def events(self, limit: int = 50) -> list:
        with self._conn() as conn:
            rows = conn.execute("SELECT * FROM events ORDER BY ts DESC LIMIT ?", (limit,)).fetchall()
        return [{"ts": datetime.fromtimestamp(r["ts"]).isoformat(timespec="seconds"),
                 "type": r["type"], "detail": r["detail"]} for r in rows]

    def kv_get(self, key: str) -> "str | None":
        with self._conn() as conn:
            row = conn.execute("SELECT v FROM meta_kv WHERE k=?", (key,)).fetchone()
        return row["v"] if row else None

    def kv_set(self, key: str, value: str) -> None:
        with self._conn() as conn:
            conn.execute("INSERT OR REPLACE INTO meta_kv (k, v) VALUES (?, ?)", (key, value))

    def import_jsonl_once(self, history_dir) -> int:
        """Migrate any legacy metadata.jsonl files into the DB, once."""
        if self.kv_get("jsonl_imported"):
            return 0
        history_dir = Path(history_dir)
        count = 0
        if history_dir.exists():
            for day_dir in sorted(history_dir.iterdir()):
                jf = day_dir / "metadata.jsonl"
                if not jf.exists():
                    continue
                for line in jf.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        self.insert(json.loads(line))
                        count += 1
                    except Exception:
                        pass
        self.kv_set("jsonl_imported", str(int(time.time())))
        if count:
            log.info("imported %d legacy metadata rows into SQLite", count)
        return count
