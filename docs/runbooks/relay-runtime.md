# Pinned relay runtime

Type: guide; document types 1. Install, upgrade and recover the pinned standalone
runtime and hook images. See [home links](../home-links.md) for launcher ownership
and [capabilities](../harness-capabilities.md) for native/adapter/policy boundaries.

`relay/package.json` selects v0.6.0; `relay/package-lock.json` fixes its commit to
`9078727105f06b4a17ccbf177821806d7eed93be`. The declared home launcher resolves to
`relay/bin/relay`, which reads that pin and runs the versioned installation under
`$HOME/.local/share/relay/` (falling back to the account's passwd home when
`HOME` is overridden and `RELAY_INSTALL_ROOT` is unset). Node and npm come from `/usr/bin`.

For a standalone launcher upgrade, after approval for the live rollout, run `just relay-install` from the reviewed
checkout before merging its pin into main. This installs the new runtime in its
stable versioned directory before the home launcher selects it. Resolve
`command -v relay`, inspect `readlink -f` of that path, and check `relay --version`
after merging. Never point the home launcher at a worktree. Every host that shares
this checkout selects the merged pin at once, and its launcher exits 127 until that
version is installed there. Other hosts cannot see this host's worktrees, so run
`just relay-install` in the main checkout on each of them as soon as the merge syncs.

On each host, `just relay-subscribers` runs `tools/hook-routes deploy live`.
It installs each subscriber file named by the live route table and its reconciliation
file. The active base is `~/.config/relay/v0.5.0-<digest-prefix>`. Different bytes
at an existing destination cause a refusal. The previous v0.5.0 file stays in
`~/.config/relay/v0.5.0` for rollback, and the v0.3.0 schema-1 rollback file
stays at `~/.config/relay/subscribers.json`. Run `just relay-reap` for reconciliation.
It points `XDG_CONFIG_HOME` at the live table's `reconciliation_file` base.

Prepare each hook cutover on every host that shares the settings before
requesting activation. Use the exact reviewed revision and install each new
runtime it names with approval. With subscriber deployment authorized, use the
sequence that matches the reviewed table:

- For a proposed `next`, use its frozen `tools/hook-routes render next --out DIR`
  output. From that reviewed revision, run `tools/hook-routes deploy next DIR`
  and `tools/hook-routes preflight --next DIR` against the same output on each host.
- For a reviewed branch that already promotes the target to live bindings, run
  `tools/hook-routes deploy live` and `tools/hook-routes preflight` from that
  exact branch revision on each host before merging it into main. Preflight
  rejects checked-in hooks that would select different paths from that host's render.

Record each host's result. A missing runtime, failed preflight or unreachable host
holds activation. Keep earlier installations and files until rollback is released.
See [hook routes](../hook-routes.md).

Schema 2 resolves each subscriber's `argv[0]` on `PATH` and passes later arguments
literally. The active template uses `env` followed by familiar's checkout path
and the `observe` command. The previous configurations also contain the ops
command guard for rollback.

For an isolated rehearsal, set `RELAY_INSTALL_ROOT` to a private scratch directory
for both `just relay-install` and the worktree's explicit `relay/bin/relay` path.
Use a private, owned mode-0700 `RELAY_STATE_DIR` for every service and CLI command.
The installer override changes the destination; it does not select another pin.

Where an inbox service is configured, inspect `relay-serve.service` and its
`ExecStart` before upgrading. After approval, stop it with
`systemctl --user stop relay-serve.service`, preserve its state directory, select
the new stable runtime in its existing unit, and start it again. Reload the user
manager if the unit changed. Check its journal and configured state path, and
verify that the running service and CLI use the same release. A host without a
configured service needs no unit created or enabled for a CLI upgrade.

Preserve inbox/seq, entries, rejected files and presence. Verify a saved answer
survives the upgrade. Through the selected launcher and an isolated service, post
`relay inbox ask --file PATH`, answer with `relay inbox answer ID ITEM=VALUE
--surface terminal`, then run `relay inbox take ID` twice. The answer must survive
a service restart and repeated take must leave the consumed entry unchanged.
The installed package's docs/runbooks/inbox-service.md describes the envelope
and recovery contract.

