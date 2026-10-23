# Session evidence reader: `session-logs search` and `show`

Status: draft for review, 2026-10-23
Task: hq-c411df (goal hq-cff824)
Inputs: the store-reach brief (`docs/notes/2026-10-20-session-store-reach-brief.md`), the
session-log survey (`docs/notes/2026-10-20-session-log-survey.md`, hq-de3e4c), the index
reach probe (`docs/notes/2026-10-20-session-index-reach.md`, hq-a1c591), the acceptance
cases (`docs/notes/session-log-acceptance-cases.md`, hq-6e5d88), and the accepted
boundary proposal of ops-630a87 (revision 4, changes 5 and A9/A10).

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
- `show` prints one turn, interval or session with its paired calls, links and models.

Every run ends with a coverage record, which says what was searched and whether an empty
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
is a new obs entry point, `session_logs.py`. It is installed later as `session-logs` (§11).
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
  hq's statement of that contract (§5). obs implements it, next to the index rows it reads.

**D2. Two verbs, typed JSONL, no other surfaces.**
- **Shape.** `search` and `show`, writing one JSON object per line. A record, turn,
  session or unparsed line is one object, and every run ends with one coverage object.
  `--pretty` renders the same objects for a person.
- **Rejected:** a `find` or `locate` verb, a picker, aggregate verbs and a trace verb.
  - Locating is `show <session>` and `search --sessions`.
  - Aggregates are ordinary `jq` over records (SL6).
  - Trace is a later composition over this output (§12).

  The survey found no demand for the others. JSONL is a recommendation for
  interoperability, not a measured preference (survey).

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
- **Claude records.** Classified by `origin.kind` where it is recorded. The leading-`<`
  rule applies only to records that predate the field.
- **Codex records.** Classified by role, phase and the injected-prefix list.
- **Why.** The prefix rule that obs's adapters and `session-episodes` share today loses a
  typed slash command (`CA:15`, SL2). obs's adapters never read `origin.kind`.
- **Before readout.** The reader carries its own classifier. The adapters keep theirs,
  because they are measurement (§10). After readout they re-base on the reader's (Stage
  B2).

**D5. Ship the reader before readout; ship the skill after it.**
- **Stage A, before readout.** Adds the reader as new files only, reachable by explicit
  path.
- **Stage B, after readout on 2027-02-16.** Rewrites the session-logs skill around the
  reader and installs `~/.agents/bin/session-logs`. Both move to obs with obs-f5710b.
- **Rejected: a skill update now with a covariate note.**
  - A skill edit changes what enrolled sessions see.
  - It plausibly acts more on the flow-on arm, whose verified gate sends reviewers to raw
    transcripts.
  - The boundary's change 5 holds such steps until readout and says a covariate note does
    not show the arms stayed equivalent.

  §10 has the full assessment.

**D6. The implementation lives with obs's code.** This task is flow-trial-1 unit
`tack-c411df`, flow on, and is its own unit root.
- **After the spec is approved:**
  1. Move this task to obs with `tasks move`, which keeps its unit and arm.
  2. Write its plan there and file Stage A's obs steps as its children.
  3. File the hq fixture step (§13.3) in hq under hq-cff824, as a dependency of the moved
     task.
  4. Record Stage B on the existing deferred tasks (obs-f5710b, obs-081ded and hq-19580c),
     not as children.
- **Why Stage B is not children:** it cannot close before `close_by` (2027-01-10), and
  children would hold the unit open by construction.
- **Rejected: keeping this task in hq with obs steps as cross-project dependencies.** A flow
  parent derives its phase from its children, and the plan's headings would have no step
  tasks.

## 3. Boundaries

| Concern | Owner | Interface |
|---|---|---|
| Store roots and home names | obs `stores.store_roots`, unchanged, until Stage B3; then hq's home registry (hq-19580c, `hq homes --json`) | function call inside obs |
| Archive capture, prune, replay | hq session-archive; `obs index --replay` writes `files.read_path` | the index row |
| Index rows (files, sessions, missing state, read path, parents, lifecycle commands) | obs | read only, inside the reader; never offered to consumers as SQL |
| Records, roles, copies, turns, final messages, pairing, links, models, coverage | obs (this reader) | the `session-logs/1` JSONL contract (§4) |
| Acceptance fixtures (harness-version store samples) | hq, `tools/fixtures/session-logs/` | a vendored copy in obs, pinned by commit and sha256 (§13.4) |
| Usage skill | hq until obs-f5710b, then obs | skill text (§11) |
| Interactive resume | hq, `hq sessions` | unchanged; separate from this reader |
| Typed trace | a later composition (obs-c5c599) | consumes this reader's output |

**The supported obs consumer interface is the reader's JSONL contract.**
- **Owner.** obs owns it and versions it as `session-logs/1`, a field of the coverage
  record. A change to any field's meaning or name bumps the version.
- **Consumers.** Agents, hq tools and later trace composition read the contract, never
  `index.sqlite`.
- **The research SQL.** The probe's SQL in hq-a1c591 remains research evidence. The locate
  step of §5, with its own tests, replaces it.

## 4. Output objects

Every object has `type`. Optional fields are omitted when they do not apply. `null` means
the field applies but the source does not record it. Objects are written in a
deterministic order (§6.4).

### 4.1 References

- **A ref names one physical line.** It is `<home>:<path relative to the home>#L<line>`, for
  example `claude-work:projects/-w-beta/c0….jsonl#L3`.
