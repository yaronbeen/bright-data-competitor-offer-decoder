"""Regression tests for independent brand review requirements."""

import hashlib
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
NOW = "2026-10-04T10:00:00Z"
TARGET = "https://pricing.vendor.com/team"


def manifest(*, timeout_seconds=None, country=None):
    job = {
        "id": "web_1", "kind": "web_page", "role": "offer_page", "company_id": "vendor",
        "source_id": "vendor_offer", "url": TARGET,
    }
    if country is not None:
        job["country"] = country
    value = {"schema_version": "1.0", "project": "competitor-offer-decoder", "jobs": [job]}
    if timeout_seconds is not None:
        value["timeout_seconds"] = timeout_seconds
    return value


def approval(value, approved_urls=None):
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return {
        "schema_version": "1.0", "project": "competitor-offer-decoder",
        "manifest_sha256": hashlib.sha256(encoded).hexdigest(),
        "expires_at": "2026-10-05T10:00:00Z", "max_requests": 1, "max_retained_records": 1,
        "approved_urls": approved_urls if approved_urls is not None else [TARGET],
        "account_budget_confirmed": True, "target_permissions_confirmed": True,
        "remote_resolution_risk_accepted": True,
    }


def test_dry_run_plan_exposes_country_formats_and_default_timeout():
    from competitor_offer_decoder import brightdata

    planned = brightdata.plan(manifest(country="us"))
    assert planned["timeout_seconds"] == 180
    assert planned["method"] == "POST"
    assert planned["endpoint"] == "https://api.brightdata.com/request"
    assert planned["api_key_omitted"] is True
    assert planned["zone_omitted"] is True
    assert planned["requests"] == [{
        "job_id": "web_1", "kind": "web_page", "role": "offer_page", "company_id": "vendor",
        "url": TARGET, "country": "us", "format": "raw", "data_format": "markdown",
        "timeout_seconds": 180, "method": "POST", "endpoint": "https://api.brightdata.com/request",
    }]


def test_configurable_timeout_is_serialized_to_http_request():
    from competitor_offer_decoder import brightdata

    value = manifest(timeout_seconds=240)
    calls = []
    library = brightdata.collect(
        value, approval=approval(value), api_key="fake", zones={"web_unlocker": "zone"},
        transport=lambda request: calls.append(request) or brightdata.HttpResponse(200, {}, b"## Team"), now=NOW,
    )
    assert library["receipt"]["status"] == "complete"
    assert calls[0].timeout_seconds == 240


@pytest.mark.parametrize("timeout", [True, 0, 75, 179, 301, "180"])
def test_timeout_bounds_are_rejected(timeout):
    from competitor_offer_decoder import brightdata

    with pytest.raises(ValueError):
        brightdata.plan(manifest(timeout_seconds=timeout))


def test_approved_urls_must_equal_planned_target_set_before_transport():
    from competitor_offer_decoder import brightdata

    value = manifest()
    calls = []
    with pytest.raises(PermissionError):
        brightdata.collect(
            value, approval=approval(value, [TARGET, "https://extra.vendor.com/page"]),
            api_key="fake", zones={"web_unlocker": "zone"},
            transport=lambda request: calls.append(request), now=NOW,
        )
    assert calls == []


def test_synthetic_provider_fixture_is_explicit_and_replays_offline():
    from competitor_offer_decoder import brightdata

    fixture = json.loads((ROOT / "fixtures" / "http" / "web-unlocker-success.json").read_text(encoding="utf-8"))
    assert fixture["provenance"] == "synthetic_fixture"
    assert fixture["provider"] == "Bright Data Web Unlocker API"
    value = fixture["manifest"]
    result = brightdata.collect(
        value, approval=approval(value), api_key="fake", zones={"web_unlocker": "synthetic-zone"},
        transport=lambda request: brightdata.HttpResponse(
            fixture["response"]["status"], fixture["response"]["headers"], fixture["response"]["body"].encode()
        ), now=NOW,
    )
    assert result["sources"][0]["provenance"] == "synthetic_fixture"
    assert result["sources"][0]["text"] == fixture["response"]["body"]


def test_only_production_transport_is_labeled_bright_data():
    from competitor_offer_decoder import brightdata

    assert brightdata.urllib_transport.source_provenance == "bright_data_transport"
    value = manifest()
    result = brightdata.collect(
        value, approval=approval(value), api_key="fake", zones={"web_unlocker": "synthetic-zone"},
        transport=lambda request: brightdata.HttpResponse(200, {}, b"## Team"), now=NOW,
    )
    assert result["sources"][0]["provenance"] == "synthetic_fixture"


