# Handover 005: User-Required Repository Name

Date: 2026-10-05.

## Current State

The user explicitly requires Bright Data in every GitHub repository name. This overrides the earlier neutral repository-slug proposal only, not the package/CLI identity or approved core scope.

Current public repository: https://github.com/yaronbeen/bright-data-competitor-offer-decoder. The existing owned repository was renamed in place using `gh repo rename`; no duplicate was created and none was deleted. Before/after repository ID `1406241544`, node ID `R_kgDOU9GLCA`, owner `yaronbeen`, public visibility, `main`, history, and prior CI runs are preserved. The exact target was absent before the rename; the authenticated owner had admin permission.

Origin is `https://github.com/yaronbeen/bright-data-competitor-offer-decoder.git`. The local path is unchanged. Package/CLI `competitor-offer-decoder`, Python module `competitor_offer_decoder`, version `0.1.0`, runtime, tests, goldens, pinned workflow, and the approved wheel are unchanged.

## Documentation Changes

Updated current public links and repository guidance, preserved the append-only prior decisions, and added the explicit naming override. Independent non-affiliation wording remains: this is not an official Bright Data repository and is not affiliated with or endorsed by Bright Data. Historical initial-authorization slugs do not override the new user requirement.

This commit is documentation-only. The new handover adds one public documentation file to the preceding 42-file core tree. No new skills, README skill snippets, skill examples, validations/manifests, or generated private evidence are publication inputs.

## Verification Checkpoint

Pre-rename public `main` was `43a1a535310cd315292fbedd1f6604f3efee1715`, with 175 passing tests in a credentials-disabled public clone and 175 passing tests each in Python 3.11/3.12 CI. Repository identity and public/default-branch state were observed after the rename. Run the normal commit hook, push the documentation-only update, then verify a fresh unauthenticated clone of the exact new URL, unchanged version/runtime, all 175 tests, offline CLI/goldens, and CI on that resulting commit before reporting its final hash.

The old URL redirects with HTTP 301 to the exact new URL. Local post-correction tests passed: 175 in 8.67s. Git diff confirms no runtime/test/fixture/package/workflow changes. New README SHA-256 `9f82a3a30f5fd45be2fa739f1753c087088efd27b99491727465369f94278964`; approved wheel SHA-256 remains `bc41c17d48985535db98d66ccd455615ca47ceb1da6fd19c9babe050e454c7e7`.

## Limits And Next Work

Production live collection remains fail-closed; no live Bright Data request is required or authorized. The five pending skills files remain untracked and unpublished until the main orchestrator separately approves them. Do not stage them while updating repository names or links.
