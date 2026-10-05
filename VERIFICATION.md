# Verification Evidence

Date: 2026-10-05

## Scope

This evidence covers the security review, independent code/QA review, release hardening, offline analysis, CLI behavior, and isolated package installation. No external target or Bright Data API request was made.

## Test-First Evidence

After adding the redirect, query, retention, fail-closed, timeout, and Markdown regressions:

```text
python3 -m pytest -q tests/test_security_regressions.py
11 failed, 3 passed in 3.93s
```

After adding the bounded-reader regression:

```text
python3 -m pytest -q tests/test_security_regressions.py::test_json_reader_uses_bounded_file_descriptor_read_not_path_read_text
1 failed in 0.10s
```

The independent QA regression pass initially produced:

```text
python3 -m pytest -q tests/test_qa_regressions.py tests/test_acceptance.py
16 failed, 46 passed in 0.81s
```

Two existing assertions were corrected with inline rationale because they contradicted the governing contract: the fixture report is `needs_review` while Harbor's required inclusion is unresolved, and an explicit incompatible unit is `fails_declared_checks` with null arithmetic. No test was weakened to accept the old behavior.

The first QA RED run also exposed an overly broad test-edit patch that had accidentally changed the separate rate-without-billing oracle. That assertion was restored to `unknown` before implementation work continued.

The brand regression pass started RED:

```text
python3 -m pytest -q tests/test_brand_regressions.py tests/test_brightdata_contract.py
6 failed, 36 passed in 0.24s
```

Those failures covered the old distribution name and 75-second timeout, missing dry-run request fields, non-exact approval URL semantics, absent provider fixture, and outdated public documentation.

The follow-up brand re-review regressions started RED:

```text
python3 -m pytest -q tests/test_brand_regressions.py tests/test_brightdata_contract.py
4 failed, 39 passed in 0.37s
```

They proved that injected transport output was incorrectly labeled `bright_data` and that plans omitted endpoint/method/credential-omission fields.

The centralized URL and output-integrity regressions started RED:

```text
python3 -m pytest -q tests/test_security_regressions.py tests/test_qa_regressions.py
4 failed, 39 passed in 4.63s
```

They proved that direct analysis still accepted query URLs, destination swaps were overwritten, and analyze/import bypassed the shared reservation primitive. The deterministic swap test was then strengthened to use a pre-created attacker inode after the filesystem reused an inode in the first test setup.

A final syscall-boundary race test failed first because no atomic exchange primitive existed. It passed after commit switched to Linux `RENAME_EXCHANGE`, displaced-inode verification, and rollback on mismatch.

The final code re-review regressions started RED:

```text
python3 -m pytest -q tests/test_qa_regressions.py tests/test_cli_contract.py
7 failed, 32 passed in 1.55s
```

They covered readiness hidden by a definitive failure, five-company manifests, raw argparse output, leaked path/decoder details, and an uncaught malformed-library `AttributeError`. The full-suite integration run then exposed one obsolete eight-job fixture without company identities; it was corrected to model four offer/terms company pairs while preserving the eight-call assertion.

Readiness/CLI follow-up tests passed (`39 passed`). Failure injection then showed analysis could leave `report.json` behind after a later output commit failed. Staged exchange/rollback tests were added for new outputs and overwrite mode; both verify that prior outputs are removed or restored and no reservation files remain.

Finalization rollback regressions inject failure after second/third reservation finalizers and during deletion of a later staged backup after an earlier backup was removed. Rollback regressions inject restore-exchange, displaced-output unlink, lock cleanup, and unexpected per-reservation failures; they verify rollback continues for remaining destinations, original bytes remain accessible at outputs or listed recovery artifacts, unrelated locks do not leak, and the CLI emits fixed `recovery_required` diagnostics.

Latest security cases reject empty userinfo delimiters `https://@host/path` and `https://:@host/path`. Rollback regressions also inject reservation-lock unlink failure and an unexpected per-reservation rollback exception, proving later reservations are still processed and unresolved paths are included in recovery diagnostics.

## Final Green Evidence

```text
python3 -m pytest -q
175 passed in 6.98s
```

