# Hook routes

Type: guide, data model; document types 1.

`harnesses/hook-routes.toml` declares the checked-in Claude Code, Codex and agy
hook wiring and the relay subscriber template.

| Table | Fields |
| --- | --- |
| `homes` | Each home names its harness, repository-relative settings path and ordered bindings. Each binding names an event, an optional matcher and its ordered lines. |
| Lines | Each names its policies and any harness timeout in seconds. A native line names its literal command. A relay line names a runtime, subscriber file and outer budget in milliseconds. `relay_event` supplies a distinct relay event argument when needed. |
| `states` | Policy state metadata. Native policies name an owner and reason. Existing relay policies name an owner and the grant for the current deployment. |
| `runtimes` | Each version names the command, runtime script and relay commit in that runtime's lock. |
| `subscribers` | Each subscriber names its policy, role, argv and `timeoutMs`. Observers can declare a registry and event-specific `privateFields`. |
| `subscriber_files` | Each file names its deployed path, repository-relative template output and ordered subscriber entries with their selection filters. `reconciliation_file` names the shared file for reconciliation. |

Run `tools/hook-routes render [--home PATH]` from a task worktree to rewrite its
tracked hook files and subscriber template. The renderer uses the supplied home
or the current home for `~/` paths in relay command lines. Native commands keep
their literal paths, and subscriber argv uses the template's `@HOME@` placeholder.
Rendering Claude Code settings replaces only the top-level `hooks` value and
preserves the surrounding bytes. Codex and agy hooks and the subscriber template
are whole-file renders.

Run `tools/hook-routes check` to compare the checkout with the table using the
current home. It compares Claude Code's parsed hook values by event and checks
the other files byte for byte. Exit status 1 names the drift or table error on
stderr. The local pre-commit hook and `just check-hygiene` check the staged
copies over the same export as the other staged checks. Portable CI hygiene
omits the HOME-dependent comparison. The renderer tests use the checked-in
settings' relay home for parity and temporary homes for CLI checks.
