"""Bounded optional Bright Data Web Unlocker API adapter."""

from __future__ import annotations

import hashlib
import json
import re
import socket
import ssl
from dataclasses import dataclass
from datetime import datetime
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, HTTPSHandler, ProxyHandler, Request, build_opener

from .core import ID_RE, PROJECT, PROVENANCE_NOTICE, _utc, normalize_text
from .url_safety import validate_https_url


MAX_RESPONSE = 2 * 1024 * 1024
DEFAULT_TIMEOUT_SECONDS = 180
MAX_TIMEOUT_SECONDS = 300
ERROR_HEADERS = {
    "x-brd-error-code", "x-brd-err-code", "x-luminati-error-code",
    "x-brd-error", "x-brd-err-msg", "x-luminati-error",
}
STATUS_HEADERS = {"x-brd-status-code", "x-luminati-status-code"}


@dataclass(frozen=True)
class HttpRequest:
    method: str
    url: str
    headers: dict[str, str]
    body: bytes
    timeout_seconds: int


@dataclass(frozen=True)
class HttpResponse:
    status: int
    headers: dict[str, str]
    body: bytes


class TransportError(RuntimeError):
    """A transport failure that intentionally carries no provider response text."""

    def __init__(self, code: str = "transport_error"):
        self.code = code
        super().__init__(code)


class TransportTimeout(TransportError):
    """A request was dispatched but its completion could not be observed."""

    def __init__(self):
        super().__init__("transport_timeout")


def _validated_url(url: object, *, live: bool) -> str:
    return validate_https_url(url, live=live)  # type: ignore[return-value]


def _live_url(url: object) -> str:
    return _validated_url(url, live=True)


def _validate_manifest(manifest: object) -> list[dict]:
    if not isinstance(manifest, dict) or set(manifest) - {"schema_version", "project", "jobs", "timeout_seconds"} or {"schema_version", "project", "jobs"} - set(manifest):
        raise ValueError("invalid manifest")
    if manifest["schema_version"] != "1.0" or manifest["project"] != PROJECT:
        raise ValueError("invalid manifest project")
    jobs = manifest["jobs"]
    timeout = manifest.get("timeout_seconds", DEFAULT_TIMEOUT_SECONDS)
    if isinstance(timeout, bool) or not isinstance(timeout, int) or not (DEFAULT_TIMEOUT_SECONDS <= timeout <= MAX_TIMEOUT_SECONDS):
        raise ValueError("timeout_seconds must be an integer from 180 to 300")
    if not isinstance(jobs, list) or not (1 <= len(jobs) <= 8):
        raise ValueError("manifest requires 1 to 8 jobs")
    ids, source_ids = set(), set()
    role_counts = {"offer_page": 0, "terms_page": 0}
    company_roles = set()
    company_ids = set()
    validated = []
    for job in jobs:
        if not isinstance(job, dict):
            raise ValueError("invalid job")
        if job.get("kind") != "web_page":
            raise ValueError("unsupported collection kind")
        required = {"id", "kind", "role", "source_id", "url"}
        if set(job) - required - {"country", "company_id"} or required - set(job):
            raise ValueError("invalid web job fields")
        if not isinstance(job["id"], str) or not ID_RE.fullmatch(job["id"]) or job["id"] in ids:
            raise ValueError("invalid or duplicate job id")
        if not isinstance(job["source_id"], str) or not ID_RE.fullmatch(job["source_id"]) or job["source_id"] in source_ids:
            raise ValueError("invalid or duplicate source id")
        ids.add(job["id"])
        source_ids.add(job["source_id"])
        if job["role"] not in {"offer_page", "terms_page"}:
            raise ValueError("unsupported web role")
        role_counts[job["role"]] += 1
        if role_counts[job["role"]] > 4:
            raise ValueError("at most four offer pages and four terms pages are allowed")
        company_id = job.get("company_id", job["source_id"])
        if not isinstance(company_id, str) or not ID_RE.fullmatch(company_id):
            raise ValueError("invalid company_id")
        company_role = (company_id, job["role"])
        if company_role in company_roles:
            raise ValueError("at most one page of each role is allowed per company")
        company_roles.add(company_role)
        company_ids.add(company_id)
        if len(company_ids) > 4:
            raise ValueError("at most four unique companies are allowed")
        _live_url(job["url"])
        if "country" in job and job["country"] is not None and (not isinstance(job["country"], str) or not re.fullmatch(r"[a-z]{2}", job["country"])):
            raise ValueError("invalid country")
        validated.append(dict(job, company_id=company_id))
    return validated


