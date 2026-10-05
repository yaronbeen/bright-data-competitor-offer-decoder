"""Independent acceptance tests derived from contract v1.0-draft, sections 3-4, 10."""

import copy
import json
import os
import socket
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "fixtures" / "demo.json"


def demo():
    return json.loads(DEMO.read_text(encoding="utf-8"))


def analyze(payload):
    from competitor_offer_decoder.core import analyze as run_analysis

    return run_analysis(payload)


def offer(report, company_id):
    return next(row for row in report["offers"] if row["company_id"] == company_id)


def test_od01_positive_fixture_decimal_totals_and_qualifications():
    report = analyze(demo())
    assert report["decision"] == "scenario_worksheet"
    assert report["analysis_method"] == "deterministic_rules_v1"
    # Contract section 3.4: any required unresolved decision makes the report needs_review.
    assert report["status"] == "needs_review"
    assert len(report["offers"]) == 3
    own, north, west = (offer(report, key) for key in ("harbor", "north", "west"))
    assert (own["base_due_per_billing_period"], own["inclusion_state"], own["scenario_status"]) == ("720.00", "not_stated", "unknown")
    assert (north["base_due_per_billing_period"], north["monthly_equivalent"], north["inclusion_state"], north["scenario_status"]) == ("600.00", "50.00", "explicitly_included", "meets_declared_checks")
    assert (west["base_due_per_billing_period"], west["inclusion_state"], west["scenario_status"]) == ("480.00", "explicitly_excluded", "fails_declared_checks")
    assert all("tax" in " ".join(row["unknown_terms"]).lower() or "fee" in " ".join(row["unknown_terms"]).lower() for row in report["offers"])
    assert not any("50.00 paid monthly" in str(value).lower() for value in report.values())
    assert "winner" not in report and "cheapest" not in report
    assert all(row["evidence"] for row in report["offers"])


def test_od02_monthly_preference_does_not_rewrite_annual_commitment():
    payload = demo()
    payload["scenario"]["billing_preference"] = "monthly"
    row = offer(analyze(payload), "north")
    assert row["billed_period"] == "annual"
    assert row["scenario_status"] == "fails_declared_checks"
    assert row["base_due_per_billing_period"] == "600.00"


def test_od03_rate_without_billing_clause_keeps_due_amount_unknown():
    payload = demo()
    payload["sources"][1]["text"] = "## Team\n\nUSD 10 per user/month.\n\nIncludes CSV export."
    row = offer(analyze(payload), "north")
    assert row["rate_state"] == "rate_only_billing_unknown"
    assert row["monthly_equivalent"] == "50.00"
    assert row["base_due_per_billing_period"] is None
    assert row["scenario_status"] == "unknown"


def test_od04_bare_dollar_without_hint_has_no_scenario_amount():
    payload = demo()
    payload["sources"][1]["text"] = "## Team\n\n$10 per user/month, billed annually.\n\nIncludes CSV export."
    row = offer(analyze(payload), "north")
    assert row["rate_state"] == "currency_unknown"
    assert row["currency"] is None
    assert row["monthly_equivalent"] is None
    assert row["base_due_per_billing_period"] is None


def test_od05_opposing_inclusion_sources_are_conflicting():
    payload = demo()
    payload["companies"][1]["plans"][0]["terms_source_ids"] = ["north_terms"]
    source = copy.deepcopy(payload["sources"][1])
    source.update(id="north_terms", role="terms_page", url="https://example.com/north/terms", text="## Team\n\nCSV export not included.")
    payload["sources"].append(source)
    row = offer(analyze(payload), "north")
    assert row["inclusion_state"] == "conflicting"
    assert row["scenario_status"] == "unknown"


def test_od06_heading_scope_prevents_cross_plan_price_and_feature_leaks():
    payload = demo()
    company = payload["companies"][1]
    company["plans"].append({"id": "pro", "name": "Pro", "offer_source_id": "north_offer", "heading": "Pro", "terms_source_ids": [], "currency_hint": None})
    payload["sources"][1]["text"] += "\n\n## Pro\n\nUSD 99 per user/month, billed annually.\n\nIncludes CSV export."
    report = analyze(payload)
    assert offer(report, "north")["observed_price"] == "10.00"
    pro = next(row for row in report["offers"] if row["company_id"] == "north" and row["plan_id"] == "pro")
    assert pro["observed_price"] == "99.00"


