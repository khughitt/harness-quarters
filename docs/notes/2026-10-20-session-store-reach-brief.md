# Session store reach — brief

Ideas: hq-c411df (origin sessions outside the default stores), hq-7b131a (a Codex
subagent's runtime model), hq-be3f69 (positive: recovering an earlier human turn).
Goal: hq-cff824. Scoped 2026-10-20.

## 1. Problem

Scope and audit agents read session logs to recover evidence: the session a feedback
report came from, the human turn behind a requirement, the model that ran a review.
The session-logs skill and its reader, `session-episodes`, reach part of what is stored.
When the evidence lives elsewhere, the agent gets no result and no explicit
"unavailable", or records the wrong model.

## 2. Current behaviour and evidence

- **Store lists differ by reader.** Each tool keeps its own list:

  | Reader | Roots |
  |---|---|
  | `agents/bin/session-episodes` `_roots` | `~/.claude/projects`, `~/.codex/sessions`; one path per `SESSION_LOGS_CLAUDE` / `SESSION_LOGS_CODEX` |
  | `tools/hq_cli/sessions.py` `homes()` | the four homes (`.claude`, `.claude-work`, `.codex`, `.codex-work`), from metadata (`history.jsonl`, `state_5.sqlite`) |
  | `tools/session_archive/config.py` `sources()` | five: both Claude `projects`, `.codex/sessions`, `.codex/archived_sessions`, `.codex-work/sessions` |
  | obs `stores.py` `store_roots` | six: both Claude `projects`, `sessions` and `archived_sessions` under both Codex homes (obs-0d1d99, done) |

  On this host, `~/.codex/archived_sessions` holds 594 rollouts and
  `~/.codex-work/archived_sessions` does not exist.
- **obs already holds most of a locate route.** Its index keeps `sessions.session_id`,
  `sessions.parent_session`, `files.path`, `files.read_path` (an unpacked archive,
  obs-de84cb, done) and `files.missing_since_ms`. No obs command exposes "where is
  session X", and the index is per host.
- **Location probe (hq-a1c591, completed 2026-10-20).** A read-only snapshot located
  all 20 sampled audited origins, including the work Codex origin, and all six native
  Codex parents. One Claude session ID returned a root plus three child files: retain
  file identity and ambiguity. All four matching rows have `subagent = 0`; native
  records and the child files' separate agent rows reveal the distinction, so that
  query's flags alone cannot identify the root (obs-b99310). Separate controls located a readable native Codex
  archive and an absent Claude file with an explicit missing mark; that session ID
  also has a readable alternate, so availability must stay per file. The snapshot has
  739 missing files and zero populated `read_path` values, so replayed-copy retrieval
  was not observed. Europa had no index at its configured state path. See the
  [probe report](2026-10-20-session-index-reach.md) for queries, hashes and limits.
- **The audit (hq-c411df note, 2026-10-20).** Locating the origins of 72 feedback reports
  needed: anchoring on a CLI call's output when the command text differs from the stored
  record (9 of 72); following a Codex subagent to its parent thread, whose dispatch brief
  is `encrypted_content` (6 of 72); and searching the work homes and `archived_sessions`.
  Every origin found was on this host; europa held none.
- **Child to parent is in the rollout.** A Codex child's `session_meta.payload.source`
  is `{"subagent": {"thread_spawn": {"parent_thread_id": …}}}`.
- **Codex model fields diverge.** `session_meta`'s `base_instructions.provenance.model` is
  the model at creation, which for a child is the parent's. The last
  `turn_context.payload.model` is the model that ran; children cannot switch model
  (hq-1bd166; lore `docs/notes/2026-10-02-codex-model-identity-brief.md` §5–§6). Of the
  400 most recent October rollouts on this host, 176 had the two differ (for example
  child `01a140a1…`: created under gpt-6.1-sol, ran gpt-6-luna).
  `relay model --harness codex` resolves only the calling session's own thread
  (relay `docs/api.md`, "Codex model resolution").
- **What already works (hq-be3f69).** Origin: Codex session `01a153c4…` (a learn-rust
  plan execution, 2026-10-19), filing call at rollout line 589. Task 1 asked for "eight
  prior review findings" that the plan did not include. The controller read this skill,
  listed that day's Codex rollouts whose `session_meta.cwd` matched, printed their human
  turns, and copied the user's revision report (session `01a1535d…`, line 184) into its
  plan workspace. It took under a minute and no question to the user. The skill's turn
  recipe is Claude-only, so all three reads were hand-written Codex scripts. That did not
  slow it here, but a Codex turn recipe would make the same route shorter.

## 3. Constraints

- Session stores are read-only inputs; tests and probes use temporary stores (AGENTS.md).
- tasks-516ab4 (idea) would stamp feedback with the reporting session, as lifecycle notes
  already are. Once it lands, new reports need id lookup, not text anchoring.
- obs-c5c599 (idea) proposes a report-to-session-to-task trace over obs's index.
- The session-search lane (hq-65f661) rules out a new transcript index.
- hq-fce47e and lore-f71994 cover a Codex session's *own* model stamp and reviewer
  identity, not a controller naming its child's model.

## 4. Alternatives

1. **hq's reader grows a locate command.** `session-episodes` (or `hq sessions`) gains
   `locate <session-id>` over all six roots plus the session-archive mirror, with child
   to parent and an explicit `unavailable` listing the stores it searched. This adds a
   fifth store list unless it imports one.
2. **obs answers locate queries.** A read-only obs query (session id to path or
   `read_path`, parent, missing state) serves both the scope agent and obs-c5c599's
   trace. The session-logs skill documents that query. hq keeps `session-episodes` as
   the baseline extractor and only aligns its roots.
3. **Document only.** The skill lists every store and the child-to-parent field, and
   agents search by hand. This costs nothing, but it gives no explicit unavailable
   result and repeats the audit's manual work.

4. **An `hq logs` reader and usage skill (the user's proposal, 2026-10-20).** One CLI
   over every store answers the common questions, for example `hq logs --harness codex
   --profile work --start-date 2026-10-14 <text>` and `hq trace --task-id <id>`, and the
   skill teaches question-to-command recipes in place of the hand-written parsers.
   A pilot found about 1,470 store-reading tool calls since September, 472 of them
   Python parsers written on the spot (hq-de3e4c). Design inputs from review, which the
   survey confirms or overturns:
   - **Release order.** First release `grep` and `show` plus the metadata filters they
     need. Add `find` only if it differs from `hq sessions`; add `trace` once the
     survey settles its evidence rules.
   - **`trace` names its evidence.** A task id in a session does not mean the session
     worked on it. Each link carries its kind and reference: provenance stamp,
     successful task command, tool-output match, or textual mention. It searches
     tool outputs as well as inputs. Child-to-parent links come from recorded metadata
     (Codex `session_meta.payload.source.subagent.thread_spawn.parent_thread_id`).
   - **Share discovery and parsing, not selection.** `tools/hq_cli/sessions.py` lists
     only Codex threads with a preview and excludes non-interactive sessions, which is
     right for resuming and would hide the subagents an investigation needs. Each
     consumer applies its own selection. "No new index" does not rule out the existing
     obs index (hq-a1c591).
   - **Result contract before verbs.** JSONL with `--pretty`. Each hit carries a
     reference to its content block, not only its line, because one Claude record can
     hold several tool calls (275 of 24,919 recent records). It also carries the tool
     name and call id, so `show` pairs a call with its output, and the runtime model of
     its turn. Every run reports coverage and truncation (stores searched, unavailable,
     unreadable), so "nothing found" can be interpreted.

Recommendation after hq-a1c591: 4, using 2's existing local location metadata. The
index covers the 20 known-origin ID lookups and six parent links, but feedback-output
anchoring still needs transcript content. No new index follows. A supported read
interface must preserve file candidates, subagents, missing state and coverage; the
research SQL is not an approved API. The accepted boundary work (ops-630a87,
obs-f5710b) assigns content parsing to obs and location/lifecycle plus harness-version
store samples to hq. The CLI design must respect that boundary and the transfer's
trial gate rather than create another parser.
hq-a60cf5 stays independent: it fixes a silent coverage gap in obs's baseline input now,
and when the shared reader lands, it replaces `session-episodes`' root list with an
import. The model route stays a skill addition (hq-7b131a), later a field of `show`.

## 5. Unanswered questions

- **Answered locally by hq-a1c591:** known-origin and parent location are covered in
  the bounded sample; content/output anchoring remains a reader operation. Missing
  state is observable, but no replayed-copy locator was populated in this snapshot.
  The audit had no archived/pruned origin; separate controls do not establish those
  cases as audited-origin successes.
- Should locate span hosts (run on each host over ssh), or report "not on this host"?
  Recommend local lookup with explicit unavailable/not-indexed state first: the audit
  found no origin on europa and no index exists there at its configured state path.
  Automatic remote access and backup materialization remain decisions for the design.
- Will tasks-516ab4 land? If so, CLI-output anchoring matters only for older reports.
  The tasks owner decides.
- Should relay offer `relay model --thread <id>` for controllers, as a verified
  alternative to the skill's recipe? relay's owner decides; this is not filed.

## 6. Proposed decomposition

- hq-cff824: goal for this cluster.
- hq-a1c591 (research, completed): [index coverage probe](2026-10-20-session-index-reach.md),
  20 readable origins and six matching parent links; separate archive/missing controls
  and an explicit replay-coverage limit. hq-c411df can incorporate both research results.
- hq-de3e4c (research, added 2026-10-20): survey what agents look for in session logs,
  to set the verbs of a proposed `hq logs` / `hq trace` CLI and its usage skill (the
  user's proposal, §4 alternative 4). hq-c411df waits on it too, and its locate-owner
  choice becomes part of that CLI's design.
- hq-a60cf5: `session-episodes extract` reads every store obs indexes. Kept
  independent (§4); the shared reader later replaces its root list.
- hq-7b131a (scoped): the session-logs skill names the route to a Codex session's or
  subagent's runtime model.
- hq-be3f69: dropped 2026-10-20 after checking its origin session; recorded in §2 as what
  already works.

## 7. Session-log question survey — hq-de3e4c, 2026-10-20

The [completed survey](2026-10-20-session-log-survey.md) classifies **183 episodes**
from both harnesses and both home profiles: 129 Claude personal, 14 Claude work,
40 Codex personal; no matching Codex-work investigation was observed. Europa was
reachable but yielded only memory-file operations. The unit is a question, including
its repeated parser attempts; batch audits remain one episode. These are sample
counts, not population prevalence.

| Question | Episodes | Investigation calls |
|---|---:|---:|
| Record formats/parser fidelity | 64 | 372 |
| Reconstruct/verify behavior | 49 | 345 |
| Runtime identity/model | 21 | 59 |
| Store coverage/retention | 17 | 51 |
| Recover earlier content/recipe | 16 | 58 |
| Aggregate patterns | 15 | 193 |
| Trace report/task origins | 1 batch | 15 |

Historical tool **outputs were required in 64 episodes**. Required parent
relationships appear in 18: six child→parent only, ten parent→child only, two both.
Eight episodes therefore need reverse child→parent binding, twelve forward
parent→child binding; six need both outputs and reverse binding (fourteen outputs
and either direction). Field-shape inspection and background shell activity do not
count as relationship traversal. Provenance and successful task commands remain distinct from
mere mentions. Outcomes: 177 found, three bounded not-found, three unknown.
The cost ranking by recorded tool time is formats, behavior, aggregates, inventory,
recovery, trace, identity. At least 51 scratch scripts and 377 inline parser
invocations were observed; unknown counts and timing limits remain explicit.

This supports §4 alternative 4's **search + show first**, including metadata filters,
all record roles, paired tool results, block-level references and per-run coverage.
A bounded normalized/raw-record stream is needed for the 64 format and 15 aggregate
questions. It does not justify a new `find` command beside the existing session
picker. `trace` should compose typed evidence links over the reader and the location
metadata whose ownership hq-a1c591 still investigates. Its automated precision and
production search costs remain unmeasured. JSONL/pretty output is a design
recommendation, not an observed preference. No tool code changed.

Two Minor annotation corrections (one scratch script and three failure tags) are
deferred to hq-edf5de; script and obstacle counts remain lower bounds.

The [episode ledger](data/2026-10-20-session-log-survey.jsonl) preserves paraphrases,
line/block/call references, line hashes, costs and conservative outcome labels.
hq-a1c591 now supplies the other research input; hq-c411df can incorporate both results.
