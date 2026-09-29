# Cross-harness review ("friends") brief

Ideas: tack-fc26cf (one-hop Codex review), tack-dd66c1 (friends bridge),
tack-91e028 (super friends pairwise flow). Goal: see the goal whose source is
this file.

## 1. Problem

An agent working in one harness should be able to ask a different model family
for a review, and later a task, without knowing how that harness is driven. The
premise behind all three ideas is that a second family catches problems a fresh
copy of the same model does not. Nothing on record tests that premise, and two
of the three ideas are built on it.

## 2. Current behaviour and evidence

- Every structured `gate: verified` reviewer in tack is Claude Code: 7 labels
  (`claude-code/claude-opus-5-5[1m]` ×5, `claude-code/claude-opus-5` ×2), plus
  one `check`. Across all tracked projects the recorded reviewer labels are
  claude-code (7), `no` (2) and `check` (1): no Codex reviewer on record.
- Cross-family review does happen ad hoc: several obs and ops tasks cite
  "conversation 2026-09-27: steering and harness-model discussion (claude +
  codex review)" as their source. Those reviews left no findings comparison.
- The flow skill's verified gate already has the seam: `reviewer:
  <harness/model>` plus an optional `session:<harness:id>` for a reviewer in its
  own session, naming "a Codex thread, a cross-harness review"
  (`agents/skills/flow/SKILL.md`, functional-core spec §4.2,
  flow-state-machine spec §5).
- Headless invocation already works in both directions:
  - Claude → Codex: codex-cli 0.159.0 has `codex review [--base <branch> |
    --commit <sha> | --uncommitted] [prompt]` and `codex exec -s read-only
    -o <file> --json --output-schema <file>`. tack-deb3e4 found `codex exec`
    waits on a non-tty stdin unless given `< /dev/null`.
  - Codex → Claude: tack-2f1271 drove `claude -p --settings …` for live Stop
    checks.
- Codex does much of the implementation work: done tasks whose provenance
  notes carry a `codex:` harness session number about 150 across projects
  (ops 30, prism 27, beliefs 17, familiar 15, obs 14, niri-material 14, …;
  tack 3, of which tack-bc49ed is the one sizable tree). None of them has a
  recorded reviewer, so the reverse direction has no baseline to replay.
- Positive signal, not cross-family: tack-b2291c (feedback from lit) — an
  independent parser review caught loader acceptance differences that passing
  fixtures missed. Its reviewer family is unknown.
- Unknown: the mindful source thoughts (48e70c65…, 34328bb6…) are not found by
  the current `mindful` CLI; the task bodies carry their content.

## 3. Constraints

- relay owns harness adapters and hook dispatch to non-Claude harnesses;
  a bridge that drives another harness is adjacent to its charter, not tack's.
- Codex subagent claims are broken until tasks-0c2c39 (`sid:<pid>`, dead at
  once); relay-c85a0f reports conflicting `CODEX_SESSION_ID`/`CODEX_THREAD_ID`.
  A bridge that claims tasks inherits both.
- The human stays at the spec and plan gates (tack-91e028 note); a pairwise
  flow may not remove them.
- Flow's reviewer field is metadata and does not substantiate independence
  until obs can join `session:` to an observed session (functional-core §4.2).
- Vendored superpowers skills are upstream; local changes go in tack's own
  skills or wrappers.

## 4. Alternatives

1. **No bridge: a documented recipe.** One paragraph in the flow skill's
   verified step (and the review-request skill it points to) giving the
   headless command for both directions (Claude → Codex and Codex → Claude), the output file in the worktree, and how to
   read the reviewer's session id. Cheapest; costs each agent a few lines of
   ceremony. **Current lean**, pending tack-fc26cf.
2. **A thin `friend` CLI** in `agents/bin`: `friend review --harness codex
   --base main --out <file>` normalizes the invocation, captures the session id
   for `session:`, and returns findings in the gate's review grammar. Worth it
   only if tack-fc26cf shows the recipe is error-prone or used often.
3. **A relay-owned dispatch or MCP bridge** that lets a live session message a
   live session in another harness. Needed for tack-91e028's multi-round pair;
   not for one-hop review.

## 5. Unanswered questions

- Does a Codex review find material problems a Claude subagent review missed
  on the same tree, and at what false-positive rate? — tack-fc26cf.
- Can the reviewer's thread id be read from `codex review` output, or only from
  `codex exec --json`? — tack-fc26cf, by running it.
- Settled 2026-09-29 (user): both directions are in scope. tack-fc26cf
  measures Codex → Claude as well as Claude → Codex, and any recipe or bridge
  serves both.
- Should the verified gate *require* a cross-family reviewer for some process
  or complexity, given the extra quota each review spends? — the user, who is
  undecided (2026-09-29). The input it needs is tack-fc26cf's new-real rate
  per review, by direction; bring the question back with that table.
- If a bridge is earned (alternative 2 or 3), does it live in tack or relay? —
  the user, undecided (2026-09-29). Moot under alternative 1; revisit only if
  tack-dd66c1 chooses 2 or 3.

## 6. Proposed decomposition

| Task | What | Waiting ideas |
|---|---|---|
| tack-fc26cf | scoped: replay Codex review on 3–4 trees a Claude subagent already reviewed, and review 3 Codex-implemented trees with both a fresh Codex and a `claude -p` reviewer; compare findings | tack-dd66c1, tack-91e028 |
| tack-dd66c1 | idea: choose alternative 1, 2 or 3 from the tack-fc26cf result | tack-91e028 |
| tack-91e028 | shelved until a bridge exists and cross-family review has shown value | — |

No design task yet: whether one is needed is the tack-fc26cf outcome.