Older services can quarantine entries containing take or refusal histories.
Do not downgrade a service against such a store or reset the durable sequence to
undo an upgrade. Keep the store intact and use a release that understands it.

The standalone pin does not rewrite installed hooks: those use absolute runtime
paths, and each harness's hook images move under their own approval. Claude Code's
(`harnesses/claude/settings.json`), Codex's (`harnesses/codex/hooks.json`,
`harnesses/codex/work/hooks.json`) and Antigravity CLI's (`harnesses/agy/hooks.json`) all
name v0.5.0 and its subscriber file. Each binding selects its own runtime and subscriber file. Claude Code's SessionStart and PostModelSwitch relay routes carry relay's
built-in task provenance (`TASKS_AGENT`/`TASKS_MODEL`), which replaced ops
`hooks/claude-provenance`; never wire both. In `harnesses/agy/hooks.json`, each relay handler
sets `"timeout": 60` paired with `--outer-ms 60000`. The `familiar-agy` observer
has a 2 s timeout. `tools/test_relay_wiring.py`
holds each file's version. Keep every installation a hook image names.

Root retirement assumes one active Codex root per process. TUIs launched with
`--no-daemon`, as the shell aliases for both Codex homes are, satisfy it. A Codex
launched without that flag starts a shared app-server daemon that outlives it, and
sessions hosted there could share its handle and retire each other's rows
(shared-daemon retirement limitation). Look for a running `codex app-server` before a rollout and after it
check that no registry row carries a daemon's pid.

From relay 0.5.0, `relay install` writes a dispatch binding only for a route its
`--qualification` record proves, and no route is qualified yet. Until one is, hq renders the
images from its route table: a version move changes only the runtime directory and subscriber file in
each relay command (plus any route the move adds or retires, named in its task), and
`tools/test_relay_wiring.py`, `tools/test_relay_subscribers.py` and `tools/test_agy_hooks.py`
pin the result against the installed runtime. Before merging, complete the
reviewed deployment and preflight sequence above on every host. Record the
prior pairs with the new relay's
`relay pairs --harness <harness> --target <settings>`, and freeze the rollback: revert the
image commit, which restores the prior runtime and subscriber paths, both still in place.

Land the images with no Codex process running. Close every session, run
`codex app-server daemon stop` for the personal home (`CODEX_HOME` unset) and
`CODEX_HOME="$HOME/.codex-work" codex app-server daemon stop` for the work home, then
confirm `pgrep -a codex` prints nothing. A `codex-trust` line in `pgrep -a codex` is a
hook finishing; check again once it exits. If the only survivor is
`codex app-server daemon pid-update-loop`, `daemon stop` does not end it once the
daemon itself has exited (`notRunning`), so end that leftover updater with `SIGTERM`
after user confirmation; stop on any other survivor rather than killing it.
Codex then asks to re-trust each changed hook. Review it in each home from a
`--no-daemon` launch with no bypass flag (`--dangerously-bypass-approvals-and-sandbox`,
`--dangerously-bypass-hook-trust`): `codex --no-daemon` for the personal home
(`CODEX_HOME` unset), `cow` for the work home. Codex writes its own trust and nobody
edits trust hashes. The personal home's new `[hooks.state]` hashes land in tracked
`harnesses/codex/config.toml`; commit that change after the review. The work home's
land in untracked local/codex/config.work.toml. A rollback stops Codex the same way
and reverts the images commit (or runs `git revert -m 1 <merge>`, noting that a
whole-merge revert also reverts any runbook and task-record changes in the merge),
which returns the images to their previous runtime and subscriber file. The CLI pin moves
in its own commit and stays where it is, and the restored table selects its previous subscriber and reconciliation files; Codex then
asks again, and the same review writes the old hashes back in both homes. Commit the
personal home's restored `[hooks.state]` hashes in `harnesses/codex/config.toml` too.
Restore no trust from a copy: the work file holds other live settings.

Real phone-gate acceptance and home-link changes have their own rollout
gates. Equivalent hosts and profiles using the same
installer and launcher are covered by one end-to-end check; a distinct service or
configuration path needs its own check.
