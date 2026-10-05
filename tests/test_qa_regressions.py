"""Regression tests for the independent code and QA review."""

import argparse
import copy
import hashlib
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "fixtures" / "demo.json"
NOW = "2026-10-04T10:00:00Z"


def demo():
    return json.loads(DEMO.read_text(encoding="utf-8"))


def manifest(jobs):
    return {"schema_version": "1.0", "project": "competitor-offer-decoder", "jobs": jobs}


def job(index, role="offer_page", company_id=None):
    value = {
        "id": f"web_{index}", "kind": "web_page", "role": role,
        "source_id": f"source_{index}", "url": f"https://pricing{index}.vendor.com/team",
    }
    if company_id is not None:
        value["company_id"] = company_id
    return value


def approval(value, retained=8):
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return {
        "schema_version": "1.0", "project": "competitor-offer-decoder",
        "manifest_sha256": hashlib.sha256(encoded).hexdigest(),
        "expires_at": "2026-10-05T10:00:00Z", "max_requests": len(value["jobs"]),
        "max_retained_records": retained, "approved_urls": [item["url"] for item in value["jobs"]],
        "account_budget_confirmed": True, "target_permissions_confirmed": True,
        "remote_resolution_risk_accepted": True,
    }


def response(brightdata, status=200, body=b"## Team\n\nUSD 10 per user/month, billed annually."):
    return brightdata.HttpResponse(status, {}, body)


def test_unavailable_selected_terms_blocks_positive_qualification_and_report_is_needs_review():
    from competitor_offer_decoder.core import analyze

    payload = demo()
    terms = copy.deepcopy(payload["sources"][1])
    terms.update(id="north_terms", role="terms_page", url="https://example.com/north/terms", status="unavailable", text="")
    payload["sources"].append(terms)
    payload["companies"][1]["plans"][0]["terms_source_ids"] = ["north_terms"]
    row = next(item for item in analyze(payload)["offers"] if item["company_id"] == "north")
    report = analyze(payload)
    assert row["scenario_status"] == "unknown"
    assert any("unavailable" in item.casefold() for item in row["unknown_terms"])
    assert report["status"] == "needs_review"


def test_conflicting_required_inclusion_makes_report_needs_review():
    from competitor_offer_decoder.core import analyze

    payload = demo()
    terms = copy.deepcopy(payload["sources"][1])
    terms.update(id="north_terms", role="terms_page", url="https://example.com/north/terms", text="CSV export not included.")
    payload["sources"].append(terms)
    payload["companies"][1]["plans"][0]["terms_source_ids"] = ["north_terms"]
    assert analyze(payload)["status"] == "needs_review"


@pytest.mark.parametrize(
    "text,expected_issue",
    [
        ("## Team\n\nFrom USD 10 per user/month, billed annually.\n\nCSV export not included.", "price"),
        ("## Team\n\nUSD 10 per user/month.\n\nCSV export not included.", "billing"),
    ],
)
def test_report_readiness_is_independent_from_a_definitive_failed_check(text, expected_issue):
    from competitor_offer_decoder.core import analyze

    payload = demo()
    payload["sources"][1]["text"] = text
    report = analyze(payload)
    row = next(item for item in report["offers"] if item["company_id"] == "north")
    assert row["scenario_status"] == "fails_declared_checks"
    assert expected_issue in row["readiness_issues"]
    assert report["status"] == "needs_review"


def test_unsupported_price_like_candidate_is_preserved_cited_and_rendered_unknown():
    from competitor_offer_decoder.core import analyze
    from competitor_offer_decoder.export import render_markdown

    payload = demo()
    payload["sources"][1]["text"] = "## Team\n\nFrom USD 10 per user/month, billed annually.\n\nIncludes CSV export."
    row = next(item for item in analyze(payload)["offers"] if item["company_id"] == "north")
    assert row["observed_price"] is None
    assert row["price_candidates"] == ["From USD 10 per user/month, billed annually."]
    assert row["evidence"]["price_candidates"][0]["quote"] == row["price_candidates"][0]
    rendered = render_markdown(analyze(payload))
    assert "Observed rate: unknown" in rendered
    assert "Unsupported price candidate" in rendered


