"""HTTP surface for the on-TV browser bridge (``/vidaa/exploit``).

Serves the read-only recon page at ``GET /vidaa/exploit`` and receives the
TV's report at ``POST /vidaa/exploit/report``.

Security notes (by design, read before changing):
- ``/vidaa/exploit`` and its ``/report`` sink are ``requires_auth=False`` so
  the TV's browser can open them without an HA login. The page itself is
  static and carries no secrets. Served with a restrictive CSP so page
  variants can only talk to their own origin and the TV's loopback services.
- The page content is an OVERRIDE FILE: ``<config>/vidaa_bridge/recon.html``
  when present (read fresh per request — hot-swappable without a restart),
  otherwise the page bundled in the package. It is replaced via
  ``PUT /vidaa/exploit/page`` which requires the per-run page key (published
  as the ``bridge_page_key`` media-player attribute) and accepts only
  size-capped HTML documents; writes are atomic and rate-limited.
- The report sink is WRITE-ONLY, body-size-capped and stores at most the
  latest report per reporting client. Nothing is ever sent from the sink back
  to the TV. The latest FULL report is retrievable with
  ``GET /vidaa/exploit/report?key`` (page key).
- The page self-updates: it long-polls ``GET /vidaa/exploit/task?seen=REV``
  (no key; delivers the newest queued read-only task only) and executes it
  inside a fixed interpreter. Tasks are queued with
  ``PUT /vidaa/exploit/task`` + page key and are validated server-side
  against the same read-only service/API allowlist the page enforces.
- Full reports are written to ``<config>/vidaa_bridge_report.json`` (for
  diagnostics/offline analysis), summarized to the log (WARNING level, so it
  survives HAOS journald filtering) and published as the bounded
  ``bridge_report`` attribute on the media player entity.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import secrets
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, ClassVar

from homeassistant.core import HomeAssistant

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

BRIDGE_PAGE_PATH = "/vidaa/exploit"
BRIDGE_REPORT_PATH = "/vidaa/exploit/report"
BRIDGE_PAGE_PUT_PATH = "/vidaa/exploit/page"
BRIDGE_TASK_PATH = "/vidaa/exploit/task"
MAX_REPORT_BYTES = 512 * 1024
MAX_PAGE_BYTES = 512 * 1024
MAX_TASK_BYTES = 64 * 1024
PAGE_WRITE_MIN_INTERVAL_S = 3

_BRIDGE_PAGE = Path(__file__).parent / "bridge" / "recon.html"

BRIDGE_DATA_KEY = "bridge_reports"
BRIDGE_SUMMARY_KEY = "bridge_summary"
BRIDGE_ENTITY_KEY = "bridge_entities"
BRIDGE_PAGE_KEY = "bridge_page_key"
BRIDGE_PAGE_META_KEY = "bridge_page_meta"
BRIDGE_TASK_KEY = "bridge_task"

BRIDGE_OVERRIDE_DIR = "vidaa_bridge"
BRIDGE_OVERRIDE_FILE = "recon.html"

# Server-side mirror of the page's read-only allowlist (defense in depth:
# a task that tries a write-capable op is rejected here, not just in page JS).
SVC_ALLOW: dict[str, tuple[str, ...]] = {
    "tvinfo": ("initialData",),
    "hiutils": ("getOSVersion", "getVersionStatus", "fileRead"),
    "pkgmgr": ("getInstalledPkgs",),
}
TASK_OPS = {"fileRead", "svc", "ws", "native", "globals", "enumerate", "sleep", "batch", "jsapi"}
JSAPI_GETTER_RE = r"^(?:Hisense_Get|His_get)[A-Za-z0-9_]{0,60}$"
WS_METHOD_ALLOW = {"start", "callAPI"}
WS_SVC_ALLOW = set(SVC_ALLOW) | {"basic/fetcher"}
WS_PORTS = (9009, 9888)

PAGE_CSP = (
    "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; "
    "img-src 'self' data:; font-src 'self'; "
    "connect-src 'self' http://localhost:* https://localhost:* ws://localhost:* wss://localhost:* "
    "http://127.0.0.1:* https://127.0.0.1:* ws://127.0.0.1:* wss://127.0.0.1:*"
)


def load_bridge_page() -> str:
    """Return the recon page HTML shipped inside the package."""
    return _BRIDGE_PAGE.read_text(encoding="utf-8")


def _override_path(hass: HomeAssistant) -> Path:
    return Path(hass.config.path(BRIDGE_OVERRIDE_DIR)) / BRIDGE_OVERRIDE_FILE


def read_bridge_page(hass: HomeAssistant) -> tuple[str, str]:
    """Return (html, source); override file wins when present, else bundled."""
    path = _override_path(hass)
    try:
        if path.is_file():
            return path.read_text(encoding="utf-8"), "override"
    except OSError as err:
        _LOGGER.warning("VIDAA bridge: override page unreadable (%s); using bundled", err)
    return load_bridge_page(), "bundled"


def validate_page_body(body: str) -> str | None:
    """Return None when body is a safe HTML document, else a rejection reason."""
    if not body:
        return "empty body"
    if len(body.encode("utf-8", "ignore")) > MAX_PAGE_BYTES:
        return f"body exceeds {MAX_PAGE_BYTES} bytes"
    head = body.lstrip()[:64].lower()
    if not (head.startswith("<!doctype html") or head.startswith("<html")):
        return "body is not an HTML document"
    return None


def write_bridge_page(hass: HomeAssistant, body: str) -> dict[str, Any]:
    """Atomically store the page override; returns page metadata."""
    path = _override_path(hass)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(body, encoding="utf-8")
    tmp.replace(path)
    sha = hashlib.sha256(body.encode("utf-8")).hexdigest()[:12]
    meta = {"sha256_12": sha, "bytes": len(body.encode("utf-8")),
            "updated": datetime.now(UTC).isoformat(), "source": "override"}
    hass.data.setdefault(DOMAIN, {})[BRIDGE_PAGE_META_KEY] = meta
    return meta


def page_status(hass: HomeAssistant) -> dict[str, Any]:
    """Current served-page provenance (source, size, hash)."""
    html, source = read_bridge_page(hass)
    meta = dict(hass.data.get(DOMAIN, {}).get(BRIDGE_PAGE_META_KEY) or {})
    meta.update({"source": source, "bytes": len(html.encode("utf-8")),
                 "sha256_12": hashlib.sha256(html.encode("utf-8")).hexdigest()[:12]})
    return meta


def get_bridge_page_key(hass: HomeAssistant) -> str | None:
    """Per-run key required to replace the page or queue a task via PUT."""
    data = getattr(hass, "data", None)
    if not isinstance(data, dict):
        return None
    key = data.get(DOMAIN, {}).get(BRIDGE_PAGE_KEY)
    return key if isinstance(key, str) else None


def validate_task(task: Any, depth: int = 0) -> str | None:
    """Return None when the task only uses read-only allowlisted ops."""
    if depth > 2 or not isinstance(task, dict):
        return "task must be a JSON object (max depth 2)"
    op = task.get("op")
    if op not in TASK_OPS:
        return f"op {op!r} not allowed"
    if op == "svc":
        svc, api = task.get("svc"), task.get("api")
        if svc not in SVC_ALLOW or api not in SVC_ALLOW[svc]:
            return f"svc call {svc}.{api} not allowed"
    elif op == "fileRead":
        if not isinstance(task.get("path"), str):
            return "fileRead needs a string path"
    elif op == "native":
        if task.get("api") != "fileRead":
            return "native lane allows fileRead only"
    elif op == "ws":
        target = str(task.get("target", ""))
        prefixes = tuple(f"{s}://{h}" for s in ("ws", "wss") for h in ("localhost", "127.0.0.1"))
        if not target.startswith(prefixes) or not any(f":{p}" in target for p in WS_PORTS):
            return "ws target must be ws(s)://(localhost|127.0.0.1):(9009|9888)"
        messages = task.get("messages", [])
        if not isinstance(messages, list) or len(messages) > 10:
            return "ws messages must be a list of at most 10"
        for msg in messages:
            if not isinstance(msg, dict):
                return "ws message must be an object"
            if msg.get("method") not in WS_METHOD_ALLOW:
                return f"ws method {msg.get('method')!r} not allowed"
            path = str(msg.get("path", ""))
            svc = path.removeprefix("phoenix://service/")
            if svc not in WS_SVC_ALLOW:
                return f"ws service {svc!r} not allowed"
            if msg.get("method") == "start" and svc not in WS_SVC_ALLOW:
                return "ws start service not allowed"
            if msg.get("method") == "callAPI":
                api = (msg.get("parameters") or {}).get("api")
                if svc not in SVC_ALLOW or api not in SVC_ALLOW.get(svc, ()):
                    return f"ws callAPI {svc}.{api} not allowed"
    elif op == "jsapi":
        fn = task.get("fn")
        if not isinstance(fn, str) or not re.match(JSAPI_GETTER_RE, fn):
            return "jsapi allows vendor getters only (Hisense_Get*/His_get*)"
        if not isinstance(task.get("args", []), list):
            return "jsapi args must be a list"
    elif op == "sleep":
        if not (isinstance(task.get("ms"), int) and 0 <= task["ms"] <= 10000):
            return "sleep ms must be an int in [0, 10000]"
    elif op == "enumerate":
        if not isinstance(task.get("filter"), str) or len(task["filter"]) > 64:
            return "enumerate needs a filter string (<=64 chars)"
    elif op == "batch":
        ops = task.get("ops")
        if not isinstance(ops, list) or len(ops) > 20:
            return "batch needs an ops list of at most 20"
        for sub in ops:
            reason = validate_task(sub, depth + 1)
            if reason:
                return reason
    return None


def set_bridge_task(hass: HomeAssistant, task: dict[str, Any]) -> dict[str, Any]:
    """Queue the latest task; monotonic rev lets pages dedupe delivery."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    cur = domain_data.get(BRIDGE_TASK_KEY) or {}
    rev = int(cur.get("rev", 0)) + 1
    meta = {"rev": rev, "updated": datetime.now(UTC).isoformat(), "op": task.get("op"),
            "delivered": None, "task": task}
    domain_data[BRIDGE_TASK_KEY] = meta
    return {k: v for k, v in meta.items() if k != "task"}


