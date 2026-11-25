# Hook routes

Type: guide, data model; document types 1.

`harnesses/hook-routes.toml` declares the checked-in Claude Code, Codex and agy
hook wiring and the relay subscriber template.

| Table | Fields |
| --- | --- |
| `homes` | Each home names its harness, repository-relative settings path and ordered bindings. Each binding names an event, an optional matcher and its ordered lines. |
| Lines | Each names its policies and any harness timeout in seconds. A native line names its literal command. A relay line names a runtime, subscriber file and outer budget in milliseconds. `relay_event` supplies a distinct relay event argument when needed, and `relay_kind` records the expected selector kind. An agy bridge line names its transport command, runtime and ordered delegate argv. |
| `states` | Policy defaults. A line's `states` map can replace a policy's metadata for that binding. Native routes name an owner and reason. Existing relay routes name an owner and the grant for the current deployment. Relay routes cite qualification `records`. Bridge routes cite fixture `evidence`. `activation` names the user grant task note that made a former target live. |
| `runtimes` | Each version names the command, runtime script and relay commit in that runtime's lock. `subscriber_schema` is the subscriber file schema that relay reads, 2 by default or 3. |
| `search_path` | The host's ordered command directories, each starting with `/` or `~/`. Every file whose runtime reads schema 3 is rendered with it, and needs it nonempty. |
| `subscribers` | Each subscriber names its policy, role, argv and `timeoutMs`. Observers can declare a registry and event-specific `privateFields`. |
| `subscriber_files` | Each file names a runtime for digest addressing or a literal deployed path, a repository-relative template output and ordered named selections. A selection can carry `harnesses`, `kinds`, `tools` and `nativeEvents` filters. A file declared by path renders schema 2, so it cannot serve a schema-3 runtime. `reconciliation_file` names the shared file for reconciliation. |
| `target_files` | New compositions name a runtime version and ordered subscriber selections. `reconciliation_next` selects a target composition for reconciliation. |
| `removals` | Each retirement names a subscriber and the authorizing owner task. Move every binding whose file contains that subscriber, and move reconciliation if it uses the file. |
| `rollback_bases` | Retained subscriber file names and literal commands that still count as donor references. |

Run `tools/hook-routes render [--home PATH]` from a task worktree to rewrite its
tracked hook files and subscriber template. The renderer uses the supplied home
or the current home for `~/` paths in relay command lines. Native commands keep
their literal paths, and subscriber argv uses the template's `@HOME@` placeholder.
Rendering Claude Code settings replaces only the top-level `hooks` value and
preserves the surrounding bytes. Codex and agy hooks and the subscriber template
are whole-file renders.

A file renders in the schema its runtime reads: `{"schema": 2, "subscribers": …}`, or
`{"schema": 3, "searchPath": …, "subscribers": …}` with `search_path` in it, placeholders
and all. The list must be one relay accepts once this home is expanded (distinct,
normalized, without `:`), and the table is refused otherwise. v0.7.0, the
standalone pin, reads schema 3, so only the `reconcile-v0.7.0` file holds the list. The
user confirms the list at the activation that first uses it; a later edit changes the
digest of each file that holds it, and so needs a new deployment and new qualification of
its routes.

Run `tools/hook-routes check` to validate the table and compare the checkout with its
live render using the current home. It compares Claude Code's parsed hook values by event and checks
the other files byte for byte. The table must cover all five shipped hook files
(Claude Code and Codex, each personal and work, and agy) and the legacy relay
subscriber template. Exit status 1 names the drift
or table error on stderr. The local pre-commit hook and `just check-hygiene` check the staged
copies over the same export as the other staged checks. Portable CI hygiene
omits the HOME-dependent comparison. The renderer tests use the checked-in
settings' relay home for parity and temporary homes for CLI checks.

## Proposed cutovers

Add an optional `next` list of lines inside a binding. The target uses those
lines for the binding and uses live lines everywhere else. An empty `next`
removes the binding's lines. To introduce a new binding, declare it with an empty
live `lines` list and put the new lines in `next`. A target line can point at
a named `target_files` composition. Use fresh names so a candidate can leave
the live runtime and file untouched.

