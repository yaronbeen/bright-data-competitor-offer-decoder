"""Regression tests for the pre-publication security review blockers."""

import copy
import hashlib
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest


NOW = "2026-10-04T10:00:00Z"


def manifest(*, count=1, url="https://pricing.vendor.com/team"):
    jobs = [
        {
            "id": f"web_{index}",
            "kind": "web_page",
            "role": "offer_page" if index == 0 else "terms_page",
            "source_id": f"source_{index}",
            "url": url if count == 1 else f"https://pricing{index}.vendor.com/team",
        }
        for index in range(count)
    ]
    return {"schema_version": "1.0", "project": "competitor-offer-decoder", "jobs": jobs}


def approval(value, *, max_retained_records=1):
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return {
        "schema_version": "1.0",
        "project": "competitor-offer-decoder",
        "manifest_sha256": hashlib.sha256(encoded).hexdigest(),
        "expires_at": "2026-10-05T10:00:00Z",
        "max_requests": len(value["jobs"]),
        "max_retained_records": max_retained_records,
        "approved_urls": [job["url"] for job in value["jobs"]],
        "account_budget_confirmed": True,
        "target_permissions_confirmed": True,
        "remote_resolution_risk_accepted": True,
    }


@pytest.mark.parametrize("status", [301, 302, 303, 307, 308])
def test_urllib_transport_never_follows_api_redirect_or_replays_token(status):
    from competitor_offer_decoder import brightdata

    requests = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            requests.append(("POST", self.path, self.headers.get("Authorization")))
            self.send_response(status)
            self.send_header("Location", "/redirected")
            self.end_headers()

        def do_GET(self):
            requests.append(("GET", self.path, self.headers.get("Authorization")))
            self.send_response(200)
            self.end_headers()

        def log_message(self, format, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        request = brightdata.HttpRequest(
            "POST",
            f"http://127.0.0.1:{server.server_port}/request",
            {"Authorization": "Bearer fake-secret-token", "Content-Type": "application/json"},
            b"{}",
            2,
        )
        result = brightdata.urllib_transport(request)
    finally:
        server.shutdown()
        thread.join()
        server.server_close()

    assert result.status == status
    assert requests == [("POST", "/request", "Bearer fake-secret-token")]


@pytest.mark.parametrize(
    "url",
    [
        "https://pricing.vendor.com/team?plan=team",
        "https://pricing.vendor.com/team?%61pi_key=secret",
        "https://pricing.vendor.com/team?token%3Dsecret",
        "https://pricing.vendor.com/team?next=https%3A%2F%2Fevil.invalid",
    ],
)
def test_all_live_query_strings_are_rejected_without_persisting_values(url):
    from competitor_offer_decoder import brightdata

    value = manifest(url=url)
    with pytest.raises(ValueError) as caught:
        brightdata.plan(value)
    assert "secret" not in str(caught.value)
    assert url not in str(caught.value)


def test_retained_record_allowance_stops_before_second_paid_call():
    from competitor_offer_decoder import brightdata

    value = manifest(count=2)
    calls = []

    def transport(request):
        calls.append(request)
        return brightdata.HttpResponse(200, {}, b"## Team\n\nUSD 10 per user/month, billed annually.")

    library = brightdata.collect(
        value,
        approval=approval(value, max_retained_records=1),
        api_key="fake-secret-token",
        zones={"web_unlocker": "zone"},
        transport=transport,
        now=NOW,
    )
    assert len(calls) == 1
    assert len(library["sources"]) == 1
    assert library["receipt"]["retained_records"] == 1
    assert library["receipt"]["status"] == "partial"
    assert library["receipt"]["jobs"][1]["state"] == "not_attempted"
    assert any(item["code"] == "provider_limit_exceeded" for item in library["receipt"]["warnings"])


def test_production_transport_is_fail_closed_before_dispatch(monkeypatch):
    from competitor_offer_decoder import brightdata

    value = manifest()
    with pytest.raises(PermissionError, match="unverified"):
        brightdata.collect(
            value,
            approval=approval(value),
            api_key="fake-secret-token",
            zones={"web_unlocker": "zone"},
            transport=brightdata.urllib_transport,
            now=NOW,
        )


def test_urllib_timeout_has_typed_completion_unknown_signal():
    from competitor_offer_decoder import brightdata

    dispatched = threading.Event()

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            dispatched.set()
            time.sleep(1.5)
            self.send_response(200)
            self.end_headers()

        def log_message(self, format, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        request = brightdata.HttpRequest("POST", f"http://127.0.0.1:{server.server_port}/request", {}, b"{}", 1)
        with pytest.raises(brightdata.TransportTimeout):
            brightdata.urllib_transport(request)
        assert dispatched.is_set()
    finally:
        server.shutdown()
        thread.join()
        server.server_close()


def test_typed_transport_timeout_becomes_completion_unknown_receipt():
    from competitor_offer_decoder import brightdata

    value = manifest(count=2)

    def timeout(request):
        raise brightdata.TransportTimeout()

    library = brightdata.collect(
        value,
        approval=approval(value),
        api_key="fake-secret-token",
        zones={"web_unlocker": "zone"},
        transport=timeout,
        now=NOW,
    )
    assert library["receipt"]["status"] == "completion_unknown"
    assert library["receipt"]["jobs"][0]["state"] == "completion_unknown"
    assert library["receipt"]["jobs"][1]["state"] == "not_attempted"


def test_markdown_untrusted_display_fields_are_single_line_and_not_links():
    from competitor_offer_decoder.core import analyze
    from competitor_offer_decoder.export import render_markdown

    payload = json.loads((__import__("pathlib").Path(__file__).parents[1] / "fixtures" / "demo.json").read_text())
    payload = copy.deepcopy(payload)
    payload["companies"][1]["name"] = "North\n[click](https://evil.invalid)"
    rendered = render_markdown(analyze(payload))
    assert "### North [click]" not in rendered
    assert "\\[click\\]\\(https://evil.invalid\\)" in rendered


def test_json_reader_uses_bounded_file_descriptor_read_not_path_read_text(monkeypatch, tmp_path):
    from competitor_offer_decoder.cli import _read_json

    source = tmp_path / "input.json"
    source.write_bytes(b'{"safe":true}')

    def unbounded_read_forbidden(*args, **kwargs):
        raise AssertionError("Path.read_text is an unbounded read")

    monkeypatch.setattr(Path, "read_text", unbounded_read_forbidden)
    assert _read_json(source) == {"safe": True}


def test_query_urls_are_rejected_across_analysis_library_and_import_without_artifacts(tmp_path, capsys):
    from competitor_offer_decoder import brightdata, cli
    from competitor_offer_decoder.core import analyze

    payload = json.loads((Path(__file__).parents[1] / "fixtures" / "demo.json").read_text(encoding="utf-8"))
    payload["sources"][0]["url"] = "https://example.com/harbor/pricing?token=must-not-persist"
    with pytest.raises(ValueError):
        analyze(payload)

    clean_payload = json.loads((Path(__file__).parents[1] / "fixtures" / "demo.json").read_text(encoding="utf-8"))
    input_path = tmp_path / "input.json"
    input_path.write_text(json.dumps(clean_payload), encoding="utf-8")
    unsafe = copy.deepcopy(clean_payload["sources"][0])
    unsafe.update(id="unsafe_library", url="https://example.com/page?secret=must-not-persist")
    library_path = tmp_path / "library.json"
    library_path.write_text(json.dumps({"project": "competitor-offer-decoder", "sources": [unsafe]}), encoding="utf-8")
    out_dir = tmp_path / "out"
    assert cli.main(["analyze", str(input_path), "--sources", str(library_path), "--out-dir", str(out_dir)]) == 2
    assert not out_dir.exists()
    assert "must-not-persist" not in capsys.readouterr().err

    with pytest.raises(ValueError):
        brightdata.normalize_export(
            "web_page", "## Team", role="offer_page",
            source_url="https://example.com/page?secret=must-not-persist",
            observed_at=NOW, source_prefix="import",
        )


def test_json_markdown_and_csv_never_render_query_bearing_source_urls():
    from competitor_offer_decoder.core import analyze
    from competitor_offer_decoder.export import render_csv, render_markdown

    payload = json.loads((Path(__file__).parents[1] / "fixtures" / "demo.json").read_text(encoding="utf-8"))
    report = analyze(payload)
    rendered = json.dumps(report) + render_markdown(report) + render_csv(report)
    assert "?" not in "".join(item["url"] or "" for item in report["source_index"])
    assert "must-not-persist" not in rendered


@pytest.mark.parametrize(
    "url",
    [
        "://".join(("https", "user%40name:secret@vendor.com/page")),
        "https://user%3Asecret@vendor.com/page",
        "https://user%2Fname@vendor.com/page",
        "https://user%5Cname@vendor.com/page",
        "://".join(("https", "%75ser:secret@vendor.com/page")),
        "https://vendor%2ecom/page",
        "https://@vendor.com/page",
        "https://:@vendor.com/page",
    ],
)
def test_percent_encoded_authority_delimiters_are_rejected_across_source_paths(url, tmp_path):
    from competitor_offer_decoder import brightdata, cli
    from competitor_offer_decoder.core import analyze

    payload = json.loads((Path(__file__).parents[1] / "fixtures" / "demo.json").read_text(encoding="utf-8"))
    payload["sources"][0]["url"] = url
    with pytest.raises(ValueError) as analysis_error:
        analyze(payload)
    assert url not in str(analysis_error.value)

    with pytest.raises(ValueError) as import_error:
        brightdata.normalize_export(
            "web_page", "## Team", role="offer_page", source_url=url,
            observed_at=NOW, source_prefix="import",
        )
    assert url not in str(import_error.value)

    value = manifest(url=url)
    with pytest.raises(ValueError) as planning_error:
        brightdata.plan(value)
    assert url not in str(planning_error.value)

    calls = []
    with pytest.raises(ValueError):
        brightdata.collect(
            value, approval=approval(value), api_key="fake", zones={"web_unlocker": "zone"},
            transport=lambda request: calls.append(request), now=NOW,
        )
    assert calls == []

    # Invalid input must stop before JSON, Markdown, or CSV artifacts are created.
    input_path = tmp_path / "unsafe.json"
    input_path.write_text(json.dumps(payload), encoding="utf-8")
    out_dir = tmp_path / "reports"
    assert cli.main(["analyze", str(input_path), "--out-dir", str(out_dir)]) == 2
    assert not out_dir.exists()

    clean_payload = json.loads((Path(__file__).parents[1] / "fixtures" / "demo.json").read_text(encoding="utf-8"))
    safe_input_path = tmp_path / "safe-input.json"
    safe_input_path.write_text(json.dumps(clean_payload), encoding="utf-8")
    unsafe_source = copy.deepcopy(clean_payload["sources"][0])
    unsafe_source.update(id="encoded_authority", url=url)
    library_path = tmp_path / "encoded-library.json"
    library_path.write_text(json.dumps({"project": "competitor-offer-decoder", "sources": [unsafe_source]}), encoding="utf-8")
    library_out = tmp_path / "library-reports"
    assert cli.main([
        "analyze", str(safe_input_path), "--sources", str(library_path), "--out-dir", str(library_out),
    ]) == 2
    assert not library_out.exists()
