"""Command-line interface."""

from __future__ import annotations

import argparse
import ctypes
import errno
import json
import os
import stat
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from . import __version__, brightdata
from .core import PROJECT, analyze, analyze_with_library
from .export import render_csv, render_markdown


MAX_FILE = 2 * 1024 * 1024


@dataclass
class OutputReservation:
    descriptor: int
    temporary: Path
    lock: Path
    destination_identity: tuple[int, int]
    created_destination: bool
    committed_identity: tuple[int, int] | None = None
    committed: bool = False
    recovery_path: Path | None = None
    recovery_identity: tuple[int, int] | None = None
    recovery_ready: bool = False
    exchange_performed: bool = False


class SafeArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        _error("invalid_arguments", "Invalid command-line arguments.")
        raise SystemExit(2)


class OutputRecoveryRequired(OSError):
    def __init__(self, artifacts: list[Path], *, uncertain: bool = False):
        self.artifacts = [str(path) for path in artifacts]
        self.uncertain = uncertain
        super().__init__("output rollback requires recovery")


def _read_bytes(path: Path) -> bytes:
    flags = os.O_RDONLY | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise ValueError("input must be a regular file")
        if metadata.st_size > MAX_FILE:
            raise ValueError("input file exceeds 2 MiB")
        with os.fdopen(descriptor, "rb", closefd=False) as stream:
            data = stream.read(MAX_FILE + 1)
        if len(data) > MAX_FILE:
            raise ValueError("input file exceeds 2 MiB")
        return data
    finally:
        os.close(descriptor)


def _read_text(path: Path) -> str:
    return _read_bytes(path).decode("utf-8")


def _read_json(path: Path):
    return json.loads(_read_text(path))


def _reserve_output(path: Path, overwrite: bool) -> OutputReservation:
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = path.parent / f".{path.name}.lock"
    lock_flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    lock_descriptor = os.open(lock, lock_flags, 0o600)
    os.close(lock_descriptor)
    destination_identity = None
    created_destination = False
    try:
        if path.exists() or path.is_symlink():
            if not overwrite:
                raise FileExistsError("output exists; use --overwrite")
            metadata = path.lstat()
            if not stat.S_ISREG(metadata.st_mode):
                raise OSError("output destination must be a regular file")
            destination_identity = (metadata.st_dev, metadata.st_ino)
        else:
            claim_flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
            claim_descriptor = os.open(path, claim_flags, 0o600)
            metadata = os.fstat(claim_descriptor)
            os.close(claim_descriptor)
            destination_identity = (metadata.st_dev, metadata.st_ino)
            created_destination = True
        descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
        return OutputReservation(descriptor, Path(temporary), lock, destination_identity, created_destination)
    except Exception:
        if created_destination and destination_identity is not None:
            _remove_destination(path, destination_identity)
        lock.unlink(missing_ok=True)
        raise


def _remove_destination(path: Path, identity: tuple[int, int]) -> None:
    try:
        metadata = path.lstat()
        if (metadata.st_dev, metadata.st_ino) == identity:
            path.unlink()
    except FileNotFoundError:
        pass


def _exchange_paths(first: Path, second: Path) -> None:
    renameat2 = getattr(ctypes.CDLL(None, use_errno=True), "renameat2", None)
    if renameat2 is None:
        raise OSError(errno.ENOTSUP, "atomic path exchange is unavailable")
    renameat2.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    renameat2.restype = ctypes.c_int
    result = renameat2(-100, os.fsencode(first), -100, os.fsencode(second), 2)
    if result != 0:
        code = ctypes.get_errno()
        raise OSError(code, os.strerror(code))


def _commit_reserved(reservation: OutputReservation, path: Path, data: str) -> None:
    try:
        with os.fdopen(reservation.descriptor, "w", encoding="utf-8", newline="") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        metadata = path.lstat()
        if (metadata.st_dev, metadata.st_ino) != reservation.destination_identity:
            raise FileExistsError("output destination changed during operation")
        temporary_identity = reservation.temporary.lstat()
        reservation.committed_identity = (temporary_identity.st_dev, temporary_identity.st_ino)
        _exchange_paths(reservation.temporary, path)
        # The temporary may now hold the original; rollback owns its cleanup.
        reservation.exchange_performed = True
        displaced = reservation.temporary.lstat()
        if (displaced.st_dev, displaced.st_ino) != reservation.destination_identity:
            _exchange_paths(reservation.temporary, path)
            reservation.exchange_performed = False
            raise FileExistsError("output destination changed during commit")
        committed = path.lstat()
        if (committed.st_dev, committed.st_ino) != (temporary_identity.st_dev, temporary_identity.st_ino):
            _exchange_paths(reservation.temporary, path)
            reservation.exchange_performed = False
            raise FileExistsError("output destination identity could not be verified")
        reservation.committed_identity = (committed.st_dev, committed.st_ino)
        reservation.committed = True
    except Exception:
        try:
            os.close(reservation.descriptor)
        except OSError:
            pass
        if not reservation.exchange_performed:
            try:
                reservation.temporary.unlink()
            except FileNotFoundError:
                pass
        raise


