# Agent Guide

## Start Here

Read the latest file in `/home/yaron/projects/bright-data-competitor-offer-decoder/handover/`, review P0 items in `/home/yaron/projects/bright-data-competitor-offer-decoder/TECH_DEBT.md`, and skim `/home/yaron/projects/bright-data-competitor-offer-decoder/LEARNINGS.md`. Do not make a real Bright Data Web Unlocker API request without new explicit URL, account, and budget authorization.

## Purpose & Context

This Python 3.11+ CLI creates deterministic, cited offer worksheets for one operator-declared scenario. Offline analysis is the product; Web Unlocker API manifests and offline imports are optional ingestion helpers. Version 0.1.0 disables production live collection because final target attribution after provider-side redirects is unverified. Core publication is authorized after QA SHIP, security SHIP, unchanged prior brand SHIP, and independent source/exact-wheel execution PASS; see `/home/yaron/projects/bright-data-competitor-offer-decoder/VERIFICATION.md`. The public repository is `yaronbeen/bright-data-competitor-offer-decoder` per the explicit user naming requirement; package and CLI identity remain `competitor-offer-decoder`. The repository is independent, not officially owned or endorsed by Bright Data. The local path remains unchanged. The bundled `offer-clarity-wedge` Markdown skill and exact README section are separately approved after skeptic, automation, and brand SHIP results supplied by the user; the skill is not a new CLI command or automatically registered plugin.

## Architecture / Design

```text
versioned JSON + optional explicit library
                 |
                 v
             core.py ----> deterministic report dict
                              |              |
                              v              v
                         offers.md       offers.csv

manifest -> approval gates -> brightdata.py -> normalized source library
```

`core.py` owns validation, block normalization, scoped extraction, citations, and Decimal calculations. `export.py` renders stable escaped artifacts. `brightdata.py` owns page-only planning, approvals, transport DTOs, normalization, and safe receipts. `cli.py` owns flags, local files, environment reads for explicit live mode, and atomic writes.

Only plan-referenced offer/terms sources influence analysis status and counts. The collection CLI must hold an exact destination claim and lock before crossing any transport boundary. Partial/pending receipts exit 4; provider/transport failure exits 3.
Injected transports are always synthetic and must emit `synthetic_fixture` provenance. Only the current in-memory `urllib_transport` invocation may emit `bright_data_transport`, and that production path remains disabled before dispatch pending redirect-attribution review. Persisted libraries must downgrade it to `operator_claimed_bright_data`. Never treat receipt-backed origin as authenticated; receipts are caller-editable local data.
`url_safety.py` is the single URL policy for analysis, libraries, imports, and live manifests; query strings are never persisted. Analyze, import, and collection must all use `OutputReservation` and verify destination inode identity through commit.
Atomic commits require Linux `renameat2(RENAME_EXCHANGE)`. If unavailable, output fails closed rather than falling back to a TOCTOU-prone replacement.
URL authority validation rejects a raw `@` even when parsed username/password are empty. Rollback catches exchange/restore/unlink/lock failures per reservation, continues the remaining outputs, preserves recovery files, and emits `recovery_required` with retained paths plus an uncertainty flag even when no path can be confirmed.
Row scenario pass/fail and report readiness are separate: any unresolved price, billing, inclusion, scope, or selected source keeps the report `needs_review`, even when another check definitively fails. Manifests allow at most four unique company identities.
CLI failures must remain fixed structured JSON; validate object/list/member types before `.get` and never echo argparse values, paths, bytes, provider text, or exception strings.

## Decisions Log

| Date | Decision | Rationale |
| --- | --- | --- |
| 2026-10-05 | Keep analysis deterministic and stdlib-only | Reproducible arithmetic and exact citation behavior are the product contract. |
| 2026-10-05 | Support only Web Unlocker page collection | Competitor offer scope excludes SERP and dataset collectors. |
| 2026-10-05 | Preserve ambiguity rather than broaden grammar | Avoid unsupported billing, bundle, feature, and currency inferences. |
| 2026-10-05 | Do not publish before independent artifact review | Publication is explicitly gated by the build request. |
| 2026-10-05 | Fail closed for production Web Unlocker collection | Current official docs provide neither a target-redirect disable option nor trustworthy final-target attribution. |
| 2026-10-05 | Correct fixture status and incompatible-unit oracle | Governing contract makes unresolved required decisions needs-review and explicit unit conflicts declared-check failures. |
| 2026-10-05 | Use brand-neutral public identity | No trademark permission exists for a branded repository/distribution name; local path remains unchanged to avoid disruption. |
| 2026-10-05 | Default provider timeout to 180 seconds | Long provider processing remains bounded and post-dispatch timeout remains completion-unknown. |
| 2026-10-05 | Publish only the approved core to yaronbeen/competitor-offer-decoder | All core gates are clear; separately reviewed skills stay out, and live collection stays disabled. |
| 2026-10-05 | Rename the owned repository to yaronbeen/bright-data-competitor-offer-decoder | Explicit user requirement to mention Bright Data in repository names supersedes the repository portion of the earlier neutral-name proposal. Package/CLI names and independent non-affiliation wording remain unchanged. |
| 2026-10-05 | Publish the separately approved offer-clarity-wedge bundle and exact README snippet | Skeptic, automation, and brand reviewers all SHIP, including prefixed repository naming. Add portable Markdown only through a normal new commit; keep runtime, package/CLI, provider gates, and private artifacts unchanged. |

## Runbook / Operations

Use `python3 -m pytest -q` for the full suite. Use `python3 -m competitor_offer_decoder analyze fixtures/demo.json --out-dir /tmp/competitor-offer-decoder-demo` for offline replay. Use `--dry-run` before collection. Keep real approvals, libraries, receipts, and reports in ignored paths. Never commit provider keys or real private source content.

## API References

- https://docs.brightdata.com/api-reference/rest-api/unlocker/unlock-website.md
- https://docs.brightdata.com/products/web-unlocker/features.md
- https://docs.brightdata.com/products/web-unlocker/introduction.md
- Build contract: `/home/yaron/.claude/data/brightdata-drafts/2026-10-04-five-project-build-contract.md`

## Project File Structure

- `/home/yaron/projects/bright-data-competitor-offer-decoder/competitor_offer_decoder/`: runtime package.
- `/home/yaron/projects/bright-data-competitor-offer-decoder/tests/`: independent contract tests; do not weaken them.
- `/home/yaron/projects/bright-data-competitor-offer-decoder/fixtures/`: invented demo and expected outputs.
- `/home/yaron/projects/bright-data-competitor-offer-decoder/handover/`: session state.
- `/home/yaron/projects/bright-data-competitor-offer-decoder/.github/workflows/test.yml`: Python 3.11/3.12 CI.

## References

See `/home/yaron/projects/bright-data-competitor-offer-decoder/LEARNINGS.md`, `/home/yaron/projects/bright-data-competitor-offer-decoder/TECH_DEBT.md`, and the latest numbered handover.
