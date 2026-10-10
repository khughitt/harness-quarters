---
id: hq-47faaa
title: "Claude's /effort is session state: filter effortLevel and preserve it with live-picks"
status: doing
priority: 2
size: s
complexity: mid
process: direct
owner: main
created: 2026-10-10T14:07:56Z
updated: 2026-10-10T19:26:50Z
started: 2026-10-10T19:26:36Z
depends: []
tags: []
agent: claude-code/claude-opus-5-5
---

Why: the user ruled on 2026-10-10 that Claude's /effort is a per-session choice, not a committed default. Today effortLevel ("high" at claude/settings.json:268, unchanged since c28e2da) is tracked, so /effort shows as a diff and a checkout overwrites the live value, unlike Codex's model_reasoning_effort, which is filtered and preserved by live-picks. Found while designing hq-14d183 (docs/specs/2026-10-10-live-model-preservation-design.md §1.1, §2).

Done when:
- the harness-state clean filter drops effortLevel from claude/settings*.json (JSON_KEYS in .githooks/harness-state-clean:20), and the committed claude/settings.json no longer carries it;
- live-picks captures and restores effortLevel with the other Claude fields (.githooks/live-picks), including forget;
- .githooks/test_harness_state_clean.py and .githooks/test_live_picks.py cover it (filtered on clean; restored after a rewrite; a newer live pick is not overwritten), and just test passes;
- the spec's §1.1 table row and §2 non-goal, README.md lines 28-31 and 120, and the live-picks docstring say effort is filtered and preserved;
- rollout follows hq-a77096: the live hooks change only from main after the suite passes, and the live /effort value survives the commit that removes it from the index (check git diff and the live file before and after).

Note: with the committed value gone, a fresh home runs Claude Code's default effort until /effort is used once; the user accepted this with the ruling.

## Notes

- 2026-10-10T18:52:16Z (main): follow-up confirmed after hq-a77096 rollout: Claude model/modelSettings and Codex model/effort are preserved; Claude effortLevel remains deliberately tracked and out of scope. Keep this as the separate decision about whether /effort should be session state; no implementation implied.
- 2026-10-10T19:22:04Z (main): scope: question; body records the filter and live-picks touch points (.githooks/harness-state-clean:20, .githooks/live-picks), that effortLevel has stayed "high" since c28e2da, and the cost of filtering (fresh homes start at the default effort); one open question: is /effort a session pick or a committed default, recommendation filter it
- 2026-10-10T19:24:33Z (main): Answered 2026-10-10 (user): /effort is a per-session choice; effortLevel is not tracked.
- 2026-10-10T19:24:33Z (main): scope: scoped; rescoped after the user's answer; todo, P2, size s, complexity mid, process direct; body states the filter, live-picks, test, doc and rollout steps
- 2026-10-10T19:26:36Z (main): started
  provenance: {"harness_session":"claude-code:f931dcfe-2b47-4c43-9945-e5557533fdda","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-10-10T19:26:41Z (main): trial: flow-trial-1 — enrolled — flow on
- 2026-10-10T19:26:41Z (main): arm: flow-trial-1 — unit tack-47faaa — flow on
- 2026-10-10T19:26:50Z (main): gate: scoped — adopted