def test_success_then_http_failure_is_partial_not_failed():
    from competitor_offer_decoder import brightdata

    value = manifest([job(0), job(1, "terms_page")])
    calls = []

    def transport(request):
        calls.append(request)
        return response(brightdata) if len(calls) == 1 else response(brightdata, 500, b"private provider text")

    library = brightdata.collect(value, approval=approval(value), api_key="secret", zones={"web_unlocker": "zone"}, transport=transport, now=NOW)
    assert library["receipt"]["status"] == "partial"
    assert library["receipt"]["retained_records"] == 1
    assert library["receipt"]["jobs"][0]["state"] == "complete"
    assert library["receipt"]["jobs"][1]["state"] == "failed"


def test_manifest_company_limits_and_one_role_each_per_company():
    from competitor_offer_decoder import brightdata

    valid_jobs = [job(index, "offer_page", f"company_{index}") for index in range(4)]
    valid_jobs += [job(index + 4, "terms_page", f"company_{index}") for index in range(4)]
    assert len(brightdata.plan(manifest(valid_jobs))["requests"]) == 8
    with pytest.raises(ValueError):
        brightdata.plan(manifest([job(index, "offer_page", f"company_{index}") for index in range(5)]))
    with pytest.raises(ValueError):
        brightdata.plan(manifest([job(0, "offer_page", "same"), job(1, "offer_page", "same")]))
    five_companies = [
        job(0, "offer_page", "one"), job(1, "offer_page", "two"), job(2, "offer_page", "three"),
        job(3, "terms_page", "four"), job(4, "terms_page", "five"),
    ]
    with pytest.raises(ValueError):
        brightdata.plan(manifest(five_companies))


@pytest.mark.parametrize(
    "invalid",
    [
        {"status": True, "headers": {}, "body": b"ok"},
        {"status": 99, "headers": {}, "body": b"ok"},
        {"status": 200, "headers": [], "body": b"ok"},
        {"status": 200, "headers": {"x": 1}, "body": b"ok"},
        {"status": 200, "headers": {}, "body": "not-bytes"},
    ],
)
def test_invalid_http_response_dto_is_safe_invalid_response(invalid):
    from competitor_offer_decoder import brightdata

    value = manifest([job(0)])
    library = brightdata.collect(
        value, approval=approval(value), api_key="secret", zones={"web_unlocker": "zone"},
        transport=lambda request: brightdata.HttpResponse(**invalid), now=NOW,
    )
    assert library["receipt"]["status"] == "failed"
    assert library["receipt"]["jobs"][0]["error_code"] == "invalid_response"
    assert library["sources"] == []


def test_only_referenced_sources_drive_scope_counts_and_status():
    from competitor_offer_decoder.core import analyze

    payload = demo()
    payload["sources"][0]["text"] += "\n\nIncludes CSV export."
    extra = copy.deepcopy(payload["sources"][0])
    extra.update(id="unused_offer", url="https://example.com/unused", status="unavailable", text="")
    payload["sources"].append(extra)
    report = analyze(payload)
    assert report["summary"] == {"analyzed_sources": 3, "excluded_sources": 1, "output_rows": 3}
    assert report["scope"]["source_ids"] == ["harbor_offer", "north_offer", "west_offer"]
    assert any(item["code"] == "unreferenced_source" and item["source_ids"] == ["unused_offer"] for item in report["warnings"])
    assert report["status"] == "ok"