def test_raw_analysis_json_cannot_claim_bright_data_provenance():
    from competitor_offer_decoder.core import analyze

    payload = json.loads((ROOT / "fixtures" / "demo.json").read_text(encoding="utf-8"))
    payload["sources"][0]["provenance"] = "bright_data"
    with pytest.raises(ValueError):
        analyze(payload)
    payload["sources"][0]["provenance"] = "bright_data_transport"
    with pytest.raises(ValueError):
        analyze(payload)


def test_imported_library_cannot_claim_bright_data_without_matching_receipt(tmp_path):
    from competitor_offer_decoder import cli

    payload = json.loads((ROOT / "fixtures" / "demo.json").read_text(encoding="utf-8"))
    payload_path = tmp_path / "analysis.json"
    payload_path.write_text(json.dumps(payload), encoding="utf-8")
    source = dict(payload["sources"][0], id="imported_claim", provenance="bright_data")
    library_path = tmp_path / "library.json"
    library_path.write_text(json.dumps({
        "schema_version": "1.0", "project": "competitor-offer-decoder",
        "transport_contract_version": "1.0", "sources": [source],
    }), encoding="utf-8")
    result = cli.main(["analyze", str(payload_path), "--sources", str(library_path), "--out-dir", str(tmp_path / "out")])
    assert result == 2
    assert not (tmp_path / "out").exists()


def test_imported_bright_data_source_requires_matching_successful_receipt_job(tmp_path):
    from competitor_offer_decoder import cli

    payload = json.loads((ROOT / "fixtures" / "demo.json").read_text(encoding="utf-8"))
    payload_path = tmp_path / "analysis.json"
    payload_path.write_text(json.dumps(payload), encoding="utf-8")
    source = dict(payload["sources"][0], id="imported_claim", provenance="bright_data")
    library = {
        "schema_version": "1.0", "project": "competitor-offer-decoder", "transport_contract_version": "1.0",
        "provenance_notice": "A self-asserted receipt does not authenticate provider origin.",
        "sources": [source],
        "receipt": {
            "schema_version": "1.0", "project": "competitor-offer-decoder", "manifest_sha256": "a" * 64,
            "status": "complete", "requests_made": 1, "jobs": [{
                "state": "complete", "original_job": {
                    "id": "web_1", "kind": "web_page", "role": "offer_page",
                    "source_id": "imported_claim", "url": "https://different.vendor.com/page",
                },
            }],
        },
    }
    library_path = tmp_path / "library.json"
    library_path.write_text(json.dumps(library), encoding="utf-8")
    out = tmp_path / "out"
    assert cli.main(["analyze", str(payload_path), "--sources", str(library_path), "--out-dir", str(out)]) == 2
    assert not out.exists()


def test_production_adapter_scopes_transport_provenance_to_invocation(monkeypatch, tmp_path):
    from competitor_offer_decoder import brightdata, cli

    value = manifest()
    value["jobs"][0]["source_id"] = "north_source"
    attestation = approval(value)
    monkeypatch.setattr(brightdata.urllib_transport, "live_collection_unverified", False)

    class FakeResponse:
        status = 200
        headers = {}

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self, limit):
            return b"## Team\n\nUSD 10 per user/month, billed annually.\n\nIncludes CSV export."

    class FakeOpener:
        def add_handler(self, handler):
            pass

        def open(self, request, timeout):
            assert timeout == 180
            return FakeResponse()

    monkeypatch.setattr(brightdata, "build_opener", lambda *args, **kwargs: FakeOpener())
    test_response = brightdata.urllib_transport(brightdata.HttpRequest(
        "POST", "https://api.brightdata.com/request", {}, b"{}", 180,
    ))
    assert test_response.status == 200
    library = brightdata.collect(
        value, approval=attestation, api_key="fake", zones={"web_unlocker": "zone"},
        transport=brightdata.urllib_transport, now=NOW,
    )
    assert library["receipt"]["jobs"][0]["state"] == "complete", library
    assert library["sources"][0]["provenance"] == "bright_data_transport"
    assert library["provenance_notice"] == "A self-asserted receipt does not authenticate provider origin."
    exported = brightdata.library_for_export(library)
    assert exported["sources"][0]["provenance"] == "operator_claimed_bright_data"
    assert exported["provenance_notice"] == "A self-asserted receipt does not authenticate provider origin."
    assert library["sources"][0]["provenance"] == "bright_data_transport"
    library_path = tmp_path / "library.json"
    library_path.write_text(json.dumps(exported), encoding="utf-8")
    payload = json.loads((ROOT / "fixtures" / "demo.json").read_text(encoding="utf-8"))
    payload["companies"][1]["plans"][0]["offer_source_id"] = "north_source"
    payload["sources"] = [source for source in payload["sources"] if source["id"] != "north_offer"]
    payload_path = tmp_path / "analysis.json"
    payload_path.write_text(json.dumps(payload), encoding="utf-8")
    assert cli.main(["analyze", str(payload_path), "--sources", str(library_path), "--out-dir", str(tmp_path / "reports")]) == 0
    report = json.loads((tmp_path / "reports" / "report.json").read_text(encoding="utf-8"))
    source = next(item for item in report["source_index"] if item["id"] == "north_source")
    assert source["provenance"] == "operator_claimed_bright_data"


