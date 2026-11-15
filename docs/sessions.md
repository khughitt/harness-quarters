# Sessions and transcript evidence

Type: guide; document types 1. Find and resume sessions, interpret their evidence,
and prepare episode inputs. [Capabilities](harness-capabilities.md) separates
observations from support; [session-log cases](session-log-cases.md) defines the
synthetic acceptance cases and [archive](session-archive.md) covers custody.

## Find and resume

```sh
tools/hq sessions -n 20
tools/hq sessions --harness codex --home personal --here
tools/hq sessions --archived
tools/hq sessions -i
```

The list uses each harness's native metadata without keeping its own index.
Interactive selection uses fzf when available and otherwise a numbered prompt.
It resumes in the recorded home and cwd only after rechecking cwd and transcript;
a disappeared path refuses rather than launching elsewhere. A closed output pipe
also refuses launch. Per-home flags come from tools/hq.toml; HQ_CONFIG selects an
alternate configuration for isolated tests. Read errors or unexpected native
schema types fail visibly instead of producing an empty list.

| Adapter | Metadata | Transcript |
| --- | --- | --- |
| claude | Home history.jsonl | projects/*/SESSION.jsonl; child files under subagents/ |
| codex | Home state_5.sqlite threads | sessions/ or archived_sessions/ rollout JSONL |
| agy | conversation_summaries.db | brain/CONVERSATION/.system_generated/logs/transcript_full.jsonl |

Personal/work homes are distinct; agy has one home. A work resume sets the selected
harness's home variable, while a personal resume clears both Claude/Codex overrides.
Agy's workspace/title/parent identity comes from its summaries database, not its
step transcript. Pi, OpenCode and Crush session-store parity remains intended work,
not current support in this registry.

Filters include harness, home, here and archived Codex threads. Missing interactive
previews and native non-interactive sessions are excluded as the adapters specify;
this list is not a complete transcript search. The footer reports omitted records,
absent homes and unresolved cwd locations. Project names/locations resolve through
one tasks resolve call; missing or invalid resolver output stops the command.
Color selection is auto/always/never and respects NO_COLOR in auto mode.
Project RGB colours and xterm-256 indices come from tasks resolve (`color` and
`color_256`); hq does not derive terminal stand-ins. A coloured project missing a
valid terminal index stops the listing with an error.

## Standalone transcript decoder

The adapters share `Home` and home discovery from `tools/harness_evidence/homes.py`.
That standalone package also names transcript stores without importing hq or its
configuration. `tools/harness-evidence discover [--home PATH] [--root HARNESS=PATH]...`
lists Claude Code and Codex transcript paths and filesystem metadata as
JSONL under schema version 1 (`root`, `file`, then `discover_end`). Explicit roots replace
all default roots; supported harness names are `claude-code` and `codex`. Defaults use
the shared personal/work homes, including Codex's archived stores, and ignore obs's
environment overrides. Discovery reads no transcript text. Matching `.jsonl` paths remain selected even
when a non-symlink directory occupies a transcript position, including subagents
and explicit archive roots. Their stat metadata is listed; opening such a source
fails visibly in header and decode instead of silently dropping the path. Codex filename identity is
marked `convention`, separate from identity recorded inside a transcript. Symlinked
transcripts appear in each root's `aliases` list with normalized place and filename
identity; they are never opened or counted as files/bytes. Missing or unreadable
roots are reported; a file that
vanishes or has unavailable metadata after its name is enumerated retains a file
object with null stat metadata and its observed state/error. Initial lstat/stat
failures remain explicit even if a later lookup could succeed; known symlink
aliases stay excluded from file objects. The listing helper retains candidates with unknown mtime
when applying a cutoff; the command applies no cutoff.

Every discovery file and alias also carries `filename_lookup`: null when no
supported placed naming convention applies, otherwise sorted unique `session_ids`,
`basis: "convention"` and a `rule`. Codex uses `rollout_name_lookup`, retaining exact
suffix/non-UUID/continuation lookup: "rollout-T.jsonl" has no T candidate while
"rollout--T.jsonl" does. Claude uses `claude_name_lookup` under a declared root,
matching exactly `*/<id>.jsonl`, `*/<id>/subagents/agent-*.jsonl` and
`*/*/subagents/agent-<agent>.jsonl`. The last pattern admits `agent-<agent>` and also bare `<agent>` when it does not
itself start `agent-`; query alias normalization removes exactly one prefix. Nested bare IDs, non-agent child names, wrong depths
and wrong suffixes are excluded. Empty lists assert no membership; unplaced or
explicit Claude names have null lookup. Aliases use their own logical names.
Lookup depth is relative to the actual declared root, including current-directory
and filesystem-root forms; public paths and refs keep their declared spelling.
These hints assert neither canonical filename identity nor recorded session identity.
Consumers retain query grammar/alias policy and confirm identity from evidence.

Discovery files/aliases and decode `file_start` also carry `path_facts`, null outside
Claude. Claude's convention object has `session` (logical filename stem), `agent`
(one filename `agent-` prefix removed, otherwise null; empty string stays distinct),
`subagent` (immediate parent is `subagents`), `parent` (grandparent name in that case,
otherwise null), and `resume_group` (POSIX parent of place.relpath when not subagent,
otherwise null). It includes `basis: "convention"`, `rule: "claude_path_layout"` and
`ref` (logical file ref, no line/hash). These are naming facts, not recorded identity,
copy decisions or observed authorship. Any-depth layout facts also describe indexed
nonstandard paths; lookup membership still obeys the exact patterns above. Facts use
logical paths even for missing/index-only files or differently named external replay
copies; physical read_path continues to supply bytes/adjacent metadata. Decoded
header agent evidence is separate. Query-ID aliases and publication of arbitrary
index/identity claims remain consumer policy, rather than native path decoding.

`tools/harness-evidence version --json` reports the evidence schema,
decoder version `19`, and the decoder revision. A pinned copy reads a `REVISION`
file inside the package; a checkout reports its HEAD with `+dirty` when
the package has changes. Without either source the command exits 2.

`tools/harness-evidence decode` reads one JSON request per stdin line and flushes
framed harness-evidence/1 objects through `request_end` before reading the next.
Requests require an integer `id` and `files`, each with logical `path` and byte
bound `size`; optional `read_path` reads captured bytes without changing identity
or refs. `roots` replaces default discovery roots, `context` supplies fork evidence
without emitting it, and `cross_file` marks copies across requested files. `text`
and `raw` default to false; transcript text, nested commands and turn-end messages
require `text`, while original physical lines require `raw` independently.
Raw strings preserve invalid UTF-8 bytes with surrogate escapes; recover exact
bytes with `raw.encode("utf-8", errors="surrogateescape")`. Typed text keeps its
existing replacement of invalid UTF-8.
Native `abort_reason` remains metadata when text is disabled. Session headers keep
their existing child flags and add `subagent_basis` for Claude Code (native timed
sidechain flags, conventional subagent path, or a heuristic negative) and
`child_basis` for Codex (native parent/thread-source evidence or a heuristic
negative). SDK and unknown headers gain no child flags. Store-placed files use the
established root's native reader, including files without a signature; rootless
explicit files retain signature detection, including SDK captures.
Headers also publish `recorded_identity`: the first qualifying native identity
observation with session, physical line, ref, hash, native basis and recognition
rule, or null. This does not replace the existing session identity. Codex's first
session metadata stops the search even with an invalid id; Claude skips sidechain
and non-string ids. A valid final JSON line can supply this observation without a
newline. Consumers apply their own peek window to its line position.
Child `.meta.json` requested models join `header.models` after transcript copy
settlement, with the sidecar ref; sidecars are separately observed metadata and
explicit-store captures never consult them. With `read_path`, child metadata comes
from beside that physical source, using the logical transcript stem and ref; it
never falls back to a stale sidecar at the logical path.
Each bounded transcript prefix is captured once in transient memory; format,
records, header, raw lines, hashes and offsets all use those same bytes. The
buffer is released after extraction; its peak cost is up to one current file's
requested prefix in addition to reader data. Cross-file mode retains the reads
needed for its requested group, rather than retaining those byte buffers.
Non-JSON numeric constants and numbers that overflow a finite float become
complete malformed `unparsed` evidence. Output JSON rejects non-finite numbers;
malformed native kinds remain unknown source records within the detected format.
Neither case aborts a later healthy file.

Copy labels carry their own `copy_basis` and `copy_rule`, independently of role
provenance. Explicit request/history constructs and native continuation links
are native; inherited-turn ranges, event mirrors and identity/line matches are
conventional; unresolved ranges, timing and ties are heuristic. Session links
use native or conventional `basis` and retain their former recognition basis
as `rule` for the later reader projection.

Each file emits keyed `file_start`, records or unparsed lines, `session`, and
`file_end` with status, emitted count and checkpoint `state`. Source failures stay
framed; malformed requests, unknown fields and invalid states exit 2 with a stderr
line. Pass the last state to resume: `replaces: {"from_line": N}` replaces line
objects at or after N, while `replaces: "all"` restarts after an earlier payload
changed. Always replace the file and session aggregates by key. Incomplete tails
are provisional and replayed. Stage 1 rereads the whole bounded prefix each time.
Copy marking uses root-list priority followed by logical relative path, independent
of request file order. Outside-root explicit files have priority zero.
The checkpoint hashes committed line objects in line/string-key order: sorted-key,
compact ASCII JSON plus a newline per object, excluding schema, decoder and
request/file transport indices. Text/raw option changes can therefore restart
replay, while request ids and decoder revision changes alone do not.
Records themselves retain native numeric block order, including when a line has
ten or more blocks.

## Cheap Claude headers

`tools/harness-evidence header` accepts one JSON request per stdin line with
`id`, `files` and explicit `roots`. Files use the same logical `path`, optional
`read_path`, fixed `size` and `identity:{device,inode}` as index decoding. Claude
roots must contain every logical path; Codex headers are explicitly unsupported.
No default roots or guessed harness are used. The capability view explicitly
marks Claude headers implemented (50 lines) and Codex headers unimplemented;
this declares implementation, not evidence that a harness version emits a field.

Each file emits one `header` object with its request id, file index, logical path,
status, `header:{session,cwd,start_ms}`, provenance and null or structured error.
The batch ends with `request_end` carrying the exact file count. Protocol, source
identity and fixed-span violations fail the command visibly. Open failures and
invalid native types carry non-ok source statuses and error details, never a
successful empty header. Consumers validate the complete ordered batch before
using any selection result.

Selection preserves the old first-50-physical-line policy, including LF, CRLF and
CR newlines, replacement of invalid UTF-8 and skipping malformed JSON lines.
The first truthy top-level CWD stops the scan immediately; `session_meta` also
stops at its payload CWD even when false or absent. Valid unterminated final JSON
lines are eligible. Finite native CWD values retain their JSON types. Session id
and UTC start time are optional evidence from records already visited; neither
justifies scanning beyond the selection. Provenance binds each value to its
source ref, physical bytes' hash, line, offset and decoder revision. This path
holds only one physical line plus bounded read-ahead and never invokes the full
reader. It has no resumable checkpoint or index extraction side effects.

## Native index extraction

The opt-in `extract: "index"` request selects the native evidence profile from
the declared harness/place. Claude supports the scratch index pilot; the Codex
profile currently supplies basic facts and declarations while stateful execution
relocation remains incomplete. Include each file's `identity: {"device": ..., "inode": ...}`, keep
`cross_file` and `raw` false, and omit `context`. Pass a saved index `state` whole:
`next_line`, `next_offset` and `digest` describe the complete raw prefix, while
`index` is opaque. The held descriptor must match the supplied identity and fixed
byte span. Resume proves that prefix in bounded reads and decodes complete lines
from its checkpoint; incompatible decoder revision, identity, logical path, options
or prefix explicitly returns `replaces:"all"`. Logical paths determine refs and
child-parent naming; `read_path` determines physical bytes.

This profile emits `file_start`, one `index_event` per complete JSON object (key
`E<byte offset>`), `unparsed` evidence for malformed lines or a partial tail, a final
cumulative native `coverage`, `file_end`, then `request_end`. The terminal count
includes every event, unparsed object and coverage object. A partial tail does not
advance the checkpoint. Valid JSON with invalid native types retains the original
index adapter's errors. Accept a file only after both terminals and the count have
been validated. On a late invalidation `file_end.restart` carries a reason and an
opaque from-zero seed; its `state` is null, so no successful checkpoint is exposed.
Drain both terminals before retrying from zero with that seed. The transport supports
this signal; Claude currently has no native restart trigger. Source-open failures
stay framed with vanished/unreadable status and null state; protocol faults fail the
request visibly. Each file releases its source handle and output before the next.

Events carry recorded and normalized session identity, timestamps, response fragments,
message origin evidence, ordered text blocks, native tool calls/results, attachment
pieces, notifications, fork evidence and stop-hook summaries. Field provenance names
native paths, coverage keys, basis, rule, revision and source ref. Index version 16
uses `provenance_format:"defaults/1"`: every `file_start` carries owned
`provenance_defaults` for all normalized fields, including notification proofs'
optional `source:"physical_line"`. Each event's `provenance` contains only changed
attributes; an empty mapping inherits the whole table. Ref and revision inherit
from the event envelope. Overrides replace whole arrays or scalar values and may
refer to earlier records or file paths. Unknown fields/attributes, revision overrides
and invalid or deletion-like supplied values fail visibly before encoding. Complete
declarations are checked once per file; native extraction supplies record-specific
changes, each resolved field is audited, and every event's ref/revision binding is
checked even with empty changes. Omitted fields inherit checked declarations; an
independent frozen full-proof oracle checks for accidentally omitted dynamic changes.
Declarations reset on each file and resume request, outside opaque state and terminal
counts. Both command and import routes use this framing. `text:true` requests
message, command, path, question, answer and dispatch text; with it disabled those
values are omitted. No human-turn, active-time, task/review or recommendation verdict
is produced. Default reader requests retain their existing object/state shapes.

Native byte sizes use UTF-8 strings or `json.dumps(value, ensure_ascii=False)` with
its default spaced separators for other values, independently of compact wire JSON.
Assistant output bytes sum text-block bytes without joining newlines plus tool-input
sizes. Joined user text preserves empty placeholders for missing text keys. Native
`durationMs` stays separate from timestamp differences. File-edit `raw_path` preserves
the exact nonempty native file/notebook path; `paths` separately carries lexical
normalization against cwd, and `paths_complete` records missing or rejected inputs.

Codex version 19 emits terminal usage responses (`response.phase:"terminal"`),
independent messages, direct call inputs and context updates. Context observations
can be untimed. Claude response fragments carry `phase:"fragment"`, `context:null`
and empty `execution` collections and diagnostic counters. Codex terminal
`usage_present` has all seven normalized usage keys. Missing direct counters remain
null; input-minus-cached arithmetic defaults absent operands to zero and still
rejects explicit null operands. A later record-usage source after count usage
requests a seeded restart. Discarded count usage contributes no applied population.
Native counters stay unchanged in `response.native`.

Codex patch header paths stay in `patch_paths`; lexical candidate `paths` normalize
separately. Direct shell calls expose ordered `commands` and directories. Code-mode
operations, result status/truncation, skill inference, bounded stateful associations,
late context replacement and terminal metadata are not yet implemented by this step;
the capability view marks stateful execution incomplete. The index-only catalogue
and original-case inventory live under `tools/fixtures/harness-evidence/`; they do
not add reader-role requirements to the ordinary reader catalogue.

Question prompts, result answers and native duration metadata retain their finite
JSON values. Consumers apply their hashing/matching/scoring rules at the original
use site; a native decode success can still precede a consumer-policy failure.
Native duration metadata describes presence and is separate from timestamp deltas.
The conformance corpus records native and consumer outcomes separately for these
cases, including old partial row/session/coverage evidence on consumer failure.

For Claude fragments, `response.usage_present` contains `output` and `thinking` booleans for native key
presence, including explicit null. Consumers preserving old storage defaults use 0
only when the flag is false and copy a present `usage.output` or `usage.thinking`
unchanged. These two fields preserve opaque native JSON storage values, including
nonnumeric values; numeric arithmetic inputs remain separately validated. Presence
flags add no raw/applied coverage population or consumer measurement rule.

Claude usage components are `input_uncached` (input tokens), `cache_write`,
`cache_read`, `output` and `thinking`; absent components are null. `context_total`
is input plus cache write plus cache read, and `uncached_total` is input plus cache
write, each null when a required component is missing or the derived result cannot
be represented as a finite wire number. A null aggregate does not erase its exact
components: consumers preserving old index arithmetic compute totals from normalized
components with their existing absent-to-zero rule, including an infinite surviving
total where the old parser produced one. `response.native` preserves
original JSON as opaque data, including invalid intermediate usage values that a
later fragment replaces. Normalized components that an invalid intermediate fragment
cannot supply are null; the original final-invalid failure remains at response flush.
SDK child evidence uses the session's first nonempty entrypoint and retains a later
native sidechain flag. Pending Stop-hook matching stores nontext equality keys, so
text-disabled terminal state contains no hook command text. Native coverage preserves
the old extraction
populations, including response usage counted at each historical EOF flush. Synthetic
`tools/fixtures/session-logs/index/` samples and frozen old-oracle controls establish conformance, not observed
harness emission or full/replay equality. Capability field declarations also expose
real nested question-option and stop-hook values. `coverage_keys` is the union; optional `coverage_scopes` name exact subsets
using conditions on decoded scalar paths such as `message.channel`. These metadata
additions do not expand `defaults/1` proofs or change per-file raw/applied coverage.
`index.tool_kinds` maps known native names to normalized kinds, and `index.features`
declares native skill events and question option labels. These describe decoder
behavior, without claims about untested harness versions or consumer metrics.
The capability artifact publishes native field provenance and coverage declarations separately from reader declarations.

## Read evidence, not mentions

The session-logs skill is the operational store/record reference. Claude records
can split one message across several API blocks and carry copied request blobs;
pair tools by call ID and distinguish a resume copy from a new ask. Codex uses
session_meta, turn_context, response_item and event_msg; runtime attribution comes
from the relevant turn context, not creation defaults or requested spawn arguments.
Agy records positional tool calls/results and later SYSTEM_MESSAGE completions.

A lifecycle note's harness_session stamp anchors task evidence. Without a stamp,
search actual successful tasks command calls and their outputs; a title, injected
instruction, command input or assistant mention does not prove ownership or success.
Parent session IDs, SDK dispatch IDs and message-thread parent fields are different
links. Missing/ambiguous parents, malformed/truncated records and unreadable stores
must remain explicit coverage limits. Empty matches with incomplete coverage mean
unknown, not proven absence. See the SL1–SL11 cases before changing a reader.

Local transcripts can contain credentials, private paths and raw tool outputs.
Use synthetic fixtures for tests and keep raw investigative evidence private.
Do not copy a transcript into a public guide or assume that a pasted tool-result
block is a human instruction. Native metadata and wrappers matter to attribution.

## Episode extraction

agents/bin/session-episodes reads local stores and task records to produce the
content-free episode input consumed by obs. Invoke it by explicit path:

```text
agents/bin/session-episodes extract --out FILE [--since DAYS] [--project PREFIX]
agents/bin/session-episodes show ID --episodes FILE
agents/bin/session-episodes confirm ID yes|no --episodes FILE
agents/bin/session-episodes label ID yes|no --episodes FILE
```

Extraction writes the episode file and review sidecars; it does not mutate source
stores. Retain stderr coverage/provenance, review unconfirmed start outputs with
show/confirm, review status-question positives and a sample of negatives, then
re-extract before handing over. Passing a byte search is not enough for escaped
JSON text; an expected successful command's output must belong to that call.

The tool's default stores cover Claude Code and Codex. Agy is an explicit harness
selection during the current trial period; do not change that measured default
as a documentation cleanup. SESSION_LOGS_CLAUDE, SESSION_LOGS_CODEX and
SESSION_LOGS_AGY select isolated roots. The tool resolves its hq helpers from its
real path and refuses a detached copy without them. Episode references are private
local locators even though records contain no transcript text.

## Wake probes and isolated homes

agents/bin/wake-judge takes a harness, transcript, nonce and exact prompt file. It
passes only a classified launched-child completion followed by a new controller
turn reporting the nonce after the controller had ended its prior turn. Unknown
input forms fail closed. No Codex completion form is currently recognized; judge
failure is not proof of a negative wake observation.

A bounded negative wake observation separately proves child completion and no
controller continuation during the observation interval. Inconclusive runs do not
change capability values. Probe shell and subagent completion independently.

Use private homes/state directories and synthetic inputs for probes; seed only
needed onboarding preferences. Claude's explicit config override keeps its generated
.claude.json inside that directory, not beside it. Complete onboarding and verify
that the requested prompt actually produced a transcript/tool call. Stop all owned
processes and remove copied credentials before disposing of scratch. Live desktop
use and paid model calls require their own authorization; a documented recipe is
not permission to run it.