def test_default_as_of_uses_parsed_datetime_not_timestamp_lexical_order():
    from competitor_offer_decoder.core import analyze

    payload = demo()
    payload.pop("as_of")
    payload["sources"][0]["observed_at"] = "2026-10-04T10:00:00Z"
    payload["sources"][1]["observed_at"] = "2026-10-04T10:00:00.9Z"
    payload["sources"][2]["observed_at"] = "2026-10-04T10:00:00.10Z"
    assert analyze(payload)["scope"]["as_of"] == "2026-10-04T10:00:00.9Z"


def test_collect_output_is_reserved_before_transport_boundary(monkeypatch, tmp_path):
    from competitor_offer_decoder import cli

    value = manifest([job(0)])
    manifest_path = tmp_path / "manifest.json"
    approval_path = tmp_path / "approval.json"
    manifest_path.write_text(json.dumps(value), encoding="utf-8")
    approval_path.write_text(json.dumps(approval(value)), encoding="utf-8")
    out = tmp_path / "library.json"

    monkeypatch.setenv("BRIGHT_DATA_API_KEY", "fake")
    monkeypatch.setenv("BRIGHT_DATA_WEB_UNLOCKER_ZONE", "zone")

    def fake_collect(*args, **kwargs):
        assert list(tmp_path.glob(".library.json.*.tmp")), "destination was not reserved before collection"
        assert out.exists(), "the exact no-overwrite destination was not atomically claimed"
        assert (tmp_path / ".library.json.lock").exists(), "the destination lock was not held"
        return {
            "schema_version": "1.0", "project": "competitor-offer-decoder", "transport_contract_version": "1.0",
            "sources": [], "receipt": {"status": "complete", "requests_made": 1},
        }

    monkeypatch.setattr(cli.brightdata, "collect", fake_collect)
    args = argparse.Namespace(
        manifest=manifest_path, out=out, live=True, accept_charges=True, approval=approval_path,
        dry_run=False, overwrite=False,
    )
    assert cli._collect_command(args) == 0
    assert out.exists()
    assert not list(tmp_path.glob("*.tmp"))


def test_unicode_csv_formula_prefix_is_escaped():
    from competitor_offer_decoder.core import analyze
    from competitor_offer_decoder.export import render_csv

    report = analyze(demo())
    report["offers"][0]["unknown_terms"] = ["\u2007\u200b=IMPORTXML(\"x\")"]
    assert "'\u2007\u200b=IMPORTXML" in render_csv(report)


@pytest.mark.parametrize("status,expected", [("partial", 4), ("pending", 4), ("failed", 3), ("completion_unknown", 3)])
def test_collection_receipt_status_has_contract_exit_code_and_safe_error(monkeypatch, tmp_path, capsys, status, expected):
    from competitor_offer_decoder import cli

    value = manifest([job(0)])
    manifest_path = tmp_path / "manifest.json"
    approval_path = tmp_path / "approval.json"
    manifest_path.write_text(json.dumps(value), encoding="utf-8")
    approval_path.write_text(json.dumps(approval(value)), encoding="utf-8")
    monkeypatch.setenv("BRIGHT_DATA_API_KEY", "fake")
    monkeypatch.setenv("BRIGHT_DATA_WEB_UNLOCKER_ZONE", "zone")
    monkeypatch.setattr(cli.brightdata, "collect", lambda *args, **kwargs: {
        "schema_version": "1.0", "project": "competitor-offer-decoder", "transport_contract_version": "1.0",
        "sources": [], "receipt": {"status": status, "requests_made": 1},
    })
    args = argparse.Namespace(
        manifest=manifest_path, out=tmp_path / "library.json", live=True, accept_charges=True,
        approval=approval_path, dry_run=False, overwrite=False,
    )
    assert cli._collect_command(args) == expected
    error = json.loads(capsys.readouterr().err)
    assert error["requests_made"] == 1
    assert "provider" not in error["message"].casefold() or error["code"] == "collection_provider_failure"


