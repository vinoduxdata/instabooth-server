"""Read and write app configuration for active, event, and template scopes."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from .config.appconfig_ import AppConfig
from .event_admin import TEMPLATE_CONFIG_GROUPS
from .scoped_context import ScopeContext, ScopeError, resolve_scope

logger = logging.getLogger(__name__)


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _payload_for_scope(scope: ScopeContext, validated: AppConfig) -> dict[str, Any]:
    data = validated.model_dump(mode="json")
    if scope.kind == "template":
        return {group: data[group] for group in TEMPLATE_CONFIG_GROUPS if group in data}
    return data


def get_scoped_config(
    configurable: str,
    event_id: str | None = None,
    template_id: str | None = None,
    secrets_is_allowed: bool = False,
) -> dict[str, Any]:
    if configurable != "app":
        raise ScopeError("scoped configuration supports configurable=app only")

    scope = resolve_scope(event_id, template_id)
    on_disk = _read_json(scope.config_file)
    if scope.kind == "template" and not on_disk:
        on_disk = {group: getattr(AppConfig(), group).model_dump(mode="json") for group in TEMPLATE_CONFIG_GROUPS}
    elif not on_disk:
        on_disk = AppConfig().model_dump(mode="json")
    else:
        defaults = AppConfig().model_dump(mode="json")
        defaults.update(on_disk)
        on_disk = defaults

    if not secrets_is_allowed:
        on_disk.get("misc", {}).pop("secret_key", None)
        on_disk.get("common", {}).pop("admin_password", None)
    return on_disk


def set_scoped_config(
    configurable: str,
    updated_config: dict[str, Any],
    event_id: str | None = None,
    template_id: str | None = None,
) -> ScopeContext:
    if configurable != "app":
        raise ScopeError("scoped configuration supports configurable=app only")

    scope = resolve_scope(event_id, template_id)
    existing = _read_json(scope.config_file)
    if scope.kind == "template":
        merged = {**AppConfig().model_dump(mode="json"), **existing, **updated_config}
    else:
        merged = {**AppConfig().model_dump(mode="json"), **existing, **updated_config}

    validated = AppConfig.model_validate(merged)
    _write_json(scope.config_file, _payload_for_scope(scope, validated))
    return scope


def reset_scoped_config(
    configurable: str,
    event_id: str | None = None,
    template_id: str | None = None,
) -> None:
    if configurable != "app":
        raise ScopeError("scoped configuration supports configurable=app only")

    scope = resolve_scope(event_id, template_id)
    validated = AppConfig()
    _write_json(scope.config_file, _payload_for_scope(scope, validated))