@pytest.mark.parametrize("text", [
    "## Team\n\nFrom USD 10 per user/month, billed annually.\n\nIncludes CSV export.",
    "## Team\n\nUSD 10 per user/month, billed annually.\n\nUSD 11 per user/month, billed annually.\n\nIncludes CSV export.",
    "## Team\n\nUSD 10 per user/month, billed annually.\n\n5 users for USD 40/month, billed monthly.\n\nIncludes CSV export.",
])
def test_od07_unsupported_from_multiple_prices_and_bundles_never_guess(text):
    payload = demo()
    payload["sources"][1]["text"] = text
    row = offer(analyze(payload), "north")
    assert row["rate_state"] == "unsupported_or_ambiguous_price"
    assert row["monthly_equivalent"] is None
    assert row["base_due_per_billing_period"] is None


def test_od08_matching_minimum_quantity_is_applied_and_disclosed():
    payload = demo()
    payload["scenario"]["quantity"] = 5
    payload["sources"][1]["text"] += "\n\nMinimum 10 user."
    row = offer(analyze(payload), "north")
    assert row["requested_quantity"] == 5
    assert row["effective_quantity"] == 10
    assert row["base_due_per_billing_period"] == "1200.00"
    assert row["calculation"]["quantity"] == 10
    assert row["evidence"]["minimum"]


def test_od09_currency_rows_are_not_converted_or_ranked():
    payload = demo()
    payload["companies"][1]["plans"][0]["currency_hint"] = "EUR"
    payload["sources"][1]["text"] = "## Team\n\nEUR 10 per user/month, billed annually.\n\nIncludes CSV export."
    report = analyze(payload)
    row = offer(report, "north")
    assert row["currency"] == "EUR"
    assert row["base_due_per_billing_period"] == "600.00"
    assert "winner" not in report and "ranking" not in report


def test_od10_incompatible_unit_has_no_scenario_arithmetic():
    payload = demo()
    payload["sources"][1]["text"] = "## Team\n\nUSD 10 per seat/month, billed annually.\n\nIncludes CSV export."
    row = offer(analyze(payload), "north")
    assert row["rate_state"] == "unsupported_or_ambiguous_price"
    assert row["monthly_equivalent"] is None
    assert row["base_due_per_billing_period"] is None
    # Contract section 6: an explicit incompatible unit fails the declared scenario checks.
    assert row["scenario_status"] == "fails_declared_checks"


def test_od11_decimal_precision_and_half_up_rounding():
    payload = demo()
    payload["scenario"].update(quantity=3, unit="user")
    payload["sources"][1]["text"] = "## Team\n\nUSD 0.10 per user/month, billed annually.\n\nIncludes CSV export."
    assert offer(analyze(payload), "north")["base_due_per_billing_period"] == "3.60"
    payload["scenario"]["quantity"] = 1
    payload["sources"][1]["text"] = "## Team\n\nUSD 1.00 per user/year, billed annually.\n\nIncludes CSV export."
    assert offer(analyze(payload), "north")["monthly_equivalent"] == "0.08"


@pytest.mark.parametrize("mutate", [
    lambda p: p.update(schema_version="2.0"),
    lambda p: p.update(unrecognized=True),
    lambda p: p["scenario"].update(quantity=True),
    lambda p: p["scenario"].update(quantity=0),
    lambda p: p["scenario"].update(unit="Users"),
    lambda p: p["scenario"].update(billing_preference="quarterly"),
    lambda p: p["scenario"].update(required_inclusion="  "),
    lambda p: p["companies"].append(copy.deepcopy(p["companies"][1])),
    lambda p: p["companies"].pop(0),
    lambda p: p["companies"][0]["plans"][0].update(offer_source_id="missing"),
])
def test_invalid_input_fails_as_value_error_before_analysis(mutate):
    payload = demo()
    mutate(payload)
    with pytest.raises((ValueError, TypeError)):
        analyze(payload)