def test_cli_object_and_filesystem_errors_are_structured_and_safe(monkeypatch, tmp_path, capsys):
    from competitor_offer_decoder import cli

    invalid = tmp_path / "invalid.json"
    invalid.write_text("[]", encoding="utf-8")
    assert cli.main(["analyze", str(invalid), "--out-dir", str(tmp_path / "out")]) == 2
    assert json.loads(capsys.readouterr().err)["code"] == "invalid_input"

    def filesystem_failure(args):
        raise OSError("private filesystem detail")

    monkeypatch.setattr(cli, "_analyze_command", filesystem_failure)
    assert cli.main(["analyze", str(invalid), "--out-dir", str(tmp_path / "out")]) == 2
    error = capsys.readouterr().err
    assert json.loads(error)["code"] == "filesystem_error"
    assert "private filesystem detail" not in error


@pytest.mark.parametrize("url", ["https://vendor.com:444/page", "https://vendor.com/page#fragment", "https://user@vendor.com/page", "https://vendor.com/pa\x00ge"])
def test_offline_import_rejects_unsafe_controls_credentials_ports_and_fragments(url):
    from competitor_offer_decoder import brightdata

    with pytest.raises(ValueError):
        brightdata.normalize_export(
            "web_page", "## Team\n\nUSD 1 per user/month, billed monthly.", role="offer_page",
            source_url=url, observed_at=NOW, source_prefix="import",
        )


def test_destination_swap_is_detected_and_never_clobbered(tmp_path):
    from competitor_offer_decoder import cli

    output = tmp_path / "report.json"
    reservation = cli._reserve_output(output, overwrite=False)
    attacker = tmp_path / "attacker.json"
    attacker.write_text("swapped-by-racer", encoding="utf-8")
    attacker.replace(output)
    with pytest.raises(FileExistsError):
        cli._commit_reserved(reservation, output, "must-not-clobber")
    cli._discard_reserved(reservation, output)
    assert output.read_text(encoding="utf-8") == "swapped-by-racer"
    assert not (tmp_path / ".report.json.lock").exists()


def test_destination_swap_at_commit_boundary_is_rolled_back(monkeypatch, tmp_path):
    from competitor_offer_decoder import cli

    output = tmp_path / "report.json"
    reservation = cli._reserve_output(output, overwrite=False)
    attacker = tmp_path / "attacker.json"
    attacker.write_text("boundary-racer", encoding="utf-8")
    original_exchange = cli._exchange_paths
    calls = 0

    def racing_exchange(source, destination):
        nonlocal calls
        calls += 1
        if calls == 1:
            attacker.replace(output)
        return original_exchange(source, destination)

    monkeypatch.setattr(cli, "_exchange_paths", racing_exchange)
    with pytest.raises(FileExistsError):
        cli._commit_reserved(reservation, output, "must-not-clobber")
    cli._discard_reserved(reservation, output)
    assert calls == 2
    assert output.read_text(encoding="utf-8") == "boundary-racer"


def test_analyze_reserves_all_outputs_before_any_commit(monkeypatch, tmp_path):
    from competitor_offer_decoder import cli

    reservations = []
    commits = []
    original_reserve = cli._reserve_output
    original_commit = cli._commit_reserved

    def reserve(path, overwrite):
        result = original_reserve(path, overwrite)
        reservations.append(path.name)
        return result

    def commit(reservation, path, data):
        assert set(reservations) == {"report.json", "offers.md", "offers.csv"}
        commits.append(path.name)
        return original_commit(reservation, path, data)

    monkeypatch.setattr(cli, "_reserve_output", reserve)
    monkeypatch.setattr(cli, "_commit_reserved", commit)
    args = argparse.Namespace(input=DEMO, out_dir=tmp_path, sources=None, dry_run=False, overwrite=False)
    assert cli._analyze_command(args) == 0
    assert set(commits) == {"report.json", "offers.md", "offers.csv"}