def plan(manifest: dict) -> dict:
    """Validate a manifest and return a zero-request execution plan."""
    jobs = _validate_manifest(manifest)
    timeout = manifest.get("timeout_seconds", DEFAULT_TIMEOUT_SECONDS)
    return {
        "schema_version": "1.0", "project": PROJECT, "requests_made": 0, "timeout_seconds": timeout,
        "method": "POST", "endpoint": "https://api.brightdata.com/request",
        "api_key_omitted": True, "zone_omitted": True,
        "requests": [{
            "job_id": item["id"], "kind": "web_page", "role": item["role"],
            "company_id": item["company_id"], "url": item["url"], "country": item.get("country"),
            "format": "raw", "data_format": "markdown", "timeout_seconds": timeout,
            "method": "POST", "endpoint": "https://api.brightdata.com/request",
        } for item in jobs],
    }


def _manifest_hash(value: dict) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _validate_approval(manifest: dict, approval: object, api_key: str, zones: dict, now: str) -> None:
    keys = {
        "schema_version", "project", "manifest_sha256", "expires_at", "max_requests",
        "max_retained_records", "approved_urls", "account_budget_confirmed",
        "target_permissions_confirmed", "remote_resolution_risk_accepted",
    }
    if not isinstance(approval, dict) or set(approval) != keys:
        raise PermissionError("valid approval is required")
    if approval["schema_version"] != "1.0" or approval["project"] != PROJECT or approval["manifest_sha256"] != _manifest_hash(manifest):
        raise PermissionError("approval does not match manifest")
    if _utc(approval["expires_at"], "expires_at") <= _utc(now, "now"):
        raise PermissionError("approval has expired")
    if isinstance(approval["max_requests"], bool) or not isinstance(approval["max_requests"], int) or approval["max_requests"] < len(manifest["jobs"]):
        raise PermissionError("request allowance is insufficient")
    if isinstance(approval["max_retained_records"], bool) or not isinstance(approval["max_retained_records"], int) or not (1 <= approval["max_retained_records"] <= 50):
        raise PermissionError("invalid retained-record allowance")
    if (
        not isinstance(approval["approved_urls"], list)
        or len(set(approval["approved_urls"])) != len(approval["approved_urls"])
        or any(not isinstance(url, str) for url in approval["approved_urls"])
        or set(approval["approved_urls"]) != {job["url"] for job in manifest["jobs"]}
    ):
        raise PermissionError("target URL is not approved")
    if any(approval[key] is not True for key in ("account_budget_confirmed", "target_permissions_confirmed", "remote_resolution_risk_accepted")):
        raise PermissionError("required attestations are absent")
    if not isinstance(api_key, str) or not api_key:
        raise PermissionError("API key is required")
    if not isinstance(zones, dict) or not isinstance(zones.get("web_unlocker"), str) or not zones["web_unlocker"]:
        raise PermissionError("Web Unlocker zone is required")


def _job_receipt(job: dict, state: str = "not_attempted", error: str | None = None) -> dict:
    return {
        "id": job["id"], "kind": job["kind"], "state": state, "original_job": dict(job),
        "requested_records": None, "returned_records": 0, "retained_records": 0,
        "excluded_records": 0, "snapshot_id": None, "error_code": error, "query_metadata": None,
    }


def _source(job: dict, text: str, observed_at: str, provenance: str) -> dict:
    _, blocks = normalize_text(text)
    canonical = "\n\n".join(
        ("#" * block["heading_level"] + " " if block["heading_level"] else "") + block["text"]
        for block in blocks
    )
    heading = next((block["text"] for block in blocks if block["heading_level"] == 1), "Selected public page")
    return {
        "id": job["source_id"], "kind": "page", "role": job["role"], "url": job["url"],
        "title": heading[:200], "text": canonical, "status": "collected" if canonical else "empty",
        "observed_at": observed_at, "published_at": None, "provider_date": None,
        "record_id": None, "record_id_origin": "none", "provenance": provenance,
    }


def _valid_response(value: object) -> bool:
    return (
        isinstance(value, HttpResponse)
        and isinstance(value.status, int) and not isinstance(value.status, bool) and 100 <= value.status <= 599
        and isinstance(value.headers, dict)
        and all(isinstance(key, str) and isinstance(item, str) for key, item in value.headers.items())
        and isinstance(value.body, bytes)
    )


