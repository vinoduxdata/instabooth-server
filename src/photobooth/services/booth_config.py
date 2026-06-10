"""Read and write booth-global configuration (instabooth-admin/booth.json)."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import jsonref
from pydantic import BaseModel

from .. import CONFIG_PATH
from .config.baseconfig import SchemaTypes
from .config.groups.cameras import GroupCameras
from .config.groups.common import GroupCommon
from .config.groups.hardwareinputoutput import GroupHardwareInputOutput
from .config.groups.hotspot import GroupHotspot
from .config.groups.misc import GroupMisc
from .event_admin import BOOTH_CONFIG_GROUPS, EventAdminError, _load_booth_config, _require_admin, booth_config_file
from .event_admin import _write_json_atomic as write_json_atomic

logger = logging.getLogger(__name__)


class BoothConfigError(Exception):
    pass


class BoothConfig(BaseModel):
    common: GroupCommon = GroupCommon()
    backends: GroupCameras = GroupCameras()
    hardwareinputoutput: GroupHardwareInputOutput = GroupHardwareInputOutput()
    misc: GroupMisc = GroupMisc()
    hotspot: GroupHotspot = GroupHotspot()

    @classmethod
    def _fix_single_allof(cls, dictionary: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(dictionary, dict):
            raise ValueError("Input must be a dictionary")

        for key, value in list(dictionary.items()):
            if key == "allOf" and len(value) == 1 and isinstance(value[0], dict):
                for allof_key, allof_value in list(value[0].items()):
                    dictionary[allof_key] = allof_value
                del dictionary["allOf"]
            elif isinstance(value, dict):
                cls._fix_single_allof(value)

        return dictionary

    @classmethod
    def get_schema(cls, schema_type: SchemaTypes = "default") -> dict[str, Any]:
        schema = cls.model_json_schema()
        cls._fix_single_allof(schema)
        if schema_type == "dereferenced":
            return jsonref.loads(json.dumps(schema))
        return schema

    @classmethod
    def from_disk(cls) -> BoothConfig:
        on_disk = _load_booth_config()
        defaults = cls().model_dump(mode="json")
        defaults.update(on_disk)
        return cls.model_validate(defaults)

    def to_disk_payload(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


def _booth_file() -> Path:
    return booth_config_file()


def apply_booth_config_on_startup() -> Path | None:
    """Merge booth-global groups into the active event config before services start."""
    try:
        _require_admin()
    except EventAdminError:
        return None
    data = _load_booth_config()
    if not data:
        return None
    return sync_booth_groups_to_active_event(data)


def get_booth_config(*, secrets_is_allowed: bool = False) -> dict[str, Any]:
    try:
        _booth_file()
    except EventAdminError as exc:
        raise BoothConfigError(str(exc)) from exc

    data = BoothConfig.from_disk().model_dump(context={"secrets_is_allowed": secrets_is_allowed}, mode="json")
    if not secrets_is_allowed:
        data.get("misc", {}).pop("secret_key", None)
        data.get("common", {}).pop("admin_password", None)
    return data


def set_booth_config(updated_config: dict[str, Any]) -> dict[str, Any]:
    try:
        booth_file = _booth_file()
    except EventAdminError as exc:
        raise BoothConfigError(str(exc)) from exc

    existing = _load_booth_config()
    merged = {**BoothConfig().model_dump(mode="json"), **existing, **updated_config}
    validated = BoothConfig.model_validate(merged)
    write_json_atomic(booth_file, validated.to_disk_payload())
    sync_booth_groups_to_active_event(validated.to_disk_payload())
    return validated.model_dump(context={"secrets_is_allowed": True}, mode="json")


def reset_booth_config() -> dict[str, Any]:
    try:
        booth_file = _booth_file()
    except EventAdminError as exc:
        raise BoothConfigError(str(exc)) from exc

    validated = BoothConfig()
    write_json_atomic(booth_file, validated.to_disk_payload())
    sync_booth_groups_to_active_event(validated.to_disk_payload())
    return validated.model_dump(context={"secrets_is_allowed": True}, mode="json")


def sync_booth_groups_to_active_event(booth_data: dict[str, Any]) -> Path | None:
    config_file = Path(CONFIG_PATH) / "config.json"
    if not config_file.is_file():
        return None

    existing = json.loads(config_file.read_text(encoding="utf-8"))
    for group in BOOTH_CONFIG_GROUPS:
        if group in booth_data:
            existing[group] = booth_data[group]
    config_file.write_text(json.dumps(existing, indent=2) + "\n", encoding="utf-8")
    return config_file


def list_booth_configurables() -> list[str]:
    return ["app"]
