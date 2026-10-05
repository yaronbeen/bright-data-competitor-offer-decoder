# Handover 004: Approved Core Release

Date: 2026-10-05.

## Current State

The user authorized public core publication to `yaronbeen/competitor-offer-decoder`. Final reviewer results supplied with that authorization are QA SHIP, security SHIP on the corrected exchange-state candidate, and unchanged prior brand SHIP. No further core re-review is pending.

Independent evidence at `/home/yaron/.claude/data/brightdata-drafts/2026-10-05-offer-independent-release-verification.md` preserves the rejected candidate's RED results and appends corrected-candidate GREEN: 175 source tests, 175 clean installed-wheel tests, two independent regression cases against each, 19 installed CLI cases, and three goldens. Zero external connections or provider requests occurred.

Reviewed wheel: `/home/yaron/projects/bright-data-competitor-offer-decoder/.venv/exchange-state-rc/competitor_offer_decoder-0.1.0-py3-none-any.whl`, SHA-256 `bc41c17d48985535db98d66ccd455615ca47ceb1da6fd19c9babe050e454c7e7`. Runtime CLI SHA-256: `f905c54d96b63b9563a0d3bea1c0411d3c5889472a207490ea5c2bee66283ff1`.

## Release Inventory

The reviewed core inventory is the 41 workspace files named by the frozen candidate's credential-pattern checks in `/home/yaron/projects/bright-data-competitor-offer-decoder/.venv/exchange-state-rc/verification.json`, plus this synchronized handover. It comprises root package/license/operations documents, the pinned test workflow, seven runtime modules, seven test modules, seven invented fixtures/goldens, six core solution documents, and the numbered core handovers. Stage those exact files only.

Do not stage `/home/yaron/projects/bright-data-competitor-offer-decoder/skills/`, `/home/yaron/projects/bright-data-competitor-offer-decoder/docs/skills/`, or `/home/yaron/projects/bright-data-competitor-offer-decoder/docs/skill-readme-section.md`. Their new content and validation/manifests are under separate independent review. Do not publish virtual environments, builds, caches, private inputs, approvals, libraries, receipts, or raw generated verification evidence.

## Release Operations

GitHub authentication was verified as `yaronbeen`; the exact requested repository returned HTTP 404 before creation. Git was initialized on `main` after parent/path verification. Status/diff/log were inspected; exactly 42 core files were staged and the five pending skills files were left untracked.

The normal hook rejected only the two known synthetic URI literals, with zero verified secrets. The authorized fallback changed only two URL source expressions in `/home/yaron/projects/bright-data-competitor-offer-decoder/tests/test_security_regressions.py` to runtime string construction. All eight URL values and all assertions were proven identical by evaluation and whole-module AST comparison. Old test SHA-256 `b13b2d33c07c659f342131cc95c075099a9faa601af6ac472e413e3044aac8b2`; new `816f24b1c92d53d9dbb1ab04853d930681af04f568fb07cb0603d78e095699ef`. All 175 tests passed again in 11.09s. Runtime, wheel, goldens, hooks, and scanner rules are unchanged. Retry only a normal commit; do not skip hooks or amend.

Repository creation, push, unauthenticated public clean-clone tests/offline CLI/goldens, and Python 3.11/3.12 CI are not yet observed at this checkpoint. Record actual results after execution.

## Limits And Next Work

Production live collection remains fail-closed. No Bright Data live request is authorized or required. Pending skill snippets remain separate from the core README for a later approved update. Historical handovers retain their then-current gate states and do not override this authorization.