- **A block.** A ref to one content block appends `#<block>`, as in `…#L3#0`.
- **Numbering.** Lines count from 1 over physical lines, blank ones included. Blocks count
  from 0. This is the acceptance notation `CW:3#0`.
- **Files outside the stores.** An explicit `--file` input uses `file:<absolute path>#L<n>`.
- **Home names.** These are the home directory's name without its dot (§5.1).
- **No absolute paths in refs.** Refs never hold the user's home path.
- **Line hash.** Each record carries `sha256`, the hash of its physical line including the
  newline. It lets a later reader report a line as changed or unavailable instead of
  silently reading different bytes (survey, "Rechecking the evidence").

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
| `turn` | the ref of the turn's start (§8) |
| `role` | one of `human`, `assistant`, `tool_call`, `tool_output`, `injected`, `dispatch`, `metadata`, `unknown` (§7) |
| `role_basis` | `origin`, `prefix_rule`, `structure` (the record's type or path decides) or `kind` |
| `kind`, `block_type` | the native record kind (`assistant`, `api-request-blob`, `response_item/message`, `event_msg/task_complete`, …) and block type (`text`, `tool_use`, `tool_result`, `thinking`, `input_text`, `encrypted_content`, …) |
| `origin_kind`, `prompt_source`, `phase`, `stop_reason`, `message_id` | the native values when recorded: Claude `origin.kind`, `promptSource`, `message.stop_reason`, `message.id`; Codex `phase` |
| `copy` | `request_blob`, `resume_history`, `fork_history`, `event_mirror` or `duplicate_file` (§7.3), with `original` when the original's ref is known |
| `call` | `{id, tool, peer, is_error, command}`: the call id; the tool name; the paired call or result ref; whether the result is an error (results only); and the shell command, when the input is one |
| `dispatch` | `{kind: "sdk_dispatch", call}` from `parent_tool_use_id`; it names a call, never a session (SL9) |
| `model` | `{value, basis}`; basis `runtime`, `requested`, `resolved` or `creation` (§9.3) |
| `text`, `text_bytes`, `truncated` | the searchable text (§6.2), cut at `--text-bytes`, its full length, and whether it was cut |
| `encrypted` | true when the block's content is encrypted and therefore unavailable |
| `raw`, `raw_truncated` | with `--raw` only: the original line, cut at `--raw-bytes` |

### 4.3 `session`: one candidate file

| Field | Meaning |
|---|---|
| `ref`, `harness`, `home`, `profile`, `store` | the file ref (no line) and its place |
| `session`, `agent`, `identity_basis` | the file's own identity and what established it (§5.2) |
| `relation` | `own`, `child` or `inherited` for a lookup by id (§5.2) |
| `state` | `readable`, `missing`, `unreadable` or `changed` |
| `missing_since`, `read_path` | from the index row (§5.3); `read_path` is home-relative when it lies under a known root, otherwise absolute |
| `cwd`, `entrypoint`, `first_at`, `last_at`, `lines` | header values and extent |
| `links` | recorded links, each `{kind, target, basis, ref}` (§9.1) |
| `models` | every model value the file records, each with its basis and ref (§9.3) |
| `index` | `{state, file_id, current}`; `current` is false when the file has grown past the indexed span |

### 4.4 `turn`: one turn (§8)

The fields are:
- `session`, `turn` (the start ref), `turn_id` (Codex);
- `trigger`, `{role, ref, origin_kind}`;
- `end` (the ref of the last record);
- `status` and `status_basis`;
- `final`, `{ref, text, basis}`, present only when the turn has a final message;
- `commentary` (refs of the turn's non-final assistant text);
- `models` (the runtime values in the turn);
- `calls` (the number of tool calls);
- `task_evidence` (only under `--task`, §8.4).

### 4.5 `unparsed`

A line that is not a JSON object, or a final line with no newline. Its fields are `ref`,
`reason` (`malformed` or `truncated`), `raw_match` (whether its bytes contain the pattern)
and, with `--raw`, its bytes. It is never a record and never has a role (SL10).

### 4.6 `coverage`: the last object of every run

| Field | Meaning |
|---|---|
| `format` | `session-logs/1` |
| `host`, `query` | the host name and the parsed arguments, defaults marked |
| `roots` | per root: home, store, state (`searched`, `absent` or `unreadable`), files, bytes |
| `index` | `{state, schema, last_complete_run}`; state `used`, `absent`, `unsupported_schema` or `unreadable`, with the reason |
| `window` | `since` and `until`, and whether `since` is the default |
| `files` | scanned, skipped by prefilter, unreadable (refs) and missing in scope (refs, with read path and its state); a list longer than 20 is cut and its count kept |
| `lines` | malformed and truncated refs, each marked `raw_match` |
| `copies` | collapsed copies by kind |
| `limits` | the record limit and whether it was hit; the text and raw byte limits |
| `matches` | parsed matches; unparsed lines with a raw match |
| `outcome`, `outcome_basis` | `found`, `not_found` or `unknown` (§6.5) |
| `rules` | the naming rule of §5.1 and the classifier version, so a later reader knows which rules produced the roles |

## 5. Location

### 5.1 Roots, homes and profiles

- **Roots.** The reader reads `stores.store_roots(env)`: two Claude roots and four Codex
  roots, with the same environment overrides the index uses (§3). It neither defines nor
  edits a root list. With `HOME` pointed at a fixture home, the six roots fall under that
  home.
- **Home name.** The root's parent directory name without its leading dot: `claude`,
  `claude-work`, `codex`, `codex-work`.
- **Store.** `archived` for an `archived_sessions` root, otherwise `live`.
- **Profile.** `work` when the home name ends in `-work`, otherwise `personal`. This is a
  stated rule, recorded in coverage. Stage B3 replaces it with hq's home registry.
- **Absent roots.** A root that does not exist is `absent`: a coverage fact, not an error
  (SL4).

### 5.2 Candidates and identity

A lookup by id (`show <id>`, `search --session <id>`) collects every candidate file from
two sources. The reader keeps every candidate and never silently picks the first one.

- **Native.**
  - Claude main file: `<root>/*/<id>.jsonl`.
  - Claude child: `<root>/*/*/subagents/agent-<id>.jsonl`.
  - Codex: `<root>/**/rollout-*-<id>.jsonl`.
  - Matching is by directory entry, never by a computed slug, as `hq sessions` already does
    (discovery contract).
- **Index.**
  - Rows whose `sessions.session_id` equals the id.
  - Codex files whose `parser_state` identity `thread_id` equals it.

Each candidate's identity comes from its own records:
- **Claude main file:** the file name, confirmed by the `sessionId` of its main-line records.
- **Claude child:** its `agentId` and its `subagents/` path. Its records carry the parent's
  `sessionId`, which is inherited (SL8).
- **Codex:** the first `session_meta`'s `payload.id`, never `payload.session_id` (SL3).

`relation` is set from that identity:
- `own`: the file's identity is the id;
- `child`: a subagent file holding rows under the parent's id (O10; Codex children and
  forks also hold such rows);
- `inherited`: a fork copy.

Only `own` files are the session. The others are listed with their relation.

### 5.3 Index facts

**How the index is opened.** The reader opens the index with obs's
`index.open_index_readonly` and reads it inside `index.read_snapshot`. That helper pins
the schema version, so a different schema yields `unsupported_schema` in coverage, not a
guess.

**What it uses:**
- per file: `path`, `read_path`, `missing_since_ms`, `byte_offset`, `size`, `indexed_at_ms`;
- per session row: `session_id`, `parent_session`, `subagent`, `start_ms`, `end_ms`, `cwd`;
- Codex identity from `parser_state`;
- `task_commands` rows for `--task` (§8.4).

**A row whose path no longer exists is missing,** even before the index marks it, because
the index lags its hourly run.

**The native walk is always the primary source.** The index adds what the walk cannot see:
- files that are gone;
- their replayed copies;
- recorded lifecycle commands.

Without an index the reader still runs. Coverage says so, and an empty answer cannot be
`not_found` (§6.5).

### 5.4 Availability, replayed copies and remote hosts

Availability is per file (M01):
- **Readable.** A readable file is read.
- **Missing, with a readable copy.** A missing file whose `read_path` is readable is read
  from that path, with `store: replayed`. Its refs keep the logical path.
- **Missing, copy unreadable.** A `read_path` that cannot be read (for example, an
  unmounted backup disk) leaves the file `missing`, and coverage names the copy's path.
- **Missing, no copy.** A missing file without a `read_path` is unavailable. Coverage says
  so and names the explicit routes:
  - replay into the index (hq-d70879);
  - restoring a copy to a scratch path with session-archive and reading it with `--file`.
- **Unreadable.** A permission failure is `unreadable`, never skipped (SL10).

**Another host is a separate, explicit run.** The reader is run there over ssh, and each
run's coverage names its host. Combining two hosts' answers is the caller's work. The
second host had no index on 2026-10-20, so its empty answers are `unknown`.

## 6. `search`

### 6.1 Selection

| Option | Selects |
|---|---|
| `PATTERN` (optional) | records whose searchable text contains it; case-insensitive literal; `--regex` for a Python regular expression, `--case` for case-sensitive |
| `--harness`, `--home`, `--profile`, `--store` | files by place (each repeatable) |
| `--session ID` | the candidates of an id (§5.2); repeatable |
| `--task ID` | sessions with ownership evidence for the task (§8.4); `--mentions` adds sessions that only mention it, labelled as such |
| `--file PATH` | an explicit file outside the stores, such as an SDK capture (SL9); repeatable |
| `--cwd PATH` | sessions whose recorded cwd is the path or inside it |
| `--since`, `--until` | a date, a timestamp or `Nd`; `--since all` removes the default |
| `--role`, `--kind`, `--tool`, `--call` | records by role, native kind, tool name or call id (each repeatable) |
| `--copies` | include copies, labelled (§7.3) |

**Default time window.** Without `--session`, `--task` or `--file`, the window defaults to
the last 30 days. Coverage marks it as the default. It bounds the scan cost of an
unqualified search: the pre-flow extractor needed about 2 minutes for 23 GB.
- `--since` skips files whose mtime is older, which is exact because every record in a file
  is older than the file's mtime.
- `--until` skips records after it.

### 6.2 Matching

The searchable text of a record is the first of these that applies:
- a message's text;
- a tool call's input, as compact JSON, plus its extracted shell command;
- a tool output's text;
- a metadata record's compact JSON.

**Raw prefilter.** A file is parsed only if its raw bytes contain the pattern. The
prefilter is used only for an ASCII literal free of characters JSON escapes (a quote, a
backslash, control characters). Any other pattern parses every file in scope, so the
prefilter never hides a match.

### 6.3 Output modes and bounds

- **Records.** The default mode emits matching records. Without a pattern and with no role
  filter it is the bounded unfiltered stream for schema and aggregate questions (SL1, SL6).
- **`--sessions`** emits one session object per matching file (SL4).
- **`--final`** emits turn objects (§8). With a pattern, it emits the turns whose final
  text matches it.
- **Bounds.** `--limit N` caps emitted objects; the default is 50, and `none` removes the
  cap. `--text-bytes` defaults to 2,000 and `--raw-bytes` to 16,384. A hit limit is
  recorded in coverage.

### 6.4 Order and copies

- **Order.** Files are ordered newest first by last activity, then by path; records follow
  file order. `--order oldest` reverses the file order. The limit applies in that order.
- **Copies.** Collapsed by default and counted in coverage (§7.3).

### 6.5 Outcomes

- **`found`:** at least one parsed match.
- **`not_found`:** zero parsed matches, and every one of these holds:
  - the index was used;
  - no file in scope was unreadable;
  - no missing file in scope lacked a readable copy;
  - no unparsed line in scope had a raw match.
- **`unknown`:** any other zero-match result. `outcome_basis` names the first reason.

**What "in scope" means.** A file is in scope when it lies under a selected root and
matches the run's session, task or file selection. For a missing file, its indexed time
span must also overlap the window.

**Absent roots** hold nothing and do not by themselves make an answer `unknown`.

**Why the index is required for `not_found`.** It is the only record of files that are
gone. So a host without an index never answers `not_found`, and a pruned file without a
replayed copy keeps an unbounded search `unknown`. That is the explicit unavailable result
the original report lacked.

**Exit codes.**
- 0 `found`, 1 `not_found`, 3 `unknown`.
- 2 for a usage error or a failure of something the run depends on, such as a failed
  `tasks show` under `--task`. Code 2 prints one line naming the command and its error.

## 7. Roles, copies and the classifier

### 7.1 Claude Code

| Record | Role |
|---|---|
| `user` with `origin.kind` `human` | `human`; in a subagent file, `dispatch` |
| `user` with any other `origin.kind` (`task-notification`, `peer`, …) | `injected`; it starts a turn (§8.1) |
| `user` with `isMeta` or `isCompactSummary` | `injected` |
| `user` with no `origin` (records older than the field) | the prefix rule: `human` unless the text begins with `<` (but not `<pasted_content`), else `injected`; the interrupt marker is `injected` and ends its turn |
| `user` tool-result blocks | `tool_output`, one object per block |
| `assistant` text and thinking blocks | `assistant` |
| `assistant` `tool_use` blocks | `tool_call` |
| `attachment` | `injected` |
| `api-request-blob` blocks | each block's own role, with `copy: request_blob` (SL1) |
| `system`, `queue-operation`, `mode`, `permission-mode`, `ai-title`, `custom-title`, `last-prompt`, `agent-name`, `file-history-*`, `cost-state`, `api-request`, `api-request-shape`, `continued-in`, `atis-latch` | `metadata` |
| anything else | `unknown`, kept in the stream with its ref (SL1 `CA:16`) |

In a subagent file every prompt record is `dispatch`, never `human`. That includes
`AG:1`, a `user` record holding the dispatch brief (SL8).

### 7.2 Codex

| Record | Role |
|---|---|
| `session_meta` | `metadata`; the first one gives identity; a later one starts fork history (§7.3) |
| `turn_context`, `event_msg` (turn start, complete, aborted, item events) | `metadata` |
| `event_msg` `user_message`, `agent_message` | `metadata`, `copy: event_mirror` (they repeat response items) |
| `response_item` message, role `user` | the injected-prefix rule: `injected` when it begins with `# AGENTS.md` or `<` (but not `<pasted_content`), else `human`; in a child thread, `dispatch` |
| `response_item` message, role `developer` | `injected` |
| `response_item` message, role `assistant` | `assistant`, with `phase` |
| `response_item` `agent_message` | `dispatch`; encrypted blocks are `encrypted` (SL7 `XC:4`) |
| `response_item` function, custom, local-shell or web-search call | `tool_call` |
| their `*_output` records | `tool_output` |
| `response_item` `reasoning` | `assistant`, `block_type: reasoning`; encrypted content is `encrypted` |
| anything else | `unknown` |

A child thread is one whose first `session_meta` records a parent: any of
`source.subagent.thread_spawn.parent_thread_id`, `payload.parent_thread_id`, or a
`thread_source` other than `user`. This is the rule obs's adapter already uses.

### 7.3 Copies

| Copy | How it is recognized | Default |
|---|---|---|
| `request_blob` | every block of a Claude `api-request-blob` record | collapsed |
| `resume_history` | a Claude record whose `uuid` already appears in an earlier-starting file of the same project directory, where a resume writes its copy (SL5 `CW2:1`, SL6 `CW2:3#0`) | collapsed |
| `fork_history` | Codex records after a second, inherited `session_meta`, up to the fork's first own `turn_context` | collapsed |
| `event_mirror` | the Codex events of §7.2 | collapsed |
| `duplicate_file` | the same physical line, at the same line number, in a second `own` file of one identity (a rollout in both `sessions/` and `archived_sessions/`) | collapsed |

- **Copies outside the scan.** Copy detection covers the files the run reads. A resume copy
  whose original is outside the scope is not recognized, and coverage says that detection
  is scope-bound.
- **Call deduplication.** A call or result id repeated in a copy is not a second call
  (SL1). Aggregates over originals are deduplicated by call id (SL6).
- **Fork rule unverified.** No fixture has a forked child yet (hq-c1fecb), so its rule is
  unverified until that fixture lands.

### 7.4 One classifier, later

The reader's classifier is a fourth implementation of rules that obs's two adapters and
`session-episodes` already share. It differs from them in reading `origin.kind`.
- **Until readout:** the four coexist, and coverage records the reader's classifier
  version.
- **Stage B2:** the adapters and the moved `session-episodes` call the reader's normalizer,
  and the skill's "change all three together" list becomes one module.

## 8. Turns and final messages (hq-b95324)

### 8.1 Turn boundaries

**Codex.** A turn runs from `event_msg` `task_started` to `task_complete` or
`turn_aborted`, keyed by `turn_id`. Its trigger is the turn's first `human`, `dispatch`
or `injected` user message, in that order of preference.

**Claude Code** records no turn boundaries. A turn runs from a prompt record to the
record before the next prompt record, where a prompt record is:
- a `user` record that is not only tool-result blocks; and
- not `isMeta` or `isCompactSummary`; and
- not the interrupt marker.

The prompt record is the trigger, with its role:
- `human`;
- `injected`, for a task notification, which starts a turn of its own (`CA:14`);
- `dispatch`, in a subagent file.

**Limit.** A human message queued while a turn is running splits that turn at the
message.

### 8.2 Final versus commentary

| | Codex | Claude Code |
|---|---|---|
| Final | the assistant message with `phase` `final_answer` (live rollouts since at least 2026-06); else the last assistant message whose text equals `task_complete.last_agent_message` (basis `last_agent_message`; the fixtures' shape) | the text blocks of the turn's last assistant message whose `stop_reason` is `end_turn` or `stop_sequence` (basis `stop_reason`); a record without `stop_reason` falls back to the last text-only assistant record (basis `position`, weaker) |
| Commentary | assistant messages with `phase` `commentary`, and phaseless ones that are not final | text blocks of assistant messages that stopped for `tool_use` |

A probe of 60 recent rollouts, run on 2026-10-23, read only record keys and values. It
found:
- `phase` on every assistant message: 890 `commentary` and 112 `final_answer`;
- 112 `task_complete` events, each with a `last_agent_message` string.

June rollouts have `task_complete` events with a null `last_agent_message` (109 of 678
such events in 40 files).

A probe of 60 recent Claude transcripts found `stop_reason` on every assistant record:
`tool_use`, `end_turn`, or once `stop_sequence`. It also found `origin.kind` values
`human`, `task-notification` and `peer`. The session-logs skill says there is no
`stopReason` and that a turn ends where the next human record begins. That misses
`message.stop_reason`, which marks a turn's end.

### 8.3 Status

| Status | Codex | Claude Code |
|---|---|---|
| `completed` | `task_complete` and a final message | a final message (§8.2) |
| `no_final` | `task_complete` with no `final_answer` and a null `last_agent_message` | the next prompt arrives, or `end_turn` comes with no text block, before any final message |
| `interrupted` | `turn_aborted` (with its `reason`) | the interrupt marker, or an interrupted tool result |
| `waiting` | the last call is an unanswered `request_user_input` | the last assistant message has an unanswered `AskUserQuestion`, `EnterPlanMode` or `ExitPlanMode` call |
| `incomplete` | `task_started` with no end before end of file | end of file with no final message and no other status; a live session can still append |

**What final messages exclude.** An injected or dispatch trigger is never human. A turn
it starts is listed with `trigger.role` showing that, so a final message in such a turn is
never attributed to a human request. Commentary is never final.

### 8.4 Selection by task

`--task ID` reads the task through `tasks show ID --json`, never its file. It then gathers
evidence in three kinds, strongest first:

1. **`provenance_stamp`.** A lifecycle note's `provenance.harness_session` names the
   session. Its ref is the task id and the note's timestamp.
2. **`successful_task_command`.** An indexed `task_commands` row for the task (start,
   park, done, drop) whose paired output, read from the transcript, holds the task's
   `{"id": …}` line.
3. **`task_command`.** An indexed row whose output does not confirm success, or cannot be
   read. Weaker than 2.

**Mentions.** A `textual_mention` (the id in any text) selects a session only under
`--mentions`, and is labelled. It is never ownership evidence (SL2, SL7).

**Turn and session level.**
- A turn carries the evidence that falls inside its span: the note's time, or the
  command's call.
- Its session's other turns carry `task_evidence: session`.
- Under `--mentions`, a turn with only a mention carries `mention`.

**Sessions without lifecycle evidence.** A session that did work on the task without
issuing a lifecycle command or stamping a note is not found this way. A reviewer child is
an example. It is reachable from a selected session through `show --links`.

### 8.5 Printing

- `show <turn ref>` prints the whole turn: its trigger, every record with its pairing, and
  its status and final message.
- `search --final --session ID`, `--task ID` or `--since …` lists the turn objects.

Together these cover listing and printing by session, task and time window.

## 9. Links and models

### 9.1 Recorded links

| Link | Recorded where | Basis |
|---|---|---|
| Codex `child_to_parent` | the child's first `session_meta`: `source.subagent.thread_spawn.parent_thread_id` (SL3 `XC:1`); the index's `parent_session` corroborates | `native_metadata`, `index` |
| Codex dispatch binding | in the parent, the spawn call (`XP:7`) and an `item_completed` `SubAgentActivity` item whose `id` equals that `call_id` and whose `agent_thread_id` is the child (`XP:8`) | `native_metadata` |
| Claude `parent_to_child` | the launch result's `toolUseResult.agentId` (`CA:12`) and the child's `subagents/agent-<id>.jsonl`; the child's `.meta.json` `toolUseId` names the dispatching call | `native_metadata`, `path` |
| Claude `child_to_parent` | the child's `subagents/` path under the parent's session directory | `path` |
| `sdk_dispatch` | an event's `parent_tool_use_id` names a dispatching call (SL9) | `native_metadata` |

**What is never a link:**
- `parentUuid`, which threads messages;
- `turn_attribution.parent_turn_id`, a turn pointer;
- `session_id` in a Codex child's `session_meta` (inherited; at depth 2 it names the root,
  not the controller);
- a parent id printed in tool output (SL8).

**When the native record and the index disagree,** both are reported.

**`show --links` follows recorded links one hop** and adds the linked sessions' `session`
objects. For a Codex child, it also adds the parent's binding records.
- **No binding.** If the parent has no binding for the child, the dispatch brief is
  reported unavailable. The parent's text is never substituted without the binding (SL7).

### 9.2 Turn models

A turn object lists the runtime models of its records:
- Codex: the turn's `turn_context.payload.model`;
- Claude: the assistant records' `message.model`.

### 9.3 Model bases

| Value | Basis |
|---|---|
| Codex `turn_context.payload.model` | `runtime`, per turn |
| Codex `session_meta` `base_instructions.provenance.model` | `creation`; never reported as runtime (hq-7b131a: 176 of 400 recent rollouts differ) |
| Codex spawn arguments' `model` | `requested` |
| Claude `message.model` on assistant records | `runtime` |
| Claude `requestedModel`, the dispatch input's `model`, `.meta.json` `model` | `requested` |
| Claude launch result `toolUseResult.resolvedModel` | `resolved`; what an alias resolved to, not proof of what ran (SL3) |

## 10. Trial gate and staged rollout

**Dates.** flow-trial-1 enrols units first started between 2026-10-05 and 2026-11-29. They
close by 2027-01-10, follow-up runs to 2027-02-09, and readout is 2027-02-16. hq and obs
are both enrolled.

**The gate.** It holds every migration step that changes treatment (what an enrolled
session sees and does) or measurement (what obs and the verdict tools read) until readout
(ops-630a87 r4, change 5).

### 10.1 The measurement path

- **`trial-arm census`** reads task records through the `tasks` CLI.
- **The obs report.** `trial-verdict` reads `obs --json outcomes report`, which reads only
  outcome tables that `obs index` derives. Those tables come from obs's adapters, store
  discovery and index derivations.
- **`session-episodes`** feeds only `obs baseline`, a manual count no verdict reads.

The planning documents nevertheless list `session-episodes` as measurement. This design
leaves it unchanged before readout and does not settle that dispute.

### 10.2 Stage A: before readout, neither treatment nor measurement

**What Stage A adds:**
- **The reader in obs.** New files only: the `session_logs.py` entry point, its modules,
  their tests, a vendored fixture copy, and a README section.
- **hq's fixture additions (§13.3).** Test data only.

**What Stage A modifies:** no existing obs module. That rules out `obs.py`, which the
systemd index unit runs from the main checkout, and the adapters, `index.py`, `stores.py`,
the outcome modules and `baseline.py`.

**What Stage A reuses:** obs's functions are imported, not changed:
- `store_roots`;
- `open_index_readonly`;
- `read_snapshot`.

**What Stage A leaves alone:**
- no skill, instruction, flow, hook or link;
- no write to any store or to obs's state directory.

The reader is reached by explicit path (`python3 <obs checkout>/session_logs.py …`). A
task brief may name it; a brief is task content, the same in either arm.

**Gate evidence before Stage A merges:**
- `git diff --stat` against the base lists only added files and the README section. With
  no executed module changed, the index and the reports run the same code.
- obs's `just gate` passes.
- hq's `just test` passes on the fixture step.

### 10.3 Stage B: after readout

Each step re-checks the gate on its date.

- **B1. The skill and link.** The session-logs skill is rewritten around the reader (§11).
  `~/.agents/bin/session-logs` is declared in hq's `links.toml`. Both move with the skill
  to obs (obs-f5710b).
- **B2. One classifier.**
  - The adapters and `session-episodes`, moved to obs by obs-f5710b, use the reader's
    normalizer.
  - The extractor stamps bump and pruned files are replayed (hq-d70879).
  - The reader's classifier version retires.
- **B3. Roots from hq's home registry** (hq-19580c, obs-081ded) for the index and the
  reader together. The profile rule of §5.1 retires.

### 10.4 Related work under the same gate

- **hq-7b131a**, a "Which model ran" skill entry, is a skill-text change. It is a treatment
  change under the same gate. Stage A's model bases (§9.3) supply its answer without a
  skill change.
- **hq-a60cf5** changes `session-episodes`' roots. That is measurement-neutral in code
  (§10.1). The planning documents treat episodes as measurement, so it needs its own gate
  assessment.

Both stay their owners' work.

## 11. Usage skill (Stage B1)

The rewritten session-logs skill leads with the reader and keeps the store and record
reference as background. Its sections:

1. **Question → command.** One recipe per surveyed question type, each a `search` or
   `show` invocation: formats, behavior, identity, inventory, recovery, aggregates,
   origins.
2. **Reading coverage.** `unknown` is not `not_found`; absent roots; missing files and
   their routes; a second host is a separate run.
3. **Evidence strength.** A provenance stamp or successful task command over a tool-output
   match, over a tool-call match, over a mention. A mention never establishes ownership.
4. **Models and links.** Runtime versus creation, requested and resolved; which links are
   recorded and which fields only look like links.
5. **Handling.** Refs rather than pasted text; never paste output publicly; `--raw` only
   for schema questions.
6. **Pre-flow episodes.** The existing `session-episodes` section, until obs-f5710b replaces
   it.

The skill's description names search and show, so it triggers on the seven question
types, not only on episode preparation.

## 12. Out of scope

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
  readout (§10).
- The existing work of hq-a60cf5, hq-7b131a, hq-c1fecb and hq-edf5de.

## 13. Acceptance

### 13.1 The existing cases

The reader passes each case by replaying the fixtures with `HOME` set to a scratch copy,
as `materialize()` does. "Synthetic" marks a shape no cited episode exercised (cases
doc).

| Case | What the reader must return | Command shape | Basis |
|---|---|---|---|
| SL1 | Five calls, each paired by id with its result, including the reversed pair `CA:6`/`CA:7`. One message, `msg_fx_m1`, spans blocks 0–2. Runtime model `claude-model-a`. `CA:10`'s blocks are `request_blob` copies, collapsed and counted (shown with `--copies`). `CA:16` is `unknown` in the unfiltered stream. `CA:13` is `metadata`. | `search --session CA --limit none` | observed; the blob and the unknown kind are synthetic |
| SL2 | Block: the `tool_output` at `CA:7#0` (`is_error`), paired with `CA:4#0`. Release: `CA:8#0` and output `CA:9#0`. `CA:2` is `injected`. `CA:10` is a copy. Human records are `CA:1` and `CA:15` (basis `origin`). `CA:14` is `injected`. | `search zz-000001 --session CA`; `show <ref>` | observed shape |
| SL3 | XC: runtime `codex-model-b` (`XC:3`, turn `turn-c1`), creation `codex-model-a` (`XC:1`), requested `codex-model-b` (`XP:7`). Controller XP by `child_to_parent` from `XC:1`. Identity from `payload.id`. AG: runtime `claude-model-b`; `sonnet` requested; `resolvedModel` resolved. | `show XC --links`; `show AG` | observed, depth 1 |
| SL4 | `/w/beta`: CW and CW2 in `claude-work` (work), XW in `codex-work` (work). XA has `store: archived`. Coverage: five roots searched, `codex-work` archive absent. | `search --sessions --cwd /w/beta --since all`; `show XA` | observed; the Codex-work session is synthetic |
| SL5 | `XA:5` is `human` and `XA:4` is `injected`. `CW:1` is human. `CW2:1` is a `resume_history` copy of `CW:1`, collapsed. `CW2:4` is a distinct human turn. | `search '<phrase>' --role human --since all` | observed; archived placement synthetic |
| SL6 | Three outputs, `CW:3#0`, `CW:6#0` (`is_error`) and `CW2:6#0`. `CW:7#0` (blob) and `CW2:3#0` (resume) are collapsed copies. `CW:4` is `injected`, not output. | `search test-fast --profile work --role tool_output --since all --limit none`, then `jq` | observed |
| SL7 | The filing output `XC:6` for call `XC:5`. Controller XP (`XC:1`). Human turn `XP:6`. Dispatch bound by `XP:7` and `XP:8`. `XC:4` is an encrypted dispatch. Each hard negative carries its role: `XP:4` `injected`, `XP:13` `assistant`, `CA:17#0`/`CA:18#0` a call and its output, `CA:15` human. | `search zz-0000f1 --since all`; `show XC --links` | observed; the parent's plain brief is synthetic. The verdict "XC filed it" is the trace composition's (§12): the reader supplies each link with its basis |
| SL8 | `parent_to_child` from `CA:12` to AG; `.meta.json` `toolUseId`. AG's `last_at` 12:02:40Z, `CA:13` at 12:02:41Z, `CA:14` at 12:03:00Z. `AG:1` is `dispatch`. AG's identity is its agent id. No link from `parentUuid`, `XC:2` or XP. | `show CA --links`; `show AG` | observed; the human-origin command synthetic |
| SL9 | Child calls `SDK:4` and `SDK:5` carry `sdk_dispatch` to `toolu_fx_dA` and `toolu_fx_dB`. Results are `SDK:7#0` and `SDK:6#0` (`is_error`). `SDK:8` and `SDK:9` are root events. No session link. | `search --file <capture> --role tool_call --role tool_output` | observed |
| SL10A | Zero parsed matches. Unparsed `CD:2` (malformed) and `XD:3` (truncated), each with `raw_match`. CU unreadable. Three roots searched, three absent. Index absent. Outcome `unknown`. | `HOME=<degraded> search needle-term --since all` | observed failures; unreadable file synthetic |
| SL10B | CF has no candidate and no index, so it is unavailable and the outcome is `unknown`. `CD:3` is an `assistant` mention. The clipped command is never presented as recovered. | `show CF`; `search 'rm -rf' --since all` | observed |

### 13.2 Location controls from the index probe

The obs-side tests build a temporary index over a fixture copy with `obs index
--state-dir <tmp>`. They do not change any index code. Each control is synthetic; this
table says what the live data did and did not show.

| Control | Test | Live evidence |
|---|---|---|
| O10: one id, several files | A Claude root and its subagent file both appear. The subagent file is `relation: child`, and the root alone is `own`. Some Codex files hold rows under their parent's id, because obs's adapter attributes inherited records to the inherited id. Such a file is `child` or `inherited` by its native `payload.id`. The test records which fixture shapes produce such rows. | obs-b99310 removed the Claude phantom rows; the shape remains wherever inherited Codex records are indexed |
| M01: missing file with a readable alternate | A rollout is copied into `archived_sessions/` and indexed, then the live copy is deleted. The reader reports two candidates: one `missing`, one `readable`. It reads the alternate. | Observed once (M01) |
| A01: native archive | XA is read from `codex:archived_sessions/…` with `store: archived`. | Observed (A01) |
| Replayed copy | A file is indexed, deleted, and replayed with `obs index --replay <archive copy> <root>`. The reader reads `read_path` with `store: replayed`. When the copy is then made unreadable, it reports `missing`, names the copy, and gives `unknown`. | **Unobserved live**: zero `read_path` rows on 2026-10-20 |
| A host without an index | No state directory: index `absent`, the native walk proceeds, a zero match gives `unknown`. | Observed (the second host, 2026-10-20); cross-host retrieval itself was not qualified and stays an explicit run |

### 13.3 New case SL11: turn-final messages and task evidence

hq adds fixtures, a section in the cases document and self-check assertions, in the
existing style. The fixtures use live shapes: Claude `stop_reason` and `origin.kind`,
Codex `phase`.

**Claude, one session with five turns:**
1. A typed human turn with commentary text before a tool call, then an `end_turn` final
   (`completed`).
2. A turn ended by the interrupt marker (`interrupted`).
3. A turn whose last call is `AskUserQuestion` with no answer (`waiting`).
4. A task-notification turn with its own final: trigger `injected`, `completed`.
5. A final turn cut at end of file after a `tool_use` (`incomplete`).

**Codex, one rollout:**
- a turn with `commentary` and `final_answer` messages;
- an aborted turn;
- a turn whose `task_complete` has a null `last_agent_message` (`no_final`);
- a phaseless turn whose final is found by `last_agent_message`;
- a `task_started` at end of file (`incomplete`).

**Task evidence:**
- One session's lifecycle note stamp names it, giving `provenance_stamp` for the turn
  holding the note's time.
- A second session only mentions the task id. It is selected only under `--mentions`.
- The task record reaches the reader through a stub `tasks` executable in the test's
  environment, which prints canned `tasks show --json` output.

**Expected:** each turn's status, final ref and basis; commentary never final; the
injected trigger labelled; and the selection and labels of the two sessions.

### 13.4 How the tests run

- **Fixture vendoring.** obs vendors hq's `tools/fixtures/session-logs/` under its test
  fixtures. A source file names the hq commit and each file's sha256, a test checks the
  copy against it, and a recipe re-vendors. The corpus stays hq's, as the boundary assigns.
- **Environment.** Each subprocess test builds its environment key by key: `PATH`, `HOME`
  (the scratch fixture copy), `XDG_STATE_HOME` (a scratch state directory) and the stub
  `tasks`. It never inherits the caller's environment.
- **Test first.** Tests precede the code they cover. Each new test is seen to fail against
  a targeted break of what it checks.
- **Live-store run before verification.** The reader runs over every record of this host's
  six roots, using `search --since all --limit none` with output counted by role and kind,
  never kept. The run reports, without writing anything:
  - files, lines, unknown kinds, unparsed lines and elapsed time;
  - any exception, which is a failure;
  - the time an unqualified default-window search takes.

  It also checks two live identity cases:
  - one divergent Codex child, whose runtime and creation models must differ (hq-7b131a);
  - one audited origin from the index probe, whose candidates must agree with that probe's
    case ledger.

### 13.5 Fixture limits

Corrections owned by hq-c1fecb that the reader's rules depend on:
- depth-2 and forked Codex children (§5.2, §7.3);
- Claude's separate `session_id` field;
- compact JSON spawn arguments;
- live failure prefixes on Bash results.

Until those land, the fork rule and depth-2 identity are covered only by the stated rules
and the live-store run.

## 14. Traceability

| Task requirement | Section |
|---|---|
| Bounded search and show; home, harness, date, session and role selection | §6, §4 |
| Normalized and raw records; paired calls; block refs | §4.1–4.2, §6.3 |
| Recorded parent links; runtime model per turn | §9 |
| Coverage and unavailable results | §4.6, §5.4, §6.5 |
| obs consumer interface and its owner; research SQL not an API | D1, §3, §5.3 |
| Parsing and location ownership | D1, §3, §7.4 |
| Trial gate and effects on enrolled sessions and measurement | D5, D6, §10 |
| Final messages, commentary, injected records, statuses, task evidence | §8, §13.3 |
| Acceptance cases, location counterexamples, synthetic or unobserved | §13.1–13.2, §13.5 |
| Local-first versus remote or archive | D3, §5.4 |
| Interactive resume kept separate | §3, §12 |
| No picker, index, aggregate verbs or precision claims | D2, §12 |
