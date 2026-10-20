# Can the obs index locate the audited report origins?

Research for hq-a1c591, 2026-10-20. Input to hq-c411df; no production code, index or harness store changed.

**Use the existing obs index for local location metadata, with an explicit file-level result and coverage.** It found the correct readable transcript for all 20 sampled audit origins and the correct parent for all six sampled Codex children. A reader must still inspect transcript content to anchor a report on a filing output or recover human context. This supports alternative 4 of the [store-reach brief](2026-10-20-session-store-reach-brief.md), using alternative 2's existing metadata rather than building another index.

## Method and bound

The original feedback-origin audit is Claude Code session `737a5757-83af-4e31-9fdd-4ce70dd9e6f1`; its method is attached to tasks-fa3525. Its retained inventory has 72 reports, 71 anchored origins and 68 distinct origin files. The audit's `origin.line` is zero-based in both locator scripts; the cases published here convert it to a one-based physical JSONL line. Its stored subagent booleans do not identify native Codex children, so selection uses each rollout's first `session_meta` instead.

The sample is purposive: include all six native child origins and the one work-home origin, then eight Claude origins in report-ID order, then fill to 20 distinct files with Codex top-level origins in report-ID order. This yields eight Claude personal, six Codex personal children, five Codex personal top-level and one Codex work top-level. It is a coverage probe, not a population estimate.

The audit contains no origin in `archived_sessions` and no origin whose source is now missing. Consequently **A01 and M01 are separate store-state controls**, selected by the lowest matching indexed file ID. They are not two more audited origins. A01 checks a natively archived Codex rollout; M01 checks an unavailable Claude file with retained index metadata. Neither qualifies replayed backup retrieval.

Queries used a SQLite backup-API snapshot taken **19:17:38–19:18:06 UTC**, opened read-only. It contains schema 15, 25,086 file rows and 26,537 session rows. The latest complete index run ended **19:02:27 UTC**. The source checkout was obs commit `6c81c8056aa00ecaf796226e3d056d7e946a1b72`, with no working changes. No indexing or replay command ran. Europa was checked only for an index at its configured `$XDG_STATE_HOME/obs/index.sqlite` (default `~/.local/state/obs/index.sqlite`): none existed. Other remote paths and stores were not searched.

## Results

| Need | Observed result | Remaining boundary |
|---|---|---|
| Known session ID → source | All 20 correct source files are among the ID query's results; all are readable. Every filing call also has an indexed `tool_calls` row. | An ID can return several files; do not silently select the first. |
| Codex child → parent | All six `sessions.parent_session` values equal the child's native spawn parent. These six links resolve to five distinct readable parents whose first native IDs agree. | This proves recorded identity and location, not recovery of encrypted or missing dispatch content. |
| Beyond the baseline reader's default roots | O02 resolves the work Codex origin. A01 resolves a readable native Codex archive. Snapshot rows also include the work Claude root. | No audited Claude-work or native-archive origin was available in this cohort. |
| Pruned/missing source | M01 resolves an absent file with retained metadata and non-null `missing_since_ms`, alongside a readable alternate file for the same ID. There are 739 missing rows. | Availability is per file. A missing mark neither makes the whole session unavailable nor locates a backup copy. |
| Replayed archive copy | Schema 15 supports `files.read_path`; the implemented replay route is documented and had prior acceptance evidence. | **Zero snapshot rows have `read_path`.** Replayed-copy retrieval was not observed here. |
| Report/task → filing output | The raw paired result for O13, an audit `created-output` anchor, contains the report ID. The index has its call ID and size/timing metadata. | The index does not store arbitrary input/output text or a feedback-filing edge. All 20 anchors have zero matching `task_commands` rows for the report. |
| Other host | Europa has no index at its configured state path. | Local absence cannot establish cross-host absence. |

The snapshot has 6,232 Claude-personal file rows (669 marked missing), 935 Claude-work (70 missing), 16,640 Codex-personal live-store rows, 594 Codex-personal native-archive rows and 685 Codex-work live-store rows. No row belongs to the work Codex archive. These are indexed file counts, not counts of unique conversations or proof that every current file was indexed.

