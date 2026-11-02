What this change does: Merge 57b47cd preserves the approved 16-hour default and main’s paused `tasks -C <dir>` closing commands. The README retains both sections accurately, and the calibration header records the reported user approval.

Reviewer: codex/gpt-6.1-sol.

Findings: none. No new Critical, Important or Minor issues found.

Checked both immutable parent diffs and connected code:
- `.worktrees/hq-b2b50b/tools/turn_pause/limits.toml` changes only active duration; counting and budget scaling remain unchanged.
- The allowlist and its unit tests match main. Protected-path checks still precede command classification; bookkeeping remains available after read grace expires.
- Default-dependent tests use 16 hours. The remaining four-hour values explicitly construct custom fixtures, including `pause_on_calls()`, and do not accidentally test the production default.
- README budget examples match the existing ceiling-based scaling.

Verdict: Ready to integrate the reviewed merge under the recorded activation approval. Declined to judge: none.

Not checked: tests were not rerun; the controller reports 408 focused and 2,702 full-suite passes. Live activation was not exercised; changing the live limits still pauses existing turns with `limits-changed`.
