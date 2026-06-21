from __future__ import annotations

import json
import logging
import re
import ssl
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple
from urllib.parse import quote, urlencode
from urllib.error import URLError
from urllib.request import Request, urlopen

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover - Python < 3.9 fallback.
    ZoneInfo = None  # type: ignore[assignment]

log = logging.getLogger(__name__)

TTL_SECONDS = 15 * 60
HTTP_TIMEOUT_SECONDS = 8
TRIP_START = "2026-06-20"
TRIP_END = "2026-07-06"

LOCS = {
    "sk": {"lat": 49.120, "lon": 20.063, "wiki": "Štrbské Pleso", "name": "Štrbské Pleso", "country": "🇸🇰"},
    "zak": {"lat": 49.299, "lon": 19.949, "wiki": "Zakopane", "name": "Zakopane", "country": "🇵🇱"},
    "kry": {"lat": 49.422, "lon": 20.961, "wiki": "Krynica-Zdrój", "name": "Krynica-Zdrój", "country": "🇵🇱"},
}

_PREFIX_FILTER = re.compile(r"^(Powiat|Gmina|Województwo|Ulica|Droga|Cmentarz|Synagoga|Parafia)", re.I)
_TITLE_FILTER = re.compile(r"\((gmina|stacja kolejowa|przystanek)", re.I)
_cache_lock = threading.Lock()
_cache_ts = 0.0
_cache_data = None  # type: Optional[Dict[str, Any]]


def get_bootstrap(fresh: bool = False) -> Dict[str, Any]:
    global _cache_data, _cache_ts

    now = time.time()
    with _cache_lock:
        if fresh:
            _cache_data = None
            _cache_ts = 0.0
        elif _cache_data is not None and now - _cache_ts < TTL_SECONDS:
            return _cache_data

    data = _build_bootstrap()
    with _cache_lock:
        _cache_data = data
        _cache_ts = time.time()
    return data


def _build_bootstrap() -> Dict[str, Any]:
    weather = {}
    places = {}
    attractions = {}

    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(_fetch_location, key, loc): key for key, loc in LOCS.items()}
        holidays_future = pool.submit(_fetch_holidays)

        for future in as_completed(futures):
            key = futures[future]
            loc_weather, loc_place, loc_attractions = future.result()
            weather[key] = loc_weather
            places[key] = loc_place
            attractions[key] = loc_attractions

        try:
            holidays = holidays_future.result()
        except Exception as exc:
            log.warning("holiday fetch failed: %s", exc)
            holidays = {"PL": {}, "SK": {}}

    return {
        "today": _today_warsaw(),
        "serverTime": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "weather": weather,
        "places": places,
        "attractions": attractions,
        "holidays": holidays,
    }


def _fetch_location(key: str, loc: Dict[str, Any]) -> Tuple[Any, Dict[str, Any], Any]:
    try:
        weather = _fetch_weather(loc)
    except Exception as exc:
        log.warning("weather fetch failed for %s: %s", key, exc)
        weather = None

    place = _fetch_place(loc)
    if weather and weather.get("elevation") is not None:
        place["elevation"] = round(weather["elevation"])

    try:
        attractions = _fetch_attractions(loc)
    except Exception as exc:
        log.warning("attraction fetch failed for %s: %s", key, exc)
        attractions = []

    return weather, place, attractions


def _fetch_weather(loc: Dict[str, Any]) -> Dict[str, Any]:
    params = {
        "latitude": loc["lat"],
        "longitude": loc["lon"],
        "current": "temperature_2m,weather_code,is_day,wind_speed_10m",
        "daily": (
            "weather_code,temperature_2m_max,temperature_2m_min,"
            "precipitation_probability_max,sunrise,sunset,uv_index_max,wind_speed_10m_max"
        ),
        "hourly": "temperature_2m,uv_index,precipitation_probability",
        "timezone": "Europe/Bratislava",
        "forecast_days": 16,
    }
    data = _json_get("https://api.open-meteo.com/v1/forecast?" + urlencode(params))

    daily = data.get("daily") or {}
    days = {}
    for i, date in enumerate(daily.get("time") or []):
        days[date] = {
            "c": _item(daily.get("weather_code"), i),
            "hi": _item(daily.get("temperature_2m_max"), i),
            "lo": _item(daily.get("temperature_2m_min"), i),
            "p": _item(daily.get("precipitation_probability_max"), i),
            "sr": _item(daily.get("sunrise"), i),
            "ss": _item(daily.get("sunset"), i),
            "uv": _item(daily.get("uv_index_max"), i),
            "wind": _item(daily.get("wind_speed_10m_max"), i),
        }

    hourly_data = data.get("hourly") or {}
    hourly = {}
    for i, stamp in enumerate(hourly_data.get("time") or []):
        date = stamp[:10]
        hour = int(stamp[11:13])
        hourly.setdefault(date, []).append(
            {
                "h": hour,
                "t": _item(hourly_data.get("temperature_2m"), i),
                "uv": _item(hourly_data.get("uv_index"), i),
                "p": _item(hourly_data.get("precipitation_probability"), i),
            }
        )

    current = data.get("current") or None
    return {
        "elevation": data.get("elevation"),
        "current": {
            "temp": current.get("temperature_2m"),
            "c": current.get("weather_code"),
            "day": current.get("is_day"),
            "wind": current.get("wind_speed_10m"),
        }
        if current
        else None,
        "days": days,
        "hourly": hourly,
    }