def test_source_status_empty_unavailable_and_pending_never_support_price_or_absence():
    for status in ("empty", "unavailable", "pending"):
        payload = demo()
        payload["sources"][1].update(status=status, text="")
        row = offer(analyze(payload), "north")
        assert row["rate_state"] == "source_unavailable"
        assert row["observed_price"] is None
        assert row["inclusion_state"] not in {"explicitly_included", "explicitly_excluded"}


def test_source_backed_values_have_exact_citations_and_scope():
    report = analyze(demo())
    source_by_id = {source["id"]: source for source in demo()["sources"]}
    for row in report["offers"]:
        for ref in row["evidence"].values():
            refs = ref if isinstance(ref, list) else [ref]
            for citation in refs:
                source = source_by_id[citation["source_id"]]
                assert citation["quote"] in source["text"]
                assert citation["block_id"].startswith("b")
                assert source["url"].startswith("https://")


def test_unheaded_source_with_heading_selection_is_unknown_not_cross_joined():
    payload = demo()
    payload["sources"][1]["text"] = "USD 10 per user/month, billed annually. Includes CSV export."
    row = offer(analyze(payload), "north")
    assert row["rate_state"] == "unsupported_or_ambiguous_price"
    assert row["inclusion_state"] == "not_stated"


def test_analysis_is_byte_deterministic_and_independent_of_environment():
    from competitor_offer_decoder.export import render_csv, render_markdown

    payload = demo()
    first = analyze(payload)
    os.environ["TZ"] = "Pacific/Auckland"
    os.environ["BRIGHT_DATA_API_KEY"] = "must-not-be-read"
    second = analyze(payload)
    assert json.dumps(first, ensure_ascii=False, sort_keys=True, separators=(",", ":")) == json.dumps(second, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    assert render_markdown(first) == render_markdown(second)
    assert render_csv(first) == render_csv(second)


def test_analysis_makes_no_socket_connections(monkeypatch):
    def denied(*args, **kwargs):
        raise AssertionError("offline analysis attempted network access")

    monkeypatch.setattr(socket, "create_connection", denied)
    assert analyze(demo())["offers"]


def test_csv_formula_injection_is_escaped_but_json_keeps_exact_source_text():
    from competitor_offer_decoder.export import render_csv

    report = analyze(demo())
    report["offers"][0]["unknown_terms"] = ["=IMPORTXML(\"x\")"]
    assert report["offers"][0]["unknown_terms"][0] == "=IMPORTXML(\"x\")"
    assert "'=IMPORTXML" in render_csv(report)


def test_markdown_escapes_untrusted_html_and_delimiters():
    from competitor_offer_decoder.export import render_markdown

    payload = demo()
    payload["scenario"]["required_inclusion"] = "<script>alert(1)</script> | `x`"
    payload["sources"][1]["text"] = "## Team\n\nUSD 10 per user/month, billed annually.\n\nIncludes <script>alert(1)</script> | `x`."
    rendered = render_markdown(analyze(payload))
    assert "<script>" not in rendered
    assert "\\|" in rendered


def test_report_has_scope_method_unknowns_and_synthetic_provenance():
    report = analyze(demo())
    assert report["scope"]
    assert report["source_index"]
    assert report["warnings"] is not None
    assert all(item["provenance"] == "synthetic_fixture" for item in report["source_index"])
    from competitor_offer_decoder.export import render_markdown

    md = render_markdown(report).lower()
    assert "synthetic" in md
    assert "not affiliated with or endorsed by bright data" in md
    assert "not stated" in md or "unknown" in md


def test_rendered_artifacts_use_fixed_csv_columns():
    from competitor_offer_decoder.export import render_csv

    columns = render_csv(analyze(demo())).splitlines()[0].split(",")
    assert columns == ["company_id", "plan_id", "role", "currency", "unit", "requested_quantity", "effective_quantity", "observed_rate", "price_period", "billed_period", "monthly_equivalent", "base_due_per_billing_period", "inclusion_state", "scenario_status", "unknown_terms", "evidence_source_ids", "evidence_urls", "provenance_notice"]


def test_page_only_project_rejects_serp_and_resume_without_requests():
    from competitor_offer_decoder import brightdata

    with pytest.raises((ValueError, NotImplementedError)):
        brightdata.plan({"schema_version": "1.0", "project": "competitor-offer-decoder", "jobs": [{"id": "s1", "kind": "serp", "role": "discovery"}]})
    calls = []
    with pytest.raises((ValueError, NotImplementedError)):
        brightdata.resume({}, approval={}, api_key="fake", transport=lambda request: calls.append(request), now="2026-10-04T10:00:00Z")
    assert calls == []


def test_collection_is_explicit_and_missing_live_gates_fail_before_transport():
    from competitor_offer_decoder import brightdata

    manifest = {"schema_version": "1.0", "project": "competitor-offer-decoder", "jobs": []}
    calls = []
    for kwargs in (
        {"approval": None, "api_key": "", "zones": {}},
        {"approval": {}, "api_key": "fake", "zones": {}},
    ):
        with pytest.raises((ValueError, PermissionError)):
            brightdata.collect(manifest, transport=lambda request: calls.append(request), now="2026-10-04T10:00:00Z", **kwargs)
    assert calls == []


def test_unapproved_fixture_or_sensitive_urls_are_rejected_before_transport():
    from competitor_offer_decoder import brightdata

    manifest = {"schema_version": "1.0", "project": "competitor-offer-decoder", "jobs": [
        {"id": "w1", "kind": "web_page", "role": "offer_page", "source_id": "offer", "url": "https://example.com/pricing?token=secret"}
    ]}
    calls = []
    with pytest.raises((ValueError, PermissionError)):
        brightdata.plan(manifest)
    with pytest.raises((ValueError, PermissionError)):
        brightdata.collect(manifest, approval={}, api_key="fake", zones={"web_unlocker": "zone"}, transport=lambda request: calls.append(request), now="2026-10-04T10:00:00Z")
    assert calls == []


def test_disabled_person_data_import_is_rejected_without_raw_logging(capsys):
    from competitor_offer_decoder import brightdata

    records = [{"url": "https://example.com/reviews/1", "review_text": "Useful offer details.", "review_id": "r1", "reviewer_name": "Private Name", "profile_url": "https://example.com/person", "author_hash": "hash", "address": "private address", "replies": ["private reply"]}]
    with pytest.raises((ValueError, NotImplementedError)):
        brightdata.normalize_export("amazon_reviews", records, role="offer_page", source_url="https://example.com/reviews", observed_at="2026-10-04T10:00:00Z", source_prefix="import")
    assert capsys.readouterr().out == ""
    assert capsys.readouterr().err == ""


def test_existing_artifacts_are_not_overwritten_without_explicit_flag(tmp_path):
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT)
    (tmp_path / "report.json").write_text("sentinel", encoding="utf-8")
    output = subprocess.run([sys.executable, "-m", "competitor_offer_decoder", "analyze", str(DEMO), "--out-dir", str(tmp_path)], cwd=ROOT, env=env, capture_output=True, text=True)
    assert output.returncode == 2
    assert (tmp_path / "report.json").read_text(encoding="utf-8") == "sentinel"