def test_analyze_commit_failure_cleans_remaining_reservations_without_touching_unrelated_files(monkeypatch, tmp_path):
    from competitor_offer_decoder import cli

    unrelated = tmp_path / "keep.txt"
    unrelated.write_text("keep", encoding="utf-8")
    original_commit = cli._commit_reserved
    commits = 0

    def fail_second(reservation, path, data):
        nonlocal commits
        commits += 1
        if commits == 2:
            raise OSError("injected write failure")
        return original_commit(reservation, path, data)

    monkeypatch.setattr(cli, "_commit_reserved", fail_second)
    args = argparse.Namespace(input=DEMO, out_dir=tmp_path, sources=None, dry_run=False, overwrite=False)
    with pytest.raises(OSError):
        cli._analyze_command(args)
    assert unrelated.read_text(encoding="utf-8") == "keep"
    assert not (tmp_path / "report.json").exists()
    assert not (tmp_path / "offers.md").exists()
    assert not (tmp_path / "offers.csv").exists()
    assert not list(tmp_path.glob(".*.lock"))
    assert not list(tmp_path.glob(".*.tmp"))


def test_analyze_overwrite_failure_restores_all_original_artifacts(monkeypatch, tmp_path):
    from competitor_offer_decoder import cli

    names = ("report.json", "offers.md", "offers.csv")
    originals = {}
    for name in names:
        path = tmp_path / name
        path.write_text(f"original:{name}", encoding="utf-8")
        originals[name] = path.read_bytes()
    original_commit = cli._commit_reserved
    commits = 0

    def fail_second(reservation, path, data):
        nonlocal commits
        commits += 1
        if commits == 2:
            raise OSError("injected commit failure")
        return original_commit(reservation, path, data)

    monkeypatch.setattr(cli, "_commit_reserved", fail_second)
    args = argparse.Namespace(input=DEMO, out_dir=tmp_path, sources=None, dry_run=False, overwrite=True)
    with pytest.raises(OSError):
        cli._analyze_command(args)
    assert {name: (tmp_path / name).read_bytes() for name in names} == originals
    assert not list(tmp_path.glob(".*.lock"))
    assert not list(tmp_path.glob(".*.tmp"))


@pytest.mark.parametrize("fail_at", [2, 3])
def test_analyze_finalize_failure_restores_all_overwrite_originals(monkeypatch, tmp_path, fail_at):
    from competitor_offer_decoder import cli

    names = ("report.json", "offers.md", "offers.csv")
    originals = {}
    for name in names:
        path = tmp_path / name
        path.write_text(f"original:{name}", encoding="utf-8")
        originals[name] = path.read_bytes()
    original_finalize = cli._finalize_reserved
    calls = 0

    def fail_during_finalize(reservation):
        nonlocal calls
        calls += 1
        original_finalize(reservation)
        if calls == fail_at:
            raise OSError("injected finalize failure")

    monkeypatch.setattr(cli, "_finalize_reserved", fail_during_finalize)
    args = argparse.Namespace(input=DEMO, out_dir=tmp_path, sources=None, dry_run=False, overwrite=True)
    with pytest.raises(OSError):
        cli._analyze_command(args)
    assert {name: (tmp_path / name).read_bytes() for name in names} == originals
    assert not list(tmp_path.glob(".*.lock"))
    assert not list(tmp_path.glob(".*.tmp"))


def test_analysis_backup_cleanup_failure_restores_every_original(monkeypatch, tmp_path):
    from pathlib import Path
    from competitor_offer_decoder import cli

    names = ("report.json", "offers.md", "offers.csv")
    originals = {}
    for name in names:
        path = tmp_path / name
        path.write_text(f"original:{name}", encoding="utf-8")
        originals[name] = path.read_bytes()
    original_unlink = Path.unlink
    injected = False

    def fail_second_backup(path, *args, **kwargs):
        nonlocal injected
        if not injected and path.parent == tmp_path and path.name.startswith(".offers.md.") and path.name.endswith(".tmp"):
            injected = True
            raise OSError("injected backup cleanup failure")
        return original_unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", fail_second_backup)
    args = argparse.Namespace(input=DEMO, out_dir=tmp_path, sources=None, dry_run=False, overwrite=True)
    with pytest.raises(OSError):
        cli._analyze_command(args)
    assert injected
    assert {name: (tmp_path / name).read_bytes() for name in names} == originals
    assert not list(tmp_path.glob(".*.lock"))
    assert not list(tmp_path.glob(".*.tmp"))
    assert not list(tmp_path.glob(".*.bak"))


