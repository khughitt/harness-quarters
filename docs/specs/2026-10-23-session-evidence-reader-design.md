# Session evidence reader: `session-logs search` and `show`

Status: draft for review, revision 7, 2026-10-26. Revision 5 was approved at ae0f8ee;
Stage A was built against that revision and plan 1fea7bf, and merged into obs at 062b73e.
This amendment records its implementation rulings and measured limits. It changes no
reader, classifier, skill, roots, links or trial measurement; §11's gates still apply.
- **Revision 1** (ce66d61) went through a fresh-context agent review: one critical finding,
  12 important and 14 minor.
- **Revision 2** (c21021e) addressed them. Its largest change is D6: the task is no longer
  moved to obs. Its re-review found 5 important findings and 12 minor.
- **Revision 3** (504e72e) addressed those. Claude turns now end at Claude's own turn-end
  records. Codex inter-agent reports are no longer dispatches. `not_found` is bounded by
  the index's coverage start. The obs README waits for Stage B. Its re-review found 5
  important findings and 10 minor.
- **Revision 4** (87b7fcb) addressed those:
  - mid-turn `isMeta` records no longer split Claude turns;
  - failed task commands require a command chain whose failure is certain;
  - the coverage start's live values and drift are stated;
  - scoped `not_found` needs a candidate and the task's start;
  - Codex fork history ends by `turn_id`.

  The user's review of it (round 4, reviewer `codex/gpt-6.1-sol`) found 4 important
  findings.
- **Revision 5** addresses those:
  - the raw-byte prefilter is gone, and unparsed lines are matched through their escapes;
  - only a single `tasks` segment's error is evidence that the command did not succeed;
  - a fork whose parent is unavailable is ambiguous to its end, and ambiguous turns have no
    final;
  - a Codex turn needs its `task_complete` to be `completed`.
- **Revision 6** (hq-28baf9) reconciles Stage A's ledger and live findings:
  - name/identity mismatches and index rows outside the configured roots are explicit;
  - coverage records unread aliases, matches hidden in collapsed copies, copy-group
    sorting, bounded mention scans and cuts around a record target;
  - response-only turns, abort reasons and bounded command fields are specified;
  - resume timing and mid-parent fork histories no longer depend on misleading wording;
  - the native fork ordinal is measured but not adopted, and the observed unmapped Codex
    kinds remain explicitly `unknown` (§8.2, §8.3, §14.7).
- **Revision 7** corrects revision 6's independent review (e8ff370): task evidence and
  mentions share the selected file order, R19's filename/identity protection is scoped
  to Codex, and a `turn_cut` report can accompany a view with no omitted objects.

Task: hq-28baf9 (amendment); hq-c411df (original design); goal hq-cff824.
Inputs: the store-reach brief (`docs/notes/2026-10-20-session-store-reach-brief.md`), the
session-log survey (`docs/notes/2026-10-20-session-log-survey.md`, hq-de3e4c), the index
reach probe (`docs/notes/2026-10-20-session-index-reach.md`, hq-a1c591), the acceptance
cases (`docs/notes/session-log-acceptance-cases.md`, hq-6e5d88), and the accepted
boundary proposal of ops-630a87 (revision 4, change 5 and Phase A steps 9–10).

## 1. Purpose

Agents read session stores to answer seven kinds of question: record formats, what
happened, which model ran, where a session is stored, earlier content, patterns across
sessions, and where a report came from (survey, "Questions"). The reader they have today,
`session-episodes`, covers two of the six stores and one of those questions. The rest are
answered with handwritten parsers: at least 51 scratch scripts and 377 inline parsers in
the surveyed sample. When a search finds nothing, they get no statement of what was
searched. That missing statement is the original report's gap: an origin in another home,
an archived rollout or a pruned file gave no result and no unavailable status.

This spec defines one read-only reader with two verbs:

- `search` selects records, turns or sessions.
- `show` prints one turn, line range or session, with its paired calls, links and models.

Every run ends with a coverage object, which says what was searched and whether an empty
answer means anything. The spec also defines:

- the reader's ownership and its interface to obs's index;
- the usage skill's contract;
- a staged rollout that leaves flow-trial-1's treatment and measurement unchanged until
  readout;
- the mapping onto the ten acceptance cases, plus one new case for turn-final messages
  (hq-b95324).

## 2. Decisions

Each decision gives the choice, the alternative rejected, and why.

**D1. obs hosts the reader; hq supplies home roots, lifecycle and fixtures.** The reader
is a new obs entry point, `session_logs.py`. It is installed later as `session-logs`
(§11.3).
- **Reasons.** The accepted boundary gives obs content parsing and the index. It gives hq
  location (home roots) and lifecycle (archive, prune, replay). A reader in obs uses the
  index's own root list (`stores.store_roots`) and its own read-only index helpers. It
  adds no fifth root list, which the brief rejected, and no second consumer of obs's SQL
  schema.
- **Rejected: an hq-hosted `hq logs`**, the user's 2026-10-20 spelling, moved to obs later.
  It would add a fourth copy of the human-or-injected rules in the owner the boundary moves
  them away from. It would also need obs's schema or a new obs export just to locate files.
  It would then move once more.
- **Candidate contract.** obs-b99310 left the file-candidate contract to hq. This spec is
  hq's statement of that contract (§5.2). obs implements it, next to the index rows it
  reads.

**D2. Two verbs, writing the `session-logs/1` JSONL stream; no other surfaces.**
- **Shape.** `search` and `show`. Each writes one JSON object per line: a record, turn,
  session or unparsed line. Every run ends with one coverage object. `--pretty` renders the
  same objects for a person.
- **Rejected:** a `find` or `locate` verb, a picker, aggregate verbs and a trace verb.
  - Locating is `show <session>` and `search --sessions`.
  - Aggregates are ordinary `jq` over records (SL6).
  - Trace is a later composition over this output (§13).

  The survey found no demand for the others. A stream suits the bounded unfiltered record
  stream that schema and aggregate questions need (survey, "Minimal verbs"). It is a
  recommendation, not a measured preference.
- **Shared CLI conventions.** The reader is an agent tool reached through `~/.agents/bin`,
  like `session-episodes` and `trial-arm`. It is not a command of the obs CLI, so it is
  outside the shared CLI table (ops `cli.toml`). It still follows that table's rules where
  they apply:
  - help on stdout;
  - exit codes 0, 1 and 2, with the error object on stderr (§6.6);
  - the vocabulary's option names and value grammars: `--limit/-n` takes a positive
    integer, `--sort`/`--reverse` set order, and `--since`/`--until` take `when`.

  Three options are the reader's own, outside the vocabulary: `--no-limit`, `--all-time`
  and `--state-dir`.

  There is no `--json`. Its vocabulary meaning is exactly one JSON value, and the reader
  always writes the stream.

  When the reader becomes a command of the obs CLI, it joins the table as a protocol row
  naming `session-logs/1`.

**D3. Local-first, with explicit unavailability.** The reader reads only these sources:
- this host's six store roots;
- this host's obs index, read-only;
- a replayed copy the index names in `files.read_path`;
- files given with `--file`.

It never contacts another host and never materializes a copy from the session archive. A
file it cannot read is reported unavailable, with the reason and the explicit operation
that would make it readable (§5.4). **Rejected:** automatic remote or archive retrieval,
which the studies did not qualify (brief §5) and which would make a read depend on the
network and on a mounted backup.

**D4. Roles follow recorded origin first.**
- **Claude records.** Classified by `origin.kind` wherever it is recorded, on a `user`
  record or inside an attachment. Records without it follow the rules of §8.1.
- **Codex records.** Classified by record type, role, phase and the injected-prefix list.
- **Why.** The prefix rule that obs's adapters and `session-episodes` share today loses a
  typed slash command (`CA:15`, SL2). obs's adapters never read `origin.kind`.
- **Before readout.** The reader carries its own classifier. The adapters keep theirs,
  because they are measurement (§11). After readout they re-base on the reader's (Stage
  B2).

**D5. Ship the reader before readout; ship the skill after it.**
- **Stage A, before readout.** Adds the reader as new files only, reachable by explicit
  path.
- **Stage B, after readout on 2027-02-16.** Rewrites the session-logs skill around the
  reader and installs `~/.agents/bin/session-logs`. Both move to obs with obs-f5710b.
- **Until then,** the reader is named only in the briefs of tasks whose subject it is
  (§11.2).
- **Rejected: a skill update now with a covariate note.**
  - A skill edit changes what enrolled sessions see.
  - It plausibly acts more on the flow-on arm, whose verified gate sends reviewers to raw
    transcripts.
  - The boundary's change 5 holds such steps until readout and says a covariate note does
    not show the arms stayed equivalent.

  §11 has the full assessment.

**D6. This task delivers the design, the plan and hq's fixture step. A new obs task builds
the reader.** This task is flow-trial-1 unit `tack-c411df`, flow on, and is its own unit
root. Its body says it "scopes the design and handoff; implementation tasks follow the
reviewed plan."

When the plan is approved:
- **hq's steps.** The plan's hq steps carry `Task N:` headings and are filed as this task's
  children. They share its unit and its worktree. Today there is one: the SL11 fixtures
  (§14.3).
- **The obs build: its plan.** The plan gives the obs build's steps headings of the form
  `obs step N:`. `tasks check` treats only `Task N:` headings as steps, so these raise no
  `unlinked_step` warning in hq.
- **The obs build: its task.** One new obs task carries those steps.
  - It cites this spec and the plan by hq commit and path.
  - It is `--process direct`, because the reviewed plan settles the work.
  - It has no parent. Under obs-f5710b, whose process is set, trial-arm would place it in
    that unit.
  - It depends on this task, and vendors the fixtures from hq's main checkout after this
    branch merges. That way it takes the fixtures as reviewed in this task's integration
    review.
  - It is a separate unit with its own arm. Whichever arm it draws, its design and plan
    were made under flow on.
  - Its body says that its spec and plan live in hq's `docs/specs/` and `docs/plans/`, not
    obs's, and cites them by commit.
- **obs's planned-work rule.** obs's `AGENTS.md` requires a reviewed spec and plan before
  planned implementation. That is met in substance: both pass flow's human-judged gates
  here, and the obs task cites them by commit and path.
- **Stage B.** Recorded as notes on the existing deferred tasks (obs-f5710b, obs-081ded,
  hq-19580c), not as new tasks.
- **hq-b95324.** Before this branch merges, `tasks note hq-b95324 --no-reviewed` records
  the reviewed contract and the remaining work.

**Rejected: moving this task to obs with `tasks move`.**
- A move gives the record a new id and leaves a `moved` tombstone.
- `trial-arm` lists no `moved` status, so lookups on the moved task and on its children
  fail with a missing unit root. `census` fails the same way, and `trial-verdict` rejects a
  unit whose root id differs from its trial id. The review reproduced this in memory on a
  synthetic tree.

**Rejected: holding obs steps as children of this task.** Children must share the
project.

## 3. Boundaries

| Concern | Owner | Interface |
|---|---|---|
| Store roots and home names | obs `stores.store_roots`, unchanged, until Stage B3; then hq's home registry (hq-19580c, `hq homes --json`) | function call inside obs |
| Archive capture, prune, replay | hq session-archive; `obs index --replay` writes `files.read_path` | the index row |
| Index rows (files, sessions, missing state, read path, parents, task commands) | obs | read only, inside the reader; never offered to consumers as SQL |
| Records, roles, copies, turns, final messages, pairing, links, models, coverage | obs (this reader) | the `session-logs/1` stream (§4) |
| Acceptance fixtures (harness-version store samples) | hq, `tools/fixtures/session-logs/` | a vendored copy in obs, pinned by commit and sha256 (§14.5) |
| Usage skill | hq until obs-f5710b, then obs | skill text (§12) |
| Interactive resume | hq, `hq sessions` | unchanged; separate from this reader |
| Typed trace | a later composition (obs-c5c599) | consumes this reader's output |

**The supported obs consumer interface is the reader's `session-logs/1` stream.**
- **Owner.** obs owns it. A change to any field's meaning or name bumps the version.
- **Consumers.** Agents, hq tools and later trace composition read the stream, never
  `index.sqlite`.