def _finalize_reserved(reservation: OutputReservation) -> None:
    if not reservation.committed:
        raise OSError("output was not staged")
    reservation.lock.unlink()


def _prepare_recovery_copy(reservation: OutputReservation) -> None:
    if reservation.created_destination:
        return
    descriptor, recovery_name = tempfile.mkstemp(
        prefix=f".{reservation.lock.name}.recovery.", suffix=".bak", dir=reservation.lock.parent,
    )
    recovery = Path(recovery_name)
    metadata = recovery.lstat()
    reservation.recovery_path = recovery
    reservation.recovery_identity = (metadata.st_dev, metadata.st_ino)
    try:
        with os.fdopen(descriptor, "wb") as destination, reservation.temporary.open("rb") as source:
            while chunk := source.read(64 * 1024):
                destination.write(chunk)
            destination.flush()
            os.fsync(destination.fileno())
        reservation.recovery_ready = True
    except Exception:
        try:
            os.close(descriptor)
        except OSError:
            pass
        try:
            recovery.unlink(missing_ok=True)
            reservation.recovery_path = None
            reservation.recovery_identity = None
        except OSError:
            pass
        raise


def _cleanup_finalized(reservations: list[OutputReservation]) -> bool:
    for reservation in reservations:
        _prepare_recovery_copy(reservation)
    for reservation in reservations:
        reservation.temporary.unlink()
    warning = False
    for reservation in reservations:
        if reservation.recovery_path is None:
            continue
        try:
            reservation.recovery_path.unlink()
            reservation.recovery_path = None
            reservation.recovery_identity = None
        except OSError:
            warning = True
    return warning


def _rollback_reserved(reservation: OutputReservation, path: Path) -> list[Path]:
    retained: list[Path] = []
    if reservation.committed or reservation.exchange_performed:
        recovery = reservation.recovery_path
        source = reservation.temporary
        if recovery is not None and reservation.recovery_ready:
            try:
                if recovery.exists():
                    source = recovery
            except OSError:
                retained.append(recovery)
        expected_original = reservation.recovery_identity if source == recovery else reservation.destination_identity
        try:
            destination = path.lstat()
            displaced = source.lstat()
            if (
                reservation.committed_identity == (destination.st_dev, destination.st_ino)
                and expected_original == (displaced.st_dev, displaced.st_ino)
            ):
                _exchange_paths(source, path)
                reservation.exchange_performed = False
                try:
                    source.unlink(missing_ok=True)
                except OSError:
                    retained.append(source)
            else:
                retained.append(source)
        except OSError:
            retained.append(source)
        reservation.committed = False
    if reservation.created_destination:
        for identity in (reservation.committed_identity, reservation.destination_identity):
            if identity is not None:
                try:
                    _remove_destination(path, identity)
                except OSError:
                    retained.append(path)
    for candidate in (reservation.temporary, reservation.recovery_path, reservation.lock):
        if candidate is None or candidate in retained:
            continue
        try:
            candidate.unlink(missing_ok=True)
        except OSError:
            retained.append(candidate)
    for candidate in (reservation.temporary, reservation.recovery_path, reservation.lock):
        if candidate is None or candidate in retained:
            continue
        try:
            if candidate.exists():
                retained.append(candidate)
        except OSError:
            retained.append(candidate)
    return retained


def _rollback_reservations(reservations: list[tuple[Path, OutputReservation]]) -> tuple[list[str], bool]:
    recovery_artifacts: list[str] = []
    uncertain = False
    for path, reservation in reversed(reservations):
        try:
            retained = _rollback_reserved(reservation, path)
            recovery_artifacts.extend(str(item) for item in retained)
            uncertain |= bool(retained)
        except Exception:
            uncertain = True
            # Keep processing other outputs; retain every candidate needed for manual recovery.
            for candidate in (reservation.recovery_path, reservation.temporary, path, reservation.lock):
                if candidate is None:
                    continue
                try:
                    if candidate.exists():
                        recovery_artifacts.append(str(candidate))
                except OSError:
                    recovery_artifacts.append(str(candidate))
    return recovery_artifacts, uncertain