def _failure_status(receipts: list[dict]) -> str:
    return "partial" if any(item["state"] in {"complete", "empty"} for item in receipts) else "failed"


def collect(
    manifest: dict, *, approval: dict, api_key: str, zones: dict,
    transport: Callable[[HttpRequest], HttpResponse], now: str,
) -> dict:
    """Perform explicitly approved Web Unlocker API requests sequentially, without application retries."""
    jobs = _validate_manifest(manifest)
    timeout_seconds = manifest.get("timeout_seconds", DEFAULT_TIMEOUT_SECONDS)
    _validate_approval(manifest, approval, api_key, zones, now)
    if getattr(transport, "live_collection_unverified", False):
        raise PermissionError("live collection is unverified and disabled")
    source_provenance = "bright_data_transport" if transport is urllib_transport else "synthetic_fixture"
    receipts = [_job_receipt(job) for job in jobs]
    sources = []
    warnings = []
    requests_made = 0
    overall = "complete"
    for index, job in enumerate(jobs):
        retained_so_far = sum(item["retained_records"] for item in receipts)
        if retained_so_far >= approval["max_retained_records"]:
            overall = "partial"
            warnings.append({
                "code": "provider_limit_exceeded",
                "source_ids": [],
                "note": "The approved retained-record allowance was reached before this request.",
            })
            break
        body = {"zone": zones["web_unlocker"], "url": job["url"], "format": "raw", "data_format": "markdown"}
        if job.get("country") is not None:
            body["country"] = job["country"]
        request = HttpRequest(
            method="POST", url="https://api.brightdata.com/request",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            body=json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode("utf-8"), timeout_seconds=timeout_seconds,
        )
        requests_made += 1
        try:
            result = transport(request)
        except (TransportTimeout, TimeoutError, socket.timeout):
            receipts[index].update(state="completion_unknown", error_code="transport_error")
            overall = "completion_unknown"
            break
        except Exception:
            receipts[index].update(state="failed", error_code="transport_error")
            overall = _failure_status(receipts)
            break
        if not _valid_response(result):
            receipts[index].update(state="failed", error_code="invalid_response")
            overall = _failure_status(receipts)
            break
        lowered = {str(key).casefold(): str(value) for key, value in result.headers.items()}
        embedded_error = any(key in lowered for key in ERROR_HEADERS)
        malformed_status = False
        for key in STATUS_HEADERS & lowered.keys():
            try:
                status_value = int(lowered[key])
                embedded_error |= not (200 <= status_value < 300)
            except ValueError:
                malformed_status = True
        error_code = None
        if malformed_status:
            error_code = "invalid_response"
        elif embedded_error:
            error_code = "provider_target_error"
        elif not (200 <= result.status < 300):
            error_code = "provider_http_error"
        elif len(result.body) > MAX_RESPONSE:
            error_code = "response_too_large"
        if error_code:
            receipts[index].update(state="failed", error_code=error_code)
            overall = _failure_status(receipts)
            break
        try:
            text = result.body.decode("utf-8")
        except UnicodeDecodeError:
            receipts[index].update(state="failed", error_code="invalid_response")
            overall = _failure_status(receipts)
            break
        try:
            envelope = json.loads(text)
        except json.JSONDecodeError:
            envelope = None
        if isinstance(envelope, dict) and {"status_code", "headers", "body"} <= set(envelope):
            receipts[index].update(state="failed", error_code="response_contract_mismatch")
            overall = _failure_status(receipts)
            break
        try:
            item = _source(job, text, now, source_provenance)
        except ValueError as exc:
            code = "unsupported_content_format" if str(exc) == "unsupported_content_format" else "invalid_response"
            receipts[index].update(state="failed", error_code=code)
            overall = _failure_status(receipts)
            break
        retained = 1 if item["status"] == "collected" else 0
        if retained_so_far + retained > approval["max_retained_records"]:
            receipts[index].update(state="failed", returned_records=retained, excluded_records=retained, error_code="provider_limit_exceeded")
            warnings.append({
                "code": "provider_limit_exceeded", "source_ids": [],
                "note": "A returned record exceeded the approved retained-record allowance.",
            })
            overall = "partial"
            break
        sources.append(item)
        receipts[index].update(state="complete" if retained else "empty", returned_records=retained, retained_records=retained)
    returned = sum(item["returned_records"] for item in receipts)
    retained = sum(item["retained_records"] for item in receipts)
    receipt = {
        "schema_version": "1.0", "project": PROJECT, "manifest_sha256": _manifest_hash(manifest),
        "status": overall, "requests_made": requests_made, "returned_records": returned,
        "retained_records": retained, "excluded_records": sum(item["excluded_records"] for item in receipts),
        "jobs": receipts, "warnings": warnings, "provider_cost_usd": None,
    }
    return {
        "schema_version": "1.0", "project": PROJECT, "transport_contract_version": "1.0",
        "provenance_notice": PROVENANCE_NOTICE, "sources": sources, "receipt": receipt,
    }