- **The research SQL.** The probe's SQL in hq-a1c591 remains research evidence. The locate
  step of §5, with its own tests, replaces it.

## 4. Output objects

Every object has `type`. Optional fields are omitted when they do not apply. `null` means
the field applies but the source does not record it. Objects are written in a
deterministic order (§6.4, §7.2).

### 4.1 References

- **A ref names one physical line.** It is `<home>:<path relative to the home>#L<line>`, for
  example `claude-work:projects/-w-beta/c0….jsonl#L3`.
- **A block.** A ref to one content block appends `#<block>`, as in `…#L3#0`.
- **Numbering.** Lines count from 1 over physical lines, blank ones included. Blocks count
  from 0. This is the acceptance notation `CW:3#0`.
- **Home names.** These are the home directory's name without its dot (§5.1).
- **Explicit files.** A `--file` input's ref is `file:<the path as given>#L<n>`.
- **Line hash.** Each record carries `sha256`, the hash of its physical line including the
  newline. It lets a later run report a line as changed instead of silently reading
  different bytes (§7.3; survey, "Rechecking the evidence").

**Refs are local handles.** A Claude project directory's name encodes the session's
absolute working directory, so a ref can name local paths. Refs belong in task notes and
local reports, never in public text. That is why the published ledgers use home-relative
globs and `source_path_sha256` instead.

### 4.2 `record`: one transcript record or content block

A record that carries several content blocks yields one object per block. A record without
blocks yields one object.

