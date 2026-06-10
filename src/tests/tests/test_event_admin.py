import json
import tempfile
from pathlib import Path

import pytest

from photobooth.paths import bootstrap_from_argv, configure
from photobooth.services import event_admin
from photobooth.services.event_admin import EventAdminError, merge_event_config


@pytest.fixture()
def admin_env(tmp_path: Path):
    admin_dir = tmp_path / "instabooth-admin"
    data_root = tmp_path / "instabooth-data"
    events_dir = data_root / "events"
    admin_dir.mkdir()
    data_root.mkdir()
    events_dir.mkdir()

    (admin_dir / "booth.json").write_text(
        json.dumps({"backends": {"group_backends": []}, "common": {"admin_password": "0000"}}),
        encoding="utf-8",
    )
    template_dir = admin_dir / "templates" / "default"
    (template_dir / "config").mkdir(parents=True)
    (template_dir / "userdata").mkdir()
    (template_dir / "template.json").write_text(
        json.dumps({"id": "default", "name": "Default"}),
        encoding="utf-8",
    )
    (template_dir / "config" / "config.json").write_text(
        json.dumps({"actions": {"image": []}, "uisettings": {"PRIMARY_COLOR": "#000000"}}),
        encoding="utf-8",
    )
    (admin_dir / "events.json").write_text(json.dumps({"events": []}), encoding="utf-8")

    event_data = tempfile.mkdtemp(prefix="event-data-", dir=tmp_path)
    configure(admin_dir, Path(event_data))
    bootstrap_from_argv(["--admin-dir", str(admin_dir), "--data-dir", event_data])
    yield admin_dir, data_root


def test_booth_config_file_mode_specific(admin_env):
    admin_dir, _ = admin_env
    (admin_dir / "booth.demo.json").write_text(
        json.dumps({"backends": {"group_backends": [{"backend_config": {"backend_type": "VirtualCamera"}}]}}),
        encoding="utf-8",
    )
    (admin_dir / "booth.prod.json").write_text(
        json.dumps({"backends": {"group_backends": [{"backend_config": {"backend_type": "Gphoto2"}}]}}),
        encoding="utf-8",
    )

    monkeypatch = pytest.MonkeyPatch()
    try:
        monkeypatch.setenv("INSTABOOTH_MODE", "demo")
        assert event_admin.booth_config_file().name == "booth.demo.json"
        assert event_admin._load_booth_config()["backends"]["group_backends"][0]["backend_config"]["backend_type"] == "VirtualCamera"

        monkeypatch.setenv("INSTABOOTH_MODE", "prod")
        assert event_admin.booth_config_file().name == "booth.prod.json"
        assert event_admin._load_booth_config()["backends"]["group_backends"][0]["backend_config"]["backend_type"] == "Gphoto2"
    finally:
        monkeypatch.undo()


def test_merge_event_config():
    merged = merge_event_config(
        {"actions": {"image": []}, "uisettings": {"PRIMARY_COLOR": "#111111"}},
        {"backends": {"group_backends": []}, "common": {"admin_password": "secret"}},
    )
    assert "actions" in merged
    assert merged["backends"]["group_backends"] == []
    assert merged["common"]["admin_password"] == "secret"


def test_create_and_activate_event(admin_env):
    admin_dir, data_root = admin_env
    event = event_admin.create_event("Test Wedding", "default")
    assert event["status"] == "draft"
    assert (data_root / "events" / event["id"] / "config" / "config.json").is_file()

    event_admin.update_event_status(event["id"], "published")
    result = event_admin.activate_event(event["id"])
    assert result["event"]["status"] == "active"
    assert (admin_dir / "active-event.json").is_file()


def test_invalid_status_transition(admin_env):
    event = event_admin.create_event("Bad Flow", "default")
    with pytest.raises(EventAdminError):
        event_admin.update_event_status(event["id"], "done")
