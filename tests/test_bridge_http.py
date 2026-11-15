"""Tests for the /vidaa/exploit browser-bridge HTTP surface."""

from __future__ import annotations

import json

import pytest

from custom_components.vidaa.http import (
    BRIDGE_PAGE_PATH,
    BRIDGE_REPORT_PATH,
    _publish_report,
    build_report_summary,
    get_bridge_summary,
    load_bridge_page,
    normalize_report,
    register_bridge_entity,
    summarize_report,
    unregister_bridge_entity,
)


def test_bridge_page_shipped_and_served_paths() -> None:
    html = load_bridge_page()
    assert len(html) > 1000
    assert BRIDGE_PAGE_PATH == "/vidaa/exploit"
    assert BRIDGE_REPORT_PATH == "/vidaa/exploit/report"
    assert BRIDGE_REPORT_PATH in html


def test_bridge_page_is_read_only() -> None:
    """The shipped page must never contain write-capable vendor APIs."""
    html = load_bridge_page()
    for banned in ("fetchFile", "fileWrite", "SetParam", "installApp", "opkg",
                   "notify_value_changed"):
        assert banned not in html, f"page references write primitive {banned}"


def test_bridge_page_service_allowlist() -> None:
    html = load_bridge_page()
    for allowed in ("initialData", "getOSVersion", "fileRead", "getInstalledPkgs", "getVersionStatus"):
        assert allowed in html


def test_normalize_report_rejects_bad_input() -> None:
    assert normalize_report("") is None
    assert normalize_report("not json") is None
    assert normalize_report("[1,2,3]") is None
    assert normalize_report(json.dumps({"x": 1})) == {"x": 1}
    assert normalize_report('{"x":"' + "A" * (600 * 1024) + '"}') is None


def test_summarize_report_bounds_size_and_covers_reads() -> None:

    report = {
        "t": "2026-11-15T00:00:00Z",
        "ua": "Chromium 111",
        "bridge_http": {"9009": "answering", "9888": "ERR"},
        "services": {"initialData": {"modelName": "X", "softwareVersion": "Y", "chipsetName": "Z"}},
        "fileread_variant": "array",
        "reads": {
            "../proc/self/status": {"ok": "Uid:\t314\t314\t314\t314\nGroups:\t616 " + "B" * 2000},
            "../proc/mounts": {"ok": "ro stuff"},
            "../var/run/superwatch_socket": {"err": "EACCES denied"},
        },
        "bridge_globals": {"TvInfo_getParam": "function"},
        "tvinfo_setters": ["setBrightness", "setContrast"],
        "pkglist_trunc": {"count": 3},
        "errors": [],
    }
    lines = summarize_report(report)
    assert any("Uid:" in line for line in lines)
    assert any("EACCES" in line for line in lines)
    assert any("setBrightness" in line for line in lines)
    assert all(len(line) < 600 for line in lines)


@pytest.mark.anyio
async def test_bridge_setup_skips_without_http_component() -> None:
    """Headless/stub environments must not fail — the views simply skip."""
    from types import SimpleNamespace

    from custom_components.vidaa.http import async_setup_bridge_http

    hass = SimpleNamespace(data={}, http=None, config=SimpleNamespace(path=lambda p: p))
    result = await async_setup_bridge_http(hass)
    assert result is False


def _fake_hass(tmp_path=None) -> object:
    from pathlib import Path
    from types import SimpleNamespace

    base = Path(tmp_path or ".")
    return SimpleNamespace(data={}, config=SimpleNamespace(path=lambda p: str(base / p)))


def test_build_report_summary_bounds_and_maps_fields() -> None:
    report = {
        "t": "2026-11-15T00:00:00Z",
        "ua": "Chromium 111" + "x" * 500,
        "bridge_http": {"9009": "answering", "9888": "ERR x" * 100},
        "wss9888": "open",
        "fileread_variant": "array",
        "reads": {f"../p/{i}": {"ok": "A" * 2000} for i in range(40)},
        "services": {"initialData": {"modelName": "85U75LEVS"}},
        "bridge_globals": {"vowOS": "object"},
        "tvinfo_setters": ["setBrightness"] * 200,
        "pkglist_trunc": {"count": 9, "has_jsservice_basic": True},
        "errors": ["e1"],
    }
    summary = build_report_summary(report, "2026-11-15T00:00:01Z")
    assert summary["received"] == "2026-11-15T00:00:01Z"
    assert summary["fileread_variant"] == "array"
    assert len(summary["reads"]) <= 20
    assert all(len(str(v.get("ok"))) <= 500 for v in summary["reads"].values())
    assert summary["initialData"] == {"modelName": "85U75LEVS"}
    assert len(json.dumps(summary)) < 20000


def test_publish_report_stores_summaries_and_republishes_entities(tmp_path) -> None:
    hass = _fake_hass(tmp_path)

    class FakeEntity:
        writes = 0

        def async_write_ha_state(self) -> None:
            FakeEntity.writes += 1

    ent = FakeEntity()
    register_bridge_entity(hass, ent)
    _publish_report(hass, {"t": "x", "url": "http://tv/", "reads": {"../proc/self/status": {"ok": "Uid:\t314"}}})
    assert FakeEntity.writes == 1
    summary = get_bridge_summary(hass)
    assert summary is not None
    assert "Uid:" in str(summary["reads"]["../proc/self/status"]["ok"])
    unregister_bridge_entity(hass, ent)
    _publish_report(hass, {"t": "y", "url": "http://tv/"})
    assert FakeEntity.writes == 1


def test_get_bridge_summary_absent_returns_none() -> None:
    assert get_bridge_summary(_fake_hass()) is None