| Field | Meaning |
|---|---|
| `ref`, `sha256`, `line`, `block` | §4.1; `block` absent for a whole record |
| `harness`, `home`, `profile`, `store` | `claude-code` or `codex`; home name; `personal` or `work` (§5.1); `live`, `archived`, `replayed` or `explicit` |
| `session` | the file's own identity (§5.2), never an inherited id |
| `agent` | the Claude child's `agentId`, in a subagent file |
| `at` | the record's timestamp, or `null` (a request blob has none) |
| `turn` | the turn's ref (§9.1) |
| `role` | one of `human`, `assistant`, `tool_call`, `tool_output`, `injected`, `dispatch`, `metadata`, `unknown` (§8) |
| `role_basis` | `origin`, `local_command`, `prefix_rule`, `agent_path` (§8.2), `structure` (the record's type or path decides) or `kind` |
| `kind`, `block_type` | the native record kind (`assistant`, `attachment/queued_command`, `api-request-blob`, `response_item/message`, `event_msg/item_completed/AgentMessage`, …) and block type (`text`, `tool_use`, `tool_result`, `thinking`, `input_text`, `encrypted_content`, …) |
| `origin_kind`, `prompt_source`, `phase`, `stop_reason`, `message_id` | the native values when recorded: Claude `origin.kind`, `promptSource`, `message.stop_reason`, `message.id`; Codex `phase` |
| `queued` | true for a Claude human message delivered mid-turn as a `queued_command` attachment |
| `synthetic` | true for a Claude assistant record whose model is `<synthetic>` |
| `copy` | `request_blob`, `resume_history`, `fork_history`, `compaction_history`, `event_mirror`, `duplicate_file` or `ambiguous` (§8.3), with `original` when the original's ref is known |
| `call` | `{id, tool, peer, is_error, command, status}`: the call id; the tool name; the paired call or result ref; whether the result is an error (results only); the shell command, when the input is one; and a call with no result is `status: pending` |
| `dispatch` | `{kind: "sdk_dispatch", call}` from `parent_tool_use_id`; it names a call, never a session (SL9) |
| `execution` | for a Codex `CommandExecution` item: `{command, exit_code, cwd, status}` |
| `call.command_bytes`, `call.command_truncated`, `execution.command_bytes`, `execution.command_truncated` | only when that command is cut: its full UTF-8 byte length and `true`; commands use the same `--text-bytes` cap as `text`, after matching (§6.3; R39) |
| `model` | `{value, basis}`; basis `runtime`, `requested`, `resolved` or `creation` (§10.3) |
| `text`, `text_bytes`, `truncated` | the searchable text (§6.2), cut at `--text-bytes`, its full length, and whether it was cut |
| `encrypted` | true when the block's content is encrypted and therefore unavailable |
| `raw`, `raw_truncated` | with `--raw` only: the original line, cut at `--raw-bytes` |

### 4.3 `session`: one candidate file

| Field | Meaning |
|---|---|
| `ref`, `harness`, `home`, `profile`, `store` | the file ref (no line) and its place |
| `session`, `agent`, `identity_basis` | the file's own identity and what established it (§5.2) |
| `relation` | for a lookup by id: `own`, `child`, `inherited`, `alias` or `mismatch` (§5.2) |
| `state` | `readable`, `missing`, `unreadable` or `changed` (§5.5) |
| `missing_since`, `read_path` | from the index row (§5.3); `read_path` is home-relative when it lies under a known root, otherwise absolute |
| `cwd`, `entrypoint`, `first_at`, `last_at`, `lines` | header values and extent |
| `links` | recorded links, each `{kind, target, basis, ref}` (§10.1) |
| `models` | every model value the file records, each with its basis and ref (§10.3) |
| `index` | `{state, file_id, current}`; `current` is false when the file has grown past the indexed span |
| `divergent` | true when another `own` file of the same identity differs from this one (§8.3) |

### 4.4 `turn`: one turn (§9)

| Field | Meaning |
|---|---|
| `session`, `turn`, `turn_id` | the session; the turn's ref, which is the ref of its first input record (Claude), first response when there is no opening input, or `task_started` (Codex); and the Codex `turn_id` |
| `inputs` | the turn's input records, plus any in-turn human records (a queued human message), each `{ref, role}` |
| `trigger` | `{ref, role, origin_kind}`, or `null` when there is no opening input (§9.1) |
| `end` | the ref of the turn's last record |
| `status`, `status_basis` | §9.3; `status_basis` also says which turn rule applied (§9.1) |
| `abort_reason` | on an interrupted turn with a closing record: the recorded Codex `turn_aborted.reason`, or `null` when no reason is recorded; omitted on other turns (R30) |
| `asks_user` | true when a Codex final message carries `questions` (§9.3) |
| `final` | `{ref, text, basis}`, present only when `status` is `completed` |
| `last_assistant` | when the turn has no final: its last assistant text's ref, or `null` if it has none; it is never labelled final |
| `commentary` | the refs of the turn's non-final assistant text |
| `models` | the runtime models of the turn's records (§10.2) |
| `calls` | the number of tool calls |
| `task_evidence` | only under `--task` (§9.4) |

### 4.5 `unparsed`

A line that is not a JSON object, or a final line with no newline. Its fields are `ref`,
`reason` (`malformed` or `truncated`), `raw_match` and, with `--raw`, its bytes. It is
never a record and never has a role (SL10).

**`raw_match`.** The line cannot be decoded, so the reader first undoes JSON string escapes
leniently (`\uXXXX`, `\/`, `\"`, `\\`, `\n` and the rest), leaving anything malformed
as it is. `raw_match` is then whether the pattern matches either the bytes or that text,
with the case rule of §6.2. An escape therefore cannot hide a match in an unparsed line.

### 4.6 `coverage`: the last object of every run

| Field | Meaning |
|---|---|
| `format` | `session-logs/1` |
| `host`, `query` | the host name and the parsed arguments, defaults marked |
| `query.sort_basis` | search only: `group_newest` or `group_path` for a store search, `file_newest` or `file_path` for other search scopes (§6.4; R46, R48) |
| `roots` | per root: home, store, state (`searched`, `absent` or `unreadable`), files, bytes |
| `index` | `{state, schema, last_complete_run, age_minutes, coverage_start, rows_outside_roots, outside_root_paths}`; state `used`, `stale`, `absent`, `unsupported_schema` or `unreadable`, with the reason; `coverage_start` per root (§5.3); unmatched index rows are counted, with their paths (R20) |
| `window` | `since` and `until`, and whether `since` is the default |
| `files` | scanned, skipped by mtime (§6.1), unreadable (refs), vanished during the run (refs), and missing in scope (refs, with read path and its state); a list longer than 20 is cut and its count kept |
| `files.aliases_not_read` | `{count, items}`: in-scope transcript aliases whose resolved target was not read by this run; items are refs, capped at 20 (§6.5; R48) |
| `lines` | malformed and truncated refs, each marked `raw_match` |
| `copies` | collapsed copies by kind; whether detection was limited to the files read (§8.3) |
| `limits` | the object limit and whether it was hit; the text and raw byte limits |
| `matches` | `parsed`, `unparsed_raw`, and `collapsed_copies`: matching records suppressed only because they are known copies, counted separately from parsed matches (§6.5; R45, R48) |
| `task.mentions_since` | under `--task`: the effective lower bound for mention-file listing, or `null` without `--mentions` (§9.4; R44, R48) |
| `target.turn_cut` | for a record-ref turn view over the nominal `--limit`: `{records, shown, before, after}`; target-line exemptions can leave every object shown (§7.2) |
| `outcome`, `outcome_basis` | `found`, `not_found` or `unknown` (§6.5, §7.4) |
| `rules` | the naming rule of §5.1 and the classifier version, so a later reader knows which rules produced the roles |

## 5. Location

### 5.1 Roots, homes and profiles

- **Roots.** The reader reads `stores.store_roots(env)`: two Claude roots and four Codex
  roots, with the same environment overrides the index uses. It neither defines nor edits a
  root list. With `HOME` pointed at a fixture home, the six roots fall under that home.
- **Home name.** The root's parent directory name without its leading dot: `claude`,
  `claude-work`, `codex`, `codex-work`.
- **Store.** `archived` for an `archived_sessions` root, otherwise `live`.
- **Profile.** `work` when the home name ends in `-work`, otherwise `personal`. This is a
  stated rule, recorded in coverage. Stage B3 replaces it with hq's home registry.
- **Absent roots.** A root that does not exist is `absent`: a coverage fact, not an error
  (SL4).
- **Unreadable roots.** A root that cannot be listed is `unreadable`.
- **Index location.** The reader finds the index the way obs does: `--state-dir`, else
  `$XDG_STATE_HOME/obs`, else `~/.local/state/obs`. It restates that rule, and a test checks
  it against `obs._state_dir` (§11.2). A relative `XDG_STATE_HOME`, which obs refuses, is
  a failure: `bad_state_dir` (§6.6).
- **Explicit files.** A `--file` input has no home, so its `profile` is `null`.

### 5.2 Candidates and identity

A lookup by id collects every candidate file from these sources, and never silently picks
the first one.

**What an id can be:**
- a Claude session uuid;
- a Claude agent id, bare or as `agent-<agentId>`;
- a Codex thread id.

**Native sources.** Matching is by directory entry, never by a computed slug, as `hq
sessions` already does (discovery contract).
- **Claude main file:** `<root>/*/<id>.jsonl`.
- **Claude children of that session:** `<root>/*/<id>/subagents/agent-*.jsonl`.
- **A Claude agent id:** `<root>/*/*/subagents/agent-<agentId>.jsonl`.
- **Codex:** `<root>/**/rollout-*-<id>.jsonl`.

**Index sources:**
- rows whose `sessions.session_id` is the id;
- for a Claude agent id, rows keyed `agent-<agentId>`, which is how obs's adapter keys a
  child's rows;
- rows whose `parent_session` is the id, which give children whose files are gone;
- Codex files whose `parser_state` identity `thread_id` is the id.

**How each candidate's identity is read:**
- **Claude main file:** a UUID file name is authoritative. If main-line `sessionId`
  values disagree with it, normalization reports `identity_basis: file_name_unconfirmed`
  but keeps the filename identity. A transcript renamed to a different UUID therefore
  remains an `own` candidate for that name and is read. This is a Stage A limit, not the
  Codex mismatch protection below. For an explicit file without a UUID name, the first
  main-line `sessionId` supplies identity when recorded.
- **Claude child:** `agent-<agentId>`, from its `agentId` and its `subagents/` path. Its
  records' `sessionId` is the parent's, which is inherited (SL8).
- **Codex:** the first `session_meta`'s `payload.id`, never `payload.session_id` (SL3).

**`relation`** is set from that identity:
- `own`: the file's identity is the id;
- `child`: a Claude subagent of the session, or a Codex rollout whose first `session_meta`
  names the id as its parent;
- `inherited`: a Codex rollout holding a later `session_meta` whose `payload.id` is the id,
  a fork copy;
- `alias`: a symlinked transcript. The reader reports it with its target and does not read
  it, as `stores._paths` skips symlinks; a dangling one is `missing`.
- `mismatch`: a native **Codex** file name matches the requested id but the file's
  recorded identity differs. It is reported after aliases and is never read as the
  requested session (R19). Claude's UUID filename authority is the separate limit above.

Only `own` files are the session. The others are listed with their relation.

**Codex children without the index.** Finding the children of a Codex thread natively
would mean reading every rollout's first line. So without the index, a Codex lookup lists
no children, and coverage says so.

### 5.3 Index facts

**How the index is opened:**
- **Path check.** The reader checks first that `index.sqlite` exists. A missing file is
  `absent`.
- **Open.** It then calls obs's `index.open_index_readonly`, which pins the schema version.
  That function's `ValueError` for a different version becomes `unsupported_schema`.
- **Errors.** Any `sqlite3.Error` becomes `unreadable`.

**When it reads.** Every index fact the run needs is read in one short `index.read_snapshot`
before the walk, so no read transaction stays open during a scan.

**What it reads:**
- per file: `path`, `read_path`, `missing_since_ms`, `byte_offset`, `size`, `indexed_at_ms`,
  `span_sha256`, `span_stable`;
- per session row: `session_id`, `parent_session`, `subagent`, `start_ms`, `end_ms`, `cwd`;
- Codex identity from `parser_state`;
- `task_commands` rows for `--task` (§9.4);
- the last complete run from `index_runs`.

**Staleness.** The index is `stale` when its last complete run ended more than 2 hours
before the reader started: twice the period of the hourly timer.

**Coverage start.** The index knows only files that existed when it ran. A file pruned or
deleted before the index first saw it is in neither the native walk nor the index.
- **Definition.** Each root's coverage start is the earliest `indexed_at_ms` among its file
  rows.
- **Why it errs late.** obs stamps `indexed_at_ms` anew whenever it re-reads a file: on an
  extractor change, and on a replay. Only rows it can no longer read, missing files, keep
  their first stamps. So the start moves later after every re-parse, and erring late errs
  toward `unknown`.
- **A root with no rows,** present or absent, has no coverage start. A search that selects
  a present root with no rows cannot answer `not_found` over the stores.
- **Live values on 2026-10-23** (review):

  | Roots | Coverage start | Held by |
  |---|---|---|
  | `claude`, `claude-work` | 2026-09-18 | only missing rows; present rows were all restamped on 2026-10-20 |
  | the three Codex roots | 2026-10-20 | every row, after that day's re-parse; no missing rows |

**Consequences until obs records a first-seen stamp (Stage B2):**
- **Store-wide Codex searches.** A default-window store-wide search that selects a Codex
  root is `unknown` until about 2026-11-19.
- **Older Codex sessions.** A zero-match search scoped to a Codex session that started
  before 2026-10-20 is `unknown`.
- **Fixes that move the start.** Replaying pruned files (hq-d70879) and Stage B2's
  extractor bump both restamp rows, so both move the coverage start later again.

**A row whose path no longer exists is missing,** even before the index marks it.

**The native walk is always the primary source.** The index adds what the walk cannot see:
- files that are gone;
- their replayed copies;
- children recorded by parent;
- recorded task commands.

Without a usable index the reader still runs. Coverage says so, and an empty answer over
the stores cannot be `not_found` (§6.5).

**Index roots mismatch (R20).** Rows under none of the currently configured roots are
not silently discarded: coverage reports `index.rows_outside_roots` and
`index.outside_root_paths`. A nonzero count blocks `not_found` over the stores, with basis
`index_roots_mismatch` when it is the first failed condition. Explicit-file searches do
not depend on the index.

### 5.4 Availability, replayed copies and remote hosts

Availability is per file (M01):
- **Readable.** A readable file is read.
- **Missing, with a readable copy.** A missing file whose `read_path` is readable is read
  from that path, with `store: replayed`. Its refs keep the logical path.
- **Missing, copy unreadable.** A `read_path` that cannot be read (for example, an
  unmounted backup disk) leaves the file `missing`, and coverage names the copy's path.
- **Missing, no copy.** A missing file without a `read_path` is unavailable. Coverage
  names the explicit routes:
  - read the session archive's mirror copy with `--file`, if the archive holds one;
  - replay the archive into the index (hq-d70879).
- **Unreadable.** A permission failure is `unreadable`, never skipped (SL10).

**Another host is a separate, explicit run.** The reader is run there over ssh, and each
run's coverage names its host. Combining two hosts' answers is the caller's work. The
second host had no index on 2026-10-20, so its empty answers are `unknown`.

### 5.5 Files that change during a run

- **Listing first.** The reader lists every selected root before reading any file.
- **A file that vanishes.** A listed file gone by the time it is read is looked for once
  under the same name in its home's other Codex root (`sessions` and `archived_sessions`),
  because a rollout can move to the archive mid-run. If it is not there either, it is
  counted as vanished, and it makes a zero-match answer `unknown`.
- **Live appends.** Each file is read up to the size it had when opened. Bytes appended
  later fall outside the run. A last line without a newline at that size is `truncated`.
- **Changed state.** A file is `changed` when the bytes up to the index's `byte_offset` no
  longer hash to its `span_sha256` (where `span_stable`). It is checked for every
  candidate `show` reads and for every file a search emits objects from. A changed file is
  read as it now is and marked, because refs taken from an earlier run may now point
  elsewhere.

## 6. `search`

### 6.1 Selection

| Option | Selects |
|---|---|
| `PATTERN` (optional) | records whose searchable text contains it; case-insensitive literal; `--regex` for a Python regular expression, `--case` for case-sensitive |
| `--harness`, `--home`, `--profile`, `--store` | files by place (each repeatable) |
| `--session ID` | the `own` files of an id (§5.2); a child is selected by its own id; repeatable |
| `--task ID` | sessions with evidence for the task (§9.4); `--mentions` adds sessions that only mention it, labelled as such |
| `--file PATH` | an explicit file outside the stores (§6.7); repeatable |
| `--cwd PATH` | sessions whose recorded cwd is the path or inside it; this also narrows the missing files in scope |
| `--since`, `--until` | `when` values (`YYYY-MM-DD`, `<n>d`, `<n>w`), inclusive, against each record's timestamp |
| `--all-time` | removes the default window; cannot be combined with `--since` |
| `--role`, `--kind`, `--tool`, `--call` | records by role, native kind, tool name or call id (each repeatable) |
| `--copies` | include copies, labelled (§8.3) |
| `--state-dir PATH` | the obs state directory (§5.1) |

**Default time window.** Without `--session`, `--task`, `--file`, `--since` or
`--all-time`, the window is the 30 days that end at `--until`, or today when `--until` is
absent. Coverage marks it as the default.

It bounds the scan cost of an unqualified search, which parses every file in scope (§6.2).
For comparison, the pre-flow extractor needed about 2 minutes for 23 GB while skipping
most files by a byte test. The live-store run (§14.4) measures the reader's own cost.
- `--since` skips files whose mtime is older, which is exact because no record in a file
  is newer than the file's mtime. Inside the files it reads, it skips records older than
  the window.
- `--until` skips records after it.
- A record without a timestamp (a request blob) belongs to the window of the record it
  copies.

**Default roles.** A pattern search matches every role except `metadata`, unless
`--role` names roles. So the Codex event items that repeat response text (§8.2) never
double a match. A search without a pattern streams every role.

### 6.2 Matching

The searchable text of a record is the first of these that applies:
- a message's text;
- a tool call's input, as compact JSON, plus its extracted shell command;
- a tool output's text;
- an execution's command and output;
- the compact JSON of a metadata or `unknown` record.

**Every file in scope is parsed.** There is no raw-byte prefilter. Valid JSON may spell any
character as an escape: `"\u006eeedle"` decodes to `needle`, but its bytes do not contain
`needle`. So a byte test can reject a file that holds a match, and coverage would then
present a false negative as conclusive.

The default window bounds the cost (§6.1). A prefilter may return later only together with:
- a stated proof that it handles every JSON escape and the case folding of §6.2;
- this counterexample as a test.

**Case.** The default match compares `casefold()` of the pattern and of the searchable text.

### 6.3 Output modes and bounds

- **Records.** The default mode emits matching records. Without a pattern and with no role
  filter it is the bounded unfiltered stream for schema and aggregate questions (SL1, SL6).
- **`--sessions`** emits one session object per matching file (SL4).
- **`--final`** emits turn objects (§9). With a pattern, it emits the turns whose final
  text matches it.
- **Bounds.**
  - `--limit/-n N` caps emitted objects; the default is 50, and `--no-limit` removes the
    cap.
  - `--text-bytes` defaults to 2,000 and `--raw-bytes` to 16,384.
  - `call.command` and `execution.command` are cut to `--text-bytes` too; when cut, their
    enclosing object carries `command_bytes` and `command_truncated: true` (R39).
    Matching uses full text and commands before any output truncation.
  - A hit limit is recorded in coverage.

### 6.4 Order and copies

- **Order (R46).** Store searches emit each copy group contiguously, holding one group at
  a time. Files of one harness/identity are grouped for duplicate detection; Claude
  non-subagent files in one home/project directory are also grouped for resume detection.
  These connections can join groups across directories. `--sort activity`, the
  default, orders groups by their newest member's mtime and files newest first inside
  each group. It is not a global per-file activity order. `--sort path` orders groups by
  their first home/path and files by home/path inside each group. `--reverse` reverses
  the resulting file sequence, keeping groups contiguous. Records follow file order,
  and the limit applies in that order. Coverage states the basis (§4.6). Other scopes
  order files by the selected file sort. Task searches sort evidence and mention-only
  files together, so a newer mention can precede a stamped session; order does not rank
  evidence strength, and a limit can exclude that stamped session.
- **Copies.** Collapsed by default and counted in coverage (§8.3).

### 6.5 Outcomes

- **`found`:** at least one parsed match.
- **`not_found`:** zero parsed matches. Every search needs these six:
  - no selected root was unreadable;
  - no file in scope was unreadable or vanished;
  - no missing file in scope lacked a readable copy;
  - no in-scope transcript alias had a resolved target that this run did not read;
  - no unparsed line in scope had a raw match;
  - no collapsed copy in scope matched the record selection and pattern.

  An unread alias blocks with basis `alias_not_read`. An alias whose target's mtime is
  before `--since` is outside the window; an alias of a file already read adds no unread
  evidence. With `--cwd`, an unread alias stays in scope because its cwd is unknown.

  A matching collapsed copy blocks with basis `collapsed_copy_match`: request blobs and
  compaction history can hold text with no original in scope. `--copies` exposes those
  records as parsed matches. Under `--final`, copies are never turns, so they do not
  contribute to `matches.collapsed_copies` or make an empty final answer unknown
  (R45, R48). All earlier conditions still apply to `--final`.

  Then it depends on the search's scope:
  - **Only explicit files:** nothing more.
  - **A session or task:** the index was `used` (present, the expected schema, and not
    stale), it has no rows outside the configured roots, and all three of these hold:
    - every selected session has at least one candidate;
    - every selected session's first record falls after its root's coverage start
      (§5.3);
    - for `--task`, the task's earliest time (its `created`, or its first note's `at`)
      falls after the coverage start of every selected root. A session pruned before the
      index first ran, and never stamped, would otherwise go unseen.
  - **Store-wide:** the index was `used`, it has no rows outside the configured roots,
    and the window starts no earlier than every
    selected root's coverage start. An `--all-time` store-wide search never answers
    `not_found`.
- **`unknown`:** any other zero-match result. `outcome_basis` names the first failed
  condition.

**What "in scope" means.** A file is in scope when it lies under a selected root and
matches the run's place, session, task, file and cwd selection. For a missing file, its
indexed time span must also overlap the window.

**Absent roots** hold nothing and do not by themselves make an answer `unknown`.

