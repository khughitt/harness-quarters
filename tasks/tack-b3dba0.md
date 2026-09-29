---
id: tack-b3dba0
title: "Reviewer brief at the verified gate: trace the hardest assertions, probe lifecycle and failure paths; prove new tests fail without the fix"
status: done
priority: "2"
size: xs
complexity: low
process: direct
owner: main
created: 2026-09-24T14:36:14Z
updated: 2026-09-24T15:01:19Z
started: 2026-09-24T14:54:20Z
completed: 2026-09-24T15:01:19Z
depends: []
tags: [flow]
source: ai-c78706
model: "claude-opus-5-5[1m]"
agent: "claude-code/claude-opus-5-5[1m]"
---

Why: five retros (ai-dc5380, ai-c6086b, ai-bdff6f, obs-03e018 twice) say the review found what tests missed only when the reviewer was asked to do more than read the diff; the ai-99ea5d review (2026-09-24) confirms it — pointed at raw transcripts rather than the implementer's summary, it caught a wrong task id and a section cited before it existed. Done: agents/skills/flow/SKILL.md, at implementing -> verified, says what the dispatch brief asks of the reviewer: check claims against the raw evidence (source, transcript, record), not the implementer's summary; hand-trace the hardest assertions; try file-lifecycle and failure-path cases (delete, rename, missing input) on anything that touches files or hooks. The implementer, before dispatch, breaks the fix once and confirms each new test fails (a mutation check). Where: the implementing -> verified row and the paragraph after the table; keep it to two or three sentences. Check: the skill text names all four asks; a fresh-session read of the row reproduces them. Lands with ai-492c56 and ai-2ce119 in one edit if taken together. Source: retro curation pass ai-c78706.

## Notes

- 2026-09-24T14:50:06Z (main): scope: scoped; body rewritten to the flow-skill edit, todo P2 xs low direct; associated with goal ai-756baa's retro curation through ai-c78706, not parented (its goal holds the hook and listing follow-ons only)
- 2026-09-24T14:54:20Z (main): started
  provenance: {"harness_session":"claude-code:a326cf7b-df61-4526-b766-65c25ebbbbde","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-09-24T14:54:27Z (feat/flow-promotions): gate: scoped — adopted
- 2026-09-24T14:54:27Z (feat/flow-promotions): gate: implementing — worktree .worktrees/flow-promotions (feat/flow-promotions), landing with the other three retro promotions
- 2026-09-24T14:55:02Z (feat/flow-promotions): The flow spec (4.1) keeps review method out of the skill and names gate criteria only; the reviewer asks are phrased as what the judge column requires, and the spec's 3.2 table and 3.3 and 3.5 are updated to match.
- 2026-09-24T14:58:19Z (feat/flow-promotions): Correction to the body: the obs-03e018 retros credit an independent permission review, not a reviewer asked to do more than read the diff; the support is ai-dc5380, ai-c6086b and ai-bdff6f. Review round 1: the reviewer-brief paragraph was method and is gone; its asks are now the judge criterion (raw evidence, hand trace, delete and rename cases), and the path rule moved to Where the record lives. missing-input dropped: no retro names it.
- 2026-09-24T15:01:07Z (feat/flow-promotions): gate: verified tree:e90a6fca17648a0041164c866d8ebba42ddc163c — checks: pytest agents/bin 382 passed and tasks check clean and skill row read against spec 3.2 row; review: important addressed brief paragraph was review method and not in the spec, important addressed undo-the-fix check passed trivially, minor addressed missing-input had no retro, minor addressed failure paths dropped in round 1, minor addressed spec judge cell lost the raw-evidence contrast, minor addressed 4.1 amendment overstated criteria-not-method; reviewer: claude-code/claude-opus-5-5[1m]
- 2026-09-24T15:01:18Z (feat/flow-promotions): retro: the first draft broke the spec's own rule (criteria not method) and neither of us saw it until a reviewer pointed at 4.1; reading the spec section that governs the file before editing it would have saved a round. The brief pointing the reviewer at raw retros rather than task bodies found two overstated claims in my own scoping.
- 2026-09-24T15:01:19Z (feat/flow-promotions): done
  provenance: {"harness_session":"claude-code:a326cf7b-df61-4526-b766-65c25ebbbbde","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-09-24T15:01:19Z (feat/flow-promotions): flow skill and spec carry the promotion from the ai-c78706 retro pass
  provenance: {"harness_session":"claude-code:a326cf7b-df61-4526-b766-65c25ebbbbde","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
