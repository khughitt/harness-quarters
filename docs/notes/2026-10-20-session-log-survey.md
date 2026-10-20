# What agents look for in session logs

Research for hq-de3e4c, 2026-10-20. Input to hq-c411df and the proposed `hq logs` reader; this is evidence and a recommendation, not an approved CLI specification. No tool implementation changed.

The smallest useful reader has **search and show**, backed by one discovery/parser layer. Search needs record roles and metadata filters; show needs a turn or interval with paired tool calls/results. Keep task/report tracing as an evidence-labelled composition over that reader and existing location metadata. A second session picker and a new text index are unnecessary for this sample.

## Method and limits

The inputs were the session-logs skill, the current store-reach and session-search briefs, hq-3558a1, obs-c5c599, and read-only native session stores. Thirty candidate groups formed the pilot; final noise exclusions, merges and justified splits leave **28 pilot episodes**. Seven labels were fixed before the broader classification; the trace label also retained the task's known feedback-origin case. The pilot is included in the final sample.

The final sample contains **183 episodes, 1,093 harness-visible investigation calls, and 132 source transcript files**, for call timestamps from **2026-09-01 through 2026-10-20 before 16:52 UTC**. Investigating sessions, rather than target stores, define the strata. Personal/work is inferred from the harness home, not the project's instructions or content:

| Investigating harness/home profile | Candidate groups in frame | Accepted episodes |
|---|---:|---:|
| Claude Code personal | 334 | 129 |
| Claude Code work | 17 | 14 |
| Codex personal | 81 | 40 |
| Codex work | 0 | 0 |

A structured scan followed a text prefilter over the six possible native roots: `~/.claude{,-work}/projects` and `~/.codex{,-work}/{sessions,archived_sessions}`. On titan five exist; the work Codex archive is absent. It parsed 7,648 prefilter-matching files, found 4,113 matching call records after 37 duplicate-call exclusions, and reported four malformed lines. Mechanical noise exclusions left 432 candidate groups. This broader rebuild includes native database/index references that the earlier pilot did not; its totals are not a trend against the task body's earlier 2,901/1,470 call estimates.

On europa the same read-only scan reached four roots; both Codex archive roots are absent. Eighteen matching files contained five path-reading calls, all memory-file operations, so no qualifying investigation episode was found there. Zero Codex-work entries means no matching reading call was observed in that home under this screen; it is not proof that none ever occurred.

Within each stratum, candidates were shuffled with seed `20261020`. The Claude personal order was split into halves for independent classification, screening prefixes `[0,84)` and `[167,249)`; the Codex prefix ends at zero-based position 56. All 17 Claude-work candidates were inspected. Companion groups outside those prefixes were included only to complete selected questions. Cross-half companions were assigned once, and shared call IDs were checked for duplication. Final review re-audited all 32 preliminary parent flags and each stratum’s other question summaries, recording the actual lookup direction. It also exposed one omitted supporting call in E055; adding it leaves 183 episodes and brings the final call count to 1,093. Investigators read raw intervals to recover variable-based commands, scratch-parser runs and waits missed by the path filter. Batch audits stayed one episode; distinct questions were split on explicit changes in question and disjoint calls.

This is a **stratified, bounded sample of retained evidence**, not a representative prevalence estimate. The path prefilter can miss readers using unrelated paths, indirect helpers or pruned stores. The source cohort is concentrated in tooling investigations, and the work stratum has only six candidate source sessions. Three classifier agents used one codebook; the controller reconciled overlaps, references and role labels. Counts below describe these episodes, not all agents or all sessions.


## Questions, ranked by observed frequency and cost

| Question type | Episodes | Investigation calls | Median elapsed span | Recorded tool time | Cost rank |
|---|---:|---:|---:|---:|---:|
| Record formats and parser fidelity | 64 | 372 | 58.2 s | 68.9 min | 1 |
| Reconstruct or verify what happened | 49 | 345 | 46.9 s | 50.2 min | 2 |
| Runtime identity and model attribution | 21 | 59 | 1.1 s | 0.4 min | 7 |
| Store coverage, retention and availability | 17 | 51 | 16.5 s | 5.9 min | 4 |
| Recover earlier content or a recipe | 16 | 58 | 22.0 s | 4.1 min | 5 |
| Measure patterns across sessions | 15 | 193 | 170.4 s | 25.4 min | 3 |
| Trace report/task origins | 1 | 15 | 386.5 s | 1.3 min | 6 |

These are primary question types, not parser syntaxes. Format surveys and behavior audits account for 113/183 episodes and 717/1,093 calls. The single trace episode is a batch feedback-origin audit: counting its individual reports as separate episodes would distort the ranking.