def normalize_export(kind, records, *, role, source_url, observed_at, source_prefix) -> dict:
    """Normalize an operator-supplied Web Unlocker API Markdown export offline."""
    if kind != "web_page" or role not in {"offer_page", "terms_page"}:
        raise ValueError("unsupported import kind/role")
    if not isinstance(records, str):
        raise ValueError("web_page export must be a Markdown string")
    _validated_url(source_url, live=False)
    _utc(observed_at, "observed_at")
    if not isinstance(source_prefix, str) or not re.fullmatch(r"[a-z][a-z0-9_-]{0,47}", source_prefix):
        raise ValueError("invalid source prefix")
    suffix = hashlib.sha256(source_url.encode("utf-8")).hexdigest()[:16]
    job = {
        "id": "offline_import", "kind": "web_page", "role": role,
        "company_id": source_prefix, "source_id": f"{source_prefix}-{suffix}", "url": source_url,
    }
    source = _source(job, records, observed_at, "operator_supplied")
    retained = int(source["status"] == "collected")
    receipt = {
        "schema_version": "1.0", "project": PROJECT, "manifest_sha256": None, "status": "complete",
        "requests_made": 0, "returned_records": retained, "retained_records": retained,
        "excluded_records": 0, "jobs": [_job_receipt(job, "complete" if retained else "empty")],
        "warnings": [], "provider_cost_usd": None,
    }
    receipt["jobs"][0].update(returned_records=retained, retained_records=retained)
    return {
        "schema_version": "1.0", "project": PROJECT, "transport_contract_version": "1.0",
        "provenance_notice": PROVENANCE_NOTICE, "sources": [source], "receipt": receipt,
    }


def resume(receipt, *, approval, api_key, transport, now):
    raise NotImplementedError("resume is unsupported for page-only collection")


def urllib_transport(request: HttpRequest) -> HttpResponse:
    """Production stdlib transport with proxies and redirects disabled."""
    opener = build_opener(ProxyHandler({}), HTTPSHandler(context=ssl.create_default_context()))
    opener.add_handler(_NoRedirect())
    raw = Request(request.url, data=request.body, headers=request.headers, method=request.method)
    try:
        with opener.open(raw, timeout=request.timeout_seconds) as response:
            body = response.read(MAX_RESPONSE + 1)
            return HttpResponse(response.status, dict(response.headers.items()), body)
    except HTTPError as exc:
        body = exc.read(MAX_RESPONSE + 1)
        return HttpResponse(exc.code, dict(exc.headers.items()), body)
    except (TimeoutError, socket.timeout) as exc:
        raise TransportTimeout() from exc
    except URLError as exc:
        if isinstance(exc.reason, (TimeoutError, socket.timeout)):
            raise TransportTimeout() from exc
        raise TransportError() from exc
    except OSError as exc:
        raise TransportError() from exc


class _NoRedirect(HTTPRedirectHandler):
    handler_order = 100

    def http_error_301(self, request, fp, code, msg, headers):
        return fp

    http_error_302 = http_error_301
    http_error_303 = http_error_301
    http_error_307 = http_error_301
    http_error_308 = http_error_301


urllib_transport.live_collection_unverified = True
urllib_transport.source_provenance = "bright_data_transport"


def library_for_export(library: dict) -> dict:
    """Downgrade invocation-local transport state to an explicit exported claim."""
    import copy

    exported = copy.deepcopy(library)
    exported["provenance_notice"] = PROVENANCE_NOTICE
    for source in exported.get("sources", []):
        if isinstance(source, dict) and source.get("provenance") in {"bright_data", "bright_data_transport"}:
            source["provenance"] = "operator_claimed_bright_data"
    return exported
