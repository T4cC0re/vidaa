"""Tests for the /vidaa/exploit browser-bridge HTTP surface."""

from __future__ import annotations

import json

import pytest

from custom_components.vidaa.http import (
    BRIDGE_PAGE_PATH,
    BRIDGE_PAGE_PUT_PATH,
    BRIDGE_REPORT_PATH,
    BRIDGE_TASK_PATH,
    _publish_report,
    build_report_summary,
    get_bridge_page_key,
    get_bridge_summary,
    get_bridge_task_meta,
    get_latest_report,
    load_bridge_page,
    next_bridge_task,
    normalize_report,
    page_status,
    read_bridge_page,
    register_bridge_entity,
    set_bridge_task,
    summarize_report,
    unregister_bridge_entity,
    validate_page_body,
    validate_task,
    write_bridge_page,
)


def test_bridge_page_shipped_and_served_paths() -> None:
    html = load_bridge_page()
    assert len(html) > 1000
    assert BRIDGE_PAGE_PATH == "/vidaa/exploit"
    assert BRIDGE_REPORT_PATH == "/vidaa/exploit/report"
    assert BRIDGE_PAGE_PUT_PATH == "/vidaa/exploit/page"
    assert BRIDGE_REPORT_PATH in html


def test_bridge_page_is_read_only() -> None:
    """The shipped page must never contain un-gated write-capable vendor APIs."""
    html = load_bridge_page()
    for banned in ("fileWrite", "SetParam", "installApp", "opkg",
                   "notify_value_changed"):
        assert banned not in html, f"page references write primitive {banned}"
    assert "fetchFile url must be same-origin" in html  # fetchFile is origin-pinned


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
    assert all(len(line) < 900 for line in lines)


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


def test_validate_page_body() -> None:
    assert validate_page_body("") == "empty body"
    assert "HTML document" in (validate_page_body("console.log(1)") or "")
    assert validate_page_body("  \n<!DOCTYPE html><html></html>") is None
    assert validate_page_body("<html><body>ok</body></html>") is None
    assert "exceeds" in (validate_page_body("<!DOCTYPE html>" + "A" * (600 * 1024)) or "")


def test_page_override_roundtrip(tmp_path) -> None:
    hass = _fake_hass(tmp_path)
    html, source = read_bridge_page(hass)
    assert source == "bundled"
    assert len(html) > 1000

    meta = write_bridge_page(hass, "<!DOCTYPE html>\n<html>marker-v3</html>")
    assert meta["source"] == "override"
    assert meta["sha256_12"]
    html, source = read_bridge_page(hass)
    assert source == "override"
    assert "marker-v3" in html

    status = page_status(hass)
    assert status["source"] == "override"
    assert status["bytes"] > 0

    # override file removed -> bundled again
    (tmp_path / "vidaa_bridge" / "recon.html").unlink()
    _html, source = read_bridge_page(hass)
    assert source == "bundled"


def test_page_key_absent_without_setup() -> None:
    assert get_bridge_page_key(_fake_hass()) is None
    assert get_bridge_page_key(None) is None


def test_page_djb2_stable_and_matches_js_algorithm(tmp_path) -> None:
    from custom_components.vidaa.http import page_djb2

    hass = _fake_hass(tmp_path)
    sha1 = page_djb2(hass)
    html = load_bridge_page()
    h = 5381
    for ch in html:  # ASCII-only page guarantees UTF-8 bytes == code units
        h = (h * 33 + ord(ch)) & 0xFFFFFFFF
    assert sha1 == f"{h:08x}"
    assert page_djb2(hass) == sha1


def test_bridge_task_path_constant() -> None:
    assert BRIDGE_TASK_PATH == "/vidaa/exploit/task"