| Question type | Typical starting inputs | Historical record roles needed | Recurring obstacles |
|---|---|---|---|
| Record formats | Harness, version/era, date range, example payload | Metadata, human/assistant messages, injected/system records, calls and results | Schema drift, duplicates, encrypted dispatches, parser mistakes |
| Behavior | Refusal/error text, task, cwd, report, commit or time | Human/assistant context, calls and results, injected/system events, timestamps | Truncation, injected matches, missing records, event-order mistakes |
| Identity | Thread/session ID, reviewer text, task stamp | Native metadata, sometimes assistant text and parent links | Creation model differs from runtime model; wrapper/phase shapes differ |
| Inventory | Home/profile, host, cwd/name, archive or time bucket | Native metadata and store/index inventory | Wrong bucket, missing store, partial retention, incomplete resume evidence |
| Recovery | Remembered text, task/report, cwd/date, old artifact | Human or assistant text, commands, sometimes their results | Wrong paths, empty scans, copied history, clipped output |
| Aggregate | Date/window, project, error or tool signature | Messages, calls/results, system events and metadata | Denominator contamination, duplicate history, timeouts, repeated parser runs |
| Trace | Report/task ID, filing text, commit, session stamp | Stamps plus calls/results, human context and recorded parent links | Mentions mistaken for ownership; filing output differs from input; missing parent context |


Costs are elapsed spans between the first selected investigation call and its last recorded result. They include thinking, intervening work and parallel waits, and are neither CPU time nor billing. Tool-time sums can overlap when calls ran concurrently. Calls include relevant scratch-parser invocations and waits that omit literal store paths. The script and obstacle totals are observed lower bounds, including the two deferred annotation corrections below. Script counts cover files authored for the investigation; an inline parser is counted separately. Unknown counts stay null, rather than becoming zero.

Ranked by recorded tool time, formats come first, behavior second, and cross-session aggregates third. Aggregates have the highest multi-episode median elapsed span (170.4 seconds); identity queries usually take one call and have a 1.1-second median span. The trace batch is expensive despite appearing only once. This supports removing repeated discovery/parsing work before adding specialized analytic commands.

The sample records **at least 51 authored scratch scripts**; eight episodes have unknown script counts. It records **at least 377 inline Python/jq parser invocations**, with 35 episodes uncounted. These are known lower bounds, not invented totals. Four calls lack paired timing; 1,089 have it. A Codex exec cell may contain several shell commands, while a Claude Bash call often contains one, so call counts are harness-visible units and are not directly comparable across harnesses. A cell's recorded timing may include other bundled work or end at an initial yield.


## Roles, evidence, coverage and outcomes

**64/183 episodes (35.0%) needed historical tool outputs**. A required parent relationship was used in **18 episodes**: six child→parent only, ten parent→child only, and two in both directions. Thus **eight episodes needed reverse child→parent binding** (4.4%), and twelve needed forward parent→child binding (6.6%). Six needed both historical outputs and reverse binding; fourteen needed outputs plus either direction. These are concrete identity/evidence bindings through native session identifiers or recorded dispatch links, including SDK parent tool-use identifiers. Merely reading a child artifact, checking a parent-field shape, or observing background shell activity does not qualify. Searching only human prompts or tool inputs would lose evidence required by those questions. Of the 183 episodes, 181 require roles beyond human text. Counts of required roles are: metadata 160, tool calls 90, tool outputs 64, assistant text 56, injected/system records 40, and human text 31; roles overlap.

Evidence used is likewise nonexclusive: native metadata 149, tool-call matches 76, tool-output matches 62, system events 44, textual mentions 29, successful task commands 8, provenance stamps 7, and artifact hashes 6. Successful commands and stamps can establish a work link; a textual mention alone cannot. Outcome anchors point to the actual search result or explicit bounded conclusion, not merely the final time a search appeared.

There are **177 found, three bounded not-found, and three unknown** outcomes. No selected episode explicitly gave up or ended solely at a demonstrated wrong store. Unknown cases include a contaminated command-frequency scan, recovery of a missing original blocked command, and mixed evidence in a multi-route wake audit. The high found share is conditional on this retained, selected cohort; it is not a tool success rate. A found negative answer means the question was answered, not that the claimed behavior occurred.

Nonexclusive obstacles include metadata-shape differences (27 episodes), injected matches (26), duplicate history (16), shell errors (16), empty intermediate scans (16), truncation (14), parser errors (10), wrong paths (8), missing stores (7), timeouts (6), encrypted dispatches (3), and live appends (2). Most were recovered intermediate failures. The target stores span both Claude homes, both Codex homes and Codex archives; source profile must not be confused with the profile being searched. The archive-mirror lookup appears in the retention cohort, but general backup and cross-host resolution were not qualified here.


