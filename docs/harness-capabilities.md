# Harness capabilities and integration

Type: guide, data model; document types 1. Capability facts use schema 1. This
covers their validated read interface, integration boundaries and re-probing.
See [home links](home-links.md), [live state](live-state.md),
[sessions](sessions.md) and [adding a harness](runbooks/adding-a-harness.md).

## Three distinct layers

A native harness event/refusal mechanism, relay's event mapping, and hq's installed
hook/subscriber policy are separate capabilities. An unmapped event does not prove
the native harness lacks it; an installed launcher does not establish a session
reader, refusal channel, durable runtime or automatic controller wake.

| Runtime | Declared integration |
| --- | --- |
| claude-code | Personal/work homes; live picks; lifecycle/guard wiring; session adapter |
| codex | Personal/work homes; picks/trust; Stop and SubagentStop claim checks; session adapter |
| agy | Two home/config roots; anchored atomic-save adoption; relay translation; session adapter with store limits |
| pi | Pinned CLI/RPC runtime and picker extension; native skill discovery |
| pi-durable | Separate pinned SDK runtime; caller-supplied context and lifecycle |
| opencode | Declared fact slug and configured home surface; relay server bridge is observational |

Crush is not currently declared in harnesses.toml. Pi CLI and pi-durable are
separate fact columns: an SDK recovery guarantee never applies to the CLI merely
because they share a package version. Current session adapters cover Claude,
Codex and agy; parity for other stores is intended work. Agy transcripts lack
workspace/title/parent metadata and stable call IDs; summaries and positional
pairing are required. Its archive is not a complete capture of every private file.

Relay's adapter docs define normalized events, refusal/context support and budgets.
Installed wiring lives in harness settings/hooks and relay/subscribers.template.json.
The pinned [runtime guide](runbooks/relay-runtime.md) describes upgrade ordering.
Guard subscribers require a real refusal channel; observers do not create one.
Current CLI scope wrapping through host-budget depends on the declared host option;
a failed scope launch stops rather than silently running unmanaged.

## Installed hook wiring

Codex personal/work hooks each register ops's claim guard on root Stop and worker
SubagentStop. A worker's agent_id selects its own claim; root metadata grants no
foreign closure authority. After a definition change, inspect and trust the exact
definition through native /hooks in each home. Trust restoration follows the
[runtime upgrade procedure](runbooks/relay-runtime.md).

Agy's local hook runs profile/capture-notice at SessionStart and heals detached
settings before startup and run_command. PreToolUse healing emits empty stdout,
keeping native permission prompts intact. Relay translates run_command to Bash
for ops's guard and dispatches its familiar subscriber. Its agy handler timeout
is 60 seconds with --outer-ms 60000. Stop also refreshes picks and performs the
local one-shot claim check, allowing a stop while fullyIdle is false under the
probed controller-wake behavior. This fallback remains until the shared guard
supports that route; an installed observer is not a substitute refusal channel.

## Decoder capability evidence

`tools/harness-evidence capabilities` shows the standalone decoder's catalogued
evidence as a table; `capabilities --json` returns the same content with the running
decoder's version and revision. Both read only the package's committed
`tools/harness_evidence/capabilities.json`, so a pinned package needs no fixtures.
Rebuild it explicitly with `tools/harness-evidence capabilities --build` in an hq
checkout after changing decoder behavior, declarations, or catalogued samples.
The artifact hashes `tools/fixtures/session-logs/CATALOGUE.toml` and every listed
sample. Builds read no metadata sidecars or uncatalogued sibling transcripts.

The `fields` map names decoded paths (`header.*` and `links[].*` for session
evidence); each `provenance` list names native JSON paths, where `[]` visits array
items. `fields_seen` requires a decoded value and native source evidence, excluding
nulls, empty evidence containers, and defaults with no source. Explicit false and
zero values can be evidence. Record kinds and role-label bases are listed separately.
Synthetic samples establish decoder conformance; observed samples or probes establish
emission. The current catalogue is entirely synthetic, and its known modeled format
versions do not establish observed emission. An unspecified or unlisted version is
untested; an absent field is unobserved. Native index field provenance and coverage declarations are published separately
from reader declarations; their presence does not establish observed harness emission.
The agy block has no reader fields (agy has no reader decode): its `fields` are its
index declarations, its `index.absent` names each field agy declares absent with the
reason, and `side_inputs.agy_conversation_summaries` declares the summaries database
the agy path facts read (path relative to the agy home, table, key, columns, open mode
and fingerprint rule). A consumer that caches decoded agy files must treat that
fingerprint as part of each file's identity.