def test_cli_module_help_and_offline_analysis_without_provider_keys(tmp_path):
    env = {key: value for key, value in os.environ.items() if not key.startswith("BRIGHT_DATA_")}
    env["PYTHONPATH"] = str(ROOT)
    help_run = subprocess.run([sys.executable, "-m", "competitor_offer_decoder", "--help"], cwd=ROOT, env=env, capture_output=True, text=True)
    assert help_run.returncode == 0
    output = subprocess.run([sys.executable, "-m", "competitor_offer_decoder", "analyze", str(DEMO), "--out-dir", str(tmp_path)], cwd=ROOT, env=env, capture_output=True, text=True)
    assert output.returncode == 0, output.stderr
    assert (tmp_path / "report.json").exists()
    assert (tmp_path / "offers.md").exists()
    assert (tmp_path / "offers.csv").exists()


def test_dry_run_reports_zero_requests_and_writes_no_artifacts(tmp_path):
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT)
    output = subprocess.run([sys.executable, "-m", "competitor_offer_decoder", "analyze", str(DEMO), "--out-dir", str(tmp_path), "--dry-run"], cwd=ROOT, env=env, capture_output=True, text=True)
    assert output.returncode == 0, output.stderr
    assert '"requests_made": 0' in output.stdout
    assert list(tmp_path.iterdir()) == []


