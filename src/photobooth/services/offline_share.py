"""Offline share: auto Wi-Fi join QR + LAN download URL for guests."""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import Request

from ..utils.network import get_local_ip
from .hotspot import auto_wifi_qr_public_path

logger = logging.getLogger(__name__)


def _lan_base_url(request: Request) -> str:
    port = request.url.port or (443 if request.url.scheme == "https" else 80)
    return f"http://{get_local_ip()}:{port}"


def resolve_wifi_qr_public_path() -> str | None:
    """Return web path to the auto-generated booth Wi-Fi join QR, if present."""
    return auto_wifi_qr_public_path()


def approval_download_url(request: Request, capture_id: UUID) -> str:
    base = _lan_base_url(request)
    return f"{base}/api/share/offline/approval/{capture_id}/download"


def media_download_url(request: Request, mediaitem_id: UUID) -> str:
    base = _lan_base_url(request)
    return f"{base}/api/share/offline/media/{mediaitem_id}/download"


def offline_share_info_for_approval(request: Request, capture_id: UUID) -> dict[str, str | None]:
    return {
        "wifi_qr_image_url": resolve_wifi_qr_public_path(),
        "download_url": approval_download_url(request, capture_id),
    }


def offline_share_info_for_media(request: Request, mediaitem_id: UUID) -> dict[str, str | None]:
    return {
        "wifi_qr_image_url": resolve_wifi_qr_public_path(),
        "download_url": media_download_url(request, mediaitem_id),
    }
