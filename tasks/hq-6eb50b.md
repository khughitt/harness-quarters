---
id: hq-6eb50b
title: "Interactive Codex sessions never deliver the claim-guard Stop block: find why and restore it"
status: dropped
priority: 1
size: s
complexity: high
process: direct
created: 2026-10-09T01:44:11Z
updated: 2026-10-09T02:15:19Z
depends: []
tags: [hooks]
source: hq-a558e8
agent: claude-code/claude-opus-5-5
---

The claim-guard rollout judgment (docs/notes/2026-10-08-claim-guard-rollout-judgment.md) found 69 root turn ends in 26 interactive Codex sessions (codex-tui, VS Code and CLI, 0.159.2 to 0.161.0, 2026-09-29 to 2026-10-09) that held a claim the session had started, inside the four-hour TTL, and not one block: the turn ended at its final answer with no continuation. Hand-traced: rollout 01a11c84… lines 652-676, tasks start obs-18b8eb at 23:10:26Z, final answer asking for acceptance at 23:11:51Z. Replaying that session's Stop input through the installed guard blocks. No rollout on this host has ever recorded a <hook_prompt> message. The only Codex blocks ever observed ran under codex exec (2026-09-25 live check on 0.156.1, recorded on hq-2f1271; the 2026-10-08 pilot on 0.161.0).

Outcome: know whether interactive Codex runs the trusted Stop hooks of ~/.codex/hooks.json at all, and whether it honours a block, then fix the wiring or record the harness limit as a capability fact (and in the guard's documented coverage). Approach: one probe in an interactive session on a scratch claim, with a hook that also records its own invocation to a file, so 'did not run' and 'ran and was ignored' separate. Verification: the probe's invocation record and the rollout, before and after any fix. The probe spends a Codex session and drives a TUI: the person runs it or approves it.

## Notes

- 2026-10-09T02:15:19Z (claim-guard-judgment): dropped
  provenance: {"harness_session":"claude-code:727f050d-a8c4-4871-8561-8f3a44e5ed7b","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-10-09T02:15:19Z (claim-guard-judgment): Premise false: review round 1 of hq-a558e8 showed the 69 held Codex turn ends were claims already released (start and park in one call); checked against the task records only one remained, a turn that ended on a server error. No evidence that interactive Codex fails to deliver the block.
  provenance: {"harness_session":"claude-code:727f050d-a8c4-4871-8561-8f3a44e5ed7b","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