def get_bridge_task_meta(hass: HomeAssistant) -> dict[str, Any] | None:
    """Latest task metadata without the payload (attribute-safe)."""
    data = getattr(hass, "data", None)
    if not isinstance(data, dict):
        return None
    cur = data.get(DOMAIN, {}).get(BRIDGE_TASK_KEY)
    if not isinstance(cur, dict):
        return None
    return {k: cur[k] for k in ("rev", "updated", "op", "delivered") if k in cur}


def next_bridge_task(hass: HomeAssistant, seen_rev: int) -> dict[str, Any] | None:
    """Return {rev, task} when a newer task than seen_rev is pending; mark delivered."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    cur = domain_data.get(BRIDGE_TASK_KEY)
    if not isinstance(cur, dict) or int(cur.get("rev", 0)) <= seen_rev:
        return None
    if cur.get("delivered") is None:
        cur["delivered"] = datetime.now(UTC).isoformat()
        _republish_bridge_entities(hass)
    return {"rev": cur["rev"], "task": cur.get("task")}


def get_latest_report(hass: HomeAssistant) -> dict[str, Any] | None:
    """Most recent full report from the per-client store (keyed endpoint only)."""
    data = getattr(hass, "data", None)
    if not isinstance(data, dict):
        return None
    store = data.get(DOMAIN, {}).get(BRIDGE_DATA_KEY)
    if not isinstance(store, dict) or not store:
        return None
    return max(store.values(), key=lambda e: str(e.get("received", "")))


def _republish_bridge_entities(hass: HomeAssistant) -> None:
    """Force state writes so bridge attributes refresh immediately."""
    for entity in list(hass.data.get(DOMAIN, {}).get(BRIDGE_ENTITY_KEY, ())):
        try:
            entity.async_write_ha_state()
        except Exception as err:
            _LOGGER.debug("Could not republish bridge state: %s", err)


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
    lines.append(f"  get_reach: {json.dumps(report.get('get_reach', {}), default=str)[:400]}")
    lines.append(f"  ws_start: {json.dumps(report.get('ws_start', []), default=str)[:500]}")
    lines.append(f"  http_svc: {json.dumps(report.get('http_svc', {}), default=str)[:600]}")
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
    if report.get("cmd"):
        lines.append(f"  cmd: {json.dumps(report.get('cmd'), default=str)[:700]}")
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
        "transport_get": _bounded_dict(report.get("get_reach"), 8, 150),
        "http_svc": _bounded_dict(report.get("http_svc"), 8, 250),
        "ws_start": [str(json.dumps(w, default=str))[:200] for w in (report.get("ws_start") or [])[:8]]
        if isinstance(report.get("ws_start"), list) else [],
        "wss9888": str(report.get("wss9888"))[:80],
        "fileread_variant": str(report.get("fileread_variant"))[:40],
        "reads": clipped_reads,
        "initialData": _bounded_dict(initial, 40, 150) if isinstance(initial, dict) else str(initial)[:300],
        "bridge_globals": _bounded_dict(report.get("bridge_globals"), 20, 40),
        "tvinfo_setters": [str(s)[:80] for s in (report.get("tvinfo_setters") or [])[:40]]
        if isinstance(report.get("tvinfo_setters"), list) else [],
        "pkglist": _bounded_dict(report.get("pkglist_trunc"), 6, 300)
        if isinstance(report.get("pkglist_trunc"), dict) else str(report.get("pkglist_trunc"))[:300],
        "cmd": _bounded_dict(report.get("cmd"), 10, 400),
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
    _republish_bridge_entities(hass)


async def async_setup_bridge_http(hass: HomeAssistant) -> bool:
    """Register the bridge views once per HA run; safe to call per entry."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    if domain_data.get("bridge_http_registered"):
        return True
    try:
        try:
            from homeassistant.components.http import HomeAssistantView
        except ImportError:
            from homeassistant.components.http.view import HomeAssistantView
    except ImportError:
        _LOGGER.warning("HomeAssistantView unavailable; %s is not being served", BRIDGE_PAGE_PATH)
        return False

    if not isinstance(domain_data.get(BRIDGE_PAGE_KEY), str):
        domain_data[BRIDGE_PAGE_KEY] = secrets.token_urlsafe(24)

    class VidaaBridgePageView(HomeAssistantView):
        """Static read-only recon page for TV browsers (override-aware)."""

        url = BRIDGE_PAGE_PATH
        extra_urls: ClassVar = [BRIDGE_PAGE_PATH + "/"]
        name = "vidaa:exploit"
        requires_auth = False

        async def get(self, request: Any) -> Any:
            from aiohttp import web

            html, _source = read_bridge_page(hass)
            return web.Response(
                text=html,
                content_type="text/html",
                headers={"Cache-Control": "no-store",
                         "Content-Security-Policy": PAGE_CSP,
                         "X-Content-Type-Options": "nosniff",
                         "X-Frame-Options": "DENY"},
            )

    class VidaaBridgeReportView(HomeAssistantView):
        """Report sink (POST) and full-report fetch for tooling (GET + key)."""

        url = BRIDGE_REPORT_PATH
        extra_urls: ClassVar = [BRIDGE_REPORT_PATH + "/"]
        name = "vidaa:exploit:report"
        requires_auth = False

        async def get(self, request: Any) -> Any:
            from aiohttp import web

            key = get_bridge_page_key(hass)
            supplied = request.headers.get("x-vidaa-page-key") or request.query.get("key")
            if not key or not secrets.compare_digest(str(supplied or ""), key):
                return web.Response(status=401, text="page key required")
            latest = get_latest_report(hass)
            if latest is None:
                return web.json_response({"report": None})
            return web.json_response(latest)

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

    class VidaaBridgePagePutView(HomeAssistantView):
        """Replace the page override; requires the per-run page key."""

        url = BRIDGE_PAGE_PUT_PATH
        extra_urls: ClassVar = [BRIDGE_PAGE_PUT_PATH + "/"]
        name = "vidaa:exploit:page"
        requires_auth = False

        def _authorized(self, request: Any) -> bool:
            key = get_bridge_page_key(hass)
            supplied = request.headers.get("x-vidaa-page-key") or request.query.get("key")
            return bool(key) and secrets.compare_digest(str(supplied or ""), key)

        async def get(self, request: Any) -> Any:
            from aiohttp import web

            if not self._authorized(request):
                return web.Response(status=401, text="page key required")
            return web.json_response(page_status(hass))

        async def put(self, request: Any) -> Any:
            from aiohttp import web

            if not self._authorized(request):
                return web.Response(status=401, text="page key required")
            last = domain_data.get("bridge_page_last_write")
            now = datetime.now(UTC).timestamp()
            if last and now - float(last) < PAGE_WRITE_MIN_INTERVAL_S:
                return web.Response(status=429, text="write rate limited")
            try:
                body = await request.text()
            except Exception:
                return web.Response(status=400, text="unreadable")
            reason = validate_page_body(body)
            if reason:
                return web.Response(status=400, text=reason)
            meta = await hass.async_add_executor_job(write_bridge_page, hass, body)
            domain_data["bridge_page_last_write"] = now
            _LOGGER.warning("VIDAA bridge: page updated sha256=%s bytes=%s",
                            meta["sha256_12"], meta["bytes"])
            await hass.async_add_executor_job(_republish_bridge_entities, hass)
            return web.json_response(meta)

    class VidaaBridgeTaskView(HomeAssistantView):
        """Task long-poll for the page (GET, no key) and task queueing (PUT + key)."""

        url = BRIDGE_TASK_PATH
        extra_urls: ClassVar = [BRIDGE_TASK_PATH + "/"]
        name = "vidaa:exploit:task"
        requires_auth = False

        async def get(self, request: Any) -> Any:
            from aiohttp import web

            try:
                seen = int(request.query.get("seen", "0"))
            except ValueError:
                seen = 0
            pending = next_bridge_task(hass, seen)
            return web.json_response(pending if pending else {"rev": 0, "task": None})

        async def put(self, request: Any) -> Any:
            from aiohttp import web

            if not self._authorized(request):
                return web.Response(status=401, text="page key required")
            try:
                body = await request.text()
            except Exception:
                return web.Response(status=400, text="unreadable")
            if len(body.encode("utf-8", "ignore")) > MAX_TASK_BYTES:
                return web.Response(status=400, text=f"task exceeds {MAX_TASK_BYTES} bytes")
            try:
                task = json.loads(body)
            except (ValueError, TypeError):
                return web.Response(status=400, text="task must be JSON")
            reason = validate_task(task)
            if reason:
                return web.Response(status=400, text=reason)
            meta = set_bridge_task(hass, task)
            _LOGGER.warning("VIDAA bridge: task queued rev=%s op=%s", meta["rev"], meta["op"])
            await hass.async_add_executor_job(_republish_bridge_entities, hass)
            return web.json_response(meta)

        def _authorized(self, request: Any) -> bool:
            key = get_bridge_page_key(hass)
            supplied = request.headers.get("x-vidaa-page-key") or request.query.get("key")
            return bool(key) and secrets.compare_digest(str(supplied or ""), key)

    registered = 0
    for view in (VidaaBridgePageView(), VidaaBridgeReportView(), VidaaBridgePagePutView(),
                 VidaaBridgeTaskView()):
        try:
            hass.http.register_view(view)
            registered += 1
        except Exception as err:
            _LOGGER.warning("Could not register bridge view %s: %s", view.url, err)
    if registered == 4:
        domain_data["bridge_http_registered"] = True
        _LOGGER.info("VIDAA bridge views registered: %s, %s, %s and %s",
                     BRIDGE_PAGE_PATH, BRIDGE_REPORT_PATH, BRIDGE_PAGE_PUT_PATH, BRIDGE_TASK_PATH)
    return registered == 4
