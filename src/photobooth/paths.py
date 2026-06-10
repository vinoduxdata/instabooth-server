"""Resolved filesystem paths for booth admin and event data."""

from __future__ import annotations

import json
import os
from pathlib import Path

ADMIN_DIR: Path | None = None
DATA_DIR: Path | None = None
INSTABOOTH_ROOT: Path | None = None


def _resolve_path(path: str | Path, base: Path) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate.resolve()
    return (base / candidate).resolve()


def configure(admin_dir: Path | None, data_dir: Path) -> None:
    global ADMIN_DIR, DATA_DIR, INSTABOOTH_ROOT

    DATA_DIR = data_dir.resolve()
    ADMIN_DIR = admin_dir.resolve() if admin_dir else None
    INSTABOOTH_ROOT = DATA_DIR.parent if ADMIN_DIR is None else ADMIN_DIR.parent


def resolve_data_path(path: str | Path) -> Path:
    if INSTABOOTH_ROOT is None:
        raise RuntimeError("paths not configured")
    return _resolve_path(path, INSTABOOTH_ROOT)


def admin_path(*parts: str) -> Path:
    if ADMIN_DIR is None:  # noqa: PLW0602
        raise RuntimeError("admin directory not configured")
    return ADMIN_DIR.joinpath(*parts)


def events_data_root() -> Path:
    if INSTABOOTH_ROOT is None:
        raise RuntimeError("paths not configured")
    return INSTABOOTH_ROOT / "instabooth-data" / "events"


def read_active_event_file() -> dict | None:
    if ADMIN_DIR is None:
        return None
    active_file = ADMIN_DIR / "active-event.json"
    if not active_file.is_file():
        return None
    return json.loads(active_file.read_text(encoding="utf-8"))


def write_active_event_file(event_id: str, data_path: str | Path) -> None:
    if ADMIN_DIR is None:
        raise RuntimeError("admin directory not configured")
    active_file = ADMIN_DIR / "active-event.json"
    payload = {
        "event_id": event_id,
        "data_path": os.path.relpath(resolve_data_path(data_path), INSTABOOTH_ROOT)  # type: ignore[arg-type]
        if INSTABOOTH_ROOT
        else str(data_path),
    }
    active_file.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def bootstrap_from_argv(argv: list[str] | None) -> list[str]:
    import argparse

    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--data-dir", type=str, default=None)
    parser.add_argument("--admin-dir", type=str, default=None)
    known, remaining = parser.parse_known_args(argv)

    cwd = Path.cwd().resolve()
    admin_dir: Path | None = None
    if known.admin_dir:
        admin_dir = Path(known.admin_dir).resolve()
    else:
        for candidate in (cwd.parent / "instabooth-admin", cwd / "instabooth-admin"):
            if candidate.is_dir():
                admin_dir = candidate.resolve()
                break

    data_dir: Path
    if known.data_dir:
        data_dir = Path(known.data_dir).resolve()
    elif admin_dir is not None:
        active = None
        active_file = admin_dir / "active-event.json"
        if active_file.is_file():
            active = json.loads(active_file.read_text(encoding="utf-8"))
        if active and active.get("data_path"):
            data_dir = _resolve_path(active["data_path"], admin_dir.parent)
        else:
            data_dir = cwd
    else:
        data_dir = cwd

    configure(admin_dir, data_dir)
    os.chdir(DATA_DIR)  # type: ignore[arg-type]
    return remaining
