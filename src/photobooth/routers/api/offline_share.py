"""Offline guest sharing — Wi-Fi QR image + LAN download links (no cloud)."""

import logging
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import FileResponse

from ...container import container
from ...services.offline_share import (
    offline_share_info_for_approval,
    offline_share_info_for_media,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/share/offline", tags=["share-offline"])


@router.get("/approval/{capture_id}")
def api_offline_share_approval_info(capture_id: UUID, request: Request):
    return offline_share_info_for_approval(request, capture_id)


@router.get("/media/{mediaitem_id}")
def api_offline_share_media_info(mediaitem_id: UUID, request: Request):
    return offline_share_info_for_media(request, mediaitem_id)


@router.get("/approval/{capture_id}/download")
def api_offline_share_approval_download(capture_id: UUID):
    try:
        capture = container.processing_service.get_capture(capture_id)
        filepath = capture.filepath
        if not filepath.is_file():
            raise FileNotFoundError(filepath)
        return FileResponse(filepath, media_type="image/jpeg", filename=f"instabooth-{capture_id}.jpg")
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"capture not found: {capture_id}") from exc
    except Exception as exc:
        logger.exception(exc)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc


@router.get("/media/{mediaitem_id}/download")
def api_offline_share_media_download(mediaitem_id: UUID):
    try:
        item = container.mediacollection_service.get_item(mediaitem_id)
        filepath = item.processed
        if not filepath.is_file():
            raise FileNotFoundError(filepath)
        suffix = filepath.suffix or ".jpg"
        return FileResponse(filepath, media_type="image/jpeg", filename=f"instabooth-{mediaitem_id}{suffix}")
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"media not found: {mediaitem_id}") from exc
    except Exception as exc:
        logger.exception(exc)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