`check` checks current and effective target policy paths independently. Every
live policy keeps a target path for the same home, event and matcher, unless a
named removal retires its subscribers. A policy can move to another group for
that event and matcher. The two literal Claude Notification matchers are disjoint.
Overlap involving other matchers is rejected.

Relay owns event projection. The shipped relay lines declare the built-in and
subscriber policies observed with the pinned runtime and record their expected
`relay_kind`. The cutover check uses that kind and the file's selectors to
preserve current subscribers, including their tool coverage. When the kind is
undeclared, the static check uses explicit policy membership and native-event
selectors as evidence and requires preserved selector coverage for known entries.
Reconciliation keeps current reconcile-capable observers and covers newly added
observers in the effective target, accounting for authorized removals.
Repository path checks cover every stored subscriber argv. Each file uses
the binding-level states for policies declared on it, and the policy default
for stored entries without a binding state on that file.

`tools/hook-routes render next --out DIR` renders the target review files to a new
or empty directory. The candidate compositions expand HOME before hashing, and
their settings commands point at
`~/.config/relay/<version>-<sha256-prefix>/relay/subscribers.json`. The output
contains those exact deployed JSON bytes under
`<version>-<sha256-prefix>/relay/subscribers.json`. The prefix has 12 hex digits.

`tools/hook-routes render candidate FILE --out DIR` renders a TOML slice for
qualification before records exist. It starts from the live routes and applies
the slice's own targets. It inherits subscriber definitions used by the
live files and those referenced by the slice. The slice can add `runtimes`, `subscribers` and
`target_files`, and can name `reconciliation_next` and `removals`. Each
`[[moves]]` entry has a `home`, the zero-based `binding` index in that home's
ordered array, and replacement `lines` using the same syntax as `next`. For example,
a slice that moves a Codex Stop binding to a new native command can contain

```toml
[[moves]]
home = "codex"
binding = 11
lines = [{ policies = ["claim-guard"], command = "claim-stop" }]
```

The candidate render checks the route structure and writes `manifest.json` with
`kind = "candidate"` and each output file's full SHA-256.

## Status

- `tools/hook-routes status` prints one JSON row per policy path, with its current
  state, target metadata for pending changes, and recorded grants and evidence.
- `tools/hook-routes status --donor PATH` lists live bindings, subscriber file
  contents, reconciliation, bridge delegates and rollback bases that name the
  donor. A binding counts as a caller when its file contains the donor, even
  when its filters would skip the donor on that event.
- `tools/hook-routes status --changed-codex-entries --base REF` compares the live
  render with the two Codex hooks files at the specified Git ref. It lists
  changed, shifted and removed command positions using the deployed home links
  declared in `links.toml`, with the event in `snake_case` and zero-based group
  and hook indexes.

## Qualification and host checks

For each `relay` state and target, `check` reads the records named in
`harnesses/qualification/` and calls the binding's installed relay package. It
checks that the hook runs the helper's Node executable and the package's declared
bin, version and locked commit. It checks the digest-addressed path
and SHA-256 of the rendered subscriber bytes, and the binding's selector
coverage against relay's adapter. Relay validates the complete subscriber file,
budget, roles, record and proof for the exact event. The rendered harness timeout
must cover the relay outer budget. Each cited version needs
passing records for both `interactive` and `non-interactive` on the platform.
If the harness, native event and tool filters leave a qualified file entry
possible, both `check` and `status` verify the binding's selection against its
pinned relay. A missing or incorrect `relay_kind` cannot hide a selected policy.
Bindings whose qualified entries are all excluded by those filters and which
declare only existing policies need no installed relay for static checking.
Static checks use the versions in the records. Host version probes run in
`preflight` and in the default `status` report for qualified routes.

- `tools/hook-routes deploy live` installs the subscriber files used by live
  bindings and reconciliation. For a file that names a runtime, render and
  deploy use the same version and expanded-byte digest in its address.
  Files have mode 0600 and relay config directories have mode 0700.
  Repeating the deployment keeps identical files and refuses different content.
- `tools/hook-routes deploy next DIR` checks the review directory from
  `render next` against the effective target for this home and installs its
  new digest-addressed subscriber files. The review compares Claude’s top-level
  `hooks` value, so a local model or effort pick can change. Every other output
  must match byte for byte. The frozen directory stays intact. The live legacy base stays available
  for rollback.