O10 demonstrates why `(harness, session_id)` is not a unique file locator: the query returns the Claude root transcript plus three native subagent files. **All four matching rows have `subagent = 0` and `parent_session = NULL`.** Each child file also contains a separate, correctly classified `agent-…` row with its parent ID and actual activity. The matching parent-ID rows in those files have zero human turns, assistant messages and tool calls. Thus a session-row flag is not a classification of the entire file. The native `isSidechain` records and `/subagents/` path identify these child files; the query's flags do not. `live_sessions` filters rows marked as subagents and retains all four matching parent-ID rows here. The correct root was checked against the audit's source reference; this evaluation oracle is not a general disambiguation algorithm. Preserve file candidates and inspect their native identity and session rows before attributing work. This location-interface gap is filed as obs-b99310.

M01 makes the same point for missing state: its ID query returns two files. The selected file is absent and marked missing; the alternate is readable. Report those facts per candidate instead of turning the missing mark into session-wide unavailability. Redacting the project-directory name also makes its source glob match that alternate. The case ledger therefore adds `source_path_sha256`, the SHA-256 of the exact home-relative path string encoded as UTF-8, to distinguish candidate identities without publishing the private directory name. It is separate from the content hashes.

For all 20 origin files, the current bytes through `files.byte_offset` hash to the snapshot's `span_sha256`, with `span_stable = 1`. Each recorded filing call and paired result also has a physical-line hash. This establishes that the inspected evidence agrees with the indexed prefix; it does not establish global freshness or complete retention. Two paired outputs do not mention the assigned report ID, so those pairs are not promoted to successful-creation evidence. Their audit input anchors and location checks remain distinct.

## Queries and interpretation

The location probe uses the persistent tables, without report views that exclude subagents. Both values are bound parameters:

```sql
SELECT s.file_id, s.harness, s.session_id, s.parent_session,
       s.subagent, s.superseded_by,
       f.path, f.read_path, f.missing_since_ms,
       f.indexed_at_ms, f.indexed_schema, f.byte_offset,
       f.span_sha256, f.span_stable
FROM sessions AS s JOIN files AS f USING (file_id)
WHERE s.harness = ? AND s.session_id = ?
ORDER BY f.file_id;
```

Apply the same query to a recorded `parent_session` with its harness. Retain every candidate and check its native identity and readability. A populated `read_path` denotes replay's reading source while `path` retains logical identity; it is not a guarantee that either file still exists. In this snapshot it is always null. A zero-row query means not indexed in this snapshot, not that the session never existed.

The coverage checks include:

```sql
SELECT harness, COUNT(*), SUM(missing_since_ms IS NOT NULL),
       SUM(read_path IS NOT NULL)
FROM files GROUP BY harness;

SELECT COUNT(*) FROM task_commands
WHERE file_id = ? AND call_id = ? AND task_id = ?;
```

The second query is deliberately a negative check. `task_commands` extracts lifecycle operations (`start`, `park`, `done`, `drop`), not feedback creation. `tool_calls` stores identifiers, bytes and outcomes, not general command/result content. `task_mentions` links task-record fields, not transcript ownership. These tables cannot replace searching a transcript's outputs, and a textual mention must remain weaker than a verified work link.

## Recommendation and evidence

Keep the proposed **search + show** reader and usage skill. Use obs's existing index as a source of local session/file/parent/missing metadata, with a supported read interface to be settled in hq-c411df. Carry the original file identity, reading source, candidate ambiguity and coverage into results. Keep content matching, call/result pairing and parent-context reading as explicit reader operations. No new text index or standalone `find` surface is justified by this probe.

The accepted ownership work, ops-630a87 and obs-f5710b, assigns content parsing to obs and location/lifecycle and harness-version store samples to hq. The CLI design must respect that boundary and the migration's trial gate; this research neither changes the parser owner nor executes the deferred transfer. Recommend a local query with explicit unavailable/not-indexed state first. Automatic cross-host access and backup materialization remain separate design decisions; this sample supplies no evidence that they are required for the audited origins.

The [case ledger](data/2026-10-20-session-index-reach.jsonl) has O01–O20 plus the explicitly separate A01/M01 controls. It contains home-relative source globs, file/call IDs, native/index parent IDs, hashes and result flags; no raw prompt, command, result text or private project path. Claude project-directory names are wildcarded; filter glob candidates by `source_path_sha256` to identify the exact path. Content hashes cover original JSONL lines including their trailing newline. Local query scripts, snapshot provenance and review reports are retained with the task evidence; the disposable index copy is not a repository artifact.

Two Minor wording corrections in the brief are deferred to hq-edf5de under the review policy: its summary's “six parents” means six links to five distinct parents, and its survey paragraph's “still investigates” should describe this completed research. The detailed results and ledger here use the verified counts and status.