def _raise_recovery_required(original: Exception, reservations: list[tuple[Path, OutputReservation]]) -> None:
    artifacts, uncertain = _rollback_reservations(reservations)
    if uncertain:
        raise OutputRecoveryRequired([Path(item) for item in artifacts], uncertain=True) from original


def _discard_reserved(reservation: OutputReservation, path: Path) -> None:
    try:
        os.close(reservation.descriptor)
    except OSError:
        pass
    try:
        reservation.temporary.unlink()
    except FileNotFoundError:
        pass
    if reservation.recovery_path is not None:
        reservation.recovery_path.unlink(missing_ok=True)
        reservation.recovery_path = None
    if reservation.created_destination:
        _remove_destination(path, reservation.destination_identity)
    reservation.lock.unlink(missing_ok=True)


def _error(code: str, message: str, requests: int = 0, *, exit_code: int | None = None) -> int:
    print(json.dumps({"code": code, "message": message, "requests_made": requests}, sort_keys=True), file=sys.stderr)
    if exit_code is not None:
        return exit_code
    return 2 if code in {"invalid_input", "invalid_configuration", "filesystem_error"} else 3


def parser() -> argparse.ArgumentParser:
    result = SafeArgumentParser(prog=PROJECT, description="Build a deterministic, cited competitor offer scenario worksheet.")
    result.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    commands = result.add_subparsers(dest="command", required=True, parser_class=SafeArgumentParser)
    analysis = commands.add_parser("analyze")
    analysis.add_argument("input", type=Path)
    analysis.add_argument("--out-dir", type=Path, required=True)
    analysis.add_argument("--sources", type=Path)
    analysis.add_argument("--dry-run", action="store_true")
    analysis.add_argument("--overwrite", action="store_true")
    collection = commands.add_parser("collect")
    collection.add_argument("manifest", type=Path)
    collection.add_argument("--out", type=Path, required=True)
    collection.add_argument("--live", action="store_true")
    collection.add_argument("--accept-charges", action="store_true")
    collection.add_argument("--approval", type=Path)
    collection.add_argument("--dry-run", action="store_true")
    collection.add_argument("--overwrite", action="store_true")
    imported = commands.add_parser("import-provider")
    imported.add_argument("file", type=Path)
    imported.add_argument("--kind", required=True)
    imported.add_argument("--role", required=True)
    imported.add_argument("--source-url", required=True)
    imported.add_argument("--observed-at", required=True)
    imported.add_argument("--source-prefix", default="import")
    imported.add_argument("--out", type=Path, required=True)
    imported.add_argument("--overwrite", action="store_true")
    resume = commands.add_parser("resume")
    resume.add_argument("receipt", type=Path)
    resume.add_argument("--out", type=Path, required=True)
    resume.add_argument("--live", action="store_true")
    resume.add_argument("--accept-charges", action="store_true")
    resume.add_argument("--approval", type=Path, required=True)
    return result