def test_recovery_copy_preparation_failure_restores_all_overwrite_originals(monkeypatch, tmp_path):
    from competitor_offer_decoder import cli

    names = ("report.json", "offers.md", "offers.csv")
    originals = {}
    for name in names:
        path = tmp_path / name
        path.write_text(f"original:{name}", encoding="utf-8")
        originals[name] = path.read_bytes()
    original_prepare = cli._prepare_recovery_copy
    calls = 0

    def fail_second_copy(reservation):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("injected recovery copy failure")
        return original_prepare(reservation)

    monkeypatch.setattr(cli, "_prepare_recovery_copy", fail_second_copy)
    args = argparse.Namespace(input=DEMO, out_dir=tmp_path, sources=None, dry_run=False, overwrite=True)
    with pytest.raises(OSError):
        cli._analyze_command(args)
    assert {name: (tmp_path / name).read_bytes() for name in names} == originals
    assert not list(tmp_path.glob(".*.lock"))
    assert not list(tmp_path.glob(".*.tmp"))
    assert not list(tmp_path.glob(".*.bak"))


@pytest.mark.parametrize("rollback_failure", ["exchange", "unlink", "lock_unlink"])
def test_rollback_failures_preserve_recovery_artifacts_and_continue(monkeypatch, tmp_path, capsys, rollback_failure):
    from competitor_offer_decoder import cli

    names = ("report.json", "offers.md", "offers.csv")
    originals = {}
    for name in names:
        path = tmp_path / name
        path.write_text(f"original:{name}", encoding="utf-8")
        originals[name] = path.read_bytes()

    original_finalize = cli._finalize_reserved
    finalize_calls = 0

    def fail_second_finalize(reservation):
        nonlocal finalize_calls
        finalize_calls += 1
        original_finalize(reservation)
        if finalize_calls == 2:
            raise OSError("injected finalizer failure")

    monkeypatch.setattr(cli, "_finalize_reserved", fail_second_finalize)
    if rollback_failure == "exchange":
        original_exchange = cli._exchange_paths
        exchange_calls = 0

        def fail_one_restore(source, destination):
            nonlocal exchange_calls
            exchange_calls += 1
            if exchange_calls == 5:
                raise OSError("injected restore exchange failure")
            return original_exchange(source, destination)

        monkeypatch.setattr(cli, "_exchange_paths", fail_one_restore)
    elif rollback_failure == "unlink":
        original_unlink = Path.unlink

        def fail_recovery_unlink(path, *args, **kwargs):
            if path.parent == tmp_path and path.name.startswith(".offers.md.") and path.name.endswith(".tmp"):
                raise OSError("injected displaced-output unlink failure")
            return original_unlink(path, *args, **kwargs)

        monkeypatch.setattr(Path, "unlink", fail_recovery_unlink)
    else:
        original_unlink = Path.unlink

        def fail_lock_unlink(path, *args, **kwargs):
            if path.parent == tmp_path and path.name == ".offers.csv.lock":
                raise OSError("injected reservation lock cleanup failure")
            return original_unlink(path, *args, **kwargs)

        monkeypatch.setattr(Path, "unlink", fail_lock_unlink)

    result = cli.main([
        "analyze", str(DEMO), "--out-dir", str(tmp_path), "--overwrite",
    ])
    assert result == 2
    error = json.loads(capsys.readouterr().err)
    assert error["code"] == "recovery_required"
    assert error["recovery_uncertain"] is True
    artifacts = [Path(path) for path in error["recovery_artifacts"]]
    assert artifacts
    for name, original_bytes in originals.items():
        output = tmp_path / name
        if output.read_bytes() != original_bytes:
            assert any(path.exists() and path.read_bytes() == original_bytes for path in artifacts)
    remaining_locks = set(tmp_path.glob(".*.lock"))
    if rollback_failure == "lock_unlink":
        assert remaining_locks == {tmp_path / ".offers.csv.lock"}
        assert tmp_path / ".offers.csv.lock" in artifacts
    else:
        assert not remaining_locks
    leftover_recovery = set(tmp_path.glob(".*.tmp")) | set(tmp_path.glob(".*.bak"))
    assert leftover_recovery <= set(artifacts)
    assert all(path.exists() for path in artifacts)


