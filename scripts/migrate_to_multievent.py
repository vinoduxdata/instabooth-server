#!/usr/bin/env python3
"""One-time migration: scaffold instabooth-admin from an existing instabooth-data folder."""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

RUNTIME_DIRS = ("cache", "config", "database", "log", "media", "recycle", "tmp", "userdata")


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _rel_data_path(data_dir_name: str, event_id: str = "default") -> str:
    return f"{data_dir_name}/events/{event_id}"


def _move_legacy_runtime_to_default_event(data_dir: Path) -> Path:
    default_event_dir = data_dir / "events" / "default"
    legacy_config = data_dir / "config" / "config.json"
    default_config = default_event_dir / "config" / "config.json"

    if default_config.is_file():
        return default_event_dir

    if not legacy_config.is_file():
        raise SystemExit(f"missing config file: {legacy_config} or {default_config}")

    default_event_dir.mkdir(parents=True, exist_ok=True)
    for name in RUNTIME_DIRS:
        src = data_dir / name
        if not src.exists():
            continue
        dst = default_event_dir / name
        if dst.exists():
            shutil.rmtree(dst) if dst.is_dir() else dst.unlink()
        shutil.move(str(src), str(dst))

    return default_event_dir


def migrate(instabooth_root: Path, data_dir_name: str = "instabooth-data", admin_dir_name: str = "instabooth-admin") -> None:
    root = instabooth_root.resolve()
    data_dir = root / data_dir_name
    admin_dir = root / admin_dir_name

    default_event_dir = _move_legacy_runtime_to_default_event(data_dir)
    config_file = default_event_dir / "config" / "config.json"
    if not config_file.is_file():
        raise SystemExit(f"missing config file: {config_file}")

    config = json.loads(config_file.read_text(encoding="utf-8"))
    booth = {
        "common": config.get("common", {}),
        "backends": config.get("backends", {}),
        "hardwareinputoutput": config.get("hardwareinputoutput", {}),
        "misc": config.get("misc", {}),
    }
    template_config = {
        "actions": config.get("actions", {}),
        "share": config.get("share", {}),
        "mediaprocessing": config.get("mediaprocessing", {}),
        "uisettings": config.get("uisettings", {}),
    }

    admin_dir.mkdir(parents=True, exist_ok=True)
    (admin_dir / "booth.json").write_text(json.dumps(booth, indent=2) + "\n", encoding="utf-8")

    template_dir = admin_dir / "templates" / "default"
    (template_dir / "config").mkdir(parents=True, exist_ok=True)
    (template_dir / "userdata").mkdir(parents=True, exist_ok=True)
    (template_dir / "template.json").write_text(
        json.dumps(
            {
                "id": "default",
                "name": "Default",
                "description": "Migrated from single-event setup",
                "version": 1,
                "created_at": _now(),
                "updated_at": _now(),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (template_dir / "config" / "config.json").write_text(json.dumps(template_config, indent=2) + "\n", encoding="utf-8")

    userdata_src = default_event_dir / "userdata"
    if userdata_src.is_dir():
        for item in userdata_src.iterdir():
            if item.name == "demoassets":
                continue
            target = template_dir / "userdata" / item.name
            if item.is_dir():
                shutil.copytree(item, target, dirs_exist_ok=True)
            else:
                shutil.copy2(item, target)

    default_data_path = _rel_data_path(data_dir_name)
    now = _now()
    (admin_dir / "events.json").write_text(
        json.dumps(
            {
                "events": [
                    {
                        "id": "default",
                        "name": "Default Event",
                        "template_id": "default",
                        "status": "active",
                        "data_path": default_data_path,
                        "created_at": now,
                        "updated_at": now,
                    }
                ]
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (admin_dir / "active-event.json").write_text(
        json.dumps({"event_id": "default", "data_path": default_data_path}, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"migration complete: {admin_dir}")
    print(f"default event data: {default_event_dir}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate single-event instabooth-data to instabooth-admin layout")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2].parent)
    args = parser.parse_args()
    migrate(args.root)


if __name__ == "__main__":
    main()
