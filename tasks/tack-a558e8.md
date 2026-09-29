---
id: tack-a558e8
title: "Rollout judgment for claim-guard: sort Stop blocks by what the blocked turn did"
status: todo
priority: 2
size: s
complexity: mid
process: direct
defer: 2026-10-09
created: 2026-09-25T02:36:07Z
updated: 2026-09-29T13:04:29Z
depends: []
parent: tack-756baa
tags: [flow, obs]
source: ai-21ea5d
agent: claude-code/claude-opus-5-5
---

Spec §6: read Stop blocks ('Stop hook feedback:' user records in Claude Code; <hook_prompt hook_run_id="stop:…"> user messages in Codex) from session logs with session-logs, classify each as resumed work, park with an action, vacuous park, bounded wait, report-and-end, or bare end on retry; decide whether the reason text or ai-c62995's rule needs work. First evidence already on ai-2f1271: a haiku controller parked with 'ready for next steps' despite the reason text.

## Notes

- 2026-09-29T13:04:29Z (main): attached: stops.py (5562 bytes): Reads every Claude Code transcript since SINCE, writes stops.json (one row per turn end: blocked or not, what the blocked turn did, its tokens) and prints the block rate by day, the responses and the guard's duration
- 2026-09-29T13:04:29Z (main): attached: after.py (4245 bytes): Reads stops.json: what followed each reply-only block (a child's completion notice, a person, the session's end), the extra round's latency, blocks per session and per project
- 2026-09-29T13:04:29Z (main): attached: share.py (2422 bytes): Reads stops.json: reply length before and after a date (FIX), and the reply-only rounds as a share of main-thread requests and tokens
- 2026-09-29T13:04:29Z (main): A first count ran early, on 2026-09-29 (ops-552425, spec section 6), and the guard changed on it the same day (ops-ed76fe): a stop is allowed while the Stop input lists a running shell or subagent. This judgment now measures the changed guard. Expect the block rate on Claude Code to fall from 34 percent of turn ends to a few percent; sort what remains by reason variant (no child running, or the guard could not look and why), since a rise in the second means a Claude Code release changed the Stop input. Also find one block inside a live session and what the turn did: the 2026-09-29 live check covered the allow only. The three attached scripts produced the first count; set SINCE to 2026-09-29T13:00 to measure the changed guard. obs-c29a58 would replace them with a report if it lands first.
