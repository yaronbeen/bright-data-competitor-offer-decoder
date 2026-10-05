# Brand-Neutral Provider Integration

## Problem

The proposed public distribution used a provider trademark even though no trademark permission was established. Integration documentation also mixed product names, omitted provider-visible request settings from dry runs, and described retry/provenance boundaries too broadly.

## Symptoms

- Distribution name `bright-data-competitor-offer-decoder` implied a closer brand relationship than intended.
- “No retries” could be read as a statement about provider internals rather than application behavior.
- A 75-second fixed timeout was too short for the reviewed provider workflow.
- Dry-run plans omitted country and output-format details.
- Exported `bright_data` receipts could be mistaken for authenticated retrieval evidence.

## Solution

- Publish only under the neutral `competitor-offer-decoder` repository/distribution identity; retain the historical local path temporarily.
- Use `Bright Data Web Unlocker API` at first public reference and `Web Unlocker API` thereafter.
- Document zero application retries while acknowledging that the provider may internally retry one submitted request.
- Default timeout to 180 seconds and allow explicit values through 300 seconds while preserving `completion_unknown` after dispatch.
- Include country, raw format, Markdown data format, and timeout in zero-request plans.
- Require approval URLs to equal the planned target set, with no extras.
- Force every injected/fake transport to `synthetic_fixture`; use `bright_data_transport` only for the current in-memory production invocation and downgrade exports/imports to `operator_claimed_bright_data` because receipts are editable and unsigned.
- Show the non-secret `POST` method and pinned endpoint in dry-run plans while explicitly marking API key and zone omitted.
- Ship explicit invented manifest/provider fixtures labeled `synthetic_fixture`.

## Prevention

Add brand regressions for public names, first-reference terminology, current documentation URLs, neutral package metadata, plan serialization, approval equality, timeout bounds, and explicit synthetic fixtures before publication review.