def _fetch_place(loc: Dict[str, Any]) -> Dict[str, Any]:
    base = {"name": loc["name"], "country": loc["country"], "extract": ""}
    try:
        data = _json_get(
            "https://pl.wikipedia.org/api/rest_v1/page/summary/" + quote(str(loc["wiki"]), safe=""),
            headers={"accept": "application/json"},
        )
    except Exception as exc:
        log.warning("place fetch failed for %s: %s", loc["name"], exc)
        return base

    base.update(
        {
            "title": data.get("title"),
            "extract": data.get("extract") or "",
            "thumb": ((data.get("thumbnail") or {}).get("source")),
            "url": (((data.get("content_urls") or {}).get("desktop") or {}).get("page")),
        }
    )
    return base


def _fetch_attractions(loc: Dict[str, Any]) -> Any:
    params = {
        "action": "query",
        "list": "geosearch",
        "gscoord": f"{loc['lat']}|{loc['lon']}",
        "gsradius": 10000,
        "gslimit": 20,
        "format": "json",
        "origin": "*",
    }
    data = _json_get("https://pl.wikipedia.org/w/api.php?" + urlencode(params))
    raw = ((data.get("query") or {}).get("geosearch") or [])
    selected = [
        item
        for item in raw
        if not _PREFIX_FILTER.search(item.get("title", ""))
        and not _TITLE_FILTER.search(item.get("title", ""))
        and item.get("title") not in (loc["name"], loc["wiki"])
    ][:7]
    if not selected:
        return []

    meta = {}
    try:
        ids = "|".join(str(item.get("pageid")) for item in selected)
        params = {
            "action": "query",
            "pageids": ids,
            "prop": "pageimages|description",
            "piprop": "thumbnail",
            "pithumbsize": 90,
            "format": "json",
            "origin": "*",
        }
        meta_data = _json_get("https://pl.wikipedia.org/w/api.php?" + urlencode(params))
        meta = (meta_data.get("query") or {}).get("pages") or {}
    except Exception as exc:
        log.warning("attraction metadata fetch failed for %s: %s", loc["name"], exc)

    out = []
    for item in selected:
        pageid = str(item.get("pageid"))
        page = meta.get(pageid) or {}
        thumb = (page.get("thumbnail") or {}).get("source")
        out.append(
            {
                "title": item.get("title"),
                "dist": int(float(item.get("dist") or 0) + 0.5),
                "lat": item.get("lat"),
                "lon": item.get("lon"),
                "url": "https://pl.wikipedia.org/?curid=" + pageid,
                "desc": page.get("description") or "",
                "thumb": thumb,
            }
        )
    return out


def _fetch_holidays() -> Dict[str, Dict[str, str]]:
    out = {"PL": {}, "SK": {}}  # type: Dict[str, Dict[str, str]]
    for country in ("PL", "SK"):
        try:
            data = _json_get(f"https://date.nager.at/api/v3/PublicHolidays/2026/{country}")
        except Exception as exc:
            log.warning("holiday fetch failed for %s: %s", country, exc)
            continue
        for holiday in data:
            date = holiday.get("date")
            if date and TRIP_START <= date <= TRIP_END:
                out[country][date] = holiday.get("localName") or holiday.get("name") or ""
    return out


def _json_get(url: str, headers: Optional[Dict[str, str]] = None) -> Any:
    try:
        return _json_get_once(url, headers=headers)
    except URLError as exc:
        if _is_cert_error(exc):
            log.warning("retrying public JSON fetch without certificate verification: %s", url)
            return _json_get_once(url, headers=headers, context=ssl._create_unverified_context())
        raise


def _json_get_once(url: str, headers: Optional[Dict[str, str]] = None, context: Optional[ssl.SSLContext] = None) -> Any:
    request_headers = {
        "User-Agent": "TatryTripApp/1.0 personal-planner",
        "Accept": "application/json",
    }
    if headers:
        request_headers.update(headers)
    request = Request(url, headers=request_headers)
    with urlopen(request, timeout=HTTP_TIMEOUT_SECONDS, context=context) as response:
        status = getattr(response, "status", 200)
        if status < 200 or status >= 300:
            raise RuntimeError(f"HTTP {status}")
        return json.loads(response.read().decode("utf-8"))


def _is_cert_error(exc: URLError) -> bool:
    reason = getattr(exc, "reason", exc)
    return isinstance(reason, ssl.SSLCertVerificationError) or "CERTIFICATE_VERIFY_FAILED" in str(exc)


def _item(values: Any, index: int) -> Any:
    if not isinstance(values, list) or index >= len(values):
        return None
    return values[index]


def _today_warsaw() -> str:
    if ZoneInfo is not None:
        try:
            return datetime.now(ZoneInfo("Europe/Warsaw")).strftime("%Y-%m-%d")
        except Exception:
            pass
    return datetime.now().strftime("%Y-%m-%d")
