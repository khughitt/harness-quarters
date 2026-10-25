# Pinned relay runtime

`relay/package.json` selects v0.2.0; `relay/package-lock.json` fixes its commit to
`067c63921602e694682d47bdb2412862359c75ff`. The declared home launcher resolves to
`relay/bin/relay`, which reads that pin and runs the versioned installation under
`$HOME/.local/share/relay/`. Node and npm come from `/usr/bin`.

After approval for a live rollout, run `just relay-install` from the reviewed
checkout before merging its pin into main. This installs the new runtime in its
stable versioned directory before the home launcher selects it. Resolve
`command -v relay`, inspect `readlink -f` of that path, and check `relay --version`
after merging. Never point the home launcher at a worktree.

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
paths. Keep their referenced installations until a separately approved hook
cutover replaces them. The historical [operator cutover](relay-cutover.md)
describes the v0.1.1 hook rollout. Real phone-gate acceptance and home-link changes
have their own rollout gates. Equivalent hosts and profiles using the same
installer and launcher are covered by one end-to-end check; a distinct service or
configuration path needs its own check.
