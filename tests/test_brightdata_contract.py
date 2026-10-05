"""Page-only Bright Data adapter acceptance tests using local recording transports."""

import hashlib
import json

import pytest


NOW = "2026-10-04T10:00:00Z"
TARGET = "https://pricing.vendor.com/team"


def manifest(url=TARGET, count=1):
    jobs = []
    for index in range(count):
        jobs.append({
            "id": f"web_{index}",
            "kind": "web_page",
            "role": "offer_page" if index % 2 == 0 else "terms_page",
            "company_id": f"company_{index // 2}",
            "source_id": f"source_{index}",
            "url": url if count == 1 else f"https://pricing{index}.vendor.com/team",
        })
    return {"schema_version": "1.0", "project": "competitor-offer-decoder", "jobs": jobs}


def approval(value, *, expires_at="2026-10-05T10:00:00Z", max_requests=None, approved_urls=None):
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {
        "schema_version": "1.0",
        "project": "competitor-offer-decoder",
        "manifest_sha256": hashlib.sha256(encoded).hexdigest(),
        "expires_at": expires_at,
        "max_requests": max_requests if max_requests is not None else len(value["jobs"]),
        "max_retained_records": 1,
        "approved_urls": approved_urls if approved_urls is not None else [job["url"] for job in value["jobs"]],
        "account_budget_confirmed": True,
        "target_permissions_confirmed": True,
        "remote_resolution_risk_accepted": True,
    }


def response(brightdata, status=200, headers=None, body=b"## Team\n\nUSD 10 per user/month, billed annually."):
    return brightdata.HttpResponse(status=status, headers=headers or {}, body=body)


def collect(brightdata, value, attestation, transport):
    return brightdata.collect(
        value,
        approval=attestation,
        api_key="fake-secret-token",
        zones={"web_unlocker": "approved-zone"},
        transport=transport,
        now=NOW,
    )


def test_c09_approval_hash_expiry_url_budget_key_and_zone_fail_before_request():
    from competitor_offer_decoder import brightdata

    value = manifest()
    valid = approval(value)
    variants = []
    bad_hash = dict(valid, manifest_sha256="0" * 64)
    variants.append((bad_hash, "fake", {"web_unlocker": "zone"}))
    variants.append((dict(valid, expires_at=NOW), "fake", {"web_unlocker": "zone"}))
    variants.append((dict(valid, approved_urls=[]), "fake", {"web_unlocker": "zone"}))
    variants.append((dict(valid, max_requests=0), "fake", {"web_unlocker": "zone"}))
    variants.append((valid, "", {"web_unlocker": "zone"}))
    variants.append((valid, "fake", {}))
    calls = []
    for attestation, api_key, zones in variants:
        with pytest.raises((ValueError, PermissionError)):
            brightdata.collect(value, approval=attestation, api_key=api_key, zones=zones, transport=lambda request: calls.append(request), now=NOW)
    assert calls == []


def test_c11_web_request_is_exact_and_raw_markdown_normalizes():
    from competitor_offer_decoder import brightdata

    value = manifest()
    calls = []

    def transport(request):
        calls.append(request)
        return response(brightdata)

    library = collect(brightdata, value, approval(value), transport)
    assert len(calls) == 1
    request = calls[0]
    assert request.method == "POST"
    assert request.url == "https://api.brightdata.com/request"
    # Brand review requires a documented configurable default of at least 180 seconds.
    assert request.timeout_seconds == 180
    assert request.headers == {"Authorization": "Bearer fake-secret-token", "Content-Type": "application/json"}
    assert json.loads(request.body) == {"zone": "approved-zone", "url": TARGET, "format": "raw", "data_format": "markdown"}
    assert library["receipt"]["requests_made"] == 1
    assert library["receipt"]["status"] == "complete"
    assert library["sources"][0]["text"] == "## Team\n\nUSD 10 per user/month, billed annually."
    assert library["sources"][0]["provenance"] == "synthetic_fixture"


def test_c11_manifest_hard_cap_is_eight_calls():
    from competitor_offer_decoder import brightdata

    assert len(brightdata.plan(manifest(count=8))["requests"]) == 8
    with pytest.raises(ValueError):
        brightdata.plan(manifest(count=9))


@pytest.mark.parametrize("headers", [
    {"x-brd-status-code": "429"},
    {"X-Luminati-Error-Code": "target_failed"},
    {"x-brd-status-code": "not-an-integer"},
])
def test_c12_embedded_provider_error_headers_never_create_evidence(headers):
    from competitor_offer_decoder import brightdata

    value = manifest()
    library = collect(brightdata, value, approval(value), lambda request: response(brightdata, headers=headers, body=b"USD 1 per user/month, billed monthly."))
    assert library["receipt"]["status"] == "failed"
    assert not any(source["status"] == "collected" for source in library["sources"])


@pytest.mark.parametrize("status", [301, 302, 401, 403, 429, 500])
def test_c12_c13_http_failures_stop_after_one_without_retry(status):
    from competitor_offer_decoder import brightdata

    value = manifest(count=2)
    calls = []

    def transport(request):
        calls.append(request)
        return response(brightdata, status=status, body=b"provider message fake-secret-token")

    library = collect(brightdata, value, approval(value), transport)
    serialized = json.dumps(library)
    assert len(calls) == 1
    assert library["receipt"]["status"] == "failed"
    assert library["receipt"]["jobs"][1]["state"] == "not_attempted"
    assert "fake-secret-token" not in serialized
    assert "provider message" not in serialized


