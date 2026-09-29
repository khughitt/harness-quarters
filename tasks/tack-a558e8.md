---
id: tack-a558e8
title: "Rollout judgment for claim-guard: sort Stop blocks by what the blocked turn did"
status: todo
priority: "2"
size: s
complexity: mid
process: direct
defer: 2026-10-09
created: 2026-09-25T02:36:07Z
updated: 2026-09-25T02:36:07Z
depends: []
parent: tack-756baa
tags: [flow, obs]
source: ai-21ea5d
agent: claude-code/claude-opus-5-5
---

Spec §6: read Stop blocks ('Stop hook feedback:' user records in Claude Code; <hook_prompt hook_run_id="stop:…"> user messages in Codex) from session logs with session-logs, classify each as resumed work, park with an action, vacuous park, bounded wait, report-and-end, or bare end on retry; decide whether the reason text or ai-c62995's rule needs work. First evidence already on ai-2f1271: a haiku controller parked with 'ready for next steps' despite the reason text.
