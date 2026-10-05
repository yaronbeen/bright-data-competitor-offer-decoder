# Post-Exchange Original Preservation

## Independently Reproduced Failure

The forward atomic exchange succeeded, moving the overwritten original into the temporary path. The following metadata read or attempted reverse exchange failed before the reservation was marked committed. Exception cleanup then deleted the original temporary, and rollback skipped the reservation because committed state was false.

Evidence: `/home/yaron/.claude/data/brightdata-drafts/2026-10-05-offer-independent-release-verification.md`. Independent regression: `/home/yaron/projects/bright-data-competitor-offer-decoder/tests/test_exchange_state_regressions.py`.

## Minimal Fix

- Record the expected new destination inode before exchange and mark exchange success immediately after the syscall returns, before metadata reads.
- Never unlink the temporary while a successful exchange remains unreversed: it may contain the last original.
- Clear exchange state only after successful reversal or restoration.
- Enter existing identity-checked rollback when either exchange or verified commit state is active.
- Leave an original at its recovery path when a raced destination cannot safely be replaced; report `recovery_required` with `recovery_uncertain: true`.

## Verification

Both independent tests failed before the fix and passed afterward without edits. The post-exchange metadata error restores all originals; reverse failure preserves/report originals instead of deleting them. Every reservation is processed. The full source suite has 175 passing cases and unchanged tests/goldens. The previous frozen candidate is superseded.