def test_common_input_size_and_text_limits_are_enforced():
    payload = demo()
    payload["sources"][0]["text"] = "x" * 50001
    with pytest.raises((ValueError, TypeError)):
        analyze(payload)
    payload = demo()
    template = payload["sources"][0]
    payload["sources"] = []
    for index in range(43):
        source = copy.deepcopy(template)
        source.update(id=f"note_{index}", kind="operator_note", role="context_note", url=None, text="x" * 50000)
        payload["sources"].append(source)
    with pytest.raises((ValueError, TypeError)):
        analyze(payload)


def test_identical_repeated_price_is_deduplicated():
    payload = demo()
    payload["sources"][1]["text"] = "## Team\n\nUSD 10 per user/month, billed annually.\n\nUSD 10 per user/month, billed annually.\n\nIncludes CSV export."
    row = offer(analyze(payload), "north")
    assert row["rate_state"] == "supported"
    assert row["base_due_per_billing_period"] == "600.00"


def test_explicit_currency_code_conflicting_with_hint_is_ambiguous():
    payload = demo()
    payload["companies"][1]["plans"][0]["currency_hint"] = "EUR"
    row = offer(analyze(payload), "north")
    assert row["rate_state"] == "unsupported_or_ambiguous_price"
    assert row["base_due_per_billing_period"] is None


def test_feature_phrase_boundaries_do_not_infer_csv_export_from_export():
    payload = demo()
    payload["sources"][1]["text"] = "## Team\n\nUSD 10 per user/month, billed annually.\n\nIncludes export."
    assert offer(analyze(payload), "north")["inclusion_state"] == "not_stated"


def test_own_unknowns_become_editorial_checks_not_competitor_answers():
    report = analyze(demo())
    assert "State whether CSV export is included." in report["own_clarity_notes"]
    assert all("North" not in note and "West" not in note for note in report["own_clarity_notes"])


def test_stale_sources_warn_but_keep_evidence():
    payload = demo()
    payload["as_of"] = "2026-11-04T10:00:01Z"
    report = analyze(payload)
    assert offer(report, "north")["observed_price"] == "10.00"
    assert any(warning["code"] == "stale_source" for warning in report["warnings"])


def test_html_document_and_ascii_controls_are_rejected():
    for text in ("<!doctype html><body>price</body>", "## Team\n\nUSD 10\x00 per user/month, billed annually."):
        payload = demo()
        payload["sources"][1]["text"] = text
        with pytest.raises((ValueError, TypeError)):
            analyze(payload)


def test_account_rate_is_flat_only_for_account_scenario():
    payload = demo()
    payload["scenario"].update(quantity=1, unit="account")
    payload["sources"][1]["text"] = "## Team\n\nUSD 10 per account/month, billed monthly.\n\nIncludes CSV export."
    row = offer(analyze(payload), "north")
    assert row["monthly_equivalent"] == "10.00"
    payload["scenario"]["unit"] = "user"
    row = offer(analyze(payload), "north")
    assert row["monthly_equivalent"] is None


def test_duplicate_heading_scope_is_unknown():
    payload = demo()
    payload["sources"][1]["text"] += "\n\n## Team\n\nUSD 1 per user/month, billed monthly."
    row = offer(analyze(payload), "north")
    assert row["scenario_status"] == "unknown"
    assert row["base_due_per_billing_period"] is None
