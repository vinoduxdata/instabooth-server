"""Auto-generate WPA Wi-Fi join QR for offline guest sharing."""

from __future__ import annotations

import logging
import os
from pathlib import Path

import qrcode

from .. import USERDATA_PATH
from .booth_config import BoothConfig

logger = logging.getLogger(__name__)

AUTO_WIFI_QR_FILENAME = "auto-wifi-qr.png"


def _escape_wifi_field(value: str) -> str:
    return value.replace("\\", "\\\\").replace(";", "\\;").replace(":", "\\:").replace(",", "\\,")


def wifi_join_payload(ssid: str, password: str) -> str:
    return f"WIFI:T:WPA;S:{_escape_wifi_field(ssid)};P:{_escape_wifi_field(password)};H:false;;"


def hotspot_credentials_from_env_or_config() -> tuple[str, str] | None:
    ssid = os.environ.get("INSTABOOTH_HOTSPOT_SSID", "").strip()
    password = os.environ.get("INSTABOOTH_HOTSPOT_PASSWORD", "").strip()
    if ssid and password:
        return ssid, password

    try:
        hotspot = BoothConfig.from_disk().hotspot
    except Exception as exc:
        logger.warning("hotspot: could not load booth config: %s", exc)
        return None

    if not hotspot.enabled:
        return None

    if hotspot.ssid and hotspot.password:
        return hotspot.ssid, hotspot.password

    return None


def auto_wifi_qr_path() -> Path:
    return Path(USERDATA_PATH, "event-inputs", "wifi-qr-code", AUTO_WIFI_QR_FILENAME)


def generate_wifi_qr_png(ssid: str, password: str, destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = wifi_join_payload(ssid, password)
    qr = qrcode.QRCode(version=None, box_size=8, border=2)
    qr.add_data(payload)
    qr.make(fit=True)
    qr.make_image(fill_color="black", back_color="white").save(destination)
    return destination


def ensure_auto_wifi_qr_on_startup() -> Path | None:
    credentials = hotspot_credentials_from_env_or_config()
    if not credentials:
        logger.info("hotspot: no credentials available; skipping Wi-Fi QR generation")
        return None

    ssid, password = credentials
    if len(password) < 8:
        logger.warning("hotspot: password too short; skipping Wi-Fi QR generation")
        return None

    destination = auto_wifi_qr_path()
    try:
        generate_wifi_qr_png(ssid, password, destination)
    except Exception as exc:
        logger.exception("hotspot: failed to write Wi-Fi QR: %s", exc)
        return None

    logger.info("hotspot: wrote Wi-Fi join QR to %s", destination.resolve())
    return destination


def auto_wifi_qr_public_path() -> str | None:
    path = auto_wifi_qr_path()
    if not path.is_file():
        return None
    relative = Path("userdata/event-inputs/wifi-qr-code", AUTO_WIFI_QR_FILENAME).as_posix()
    return f"/{relative}"
