"""Resolve filesystem scope for events, templates, and the active runtime."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from .. import CONFIG_PATH, USERDATA_PATH
from .. import paths as paths_module
from ..paths import admin_path, resolve_data_path
from .event_admin import EventAdminError, get_active_event, get_event


@dataclass
class ScopeContext:
    kind: Literal["active", "event", "template"]
    root: Path
    config_file: Path
    userdata_dir: Path
    is_runtime_active: bool


class ScopeError(Exception):
    pass


def resolve_scope(event_id: str | None = None, template_id: str | None = None) -> ScopeContext:
    if event_id and template_id:
        raise ScopeError("cannot set both event_id and template_id")

    if template_id:
        root = admin_path("templates", template_id)
        if not root.is_dir():
            raise ScopeError(f"template not found: {template_id}")
        return ScopeContext(
            kind="template",
            root=root.resolve(),
            config_file=(root / "config" / "config.json").resolve(),
            userdata_dir=(root / "userdata").resolve(),
            is_runtime_active=False,
        )

    if event_id:
        try:
            event = get_event(event_id)
        except EventAdminError as exc:
            raise ScopeError(str(exc)) from exc
        root = resolve_data_path(event["data_path"])
        if not root.is_dir():
            raise ScopeError(f"event data directory missing: {root}")
        active = get_active_event()
        is_active = bool(
            active
            and active.get("id") == event_id
            and paths_module.DATA_DIR is not None
            and root.resolve() == paths_module.DATA_DIR.resolve()
        )
        return ScopeContext(
            kind="event",
            root=root.resolve(),
            config_file=(root / "config" / "config.json").resolve(),
            userdata_dir=(root / "userdata").resolve(),
            is_runtime_active=is_active,
        )

    runtime_root = (paths_module.DATA_DIR or Path.cwd()).resolve()
    return ScopeContext(
        kind="active",
        root=runtime_root,
        config_file=Path(CONFIG_PATH, "config.json").resolve(),
        userdata_dir=Path(USERDATA_PATH).resolve(),
        is_runtime_active=True,
    )


def sanitize_under_root(filepath: str, root: Path) -> Path:
    root = root.resolve()
    relative = filepath.removeprefix("/").removeprefix("./")
    candidate = (root / relative).resolve()
    if candidate != root and root not in candidate.parents:
        raise ValueError(f"path outside scope: {filepath}")
    return candidate
