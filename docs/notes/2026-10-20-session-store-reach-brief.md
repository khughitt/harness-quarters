# Session store reach — brief

Goal: hq-cff824. Reader design: hq-c411df. Scoped 2026-10-20; updated 2026-10-22
with completed studies, acceptance cases and the obs root-location fix.

## 1. Problem

Agents need to recover a report's origin, an earlier human turn, a reviewer's runtime
model, or the calls and results behind a claim. The current session-logs skill and
`session-episodes` reader cover only part of the retained evidence. Missing matches
need coverage and availability information so an agent can distinguish an unsuccessful
search from an unavailable source.

## 2. Current behaviour and evidence

| Reader | Discovery today |
|---|---|
| `agents/bin/session-episodes` `_roots` | Default Claude projects and Codex sessions; one override per harness |
| `tools/hq_cli/sessions.py` `homes()` | Four personal/work harness homes; selection suited to interactive resume |
| `tools/session_archive/config.py` `sources()` | Five fixed capture roots; no Codex-work native archive |
| obs `stores.py` `store_roots` | Six personal/work live and native-archive roots |

The local code still has these separate discovery lists. No reader design or
implementation plan is attached to hq-c411df.

- **Completed survey, hq-de3e4c (686e160).** The
  [survey](2026-10-20-session-log-survey.md) and its
  [episode ledger](data/2026-10-20-session-log-survey.jsonl) cover 183 investigation
  episodes and 1,093 calls: 129 Claude personal, 14 Claude work and 40 Codex personal.
  Formats (64 episodes), behavior (49), identity (21), inventory (17), recovery (16),
  aggregates (15) and one batch trace motivate search + show. Historical outputs were
  required in 64 episodes; 18 needed relationships: eight child-to-parent, twelve
  parent-to-child, with two using both. Formats, behavior and aggregates cost most
  in recorded tool time. At least 51 scratch scripts and 377 inline parsers were
  observed. Outcomes were 177 found, three bounded not-found and three unknown.
  These describe a bounded retained sample, not prevalence or a tool success rate.
- **Completed location probe, hq-a1c591 (228f751).** The
  [report](2026-10-20-session-index-reach.md) and
  [case ledger](data/2026-10-20-session-index-reach.jsonl) locate 20 sampled origins
  and six Codex child links to five parents using existing obs metadata. Output
  anchoring still needs transcript content. The snapshot had 739 missing files and
  no populated `read_path`: replayed-copy retrieval was unobserved. Native archive
  A01 and missing-file M01 were separate controls, not audited-origin successes.
  M01 also has a readable alternate for the same session ID. Europa had no index at
  its configured path; this does not establish cross-host absence.
- **Root-row defect resolved, hq-1adbfe / obs-b99310.** Probe case O10 historically
  returned a root and three child files with phantom parent-ID rows. obs fix
  `54ce9e187b825dc7ace6ff23ba9820e172b1f89c` routes child `agentId` request records
  without `isSidechain` to the child. Its 2026-10-20 completion records renewal of
  6,432 Claude files and zero non-subagent rows in child paths, previously 150.
  This resolves that defect; alternate files and per-file availability still matter.
- **Portable checks exist, hq-6e5d88 (03af2f4).** Ten
  [acceptance cases](session-log-acceptance-cases.md), fixtures under
  `tools/fixtures/session-logs/` and `tools/test_session_log_cases.py` cover all seven
  question types. Fidelity corrections remain open in hq-c1fecb.
- The original 72-report audit needed output anchoring for nine reports and parent
  context for six. Codex native spawn metadata records the parent; creation-model
  provenance can differ from the runtime model in `turn_context`. The model-route
  addition remains hq-7b131a. hq-be3f69 already demonstrated recovery of an earlier
  human turn through the skill, using a handwritten Codex parser.
- **Final-message retrieval gap, hq-b95324 (code checked at b5cacb9).**
  `session-episodes show` prints a "last assistant" message only after looking up an
  extracted episode/candidate ID. Its CLI has extract/show/confirm/label, with no
  query for turn-final messages by session, task or time window. `_evidence` already
  uses `turn_after` and the shared parser, so reuse the reader's turn/role evidence
  rather than introducing another handwritten JSONL scan. Existing episode evidence
  is narrower than general final-message retrieval; this gap is not already delivered.

## 3. Constraints

Stores remain read-only; checks use temporary or sanitized fixtures. Keep interactive
resume selection separate from investigation selection, which must include children
and non-interactive sessions. The session-search lane hq-65f661 rules out another
transcript index. hq-a60cf5 independently aligns baseline extraction roots.

