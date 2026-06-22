from __future__ import annotations

import configparser
import secrets
from dataclasses import dataclass
from pathlib import Path
from typing import Union


@dataclass(frozen=True)
class ServerConfig:
    host: str
    port: int
    auth_token: str
    admin_enabled: bool
    admin_timeout: int


@dataclass(frozen=True)
class CameraConfig:
    snapshot_width: int
    snapshot_height: int
    live_width: int
    live_height: int
    live_fps: int
    live_quality: int
    live_idle_timeout: float
    hflip: bool
    vflip: bool
    tuning_file: str
    warmup_seconds: float
    retry_count: int
    retry_delay_seconds: float
    night_mode: str
    night_max_exposure_us: int
    night_max_gain: float
    night_target_brightness: float
    night_brightness_threshold: float
    live_night_max_us: int
    jpeg_quality: int
    img_sharpness: float
    img_contrast: float
    img_saturation: float
    denoise: str


@dataclass(frozen=True)
class SnapshotConfig:
    retain_days: int
    skip_when_camera_busy: bool
    interval_seconds: int


@dataclass(frozen=True)
class PathConfig:
    data_dir: Path
    lock_file: Path


@dataclass(frozen=True)
class LocationConfig:
    latitude: float
    longitude: float
    name: str
    weather: bool


@dataclass(frozen=True)
class AppConfig:
    server: ServerConfig
    camera: CameraConfig
    snapshot: SnapshotConfig
    paths: PathConfig
    location: LocationConfig
    config_path: Path


def _get_bool(parser: configparser.ConfigParser, section: str, key: str, fallback: bool) -> bool:
    if not parser.has_option(section, key):
        return fallback
    return parser.getboolean(section, key)


def _get_float(parser: configparser.ConfigParser, section: str, key: str, fallback: float) -> float:
    if not parser.has_option(section, key):
        return fallback
    return parser.getfloat(section, key)


def _get_int(parser: configparser.ConfigParser, section: str, key: str, fallback: int) -> int:
    if not parser.has_option(section, key):
        return fallback
    return parser.getint(section, key)


def _get_str(parser: configparser.ConfigParser, section: str, key: str, fallback: str) -> str:
    if not parser.has_option(section, key):
        return fallback
    return parser.get(section, key).strip()


def load_config(path: Union[str, Path]) -> AppConfig:
    config_path = Path(path).expanduser().resolve()
    parser = configparser.ConfigParser()
    parser.read(config_path)

    server = ServerConfig(
        host=_get_str(parser, "server", "host", "0.0.0.0"),
        port=_get_int(parser, "server", "port", 8090),
        auth_token=_get_str(parser, "server", "auth_token", ""),
        admin_enabled=_get_bool(parser, "server", "admin_enabled", True),
        admin_timeout=_get_int(parser, "server", "admin_timeout", 60),
    )
    camera = CameraConfig(
        snapshot_width=_get_int(parser, "camera", "snapshot_width", 1920),
        snapshot_height=_get_int(parser, "camera", "snapshot_height", 1080),
        live_width=_get_int(parser, "camera", "live_width", 1280),
        live_height=_get_int(parser, "camera", "live_height", 720),
        live_fps=_get_int(parser, "camera", "live_fps", 5),
        live_quality=_get_int(parser, "camera", "live_quality", 50),
        live_idle_timeout=_get_float(parser, "camera", "live_idle_timeout", 8.0),
        hflip=_get_bool(parser, "camera", "hflip", True),
        vflip=_get_bool(parser, "camera", "vflip", True),
        tuning_file=_get_str(
            parser,
            "camera",
            "tuning_file",
            "/usr/share/libcamera/ipa/rpi/vc4/imx477_noir.json",
        ),
        warmup_seconds=_get_float(parser, "camera", "warmup_seconds", 0.7),
        retry_count=_get_int(parser, "camera", "retry_count", 3),
        retry_delay_seconds=_get_float(parser, "camera", "retry_delay_seconds", 3.0),
        night_mode=_get_str(parser, "camera", "night_mode", "auto"),
        night_max_exposure_us=_get_int(parser, "camera", "night_max_exposure_us", 2_000_000),
        night_max_gain=_get_float(parser, "camera", "night_max_gain", 16.0),
        night_target_brightness=_get_float(parser, "camera", "night_target_brightness", 90.0),
        night_brightness_threshold=_get_float(parser, "camera", "night_brightness_threshold", 35.0),
        live_night_max_us=_get_int(parser, "camera", "live_night_max_us", 500_000),
        jpeg_quality=_get_int(parser, "camera", "jpeg_quality", 92),
        img_sharpness=_get_float(parser, "camera", "img_sharpness", 1.0),
        img_contrast=_get_float(parser, "camera", "img_contrast", 1.0),
        img_saturation=_get_float(parser, "camera", "img_saturation", 1.0),
        denoise=_get_str(parser, "camera", "denoise", "high"),
    )
    snapshot = SnapshotConfig(
        retain_days=_get_int(parser, "snapshot", "retain_days", 14),
        skip_when_camera_busy=_get_bool(parser, "snapshot", "skip_when_camera_busy", True),
        interval_seconds=_get_int(parser, "snapshot", "interval_seconds", 60),
    )
    paths = PathConfig(
        data_dir=Path(_get_str(parser, "paths", "data_dir", "/home/user/camera-remote-data")).expanduser(),
        lock_file=Path(_get_str(parser, "paths", "lock_file", "/tmp/camera-remote-camera.lock")).expanduser(),
    )
    location = LocationConfig(
        latitude=_get_float(parser, "location", "latitude", 52.23),
        longitude=_get_float(parser, "location", "longitude", 21.01),
        name=_get_str(parser, "location", "name", "Warszawa"),
        weather=_get_bool(parser, "location", "weather", True),
    )
    return AppConfig(server, camera, snapshot, paths, location, config_path)


def ensure_auth_token(path: Union[str, Path]) -> str:
    config_path = Path(path).expanduser().resolve()
    parser = configparser.ConfigParser()
    parser.read(config_path)
    if not parser.has_section("server"):
        parser.add_section("server")

    current = parser.get("server", "auth_token", fallback="").strip()
    if current:
        return current

    token = secrets.token_hex(16)
    parser.set("server", "auth_token", token)
    with config_path.open("w", encoding="utf-8") as fh:
        parser.write(fh)
    return token
