"""Independent regressions for failures after a successful atomic exchange."""

import json
from pathlib import Path

import pytest

from competitor_offer_decoder import cli


DEMO = Path(__file__).resolve().parents[1] / "fixtures" / "demo.json"


@pytest.mark.parametrize("fault", ["post_exchange_lstat", "reverse_exchange"])
def test_exchange_failure_preserves_originals_and_reports_uncertainty(monkeypatch, tmp_path, capsys, fault):
    names = ("report.json", "offers.md", "offers.csv")
    originals = {name: f"original:{name}".encode() for name in names}
    for name, content in originals.items():
        (tmp_path / name).write_bytes(content)
    target = tmp_path / "offers.md"
    racer = tmp_path / "racer.md"
    racer.write_bytes(b"unrelated-racer-content")

    real_exchange = cli._exchange_paths
    real_lstat = Path.lstat
    real_unlink = Path.unlink
    real_rollback = cli._rollback_reserved
    state = {"forward_exchanges": 0, "lstat_failures": 0, "reverse_failures": 0, "deleted_original": False}
    displaced_path = None
    rollback_paths = []

    def exchange(source, destination):
        nonlocal displaced_path
        if destination == target and state["forward_exchanges"] and fault == "reverse_exchange" and not state["reverse_failures"]:
            state["reverse_failures"] += 1
            raise OSError("injected one-shot reverse exchange failure")
        real_exchange(source, destination)
        if destination == target and not state["forward_exchanges"]:
            displaced_path = source
            state["forward_exchanges"] += 1
            if fault == "reverse_exchange":
                # Trigger a real destination-inode mismatch, leaving the original in the temporary.
                racer.replace(target)

    def lstat(path, *args, **kwargs):
        if path == displaced_path and state["forward_exchanges"] and fault == "post_exchange_lstat" and not state["lstat_failures"]:
            state["lstat_failures"] += 1
            raise OSError("injected one-shot post-exchange lstat failure")
        return real_lstat(path, *args, **kwargs)

    def unlink(path, *args, **kwargs):
        contains_original = path == displaced_path and path.exists() and path.read_bytes() == originals["offers.md"]
        result = real_unlink(path, *args, **kwargs)
        if contains_original:
            state["deleted_original"] = True
        return result

    def rollback(reservation, path):
        rollback_paths.append(path.name)
        return real_rollback(reservation, path)

    monkeypatch.setattr(cli, "_exchange_paths", exchange)
    monkeypatch.setattr(Path, "lstat", lstat)
    monkeypatch.setattr(Path, "unlink", unlink)
    monkeypatch.setattr(cli, "_rollback_reserved", rollback)

    result = cli.main(["analyze", str(DEMO), "--out-dir", str(tmp_path), "--overwrite"])
    captured = capsys.readouterr()
    error = json.loads(captured.err)
    assert result == 2 and captured.out == ""
    assert state["forward_exchanges"] == 1
    assert state["lstat_failures"] == int(fault == "post_exchange_lstat")
    assert state["reverse_failures"] == int(fault == "reverse_exchange")
    assert set(rollback_paths) == set(names)
    for name in ("report.json", "offers.csv"):
        assert (tmp_path / name).read_bytes() == originals[name]
        assert not (tmp_path / f".{name}.lock").exists()

    recovery_paths = [Path(path) for path in error.get("recovery_artifacts", [])]
    available = {}
    for name, original in originals.items():
        available[name] = False
        for candidate in [tmp_path / name, *recovery_paths]:
            try:
                available[name] |= candidate.is_file() and candidate.read_bytes() == original
            except OSError:
                pass
    issues = [f"{name}: original bytes absent from destination and reported recovery paths" for name in names if not available[name]]
    if target.read_bytes() != originals["offers.md"]:
        if error.get("code") != "recovery_required" or error.get("recovery_uncertain") is not True:
            issues.append("unresolved restoration must emit recovery_required with recovery_uncertain=true")
    observation = {
        "fault": fault, "exit": result, "error": error, "injection": state,
        "original_available": available, "rollback_paths": rollback_paths, "issues": issues,
    }
    print(json.dumps(observation, sort_keys=True))
    assert not issues, json.dumps(observation, sort_keys=True)
