# Reject Percent-Encoding in URL Authorities

## Problem

URL parsers expose percent-encoded authority components differently from literal userinfo delimiters. A URL containing escaped `@`, `:`, `/`, or `\\` in its authority can be interpreted differently by downstream URL consumers.

## Symptoms

- Source URL validation checked parsed `username`, `password`, and hostname fields but did not express a direct policy against percent-encoded authority syntax.
- The same URL validator is shared by analysis, offline import, and live manifest planning, so a gap could affect persisted citations and network targets.

## Solution

- Reject any percent escape in `urlsplit(value).netloc` before inspecting authority fields.
- Keep errors fixed and omit the offending URL value.
- Regression-test encoded username delimiters, encoded credentials, escaped host separators, direct analysis, import, collection planning/dispatch, and the no-output CLI path.

## Root Cause

Validation relied on one parser's semantic username/password decomposition instead of enforcing the application's stricter source URL grammar on the raw authority representation.

## Prevention

Keep authority validation centralized in `url_safety.py`; route every source/import/manifest URL through it and add percent-encoding cases whenever URL parsing behavior changes.