def test_validate_task_matrix() -> None:
    assert validate_task({"op": "fileRead", "path": "../proc/uptime"}) is None
    assert validate_task({"op": "svc", "svc": "tvinfo", "api": "initialData"}) is None
    assert validate_task({"op": "native", "api": "fileRead", "args": {}}) is None
    assert validate_task({"op": "globals", "names": ["vowOS"]}) is None
    assert validate_task({"op": "enumerate", "filter": "Picture"}) is None
    assert validate_task({"op": "sleep", "ms": 500}) is None
    assert validate_task({"op": "jsapi", "fn": "Hisense_GetPictureInfo"}) is None
    assert validate_task({"op": "jsapi", "fn": "His_getSource", "args": []}) is None
    assert validate_task({"op": "batch", "ops": [{"op": "sleep", "ms": 1},
                                                 {"op": "fileRead", "path": "../x"}]}) is None
    assert validate_task({"op": "ws", "target": "wss://localhost:9888",
                          "messages": [{"path": "phoenix://service/basic/fetcher", "method": "start",
                                        "parameters": {}, "session": 1, "timeout": 10}]}) is None
    assert validate_task({"op": "ws", "target": "ws://127.0.0.1:9009",
                          "messages": [{"path": "phoenix://service/hiutils", "method": "callAPI",
                                        "parameters": {"api": "fileRead"}, "session": 2}]}) is None


def test_validate_task_rejects_write_and_out_of_scope() -> None:
    assert "not allowed" in (validate_task({"op": "eval"}) or "")
    assert "args object" in (validate_task({"op": "svc", "svc": "basic/fetcher", "api": "fetchFile"}) or "")
    assert "getter" in (validate_task({"op": "jsapi", "fn": "Hisense_SetPictureMode"}) or "")
    assert "getter" in (validate_task({"op": "jsapi", "fn": "TvInfo_setParam"}) or "")
    assert "getter" in (validate_task({"op": "jsapi", "fn": "His_restart"}) or "")
    # fetchFile: gated to payload endpoint + chain targets only
    good_fetch = {"op": "svc", "svc": "basic/fetcher", "api": "fetchFile",
                  "args": {"url": "http://10.0.0.5:8123/vidaa/exploit/p/sw2.js",
                           "directory": "/APPS/installer.ipk", "permission": 420}}
    assert validate_task(good_fetch) is None
    assert "/vidaa/exploit/p/" in (validate_task({"op": "svc", "svc": "basic/fetcher", "api": "fetchFile",
                                                  "args": {"url": "http://evil.example/x.js",
                                                           "directory": "/APPS/installer.ipk"}}) or "")
    assert "allowlisted" in (validate_task({"op": "svc", "svc": "basic/fetcher", "api": "fetchFile",
                                            "args": {"url": "http://h:8123/vidaa/exploit/p/a",
                                                     "directory": "/etc/passwd"}}) or "")
    assert validate_task({"op": "svc", "svc": "basic/fetcher", "api": "fetchFile",
                          "args": {"url": "http://h/vidaa/exploit/p/a",
                                   "directory": "/APPS/installer.ipk", "permission": 999}}) is not None
    # fetchFile over ws framing is not the canonical channel -> rejected
    assert "svc op" in (validate_task({"op": "ws", "target": "wss://localhost:9888",
                                       "messages": [{"path": "phoenix://service/basic/fetcher",
                                                     "method": "callAPI",
                                                     "parameters": {"api": "fetchFile", "args": {}}}]}) or "")
    # fn: superwatch proxy op, install/uninstall framing only
    assert validate_task({"op": "fn", "fnpath": "basic/fetch/sw2",
                          "list": ["90:83:90;re.installer",
                                   "91:82:91;/APPS/installer.ipk;re.installer;"]}) is None
    assert "fnpath" in (validate_task({"op": "fn", "fnpath": "basic/fetch/evil",
                                       "list": ["90:82:90;x"]}) or "")
    assert "framing" in (validate_task({"op": "fn", "fnpath": "basic/fetch/sw2",
                                        "list": ["90:99:90;whatever"]}) or "")
    assert validate_task({"op": "fn", "fnpath": "basic/fetch/sw2", "list": []}) is not None
    assert validate_task({"op": "fn", "fnpath": "basic/fetch/sw2",
                          "list": ["90:82:90;`rm -rf /`"]}) is not None
    assert validate_task({"op": "fn", "fnpath": "basic/fetch/sw2",
                          "list": ["90:83:90;re.installer", "91:82:91;/APPS/installer.ipk;re.installer;"]}) is None
    assert "not allowed" in (validate_task({"op": "svc", "svc": "basic/fetcher", "api": "fetchFile"}) or "")
    assert "not allowed" in (validate_task({"op": "svc", "svc": "tvinfo", "api": "setBrightness"}) or "")
    assert "native lane" in (validate_task({"op": "native", "api": "fileWrite"}) or "")
    assert validate_task({"op": "fileRead"}) is not None          # missing string path
    assert validate_task({"op": "sleep", "ms": 99999}) is not None
    assert "ws target" in (validate_task({"op": "ws", "target": "wss://evil.example:9999",
                                          "messages": []}) or "")
    assert "not allowed" in (validate_task({"op": "ws", "target": "wss://localhost:9888",
                                            "messages": [{"path": "phoenix://service/pkgmgr",
                                                          "method": "callAPI",
                                                          "parameters": {"api": "installApp"}}]}) or "")
    assert validate_task({"op": "ws", "target": "wss://localhost:9888",
                          "messages": [{"path": "phoenix://service/tvinfo", "method": "start"}]}) is None
    assert "not allowed" in (validate_task({"op": "ws", "target": "wss://localhost:9888",
                                            "messages": [{"path": "phoenix://service/tvinfo",
                                                          "method": "callAPI",
                                                          "parameters": {"api": "setBrightness"}}]}) or "")
    assert validate_task("nope") is not None


