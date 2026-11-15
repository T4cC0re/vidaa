"""Tests for the /vidaa/exploit browser-bridge HTTP surface."""

from __future__ import annotations

import json

import pytest

from custom_components.vidaa.http import (
    BRIDGE_PAGE_PATH,
    BRIDGE_REPORT_PATH,
    load_bridge_page,
    normalize_report,
    summarize_report,
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
