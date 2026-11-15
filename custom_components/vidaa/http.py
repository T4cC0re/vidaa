"""HTTP surface for the on-TV browser bridge (``/vidaa/exploit``).

Serves the read-only recon page at ``GET /vidaa/exploit`` and receives the
TV's report at ``POST /vidaa/exploit/report``.

Security notes (by design, read before changing):
- ``/vidaa/exploit`` and its ``/report`` sink are ``requires_auth=False`` so
  the TV's browser can open them without an HA login. The page itself is
  static and carries no secrets.
- The report sink is WRITE-ONLY, body-size-capped and stores at most the
  latest report per reporting client. Nothing is ever sent from the sink back
  to the TV.
- Full reports are written to ``<config>/vidaa_bridge_report.json`` (for
  diagnostics/offline analysis), summarized to the log (WARNING level, so it
  survives HAOS journald filtering) and published as the bounded
  ``bridge_report`` attribute on the media player entity.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, ClassVar

from homeassistant.core import HomeAssistant

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

BRIDGE_PAGE_PATH = "/vidaa/exploit"
BRIDGE_REPORT_PATH = "/vidaa/exploit/report"
MAX_REPORT_BYTES = 512 * 1024

_BRIDGE_PAGE = Path(__file__).parent / "bridge" / "recon.html"

BRIDGE_DATA_KEY = "bridge_reports"
BRIDGE_SUMMARY_KEY = "bridge_summary"
BRIDGE_ENTITY_KEY = "bridge_entities"


def load_bridge_page() -> str:
    """Return the recon page HTML shipped inside the package."""
    return _BRIDGE_PAGE.read_text(encoding="utf-8")


def normalize_report(body: str) -> dict[str, Any] | None:
    """Parse and bound a posted report body; None when unusable."""
    if not body or len(body.encode("utf-8", "ignore")) > MAX_REPORT_BYTES:
        return None
    try:
        data = json.loads(body)
    except (ValueError, TypeError):
        return None
    return data if isinstance(data, dict) else None


def summarize_report(report: dict[str, Any]) -> list[str]:
    """Bounded single-line log summary lines for a report (log-safe sizes)."""
    lines = [f"bridge report at {report.get('t', '?')}"]
    ua = str(report.get("ua", ""))[:160]
    lines.append(f"  ua: {ua}")
    lines.append(f"  transports: {json.dumps(report.get('bridge_http', {}))[:200]} wss={str(report.get('wss9888'))[:40]}")
    initial = report.get("services", {}).get("initialData") if isinstance(report.get("services"), dict) else None
    lines.append(f"  initialData: {json.dumps(initial, default=str)[:300]}")
    lines.append(f"  fileread_variant: {report.get('fileread_variant')}")
    reads = report.get("reads") or {}
    for key in ("../proc/self/status", "../proc/mounts", "../proc/version", "../proc/net/unix",
                "../var/run/superwatch_socket", "../var/local",
                "../APPS/pkgs/tv.vidaa.jsservice.basic/CHA/services/serviceList.json"):
        entry = reads.get(key)
        if isinstance(entry, dict):
            value = entry.get("ok") if entry.get("ok") is not None else entry.get("err")
            lines.append(f"  read {key}: {str(value)[:400]}")
    lines.append(f"  globals: {json.dumps(report.get('bridge_globals', {}))[:300]}")
    lines.append(f"  tvinfo_setters: {json.dumps(report.get('tvinfo_setters'))[:400]}")
    lines.append(f"  pkgmgr: {json.dumps(report.get('pkglist_trunc'), default=str)[:400]}")
    lines.append(f"  errors: {json.dumps(report.get('errors', []), default=str)[:300]}")
    return lines


def _store_report(hass: HomeAssistant, report: dict[str, Any], received: str | None = None) -> None:
    """Persist the latest report per reporting client id."""
    store: dict[str, Any] = hass.data.setdefault(DOMAIN, {}).setdefault(BRIDGE_DATA_KEY, {})
    client = str(report.get("url") or report.get("ua") or "unknown")[:120]
    store[client] = {"received": received or datetime.now(UTC).isoformat(), "report": report}
    try:
        payload = json.dumps({k: v for k, v in store.items()}, indent=2, ensure_ascii=False, default=str)
        Path(hass.config.path("vidaa_bridge_report.json")).write_text(payload, encoding="utf-8")
    except OSError as err:
        _LOGGER.debug("Could not persist bridge report file: %s", err)


def _bounded_dict(value: Any, max_items: int, value_len: int) -> dict[str, str]:
    """Stringify a mapping with per-value length caps (no JSON round-trip)."""
    if not isinstance(value, dict):
        return {}
    return {str(k)[:120]: str(v)[:value_len] for k, v in list(value.items())[:max_items]}


def build_report_summary(report: dict[str, Any], received: str) -> dict[str, Any]:
    """Build a bounded summary of a report for entity attributes (size-capped)."""
    reads = report.get("reads") or {}
    clipped_reads: dict[str, Any] = {}
    for key, entry in list(reads.items())[:20]:
        if isinstance(entry, dict):
            clipped_reads[str(key)[:120]] = {
                "ok": str(entry.get("ok"))[:500] if entry.get("ok") is not None else None,
                "err": str(entry.get("err"))[:150] if entry.get("err") is not None else None,
            }
        else:
            clipped_reads[str(key)[:120]] = str(entry)[:150]
    services = report.get("services") if isinstance(report.get("services"), dict) else {}
    initial = services.get("initialData")
    return {
        "received": received,
        "t": str(report.get("t", ""))[:40],
        "ua": str(report.get("ua", ""))[:160],
        "bridge_http": _bounded_dict(report.get("bridge_http"), 10, 200),
        "wss9888": str(report.get("wss9888"))[:80],
        "fileread_variant": str(report.get("fileread_variant"))[:40],
        "reads": clipped_reads,
        "initialData": _bounded_dict(initial, 40, 150) if isinstance(initial, dict) else str(initial)[:300],
        "bridge_globals": _bounded_dict(report.get("bridge_globals"), 20, 40),
        "tvinfo_setters": [str(s)[:80] for s in (report.get("tvinfo_setters") or [])[:40]]
        if isinstance(report.get("tvinfo_setters"), list) else [],
        "pkglist": _bounded_dict(report.get("pkglist_trunc"), 6, 300)
        if isinstance(report.get("pkglist_trunc"), dict) else str(report.get("pkglist_trunc"))[:300],
        "errors": [str(e)[:100] for e in (report.get("errors") or [])[:10]]
        if isinstance(report.get("errors"), list) else [],
    }


def get_bridge_summary(hass: HomeAssistant) -> dict[str, Any] | None:
    """Latest bounded bridge-report summary, for entity attributes."""
    data = getattr(hass, "data", None)
    if not isinstance(data, dict):
        return None
    summary = data.get(DOMAIN, {}).get(BRIDGE_SUMMARY_KEY)
    return summary if isinstance(summary, dict) else None


def register_bridge_entity(hass: HomeAssistant, entity: Any) -> None:
    """Track an entity that re-publishes the bridge summary on new reports."""
    data = getattr(hass, "data", None)
    if not isinstance(data, dict):
        return
    entity_set: set[Any] = data.setdefault(DOMAIN, {}).setdefault(BRIDGE_ENTITY_KEY, set())
    entity_set.add(entity)


def unregister_bridge_entity(hass: HomeAssistant, entity: Any) -> None:
    """Drop an entity from bridge-summary republishing."""
    data = getattr(hass, "data", None)
    if not isinstance(data, dict):
        return
    entity_set: set[Any] = data.setdefault(DOMAIN, {}).setdefault(BRIDGE_ENTITY_KEY, set())
    entity_set.discard(entity)


def _publish_report(hass: HomeAssistant, report: dict[str, Any]) -> None:
    """Store, summarize, persist and republish a received report."""
    received = datetime.now(UTC).isoformat()
    _store_report(hass, report, received)
    hass.data.setdefault(DOMAIN, {})[BRIDGE_SUMMARY_KEY] = build_report_summary(report, received)
    for entity in list(hass.data.get(DOMAIN, {}).get(BRIDGE_ENTITY_KEY, ())):
        try:
            entity.async_write_ha_state()
        except Exception as err:
            _LOGGER.debug("Could not republish bridge summary: %s", err)


async def async_setup_bridge_http(hass: HomeAssistant) -> bool:
    """Register the bridge views once per HA run; safe to call per entry."""
    if hass.data.get(DOMAIN, {}).get("bridge_http_registered"):
        return True
    try:
        try:
            from homeassistant.components.http import HomeAssistantView
        except ImportError:
            from homeassistant.components.http.view import HomeAssistantView
    except ImportError:
        _LOGGER.warning("HomeAssistantView unavailable; %s is not being served", BRIDGE_PAGE_PATH)
        return False

    class VidaaBridgePageView(HomeAssistantView):
        """Static read-only recon page for TV browsers."""

        url = BRIDGE_PAGE_PATH
        extra_urls: ClassVar = [BRIDGE_PAGE_PATH + "/"]
        name = "vidaa:exploit"
        requires_auth = False

        async def get(self, request: Any) -> Any:
            from aiohttp import web

            return web.Response(text=load_bridge_page(), content_type="text/html",
                                headers={"Cache-Control": "no-store"})

    class VidaaBridgeReportView(HomeAssistantView):
        """Write-only sink for the recon page's report."""

        url = BRIDGE_REPORT_PATH
        extra_urls: ClassVar = [BRIDGE_REPORT_PATH + "/"]
        name = "vidaa:exploit:report"
        requires_auth = False

        async def post(self, request: Any) -> Any:
            from aiohttp import web

            try:
                body = await request.text()
            except Exception:
                return web.Response(status=400, text="unreadable")
            report = normalize_report(body)
            if report is None:
                return web.Response(status=400, text="invalid report")
            await hass.async_add_executor_job(_publish_report, hass, report)
            for line in summarize_report(report):
                _LOGGER.warning("VIDAA bridge: %s", line)
            return web.Response(text="REPORT_SAVED")

    registered = 0
    for view in (VidaaBridgePageView(), VidaaBridgeReportView()):
        try:
            hass.http.register_view(view)
            registered += 1
        except Exception as err:
            _LOGGER.warning("Could not register bridge view %s: %s", view.url, err)
    if registered == 2:
        hass.data.setdefault(DOMAIN, {})["bridge_http_registered"] = True
        _LOGGER.info("VIDAA bridge views registered: %s and %s", BRIDGE_PAGE_PATH, BRIDGE_REPORT_PATH)
    return registered == 2
