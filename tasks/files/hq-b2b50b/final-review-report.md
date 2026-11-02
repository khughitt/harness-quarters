What this change does: Raises the default active-time cutoff from 4 to 16 hours, preserving the other limits and all counting and budget algorithms. It documents the historical evidence, budget consequences, and activation behavior.

Reviewer: codex/gpt-6.1-sol. Reviewed frozen tree dbc616b5406d6c9d9b09363ad3b58a5e8e0bc555 against d9aac7e546eb98778ddd7686aee5e51975be9902.

Findings: **Critical 0, Important 0, Minor 0.**

Strengths:

- The production change is confined to `.worktrees/hq-b2b50b/tools/turn_pause/limits.toml:4`. The shared loader, counter, engine, and hook paths continue to enforce the existing strict “above limit” boundary.
- `.worktrees/hq-b2b50b/tools/test_turn_pause_hook.py:361` checks both harness adapters through exactly 16 hours and beyond, including the 12-hour warning. Budget tests cover the changed scaling denominator for both shorter and longer explicit budgets.
- The calibration table agrees with the attached measurement output. The 16-hour recommendation preserves the original controller’s call-based stop and the independent time-only guard while giving more headroom to long executions.
- `.worktrees/hq-b2b50b/docs/notes/2026-11-02-active-cutoff-report.md:52` clearly distinguishes measured duration from validity. It discloses the remaining 21.1-hour review-correction case, incomplete historical evidence, and the additional exposure for low-call runaways.
- README correctly describes budget scaling and the existing `limits-changed` pause. Activation remains subject to user approval.

Declined to judge: whether individual historical tail sessions were valid or runaway. The retained aggregate evidence cannot establish that distinction; the report appropriately avoids claiming otherwise.

**Verdict: Ready to merge once the required full suite passes and the user approves live activation.** No corrective changes required.

Not checked: I did not rerun tests or replay live session stores; full verification was still running when dispatched.
Risk: Valid work exceeding 16 active hours can still pause, and activation pauses existing turns on their next hooked call.