def test_unexpected_rollback_exception_does_not_stop_remaining_outputs(monkeypatch, tmp_path, capsys):
    from competitor_offer_decoder import cli

    names = ("report.json", "offers.md", "offers.csv")
    originals = {}
    for name in names:
        path = tmp_path / name
        path.write_text(f"original:{name}", encoding="utf-8")
        originals[name] = path.read_bytes()
    original_finalize = cli._finalize_reserved
    finalizes = 0

    def fail_finalize_second(reservation):
        nonlocal finalizes
        finalizes += 1
        original_finalize(reservation)
        if finalizes == 2:
            raise OSError("trigger rollback")

    original_rollback = cli._rollback_reserved
    rollback_paths = []

    def fail_one_rollback(reservation, path):
        rollback_paths.append(path.name)
        if path.name == "offers.md":
            raise OSError("injected unexpected rollback exception")
        return original_rollback(reservation, path)

    monkeypatch.setattr(cli, "_finalize_reserved", fail_finalize_second)
    monkeypatch.setattr(cli, "_rollback_reserved", fail_one_rollback)
    result = cli.main(["analyze", str(DEMO), "--out-dir", str(tmp_path), "--overwrite"])
    assert result == 2
    error = json.loads(capsys.readouterr().err)
    assert error["code"] == "recovery_required"
    artifacts = [Path(path) for path in error["recovery_artifacts"]]
    assert {"report.json", "offers.md", "offers.csv"} <= set(rollback_paths)
    assert any(path.read_bytes() == originals["offers.md"] for path in artifacts if path.exists())
    assert (tmp_path / "report.json").read_bytes() == originals["report.json"]
    assert (tmp_path / "offers.csv").read_bytes() == originals["offers.csv"]


def test_rollback_uncertainty_is_preserved_even_when_no_artifact_path_can_be_confirmed(monkeypatch, tmp_path):
    from competitor_offer_decoder import cli

    output = tmp_path / "missing.json"
    reservation = cli.OutputReservation(-1, tmp_path / ".missing.tmp", tmp_path / ".missing.lock", (1, 1), False)
    monkeypatch.setattr(cli, "_rollback_reserved", lambda *args: (_ for _ in ()).throw(OSError("rollback unknown")))
    monkeypatch.setattr(Path, "exists", lambda self: False)
    artifacts, uncertain = cli._rollback_reservations([(output, reservation)])
    assert artifacts == []
    assert uncertain is True


def test_import_reserves_destination_before_normalization(monkeypatch, tmp_path):
    from competitor_offer_decoder import cli

    source = tmp_path / "page.md"
    source.write_text("## Team", encoding="utf-8")
    output = tmp_path / "library.json"
    original = cli.brightdata.normalize_export

    def normalize(*args, **kwargs):
        assert output.exists()
        assert (tmp_path / ".library.json.lock").exists()
        return original(*args, **kwargs)

    monkeypatch.setattr(cli.brightdata, "normalize_export", normalize)
    assert cli.main([
        "import-provider", str(source), "--kind", "web_page", "--role", "offer_page",
        "--source-url", "https://example.com/page", "--observed-at", NOW, "--out", str(output),
    ]) == 0
    assert output.exists()
