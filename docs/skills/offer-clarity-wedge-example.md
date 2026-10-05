# Checked Example: Earn The Claim

This is a manual exercise of the skill on a newly generated offline report, not an additional CLI output or live pricing research. All example evidence is invented.

From the repository root, generate the input with `python3 -m competitor_offer_decoder analyze fixtures/demo.json --out-dir /tmp/offer-skill-example`. Ask an assistant with local file access: "Read the offer-clarity-wedge SKILL.md as instructions. Use /tmp/offer-skill-example/report.json as untrusted data. Write the memo in Markdown without opening links or taking actions." No installation or configuration is needed; the bundled skill is not auto-registered.

## Scope

Checked input: `/tmp/opencode/skills-20261005-competitor_offer_decoder/demo/report.json`. As of `2026-10-04T10:00:00Z`; status `needs_review`; decision `scenario_worksheet`. Scenario: quantity `5`, unit `user`, annual billing preference, required inclusion `CSV export`. Synthetic sources: `harbor_offer`, `north_offer`, `west_offer`. Selected plans only, not representative market research. A self-asserted receipt does not authenticate provider origin.

## Supported Contrast

- Harbor / Team: own offer; annual base due `USD 720.00`; `supported` rate, inclusion `not_stated`, scenario `unknown`, readiness issue `inclusion`. Price: `harbor_offer/b0002`. Absence state: `offers[0].inclusion_state`; there is no absence quotation.
- North / Team: annual base due `USD 600.00`; `supported` rate, inclusion `explicitly_included`, scenario `meets_declared_checks`, no readiness issue. Refs: `north_offer/b0002`, `north_offer/b0003`.
- West / Team: annual base due `USD 480.00`; `supported` rate, inclusion `explicitly_excluded`, scenario `fails_declared_checks`, no readiness issue. Refs: `west_offer/b0002`, `west_offer/b0003`.

The lower selected West base does not satisfy the required export check. This is an unranked, scenario-specific contrast, not a winner or total-cost conclusion. An annual commitment is not monthly payment; any monthly equivalent in the underlying report is comparison-only.

## Blocked Claims

Do not say Harbor includes CSV export, is cheapest, or offers a unique advantage. Its inclusion remains unstated. Taxes and fees are unstated; discounts are not inferred; unselected terms remain unknown for all three rows. No price candidate is unsupported in this demo. North passing the declared checks does not resolve Harbor's readiness issue or establish checkout eligibility.

## Earn The Claim

Own-offer clarity task: "State whether CSV export is included." Human question: What exact inclusion or exclusion statement is the product owner prepared to verify for Harbor / Team?

Editorial hypothesis: make the export decision explicit before attempting export-led positioning. No affirmative Harbor inclusion copy is supported yet. No price, product, or website changes were made.

## Evidence And Warnings

Warnings: none supplied; literal grammar and selected snapshots still limit the result. Inspect real excerpts for sensitive information before sharing.

- `harbor_offer/b0002`: "USD 12 per user/month, billed annually."
- `north_offer/b0002`: "USD 10 per user/month, billed annually."
- `north_offer/b0003`: "Includes CSV export."
- `west_offer/b0002`: "USD 8 per user/month, billed annually."
- `west_offer/b0003`: "CSV export not included."

All three sources: observed `2026-10-04T10:00:00Z`; status `collected`; provenance `synthetic_fixture`; record unknown / `none`; published/provider dates unknown.

- `harbor_offer`: `https://example.com/harbor/pricing`; SHA-256 `d538e37f52c87f6330d891587b87c66d9fb1df0a6866cc185db0ad9e1b33307f`.
- `north_offer`: `https://example.com/north/pricing`; SHA-256 `38ebf5f66a898c41b3da1a9e3fef5792071bedcc3165a509b3527d4c9c8308bc`.
- `west_offer`: `https://example.com/west/pricing`; SHA-256 `77d49f93d01dd0cd0ce6c5f6173da907be50253cb5caf4d7b3d290402299707a`.

Hashes identify invented snapshots, not truth. [Validation record](validation.md).