## Fact schema and lookup

Use only the supported reader, not a hand-written TOML reader:

```text
tools/harness-facts check
tools/harness-facts list [--pretty]
tools/harness-facts get FACT HARNESS
```

The root has schema=1 and facts keyed by lowercase hyphenated names. Declared
harness names come from harnesses.toml. Each fact has:

| Field | Allowed content |
| --- | --- |
| type | boolean or set |
| description | Nonempty explanatory string |
| probe | Optional existing relative file inside this checkout |
| harness | Optional table of entries keyed only by declared harness names |

An entry is either unknown (status and optional nonempty note only) or probed
(status, value, version, date, evidence and optional note). Boolean values must be
booleans; set values are lists of unique strings. Version and evidence are nonempty
strings; date is a local TOML date, not a timestamp. Unknown fields, undeclared
harnesses, invalid probe paths/types and malformed files are refused. A missing
entry for a declared harness is unknown, never a default value.

Get returns fact, harness, type and status, plus value/version/date/evidence for
probed entries and note when present. Sets are sorted for display. List adds root
schema/harnesses and a facts map with description/probe and a complete harness view.
Invalid input or an undeclared name exits 2; probed and unknown lookups exit 0.

Python callers can load tools/harness-facts as a source module and call
lookup(fact, harness, path=None, manifest=None). The entire fact file and declared
manifest are validated before returning an entry. Invalid raises Invalid with
problems; undeclared fact/harness raises Undeclared (a LookupError). A reader that
must leave the checkout untouched disables bytecode writes before loading.

## Evidence and unknowns

False and an empty set are observed negative values. Unknown means no conclusive
probe; consumers choose what their policy permits. File validation does not prove
a probe still applies to a newer harness version, nor that the feature is deployed.
Consumers own freshness and failure policy.

Private provenance may use `records@FULL_SHA:hq/docs/notes/FILE` locators in the
fact file. Access to that records repository and git show at the pinned commit
is needed to inspect the original bytes; normal capability lookup does not require
it. Public guides describe the procedure without duplicating private transcripts.

## Re-probing a fact

Read the fact's probe and existing record, isolate the harness home/state and run
only within the approved spend/host-use scope. Keep raw results private. Update
value, version, date and evidence together only for a conclusive observation.
Inconclusive results change no value. Record a negative observation's bounded
coverage; wake-judge failure alone is not a conclusive no-wake result.

For controller wake, test shell and subagent completion independently. Both waking
permits true; either inconclusive leaves the old entry; a conclusive failure of
one kind permits false with only the proven waking kinds listed. Record actual
completion output and controller behavior, not a terminal indicator.

Answer-route probes exercise delayed answer, restart while pending, duplicate
answer and cancellation. Temporary Codex/Claude/OpenCode/agy state must not attach
to live homes or daemons. An available route is probed true only if the answer
actually reaches the waiting turn/continuation with the documented surface.

## Re-probing pi

A pin change in harnesses/pi/package.json starts a new capability epoch. Under the
upgrade's explicit authorization, install the lock, run RPC and durable probes
separately, and refresh applicable rows in one change before unattended reliance.
The first interactive run may write tracked lastChangelogVersion; account for it.

Run the picker-extension probe in its scratch agent directory, starting with
--check P1a, then its remaining cases. That local dummy-provider probe makes no
API calls. The separate loopback driver attached to hq-f1aff0 covers the RPC
exit status, session directory, extension API and context-file reporting facts
with synthetic credentials. The general RPC and durable probes for model
behavior need a real model key and paid calls. Documentation and a pin change
do not authorize that spend. MCP protocol revisions require
checking the pinned client construction too; the probe server's acceptance alone
does not establish the requested revision. Changes to the external analyst
runtime/tool epoch need their owning project's requalification independently.
