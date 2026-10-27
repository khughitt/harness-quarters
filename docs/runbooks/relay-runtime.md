# Pinned relay runtime

`relay/package.json` selects v0.2.1; `relay/package-lock.json` fixes its commit to
`78a70be9b318511d88e0f8ca8d31f54807ed2540`. The declared home launcher resolves to
`relay/bin/relay`, which reads that pin and runs the versioned installation under
`$HOME/.local/share/relay/`. Node and npm come from `/usr/bin`.

After approval for a live rollout, run `just relay-install` from the reviewed
checkout before merging its pin into main. This installs the new runtime in its
stable versioned directory before the home launcher selects it. Resolve
`command -v relay`, inspect `readlink -f` of that path, and check `relay --version`
after merging. Never point the home launcher at a worktree. Every host that shares
this checkout selects the merged pin at once, and its launcher exits 127 until that
version is installed there. Other hosts cannot see this host's worktrees, so run
`just relay-install` in the main checkout on each of them as soon as the merge syncs.

On a new host, `just relay-subscribers` renders `relay/subscribers.template.json` into
`~/.config/relay/subscribers.json`, the file every relay hook passes with
`--subscribers`; it refuses to replace different content unless run with `FORCE=1`.

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

Preserve `inbox/seq`, entries, rejected files and presence. Verify a saved answer
survives the upgrade. Through the selected launcher and an isolated service, post
`relay inbox ask --file PATH`, answer with `relay inbox answer ID ITEM=VALUE
--surface terminal`, then run `relay inbox take ID` twice. The answer must survive
a service restart and repeated take must leave the consumed entry unchanged.
The installed package's `docs/runbooks/inbox-service.md` describes the envelope
and recovery contract.

Older services can quarantine entries containing take or refusal histories.
Do not downgrade a service against such a store or reset the durable sequence to
undo an upgrade. Keep the store intact and use a release that understands it.

The standalone pin does not rewrite installed hooks: those use absolute runtime
paths, and each harness's hook images move under their own approval. Codex's
(`codex/hooks.json`, `codex/work/hooks.json`) name v0.2.1, whose SessionStart
retires replaced Codex roots; Claude Code's (`claude/settings.json`) name v0.1.1,
which that release does not change. `tools/test_relay_wiring.py` holds each file's
version. Keep every installation a hook image names.

Root retirement assumes one active Codex root per process. TUIs launched with
`--no-daemon`, as the shell aliases for both Codex homes are, satisfy it. A Codex
launched without that flag starts a shared app-server daemon that outlives it, and
sessions hosted there could share its handle and retire each other's rows
(relay-511e14). Look for a running `codex app-server` before a rollout and after it
check that no registry row carries a daemon's pid.

To move Codex's hooks to the pinned release, install it into the stable root first,
then plan with its own installer on copies:

```zsh
/usr/bin/node "$HOME/.local/share/relay/<version>/node_modules/relay/bin/relay.js" install --harness codex --json --node /usr/bin/node --subscribers "$HOME/.config/relay/subscribers.json" --evidence FILE --target COPY
```

COPY is an absolute path ending in `/hooks.json` (any other name fails as `relay
operation failed`). Without `--apply` nothing is written; confirm the planned
`after` text differs from the current image only in the runtime directory. A
rehearsal before installation may plan from a scratch runtime and replace its path
with the expanded absolute stable path; the stable plan must then reproduce those
bytes.

Land the images with no Codex process running. Close every session, run
`codex app-server daemon stop` for the personal home (`CODEX_HOME` unset) and
`CODEX_HOME="$HOME/.codex-work" codex app-server daemon stop` for the work home, then
confirm `pgrep -a codex` prints nothing; stop on a survivor rather than killing it.
Codex then asks to re-trust each changed hook. Review it in each home from a
`--no-daemon` launch with no bypass flag (`--dangerously-bypass-approvals-and-sandbox`,
`--dangerously-bypass-hook-trust`): `codex --no-daemon` for the personal home, `cow`
for the work home. Codex writes its own trust and nobody edits trust hashes. The
personal home's new `[hooks.state]` hashes land in tracked `codex/config.toml`;
commit that change after the review. The work home's land in untracked
`local/codex/config.work.toml`. A rollback stops Codex the same way and reverts the
merge, which returns both the images and the CLI pin to their previous versions;
Codex then asks again, and the same review writes the old hashes back in both homes.
Restore no trust from a copy: the work file holds other live settings.

The historical [operator cutover](relay-cutover.md) describes the v0.1.1 hook
rollout. Real phone-gate acceptance and home-link changes have their own rollout
gates. Equivalent hosts and profiles using the same
installer and launcher are covered by one end-to-end check; a distinct service or
configuration path needs its own check.
