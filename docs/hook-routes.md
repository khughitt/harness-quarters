# Hook routes

Type: guide, data model; document types 1.

`harnesses/hook-routes.toml` declares the checked-in Claude Code, Codex and agy
hook wiring and the relay subscriber template.

| Table | Fields |
| --- | --- |
| `homes` | Each home names its harness, repository-relative settings path and ordered bindings. Each binding names an event, an optional matcher and its ordered lines. |
| Lines | Each names its policies and any harness timeout in seconds. A native line names its literal command. A relay line names a runtime, subscriber file and outer budget in milliseconds. `relay_event` supplies a distinct relay event argument when needed. An agy bridge line names its transport command, runtime and ordered delegate argv. |
| `states` | Policy defaults. A line's `states` map can replace a policy's metadata for that binding. Native routes name an owner and reason. Existing relay routes name an owner and the grant for the current deployment. Relay routes cite qualification `records`. Bridge routes cite fixture `evidence`. `activation` names the user grant task note that made a former target live. |
| `runtimes` | Each version names the command, runtime script and relay commit in that runtime's lock. |
| `subscribers` | Each subscriber names its policy, role, argv and `timeoutMs`. Observers can declare a registry and event-specific `privateFields`. |
| `subscriber_files` | Each file names its deployed path, repository-relative template output and ordered named selections. A selection can carry `harnesses`, `kinds`, `tools` and `nativeEvents` filters. `reconciliation_file` names the shared file for reconciliation. |
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

Run `tools/hook-routes check` to validate the table and compare the checkout with its
live render using the current home. It compares Claude Code's parsed hook values by event and checks
the other files byte for byte. The table must cover all four shipped harness
settings and the legacy relay subscriber template. Exit status 1 names the drift
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

`check` checks current and effective target policy paths independently. It uses
each line's policy declarations and subscriber selectors that establish a native
path or have no event filter. The two literal Claude Notification matchers are
disjoint. Overlap involving other matchers is rejected. Relay determines
selection for kind-only filters because it owns event projection. Reconciliation
keeps reconcile-capable observers unless their owner has authorized removal.

`tools/hook-routes render next --out DIR` renders the target review files to a new
or empty directory. The candidate compositions expand HOME before hashing, and
their settings commands point at
`~/.config/relay/<version>-<sha256-prefix>/relay/subscribers.json`. The output
contains those exact deployed JSON bytes under
`<version>-<sha256-prefix>/relay/subscribers.json`. The prefix has 12 hex digits.

`tools/hook-routes render candidate FILE --out DIR` renders a TOML slice for
qualification before records exist. The slice can add `runtimes`, `subscribers`
and `target_files`, and can name `reconciliation_next` and `removals`. Each
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
