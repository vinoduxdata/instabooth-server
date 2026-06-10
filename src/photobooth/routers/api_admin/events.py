import logging
import os
import sys

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from ...services import event_admin
from ...services.event_admin import EventAdminError, EventStatus

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/events", tags=["admin", "events"])


class EventInputValue(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    value: str | None = None


class CreateEventRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    template_id: str = Field(min_length=1, max_length=120)
    event_id: str | None = Field(default=None, min_length=1, max_length=120)
    event_inputs: list[EventInputValue] = Field(default_factory=list)


class UpdateEventStatusRequest(BaseModel):
    status: EventStatus


class UpdateEventRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)


@router.get("/enabled")
def api_events_enabled():
    return {"enabled": event_admin.is_admin_enabled()}


@router.get("")
def api_list_events():
    return {"events": event_admin.list_events(), "active": event_admin.get_active_event()}


@router.get("/active")
def api_get_active_event():
    active = event_admin.get_active_event()
    if not active:
        raise HTTPException(404, "no active event configured")
    return active


@router.get("/{event_id}")
def api_get_event(event_id: str):
    try:
        return event_admin.get_event(event_id)
    except EventAdminError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.post("")
def api_create_event(body: CreateEventRequest):
    try:
        return event_admin.create_event(
            body.name,
            body.template_id,
            body.event_id,
            [item.model_dump() for item in body.event_inputs],
        )
    except EventAdminError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/{event_id}/event-inputs/{input_name}/file")
async def api_upload_event_input_file(event_id: str, input_name: str, file: UploadFile = File(...)):
    if not file.filename:
        raise HTTPException(400, "uploaded file has no filename")
    try:
        relative_path = event_admin.save_event_input_file(event_id, input_name, file.filename, file.file)
        return {"path": relative_path}
    except EventAdminError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.patch("/{event_id}")
def api_update_event(event_id: str, body: UpdateEventRequest):
    try:
        return event_admin.update_event(event_id, body.name)
    except EventAdminError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.delete("/{event_id}")
def api_delete_event(event_id: str):
    try:
        return event_admin.delete_event(event_id)
    except EventAdminError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.patch("/{event_id}/status")
def api_update_event_status(event_id: str, body: UpdateEventStatusRequest):
    try:
        return event_admin.update_event_status(event_id, body.status)
    except EventAdminError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/{event_id}/activate")
def api_activate_event(event_id: str, restart: bool = False):
    try:
        result = event_admin.activate_event(event_id)
    except EventAdminError as exc:
        raise HTTPException(400, str(exc)) from exc

    if restart and result.get("restart_required"):
        from ...paths import ADMIN_DIR

        data_path = result["data_path"]
        logger.info("restarting photobooth with data-dir %s", data_path)
        from pathlib import Path

        argv = [sys.executable, "-m", "photobooth", "--data-dir", data_path]
        env = os.environ.copy()
        if ADMIN_DIR is not None:
            argv.extend(["--admin-dir", str(ADMIN_DIR)])
            server_src = ADMIN_DIR.parent / "instabooth-server" / "src"
            if server_src.is_dir():
                env["PYTHONPATH"] = str(server_src) + (f":{env['PYTHONPATH']}" if env.get("PYTHONPATH") else "")
        os.execve(sys.executable, argv, env)

    return result
