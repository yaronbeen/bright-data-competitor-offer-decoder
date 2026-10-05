# Competitor Offer Decoder

Public repository: [yaronbeen/bright-data-competitor-offer-decoder](https://github.com/yaronbeen/bright-data-competitor-offer-decoder). Package and CLI name remain `competitor-offer-decoder`. This is an independent project, not an official Bright Data repository. No trademark permission or affiliation is implied.

**The cheapest headline price may not buy the thing you need.**

Competitor Offer Decoder turns selected pricing-page statements into a cited scenario worksheet. For the invented five-user fixture, North's annual base is `USD 600.00` and explicitly includes CSV export. West's lower `USD 480.00` base explicitly excludes it. Harbor's `USD 720.00` base does not state whether export is included, so the overall report is `needs_review` and proposes the editorial check: `State whether CSV export is included.` It does not name a winner.

```text
North / Team
  monthly equivalent: 50.00 (comparison only)
  annual base due:     600.00
  CSV export:          explicitly included
  declared checks:     meets

West / Team
  annual base due:     480.00
  CSV export:          explicitly excluded
  declared checks:     fails
```

The useful artifact is a deterministic JSON report plus readable Markdown and fixed-column CSV. Every extracted price, minimum, and inclusion statement points to an exact source block. Unknowns remain unknown.

## Offline Quickstart

Requires Python 3.11 or newer on Linux. Identity-preserving output commits use Linux `renameat2(RENAME_EXCHANGE)` and fail closed when atomic exchange is unavailable. The fixture is invented, uses `example.com`, needs no key, and makes no network request.

```bash
python3 -m competitor_offer_decoder --version
python3 -m competitor_offer_decoder analyze fixtures/demo.json --out-dir /tmp/competitor-offer-decoder-demo
```

Installed CLI:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/competitor-offer-decoder analyze fixtures/demo.json --out-dir /tmp/competitor-offer-decoder-installed
```

Outputs are `report.json`, `offers.md`, and `offers.csv`. Existing files are not overwritten unless `--overwrite` is supplied. A validation-only run writes nothing:

```bash
python3 -m competitor_offer_decoder analyze fixtures/demo.json --out-dir /tmp/no-output --dry-run
```

The checked-in outputs under `fixtures/expected/` are deterministic snapshots of the synthetic fixture.

## Decision Boundary

The operator selects one to four companies, one to three named plans per company, exact source pages, and an optional exact Markdown heading for each plan. The scenario supplies a quantity, singular unit, monthly/annual/either preference, and one required inclusion.

Supported price sentences are deliberately narrow:

```text
USD 10 per user/month, billed monthly.
USD 10 per user/month, billed annually.
USD 120 per user/year, billed annually.
$10 per user/month, billed annually.  # requires currency_hint
```

An otherwise matching rate without `billed ...` is retained as an observed rate, but the due amount remains unknown. Supported minimums use `Minimum 10 user.` Supported inclusion statements use one exact form such as `Includes CSV export.` or `CSV export not included.`

The parser intentionally does not interpret `from`, `starting at`, ranges, tiers, bundles, plural/different units, included-seat assumptions, taxes, fees, discounts, exchange rates, or unit conversions. Unsupported price-like text is retained as an exact cited candidate while all scenario amounts remain null. An explicitly incompatible unit fails the declared scenario checks; ambiguity without an explicit contradiction remains unknown. Multiple unequal prices, duplicate plan headings, currency conflicts, and opposing inclusion statements remain ambiguous or conflicting. Monthly equivalent is arithmetic for comparison, never a claim that monthly payment is offered.

## Input And Output

`fixtures/demo.json` shows the complete versioned input envelope. Sources carry explicit status, observation date, URL, provenance, and record-ID origin. A heading scopes one exact Markdown section through the next heading of equal or higher rank. A null heading is accepted only for an unheaded page.

The report includes:

- `scope`: the exact scenario, source IDs, and `as_of` date.
- `offers`: one row per selected plan, in input order.
- `evidence`: exact block citations for price, minimum, and inclusion fields.
- `source_index`: URL, dates, hash, record identity, and provenance, without full source text.
- `own_clarity_notes`: factual editorial checks for unresolved fields in the operator's own offer.
- `warnings`: for example, snapshots over 30 days old relative to explicit `as_of`.
- `readiness_issues`: unresolved `price`, `billing`, `inclusion`, `scope`, or selected-source evidence, evaluated independently from pass/fail.
- `provenance_notice`: repeated in JSON, Markdown, and CSV: `A self-asserted receipt does not authenticate provider origin.`

Only offer/terms sources referenced by selected plans drive `as_of`, analyzed counts, and report status. Other supplied sources remain indexed but are classified with an `unreferenced_source` warning and excluded from analysis counts. Report readiness is independent from scenario pass/fail: a plan can definitively fail one declared check and still make the report `needs_review` because price, billing, inclusion, scope, or selected-source evidence remains unresolved. A collected statement from another selected page cannot turn that uncertainty into a positive qualification.

A negative example such as `From USD 10 per user/month, billed annually.` produces `unsupported_or_ambiguous_price`, null scenario amounts, an explicit `Observed rate: unknown`, and an exact cited unsupported candidate. It is not silently converted to `10.00`.

## Offline Provider Import

An already authorized **Bright Data Web Unlocker API** Markdown export can be normalized without HTTP:

```bash
python3 -m competitor_offer_decoder import-provider fixtures/provider-page.md \
  --kind web_page \
  --role offer_page \
  --source-url https://pricing.vendor.com/team \
  --observed-at 2026-10-04T10:00:00Z \
  --out /tmp/vendor.library.json
```

The resulting source is labeled `operator_supplied`; the command does not certify where the file came from. Add it explicitly with `analyze ... --sources /tmp/vendor.library.json`. Duplicate source IDs are rejected.

## Optional Bright Data Retrieval

Manifest planning and the Web Unlocker API adapter are included, but **production live collection is disabled in version 0.1.0**. Current official documentation does not provide a verified request option to disable target-site redirects or a response field/header that identifies the final target URL. Accepting returned content would therefore risk attributing redirected content to the operator-approved URL. The production transport fails closed before dispatch. Offline import and injected local transports remain usable.

Prerequisites:

- Existing Bright Data API access and an existing Web Unlocker zone.
- `BRIGHT_DATA_API_KEY` and `BRIGHT_DATA_WEB_UNLOCKER_ZONE` in the process environment.
- A manifest listing exact approved page URLs. It permits at most four unique `company_id` values, four offer pages, and four terms pages, with one page of each role per company. If omitted for compatibility, `company_id` deterministically defaults to `source_id` and still counts toward the four-company cap.
- A separate approval JSON matching the manifest SHA-256, expiry, the exact set of planned URLs with no extras, request allowance, retention allowance, and three operator attestations.
- Explicit target permission and account-budget review by the operator.

Plan first, with no credential read and no request:

```bash
python3 -m competitor_offer_decoder collect fixtures/manifest.synthetic.json --out /tmp/library.json --dry-run
```

That manifest is invented and exists only to show a zero-request plan. The plan includes the non-secret `POST` method, pinned API endpoint, `country`, `format`, `data_format`, and timeout; it explicitly states that the API key and zone are omitted.

The following live command is intentionally rejected before HTTP in version 0.1.0, even with valid credentials and approval:

```bash
python3 -m competitor_offer_decoder collect manifest.json \
  --out /tmp/library.json \
  --live --accept-charges --approval approval.json
```

Do not remove that fail-closed gate until current official documentation or an independently reviewed response contract provides trustworthy final-target attribution. Analyze, import, and collection outputs use exclusive destination claims, sidecar locks, and inode verification before and after commit; a swapped destination is rejected. Multi-artifact analysis retains displaced originals through two-phase finalization and prepares recovery copies before deleting staged backups. Rollback continues across outputs; if a restore fails, the CLI preserves the last recovery artifact and reports it with `recovery_required`, including an uncertainty flag even when no path can be confirmed. Failure pruning recovery copies after successful output commit is surfaced as `recovery_cleanup_warning`. One centralized URL validator handles direct analysis sources, appended libraries, offline imports, and live manifests. It rejects every query string before persistence, so query values cannot reach report JSON, Markdown, CSV, plans, libraries, or receipts. Injected-transport collection enforces the retained-record allowance before each request and while retaining. A successful job followed by a provider failure produces a truthful partial receipt. The application performs **zero API retries**: one planned job produces at most one application request. Bright Data may internally retry work while servicing that single request; those provider internals are not additional client requests and are not controlled or counted by this application. The manifest `timeout_seconds` is configurable from `180` to `300`, defaults to `180`, and a post-dispatch timeout remains `completion_unknown`; do not immediately retrigger it. The local call cap is not a provider spending cap. Response-size checks cannot undo provider work. This page-only project does not support SERP, dataset jobs, or snapshot resume.

Documentation reviewed on 2026-10-05: the current [REST unlock-website reference](https://docs.brightdata.com/api-reference/rest-api/unlocker/unlock-website.md), [features guide](https://docs.brightdata.com/products/web-unlocker/features.md), and [introduction](https://docs.brightdata.com/products/web-unlocker/introduction.md). Their documented request properties do not include a target-redirect control, and their documented response does not establish a final target URL. No option was invented.

## Privacy And Safety

Analysis and generated files stay local. Provider normalizers retain only the allowlisted source fields and do not save raw provider response metadata. Injected and fixture transports always produce `synthetic_fixture` provenance. Only the current in-memory production transport invocation can produce `bright_data_transport`; raw analysis input cannot assert it. Before writing a collection library, the CLI downgrades that invocation-local marker to `operator_claimed_bright_data`. Imported legacy `bright_data` fields are downgraded the same way. A matching receipt does not authenticate provider origin: local receipts can be edited, so even a matching job is only a self-asserted retrieval claim. Production collection is currently fail-closed before dispatch. `operator_claimed_bright_data` does not establish that Bright Data retrieved the source, nor authorship, truth, verification, endorsement, completeness, or ownership of target content. This is metadata minimization, not anonymization: page text can still contain names, contact details, or sensitive information. Inspect excerpts before sharing and remove private reports when no longer needed.

Central URL validation rejects any raw `@` in the URL authority (including empty userinfo), percent-encoded authority components, credentials, fragments, IP literals, local/reserved names, non-443 ports, and every query string for analysis sources, imported sources, and live targets. These syntax checks do not prove public DNS resolution, defeat rebinding, establish legal permission, or guarantee target safety. Operators remain responsible for source rights, target terms, retention, account charges, and publication decisions. No telemetry is included.

## Differentiation And Limits

The nearest common alternative is a pricing-page tracker that records changing numbers or exports AI-extracted fields to a spreadsheet. This project instead answers a narrower question: for one declared quantity, billing preference, unit, and required feature, what can the selected text support? Its heading-scoped joins, Decimal arithmetic, commitment distinction, and exact citations are local deterministic logic. This comparison describes scope, not universal novelty or superiority.

The output is not exhaustive market research, a checkout quote, tax advice, purchase eligibility, a price guarantee, or a completeness claim. Literal grammar can miss semantically equivalent wording. Selected pages may be stale, partial, personalized, or unavailable. There is no LLM, fuzzy matching, hidden API, auto-discovery, ranking, or universal cheapest-vendor conclusion.

## Testing And Status

```bash
python3 -m pip install setuptools==81.0.0 -r requirements-dev.lock
python3 -m pip install --no-deps -e .
python3 -m pytest -q
```

- Offline, security, QA, and brand contracts: verified locally on 2026-10-05 with 175 passing tests, including failures immediately after a successful path exchange, empty-userinfo rejection, recovery failures, and provenance disclosure regressions.
- Fixture CLI and deterministic artifacts: verified locally.
- Real urllib redirect/timeout behavior: verified against local loopback HTTP servers; no external request was made.
- Live Bright Data retrieval: deliberately disabled pending trustworthy final-target attribution.
- Core release gates: QA SHIP, security SHIP, and unchanged prior brand SHIP, with independent corrected-source and exact-wheel execution PASS (175 tests each). Core publication is authorized; this does not verify live provider compatibility.

Exit code `0` means valid output or plan, including honest business unknowns. `2` means invalid input, flags, or filesystem configuration. `3` means provider/transport failure or completion unknown. `4` means a saved collection receipt is partial or pending. Argparse, missing-file, malformed JSON/object, invalid UTF-8, filesystem, and provider errors use fixed structured JSON messages that do not echo arguments, paths, source values, provider bodies, exception details, or credentials.

Troubleshooting:

- `unsupported_or_ambiguous_price`: rewrite nothing; confirm that the selected page actually uses a supported exact sentence or preserve the unknown.
- `output exists`: choose a new directory or intentionally add `--overwrite`.
- approval failure: regenerate the manifest hash and confirm expiry, exact URLs, allowances, attestations, key, and zone before any live attempt.
- `response_contract_mismatch`: retain the receipt and review the current provider response documentation; do not add an unreviewed fallback parser.

Uses Bright Data for optional public-data retrieval. Analysis and decisions are local application logic. Not affiliated with or endorsed by Bright Data.