**Why the index is required for `not_found`.** It is the only record of files that are
gone. Even a fresh index has two blind spots:
- a file created and deleted between two of its runs, which is why staleness is bounded;
- a file gone before it first ran, which is why the window must start inside its coverage.

**What that means for answers.**
- A host without an index never answers `not_found`.
- A pruned file without a replayed copy keeps a search that reaches it `unknown`.
- A window reaching before the index's coverage is `unknown`, with basis
  `before_index_coverage`.

That is the explicit unavailable result the original report lacked.

**On this host today.** An unscoped default-window search with zero matches is
`unknown`, for two independent reasons (review, 2026-10-23):
- **Missing Claude files.** 102 Claude files in the `claude` home were missing, had no
  replayed copy, and ended within the last 30 days. Files the archive never captured stay
  unavailable.
- **Codex coverage.** The Codex roots' coverage started on 2026-10-20 (§5.3).

So for now only a search confined to roots that are clear of both can answer
`not_found`. `--home claude-work` is one.

### 6.6 Exit codes and errors

- **0:** the run completed, whatever its outcome. The outcome is in coverage.
- **1:** the run failed. One error object, `{"error":{"kind","detail"}}`, goes to stderr,
  with nothing more on stdout. The kinds are:
  - `tasks_failed`: `tasks show` failed or printed something other than a task;
  - `unknown_format`: a `--file` that is neither a transcript, a rollout nor an SDK stream;
  - `unreadable_input`: a `--file` that cannot be read;
  - `bad_state_dir`: obs's state-directory rule refused the environment (§5.1).
- **2:** a usage error, printed on one line to stderr with the usage line. A malformed ref
  or `when` value is a usage error.

### 6.7 Explicit files

- **Format.** A `--file` input's format is decided by the first record that matches one of
  these signatures:
  - a `session_meta` record makes it a Codex rollout;
  - a record with `sessionId`, or a Claude kind that comes without one (such as
    `fork-context-ref`), makes it a Claude transcript;
  - an event with `session_id` whose `type` is `system`, `user`, `assistant` or `result`
    makes it a Claude SDK stream. That includes the stream's opening `system`/`init` event.

  A file in which no record matches is `unknown_format`.
- **Identity and place.** The file's identity comes from its records as in §5.2. Its store
  is `explicit`, and its home is `file`.

## 7. `show`

### 7.1 Targets

| Target | Default view |
|---|---|
| a session id (§5.2) | the session view: a session object for every candidate, `own` first, then `child`, `inherited`, `alias` and `mismatch`; then a turn object for each turn of each readable `own` candidate |
| a file ref (`<home>:<path>`) | the session view of that file |
| a record or block ref | the turn view: the turn object of the turn holding the record, then every record of that turn, each call followed by its paired result |
| `--file PATH` | the session view of an explicit file; with `--lines`, its line view |
| an explicit file's record ref (`file:<path>#L<n>`) | the turn view inside that file |

### 7.2 Options and bounds

| Option | Effect |
|---|---|
| `--lines A-B` | the line view: the records of physical lines A to B of the target's file |
| `--turn` | the turn view for a session or file target: every turn, each with its records |
| `--links` | follows recorded links one hop (§10.1) and adds the linked sessions' session objects and the binding records: Claude's launch call and result, Codex's spawn call and `SubAgentActivity` item |
| `--copies`, `--raw`, `--text-bytes`, `--raw-bytes`, `--state-dir` | as for `search` |
| `--expect-sha256 H` | with a record ref: compare the line's hash with a previously captured one (§7.4) |
| `--limit/-n N` | caps emitted objects: 200 turns in the session view, 500 records in the turn and line views; `--no-limit` removes the cap |

`show` emits every role, metadata included, because it shows a whole span.

**A record target survives the limit (step 10 corrective review).** A record-ref turn
view windows its records around the target line. Every record on that physical line is
shown, even when that exceeds `--limit`, including a changed line under
`--expect-sha256`. The turn object is emitted separately from the record cap. If the
turn exceeds the nominal cap, coverage records `limits.hit` and `target.turn_cut`:
`records` is the full
turn's record/unparsed-object count, `shown` is the count emitted, and `before`/`after`
count objects outside the retained window. These counts are objects, not physical lines.
The flags are set before target-line objects are restored. For three objects all on
the target line and `--limit 1`, all three return with `limits.hit: true` and
`turn_cut: {records: 3, shown: 3, before: 0, after: 0}`. Check `shown < records` to infer
omission; `limits.hit` alone does not establish it. This retains the step-10 ledger's
coverage caveat without changing the reader.

**Order.** Objects follow file order. When an id has several readable `own` files, each is
read, in root order:
- lines of a later file that repeat an earlier one's are collapsed as `duplicate_file`;
- files that differ are both read and marked `divergent`.

### 7.3 Changed lines

- **Line beyond the end.** A record ref whose line is past the end of a readable file
  gives `unknown`, with basis `line_absent`.
- **Hash mismatch.** With `--expect-sha256`, a line whose hash differs gives `unknown`,
  with basis `line_changed`. The current line is still shown, marked.

### 7.4 Outcomes and exit codes

`show` answers `found` or `unknown`, never `not_found`.
- **`found`:** the target resolved to at least one readable record or file.
- **`unknown`:** anything else, including:
  - every candidate missing without a copy;
  - an id looked up without a usable index (SL10B);
  - an id with no candidate in any source.

**Why there is no `not_found`.** An id carries no time the reader can check against the
index's coverage start (§5.3). An id with no candidate may be a session pruned before the
index first ran.

Exit codes and errors are those of §6.6.

## 8. Roles, copies and the classifier

### 8.1 Claude Code

| Record | Role |
|---|---|
| `user` with `origin.kind` `human` (a typed prompt, or a slash command beginning `<command-message>`) | `human`; in a subagent file, `dispatch` |
| `user` with any other `origin.kind` (`task-notification`, `peer`, …) | `injected` |
| `user` with `isMeta` or `isCompactSummary` (including `isMeta` peer records) | `injected` |
| `user` without `origin`, or `system` with subtype `local_command`, whose text begins `<command-name>` or `<bash-input>` | `human`, basis `local_command`: the person's local command, which reaches no model |
| `user` without `origin`, or `system` with subtype `local_command`, whose text begins `<local-command-stdout>`, `<local-command-stderr>`, `<bash-stdout>` or `<bash-stderr>` | `injected`, basis `local_command`: that command's output |
| `user` that is the interrupt marker (`[Request interrupted by user…`) | `injected`; it ends the preceding turn (§9.1) |
| other `user` without `origin` (records older than the field) | the prefix rule: `human` unless the text begins with `<` (but not `<pasted_content`), else `injected` |
| `user` tool-result blocks | `tool_output`, one object per block |
| `attachment` with `attachment.origin.kind` (`queued_command`) | `human` with `queued: true` when the kind is `human`, else `injected` |
| other `attachment` | `injected` |
| `assistant` text and thinking blocks | `assistant`; a `<synthetic>` model marks it `synthetic` |
| `assistant` `tool_use` blocks | `tool_call` |
| `api-request-blob` blocks | the role of their request message (system → `injected`, user → the `user` rules, assistant → `assistant` or `tool_call`), each with `copy: request_blob` (SL1) |
| `system` with subtype `turn_duration` or `stop_hook_summary` | `metadata`; `turn_duration` ends a turn, and a `stop_hook_summary` with `hookErrors` marks a Stop-hook continuation (§9.1) |
| other `system`; `queue-operation`, `mode`, `permission-mode`, `ai-title`, `custom-title`, `last-prompt`, `agent-name`, `agent-setting`, `agent-color`, `pr-link`, `file-history-*`, `cost-state`, `api-request`, `api-request-shape`, `continued-in`, `atis-latch`, `isolation-latch`, `bridge-session`, `fork-context-ref`, `summary`, `relocated`, `worktree-state` | `metadata`; `continued-in` is also a link (§8.3) |
| anything else | `unknown`, kept in the stream with its ref (SL1 `CA:16`) |

**Subagent files.** In a subagent file every prompt record is `dispatch`, never `human`.
That includes `AG:1`, a `user` record holding the dispatch brief (SL8).

**Forked subagents.** A forked subagent file begins with `fork-context-ref`. Its first
assistant response copies the parent's message holding the launching call, so that
response is `fork_history`. obs's adapter handles it the same way.

**Local commands.** The two local-command rules match what versions 2.1.292 to 2.1.304
write, in both record shapes, as the review observed in 600 recent files. A slash command
that reaches the model carries `origin.kind` `human` and follows the first row.

### 8.2 Codex

