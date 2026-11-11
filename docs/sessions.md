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