The security regressions include real loopback-server checks for 301, 302, 303, 307, 308, a post-dispatch socket timeout, all-path query rejection, percent-encoded authority/userinfo delimiter rejection across direct analysis, appended source libraries, offline import, live planning/collection, and CLI output creation. They assert unsafe URLs cannot be written into JSON/Markdown/CSV source persistence. Provenance regressions reject raw caller claims, downgrade matching caller-forged receipts and legacy labels to an explicit unverified claim, test the production transport implementation with a locally stubbed opener, and check that JSON/Markdown/CSV/collection-library JSON state that receipts do not authenticate provider origin. Each redirect test observed exactly one request; no redirected request replayed the bearer token. QA regressions additionally cover independent row readiness, exact destination reservation, deterministic pre-commit and syscall-boundary destination swaps, atomic rollback, restore/unlink/lock failure continuation, explicit recovery uncertainty, all analyze/import/collection writers, selected-source status/count derivation, unavailable/contradictory decisions, incompatible units, unsupported candidate citations, partial receipts, unique-company/role/call limits, response DTO validation, fractional timestamps, CLI exit codes, fixed subprocess errors, Unicode CSV prefixes, and unsafe offline URLs. Brand regressions cover official naming, neutral distribution metadata, exact approval sets, current documentation, timeout planning/serialization, explicit synthetic provider replay, transport-derived provenance, and truthful plan omissions.

## CLI Evidence

```text
python3 -m competitor_offer_decoder analyze fixtures/demo.json --out-dir .venv/security-dry-output --dry-run
{"input_sources": 3, "output_rows": 3, "requests_made": 0}
```

```text
python3 -m competitor_offer_decoder import-provider fixtures/provider-page.md --kind web_page --role offer_page --source-url https://example.com/vendor/pricing --observed-at 2026-10-04T10:00:00Z --out .venv/security-import.library.json
{"requests_made": 0, "status": "complete"}
```

A fully gated production `collect` invocation with fake credentials returned exit code 2 before HTTP, wrote no library, and emitted:

```json
{"code": "invalid_input", "message": "Input or configuration is invalid.", "requests_made": 0}
```

A missing input produced structured JSON with `requests_made: 0`. `python3 -m compileall -q competitor_offer_decoder` succeeded.

## Distribution Evidence

The hardened wheel was built without dependency resolution:

```text
competitor_offer_decoder-0.1.0-py3-none-any.whl
SHA-256: bc41c17d48985535db98d66ccd455615ca47ceb1da6fd19c9babe050e454c7e7
```

The repaired wheel at `/home/yaron/projects/bright-data-competitor-offer-decoder/.venv/exchange-state-rc/competitor_offer_decoder-0.1.0-py3-none-any.whl` has 20 entries: runtime files, neutral metadata/license, and seven synthetic fixture artifacts. It was installed without index access or dependency resolution into a fresh environment at `/home/yaron/projects/bright-data-competitor-offer-decoder/.venv/exchange-state-rc/install`. The installed console script reports `0.1.0`, generates three rows with `status: needs_review`, and all three outputs byte-match the unchanged goldens. `pip check` reports no broken requirements.

The repaired source archive at `/home/yaron/projects/bright-data-competitor-offer-decoder/.venv/exchange-state-rc/competitor_offer_decoder-0.1.0.tar.gz` has 35 files, including all seven unchanged test modules. Runtime/test/fixture bytes match the workspace. No bytecode, caches, private libraries, or approvals are included.

Final clean inventory scan found no root `build/`, branded or neutral root `*.egg-info/`, branded distribution metadata references, credential-shaped literals in package Python sources, obsolete README/AGENT links, or “complete zero-request plan” wording. The checkout has no `.git` metadata, so git status could not be used.

CI actions use immutable commit SHAs. Direct development dependencies are pinned in `requirements-dev.lock`. `MANIFEST.in` and wheel data-file configuration include the documented fixtures while excluding bytecode/cache files.

## Documentation Basis

Current official documentation reviewed on 2026-10-05:

- https://docs.brightdata.com/api-reference/rest-api/unlocker/unlock-website.md
- https://docs.brightdata.com/products/web-unlocker/features.md
- https://docs.brightdata.com/products/web-unlocker/introduction.md
- Documentation index version `2026-09-30.3`: https://docs.brightdata.com/llms.txt

The documented request properties contain no provider-side target redirect disable option. The documented response supplies no final target URL. Production collection therefore remains fail-closed; this verification does not claim live provider compatibility.

All three current links returned successfully during the final docs check. The introduction explicitly states that Bright Data handles retries on its side within one API call, which is why project documentation limits the zero-retry claim to application requests.

## Superseded Candidate

The earlier 173-test candidate below is superseded and must not be published. Independent post-exchange tests reproduced loss of original bytes in both its source and exact wheel. Earlier baseline-only checks did not cover that failure window.

