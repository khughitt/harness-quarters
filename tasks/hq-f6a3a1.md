---
id: hq-f6a3a1
title: "parse_note, the grammar and the corpus"
status: done
priority: "2"
size: s
complexity: mid
process: direct
owner: feat/functional-core
created: 2026-09-22T10:04:33Z
updated: 2026-09-22T10:16:26Z
started: 2026-09-22T10:06:56Z
completed: 2026-09-22T10:16:26Z
depends: []
parent: hq-634de8
tags: [flow]
agent: claude-code/claude-fable-5-1
plan: docs/plans/2026-09-22-functional-core.md
step: "Task 1: `parse_note`, the grammar and the corpus"
---

Outcome: agents/flow/gate-notes.md (the grammar), agents/flow/gate-notes.jsonl (the corpus, every shape on record added), and in agents/bin/flow-state a parse_note(text) entry point returning gate / not-a-gate / malformed with the tree and, for verified notes with review:, the Verdict of Finding records; gates() re-expressed through it, malformed() beside it; Derivation untouched. Approach: plan Task 1, TDD: corpus test through parse_note first, then the implementation. Verification: uv run --with pytest pytest agents/bin/test_flow_state.py passes with every pre-existing test unchanged; grep class Derivation prints one line; the corpus covers all three kinds and all nine malformed reasons.

## Notes

- 2026-09-22T10:04:33Z (feat/functional-core): gate: scoped — step of ai-634de8 plan
- 2026-09-22T10:06:56Z (feat/functional-core): started
  provenance: {"harness_session":"claude-code:036c5f2f-1ba8-4479-a39b-a87a8310cbac","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-09-22T10:07:13Z (feat/functional-core): gate: implementing .worktrees/functional-core
- 2026-09-22T10:09:34Z (feat/functional-core): corpus sweep: 38 distinct gate notes across 2165 records; one malformed on record — obs-03e018 (done) 'gate: verified tree:f5eaf94' (7-char commit hash), later reopened and re-verified with a 40-hex tree, so Task 2's reduction supersedes it (JSON diagnostic only, rendering stays closed). Appended it and the tree-less reopen shape to the corpus; no literal review: field exists on record yet.
- 2026-09-22T10:16:17Z (feat/functional-core): gate: verified tree:4b0a28870b6a382974a264277849e3394ea477a7 — uv run --with pytest pytest agents/bin/test_flow_state.py -q: 102 passed (60 pre-existing unchanged, 38 corpus cases, 4 unit); grep class Derivation prints one line; fresh-context review (sonnet) of the diff at tree a5906962: approve with fixes, 4 minors all addressed at this tree (empty state names <none>; tree: token anchored at a word boundary so worktree: is free text; grammar says lowercase hex; any reviewer label may carry a session, pinned by a corpus line)
- 2026-09-22T10:16:17Z (feat/functional-core): retro: writing the grammar and corpus before the parser made the reviewer's job a grammar-vs-code diff, which is where all four findings came from; the on-record sweep was worth it — it found the one real malformed note (obs-03e018) that Task 2's supersession rule was designed for. Hurt: I wrote a gate: implementing on the parent by reflex; parents derive that state.
- 2026-09-22T10:16:26Z (feat/functional-core): done
  provenance: {"harness_session":"claude-code:036c5f2f-1ba8-4479-a39b-a87a8310cbac","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-09-22T10:16:26Z (feat/functional-core): parse_note classifies every note as gate, not-a-gate or malformed against agents/flow/gate-notes.md; 38-line corpus is the test fixture; gates() re-expressed, malformed() added, Gate carries a Verdict of Finding records
  provenance: {"harness_session":"claude-code:036c5f2f-1ba8-4479-a39b-a87a8310cbac","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