- `tools/hook-routes preflight [--next DIR]` resolves the commands, checks the
  installed runtimes, budgets and subscriber selections, and reads the deployed
  subscriber bytes. Live preflight first checks the checked-in hooks and template
  against the current home's render. Each consuming runtime loads the deployed file through relay's
  public config reader, including the standalone pin for reconciliation. Preflight
  checks the interpreter and script or observer behind the shipped `env` wrappers
  and the executables in each agy bridge line’s declared delegate argv. Commands are
  looked up on the caller's `PATH`, except that a schema-3 file's subscribers are looked up
  as relay does, only in `search_path`: the first directory that holds the command decides
  (`unusable-command` when it is not an executable regular file), and the interpreter an
  `#!/usr/bin/env` script names must be found there too, for the command itself and for the
  absolute script an `env` wrapper runs. Existing
  routes also undergo the host selection check. With
  `--next` it checks the review directory and the live relay selections that the
  cutover relies on for subscriber retention. A qualified binding needs
  a successful harness version probe and records for that version in both modes.
  A version with carried latency evidence still needs relay's qualification
  record with its fresh exact-version proof. Preflight exits 1 on a finding.
- `tools/hook-routes reconcile-base` prints the live reconciliation file's XDG
  config base. `just relay-reap` uses it. Reverting a cutover restores the
  previous reconciliation selection with the hook settings.

The bridge can call `relay_runtime.call(package, "project", payload)` with
`harness`, `event`, raw native JSON text in `raw`, `invokingCwd`, `subscriber`
and `registry`. The result is relay's subscriber envelope. The `parse-guard`
operation takes reply text in `output` and returns relay's parsed guard reply.
The SessionStart bridge uses `parse-notice` on each owner's stdout and passes the
ordered contexts to `combine`. Both operations use the v0.6.0 public exports.

An agy SessionStart bridge line supplies the launcher in `command`. The renderer
adds `SessionStart --runtime PACKAGE` and one `--delegate` per declared argv in
order. Duplicate delegate argv are rejected before any owner runs. The bridge
heals detached settings first, then runs each owner on PATH
with its projected envelope and a ten-second timeout. It injects one system
message with the combined context, or replies `{}` when every notice is empty.
A failed owner contributes a diagnostic. If the diagnostic does not fit in the
combined context, the bridge writes the same failure to stderr. A failed profile or event projection
keeps the visible `profile: unresolved` line. SessionStart loads v0.6.0 and calls
`lore hook profile-notice` followed by `mindful notice session-start`.

The agy Stop bridge accepts `Stop --runtime PACKAGE --guard 'tasks hook claim-guard'`.
A Stop bridge line supplies only the launcher in `command`. The renderer derives
the package directory from the declared runtime and the guard argv from the single
entry in `delegates`. The bridge reads up
to 4 MiB of native UTF-8 input, projects it for the guard and gives the owner ten
seconds to reply. On Linux the bridge adopts and reaps any descendants the guard
leaves, including its separately grouped facts reader. An owner denial becomes agy's `continue` with the owner's reason.
An owner allowance becomes `{}`. On a transport failure, agy's own termination
reasons and positive safe-integer refires allow the turn to end. Other failures
produce a one-line `continue` reason. Stop loads v0.5.0 and calls the guard once.
The separate native Stop refresh still heals settings. All three agy relay
bindings use v0.5.0 and the digest-addressed file shared with Claude Code and
both Codex homes. Reconciliation selects the same subscribers in `reconcile-v0.7.0`.

The activation reference `hq-a83688:agy-owner-activation` reserves a note on
hq-a83688 for the user's grant. On a candidate branch, the reference alone
conveys no authority. Before merging the candidate, record the grant, ensure
the owner commands and runtimes pass preflight on each host, and close all agy
sessions. Running sessions cache command strings for the retired invocation
forms. To roll back after activation, revert the merge with
`git revert -m 1 <merge>` and restart agy sessions.

## Claude Code donor cutover