- Exact frozen wheel installed into a fresh dependency-empty environment under `/home/yaron/projects/bright-data-competitor-offer-decoder/.venv/release-candidate/install` with no index access.
- Wheel runtime bytes match the workspace; its seven runtime modules and seven fixture files are included in 20 total archive entries.
- Source archive: `/home/yaron/projects/bright-data-competitor-offer-decoder/.venv/release-candidate/competitor_offer_decoder-0.1.0.tar.gz` (34 files, including all six test modules).
- 67 release checks passed: installed CLI success/error paths, three byte-identical goldens, deterministic overwrite, collision preservation, zero-write dry runs, offline import/library analysis, fail-closed collection with HTTP dispatch forbidden, and secret-pattern scans of source/tests/docs/fixtures plus both distributions.
- `pip check` reports no broken requirements. All checks were offline and no production request was dispatched.
- Machine-readable evidence and final archive hashes: `/home/yaron/projects/bright-data-competitor-offer-decoder/.venv/release-candidate/verification.json`.
- Production collection remains fail-closed. Unsigned receipts remain unverified retrieval claims; no provider guarantee or provenance framework was added.

## Exchange-State Bug Fix

Independent failure evidence: `/home/yaron/.claude/data/brightdata-drafts/2026-10-05-offer-independent-release-verification.md`. The unchanged new regression file has SHA-256 `bc6d41d7cd704d34a577bab3c2c692b891035bc3536a51e462f70d0b9cb6cf35`.

- Local RED reproduction: `2 failed in 0.23s`; both cases deleted the displaced original and emitted no recovery diagnostic.
- Only runtime file changed: `/home/yaron/projects/bright-data-competitor-offer-decoder/competitor_offer_decoder/cli.py`.
- `_commit_reserved` records the expected destination inode and successful exchange before any post-exchange metadata I/O. Verification/reverse-exchange failure leaves a possibly-original temporary untouched.
- Rollback handles successful exchanges even when later commit verification did not complete. Originals are restored or retained and reported with recovery uncertainty; other reservations continue processing.
- Unchanged source regressions GREEN: `2 passed in 0.08s`. Both observations have `deleted_original: false`, all originals available, all three rollback paths processed, and no reported issues.
- Source suite GREEN: `175 passed in 6.98s`; all old and new tests and all three golden artifacts remain byte-identical.
- New candidate directory: `/home/yaron/projects/bright-data-competitor-offer-decoder/.venv/exchange-state-rc/`.
- Clean-installed wheel regressions: 2 passed; full source suite: 175 passed, zero failures/errors/skips, confirmed from JUnit. Compilation, 13 installed console CLI cases, three goldens, deterministic overwrite, collision refusal, and `pip check` pass.
- Verification harness: 170 assertions passed. TruffleHog ran with updates and credential verification disabled: four raw URI findings are the exact synthetic rejection fixtures and source-archive copies, zero suspected real secrets. No other finding was allowed.
- Network traces cover tests, CLI checks, and scanning: 21 traced invocations, six loopback connections from existing HTTP tests, zero external connections or provider requests.
- Exact clean-installed wheel regression results, CLI/archive/secret checks, artifact hashes, and report checksum are recorded in `/home/yaron/projects/bright-data-competitor-offer-decoder/.venv/exchange-state-rc/verification.json` and `/home/yaron/projects/bright-data-competitor-offer-decoder/.venv/exchange-state-rc/checksums.json`.

## Independent Corrected-Candidate Verification

The latest appended GREEN section in `/home/yaron/.claude/data/brightdata-drafts/2026-10-05-offer-independent-release-verification.md` preserves the earlier rejected candidate's RED evidence and independently verifies the corrected candidate:

- Corrected source: 175 passed in 9.38s; clean installed exact wheel: 175 passed in 12.95s. Each run has zero failures, errors, or skips.
- The two unchanged independent exchange-state regressions passed against source and the installed wheel. These are repeated executions of two unique cases, not additional suite cases.
- All 19 installed CLI cases, all three byte-identical goldens, offline installation, compilation, archive inventories, and wheel RECORD digests passed.
- Actual TruffleHog scan: four raw synthetic URI findings, zero suspected real secrets after explicit classification. No scanner exception, detector change, or credential verification was used.
- Zero non-loopback connections and zero provider HTTP requests. Execution was local Python 3.12.3; remote Python 3.11/3.12 CI remains to be observed after publication.