## Minimal verbs and result record

1. **Search:** text plus harness, home/profile, date, cwd/session and role filters. Search actual human text, assistant text, tool inputs, tool outputs and injected/system records independently. Permit an unfiltered normalized record stream within explicit bounds so schema inspection and aggregate queries can use ordinary JSON tools. Unknown record kinds remain inspectable. A human-only default cannot answer the sampled diagnostic and provenance questions.
2. **Show:** resolve a session/record reference to its surrounding turn or interval; pair tool calls with results by call ID and preserve content-block positions. Include a parent link and per-turn runtime model when recorded. Allow explicit bounded raw-record inspection for schema questions; a prose-only renderer would force the handwritten parsers to return.
3. **Trace, as a later composition:** start from a task, feedback report, commit, or recorded session ID. Return typed evidence links and their source references, including the task command's successful output when available. A mention remains a mention. Follow a child to its parent only through recorded links; encrypted/missing dispatches stay unavailable. The location-owner question remains with hq-a1c591, which this survey does not answer.

Keep `hq sessions` for choosing and resuming an interactive session. Investigation discovery must also reach children, SDK/exec sessions, both homes, archives and missing-file metadata, even when they have no interactive preview. This does not justify a separate `find` verb. The proposed spelling `hq logs grep`/`hq logs show` fits these two capabilities; the survey does not measure preferences for command names or `--pretty`.

Each content hit needs: host, harness, home/profile, session ID, parent ID when known, timestamp/turn ID, role and record kind, a source reference including JSONL line and content block, tool name/call ID and paired-result reference where applicable, runtime model when recorded, and the matched content. Parent associations need their kind and lookup direction, since a parent session pointer and an SDK parent dispatch pointer are different evidence. Trace edges add evidence kind and direction; native metadata and textual inference must remain distinguishable. A query ends with coverage: requested/searched roots, absent/unreachable/unreadable roots, malformed records, limits/truncation, duplicate handling and match counts. Empty results carry that coverage; they do not prove global absence. Fields can be null when the source does not record them.

The sample supports the brief's first-release ordering of **search + show**, its requirement to preserve outputs and parent links, and separate selection policies for resuming versus investigation. It strengthens the case for metadata/raw-record streaming: 64 format questions and 15 aggregate questions would still need handwritten parsers behind a renderer that exposes only prose. It does not establish a demand for a new `find` surface or specialized aggregate verbs.

It also leaves three hypotheses unproven: which existing component should own location lookup (hq-a1c591), whether automated trace links can meet a precision target, and what a bounded search costs in production (hq-ea0975 measures that separately). JSONL and a pretty renderer are recommendations for interoperability and inspection, not measured user preferences. No new index or cross-host service follows from these results.


## Rechecking the evidence

The dataset is [data/2026-10-20-session-log-survey.jsonl](data/2026-10-20-session-log-survey.jsonl): one classified question per line, stable `E001`–`E183` IDs, paraphrased question and outcome, trigger references, required roles, evidence kinds, failure tags, script/parser counts, costs and exact source references. `parent_link_direction` is `child_to_parent`, `parent_to_child`, `both`, `none`, or `unknown`; audited cases also carry the basis and supporting call lines. It contains no raw prompt, command, tool output, private project path, or machine-specific absolute path. `source` is a home-relative glob; resolve it beneath the named host's home. Each call, result, trigger and outcome reference includes the SHA-256 of its original JSONL line, including the trailing newline. Block indices are zero-based. These anchors survive append-only growth; deletion, compaction or a changed line must be reported as unavailable/changed.

Representative checks: E002 (Does the claim-guard judgment agree with actual blocked turns and claim releases?), E008 (Can parent dispatches and child transcripts reliably support task attribution?), E046 (Which sessions and human turns originated a batch of feedback reports?), E104 (Can the complete original blocked command be recovered?), E142 (Which background-completion paths actually wake their controllers?), E175 (What do earlier pre-push hook outputs say about local test latency?). The dataset, rather than classifier summary counters, is authoritative for all totals. Required-output flags and role lists were reconciled so current search responses are not mistaken for historical tool outputs. Investigator reports and the frozen codebook are retained locally with the task’s review evidence.


Known minor annotation omissions are deferred to **hq-edf5de**, under the review policy: E037 leaves one authored scratch parser uncounted, and E008 lacks parser-error, truncation and shell-error tags seen in its source. These affect lower-bound script/obstacle totals, not episode categories, output requirements or the corrected parent-direction counts.