| Record | Role |
|---|---|
| `session_meta` | `metadata`; the first one gives identity; a later one starts fork history (§8.3) |
| `turn_context`; `event_msg` turn start, complete and aborted | `metadata` |
| `event_msg` `item_completed` with `AgentMessage` or `UserMessage` items; `event_msg` `user_message` and `agent_message` (older rollouts) | `metadata`, `copy: event_mirror` (they repeat response items) |
| `event_msg` `item_completed` with `CommandExecution` | `metadata` with `execution` (§4.2). Its `id` matched no call id in 60 recent rollouts, so it is not paired with a call |
| other `item_completed` items (`SubAgentActivity`, `Reasoning`, `FileChange`, `CollabAgentToolCall`, `ContextCompaction`, …) | `metadata`; `SubAgentActivity` binds a spawn (§10.1) |
| `response_item` message, role `user`, in a root thread | the injected-prefix rule: `injected` when it begins with `# AGENTS.md` or `<` (but not `<pasted_content`), else `human` |
| `response_item` message, role `user`, in a child thread | `injected` under the same prefix rule, else `dispatch` |
| `response_item` message, role `developer` | `injected` |
| `response_item` message, role `assistant` | `assistant`, with `phase` |
| `response_item` `agent_message` from the thread's controller | `dispatch`, basis `agent_path`; encrypted blocks are `encrypted` (SL7 `XC:4`) |
| `response_item` `agent_message` from anyone else (a child's report, a sibling) | `injected`, basis `agent_path` |
| `inter_agent_communication_metadata`, `token_usage_record`, `world_state` | `metadata` |
| `compacted` | `metadata`; its `replacement_history` messages are `compaction_history` copies (§8.3) |
| `response_item` function, custom, local-shell or web-search call | `tool_call` |
| their `*_output` records | `tool_output` |
| `response_item` `reasoning` | `assistant`, `block_type: reasoning`; encrypted content is `encrypted` |
| anything else | `unknown` |

**Observed kinds without another row (R15).** The following stay `unknown`, including
their compact JSON as searchable text. This makes Stage A's fallback explicit rather
than silently treating a familiar-looking name as metadata or a paired call. Counts are
from the four retained sweep slices (§14.7), with copies included:

| Native kind (or compacted entry type) | Records | Role |
|---|---:|---|
| `event_msg/token_count` | 1,817,365 | `unknown` |
| `event_msg/exec_command_end` | 76,438 | `unknown` |
| `event_msg/patch_apply_end` | 72,656 | `unknown` |
| `event_msg/agent_reasoning` | 43,878 | `unknown` |
| `event_msg/sub_agent_activity` | 33,857 | `unknown` |
| `event_msg/thread_settings_applied` | 15,862 | `unknown` |
| `compacted` entry `compaction` | 9,390 | `unknown`, `copy: compaction_history` |
| `event_msg/context_compacted` | 8,129 | `unknown` |
| `event_msg/mcp_tool_call_end` | 7,469 | `unknown` |
| `event_msg/web_search_end` | 4,861 | `unknown` |
| `event_msg/collab_waiting_end` | 1,705 | `unknown` |
| `event_msg/collab_agent_spawn_end` | 1,212 | `unknown` |
| `event_msg/collab_close_end` | 1,071 | `unknown` |
| `response_item/tool_search_call` | 574 | `unknown` |
| `response_item/tool_search_output` | 574 | `unknown` |
| `event_msg/collab_agent_interaction_end` | 375 | `unknown` |
| `response_item/additional_tools` | 335 | `unknown` |
| `event_msg/thread_rolled_back` | 172 | `unknown` |
| `event_msg/collab_resume_end` | 37 | `unknown` |
| `compacted` entry `additional_tools` | 21 | `unknown`, `copy: compaction_history` |
| `event_msg/view_image_tool_call` | 14 | `unknown` |
| `event_msg/error` | 8 | `unknown` |
| top-level `retained_context` | 1 | `unknown` |

These are 2,096,004 Codex records, not 2,096,004 failures to parse. Unknown roles can
produce default pattern hits, unlike `metadata`; copy suppression still applies. This
revision retains that behavior. Reclassifying them requires checking their actual record
shapes and the effect on matching, pairing and turns, then revising the classifier
contract. Counts alone do not establish those meanings. The non-Codex unknown kinds in
the same sweep were `frame-link` (55), `artifact-comment-monitor` (17) and
`artifact-autoreact-ledger` (15); they keep §8.1's fallback too.

A rollout is a child thread when its first `session_meta` records either of these:
- a parent, in `source.subagent.thread_spawn.parent_thread_id` or `payload.parent_thread_id`;
- a `thread_source` set to a value other than `user`.

This is the rule obs's adapter uses.

**Agent paths and direction.**
- **A thread's own agent path** is `source.subagent.thread_spawn.agent_path` in its first
  `session_meta`. A root thread's path is `/root`.
- **Its controller** is that path with its last segment removed.
- **Dispatch or report.** An `agent_message` whose `author` is the thread's controller is a
  dispatch. Every other author makes it `injected`: a child's report, a sibling's message,
  or one from an ancestor above the controller. In a root thread every `agent_message` is
  therefore `injected`. In child threads the review found 35 sibling and 12 higher-ancestor
  authors.

  The review found 126 such messages in 80 recent root rollouts, all addressed to `/root`
  from a child, and 69 in child threads addressed from the controller.
- **No recorded agent path.** If a child thread records no agent path, its `agent_message`
  records are `unknown`. Direction is never guessed.

### 8.3 Copies

| Copy | How it is recognized | Default |
|---|---|---|
| `request_blob` | every block of a Claude `api-request-blob` record | collapsed |
| `resume_history` | below | collapsed |
| `fork_history` | Codex: the copied turns after a second, inherited `session_meta` (below); Claude: a forked subagent's first assistant response (§8.1) | collapsed |
| `compaction_history` | the messages inside a Codex `compacted` record's `replacement_history`, which repeat earlier messages | collapsed |
| `event_mirror` | the Codex events of §8.2 | collapsed; also outside a pattern search's default roles |
| `duplicate_file` | a line that repeats, at the same line number, a line of an earlier-root `own` file of the same identity (`sessions/` comes before `archived_sessions/`) | collapsed into the earlier-root file |
| `ambiguous` | a shared run whose copy cannot be told from its original, or a fork's range whose parent is unavailable (below) | not collapsed; a turn built from it has no `final` |

**`resume_history`.** Two Claude files in one project directory share record `uuid`s. The
shared records need not be contiguous in either file. Which file holds the copy is decided
in this order:
1. **Native link.** A `continued-in` record in one file whose `continuedInSessionId` names
   the other file's session makes the named file the copy. The pair is also reported as a
   `continued_in` link.
2. **Timing.** Otherwise, the copy is the file whose first unshared user or assistant
   record is later than every user or assistant record of the other file. A resume
   continues a session after the original stopped.
   - In the fixtures, `CW2:4` (10:00:00) is later than all of CW (last at 09:06:05), while
     `CW:4` is not later than all of CW2. So CW2's lines 1–3 are copies of CW's (SL5, SL6).
   - On live files, the review found the rule agreed with `continued-in` in all 18 pairs
     that rule decided.
3. **Ties (R26).** A file with no unshared user or assistant record cannot meet the timing
   test. The shared records of both files are `ambiguous` only when neither or both meet
   it. A wholly copied original plus a resume that adds later records is therefore a
   decided resume, not a tie. A forked live pair with neither file later falls here.

**Rules that hold for every kind:**
- **Scope.** Copy detection covers only the files the run reads. A resume copy whose
  original is outside the scope is not recognized, and coverage says so.
- **Call deduplication.** A call or result id repeated in a copy is not a second call
  (SL1). Aggregates over originals are deduplicated by call id (SL6).
**Codex `fork_history`.** A forked rollout's second `session_meta` carries the inherited
thread's id.
- **What is copied.** A run after it repeats that thread's history. It may start partway
  through the parent's turns, or copy no parent `task_started` at all. It need not be a
  prefix of the parent's whole history. Copies are restamped at fork time, so timestamps
  cannot mark the end. The original review's 150 prefix examples were one observed
  shape, not a requirement. Stage A's later 20-fork sample included seven whose copied
  turn ids were not a prefix of the parent's ids and one with no copied `task_started`;
  the turn-id boundary held on all 20 (§14.7).
- **The rule.** The records after the second `session_meta` are `fork_history` until the
  first `task_started` whose `turn_id` does not occur in the inherited thread's own
  rollout. That rollout is found by the inherited id (§5.2).
- **Native ordinal: retain R11.** The first `session_meta.payload` may carry
  `subagent_history_start_ordinal`. In all 269 measured forks carrying it, its value
  equalled the zero-based index of the record immediately before the first own
  `task_started` (the measured own physical line minus 2). The observed versions carrying
  it were 0.147.0–0.164.0, not a guarantee that every version or future format carries it.
  This revision does **not** use it as an independent boundary. The measurement validated
  agreement with readable parents; it did not qualify invalid ordinals, conflicting
  boundaries, malformed-line offsets or a fork stopping before any own turn. Adopting it
  requires those controls, including parent-absent replay, in a later reviewed change.
- **Parent unavailable.** The reader has no accepted independent boundary in that case.
  A fork can stop after copying before it starts a turn of its own. Everything after the
  second `session_meta` therefore remains `ambiguous` to the end, even when the native
  ordinal is present. This is an explicit limit, not a claim that the field is absent.
- **Turn detection.** Copied turns are not turns of the fork; turn detection skips them.
- **Ambiguous turns.** A turn built from an ambiguous range carries `copy: ambiguous` and
  never has a `final`. Its last assistant text appears only as `last_assistant`, so a
  parent's final answer is never attributed to the fork. That holds until an independent
  boundary settles ownership, such as the inherited rollout becoming readable.
- **Coverage.** SL11's XF has a readable parent; XK has no parent and an ordinal past its
  last record. XK still has no final. The live-store check adds mid-parent and
  no-copied-start shapes (§14.4, §14.7).

### 8.4 One classifier, later

The reader's classifier is a fourth implementation of rules that obs's two adapters and
`session-episodes` already share. It differs from them in honouring `origin.kind` and the
local-command shapes.
- **Until readout:** the four coexist, and coverage records the reader's classifier
  version.
- **Stage B2:** the adapters and the moved `session-episodes` call the reader's normalizer,
  and the skill's "change all three together" list becomes one module.

## 9. Turns and final messages (hq-b95324)

### 9.1 Turn boundaries

**Codex.**
- **Span.** A turn runs from `event_msg` `task_started` to `task_complete` or
  `turn_aborted`, keyed by `turn_id`.
- **Unended turns.** A `task_started` followed by another `task_started` with no end
  between them ends where the next begins (status `incomplete`, §9.3). The review saw this
  6 times in 600 rollouts.
- **Inputs.** The user, developer and `agent_message` records before the turn's first
  assistant or tool record.

**Claude Code** has two rules. A file that holds any `system` `turn_duration` record uses
the marker rule; any other file, written by versions older than the marker, uses the
derived rule. Every `turn_duration` in 200 recent files followed a `stop_hook_summary`
whose `hookErrors` was empty. The 34 summaries with `hookErrors` were never followed by
one: the blocking Stop hook made the model continue.

Both rules sort records into three kinds:
- **Input records.** `user` records that are neither only tool-result blocks nor
  `isCompactSummary`, and `system` `local_command` records. These are human, injected and
  dispatch prompts, local commands and their output, and the interrupt marker.
- **Response records.** Assistant records and tool outputs.
- **Everything else.** Attachments (including queued messages), `system` markers,
  metadata and copies. These belong to the turn they fall in.

**The marker rule:**
- **End.** A turn ends at a `turn_duration` record, or at an interrupt marker that follows
  its response. A `turn_duration` with no turn open ends nothing. Of 1,284 live
  `turn_duration` records, 3 followed an `isMeta` record that got no response rather than a
  summary (review). Under this rule they end no turn, because inputs without a response
  form none.
- **Start.** The next turn begins right after that end, or at the file's start. Its inputs
  are the input records between the end and its first response record.
- **`isMeta` records at a turn's opening.** An `isMeta` `user` record counts as an input
  only there, so a scheduled task's reminder, an `isMeta` peer message or a reminder after a
  local command can trigger a turn.
- **`isMeta` records mid-turn.** Inside an open turn an `isMeta` record belongs to that
  turn and never ends it. Two kinds are common: the record a Skill load writes after its
  tool result (it carries `sourceToolUseID` and the turn's `promptId`), and a blocking Stop
  hook's feedback.
- **No end marker.** A response followed by an input record that is not `isMeta`, with no
  end marker between them, ends the turn there, with `status_basis` `no_end_marker`.
- **Stop-hook continuation.** Live, it runs in this order:
  1. an `end_turn` message;
  2. the `isMeta` feedback record;
  3. a `hook_blocking_error` attachment;
  4. a `stop_hook_summary` with `hookErrors`;
  5. more model activity.

  No `turn_duration` comes until the turn really ends. All of it is one turn, and the
  first message is commentary.
- **Simulation.** The review ran this rule over 118 marker files and got:
  - 930 turns;
  - 10 `no_end_marker` splits, none at an `isMeta` record;
  - 13 `isMeta`-triggered turns;
  - a final for 492 of 493 human-triggered turns.

**The derived rule:**
- **Start.** A turn starts at the first input record after a response record, or at the
  file's first input record. An `isMeta` record is not an input under this rule.
- **End.** It ends before the next input record that follows a response record.
- **Interrupt marker.** A marker right after a response belongs to that turn and ends it.

**In both rules:**
- **Responses without opening inputs (R28, R33).** A run of responses still forms a turn,
  as in an SDK capture or resumed tail. Its `trigger` is `null`, its opening `inputs` are
  empty, and its ref is its first response line, never an invented input or metadata
  line. Any queued in-turn human attachment is still listed in `inputs`. The marker or
  derived rule decides its end and §9.3 decides its status normally; the derived rule
  never closes on `turn_duration`.
- **Queued messages.** A queued human attachment inside the turn is listed in `inputs`. It
  never becomes the trigger.
- **Interrupt markers.** The next turn starts at the first input after an interrupt marker.
- **Interrupted before any response.** A prompt followed by a marker with no response
  forms a turn of its own: `interrupted`, with no final.
- **Message grouping.** Claude writes one record per content block. A message is the set of
  assistant records sharing a `message.id`, and `stop_reason` is read per message. In
  42,303 live messages, no two records of one message disagreed on it (review).

**The trigger,** for both harnesses, is chosen from the turn's opening inputs, the run
before its first response record. It is `null` when that run is empty; otherwise it is
the first of these that exists:
1. the last `human` or `dispatch` input that is not a local-command record;
2. else the last `injected` input that is not a local command's output;
3. else the last local-command input.

**When a run of inputs is not a turn.** A run of inputs with no response is a turn only in
two cases:
- it ends the file and its trigger comes from 1 or 2. Such a turn is `incomplete`;
- it is the interrupted case above.

A local command followed by nothing is not a turn.

**What the fixture gives.** CA has no markers, so it uses the derived rule. A task
notification and a slash command with no response between them (`CA:14`, `CA:15`) form one
turn, triggered by the human `CA:15`.

### 9.2 Final versus commentary

| | Codex | Claude Code |
|---|---|---|
| Final | the assistant message with `phase` `final_answer` (basis `phase`); else the last assistant message whose text equals `task_complete.last_agent_message` (basis `last_agent_message`); else that event's text itself, with the event's ref (basis `last_agent_message_event`) | the text blocks of the turn's last non-synthetic message, when that message stopped for `end_turn` or `stop_sequence` and has text (basis `stop_reason`); an earlier `end_turn` message is never final. In a turn with no `stop_reason` on any record, the last text-only assistant record (basis `position`, weaker) |
| Commentary | every other assistant message of the turn | every other assistant text of the turn: text in messages that stopped for `tool_use`, and an `end_turn` message followed by more activity in the same turn (a Stop-hook continuation, §9.1) |

**Absent fields.** An absent `last_agent_message` is treated as null. That is the shape of
XA and XW.

**Synthetic records.** A `<synthetic>` assistant record is never final and is never a
runtime model.

**Live evidence on 2026-10-23.** The probes read only record keys and values.
- **Codex:** in 60 recent rollouts, every assistant message had a `phase`: 890
  `commentary` and 112 `final_answer`. The 112 `task_complete` events each held a
  `last_agent_message` string.
- **Codex in June:** 109 of 678 `task_complete` events in 40 files had a null message.
- **Claude:** in 60 recent transcripts, every assistant record had a `stop_reason`
  (`tool_use`, `end_turn`, or once `stop_sequence`). `origin.kind` took the values
  `human`, `task-notification` and `peer`.
- **Claude, grouped by message:** in 200 recent files, 551 of 1,820 `end_turn` records had
  no text block, but no `end_turn` message did.

The session-logs skill says there is no `stopReason` and that a turn ends where the next
human record begins. That misses `message.stop_reason`, which marks a turn's end.

### 9.3 Status

The first row that applies decides a turn's status.

| Status | Codex | Claude Code |
|---|---|---|
| `interrupted` | `turn_aborted` (with its `reason`) | the interrupt marker after the turn's response; a prompt interrupted before any response (§9.1); or an interrupted tool result |
| `waiting` | the turn's last call is an unanswered `request_user_input` | the last message's pending call is `AskUserQuestion`, `EnterPlanMode` or `ExitPlanMode` with no result |
| `completed` | `task_complete` and a final message (§9.2) | a final message (§9.2) |
| `no_final` | `task_complete` with no final message | the turn closed, by a `turn_duration` or by the next input, without a final message: its last message stopped for `end_turn` with no text, or for `tool_use` with every result present, or only synthetic messages ended it |
| `incomplete` | `task_started` with no end before end of file or before the next `task_started` | end of file with no final message and no closing message; a live session can still append |

**Codex turns need their closing event.** `completed` and `no_final` both require the
turn's `task_complete`. A turn that ends without one is `incomplete`, even when it holds a
`final_answer` message. That covers a turn that runs to the end of the file and one cut
short by the next `task_started` (§9.1). Its `final_answer` message then appears as
`last_assistant`, not as `final`.

**A Claude turn at the end of a file.** A Claude turn's final `end_turn` message closes it,
so it is `completed` even when no `turn_duration` follows yet. Its `status_basis` is
`no_end_marker_eof`. A live session can still append a Stop-hook continuation, and a later
run then reads that message as commentary.

**Which message is final.** Only a `completed` turn has one. For every other status, the
turn object carries `last_assistant`, the last thing the assistant said, which is never
labelled final.

**What final messages exclude.** An injected or dispatch trigger is never human. A turn it
starts is listed with `trigger.role` showing that, so a final message in such a turn is
never attributed to a human request.

**Questions and waits.**
- **Codex questions.** A final message whose `AgentMessage` item carries `questions` is
  asking the user. Its turn is still `completed`, with `asks_user: true`. Of 9 such turns in
  80 recent rollouts, 8 ended in `task_complete` with the message, and 1 was aborted.
- **Codex `waiting`.** It applies only to the older `request_user_input` call, which no
  recent rollout used, so it is unobserved.
- **Claude `waiting`.** The wait tools are the set `session-episodes` uses. A pending one at
  the end of a turn is rare: 1 of 93 `AskUserQuestion` calls in 600 files (review). The
  live-store run reports each tool's count.

### 9.4 Selection by task

`--task ID` reads the task through `tasks show ID --json`, never its file. The two sources
are:
- `notes[]`: each entry has `at`, `harness_session` (`<harness>:<id>`), `harness_session_source`
  and `text`;
- the index's `task_commands` rows for the task.

It gathers evidence of these kinds, strongest first:

1. **`provenance_stamp`.** A stamped note, lifecycle or ordinary, whose `harness_session`
   names the session. The ref is the task id with the note's `at`.
2. **`successful_task_command`.** A `task_commands` row with `status` `ok`. The verb is the
   one obs records: `start`, `park`, `done`, `drop`, `review`, `concerns`, and so on.
3. **`unsuccessful_task_command`.** The task command was attempted and did not succeed.
   Both of these must hold:
   - the call's command is exactly one segment, the `tasks` command itself, by obs's
     `shell_clear.chain`, imported unchanged;
   - its result is an error: a Claude result marked `is_error` (basis `result_is_error`),
     or an indexed `failed` row (basis `index_status`).

   It does not say whether `tasks` refused the command or something stopped it first, such
   as a hook denial. SL2's `CA:4`/`CA:7` is the hook case. It is an attempt, not
   ownership.
4. **`task_command`.** Every other row, with the index status and the paired result's error
   flag recorded. That includes:
   - an `unknown` row;
   - an error in a chain;
   - an indexed `failed` row whose command is a chain.

**Why a chain's error is uncertain.** A chain's result belongs to the whole chain, and no
store records the `tasks` segment's own result.
- `false && tasks start <id>` fails without running `tasks`.
- `tasks start <id> && false` fails after `tasks` succeeded.

obs marks a row certain for any all-`&&` chain and gives it the call's status
(`call_evidence.py:220`, `:256`). Its `ok` is therefore sound, because every segment ran
and succeeded. Its `failed` on a chain is not, so the reader trusts `failed` only for a
single segment.

**Why Claude rows are mostly `unknown`.** On 2026-10-23 live Claude rows were 1,223 `ok`
and 3,478 `unknown`, with none `failed` (review).
- **Chains.** Most `unknown` rows (2,827 calls) are successful commands in chains that are
  not all `&&`, which obs cannot attribute.
- **Errors.** 92 calls returned errors; 10 of them were single `tasks` segments.
- **Consequence.** Most Claude lifecycle commands are tier 4, so Claude ownership evidence
  rests mainly on stamps.

**What counts as ownership.** Only 1 and 2 are ownership evidence; 3 and 4 select the
session and are labelled.

**Mentions.** A `textual_mention` (the id in any text) selects a session only under
`--mentions`. It is never ownership evidence (SL2, SL7).

**Bounded mention listing (R44, R48).** Under `--task --mentions`, additional mention-only
files are listed from the later of `--since` and the task's earliest time (`created`, or
its earliest note). Files with older mtimes and missing files whose indexed span ends
before that bound are skipped. Coverage reports the bound as `task.mentions_since`.
This bounds extra file discovery, not ownership: the evidence-selected sessions are still
read, and a mention in a selected file is still only a mention. It replaces an unbounded
store scan that the final review identified as a roughly 25-minute invocation.

**Without the index,** only stamps are found, and coverage says so.

**Turn and session level.**
- A turn carries the evidence that falls inside its span: the note's time, or the
  command's call.
- Its session's other turns carry `task_evidence: session`.

**Sessions this misses.** A session that worked on the task without a recorded command or
a stamped note is not found this way. A reviewer child is an example. It is reached from a
selected session with `show --links`.

### 9.5 Listing and printing

- `search --final` lists turn objects. It takes `--session ID`, `--task ID` or a window.
- `show <record ref>` prints a whole turn: its trigger, every record with its pairing, its
  status and its final message.
- `show <session> --turn` prints every turn of a session.

Together these cover listing and printing final messages by session, task and time window.

## 10. Links and models

### 10.1 Recorded links

| Link | Recorded where | Basis |
|---|---|---|
| Codex `child_to_parent` | the child's first `session_meta`: `source.subagent.thread_spawn.parent_thread_id` (SL3 `XC:1`); the index's `parent_session` corroborates | `native_metadata`, `index` |
| Codex dispatch binding | in the parent, the spawn call (`XP:7`) and an `item_completed` `SubAgentActivity` item whose `id` equals that `call_id` and whose `agent_thread_id` is the child (`XP:8`); 90 of 90 live spawns bound this way (review) | `native_metadata` |
| Claude `parent_to_child` | the launch result's `toolUseResult.agentId` (`CA:12`) and the child's `subagents/agent-<id>.jsonl`; the child's `.meta.json` `toolUseId` names the dispatching call | `native_metadata`, `path` |
| Claude `child_to_parent` | the child's `subagents/` path under the parent's session directory; the index's `parent_session` corroborates | `path`, `index` |
| `sdk_dispatch` | an event's `parent_tool_use_id` names a dispatching call (SL9) | `native_metadata` |

**What is never a link:**
- `parentUuid`, which threads messages;
- `turn_attribution.parent_turn_id`, a turn pointer;
- `session_id` in a Codex child's `session_meta` (inherited; at depth 2 it names the root,
  not the controller);
