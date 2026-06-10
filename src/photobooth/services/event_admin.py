"""Event and template management for multi-event booths."""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from .. import initialize_data_environment
from .. import paths as paths_module
from ..paths import admin_path, events_data_root, read_active_event_file, resolve_data_path, write_active_event_file

logger = logging.getLogger(__name__)

EventStatus = Literal["draft", "published", "active", "pause", "done", "archive", "deleted"]

STATUS_TRANSITIONS: dict[EventStatus, set[EventStatus]] = {
    "draft": {"published", "deleted"},
    "published": {"active", "deleted"},
    "active": {"pause", "done"},
    "pause": {"active", "done"},
    "done": {"archive"},
    "archive": {"deleted"},
    "deleted": set(),
}

BOOTH_CONFIG_GROUPS = ("common", "backends", "hardwareinputoutput", "misc")
TEMPLATE_CONFIG_GROUPS = ("actions", "share", "mediaprocessing", "uisettings")


class EventAdminError(Exception):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "event"


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json_atomic(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def _require_admin() -> Path:
    if paths_module.ADMIN_DIR is None:
        raise EventAdminError("instabooth-admin is not configured (missing --admin-dir or ../instabooth-admin)")
    return paths_module.ADMIN_DIR


def _events_file() -> Path:
    return admin_path("events.json")


def _load_events_registry() -> dict[str, Any]:
    _require_admin()
    events_file = _events_file()
    if not events_file.is_file():
        return {"events": []}
    return _read_json(events_file)


def _save_events_registry(registry: dict[str, Any]) -> None:
    _write_json_atomic(_events_file(), registry)


def _load_booth_config() -> dict[str, Any]:
    booth_file = admin_path("booth.json")
    if not booth_file.is_file():
        return {}
    return _read_json(booth_file)


def _load_template_config(template_id: str) -> dict[str, Any]:
    config_file = admin_path("templates", template_id, "config", "config.json")
    if not config_file.is_file():
        raise EventAdminError(f"template config not found: {template_id}")
    return _read_json(config_file)


def merge_event_config(template_config: dict[str, Any], booth_config: dict[str, Any]) -> dict[str, Any]:
    merged = {group: template_config[group] for group in TEMPLATE_CONFIG_GROUPS if group in template_config}
    for group in BOOTH_CONFIG_GROUPS:
        if group in booth_config:
            merged[group] = booth_config[group]
    return merged


def list_templates() -> list[dict[str, Any]]:
    _require_admin()
    templates_dir = admin_path("templates")
    if not templates_dir.is_dir():
        return []
    templates: list[dict[str, Any]] = []
    for item in sorted(templates_dir.iterdir()):
        if not item.is_dir():
            continue
        meta_file = item / "template.json"
        if meta_file.is_file():
            templates.append(_read_json(meta_file))
        else:
            templates.append({"id": item.name, "name": item.name})
    return templates


def get_template(template_id: str) -> dict[str, Any]:
    meta_file = admin_path("templates", template_id, "template.json")
    if not meta_file.is_file():
        raise EventAdminError(f"template not found: {template_id}")
    return _read_json(meta_file)


def list_events(include_deleted: bool = False) -> list[dict[str, Any]]:
    registry = _load_events_registry()
    events = registry.get("events", [])
    if include_deleted:
        return events
    return [event for event in events if event.get("status") != "deleted"]


def get_event(event_id: str) -> dict[str, Any]:
    for event in list_events(include_deleted=True):
        if event["id"] == event_id:
            return event
    raise EventAdminError(f"event not found: {event_id}")


def _relative_data_path(data_dir: Path) -> str:
    if paths_module.INSTABOOTH_ROOT is None:
        return str(data_dir)
    try:
        return os.path.relpath(data_dir, paths_module.INSTABOOTH_ROOT)
    except ValueError:
        return str(data_dir)


@contextmanager
def _use_data_dir(data_dir: Path):
    previous = Path.cwd()
    os.chdir(data_dir)
    try:
        yield
    finally:
        os.chdir(previous)


def _init_event_data_dir(event_data_dir: Path, template_id: str) -> None:
    template_dir = admin_path("templates", template_id)
    if not template_dir.is_dir():
        raise EventAdminError(f"template not found: {template_id}")

    event_data_dir.mkdir(parents=True, exist_ok=True)

    template_config_dir = template_dir / "config"
    if template_config_dir.is_dir():
        shutil.copytree(template_config_dir, event_data_dir / "config", dirs_exist_ok=True)

    template_userdata = template_dir / "userdata"
    if template_userdata.is_dir():
        shutil.copytree(template_userdata, event_data_dir / "userdata", dirs_exist_ok=True)

    merged_config = merge_event_config(_load_template_config(template_id), _load_booth_config())
    config_file = event_data_dir / "config" / "config.json"
    config_file.parent.mkdir(parents=True, exist_ok=True)
    config_file.write_text(json.dumps(merged_config, indent=2) + "\n", encoding="utf-8")

    with _use_data_dir(event_data_dir):
        initialize_data_environment()
        from ..database.database import create_db_and_tables

        create_db_and_tables()


def create_event(
    name: str,
    template_id: str,
    event_id: str | None = None,
    event_input_values: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    _require_admin()
    template = get_template(template_id)
    validated_inputs = validate_event_input_values(template, event_input_values or [])

    event_id = event_id or f"evt-{_slugify(name)}-{uuid.uuid4().hex[:8]}"
    if any(item["id"] == event_id for item in list_events(include_deleted=True)):
        raise EventAdminError(f"event id already exists: {event_id}")

    event_data_dir = events_data_root() / event_id
    if event_data_dir.exists():
        raise EventAdminError(f"event data directory already exists: {event_data_dir}")

    _init_event_data_dir(event_data_dir, template_id)

    now = _now()
    event = {
        "id": event_id,
        "name": name,
        "template_id": template_id,
        "status": "draft",
        "data_path": _relative_data_path(event_data_dir),
        "event_inputs": validated_inputs,
        "created_at": now,
        "updated_at": now,
    }

    registry = _load_events_registry()
    registry.setdefault("events", []).append(event)
    _save_events_registry(registry)
    return event


def update_event_status(event_id: str, new_status: EventStatus) -> dict[str, Any]:
    registry = _load_events_registry()
    updated_event: dict[str, Any] | None = None

    for event in registry.get("events", []):
        if event["id"] != event_id:
            continue
        current_status: EventStatus = event.get("status", "draft")
        allowed = STATUS_TRANSITIONS.get(current_status, set())
        if new_status not in allowed:
            raise EventAdminError(f"cannot transition from {current_status} to {new_status}")
        event["status"] = new_status
        event["updated_at"] = _now()
        updated_event = event
        break

    if updated_event is None:
        raise EventAdminError(f"event not found: {event_id}")

    if new_status == "active":
        for event in registry.get("events", []):
            if event["id"] != event_id and event.get("status") == "active":
                event["status"] = "pause"
                event["updated_at"] = _now()

    _save_events_registry(registry)
    return updated_event


def activate_event(event_id: str) -> dict[str, Any]:
    event = get_event(event_id)
    status = event.get("status", "draft")
    if status == "draft":
        event = update_event_status(event_id, "published")
    if event.get("status") == "published":
        event = update_event_status(event_id, "active")
    elif event.get("status") == "pause":
        event = update_event_status(event_id, "active")
    elif event.get("status") != "active":
        raise EventAdminError(f"event cannot be activated from status {status}")

    data_path = resolve_data_path(event["data_path"])
    if not data_path.is_dir():
        raise EventAdminError(f"event data directory missing: {data_path}")

    write_active_event_file(event_id, event["data_path"])
    return {
        "event": event,
        "data_path": str(data_path),
        "restart_required": str(data_path.resolve()) != str(paths_module.DATA_DIR.resolve()) if paths_module.DATA_DIR else True,
    }


def get_active_event() -> dict[str, Any] | None:
    active = read_active_event_file()
    if not active:
        return None
    try:
        event = get_event(active["event_id"])
    except EventAdminError:
        return None
    return {
        **event,
        "resolved_data_path": str(resolve_data_path(event["data_path"])),
    }


def is_admin_enabled() -> bool:
    return paths_module.ADMIN_DIR is not None and paths_module.ADMIN_DIR.is_dir()


def update_event(event_id: str, name: str | None = None) -> dict[str, Any]:
    registry = _load_events_registry()
    updated_event: dict[str, Any] | None = None
    for event in registry.get("events", []):
        if event["id"] != event_id:
            continue
        if name is not None:
            event["name"] = name
        event["updated_at"] = _now()
        updated_event = event
        break
    if updated_event is None:
        raise EventAdminError(f"event not found: {event_id}")
    _save_events_registry(registry)
    return updated_event


def delete_event(event_id: str) -> dict[str, Any]:
    event = get_event(event_id)
    if event.get("status") == "active":
        raise EventAdminError("cannot delete the active event; pause or activate another event first")
    return update_event_status(event_id, "deleted")


def _sanitize_template_input_name(name: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", name.strip()).strip("-").lower()
    return slug or "input"


def validate_event_inputs_schema(event_inputs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    validated: list[dict[str, Any]] = []
    for item in event_inputs:
        name = str(item.get("name", "")).strip()
        input_type = item.get("type")
        required = bool(item.get("required", False))
        if not name:
            raise EventAdminError("each event input requires a name")
        if input_type not in ("text", "file"):
            raise EventAdminError(f"invalid event input type for {name!r}: {input_type!r}")
        key = name.casefold()
        if key in seen:
            raise EventAdminError(f"duplicate event input name: {name}")
        seen.add(key)
        validated.append({"name": name, "type": input_type, "required": required})
    return validated


def validate_event_input_values(template: dict[str, Any], values: list[dict[str, Any]]) -> dict[str, str]:
    schema = template.get("event_inputs", [])
    schema_by_name = {item["name"]: item for item in schema}
    provided: dict[str, str] = {}

    for item in values:
        name = str(item.get("name", "")).strip()
        if not name:
            raise EventAdminError("each event input value requires a name")
        if name not in schema_by_name:
            raise EventAdminError(f"unknown event input: {name}")
        value = item.get("value")
        if value not in (None, ""):
            provided[name] = str(value)

    for field in schema:
        name = field["name"]
        if field.get("required") and field["type"] == "text" and name not in provided:
            raise EventAdminError(f"required event input missing: {name}")

    return provided


def validate_template_inputs(inputs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    validated: list[dict[str, Any]] = []
    for item in inputs:
        name = str(item.get("name", "")).strip()
        input_type = item.get("type")
        if not name:
            raise EventAdminError("each template input requires a name")
        if input_type not in ("text", "file"):
            raise EventAdminError(f"invalid input type for {name!r}: {input_type!r}")
        key = name.casefold()
        if key in seen:
            raise EventAdminError(f"duplicate template input name: {name}")
        seen.add(key)
        value = item.get("value")
        validated.append(
            {
                "name": name,
                "type": input_type,
                "value": None if value in (None, "") else str(value),
            }
        )
    return validated


def update_template(
    template_id: str,
    name: str | None = None,
    description: str | None = None,
    inputs: list[dict[str, Any]] | None = None,
    event_inputs: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    meta_file = admin_path("templates", template_id, "template.json")
    if not meta_file.is_file():
        raise EventAdminError(f"template not found: {template_id}")
    meta = _read_json(meta_file)
    if name is not None:
        meta["name"] = name
    if description is not None:
        meta["description"] = description
    if inputs is not None:
        meta["inputs"] = validate_template_inputs(inputs)
    if event_inputs is not None:
        meta["event_inputs"] = validate_event_inputs_schema(event_inputs)
    meta["updated_at"] = _now()
    _write_json_atomic(meta_file, meta)
    return meta


def save_event_input_file(event_id: str, input_name: str, filename: str, fileobj) -> str:
    event = get_event(event_id)
    template = get_template(event["template_id"])
    schema_by_name = {item["name"]: item for item in template.get("event_inputs", [])}
    if input_name not in schema_by_name:
        raise EventAdminError(f"unknown event input: {input_name}")
    if schema_by_name[input_name]["type"] != "file":
        raise EventAdminError(f"event input {input_name} is not a file field")

    event_data_dir = resolve_data_path(event["data_path"])
    slug = _sanitize_template_input_name(input_name)
    target_dir = event_data_dir / "userdata" / "event-inputs" / slug
    target_dir.mkdir(parents=True, exist_ok=True)
    safe_name = Path(filename).name
    if not safe_name:
        raise EventAdminError("uploaded file has no filename")
    target_file = target_dir / safe_name
    with open(target_file, "wb") as out:
        shutil.copyfileobj(fileobj, out)
    relative = Path("userdata", "event-inputs", slug, safe_name).as_posix()

    registry = _load_events_registry()
    for item in registry.get("events", []):
        if item["id"] != event_id:
            continue
        item.setdefault("event_inputs", {})[input_name] = relative
        item["updated_at"] = _now()
        break
    _save_events_registry(registry)
    return relative


def save_template_input_file(template_id: str, input_name: str, filename: str, fileobj) -> str:
    get_template(template_id)
    slug = _sanitize_template_input_name(input_name)
    target_dir = admin_path("templates", template_id, "userdata", "inputs", slug)
    target_dir.mkdir(parents=True, exist_ok=True)
    safe_name = Path(filename).name
    if not safe_name:
        raise EventAdminError("uploaded file has no filename")
    target_file = target_dir / safe_name
    with open(target_file, "wb") as out:
        shutil.copyfileobj(fileobj, out)
    relative = Path("userdata", "inputs", slug, safe_name)
    return relative.as_posix()


def delete_template(template_id: str) -> None:
    if template_id == "default":
        raise EventAdminError("cannot delete the default template")
    template_dir = admin_path("templates", template_id)
    if not template_dir.is_dir():
        raise EventAdminError(f"template not found: {template_id}")
    for event in list_events(include_deleted=True):
        if event.get("template_id") == template_id:
            raise EventAdminError(f"template is used by event {event['id']}")
    shutil.rmtree(template_dir)
