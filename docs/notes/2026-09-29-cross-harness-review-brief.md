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
- Same-family baseline: tack-b2291c (feedback from lit) — in lit-a7b4ec, a
  Codex session's fresh-context reviewer subagent (`review_safe_yaml`,
  gpt-6-sol, `fork_turns: none`) caught YAML acceptance changes that a
  371-test gate passed. A fresh reviewer from the same family already finds
  real problems; tack-fc26cf measures what a second family adds on top.
- Unknown: the mindful source thoughts (48e70c65…, 34328bb6…) are not found by
  the current `mindful` CLI; the task bodies carry their content.

### 2.1 Measurement (tack-fc26cf, 2026-10-02)

Seven trees, each reviewed once by `claude -p` (claude-opus-5-5, effort high)
and once by `codex exec` (gpt-6.1-sol, reasoning high) with one shared prompt:
review `git diff base...HEAD` against the task record, report material
problems as `[severity] path:line — problem — evidence`, or `No findings.`
Every finding was triaged against the code at HEAD, mostly by reproduction, as
real, false, or out of diff.

Method notes:
- tack's history was squashed on 2026-09-29. The four Claude trees were
  recovered from unreachable objects; each recorded `tree:` equals the landing
  commit's tree minus `tasks/` and `docs/{specs,plans}`.
- A recorded Claude review saw a pre-fix tree that was never committed, and
  its findings were fixed before the verified tree. So the same-family
  baseline on every tree is a fresh review of the same final tree, and the
  recorded findings serve only to check overlap. None of the 8 real findings
  from the fresh Claude reviews was among them.
- The triage was done by Claude subagents. Each verdict rests on a quoted
  line or a reproduction, but a judge from one family is a residual bias.
- Reviewers checked claims against the host's current tools. Two Claude
  findings that held only against today's `tasks` CLI or registry are
  counted as false.

| Tree (implementer) | Claude: findings / real | Codex: findings / real | Both | Only Claude | Only Codex |
|---|---|---|---|---|---|
| tack-2ce119 (Claude) | 3 / 2 | 0 / 0 | 0 | 2 | 0 |
| tack-99ea5d (Claude) | 3 / 3 | 0 / 0 | 0 | 3 | 0 |
| tack-bdff6f (Claude) | 3 / 1 | 2 / 2 | 1 | 0 | 1 |
| tack-634de8 (Claude) | 3 / 2 | 1 / 1 | 1 | 1 | 0 |
| tasks-2578c3 (Codex) | 2 / 1 | 0 / 0 | 0 | 1 | 0 |
| obs-2cf65e (Codex) | 5 / 5¹ | 3 / 3 | 1 | 4 | 2 |
| ops-7e210f (Codex) | 5 / 4 | 3 / 3 | 1² | 3 | 2 |
| **Total** | **24 / 18** | **9 / 9** | **4** | **14** | **5** |

¹ One partly real. ² Same check, different bypass.

Per direction (new-real: real findings the same-family reviewer did not
report):

- **Claude → Codex** (Codex reviewing Claude-implemented work): 1 new-real
  finding in 4 reviews (0.25 per review). It is
  `agents/bin/retros:183`: when every project is unreachable, the error does
  not name them. Codex missed 6 of the 8 problems the fresh Claude review
  found. Two of its four reviews returned `No findings.` on trees where Claude
  found 3 and 2 real minor problems.
- **Codex → Claude** (Claude reviewing Codex-implemented work): 8 new-real
  findings in 3 reviews (2.7 per review):
  - tasks `README.md:440`: `list --parked` titles are not colored.
  - obs `join.py:155`: an ambiguous close is lost.
  - obs `stores.py:155`: a non-object listing aborts the run.
  - obs `stores.py:185`: diagnostics are discarded (partly real).
  - obs `tests/test_stores.py:153`: the harness path is never exercised.
  - ops `bin/relay-guard-probe:222`: `passed` is stricter than the plan.
  - ops `bin/relay-guard-probe:245`: `redact` misses quoted paths.
  - ops `tests/test_relay_guard_probe.py`: 17 of the plan's 34 tests are
    missing, and two mutations survive. Important.

  Claude missed 4 of the 6 problems the fresh Codex review found, including
  the two important ones:
  - obs `join.py:190`: `child_count` is always 0, because a test invented the
    field.
  - ops `bin/relay-guard-probe:213`: the nested gate passes on a marker the
    plain shell made.
- **By reviewer, whoever implemented:**

  | Reviewer | Findings | Real (precision) | Seen only by this reviewer | Important (by triage) |
  |---|---|---|---|---|
  | Claude | 24 | 18 (75%) | 14 | 1 |
  | Codex | 9 | 9 (100%) | 5 | 2 |

  In shape, Claude measured the change against its plan and documents and ran
  mutations. Codex built adversarial inputs against the logic and checked the
  real CLI's output format. Both labelled minor edge cases important.
- The direction asymmetry is mostly reviewer volume, not who implemented: on
  all seven trees Claude reported at least as many findings as Codex. The two
  reviews overlapped on 4 problems out of 23 distinct real ones. On every tree
  at least one reviewer found a real problem the other missed. Both did so on
  2 trees (obs, ops), Claude alone on 4, and Codex alone on 1 (tack-bdff6f).
- No same-family repeat was run. The table cannot separate "another family"
  from "another independent review". The fresh Claude reviews finding 8 real
  problems that the recorded Claude reviews missed suggests a second review
  from either family adds findings.
- Cost and time per review:
  - Claude: $0.50–1.09 ($4.79 for 7), 95–197 s.
  - Codex: 127–301 s, 0.31–0.90 M input tokens (mostly cached), 1.9–4.8 k
    output tokens.

Invocations that worked, both with stdin from `/dev/null`:

- **Codex.** `codex exec -s read-only --json -o <file> "<prompt>"`. The
  session id is `thread_id` in the first `--json` event (`thread.started`).
  `codex review --base <branch>` also ran, but it refuses a custom prompt (it
  takes one only without `--base`/`--commit`). It prints `session id:` on
  stderr.
- **Claude.** `claude -p "<prompt>" --model <id> --effort high
  --output-format json --permission-mode bypassPermissions
  --disallowedTools Edit Write NotebookEdit`. `session_id` and
  `total_cost_usd` are in the JSON result.

Both reviewers ran in a scratch `git clone --shared -n` checked out at the
head, with a `base` branch at the range's start. No bridge or wrapper was
needed.

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
   ceremony. **Recommended** after tack-fc26cf (§2.1):
   - Both directions worked first time with one command each, and both
     expose the session id.
   - The only trap was `codex review --base` refusing a custom prompt, and
     one sentence in a recipe covers it.
   - Nothing a CLI would normalize (alternative 2) proved error-prone.
   - No one-hop review needed a live session (alternative 3).
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
  per review, by direction; bring the question back with that table. Now in
  §2.1:
  - **Rates.** Codex reviewing Claude's work finds 0.25 new-real per review;
    Claude reviewing Codex's work finds 2.7.
  - **Overlap.** The two reviews overlap on only 4 of 23 real problems.
  - **Caveat.** No same-family repeat was run, so part of the gain may come
    from any second independent review.
  - **Cost.** Under $1.10 or about 5 minutes per review.
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
