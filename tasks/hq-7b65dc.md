---
id: hq-7b65dc
title: "Capability fact: Claude Code refuses a subagent Write to a report*-named file"
status: doing
priority: 3
size: s
complexity: mid
process: direct
owner: subagent-write-fact
created: 2026-10-12T11:00:29Z
updated: 2026-10-12T11:24:41Z
started: 2026-10-12T11:16:05Z
depends: []
tags: []
source: lore-5501d5
agent: claude-code/claude-opus-5-5
---

Claude Code refuses a subagent's Write when the basename starts with `report` (`report.md`, `report-*.md`) with "Subagents should return findings as text, not write report files." `<slug>-report.md` names (SDD's `task-N-report.md`) are accepted. Local logs on 2026-10-12: 6 refusals, about 500 accepted writes. Record it in facts/capabilities.toml with a probe that confirms the basename rule (prefix only vs any 'report' token) on the current version. lore's Processes fragment now carries the naming rule (lore-5501d5).

## Notes

- 2026-10-12T11:16:05Z (main): started
  provenance: {"harness_session":"claude-code:4eec061d-7482-4022-9ce4-5a232f7d9577","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-10-12T11:16:11Z (main): trial: flow-trial-1 — enrolled — flow on
- 2026-10-12T11:16:11Z (main): arm: flow-trial-1 — unit tack-7b65dc — flow on
- 2026-10-12T11:19:28Z (main): gate: scoped — adopted
- 2026-10-12T11:19:28Z (main): binary 2.1.296: Write validateInput refuses when agentId is set and the basename matches /^(REPORT|SUMMARY|FINDINGS|ANALYSIS).*\.md$/i (event tengu_subagent_md_report_blocked, errorCode 5); wider than the task assumed
- 2026-10-12T11:19:29Z (subagent-write-fact): resumed
  provenance: {"harness_session":"claude-code:4eec061d-7482-4022-9ce4-5a232f7d9577","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-10-12T11:19:29Z (subagent-write-fact): gate: implementing .worktrees/subagent-write-fact
- 2026-10-12T11:24:41Z (subagent-write-fact): attached: subagent-write-probe-2026-10-12.jsonl (204270 bytes): stream-json transcript of the passing probe run on Claude Code 2.1.296
