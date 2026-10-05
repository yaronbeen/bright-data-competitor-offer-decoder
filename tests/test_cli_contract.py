"""CLI safety and filesystem acceptance tests."""

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "fixtures" / "demo.json"


def run_cli(*args, env=None):
    actual_env = dict(os.environ) if env is None else dict(env)
    actual_env["PYTHONPATH"] = str(ROOT)
    return subprocess.run([sys.executable, "-m", "competitor_offer_decoder", *map(str, args)], cwd=ROOT, env=actual_env, capture_output=True, text=True)


def write_collection_inputs(tmp_path):
    manifest = {
        "schema_version": "1.0",
        "project": "competitor-offer-decoder",
        "jobs": [{"id": "web_1", "kind": "web_page", "role": "offer_page", "source_id": "live_offer", "url": "https://pricing.vendor.com/team"}],
    }
    encoded = json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    approval = {
        "schema_version": "1.0",
        "project": "competitor-offer-decoder",
        "manifest_sha256": hashlib.sha256(encoded).hexdigest(),
        "expires_at": "2099-01-01T00:00:00Z",
        "max_requests": 1,
        "max_retained_records": 1,
        "approved_urls": ["https://pricing.vendor.com/team"],
        "account_budget_confirmed": True,
        "target_permissions_confirmed": True,
        "remote_resolution_risk_accepted": True,
    }
    manifest_path = tmp_path / "manifest.json"
    approval_path = tmp_path / "approval.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    approval_path.write_text(json.dumps(approval), encoding="utf-8")
    return manifest_path, approval_path


def test_c09_collect_without_live_or_charge_acknowledgement_exits_two_before_output(tmp_path):
    manifest_path, approval_path = write_collection_inputs(tmp_path)
    output = tmp_path / "library.json"
    result = run_cli("collect", manifest_path, "--out", output, "--approval", approval_path)
    assert result.returncode == 2
    assert not output.exists()
    error = json.loads(result.stderr)
    assert error["requests_made"] == 0


def test_c10_live_dry_run_wins_makes_zero_requests_and_no_output(tmp_path):
    manifest_path, approval_path = write_collection_inputs(tmp_path)
    output = tmp_path / "library.json"
    env = dict(os.environ, BRIGHT_DATA_API_KEY="fake", BRIGHT_DATA_WEB_UNLOCKER_ZONE="fake-zone")
    result = run_cli("collect", manifest_path, "--out", output, "--live", "--accept-charges", "--approval", approval_path, "--dry-run", env=env)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["requests_made"] == 0
    assert not output.exists()


def test_c10_dry_run_still_validates_manifest(tmp_path):
    bad_manifest = tmp_path / "manifest.json"
    bad_manifest.write_text('{"schema_version":"1.0","project":"wrong","jobs":[]}', encoding="utf-8")
    output = tmp_path / "library.json"
    result = run_cli("collect", bad_manifest, "--out", output, "--dry-run")
    assert result.returncode == 2
    assert not output.exists()
    assert json.loads(result.stderr)["requests_made"] == 0


def test_c19_collision_preserves_all_existing_artifacts(tmp_path):
    original = {}
    for name in ("report.json", "offers.md", "offers.csv"):
        path = tmp_path / name
        path.write_text(f"sentinel-{name}", encoding="utf-8")
        original[name] = path.read_bytes()
    result = run_cli("analyze", DEMO, "--out-dir", tmp_path)
    assert result.returncode == 2
    assert {name: (tmp_path / name).read_bytes() for name in original} == original
    assert not list(tmp_path.glob("*.tmp"))


def test_c19_invalid_input_writes_nothing_and_error_is_structured(tmp_path):
    invalid = tmp_path / "invalid.json"
    invalid.write_text('{"schema_version":"wrong"}', encoding="utf-8")
    output = tmp_path / "output"
    result = run_cli("analyze", invalid, "--out-dir", output)
    assert result.returncode == 2
    assert not output.exists() or list(output.iterdir()) == []
    error = json.loads(result.stderr)
    assert set(error) >= {"code", "message", "requests_made"}
    assert error["requests_made"] == 0


def test_cli_version_is_available_without_install_or_keys():
    env = {key: value for key, value in os.environ.items() if not key.startswith("BRIGHT_DATA_")}
    result = run_cli("--version", env=env)
    assert result.returncode == 0
    assert "0.1.0" in result.stdout


def test_unknown_flags_return_fixed_structured_json_without_echoing_value():
    result = run_cli("analyze", DEMO, "--out-dir", "/tmp/unused", "--secret-flag=must-not-echo")
    assert result.returncode == 2
    error = json.loads(result.stderr)
    assert error == {
        "code": "invalid_arguments", "message": "Invalid command-line arguments.", "requests_made": 0,
    }
    assert "must-not-echo" not in result.stderr


def test_missing_file_error_is_structured_and_does_not_echo_path(tmp_path):
    missing = tmp_path / "private-secret-name.json"
    result = run_cli("analyze", missing, "--out-dir", tmp_path / "out")
    assert result.returncode == 2
    error = json.loads(result.stderr)
    assert error == {"code": "invalid_input", "message": "Input file was not found.", "requests_made": 0}
    assert "private-secret-name" not in result.stderr


def test_invalid_utf8_error_is_fixed_structured_json(tmp_path):
    invalid = tmp_path / "invalid.json"
    invalid.write_bytes(b"\xff\xfe")
    result = run_cli("analyze", invalid, "--out-dir", tmp_path / "out")
    assert result.returncode == 2
    assert json.loads(result.stderr) == {
        "code": "invalid_input", "message": "Input file is not valid UTF-8.", "requests_made": 0,
    }


def test_malformed_source_library_types_are_fixed_structured_errors(tmp_path):
    library = tmp_path / "library.json"
    library.write_text(json.dumps({"project": "competitor-offer-decoder", "sources": [1]}), encoding="utf-8")
    result = run_cli("analyze", DEMO, "--sources", library, "--out-dir", tmp_path / "out")
    assert result.returncode == 2
    assert json.loads(result.stderr) == {
        "code": "invalid_input", "message": "Input or configuration is invalid.", "requests_made": 0,
    }
