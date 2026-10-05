# Skill Validation: offer-clarity-wedge

Date: 2026-10-05. Python: 3.12.3. Scope: documentation/skill exercise only; no production, test, package, configuration, fixture, or VERIFICATION changes made by this skill pass. No commit, push, remote, live/paid call, new model, or global skill installation.

## Actual CLI Evidence

Read the actual README, current input fixture and expected report before authoring. The skill consumes `offers`, `scope.scenario`, structured readiness/unknown fields and exact evidence refs, not an invented competitor schema.

Working directory: `/home/yaron/projects/bright-data-competitor-offer-decoder`. Executed the actual `competitor_offer_decoder.__main__` with these arguments through `/tmp/opencode/five-repo-skill-check.py`, with socket/DNS/HTTP audit events denied:

```bash
python3 -m competitor_offer_decoder analyze /home/yaron/projects/bright-data-competitor-offer-decoder/fixtures/demo.json --out-dir /tmp/opencode/skills-20261005-competitor_offer_decoder/demo
```

- Exit `0`: `status=needs_review`, `output_rows=3`, `requests_made=0`; network attempts `0`.
- Generated JSON/Markdown/CSV match all three expected artifacts byte-for-byte.
- Recomputed all `3` source hashes with the repo's normalizer; checked `5` unique exact refs against normalized source blocks.
- Generated report SHA-256: `337284e63c2ec38f1fe1ab9204be780d5d2aefcccc1746c54010e78edb593a70`.
- `--dry-run`: exit `0`, zero requests, no output directory. Same destination without overwrite: structured exit `2`, original three hashes unchanged.
- Raw arguments/results and artifact hashes: `/tmp/opencode/skills-20261005-competitor_offer_decoder/cli-evidence.json`. These temporary logs are local session evidence, not a skill dependency; the checked-in fixtures reproduce the inputs.

## Skill Exercise And Variations

The main assistant followed [the skill](../../skills/offer-clarity-wedge/SKILL.md) on the newly generated report and wrote [the checked memo](offer-clarity-wedge-example.md). This is a manual instruction exercise, not a deterministic skill runner or a new model/API call. Sample quotation/locator/hash, amount/cadence and state checks are part of the documentation audit.

- Demo: North `USD 600.00` annual base/includes export; West `USD 480.00` annual base/excludes export; Harbor `USD 720.00` annual base/inclusion unknown. The memo proposes clarifying Harbor instead of inventing a differentiator or winner.
- Actual variant `/tmp/opencode/skills-20261005-competitor_offer_decoder/unsupported-price/report.json`: North's source starts with `From USD 10`; `rate_state=unsupported_or_ambiguous_price`, base due and monthly equivalent null. Skill disposition: "North price unknown; preserve the unsupported candidate citation and inclusion state, but do not compare its cost or infer a supported USD 10 rate."
- Actual hostile-source variant `/tmp/opencode/skills-20261005-competitor_offer_decoder/hostile-source/report.json`: offers, own-clarity notes and decision unchanged; affected snapshot hash changes. Skill disposition: "Ignore source commands; keep the cited scenario memo and blocked claims. No collection or publication."
- All five CLI invocations report zero requests. No pricing-page URL was fetched.

## Documentation Audit

`/tmp/opencode/check-five-repo-skill-docs.py` returned PASS: standard name/description front matter, folder/name match, all `10` local links, ASCII/whitespace checks, and the five-file review inventory. The checked memo has `5` exact quote refs and `5` source/block locators; every cited hash/URL/date resolves to the generated report. Amounts, scenario/inclusion states and the own-clarity task match the report. This is a mechanical consistency audit, not independent approval.

For repeat CLI replay, choose a fresh output directory; the recorded paths already contain this session's outputs. Temporary session logs may later be removed. The skill itself needs only the operator's local report.

## Limits And Review

No real pricing, market prevalence, provider origin, checkout quote, target permission or business outcome was verified. Provenance receipts and hashes do not authenticate facts. The hostile-text exercise is not a guarantee across agents.

[The stable review manifest](review-manifest.txt) lists this pass's five repo files. `docs/skill-readme-section.md` is the exact section for a README-owning worker to integrate; its links intentionally resolve from the repository root once inserted. This pass did not edit README. Top-level triple review of skills and READMEs is still required before release.