- a parent id printed in tool output (SL8).

**When the native record and the index disagree,** both are reported.

**No binding.** If a Codex parent has no binding for a child, the child's dispatch brief is
reported unavailable. The parent's text is never substituted without the binding (SL7).

### 10.2 Turn models

A turn object lists the runtime models of its records:
- Codex: the turn's `turn_context.payload.model`;
- Claude: the non-synthetic assistant records' `message.model`.

### 10.3 Model bases

| Value | Basis |
|---|---|
| Codex `turn_context.payload.model` | `runtime`, per turn |
| Codex `session_meta` `base_instructions.provenance.model` | `creation`; never reported as runtime (hq-7b131a: 176 of 400 recent rollouts differ) |
| Codex spawn arguments' `model` | `requested` |
| Claude `message.model` on non-synthetic assistant records | `runtime` |
| Claude `requestedModel`, the dispatch input's `model`, `.meta.json` `model` | `requested` |
| Claude launch result `toolUseResult.resolvedModel` | `resolved`; what an alias resolved to, not proof of what ran (SL3) |

## 11. Trial gate and staged rollout

**Dates.** flow-trial-1 enrols units first started between 2026-10-05 and 2026-11-29. They
close by 2027-01-10, follow-up runs to 2027-02-09, and readout is 2027-02-16. hq and obs
are both enrolled.

**The gate.** It holds every migration step that changes treatment (what an enrolled
session sees and does) or measurement (what obs and the verdict tools read) until readout
(ops-630a87 r4, change 5).

### 11.1 The measurement path

- **`trial-arm census`** reads task records through the `tasks` CLI, and lists records by
  status.
- **The obs report.** `trial-verdict` reads `obs --json outcomes report`, which reads only
  outcome tables that `obs index` derives. Those tables come from obs's adapters, store
  discovery and index derivations.
- **`session-episodes`** feeds only `obs baseline`, a manual count no verdict reads.

The planning documents nevertheless list `session-episodes` as measurement. This design
leaves it unchanged before readout and does not settle that dispute.

### 11.2 Stage A: before readout, neither treatment nor measurement

**What Stage A adds:**
- **The reader in obs.** New files: the `session_logs.py` entry point, its modules, their
  tests and the vendored fixture copy.
- **hq's fixture step (§14.3).** Test data only.

**What Stage A edits.** Files no index, report or timer runs:
- the justfile: the list of modules its `check` recipe compiles, and a recipe that
  re-vendors the fixtures (§14.5);
- `.gitignore`, to re-include the vendored fixtures' dot-directories, as hq already does;
- the obs task's own record under `tasks/`.

**Module names.** Every new module is named `session_logs*.py`. The systemd unit runs
`obs.py` with the checkout first on the import path, so a new name must not shadow a
standard-library or existing obs module. This prefix guarantees it does not.

**Treatment, edit by edit.** Each edit above was also judged for treatment:
- The tests, fixtures, compile list, vendoring recipe and ignore rule say how to test the
  reader. None tells a session to use it.
- The new files can be found in obs's tree, as any file can, in either arm.
- A README section on the reader would be a general aid, the thing the brief rule below
  forbids. It waits for Stage B1.