The personal Claude Code home's SessionStart and Stop relay lines use the live
`donor-2-shared` subscriber file. Its tracked template is
`relay/subscribers.donor-2.template.json`. Its expanded bytes match the frozen donor-2
candidate's `v0.5.0-19b427ac306a/relay/subscribers.json`. The native ops and lore
SessionStart lines and the native Stop claim guard and state refresh lines are
gone from that home. Their policies are `relay` states on the two lines and cite
the Claude Code 2.1.331 records for both session modes. A native SessionStart
line runs `tasks notices --pretty` before the relay line. The ops hook gained that
notice after donor-2 was frozen, and donor-2 has no subscriber for it. The line
has a 5 second timeout. Relay's latency support covers only the measured native
entries, so with this extra line SessionStart latency is unknown by relay's rule.
The user accepted this limitation on hq-8185d3. Stop is unaffected. Every other Claude
Code relay line keeps the shared file. The
Codex homes and the work Claude Code home are unchanged.

The activation reference `hq-a83688:claude-donor-activation` reserves a note on
hq-a83688 for the user's grant. Before merging, deploy and preflight on each host,
then pause Claude Code sessions. To roll back, revert the merge with
`git revert -m 1 <merge>` and restart Claude Code sessions. The digest-addressed file
can stay deployed.

## Donor policy equivalence

`tools/hook-routes equivalence --next DIR --out FILE` reads the frozen
`render candidate` directory. It verifies the manifest hashes, subscriber-file
addresses and binding runtime identity. The pinned relay selects the subscribers
for each binding and dispatches the unchanged bytes through its public hook CLI.
The output contains a `policyEquivalence` evidence string for each applicable
policy and case, including the binding, harness, target version, session mode,
source fixture, runtime commit and SHA-256 of the deployed subscriber bytes.
Each line identifies the local event template file and its SHA-256, the digest
of the exact payload sent to both commands, its upstream fixture ancestry and
the synthetic substitutions. A difference or failed dispatch exits 1 and includes
the native and relay observations. A failed notice or observer retains its own
diagnostic, including stderr forwarded by the failed observer. Registry publication
follows notice collection, so a publication failure marks the composition failed
while an independently confirmed notice can still pass. A failure belonging to
a subscriber outside the policies compared by that case produces a separate
failed composition line and a nonzero command exit. The destination must be new.

The recorded corpus in `tools/fixtures/hook-equivalence/` covers profile
delivery and failure, instruction drift, missing-index repair, empty and
nonempty capture queues, and Stop refresh. A recorded event describes one
target version and session mode. The shipped synthetic inputs cover the
interactive Claude Code 2.1.325 and Codex 0.168.0 fixture targets documented
by relay, and Claude Code 2.1.331 in both interactive and non-interactive
(`claude -p`) mode, derived from relay's live payload captures at that version.
Other targets require sourced fixtures of their own. These strings
supply the policy check in a qualification row. Live delivery and latency
have their own evidence requirements.

Each side starts at the same pathname from a fresh copy of a fixture-owned
checkout, home, XDG directories, Git config, tasks registry and detached
records store. The runner copies refresh and its companion scripts into the
fixture hq checkout, and uses the fixture PATH for the owner commands.
Profile replay copies the deployed native lore hook, source and profile files
independently of the replacement executable selected on PATH. Both trees run at
the same logical pathname so that recovery commands remain comparable.
For a schema-3 file the relay side finds the owner commands through the file's own list:
they are bound at its first usable directory, beside the system programs when that is one
of the sandbox's own directories, and `PATH` must be the list.
It rejects unexpected subscriber environment keys or values. Claude
subscribers receive the two provenance values the pinned relay supplies for
the synthetic event. The fixture runs the donor and owner stale-notice
policies against a recorded assembler result and excludes the retired ops
Projects check. Capture compares the actual donor and owner clients against
an isolated triage-queue service. The native donor fixes its address at
`localhost:3331`. Every real hook replay runs in Linux bubblewrap with a private PID namespace
and proc filesystem. Relay looks up harness ancestry while selecting its
supervisor and publishing its registry. The fixture checks that its namespace
differs from the caller's and that proc belongs to it before running any hooks.
It also uses private mounts and loopback for existing absolute observer argv and
the fixed capture endpoint. An unavailable namespace prevents a real replay.
Admission-only checks use the pinned public budget API with a private environment.
