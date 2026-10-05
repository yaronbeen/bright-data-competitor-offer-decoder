# Web Unlocker Redirect Attribution: Fail Closed

## Problem

The client approved one target URL but raw Web Unlocker content could have originated after a provider-side target redirect. The local urllib redirect policy controls only the POST to `api.brightdata.com`; it cannot control redirects followed inside the provider.

## Symptoms

- A custom urllib redirect handler ran after the default handler for 301, 302, and 303, causing a second request with the bearer header.
- Returned page content was labeled with the requested target URL without verified final-target metadata.
- Query strings could enter plans and receipts.
- Generic transport wrapping erased whether a timeout happened after dispatch.

## Failed Attempts

- Merely adding an `HTTPRedirectHandler` instance to `build_opener` did not reliably outrank the default redirect handler.
- Searching for a plausible redirect option was rejected because the current OpenAPI and configuration docs do not document one.

## Solution

- Give the no-redirect handler an earlier handler order and verify 301, 302, 303, 307, and 308 against a loopback server with exactly one request.
- Mark the production urllib transport as live-unverified and reject it in collection before dispatch. Keep offline import and injected fake transports available.
- Reject every live URL containing a query string.
- Enforce retained-record allowance before each request and before retaining results.
- Preserve `TransportTimeout` through urllib so collection records `completion_unknown`.

## Root Cause

Client HTTP redirects and provider-side target redirects are separate trust boundaries. The original implementation addressed the former incompletely and assumed attribution for the latter without documentation.

## Prevention

Keep network behavior covered by local protocol tests, never invent provider options, and require explicit final-target evidence before enabling production collection.

Apply one query-free URL validator to every persisted source path, not only live manifests. Every CLI writer must reserve and identity-check its destination so a deterministic path swap cannot be clobbered between validation and commit.
