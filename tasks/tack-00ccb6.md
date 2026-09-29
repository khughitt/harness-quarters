---
id: tack-00ccb6
title: Controller-wake probe and CHILD_WAKES
status: done
priority: "2"
size: m
complexity: mid
process: direct
owner: turn-boundary-gate
created: 2026-09-25T00:44:16Z
updated: 2026-09-25T02:36:07Z
started: 2026-09-25T02:13:20Z
completed: 2026-09-25T02:36:07Z
depends: [tack-52f641]
parent: tack-21ea5d
tags: [hooks]
model: claude-opus-5-5
agent: claude-code/claude-opus-5-5
plan: docs/plans/2026-09-24-turn-boundary-gate.md
step: "Task 11: Controller-wake probe and `CHILD_WAKES`"
---

## Notes

- 2026-09-25T02:13:20Z (turn-boundary-gate): started
  provenance: {"harness_session":"claude-code:d0b98713-18aa-4adc-b06e-bbf99d4b11c2","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-09-25T02:21:12Z (turn-boundary-gate): wake probe claude-code subagent: PASS after a Step 2 extension (the first judge run failed on record type 'last-prompt'). Inspected: ai-title, atis-latch, mode, permission-mode, last-prompt are session metadata; queue-operation only enqueued <task-notification> or dequeued empty; attachments were 15 harness-context subtypes. Extended narrowly (queue-operation only empty or notification; attachment only the seen subtypes), 3 tests, 31 pass. Transcript: turn ended WAITING, notification naming the Agent tool_use, WAITING again, completion notification, reply = nonce 3fcbfba717ed01ba, one human prompt.
- 2026-09-25T02:24:37Z (turn-boundary-gate): wake probe claude-code background: PASS (launch Bash run_in_background, notification naming its tool_use id, controller read the output file and replied with nonce 0b3010a02d0fce2b; one human prompt).
- 2026-09-25T02:28:17Z (turn-boundary-gate): wake judge sanity control claude-code (second human prompt typed mid-run): FAIL: unclassified input: 'Did the subagent report?' — as required.
- 2026-09-25T02:31:45Z (turn-boundary-gate): wake probe codex subagent (codex-cli 0.156.1, gpt-5.6-sol TUI): FAIL, no wake — spawn_agent launched /root/read_nonce, turn ended WAITING, task_complete, then nothing within 170 s (no notification, no second turn). Judge stopped earlier on unknown record type 'world_state'; not extended, since the transcript cannot pass either way.
- 2026-09-25T02:35:08Z (turn-boundary-gate): wake probe codex background: FAIL, no wake — exec_command ran the sleep, turn ended WAITING, task_complete, no second turn within 170 s. Codex sanity control skipped (no Codex PASS to protect). Outcome: CHILD_WAKES claude-code True (both runs PASS), codex False (both FAIL).
- 2026-09-25T02:36:07Z (turn-boundary-gate): done
  provenance: {"harness_session":"claude-code:d0b98713-18aa-4adc-b06e-bbf99d4b11c2","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-09-25T02:36:07Z (turn-boundary-gate): Wake probes: Claude Code woke for subagent and background command (judge PASS, control FAIL); Codex for neither; ops 72b9cc3 sets CHILD_WAKES claude-code True; judge learned Claude session metadata forms (c02422d)
  provenance: {"harness_session":"claude-code:d0b98713-18aa-4adc-b06e-bbf99d4b11c2","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