def _analyze_command(args) -> int:
    payload = _read_json(args.input)
    if not isinstance(payload, dict):
        raise TypeError("analysis input must be an object")
    if args.sources:
        library = _read_json(args.sources)
        report = analyze_with_library(payload, library)
        input_source_count = len(payload["sources"]) + len(library["sources"])
    else:
        report = analyze(payload)
        input_source_count = len(payload["sources"])
    if args.dry_run:
        print(json.dumps({"input_sources": input_source_count, "output_rows": len(report["offers"]), "requests_made": 0}, sort_keys=True))
        return 0
    paths = [args.out_dir / "report.json", args.out_dir / "offers.md", args.out_dir / "offers.csv"]
    rendered = [json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", render_markdown(report), render_csv(report)]
    reservations: list[tuple[Path, OutputReservation]] = []
    try:
        for path in paths:
            reservations.append((path, _reserve_output(path, args.overwrite)))
        for (path, reservation), content in zip(reservations, rendered):
            _commit_reserved(reservation, path, content)
        for _, reservation in reservations:
            _finalize_reserved(reservation)
        cleanup_warning = _cleanup_finalized([reservation for _, reservation in reservations])
    except Exception:
        import sys
        _raise_recovery_required(sys.exception(), reservations)
        raise
    result = {"status": report["status"], "output_rows": len(report["offers"]), "requests_made": 0}
    if cleanup_warning:
        result["recovery_cleanup_warning"] = True
    print(json.dumps(result, sort_keys=True))
    return 0


def _collect_command(args) -> int:
    manifest = _read_json(args.manifest)
    planned = brightdata.plan(manifest)
    if args.dry_run:
        print(json.dumps(planned, sort_keys=True))
        return 0
    if not args.live or not args.accept_charges or args.approval is None:
        raise PermissionError("collect requires --live, --accept-charges, and --approval")
    approval = _read_json(args.approval)
    reservation = _reserve_output(args.out, args.overwrite)
    try:
        library = brightdata.collect(
            manifest, approval=approval, api_key=os.environ.get("BRIGHT_DATA_API_KEY", ""),
            zones={"web_unlocker": os.environ.get("BRIGHT_DATA_WEB_UNLOCKER_ZONE", "")},
            transport=brightdata.urllib_transport, now=_now(),
        )
        receipt = library["receipt"]
        exported_library = brightdata.library_for_export(library)
        _commit_reserved(reservation, args.out, json.dumps(exported_library, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
        _finalize_reserved(reservation)
        cleanup_warning = _cleanup_finalized([reservation])
    except Exception as exc:
        try:
            artifacts = _rollback_reserved(reservation, args.out)
        except Exception:
            artifacts = [reservation.recovery_path, reservation.temporary, reservation.lock]
            artifacts = [item for item in artifacts if item is not None]
            raise OutputRecoveryRequired(artifacts, uncertain=True) from exc
        if artifacts:
            raise OutputRecoveryRequired(artifacts, uncertain=True) from exc
        raise
    status = receipt["status"]
    if status == "complete":
        result = {"status": status, "requests_made": receipt["requests_made"]}
        if cleanup_warning:
            result["recovery_cleanup_warning"] = True
        print(json.dumps(result, sort_keys=True))
        return 0
    if status in {"partial", "pending"}:
        return _error("collection_incomplete", "Collection is partial or pending; inspect the saved receipt.", receipt["requests_made"], exit_code=4)
    return _error("collection_provider_failure", "Collection did not complete; inspect the saved receipt.", receipt["requests_made"], exit_code=3)


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def main(argv=None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "analyze":
            return _analyze_command(args)
        if args.command == "collect":
            return _collect_command(args)
        if args.command == "import-provider":
            if args.kind != "web_page":
                raise ValueError("only web_page import is supported")
            source_text = _read_text(args.file)
            reservation = _reserve_output(args.out, args.overwrite)
            try:
                library = brightdata.normalize_export(
                    args.kind, source_text, role=args.role,
                    source_url=args.source_url, observed_at=args.observed_at, source_prefix=args.source_prefix,
                )
                _commit_reserved(reservation, args.out, json.dumps(library, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
                _finalize_reserved(reservation)
                cleanup_warning = _cleanup_finalized([reservation])
            except Exception as exc:
                try:
                    artifacts = _rollback_reserved(reservation, args.out)
                except Exception:
                    artifacts = [reservation.recovery_path, reservation.temporary, reservation.lock]
                    artifacts = [item for item in artifacts if item is not None]
                    raise OutputRecoveryRequired(artifacts, uncertain=True) from exc
                if artifacts:
                    raise OutputRecoveryRequired(artifacts, uncertain=True) from exc
                raise
            result = {"status": "complete", "requests_made": 0}
            if cleanup_warning:
                result["recovery_cleanup_warning"] = True
            print(json.dumps(result, sort_keys=True))
            return 0
        raise ValueError("resume is unsupported for page-only collection")
    except FileNotFoundError:
        return _error("invalid_input", "Input file was not found.")
    except OutputRecoveryRequired as exc:
        print(json.dumps({
            "code": "recovery_required", "message": "Output rollback was incomplete; recover originals from the listed artifacts.",
            "requests_made": 0, "recovery_artifacts": exc.artifacts, "recovery_uncertain": exc.uncertain,
        }, sort_keys=True), file=sys.stderr)
        return 2
    except UnicodeError:
        return _error("invalid_input", "Input file is not valid UTF-8.")
    except json.JSONDecodeError:
        return _error("invalid_input", "Input file is not valid JSON.")
    except FileExistsError:
        return _error("invalid_input", "Output already exists or changed during operation.")
    except (ValueError, TypeError, PermissionError):
        return _error("invalid_input", "Input or configuration is invalid.")
    except OSError:
        return _error("filesystem_error", "A filesystem operation failed.")


if __name__ == "__main__":
    raise SystemExit(main())