def test_task_rev_flow(tmp_path) -> None:
    hass = _fake_hass(tmp_path)
    assert next_bridge_task(hass, 0) is None
    meta = set_bridge_task(hass, {"op": "fileRead", "path": "../proc/uptime"})
    assert meta["rev"] == 1 and meta["op"] == "fileRead"
    assert get_bridge_task_meta(hass)["rev"] == 1
    pending = next_bridge_task(hass, 0)
    assert pending and pending["rev"] == 1 and pending["task"]["path"] == "../proc/uptime"
    assert get_bridge_task_meta(hass)["delivered"] is not None
    assert next_bridge_task(hass, 1) is None            # already seen
    meta2 = set_bridge_task(hass, {"op": "globals", "names": ["vowOS"]})
    assert meta2["rev"] == 2


def test_get_latest_report_picks_newest(tmp_path) -> None:
    hass = _fake_hass(tmp_path)
    assert get_latest_report(hass) is None
    _publish_report(hass, {"t": "old", "url": "a"})
    hass.data["vidaa"]["bridge_reports"]["a"]["received"] = "2026-01-01T00:00:00+00:00"
    _publish_report(hass, {"t": "new", "url": "b"})
    hass.data["vidaa"]["bridge_reports"]["b"]["received"] = "2026-11-15T00:00:00+00:00"
    latest = get_latest_report(hass)
    assert latest and latest["report"]["t"] == "new"


def test_payload_roundtrip(tmp_path) -> None:
    from custom_components.vidaa.http import read_payload, write_payload

    hass = _fake_hass(tmp_path)
    meta = write_payload(hass, "installer.ipk", b"ar-chive-bytes")
    assert meta["bytes"] == 14 and meta["sha256_12"]
    assert read_payload(hass, "installer.ipk") == b"ar-chive-bytes"
    assert read_payload(hass, "missing.ipk") is None
    assert read_payload(hass, "../escape") is None
    try:
        write_payload(hass, "bad name!", b"x")
        raise AssertionError("name accepted")
    except ValueError:
        pass
