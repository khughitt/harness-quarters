---
id: tack-e3cef2
title: "Find when Codex multi-agent V2 evicts finished children at the thread limit, and set the local remedy"
status: doing
priority: 2
size: s
complexity: mid
process: direct
owner: main
created: 2026-09-27T14:55:57Z
updated: 2026-09-30T14:09:45Z
started: 2026-09-30T14:09:45Z
depends: []
tags: [feedback, friction, "from:beliefs"]
agent: codex
---

Why: the vendored superpowers v6.4.1 reference (agents/vendor/superpowers/skills/using-superpowers/references/codex-tools.md, Lifecycle bullet) says V2 has no close_agent and finished children are evicted automatically when slots are needed. In practice spawn_agent returns 'collab spawn failed: agent thread limit reached' in 8 Codex sessions from 0.154.0 to 0.158.0 across tasks, beliefs, mindful, niri-material and tack (grep of ~/.codex/sessions/2026/09). In the reported beliefs session (rollout-2026-09-27T09-34-42-01a0e313…, 0.157.1, V2 tools: followup_task, no close_agent) one finished reviewer was evicted for the fourth spawn, then the fifth was refused while list_agents showed /root and one reviewer running and two completed. Reusing a completed reviewer with followup_task worked. The reference is upstream text: tack overrides, never edits, the submodule. ~/.codex/config.toml is tack's codex/config.toml and has no [agents] section; features list shows multi_agent true, multi_agent_v2 false (the preset selects V2).

Question: Under what condition does V2 evict a finished child (never, only after its result was read by wait_agent, only past some age), what is the thread limit and does [agents] max_threads change it, on the installed codex-cli 0.159.0?

Where to start: the beliefs rollout above and the other seven sessions (grep 'agent thread limit reached'); codex exec in a scratch directory with --ephemeral, spawning trivial fork_turns:none children and calling list_agents between spawns, with and without wait_agent reading each result, then with -c agents.max_threads=<n>.

Bound: one scratch probe, a handful of trivial children per case; no edits to the vendored submodule; filing upstream is the user's call, not part of this task.

Expected result: the observed eviction rule and limit recorded here, and one local remedy landed: an [agents] max_threads value in codex/config.toml, or one Codex line in AGENTS.md (reuse a completed child with followup_task before spawning a new one when the limit is hit), whichever the probe supports. Also a draft upstream issue (text only, in the task note) for the user to decide on. Done when a fresh codex exec spawn sequence that hit the limit before no longer fails, or the AGENTS.md line is in place and the probe shows why config cannot help.

## Original report

The Codex skill reference says finished agents are evicted when slots are needed, but spawn_agent refused a fresh reviewer with 'agent thread limit reached' while completed agents remained; reusing a completed reviewer worked. (feedback, friction, from beliefs)

## Notes

- 2026-09-29T20:58:14Z (main): scope: scoped; confirmed recurring (8 sessions, 5 projects, 0.154–0.158) against the vendored superpowers codex-tools.md Lifecycle claim; rewritten as a bounded eviction probe on 0.159 with a local remedy (config or AGENTS.md line) and a draft upstream issue for the user; todo P2 s/mid/direct
- 2026-09-30T14:09:45Z (main): started
  provenance: {"harness_session":"claude-code:2f6c453d-6dcd-4c66-8605-2a894929ca8c","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