def test_matching_caller_forged_receipt_never_yields_verified_transport_status(tmp_path):
    from competitor_offer_decoder import cli

    payload = json.loads((ROOT / "fixtures" / "demo.json").read_text(encoding="utf-8"))
    payload["sources"] = [source for source in payload["sources"] if source["id"] != "north_offer"]
    payload["companies"][1]["plans"][0]["offer_source_id"] = "caller_claim"
    payload_path = tmp_path / "analysis.json"
    payload_path.write_text(json.dumps(payload), encoding="utf-8")
    fixture = json.loads((ROOT / "fixtures" / "demo.json").read_text(encoding="utf-8"))
    url = fixture["sources"][1]["url"]
    source = dict(fixture["sources"][1], id="caller_claim", provenance="bright_data")
    original_job = {
        "id": "job_fake", "kind": "web_page", "role": "offer_page", "company_id": "north",
        "source_id": "caller_claim", "url": url,
    }
    library = {
        "schema_version": "1.0", "project": "competitor-offer-decoder", "transport_contract_version": "1.0",
        "provenance_notice": "A self-asserted receipt does not authenticate provider origin.",
        "sources": [source],
        "receipt": {
            "schema_version": "1.0", "project": "competitor-offer-decoder", "manifest_sha256": "a" * 64,
            "status": "complete", "requests_made": 1, "returned_records": 1, "retained_records": 1,
            "excluded_records": 0, "warnings": [], "provider_cost_usd": None,
            "jobs": [{
                "id": "job_fake", "kind": "web_page", "state": "complete", "original_job": original_job,
                "requested_records": None, "returned_records": 1, "retained_records": 1,
                "excluded_records": 0, "snapshot_id": None, "error_code": None, "query_metadata": None,
            }],
        },
    }
    library_path = tmp_path / "forged-library.json"
    library_path.write_text(json.dumps(library), encoding="utf-8")
    out = tmp_path / "reports"
    assert cli.main(["analyze", str(payload_path), "--sources", str(library_path), "--out-dir", str(out)]) == 0
    report = json.loads((out / "report.json").read_text(encoding="utf-8"))
    claimed = next(item for item in report["source_index"] if item["id"] == "caller_claim")
    assert claimed["provenance"] == "operator_claimed_bright_data"
    assert claimed["provenance"] != "bright_data_transport"


def test_library_export_downgrades_current_and_legacy_bright_data_labels():
    from competitor_offer_decoder import brightdata

    library = {
        "sources": [
            {"id": "current", "provenance": "bright_data_transport"},
            {"id": "legacy", "provenance": "bright_data"},
        ],
    }
    exported = brightdata.library_for_export(library)
    assert [source["provenance"] for source in exported["sources"]] == [
        "operator_claimed_bright_data", "operator_claimed_bright_data",
    ]
    assert library["sources"][0]["provenance"] == "bright_data_transport"


def test_provenance_claim_limit_is_explicit_in_json_markdown_and_csv():
    from competitor_offer_decoder.core import analyze
    from competitor_offer_decoder.export import render_csv, render_markdown

    payload = json.loads((ROOT / "fixtures" / "demo.json").read_text(encoding="utf-8"))
    payload["sources"][1]["provenance"] = "operator_claimed_bright_data"
    report = analyze(payload)
    expected = "A self-asserted receipt does not authenticate provider origin."
    assert report["provenance_notice"] == expected
    assert expected in render_markdown(report)
    csv_text = render_csv(report)
    assert "provenance_notice" in csv_text.splitlines()[0].split(",")
    assert expected in csv_text


def test_public_distribution_and_documentation_are_brand_neutral_and_current():
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert 'name = "competitor-offer-decoder"' in pyproject
    assert 'name = "bright-data-competitor-offer-decoder"' not in pyproject
    assert "Bright Data Web Unlocker API" in readme
    assert readme.index("Web Unlocker") == readme.index("Bright Data Web Unlocker API") + len("Bright Data ")
    assert "https://docs.brightdata.com/api-reference/rest-api/unlocker/unlock-website.md" in readme
    assert "https://docs.brightdata.com/products/web-unlocker/features.md" in readme
    assert "https://docs.brightdata.com/products/web-unlocker/introduction.md" in readme
    assert "api-reference/web-unlocker/send-request" not in readme