def test_c12_unexpected_json_envelope_is_contract_mismatch():
    from competitor_offer_decoder import brightdata

    value = manifest()
    body = json.dumps({"status_code": 200, "headers": {}, "body": "## Team"}).encode()
    library = collect(brightdata, value, approval(value), lambda request: response(brightdata, body=body))
    assert library["receipt"]["status"] == "failed"
    assert library["receipt"]["jobs"][0]["error_code"] == "response_contract_mismatch"
    assert library["sources"] == [] or all(source["status"] != "collected" for source in library["sources"])


def test_c12_response_over_two_mib_is_rejected():
    from competitor_offer_decoder import brightdata

    value = manifest()
    library = collect(brightdata, value, approval(value), lambda request: response(brightdata, body=b"x" * (2 * 1024 * 1024 + 1)))
    assert library["receipt"]["status"] == "failed"
    assert library["receipt"]["jobs"][0]["error_code"] == "response_too_large"


def test_c13_timeout_is_completion_unknown_once_and_safe():
    from competitor_offer_decoder import brightdata

    value = manifest(count=2)
    calls = []

    def timeout(request):
        calls.append(request)
        raise TimeoutError("provider leaked fake-secret-token")

    library = collect(brightdata, value, approval(value), timeout)
    assert len(calls) == 1
    assert library["receipt"]["status"] == "completion_unknown"
    assert library["receipt"]["jobs"][0]["state"] == "completion_unknown"
    assert library["receipt"]["jobs"][1]["state"] == "not_attempted"
    assert "fake-secret-token" not in json.dumps(library)


def test_c14_c15_scraper_pending_and_resume_are_unsupported_without_http():
    from competitor_offer_decoder import brightdata

    calls = []
    with pytest.raises((ValueError, NotImplementedError)):
        brightdata.resume({"schema_version": "1.0", "project": "competitor-offer-decoder", "receipt": {"status": "pending"}}, approval={}, api_key="fake", transport=lambda request: calls.append(request), now=NOW)
    for kind in ("amazon_reviews", "youtube_comments", "serp"):
        with pytest.raises(ValueError):
            brightdata.plan({"schema_version": "1.0", "project": "competitor-offer-decoder", "jobs": [{"id": "x", "kind": kind}]})
    assert calls == []


def test_c16_empty_page_is_truthful_empty_source_and_zero_retained_records():
    from competitor_offer_decoder import brightdata

    value = manifest()
    library = collect(brightdata, value, approval(value), lambda request: response(brightdata, body=b"  \n"))
    assert library["receipt"]["status"] == "complete"
    assert library["receipt"]["retained_records"] == 0
    assert library["sources"][0]["status"] == "empty"
    assert library["sources"][0]["text"] == ""


@pytest.mark.parametrize("url", [
    "http://pricing.vendor.com/team",
    "https://user@pricing.vendor.com/team",
    "https://127.0.0.1/team",
    "https://[::1]/team",
    "https://localhost/team",
    "https://pricing.local/team",
    "https://example.com/team",
    "https://sub.example.net/team",
    "https://pricing.vendor.com:444/team",
    "https://pricing.vendor.com/team#fragment",
    "https://pricing.vendor.com/team?api%5Fkey=secret",
])
def test_c17_unsafe_live_targets_are_rejected_during_planning(url):
    from competitor_offer_decoder import brightdata

    with pytest.raises(ValueError):
        brightdata.plan(manifest(url=url))


def test_c17_host_case_and_trailing_dot_normalize_before_safety_checks():
    from competitor_offer_decoder import brightdata

    with pytest.raises(ValueError):
        brightdata.plan(manifest(url="https://EXAMPLE.COM./team"))


def test_c18_source_content_never_creates_an_unapproved_request():
    from competitor_offer_decoder import brightdata

    value = manifest()
    value["jobs"][0]["url"] = "https://pricing.vendor.com/team?next=https%3A%2F%2Fother.vendor.com"
    attestation = approval(value, approved_urls=[TARGET])
    calls = []
    with pytest.raises((ValueError, PermissionError)):
        collect(brightdata, value, attestation, lambda request: calls.append(request))
    assert calls == []


def test_normalize_export_accepts_only_web_page_and_omits_unknown_fields():
    from competitor_offer_decoder import brightdata

    library = brightdata.normalize_export(
        "web_page",
        "## Team\n\nUSD 10 per user/month, billed annually.",
        role="offer_page",
        source_url=TARGET,
        observed_at=NOW,
        source_prefix="import",
    )
    assert library["receipt"]["requests_made"] == 0
    assert library["sources"][0]["provenance"] == "operator_supplied"
    assert set(library["sources"][0]) == {"id", "kind", "role", "url", "title", "text", "status", "observed_at", "published_at", "provider_date", "record_id", "record_id_origin", "provenance"}
    for kind in ("serp", "amazon_reviews", "youtube_comments", "google_maps_reviews"):
        with pytest.raises((ValueError, NotImplementedError)):
            brightdata.normalize_export(kind, [], role="offer_page", source_url=TARGET, observed_at=NOW, source_prefix="import")
