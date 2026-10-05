# Handover 003: Post-Exchange Bug Fix

Date: 2026-10-05.

## Scope

The preceding frozen candidate is superseded by an independently reproduced safety defect. This pass fixes only the exchange-state window; no tests, fixtures, provider behavior, or provenance framework were changed.

## Fix And Evidence

- Runtime change limited to `/home/yaron/projects/bright-data-competitor-offer-decoder/competitor_offer_decoder/cli.py`.
- Successful forward exchange is recorded before metadata I/O; verification/reverse failure cannot delete a possibly-original temporary.
- Existing identity-checked rollback runs even when commit verification did not complete. A raced destination leaves the original at a reported recovery path, with uncertainty, while other reservations continue.
- Independent tests unchanged, SHA-256 `bc6d41d7cd704d34a577bab3c2c692b891035bc3536a51e462f70d0b9cb6cf35`.
- RED: 2 failed; source GREEN: 2 passed; full source suite: 175 passed. All seven test files and three goldens match their pre-fix hashes.
- New release directory: `/home/yaron/projects/bright-data-competitor-offer-decoder/.venv/exchange-state-rc/`.
- Exact new wheel, source archive, regression XML/logs, CLI/golden/secret results, and frozen report hashes: `/home/yaron/projects/bright-data-competitor-offer-decoder/.venv/exchange-state-rc/verification.json` and `/home/yaron/projects/bright-data-competitor-offer-decoder/.venv/exchange-state-rc/checksums.json`.

## Gate

The top-level orchestrator owns independent final review. Do not publish the old or new candidate before approval. No nested reviewer, live/paid request, remote operation, commit, or publication was performed. Production collection remains fail-closed.