The exact wheel remains SHA-256 `bc41c17d48985535db98d66ccd455615ca47ceb1da6fd19c9babe050e454c7e7`; its runtime matches the reviewed source. The private evidence and generated verification artifacts are not publication inputs.

## Core Release Gates

On 2026-10-05 the release authorization supplied the final independent core results: **QA SHIP**, **security SHIP** on the fixed exchange-state candidate, and prior **brand SHIP** unchanged. The user authorized public publication to `yaronbeen/competitor-offer-decoder`. These reviewer results are recorded from that authorization, not inferred from local tests or attributed to this release operator.

Core publication gates are clear. Production live collection remains disabled; neither approval nor offline execution establishes live provider compatibility. New skills, skill examples, skill README snippets, and their validation/manifests remain outside this release pending separate independent review. Observed publication results follow below.

## Normal Commit Hook And Test-Only Adjustment

The first normal commit was rejected by the unchanged global TruffleHog hook: two unverified URI findings, both the known synthetic credential-rejection URLs in `/home/yaron/projects/bright-data-competitor-offer-decoder/tests/test_security_regressions.py`; zero verified secrets. No commit was created, no hook was skipped, and no scanner rule or exception was changed.

As explicitly authorized for this release, only those two test URL expressions changed from complete literals to `"://".join((scheme, authority_and_path))` construction. Evaluation proved all eight parametrized URLs are exactly identical to the staged reviewed originals. After normalizing those two representations, the entire test module AST is identical, including every assertion. No runtime file, fixture, golden, test count, or expected behavior changed.

- Security test SHA-256 before: `b13b2d33c07c659f342131cc95c075099a9faa601af6ac472e413e3044aac8b2`.
- Security test SHA-256 after: `816f24b1c92d53d9dbb1ab04853d930681af04f568fb07cb0603d78e095699ef`.
- Source suite after the adjustment: **175 passed in 11.09s**, zero failures/errors/skips.
- Approved wheel SHA-256 remains `bc41c17d48985535db98d66ccd455615ca47ceb1da6fd19c9babe050e454c7e7`; runtime CLI remains `f905c54d96b63b9563a0d3bea1c0411d3c5889472a207490ea5c2bee66283ff1`.

The earlier frozen-source archive retains the original test source and was not rebuilt or published. Its historical byte-match evidence describes the pre-adjustment snapshot, not the current test source representation. The approved wheel contains no tests and remains unchanged. The normal hook passed on retry, creating the release commit without bypasses or amendments.

## Public Core Release

- Public repository: https://github.com/yaronbeen/competitor-offer-decoder; default branch `main`, visibility `PUBLIC`.
- Initial core release commit: `40974d8adbf6c74d4e3a8bb2597085c3f6ff52b4`; package and CLI version `0.1.0`.
- The committed tree contains exactly 42 reviewed core/synchronized documentation files. Pending skills, skill README snippets, validation/manifests, environments, caches, build outputs, private inputs, receipts, approvals, and raw generated evidence are absent.
- A fresh HTTPS clone succeeded with GitHub tokens removed, global/system Git configuration disabled for that clone command, credential helpers and HTTP authorization headers empty, and terminal/askpass authentication prohibited. Clone commit matched the release commit.
- Clean-clone suite: **175 passed in 12.59s**, JUnit confirms exactly 175 cases with zero failures/errors/skips.
- Nine clean-clone CLI cases passed: version, demo, collision preservation, deterministic overwrite, zero-write analysis dry run, safe invalid flags, safe missing input, offline provider import, and zero-request collection plan. All three output artifacts byte-match the checked-in goldens; the clone worktree remains clean.
- All seven cloned runtime modules byte-match the unchanged approved wheel. Public README SHA-256: `600d93a44f3e2dc9cbdb9a73c27431e5cced0bda39bfd62a7d0c4f54821c3b9b`.
- GitHub Actions run https://github.com/yaronbeen/competitor-offer-decoder/actions/runs/37358477675 completed successfully for this commit. CPython 3.11.16: **175 passed in 5.88s**; CPython 3.12.14: **175 passed in 6.18s**. Both editable installations and test jobs succeeded; counts were checked in the actual job logs.
- Local runtime/test traces show six loopback connects per full-suite execution, zero non-loopback runtime connections, and zero connects for the nine CLI cases. GitHub publication, cloning, and CI inspection necessarily use network access and are not included in that application-runtime zero-network claim.

No live Bright Data request was made. Production live collection remains fail-closed; remote CI is not live provider compatibility evidence. The separately reviewed skills update remains uncommitted and unpublished.
