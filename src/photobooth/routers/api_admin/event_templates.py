from typing import Literal

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from ...services import event_admin
from ...services.event_admin import EventAdminError

router = APIRouter(prefix="/event-templates", tags=["admin", "event-templates"])


class TemplateInputField(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    type: Literal["text", "file"]
    value: str | None = None


class TemplateEventInputField(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    type: Literal["text", "file"]
    required: bool = False


class CreateTemplateRequest(BaseModel):
    id: str = Field(min_length=1, max_length=120)
    name: str = Field(min_length=1, max_length=120)
    description: str = ""
    inputs: list[TemplateInputField] = Field(default_factory=list)
    event_inputs: list[TemplateEventInputField] = Field(default_factory=list)


class UpdateTemplateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = None
    inputs: list[TemplateInputField] | None = None
    event_inputs: list[TemplateEventInputField] | None = None


@router.get("")
def api_list_event_templates():
    templates = [item for item in event_admin.list_templates() if item.get("id") != "default"]
    return {"templates": templates}


@router.get("/{template_id}")
def api_get_event_template(template_id: str):
    try:
        return event_admin.get_template(template_id)
    except EventAdminError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.post("")
def api_create_event_template(body: CreateTemplateRequest):
    from datetime import datetime, timezone

    from ...paths import admin_path

    if not event_admin.is_admin_enabled():
        raise HTTPException(400, "instabooth-admin is not configured")

    template_dir = admin_path("templates", body.id)
    if template_dir.exists():
        raise HTTPException(400, f"template already exists: {body.id}")

    import json

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    template_dir.mkdir(parents=True)
    (template_dir / "config").mkdir()
    (template_dir / "userdata").mkdir()
    inputs = event_admin.validate_template_inputs([item.model_dump() for item in body.inputs])
    event_inputs = event_admin.validate_event_inputs_schema([item.model_dump() for item in body.event_inputs])
    (template_dir / "template.json").write_text(
        json.dumps(
            {
                "id": body.id,
                "name": body.name,
                "description": body.description,
                "inputs": inputs,
                "event_inputs": event_inputs,
                "version": 1,
                "created_at": now,
                "updated_at": now,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    default_template_config = admin_path("templates", "default", "config", "config.json")
    if default_template_config.is_file():
        (template_dir / "config" / "config.json").write_text(default_template_config.read_text(encoding="utf-8"), encoding="utf-8")

    return event_admin.get_template(body.id)


@router.patch("/{template_id}")
def api_update_event_template(template_id: str, body: UpdateTemplateRequest):
    try:
        inputs = None
        if body.inputs is not None:
            inputs = [item.model_dump() for item in body.inputs]
        event_inputs = None
        if body.event_inputs is not None:
            event_inputs = [item.model_dump() for item in body.event_inputs]
        return event_admin.update_template(template_id, body.name, body.description, inputs, event_inputs)
    except EventAdminError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/{template_id}/inputs/{input_name}/file")
async def api_upload_template_input_file(template_id: str, input_name: str, file: UploadFile = File(...)):
    if not file.filename:
        raise HTTPException(400, "uploaded file has no filename")
    try:
        relative_path = event_admin.save_template_input_file(template_id, input_name, file.filename, file.file)
        template = event_admin.get_template(template_id)
        inputs = template.get("inputs", [])
        updated = False
        for item in inputs:
            if item.get("name") == input_name:
                item["value"] = relative_path
                updated = True
                break
        if not updated:
            raise EventAdminError(f"template input not found: {input_name}")
        event_admin.update_template(template_id, inputs=inputs)
        return {"path": relative_path, "inputs": inputs}
    except EventAdminError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.delete("/{template_id}")
def api_delete_event_template(template_id: str):
    try:
        event_admin.delete_template(template_id)
        return {"deleted": template_id}
    except EventAdminError as exc:
        raise HTTPException(400, str(exc)) from exc
