import os
from pathlib import Path

import pytest

from photobooth.services.hotspot import generate_wifi_qr_png, wifi_join_payload


def test_wifi_join_payload_escapes_special_characters():
    payload = wifi_join_payload("Insta;Booth", "pa:ss,word")
    assert payload == r"WIFI:T:WPA;S:Insta\;Booth;P:pa\:ss\,word;H:false;;"


def test_generate_wifi_qr_png(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("INSTABOOTH_HOTSPOT_SSID", "InstaBooth")
    monkeypatch.setenv("INSTABOOTH_HOTSPOT_PASSWORD", "instabooth-guest")
    destination = tmp_path / "auto-wifi-qr.png"
    generate_wifi_qr_png("InstaBooth", "instabooth-guest", destination)
    assert destination.is_file()
    assert destination.stat().st_size > 0