Accepted boundary work ops-630a87 / obs-f5710b assigns content parsing and
session-logs to obs, and location/lifecycle plus harness-version samples to hq.
Its transfer waits until after flow-trial-1 readout; assess effects on enrolled
sessions and measurement explicitly. Planning does not authorize that transfer.
The probe's SQL is research evidence, not an approved consumer API.

Keep deferred annotation/wording corrections in hq-edf5de and fixture corrections in
hq-c1fecb. tasks-516ab4 may add reporting-session stamps; older reports still require
content/output anchoring. obs-c5c599 covers report-to-session tracing, hq-ea0975
measures search cost, and hq-fce47e / lore-f71994 address a session's own model stamp.

## 4. Alternatives

- **Location only (original alternatives 1–2):** grow an hq locator or expose obs
  lookup metadata and document it. This can resolve IDs and parents but leaves the
  survey's content, output-pairing and format questions to handwritten parsers.
- **Guidance only (original alternative 3):** document every store and parent/model
  field. Small, but repeats the manual parsing and cannot itself report coverage.
- **Search + show and a usage skill (original alternative 4, the user's proposal):**
  use existing location metadata and the accepted shared parsing boundary. Lean here;
  reject another picker or index. Keep trace as a later typed-evidence composition.

First-release design inputs: metadata and role filters; bounded normalized/raw records;
call/result pairing by ID; line and content-block references; recorded parent links
and per-turn runtime model; and per-run searched, missing, unreadable, malformed and
truncated coverage. A mention is weaker than a successful task command or provenance
stamp. JSONL with a pretty renderer is a recommendation, not a surveyed preference.
For hq-b95324, express listing and printing turn-final assistant messages through
the same search/show design, with session, task and time-window selection. Prefer
that to a separate final-message verb or another parser; command syntax remains a
design decision.

## 5. Unanswered questions

- **hq-c411df's design:** what supported obs interface exposes candidate identity,
  read paths, parents and missing state while preserving the ownership boundary?
- **hq-c411df's design:** settle command/output contracts and the staged rollout
  around the trial gate. Automatic remote access and backup materialization remain
  explicit decisions; lean toward local lookup with explicit unavailable/not-indexed
  results first. The studies did not qualify general replay or remote retrieval.
- **Reader acceptance work:** incorporate hq-c1fecb's fidelity corrections and the
  location controls. Automated trace precision and production search costs remain
  unmeasured; no precision claim follows from this sample.
- **hq-c411df's design, from hq-b95324:** define a final message across Claude and
  Codex, including commentary, injected records, interrupted/incomplete turns and
  turns with no final response. Define task selection's evidence (recorded ownership
  versus textual mentions), preserve source references, and map a focused acceptance
  case to the chosen contract. Existing "last assistant" output alone does not settle
  those semantics. No new research is justified before the design traces this code.
- **Other owners:** tasks decides tasks-516ab4. A potential relay thread-model query
  remains an unfiled option; relay's own-session resolver is not that interface.

## 6. Proposed decomposition

- **hq-c411df:** scope the existing idea as the high-complexity, planned design task.
  Both research inputs are complete. Produce reviewed design and implementation plan
  with acceptance mapping and rollout gates before implementation; reuse this record,
  not another design task. Keep it under hq-cff824.
- **hq-b95324:** keep this idea briefed under hq-cff824, depending on hq-c411df's
  reviewed design and plan. Its design handoff includes final-message selection and
  the acceptance question above. On completion, hq-c411df records the result with
  `tasks note hq-b95324 --no-reviewed` before its branch merges; then re-scope the
  idea against the reviewed contract instead of creating a parallel CLI effort.
- **hq-1adbfe:** propose drop as a delivered positive result of obs-b99310; preserve
  its source body and dated verification. No new research waits on it.
- **hq-a60cf5 / hq-7b131a:** existing independent root-alignment and model-route work;
  the shared reader can later replace duplicated discovery through the chosen interface.
- **hq-c1fecb / hq-edf5de:** existing fixture and annotation corrections; retain them.
- **hq-a1c591 / hq-de3e4c / hq-6e5d88:** completed evidence and acceptance inputs,
  not new research. hq-be3f69 remains the previously dropped positive example.

hq-1639fd concerns retention of linked Claude units, rather than reader behavior.
It was considered as related context in this pass and remains untouched for retention
scoping under the archive effort.
