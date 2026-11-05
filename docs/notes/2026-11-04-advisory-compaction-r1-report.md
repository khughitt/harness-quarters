# Code Review Round 1: hq-e51fac and lore-d27b9c

- **Verified Reviewer Identity:** `agy/gemini` (read-only research subagent `b0dd7104-5ea9-4be7-8e57-4b55ec3f0d5d`; returned full review in message because no plan workspace exists for direct tasks; persisted by controller)
- **Reviewed Revisions:**
  - `hq-e51fac` (`.worktrees/hq-e51fac`): `d6de8ee76b1049e6373bba611db86e5b845cddcb..a3c247dbba1f0a117a4f3ba9064111037e8e9c6f` (HEAD `a3c247dbba1f0a117a4f3ba9064111037e8e9c6f`)
  - `lore-d27b9c` (`.worktrees/lore-d27b9c`): `c5c5e2a13cc52616781609183f5db436202dea74..be6f6b6a7277c583a1aa2487eaf576e02f0160ee` (HEAD `be6f6b6a7277c583a1aa2487eaf576e02f0160ee`)

## Strengths

- **Backward-compatible state and limits in hq-e51fac:** Introducing `PAUSE_COUNTS = ('active', 'calls', 'spawns')` in `tools/turn_pause/counters.py:11` while keeping `COUNTS`, `TurnState.compactions`, `Limits.compactions`, and `tools/turn_pause/limits.toml` unchanged preserves both `limits_sha` and the serialized `RootState` schema, preventing `limits-changed` mid-turn pauses when live sessions pick up the updated hook.
- **Clear advisory warning and CLI surface in hq-e51fac:** `tools/turn_pause/hook.py:68-71,123-124` and `tools/hq_cli/pause.py:81-93` cleanly distinguish advisory compaction warnings and unhooked compaction display (`compactions -/2 (advisory, unhooked)`) while keeping `--json` output schemas stable.
- **Focused test coverage in hq-e51fac:** `tools/test_turn_pause_counters.py:148-163`, `tools/test_turn_pause_hook.py:747-760`, and `tools/test_hq_pause.py:15,51,134` directly test that compaction warns once at the threshold and never pauses the turn at 3 or 10 compactions.

## Issues

### Critical

- None.

### Important

1. **Contradictory hard-stop compaction rule remains in planned-execution recovery guidance (`rule:6c0a22eb29eb4e1db82c7e7e9fc6ae27`):**
   - **Location:** `instructions/fragments/decisions.md:364-373` (assembled at `instructions/AGENTS.md:495-504` and tracked in `instructions/rules/6c0a22eb29eb4e1db82c7e7e9fc6ae27.json:22`).
   - **Problem:** While `rule:1f37e3afebdd433a9ccaa2970cde7289` (`instructions/fragments/decisions.md:60-63`) was updated to state that reaching or crossing the compaction threshold never pauses or stops a turn on its own (hooked or unhooked), `rule:6c0a22eb29eb4e1db82c7e7e9fc6ae27` later in the same `## Decisions` fragment still says:
     `After compaction below hq pause limits, check hq pause status (maintaining any counts the hook does not observe) and recover inside the current turn budget ... When compactions cross hq pause limits (with no separate earlier threshold), stop under the turn-pause rule above and, when compaction or context growth is the binding cause, recommend a user-chosen fresh controller in the pause decision.`
   - **Impact:** Directly contradicts `rule:1f37e3afebdd433a9ccaa2970cde7289` and violates `lore-d27b9c`'s requirement that crossing the compaction threshold never stops or parks a turn on its own.
   - **Fix:** Update `rule:6c0a22eb29eb4e1db82c7e7e9fc6ae27` in `instructions/fragments/decisions.md:364-373` so that after any compaction while enforced turn limits remain uncrossed, the controller checks `hq pause status` (maintaining enforced counts where no pause hook runs) and recovers inside the current turn budget, and only stops/recommends a user-chosen fresh controller when an enforced turn-pause limit is crossed. Refresh `instructions/rules/6c0a22eb29eb4e1db82c7e7e9fc6ae27.json` and rerun `just assemble` and `just check`.

### Minor

1. **Hook pause refusal and notification strings still format `compactions {k}/{K}` without `(advisory)`:**
   - **Location:** `tools/turn_pause/hook.py:51-53,65-66,356-357`.
   - **Problem:** Task `hq-e51fac` specifies that `human-readable status/limits/refusal text labels compactions as advisory`. While `COMPACTION_WARNING_TEXT` and `BUDGET_TEXT` in `hook.py` and `status`/`show_limits` in `pause.py` label `compactions` as `(advisory)`, the refusal templates `ROOT_TEXT` (`hook.py:53`), `LIMITS_CHANGED_HEAD` (`hook.py:66`), and `_notice` (`hook.py:357`) still render `compactions {k}/{K}` unadorned.
   - **Fix:** Append `(advisory)` to `compactions {k}/{K}` in `ROOT_TEXT`, `LIMITS_CHANGED_HEAD`, and `_notice` (and matching test strings in `tools/test_turn_pause_hook.py`).

## Declined to Judge

- Frozen historical design specs and notes under `docs/specs/2026-11-01-turn-pause-design.md`, `docs/plans/2026-11-01-turn-pause.md`, and `docs/notes/2026-11-01-turn-pause-activation.md` in `hq`: outside task scope per the Design & Plan Docs rule because they are dated decision/historical records rather than reference docs (`README.md` is the live reference section and was updated).

## Assessment

**Ready to merge? With fixes.**
