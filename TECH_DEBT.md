# Technical Debt

## P0 (Next Session)

- Keep production live collection disabled until current official documentation or an independently reviewed provider response contract supplies trustworthy final-target attribution. Authorization and a spend ceiling remain separately required for any future smoke test.

## P1 (This Week)

- Validate installed wheel fixture data-file locations across Python 3.11 and 3.12 in a separate packaging check; the successful remote CI verifies editable installation and pytest, not wheel data-file placement.
- Keep the separately reviewed skills and README additions unpublished until their independent review is approved; they are not part of the core release.

## P2 (When Convenient)

- Consider a public JSON Schema only if it can exactly preserve the stricter application constraints and error behavior.
- Refresh immutable CI action pins in a separately reviewed update to remove the hosted runner's Node.js 20 deprecation warning; current Python 3.11/3.12 jobs pass under its Node.js 24 override.

## P3 (Nice To Have)

- Add a manually maintained changelog after the first reviewed release.

## Resolved Items

- 2026-10-05: Published the approved 42-file core to public `yaronbeen/competitor-offer-decoder` on `main`; unauthenticated clean clone passed 175 tests, nine offline CLI cases, and three byte-identical goldens. GitHub Actions run `37358477675` passed 175 tests each on Python 3.11 and 3.12. Pending skills and generated private evidence remain excluded.
- 2026-10-05: Core publication authorized for public `yaronbeen/competitor-offer-decoder` after final QA SHIP, security SHIP, unchanged prior brand SHIP, and independent corrected-source/exact-wheel execution PASS (175 tests each plus the two targeted regressions each). No live provider compatibility claim or request is authorized by these results.
- 2026-10-05: Independently reproduced post-exchange original loss fixed by recording exchange state before metadata inspection, retaining possibly-original temporaries on verification/reverse failure, and entering identity-checked rollback before commit verification completes. Tests and goldens unchanged.
- 2026-10-05: URL validator rejects empty userinfo delimiters; rollback cleanup is best-effort per reservation with retained artifacts and a structured recovery-required error.

- 2026-10-05: Implemented deterministic offer parsing, Decimal arithmetic, citations, exports, CLI safety, and bounded page-only retrieval.
- 2026-10-05: Added invented fixture replay, expected artifacts, packaging, CI configuration, and repository operations documentation.
- 2026-10-05: Added redirect/timeout/query/retention security regressions, fail-closed production collection, bounded file reads, immutable CI action pins, and a direct development dependency lock.
- 2026-10-05: Resolved independent code/QA P0/P1 findings for receipt reservation, selected-source uncertainty, status/unit semantics, candidate citations, partial receipts, company limits, response DTOs, parsed timestamps, safe CLI exits, and explicit unknown rendering.
- 2026-10-05: Resolved brand P1/P2 findings: official product naming, neutral distribution identity, current docs, explicit synthetic provider fixture, dry-run request details, exact approved URL sets, configurable 180-second timeout, retry-boundary wording, and provenance clarification.
- 2026-10-05: Resolved brand re-review blockers by deriving provenance from the production-vs-injected transport boundary, expanding plans with endpoint/method and explicit credential omissions, and synchronizing AGENT links with README.
- 2026-10-05: Resolved follow-up security blockers with centralized query-free URL persistence, identity-checked output reservations for every CLI writer, deterministic swap tests, and clean generated-metadata inventory checks.
- 2026-10-05: Resolved code re-review blockers by separating report readiness from scenario decisions, capping manifests at four unique companies, and making argparse/input/filesystem/provider errors fixed structured JSON with pre-access type guards.
- 2026-10-05: Analysis artifact sets now stage together and roll back on commit failure, preserving prior overwrite contents; verified with deterministic failure injection.
- 2026-10-05: Rejected percent-encoded authority syntax centrally across direct analysis, appended libraries, offline import, and live manifest validation with persistence/rendering regression coverage.
- 2026-10-05: Scoped `bright_data_transport` to the in-memory production invocation; all exported/imported provider origin is downgraded to `operator_claimed_bright_data`, since receipts are caller-editable and cannot authenticate origin.
- 2026-10-05: Analysis finalization separates lock release from backup deletion, prepares recovery copies, rolls back on finalizer/backup-removal errors, and emits a cleanup warning if only recovery-copy pruning fails.
