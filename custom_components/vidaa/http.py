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
  diagnostics/offline analysis) and summarized to the log.
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


def _store_report(hass: HomeAssistant, report: dict[str, Any]) -> None:
    """Persist the latest report per reporting client id."""
    store: dict[str, Any] = hass.data.setdefault(DOMAIN, {}).setdefault(BRIDGE_DATA_KEY, {})
    client = str(report.get("url") or report.get("ua") or "unknown")[:120]
    store[client] = {"received": datetime.now(UTC).isoformat(), "report": report}
    try:
        payload = json.dumps({k: v for k, v in store.items()}, indent=2, ensure_ascii=False, default=str)
        Path(hass.config.path("vidaa_bridge_report.json")).write_text(payload, encoding="utf-8")
    except OSError as err:
        _LOGGER.debug("Could not persist bridge report file: %s", err)


async def async_setup_bridge_http(hass: HomeAssistant) -> bool:
    """Register the bridge views once per HA run; safe to call per entry."""
    if hass.data.get(DOMAIN, {}).get("bridge_http_registered"):
        return True
    try:
        from homeassistant.components.http import HomeAssistantView
    except ImportError:
        _LOGGER.debug("HTTP component unavailable; bridge views not registered")
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
            await hass.async_add_executor_job(_store_report, hass, report)
            for line in summarize_report(report):
                _LOGGER.info("VIDAA bridge: %s", line)
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
