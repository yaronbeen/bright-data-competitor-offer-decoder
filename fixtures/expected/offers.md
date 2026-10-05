# Competitor offer scenario worksheet

> Synthetic fixture data: all synthetic-labeled sources are invented examples.

**Method:** `deterministic_rules_v1`

**Bounded scenario:** 5 user; billing preference annual; required inclusion CSV export.

Monthly equivalents are comparison calculations, not monthly payment options. Taxes, fees, discounts, and unselected terms remain unknown. This worksheet does not select a winner.

A self-asserted receipt does not authenticate provider origin.

## Offers

### Harbor: Team

- Observed rate: USD 12.00 per user/month
- Billing commitment: annual
- Monthly equivalent: 60.00 (comparison only)
- Base due per billing period: 720.00
- Required inclusion: not stated
- Declared-check result: unknown

- Unknown/limit: Taxes and fees are not stated in the selected scope.
- Unknown/limit: Discounts are not inferred.
- Unknown/limit: Whether CSV export is included is not established.

- Evidence (price): `harbor_offer/b0002`: “USD 12 per user/month, billed annually.”

### North: Team

- Observed rate: USD 10.00 per user/month
- Billing commitment: annual
- Monthly equivalent: 50.00 (comparison only)
- Base due per billing period: 600.00
- Required inclusion: explicitly included
- Declared-check result: meets declared checks

- Unknown/limit: Taxes and fees are not stated in the selected scope.
- Unknown/limit: Discounts are not inferred.

- Evidence (price): `north_offer/b0002`: “USD 10 per user/month, billed annually.”
- Evidence (inclusion_positive): `north_offer/b0003`: “Includes CSV export.”

### West: Team

- Observed rate: USD 8.00 per user/month
- Billing commitment: annual
- Monthly equivalent: 40.00 (comparison only)
- Base due per billing period: 480.00
- Required inclusion: explicitly excluded
- Declared-check result: fails declared checks

- Unknown/limit: Taxes and fees are not stated in the selected scope.
- Unknown/limit: Discounts are not inferred.

- Evidence (price): `west_offer/b0002`: “USD 8 per user/month, billed annually.”
- Evidence (inclusion_negative): `west_offer/b0003`: “CSV export not included.”

## Own-offer clarity checks

- State whether CSV export is included.

## Evidence appendix

- `harbor_offer`: https://example.com/harbor/pricing; observed 2026-10-04T10:00:00Z; record ; SHA-256 `d538e37f52c87f6330d891587b87c66d9fb1df0a6866cc185db0ad9e1b33307f`; provenance `synthetic_fixture`.
- `north_offer`: https://example.com/north/pricing; observed 2026-10-04T10:00:00Z; record ; SHA-256 `38ebf5f66a898c41b3da1a9e3fef5792071bedcc3165a509b3527d4c9c8308bc`; provenance `synthetic_fixture`.
- `west_offer`: https://example.com/west/pricing; observed 2026-10-04T10:00:00Z; record ; SHA-256 `77d49f93d01dd0cd0ce6c5f6173da907be50253cb5caf4d7b3d290402299707a`; provenance `synthetic_fixture`.

## Limits

Selected pages and narrow literal grammar bound this report. Unknown means not established by the selected scope, not absent from the market or offer.

Uses Bright Data for optional public-data retrieval. Analysis and decisions are local application logic. Not affiliated with or endorsed by Bright Data.
