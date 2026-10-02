---
id: tack-fc26cf
title: "Measure whether a review from the other model family finds problems a same-family review missed, in both directions"
status: doing
priority: 2
size: l
complexity: mid
process: direct
owner: main
created: 2026-09-15T01:01:58Z
updated: 2026-10-02T07:56:05Z
started: 2026-10-02T07:56:05Z
depends: []
parent: tack-67d253
tags: [flow, skills]
source: "mindful:thought:48e70c654fd84c6ab72d3f06b6261683"
agent: claude-code/claude-opus-5
---

Why: tack-dd66c1 (friends bridge) and tack-91e028 (pairwise flow) both rest on the claim that a different model family catches different problems. Nothing on record tests it: every structured verified-gate reviewer across the tracked projects is claude-code, and the ad hoc 'claude + codex review' conversations left no comparison. Both directions are in scope (user, 2026-09-29). codex-cli 0.159 ships `codex review --commit/--base` and `codex exec -s read-only -o <file>`; `claude -p` drives Claude headlessly (tack-2f1271). No bridge is needed. Brief: docs/notes/2026-09-29-cross-harness-review-brief.md.

Question: On the same tree, does a reviewer from the other model family find material problems a same-family reviewer did not, and which same-family findings does it miss? Answer separately for Claude → Codex and Codex → Claude.

Where to start:
- Claude-implemented, Claude-reviewed (baseline already recorded): tack-2ce119, tack-99ea5d, tack-bdff6f, tack-634de8 (their `gate: verified tree:<f>` notes; `~/.agents/bin/flow-state <id>`). Map each tree to its commit with `git log --all --format='%H %T'` and run `codex review --commit <sha>` (or `--base` over the task's range) in a scratch worktree at that commit, stdin from /dev/null (tack-deb3e4: codex exec waits on a non-tty stdin).
- Codex-implemented, no reviewer on record: tack-bc49ed, plus two sizable done tasks from ops or obs whose provenance notes carry a `codex:` harness_session. Run both a fresh `codex review` (same-family baseline) and a `claude -p` review with the same instructions over the same range.
Write every review's output to a file in its scratch worktree.

Bound: 3–4 trees per direction; no wrapper script, no skill or AGENTS.md edits. Triage each finding against the diff as new-real, duplicate, or false. Record quota or wall time per review.

Expected result: a per-tree table (same-family findings, cross-family findings, overlap, new-real, false) and a per-direction summary, the invocations that worked, and whether each reviewer's session id was obtainable for a `session:` label; recorded as a note here and in the brief's §2, with a recommendation between the brief's alternatives 1–3 in §4 and the new-real rate per review the brief's gate-requirement question needs. Done when every new-real finding cites a file:line in the reviewed diff.

Ideas it wakes: On completion, run tasks note on tack-dd66c1 and tack-91e028 with the finding, in the same commit as this result.

## Original idea

Smallest super-friends experiment, no bridge: Claude writes a plan, Codex is launched non-interactively to review it and write findings to a file in the worktree, Claude incorporates them (receiving-code-review discipline). Tests whether a second model family finds different problems before any transport is built. Related: ai-91e028.

## Notes

- 2026-09-16T15:57:35Z (main): Related: ai-dd66c1 (friends bridge) names this one-hop file exchange as the candidate first step; filed from mindful:thought:34328bb6f74e4517bb0c5a2569ade36b.
- 2026-09-29T20:39:10Z (main): scope: scoped; retitled to the outcome, body rewritten as a bounded replay of Codex review over four Claude-reviewed trees, todo P2 m/mid/direct, parented under tack-67d253; brief: docs/notes/2026-09-29-cross-harness-review-brief.md
- 2026-09-29T20:47:27Z (main): Scope widened 2026-09-29 by the user's answer: both directions (Codex → Claude too). Added a Codex-implemented leg (tack-bc49ed plus two ops/obs trees, fresh Codex and claude -p reviews on each); size m → l. Gate-requirement and tack-vs-relay questions stay with the user, undecided; this task's table is the input for the first.
- 2026-10-02T07:56:05Z (main): started
  provenance: {"harness_session":"claude-code:9184bb38-6b6b-4acf-a3f3-bd4f5a329f4f","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