**What Stage A must not modify:**
- any existing `.py` module in obs, including `obs.py`, which the systemd index unit runs
  from the main checkout, the adapters, `index.py`, `stores.py`, the outcome modules and
  `baseline.py`;
- the systemd units;
- the shared CLI table.

**What Stage A reuses:** obs's functions are imported, not changed:
- `stores.store_roots`;
- `index.open_index_readonly`;
- `index.read_snapshot`;
- `shell_clear.chain`.

**What Stage A restates.** Importing `obs.py` would pull in its whole module graph. So the
reader restates the three-line state-directory rule of `obs._state_dir`, and a test imports
`obs._state_dir` to show the two agree. The review found no import-time side effects in
`stores` and `index`; the plan checks `shell_clear` the same way.

**What Stage A leaves alone:**
- no skill, instruction, flow, hook or link;
- no write to any store or to obs's state directory;
- no move of an enrolled task record. `trial-arm` cannot follow a `moved` record (D6). That
  is why this design files new tasks instead.

**Who may name the reader before readout.** The reader is reached by explicit path
(`python3 <obs checkout>/session_logs.py …`). It is named only in the briefs of tasks whose
subject it is:
- this unit;
- the obs task that builds and verifies it;
- hq-b95324's re-scope against this design.

Whether a brief names it follows from that subject, never from the task's arm. It is not
added to other briefs as a general aid. The review noted why: flow-on controllers would
otherwise be the ones naming it.

**Gate evidence before the obs task merges:**
- `git diff --stat` against its base lists only added `session_logs*` modules, tests and
  vendored fixtures, plus the edits above;
- obs's `just gate` passes;
- hq's `just test` passes on the fixture step.

With no executed module changed, the index and the reports run the same code.

### 11.3 Stage B: after readout

Each step re-checks the gate on its date.

- **B1. The skill, link and README.**
  - The session-logs skill is rewritten around the reader (§12).
  - `~/.agents/bin/session-logs` is declared in hq's `links.toml`.
  - obs's README gains its section on the reader.
  - The skill moves to obs with obs-f5710b.
  - The reader joins the shared CLI table as a protocol row when the obs CLI takes it.
- **B2. One classifier, and a first-seen stamp.**
  - The adapters and `session-episodes`, moved to obs by obs-f5710b, use the reader's
    normalizer.
  - obs's index gains a first-seen stamp per file that no re-read moves. The coverage
    start (§5.3) then stops moving later, and older Codex sessions can answer
    `not_found`.
  - The extractor stamps bump and pruned files are replayed (hq-d70879).
  - The reader's classifier version retires.
- **B3. Roots from hq's home registry** (hq-19580c, obs-081ded) for the index and the
  reader together. The profile rule of §5.1 retires.

### 11.4 Related work under the same gate

- **hq-7b131a**, a "Which model ran" skill entry, is a skill-text change. It is a treatment
  change under the same gate. Stage A's model bases (§10.3) supply its answer without a
  skill change.
- **hq-a60cf5** changes `session-episodes`' roots. That is measurement-neutral in code
  (§11.1). The planning documents treat episodes as measurement, so it needs its own gate
  assessment.

Both stay their owners' work.

## 12. Usage skill (Stage B1)

The rewritten session-logs skill leads with the reader and keeps the store and record
reference as background. Its sections:

1. **Question → command.** One recipe per surveyed question type, each a `search` or
   `show` invocation: formats, behavior, identity, inventory, recovery, aggregates,
   origins.
2. **Reading coverage.** `unknown` is not `not_found`; absent roots; missing files and
   their routes; a stale or absent index; a second host is a separate run.
3. **Evidence strength.** A provenance stamp or successful task command over a tool-output
   match, over a tool-call match, over a mention. A mention never establishes ownership.
4. **Models and links.** Runtime versus creation, requested and resolved; which links are
   recorded and which fields only look like links.
5. **Handling.** Refs are local handles; never paste output publicly; `--raw` only for
   schema questions.
6. **Pre-flow episodes.** The existing `session-episodes` section, until obs-f5710b replaces
   it.

The skill's description names search and show, so it triggers on the seven question
types, not only on episode preparation.

## 13. Out of scope

- An interactive picker or resume. `hq sessions` keeps both, with its own
  interactive-only selection.
- A new transcript index or full-text table (lane hq-65f661).
- Aggregate verbs.
- A trace verb, and any claim about automated trace precision. A later trace composition
  (obs-c5c599) keeps typed evidence: a mention stays a mention, and a child reaches its
  parent only through a recorded link.
- Remote access, archive materialization, and any write to a store.
- opencode, Crush (obs-175b10) and pi session stores.
- Changing obs's adapters, store discovery, index schema or `session-episodes` before
  readout (§11).
- The existing work of hq-a60cf5, hq-7b131a, hq-c1fecb and hq-edf5de.

## 14. Acceptance

### 14.1 The existing cases

The reader passes each case by replaying the fixtures with `HOME` set to a scratch copy,
as `materialize()` does. Commands are shown without `--all-time`, which every fixture query
passes because the fixtures are dated, unless its row names a `--since`. "Synthetic" marks a shape no cited episode
exercised (cases doc).

| Case | What the reader must return | Command shape | Basis |
|---|---|---|---|
| SL1 | Five calls, each paired by id with its result, including the reversed pair `CA:6`/`CA:7`. One message, `msg_fx_m1`, spans blocks 0–2. Runtime model `claude-model-a`. `CA:10`'s blocks are `request_blob` copies, collapsed and counted (shown with `--copies`). `CA:16` is `unknown` in the unfiltered stream. `CA:13` is `metadata`. | `search --session CA --no-limit` | observed; the blob and the unknown kind are synthetic |
| SL2 | `show CA:4#0` gives the call paired with the `tool_output` `CA:7#0` (`is_error`). `CA:8#0` is paired with `CA:9#0`. `CA:2` is `injected`, `CA:10` a collapsed copy, and `CA:14` `injected`. Human records are `CA:1` and `CA:15` (basis `origin`). `--task zz-000001` gives `CA:8` as `successful_task_command` (the index row is `ok`) and `CA:4` as `unsuccessful_task_command` (a single `tasks` segment; the index row is `unknown`; basis `result_is_error` from `CA:7`). | `search zz-000001 --session CA`; `show CA:4#0`; `search --session CA --role human`; `search --task zz-000001 --sessions` | observed shape |
| SL3 | XC: runtime `codex-model-b` (`XC:3`, turn `turn-c1`), creation `codex-model-a` (`XC:1`), requested `codex-model-b` (`XP:7`). Controller XP by `child_to_parent` from `XC:1`. Identity from `payload.id`. AG: runtime `claude-model-b`; `sonnet` requested; `resolvedModel` resolved, from CA's binding records. | `show XC --links`; `show agent-a0000000000000b01 --links` | observed, depth 1 |
| SL4 | `/w/beta`: CW and CW2 in `claude-work` (work), XW in `codex-work` (work). XA has `store: archived`. Coverage: five roots searched, `codex-work` archive absent. | `search --sessions --cwd /w/beta`; `show XA` | observed; the Codex-work session is synthetic |
| SL5 | `XA:5` is `human`, and `XA:4` appears only under `--role injected`. `CW:1` is human. `CW2:1` is a `resume_history` copy of `CW:1`, collapsed. `CW2:4` is a distinct human turn. | `search '<phrase>' --role human`; `search '<phrase>' --role injected` | observed; archived placement synthetic |
| SL6 | Three outputs, `CW:3#0`, `CW:6#0` (`is_error`) and `CW2:6#0`. `CW:7#0` (blob) and `CW2:3#0` (resume) are collapsed copies. `CW:4` is `injected`, not output. | `search test-fast --profile work --role tool_output --no-limit`, then `jq` | observed |
| SL7 | The filing output `XC:6` for call `XC:5`. Controller XP (`XC:1`). Human trigger `XP:6`, with `XP:4` and `XP:5` as injected inputs. Dispatch bound by `XP:7` and `XP:8`. `XC:4` is an encrypted dispatch. `XP:13` is `assistant`; `CA:17#0` and `CA:18#0` are a call and its output; `CA:15` is human. | `search zz-0000f1`; `show XC --links`; `show XP:6` | observed; the parent's plain brief is synthetic. The verdict "XC filed it" is the trace composition's (§13): the reader supplies each link with its basis |
| SL8 | `parent_to_child` from `CA:12` to AG; `.meta.json` `toolUseId`. AG's `last_at` 12:02:40Z, `CA:13` at 12:02:41Z, `CA:14` at 12:03:00Z. `AG:1` is `dispatch`. AG's identity is `agent-a0000000000000b01`. No link from `parentUuid`, `XC:2` or XP. | `show CA --links`; `show agent-a0000000000000b01` | observed; the human-origin command synthetic |
| SL9 | Child calls `SDK:4` and `SDK:5` carry `sdk_dispatch` to `toolu_fx_dA` and `toolu_fx_dB`. Results are `SDK:7#0` and `SDK:6#0` (`is_error`). `SDK:8` and `SDK:9` are root events. No session link. | `search --file <capture> --role tool_call --role tool_output` | observed |
| SL10A | Zero parsed matches. Unparsed `CD:2` (malformed) and `XD:3` (truncated), each with `raw_match`. CU unreadable. Three roots searched, three absent. Index absent. Outcome `unknown`. | `HOME=<degraded> search needle-term` | observed failures; unreadable file synthetic |
| SL10B | CF has no candidate and no index, so it is unavailable and the outcome is `unknown`. `CD:3` is an `assistant` mention. The clipped command is never presented as recovered. | `show CF`; `search 'rm -rf'` | observed |

### 14.2 Location and outcome controls

The obs-side tests build a temporary index over a fixture copy with `obs --state-dir <tmp>
index`. They do not change any index code. Each control is synthetic; this table says what
the live data did and did not show.

| Control | Test | Live evidence |
|---|---|---|
| O10, Claude: one session, its children | `show CA` lists CA as `own` and AG as `child`, by path and by the index's `parent_session`. `show agent-a0000000000000b01` finds AG as `own` | obs-b99310 removed the old shape, child files holding rows under the root's id; children are now keyed `agent-<id>` (4,361 live child rows, review) |
| O10, Codex: rows under another id | `show XP` lists XC as `child` through the index. The test records which fixture shapes index inherited rows under another id, and checks that such files are `child` or `inherited` by their native `payload.id` | the shape remains wherever obs attributes inherited Codex records to an inherited id |
| M01: missing file with a readable alternate | A rollout is copied into `archived_sessions/` and indexed, then the live copy is deleted. The reader reports two candidates: one `missing`, one `readable`. It reads the alternate. | Observed once (M01) |
| A01: native archive | XA is read from `codex:archived_sessions/…` with `store: archived`. | Observed (A01) |
| Replayed copy | A file is indexed, deleted, and replayed with `obs --state-dir <tmp> index --replay <archive copy> <root>`. The reader reads `read_path` with `store: replayed`. When the copy is then made unreadable, it reports `missing`, names the copy, and gives `unknown`. | **Unobserved live**: zero `read_path` rows on 2026-10-20 |
| Escaped text | An explicit file whose record holds `"\u006eeedle"` gives `found` for `needle`. A malformed line holding the same escape is an `unparsed` object with `raw_match` true, and the outcome is `unknown`. | the reviewer reproduced the decoding mismatch (round 4) |
| `not_found` | A fresh index over the home, and a term in no record, gives `not_found` when the search is scoped to a home with nothing unreadable or missing and run with `--since 2026-10-01`. The test sets the temporary index's file stamps to 2026-09-01, so the window lies inside its coverage; the test owns that index. The same term over an explicit file also gives `not_found`. | none needed |
| Stale index | The same query, with the temporary index's last complete run aged past 2 hours, gives `unknown` with basis `stale_index`. | none needed |
| Before the index's coverage | The same query with `--all-time`, or with a `--since` earlier than the root's coverage start, gives `unknown` with basis `before_index_coverage`. | the live coverage starts: 2026-09-18 for the Claude roots, 2026-10-20 for the Codex roots (review) |
| A host without an index | No state directory: index `absent`, the native walk proceeds, a zero match gives `unknown`. | Observed (the second host, 2026-10-20); cross-host retrieval itself was not qualified and stays an explicit run |
| Change during a run | A file deleted between listing and reading is `vanished`. A rollout moved to `archived_sessions/` in between is found there. A file whose indexed prefix is rewritten is `changed`. The reader takes a test hook between listing and reading so the test can make these changes. | none |

