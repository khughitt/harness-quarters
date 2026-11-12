# Adding a harness

Type: guide; document types 1. Integrate a harness through the owners of its homes,
state, hooks and evidence readers. Start with [architecture](../architecture.md),
[home links](../home-links.md), [live state](../live-state.md) and
[capabilities](../harness-capabilities.md); this checklist does not grant rollout,
paid-probe or host-use authority.

## Choose the supported layers

Decide which layers are actually needed: home/config delivery, instructions/skills,
selection preservation, native hooks, relay observers/guards, session discovery,
archive custody or evidence indexing. A launcher alone promises none of the others.
Use a distinct canonical slug for runtimes with different guarantees, as with the
pi CLI and durable SDK. Record unsupported and unprobed layers explicitly.

Search owner code before editing: harness name enumerations, native event schemas,
CLI value validation, fixtures, command aliases and source-distribution manifests.
Read every matching caller, not just a central-looking list. Existing registry
readers derive their choices from their owner; avoid a new parallel enumeration.

## Homes and private inputs

1. Declare real homes and links in links.toml; distinguish personal/work groups
   and their activation conditions. Targets belong to registered owner checkouts.
2. Link instruction/profile/general skills to lore and task/flow tools to their
   owners. Follow links when searching assembled skill directories; an empty
   recursive search without symlink following proves nothing.
3. Keep credentials, session stores and private work settings outside tracked
   configuration. Add only necessary narrowly scoped layout allowances, never a
   broad privacy exemption to make an example pass.
4. Rehearse preview, refusal and first-run adoption in synthetic homes. On a live
   host use an approved window and link before first launch where possible.
   Anchored atomic saves and genuinely new first-run files have different guards.

## Config state and capability facts

Observe whether settings writes follow symlinks or replace them atomically; test
all picker/config/trust actions in isolation. Add a harnesses.toml schema-1 entry
only with the matching .gitattributes route and validator coverage. Separate
picker units, non-restored installation IDs and project trust deliberately.
Exercise capture, restore, forget, invalid-input refusal and filtered-empty restage;
prove that newer live units win and unrelated settings survive.

Declare facts only for conclusions consumers need. Update public re-probe procedures
in harness-capabilities.md, not a historical README heading. Probe exact harness
versions under explicit model-spend/desktop authorization; inconclusive observations
leave prior values unchanged. Fact readers use tools/harness-facts, never mirrors
or a hand-parsed TOML default. Keep raw private evidence and synthetic fixtures
separate; describe the new version/epoch requalification requirement.

## Native hooks, guards and relay

Inspect native stdin fields, tool names, stdout refusal/context schemas and timeout
behavior. Verify cancellation, completion, worker identity and unhooked tools;
never assume another harness's Stop semantics apply. Hq wiring calls owner tools;
lore owns profile injection and ops/tasks own command/claim guard policy.

In relay, add the canonical adapter/registry vocabulary, native translation and
fixtures. Update consumers through their declared adapter interfaces. A guard
requires a refusal channel; observer-only server events do not gain one because
the subscriber is named guard. Sum subscriber budgets with input/termination
reserves and ensure outer native timeouts fit. Installed absolute runtime paths
and the standalone launcher pin are separate surfaces; preserve working old
versions until no hook image needs them. See [relay runtime](relay-runtime.md).

Claim/provenance integration uses the worker's actual native session identity,
not a shared root PID or inherited session_id as closure authority. Coordinate
owner fixtures and pinned copies through normal distribution routes. Do not
hand-edit a vendored fixture or assume shell-launched children inherit the intended
home, model or worker controls; test each actual launch path.

## Sessions, custody and readers

Add a tools/harness_stores adapter only when real metadata supports discovery.
`tools/harness_evidence/homes.py` owns the shared `Home` type, harness slugs, home
discovery and transcript-store paths. The adapter binds that discovery function to
its harness alias; `harness_stores.Home` remains the same public type.
List from native metadata, recheck cwd/transcript before launch and fail on schema
changes. Search/show evidence needs all relevant homes and explicit files, not
just visible interactive sessions. Runtime attribution, copied history, parent
links and SDK dispatch remain separate; use the [SL1–SL11 cases](../session-log-cases.md).

Archive selection and deletion eligibility are separate decisions. Declare complete
source coverage and optional/missing-root behavior; identify metadata outside the
transcript. Add pruning only with identity/open-file/quarantine rules and the
corresponding obs readiness contract. An incomplete archive must be described as
incomplete, not silently treated as a deletion backup. Use [archive](../session-archive.md)
for its safety gates. Extend session-logs/episodes and obs independently; broad
store parity is not implied by a picker adapter.

## Verify and roll out

Use synthetic homes, key-by-key credential-free subprocess environments and the
protected focused test route. Verify owner schemas and staged config/fact checks,
then mandatory hygiene. A supported command that produces no selected tests is
not verification. Keep paid probes and live desktop/host changes separately gated.

Distribute source through the owning project's established tooling, install the
required stable runtime before a home launcher selects it, then apply links from
main only. Rehearse one host/profile end to end for the same configuration route;
a distinct harness path needs its own check. Preserve private inputs, rollback
conditions and ownership of each still-running process or retained artifact.
