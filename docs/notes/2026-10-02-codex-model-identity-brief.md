# Brief: Codex sessions naming their own model

Goal: tack-fce47e. Idea: tack-52ac05 (source: tack-1327b8).

## 1. Problem

A Codex session cannot say which model it is. Task stamps (`agent`, `model`) and the
review notes obs reads (`reviewer: codex/<model>`) lose the model half for every Codex
session, so model attribution in outcome measures covers Claude Code only.

## 2. Current behaviour and evidence

- **Claude Code has no gap.** The ops `claude-provenance` hook (SessionStart and
  PostModelSwitch) writes an env file that each Bash call re-reads, so `TASKS_AGENT` is
  `claude-code/<model>` and `TASKS_MODEL` follows `/model` (tack-d5a56c, live acceptance
  2026-09-13). The idea's body suspected otherwise; that part is settled.
- **Codex exports a constant.** `codex/config.toml:197` sets `TASKS_AGENT = "codex"` in
  `shell_environment_policy`; the effective model can be overridden per session (`-m`,
  profiles), so config is not evidence.
- **The rollout knows.** Each `turn_context` line carries `payload.model` and `effort`,
  and obs already extracts them (`obs/codex_adapter.py:66-69`). The session sees
  `CODEX_THREAD_ID`, which names its rollout file.
- **Session ids are unreliable in children.** relay-c85a0f, relay-60ae9e, and
  relay-652c96 report Codex child sessions exporting conflicting `CODEX_SESSION_ID` and
  `CODEX_THREAD_ID`; a resolver keyed on either inherits that.
- obs-5ecc0c (idea) wants a model and effort breakdown per task stage.

## 3. Constraints

- "Pass `--agent` only when you know it; never guess" (doc/instruction-provenance.md
  T13): a fallback must stamp the harness alone, never a config default.
- The reviewer field is metadata until obs joins `session:` to an observed session
  (cross-harness review brief §3).
- relay owns harness adapters and identity; tasks owns stamping; obs owns derivation.

## 4. Alternatives

1. **A resolver command (lean).** `agent-identity` prints `codex/<model>` from the
   session's rollout (thread id → rollout → last `turn_context.model`), or `codex` when
   it cannot verify. Agents use it for review notes; tasks calls it when `TASKS_AGENT`
   is bare `codex`. Home: relay (identity), with tasks as caller.
2. **obs derives it after the fact.** Stamps stay `codex`; obs fills the model by
   joining the task's session to the rollout it already parses. No harness change, but
   review notes stay unverified text and the join needs reliable session ids.
3. **tasks reads the rollout itself.** Fewer moving parts, but couples the tasks CLI to
   Codex's private file layout.

## 5. Unanswered questions

- Does thread id → rollout → `turn_context.model` resolve correctly in a top-level and
  in a child Codex session, given the id conflict? — research tack-1bd166.
- Does Codex expose the model to hooks or the shell any other way (a hook payload, an
  env var in a newer CLI)? — the same research.
- Which project owns the resolver? — decided by the research result: relay if ids hold,
  obs (alternative 2) if they do not.

## 6. Proposed decomposition

- tack-1bd166: probe both questions; wakes tack-52ac05.
- Then one implementation task in the owning project, filed from the result.