### 14.3 New case SL11: turn-final messages and task evidence

**What hq adds.** Fixtures, a section in the cases document and self-check assertions, in
the existing style. The fixtures use live shapes:
- Claude: `stop_reason`, `origin.kind`, message grouping by `message.id`, queued
  attachments and local commands;
- Codex: `phase`, and `item_completed` mirrors.

**Claude, one session with `turn_duration` markers (the marker rule):**
1. A typed human turn: commentary text, then a tool call, then a final message whose
   thinking and text blocks are separate records of one message, then
   `stop_hook_summary` and `turn_duration` (`completed`).
2. A local command written as a `system` `local_command` record, its output, then a typed
   prompt. They form one turn, triggered by the prompt.
3. A turn with a queued human attachment mid-response. It is listed in `inputs` and is not
   the trigger.
4. A Stop-hook continuation in the live order: an `end_turn` message, the `isMeta` feedback
   record, a `hook_blocking_error` attachment, a `stop_hook_summary` with `hookErrors`, more
   activity, then a final `end_turn` message and `turn_duration`. It is one turn; the first
   message is commentary.
5. A Skill load mid-turn: the Skill call, its result, then the `isMeta` record carrying
   `sourceToolUseID` and the turn's `promptId`, then more activity. The turn keeps its human
   trigger and its final.
6. After a `turn_duration`, an `isMeta` scheduled-task reminder that gets a response: a
   turn of its own, with trigger `injected` and its own final. The preceding human turn
   keeps its final.
7. The same with an `isMeta` peer message.
8. A turn ended by the interrupt marker (`interrupted`, with `last_assistant`).
9. A prompt interrupted before any response: a turn of its own, `interrupted`, with no
   final.
10. A turn whose last call is `AskUserQuestion` with no answer (`waiting`).
11. A turn whose only end is a `<synthetic>` `stop_sequence` message (`no_final`).
12. A task-notification turn with its own final: trigger `injected`, `completed`.
13. A final turn cut at end of file with a call pending (`incomplete`).

The existing CA fixture covers the derived rule for files without markers.

**Codex, a parent rollout and its child:**
- a turn with `commentary` and `final_answer` messages and their `AgentMessage` mirrors;
- a final message with `questions` (`completed`, `asks_user`);
- an aborted turn;
- a turn whose `task_complete` has a null `last_agent_message` (`no_final`);
- a phaseless turn whose final is found by `last_agent_message`;
- a `task_started` followed by another with no end between them (`incomplete`);
- a `task_started` at end of file (`incomplete`);
- in the parent, a child's report `agent_message` (`injected`); in the child, its
  controller's `agent_message` (`dispatch`);
- a final `final_answer` message followed by another `task_started` with no
  `task_complete` between them: `incomplete`, with no `final` and the message as
  `last_assistant`.

**Codex, a fork whose parent rollout is absent and which holds only copied history:**
- every record after its second `session_meta` is `copy: ambiguous`;
- its turns carry `copy: ambiguous` and no `final`;
- the copied parent's final answer appears only as `last_assistant`.

**Task evidence:**
- One session's stamped note names it, giving `provenance_stamp` for the turn holding the
  note's time.
- A second session only mentions the task id. It is selected only under `--mentions`.
- Three failing calls in a third session:
  - `tasks start <id>` alone with an error result: `unsuccessful_task_command`;
  - `false && tasks start <id>` with an error result: `task_command`;
  - `tasks start <id> && false` with an error result: `task_command`.
- The task record reaches the reader as a `tasks show --json` document captured from the
  real CLI over a scratch project, served by the wrapper of §14.5. The field path is
  therefore the live one, not this spec's. hq keeps the captured document with the
  fixtures.

**Expected:** each turn's status, final ref and basis; commentary never final; the
injected trigger labelled; the mirrors collapsed; and the selection and labels of the two
sessions.

**Unchanged:** the existing fixtures. Their limits stay with hq-c1fecb (§14.6).

### 14.4 Live-store run before verification

The reader runs over every record of this host's six roots through its module API, with
output counted by role and kind and never kept. The run reports, without writing anything:
- files, lines, unknown kinds, unparsed lines and elapsed time;
- any exception, which is a failure;
- the pending-at-turn-end count of each wait tool (§9.3);
- the time and the outcome of an unqualified default-window search, with its count of
  missing files in scope.

It reports each root's coverage start (§5.3).

It also checks four live cases:
- **Model bases.** One divergent Codex child, whose runtime and creation models must
  differ (hq-7b131a).
- **Candidates.** One audited origin from the index probe, whose candidates must agree with
  that probe's case ledger.
- **Task evidence.** `search --task hq-c411df --sessions` must list the sessions that this
  task's stamped notes name. This checks the `notes[]` field path against the real CLI.
- **Forks.** For a sample of live forks whose parent rollout is present, the copied range
  must end where the parent's turn ids end, and the fork's own turns must keep their own
  finals. Then each sampled fork is copied alone into a scratch home, without its parent.
  There, its whole range must come out `ambiguous`, with no finals.

### 14.5 How the tests run

- **Fixture vendoring.** obs vendors hq's `tools/fixtures/session-logs/` under its test
  fixtures. A source file names the hq commit and each file's sha256, a test checks the
  copy against it, and a justfile recipe re-vendors. The corpus stays hq's, as the boundary
  assigns.
- **Environment.** Each subprocess test builds its environment key by key and never
  inherits the caller's:
  - `PATH`;
  - `HOME`, the scratch fixture copy;
  - `XDG_STATE_HOME` and `XDG_CONFIG_HOME`, scratch directories.
- **A real `tasks`, isolated.** `obs index` calls `tasks list`, `tasks projects` and
  `tasks resolve`; a stub answering only `show` would leave its run incomplete. So the
  tests use the real `tasks` CLI over a scratch registry holding a `zz` project. A wrapper
  first on `PATH` answers every `tasks show` of a fixture task id from the captured document
  (§14.3), with or without `-C`, and passes every other call to the real CLI. That includes
  the `tasks -C <checkout> show <id>` calls `obs index` makes, so the index and the reader
  see the same record.
- **Test first.** Tests precede the code they cover. Each new test is seen to fail against
  a targeted break of what it checks.

### 14.6 Fixture limits

hq-c1fecb's corrections landed with hq 30717ad, merged at a569687: depth-2 child XG,
Claude's separate `session_id`, compact spawn JSON and live Bash failure prefixes.
Stage A vendors the resulting corpus at hq 61a9604. SL11 supplies readable-parent XF and
parent-unavailable XK; the latter's invalid ordinal does not qualify a usable native
boundary. Mid-parent copies and no-copied-`task_started` shapes were measured live, not
added to this fixture corpus (§14.7).

### 14.7 Stage A evidence and amendment decisions (2026-10-26)

**Sources.** obs-d98663's attached `sdd-ledger-portable.md` (R1–R48) and
`live-sweep-summary.txt`; its retained `live/live_run.py`, `live/case-forks.json` and four
`live/sweep-*.json` slices. hq-28baf9 verified their retained manifest and every entry
before using them. The raw ledger's SHA-256 is
`4ee9e37e4643476e87b626fdb0ae978f85755590b98c1e13c48611731be0c1cd`; the manifest's is
`5bf30ddd1c34123fdd2f9dec293074e9eddf55497ffbf619da9cb9b684289671`.
The portable ledger substitutes a storage-root placeholder; it is not the raw bytes.

**What ran.** The full six-root sweep counted 25,563 files, 35,380,838,844 bytes
(33.0 GiB), 10,903,272 physical lines and 11,595,151 normalized records, including
copies. It saw zero exceptions and 27 malformed Codex lines. Counts include repeated
history, so they are not counts of distinct conversations or errors. The four slices
reported 1,357.5 seconds in total (the task note rounds the overall run to 1,359 seconds);
two used reader 271864d and two 9ed18da while corrective
edits were present. They are evidence for those runs, not a sweep of the final merged
tree. The merged Stage A reader is obs 062b73e.

All four §14.4 live cases passed: divergent model bases, 20 audited origin candidates,
three stamped sessions for hq-c411df, and 20 sampled forks, connected and copied alone.
The default-window search answered `found` in 326.8 seconds, with peak child RSS of
1,796,712 KiB (about 1.71 GiB). The sweep peaked at 4,884,988 KiB (about 4.66 GiB)
on the rollout the task note describes as 1.23 GB: Stage A still holds a file's
normalized records in memory. Per-group ordering bounds the number of groups held, not
an individual file's size. These are measured costs, not performance guarantees.

The Claude roots' coverage started at `2026-09-18T13:33:02.387Z`; the three populated
Codex roots at `2026-10-20T21:00:08.426Z`. `codex-work:archived_sessions` was empty with
no coverage start. The same incomplete-history rules in §5.3 and §6.5 still apply.

**A1 — retain the parent-turn-id fork rule (R11).**
- **Decision:** do not adopt `subagent_history_start_ordinal` as a fallback in this
  revision; reject enabling it solely from the agreement count. The first metadata
  record carried it on 127 of 293 forks in the 0.140–0.149 bucket and all 142 in the
  ≥0.150 bucket; none of the 877 in the 0.110–0.139 bucket carried it. The 269 carrying
  it all agreed, and their recorded versions span 0.147.0–0.164.0. These are observed
  files, not a version-based detection rule.
- **Why:** the live check establishes positive agreement when a parent and an own turn
  exist. It leaves the invalid, conflicting, malformed-line and no-own-turn cases in
  §8.3 unqualified. Retaining the shipped rule makes this amendment's contract replayable
  without claiming that an unimplemented fallback has shipped.
- **Cost:** parent-unavailable forks remain ambiguous, and their own finals remain
  unavailable even when the field could eventually settle them. A later adoption must
  test both native-boundary and parent-derived paths, plus their disagreement.

**A2 — retain explicit unknown kinds (R15).**
- **Decision:** keep the §8.2 inventory as `unknown`; reject reclassifying those names
  from counts alone. Unknown is a kept, searchable record, not a dropped or unparsed one.
- **Why:** the sweep identifies the coverage gap but does not validate the roles, mirror
  relationships or call/result semantics of these shapes.
- **Cost:** roughly 2.1 million Codex records remain unknown, mostly token counts, and
  their JSON can match default searches. Reclassification needs source-shape controls
  and the classifier/version review required by §3 and §8.4.

The remaining amendments specify already implemented behavior: R19/R20 (§4.3, §5),
R26 (§8.3), R28/R30/R33 (§4.4, §9.1), the step-10 target-line correction (§7.2), and
R39/R44–R48 (§4.2, §4.6, §6.3–6.5, §9.4). They do not authorize the deferred skill or
discovery migration. Stage B still rechecks §11's gate after the 2027-02-16 readout.

## 15. Traceability

| Task requirement | Section |
|---|---|
| Bounded search and show; home, harness, date, session and role selection | §6, §7 |
| Normalized and raw records; paired calls; block refs | §4.1–4.2, §6.3, §7.2 |
| Recorded parent links; runtime model per turn | §10 |
| Coverage and unavailable results | §4.6, §5.4–5.5, §6.5, §7.4 |
| obs consumer interface and its owner; research SQL not an API | D1, §3, §5.3 |
| Parsing and location ownership | D1, §3, §8.4 |
| Trial gate and effects on enrolled sessions and measurement | D5, D6, §11 |
| Final messages, commentary, injected records, statuses, task evidence | §9, §14.3 |
| Acceptance cases, location counterexamples, synthetic or unobserved | §14.1–14.2, §14.6 |
| Local-first versus remote or archive | D3, §5.4 |
| Interactive resume kept separate | §3, §13 |
| No picker, index, aggregate verbs or precision claims | D2, §13 |
| Stage A rulings, native-boundary decision and live-kind inventory | §4.2–4.6, §5.2–5.3, §6.3–6.5, §7.2, §8.2–8.3, §9.1, §9.4, §14.7 |
