# Offer Decision Truthfulness And Receipt Reservation

## Problem

Useful extracted values were allowed to overstate certainty: an unavailable selected terms page did not block positive qualification, unresolved fixture decisions still produced `status: ok`, and an explicit incompatible unit was labeled unknown instead of failed. Collection also checked an output path without atomically claiming it before the transport boundary.

## Symptoms

- Positive scenario qualification could coexist with unavailable selected evidence.
- Unreferenced unavailable sources incorrectly influenced counts/status while unresolved selected rows did not.
- Unsupported price-like text disappeared instead of remaining cited.
- A success followed by failure was labeled fully failed rather than partial.
- Output collisions could occur after a potential paid request.

## Failed Assumptions

- A valid price on one page was treated as sufficient despite another explicitly selected page being unavailable.
- Report status was derived only from collection state rather than unresolved required row decisions.
- A preflight existence check was mistaken for atomic destination reservation.

## Solution

- Derive status, counts, stale warnings, and default `as_of` only from plan-referenced sources.
- Block positive qualification when any selected source is unavailable; classify required contradictions and unresolved decisions explicitly.
- Preserve exact unsupported price candidates with block citations and render unknown price fields visibly.
- Validate response DTO fields before use and return partial after prior successful jobs.
- Enforce four offer/four terms pages and one role per deterministic company identity.
- Claim a new output path atomically and hold a sidecar lock plus reserved temp file before invoking collection.

## Root Cause

Row extraction, report-level readiness, and collection durability are separate decisions. Conflating them caused technically correct arithmetic to be presented with stronger evidence and operational certainty than the selected inputs supported.

## Prevention

Test row decisions separately from report status, test unavailable and unreferenced sources together, preserve candidate evidence even when parsing fails, and place filesystem reservation assertions inside a fake transport boundary.

Keep `readiness_issues` independent from `scenario_status`: a definitive failure in one dimension cannot hide unresolved price, billing, inclusion, scope, or selected-source evidence.
