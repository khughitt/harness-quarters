---
id: tack-21ea5d
title: "Gates as hooks: enforce workflow checkpoints in the harness, not in skill prose"
status: done
priority: "2"
size: m
complexity: mid
process: planned
owner: main
created: 2026-09-15T01:01:58Z
updated: 2026-09-25T10:28:39Z
started: 2026-09-24T23:23:50Z
completed: 2026-09-25T10:28:39Z
depends: []
parent: tack-756baa
tags: [flow, skills, rules]
source: "mindful:thought:48e70c654fd84c6ab72d3f06b6261683"
agent: claude-code/claude-opus-5
spec: docs/specs/2026-09-24-turn-boundary-gate-design.md
plan: docs/plans/2026-09-24-turn-boundary-gate.md
---

Move deterministic gates out of prompts: a Stop hook that runs tasks check, a pre-commit that refuses without a doing task, a check that a planned task has a reviewed spec before code changes. Harness-independent where possible (Claude Code, Codex). Lets the skill prose shrink to judgment only.

## Notes

- 2026-09-22T00:30:22Z (main): scope: briefed; evidence narrows the gate worth enforcing first: 16 flow closures on record all carry verified gate + retro (no state-gate violation to catch), while the turn-boundary stall (ai-c62995, twice) is the recorded failure and obs's stall proxy already measures it — a Stop hook refusing to end a turn on an unparked claim is the candidate; feasibility research ai-80b836 (Claude Code block semantics, Codex stop hooks, the tasks claim query) precedes design; tasks check on Stop and a pre-commit without a doing task stay listed as later gates; brief: docs/notes/2026-09-21-flow-gates-brief.md
- 2026-09-22T01:22:16Z (main): ai-80b836 finding 2026-09-21: a Stop hook can refuse the turn end in both harnesses (decision:block / exit 2; stop_hook_active guards the retry), matching claim.session from tasks prime --all-projects against the input session_id — no new tasks command. Claude Code: a subagent's tasks start claims under the controller's session, so the controller's Stop is refused (the owner's obligation is visible); a Stop also fires in the subagent context, indistinguishable by input, blocked once. Codex: blocked by the tasks gap tasks-3190fb — claims are sid:<command pid> and die with the command until identity reads CODEX_SESSION_ID. Observed cost: the blocked model parked with a vacuous next step ('Waiting for next steps'), the induced-park shape the proxy counts as handled. Design next: the hook (ops hooks now, relay after cutover), its reason text (name the claim, name park with a real next step as the release, tell a subagent to report and stop), and the rollout judgment that separates resumed progress, legitimate parks, unnecessary parks.
- 2026-09-22T01:47:13Z (main): Follow-up to ai-80b836: tasks-3190fb is done at tasks main 903f04a; tasks was reinstalled. Codex claims now use the native thread id and TTL liveness, resolving the tasks-side identity blocker in the earlier finding. Brief §5 records the remaining native-identity Stop-hook rerun and unprobed Codex subagent coverage. Inappropriate parking and rollout judgment remain open.
- 2026-09-22T02:55:34Z (main): ai-634de8 (spec section 3.4): the Stop hook is a guard, Event -> Reply, total: its own failure (tasks prime unreachable, malformed input) is a block with that reason, never a pass; reason text names the claim and the release (a park with a real next step). Recording is a separate observer subscriber.
- 2026-09-24T23:23:45Z (main): Scoped 2026-09-24: design the Stop hook on an abandoned claim (brief §4 alt 1, §5 findings) together with the turn-boundary guidance it depends on (ai-c62995 park next-step content, ai-804671 untracked background waits); one spec. Hook lands in ops hooks now, relay after ai-539508.
- 2026-09-24T23:23:50Z (main): started
  provenance: {"harness_session":"claude-code:d0b98713-18aa-4adc-b06e-bbf99d4b11c2","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-09-24T23:26:30Z (turn-boundary-gate): Spec drafted: docs/specs/2026-09-24-turn-boundary-gate-design.md (guard in ops as pure decide + shell; one-shot block, reason text carries the rules; relay entry and 14d rollout judgment as follow-ups). Awaiting user review.
- 2026-09-24T23:26:36Z (turn-boundary-gate): parked (waiting on user, review): User reviews docs/specs/2026-09-24-turn-boundary-gate-design.md (in .worktrees/turn-boundary-gate); on approval, writing-plans in that worktree, then file the ops task per spec §7
  provenance: {"harness_session":"claude-code:d0b98713-18aa-4adc-b06e-bbf99d4b11c2","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-09-24T23:43:40Z (turn-boundary-gate): Spec review 2026-09-24: three findings verified and taken. (1) prime --all-projects drops claims on worktree-only tasks (reproduced: zz-6fec1d local yes, all-projects doing:[]); (3) it skips unreachable projects with a warning and exit 0; both answered by a new tasks claims --all-projects read over the per-prefix claim store, all-or-nothing coverage. (2) Codex does not wake an idle controller (installed codex-tools guidance); running-child branch now per harness via CHILD_WAKES, default False until a controller-wake probe proves it.
- 2026-09-24T23:43:41Z (turn-boundary-gate): parked (waiting on user, review): User reviews the revised docs/specs/2026-09-24-turn-boundary-gate-design.md (in .worktrees/turn-boundary-gate); on approval, writing-plans there and file the tasks and ops pieces per §7
  provenance: {"harness_session":"claude-code:d0b98713-18aa-4adc-b06e-bbf99d4b11c2","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-09-25T00:17:00Z (turn-boundary-gate): Spec review round 2: subagent exit made conditional (report only when complete or blocked; a worker's turn end is final, never with its own check running), mirrored in the Processes rule; CHILD_WAKES flips only when both a subagent and a background-command wake probe pass.
- 2026-09-25T00:17:01Z (turn-boundary-gate): parked (waiting on user, review): User reviews round-2 edits to docs/specs/2026-09-24-turn-boundary-gate-design.md (in .worktrees/turn-boundary-gate); on approval, writing-plans there and file the tasks and ops pieces per §7
  provenance: {"harness_session":"claude-code:d0b98713-18aa-4adc-b06e-bbf99d4b11c2","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-09-25T00:44:41Z (turn-boundary-gate): resumed
  provenance: {"harness_session":"claude-code:d0b98713-18aa-4adc-b06e-bbf99d4b11c2","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-09-25T00:44:41Z (turn-boundary-gate): Plan drafted: docs/plans/2026-09-24-turn-boundary-gate.md, 11 steps (children ai-1a2741 … ai-3ce37e; ai-c62995 and ai-804671 are Tasks 6 and 7). Spec amended during planning: tasks claims always reads every prefix (--all-projects accepted as default, like quiet); timeout tested by injection; all pieces tracked as ai plan steps.
- 2026-09-25T00:44:41Z (turn-boundary-gate): parked (waiting on user, review): User reviews docs/plans/2026-09-24-turn-boundary-gate.md (in .worktrees/turn-boundary-gate) and picks subagent-driven or native execution; then start Task 1 (ops worktree)
  provenance: {"harness_session":"claude-code:d0b98713-18aa-4adc-b06e-bbf99d4b11c2","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-09-25T00:55:35Z (turn-boundary-gate): resumed
  provenance: {"harness_session":"claude-code:d0b98713-18aa-4adc-b06e-bbf99d4b11c2","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-09-25T00:55:35Z (turn-boundary-gate): Plan review round 1: four findings verified and taken. (1) wake probe now judged from transcript order with a nonce absent from the prompt, plus a known-non-wake sanity run; (2) Registry::load_from used exists(), so a permission error read as an empty registry: new Task 1 reads and fails on anything but NotFound; (3) vendor-cli overwrote destinations unchecked: Task 5 preflights every copy (HEAD or exact published bytes only); (4) ops pre-commit check-vendored blocks a worktree cli.toml edit: the row moves to ops main at landing, per bin/vendored's own rule.
- 2026-09-25T00:55:36Z (turn-boundary-gate): parked (waiting on user, review): User reviews revised docs/plans/2026-09-24-turn-boundary-gate.md (in .worktrees/turn-boundary-gate) and picks subagent-driven or native; then start Task 1 (tasks worktree)
  provenance: {"harness_session":"claude-code:d0b98713-18aa-4adc-b06e-bbf99d4b11c2","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-09-25T01:01:55Z (turn-boundary-gate): resumed
  provenance: {"harness_session":"claude-code:d0b98713-18aa-4adc-b06e-bbf99d4b11c2","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-09-25T01:01:55Z (turn-boundary-gate): Plan review round 2: wake judge false positives confirmed (Claude WAITING beside a TaskOutput call passed; Codex passed with no notification and skipped unknown inputs). Judge is now Task 10, a committed agents/bin/wake-judge with 17 tests incl. both review cases; fails closed on any unclassified input or record type; completion must be a known-form notification naming the launched child after a text-only WAITING turn end; Codex has no known form, so it cannot pass until one is added from a real rollout with a test. Probe is Task 11, follow-ups Task 12.
- 2026-09-25T01:01:55Z (turn-boundary-gate): parked (waiting on user, review): User reviews the round-2 plan revision (Task 10 wake judge) in .worktrees/turn-boundary-gate/docs/plans/2026-09-24-turn-boundary-gate.md and picks subagent-driven or native; then start Task 1 (tasks worktree)
  provenance: {"harness_session":"claude-code:d0b98713-18aa-4adc-b06e-bbf99d4b11c2","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-09-25T01:09:56Z (turn-boundary-gate): resumed
  provenance: {"harness_session":"claude-code:d0b98713-18aa-4adc-b06e-bbf99d4b11c2","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-09-25T08:28:00Z (turn-boundary-gate): parked (waiting on user, dependency): Closes with ai-3ce37e once ai lands (waiting on the europa tasks reinstall)
  provenance: {"harness_session":"claude-code:d0b98713-18aa-4adc-b06e-bbf99d4b11c2","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-09-25T10:28:39Z (main): resumed
  provenance: {"harness_session":"claude-code:d0b98713-18aa-4adc-b06e-bbf99d4b11c2","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-09-25T10:28:39Z (main): done
  provenance: {"harness_session":"claude-code:d0b98713-18aa-4adc-b06e-bbf99d4b11c2","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-09-25T10:28:39Z (main): claim-guard Stop guard live in Claude Code and Codex (ops e402b37) over tasks claims (tasks 83e3ccf); rules in AGENTS.md and flow; wake-judge in agents/bin; CHILD_WAKES claude-code True, codex False by probe
  provenance: {"harness_session":"claude-code:d0b98713-18aa-4adc-b06e-bbf99d4b11c2","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
