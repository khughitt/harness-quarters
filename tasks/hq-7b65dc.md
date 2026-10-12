---
id: hq-7b65dc
title: "Capability fact: Claude Code refuses a subagent Write to a report*-named file"
status: done
priority: 3
size: s
complexity: mid
process: direct
owner: subagent-write-fact
created: 2026-10-12T11:00:29Z
updated: 2026-10-12T11:39:57Z
started: 2026-10-12T11:16:05Z
completed: 2026-10-12T11:39:57Z
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
- 2026-10-12T11:24:41Z (subagent-write-fact): probe run 1 inconclusive: one subagent given all names stopped at its first refusal (the message tells it to answer in text); probe now uses one subagent per name. Run 2 on 2.1.296: outcome true; refused report.md REPORT-probe.md reports.md Summary.md findings-1.md ANALYSIS.MD sub/report.md; written task-1-report.md my-summary.md report.txt report/notes.md notes.md; main agent's main/report.md written
- 2026-10-12T11:25:44Z (subagent-write-fact): filed lore-d91181: lore's naming rule covers report only; the probed rule has four prefixes
- 2026-10-12T11:29:44Z (subagent-write-fact): review: impl round 1 — verdict: revise; findings: important 1, minor 9; reviewer: claude-code
- 2026-10-12T11:31:46Z (subagent-write-fact): probe run 3 (after review fixes) on 2.1.296: outcome true, exit 0, malformed 0, every name as predicted, control written, no session residue left under ~/.claude/projects
- 2026-10-12T11:34:24Z (subagent-write-fact): review: impl round 2 — verdict: revise; findings: important 0, minor 7; reviewer: claude-code
- 2026-10-12T11:39:09Z (subagent-write-fact): gate: verified tree:2592af78a649d9030d09f9166c80260d6ae3805d — checks: just test 693 passed; harness-facts check ok; claude/probes/subagent-write-probe.py live on Claude Code 2.1.296 outcome true exit 0 with no session residue; new probe tests each seen failing under a targeted break; review: important addressed probe counted a file on disk as written after a refused subagent write, minor addressed note overclaimed Write-only, minor addressed control never read the main agent result, minor addressed crash timeout and nonzero exit lost evidence or read as false, minor addressed null content message or input crashed classify, minor addressed host mods loaded and session dirs left under the Claude projects store, minor addressed README lacked the true false inconclusive rule, minor addressed description named a Claude tool, minor addressed pre-commit fixture hard-coded the probe list, minor addressed a main write overrode a clean subagent refusal, minor deferred session_store ignores CLAUDE_CONFIG_DIR and hashed long paths, minor deferred outcomes does not normalise relative paths, minor deferred no test drives main through a timeout or nonzero exit; reviewer: claude-code
- 2026-10-12T11:39:39Z (subagent-write-fact): gate: verified tree:2592af78a649d9030d09f9166c80260d6ae3805d — checks: just test 693 passed and harness-facts check ok and claude/probes/subagent-write-probe.py live on Claude Code 2.1.296 gave outcome true exit 0 with no session residue and each new probe test was seen failing under a targeted break; review: important addressed probe counted a file on disk as written after a refused subagent write, minor addressed note overclaimed Write-only, minor addressed control never read the main agent result, minor addressed crash timeout and nonzero exit lost evidence or read as false, minor addressed null content message or input crashed classify, minor addressed host mods loaded and session dirs left under the Claude projects store, minor addressed README lacked the true false inconclusive rule, minor addressed description named a Claude tool, minor addressed pre-commit fixture hard-coded the probe list, minor addressed a main write overrode a clean subagent refusal, minor deferred session_store ignores CLAUDE_CONFIG_DIR and hashed long paths, minor deferred outcomes does not normalise relative paths, minor deferred no test drives main through a timeout or nonzero exit; reviewer: claude-code/claude-opus-5-5
- 2026-10-12T11:39:49Z (subagent-write-fact): retro: reading the rule out of the binary before probing turned a guess (report prefix) into an exact regex and let the probe predict every name, which also exposed lore's rule as too narrow (lore-d91181). The first live run was inconclusive because the refusal text tells a subagent to stop and answer in text, so a probe that drives a model needs one attempt per subagent. The fresh review caught a false-pass path (file on disk without a successful subagent write) that the passing run could not show.
- 2026-10-12T11:39:57Z (subagent-write-fact): done
  provenance: {"harness_session":"claude-code:4eec061d-7482-4022-9ce4-5a232f7d9577","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-10-12T11:39:57Z (subagent-write-fact): subagent-write-refused fact for claude-code 2.1.296: REPORT/SUMMARY/FINDINGS/ANALYSIS prefixes on .md, case-insensitive basename, probed by claude/probes/subagent-write-probe.py; lore follow-up lore-d91181
  provenance: {"harness_session":"claude-code:4eec061d-7482-4022-9ce4-5a232f7d9577","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
