---
id: hq-a8d65f
title: Install the pinned pi on europa and link its agent directory from hq
status: doing
priority: 2
size: xs
complexity: low
process: direct
owner: main
created: 2026-10-15T21:14:37Z
updated: 2026-10-19T09:19:00Z
started: 2026-10-19T09:13:59Z
depends: []
parent: hq-aa9b44
tags: []
agent: claude-code/claude-opus-5-5
---

Why: the user wants pi installed and configured on europa as on titan. hq-61a47e landed the tracked pi/settings.json and its [harness.pi.links] entry (merge 6b434eb); europa reads the same hq checkout through Dropbox, so it gets the same settings file and, by design, the same deviceId (README pi entry).

Done, on europa:
- `just pi-install` from hq main installs pi 1.1.0 under ~/.local/share/pi/1.1.0; `pi --version` prints 1.1.0 through ~/.local/bin/pi.
- Before pi's first run: `mkdir -p ~/.pi/agent`, then `just link --apply` from hq main (the README's new-host route; if pi already ran there, move its real settings.json aside first, carrying any configuration into pi/settings.json). `just link-check` exits 0.
- ~/.pi/agent/settings.json and AGENTS.md resolve into hq and lore; one interactive pi start shows no changelog (the tracked lastChangelogVersion matches the pin) and leaves `git status` clean apart from a size-only mark.
- auth.json is per host: log in on europa as needed; it never enters hq.

Not blocked by hq-24416e: pick preservation reaches europa when that lands, through the same checkout.

## Notes

- 2026-10-16T00:42:03Z (main): hq-24416e is merged and rolled out on titan. Europa: run just link --apply from hq main; it now also creates ~/.pi/agent/extensions/harness-state.ts. Run just link-check and verify pi defaults survive capture plus checkout. Do not point the extension or refresh command at a worktree.
- 2026-10-19T09:13:59Z (main): started
  provenance: {"harness_session":"claude-code:0b615834-ed7a-43c8-92d4-87a942bab2d7","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-10-19T09:14:07Z (main): arm: flow-trial-1 — unit tack-aa9b44 — flow on
- 2026-10-19T09:14:27Z (main): gate: scoped — adopted
  provenance: {"harness_session":"claude-code:0b615834-ed7a-43c8-92d4-87a942bab2d7","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-10-19T09:14:27Z (main): gate: implementing main — host rollout on europa run from hq main as AGENTS.md requires for link apply, no repository change
  provenance: {"harness_session":"claude-code:0b615834-ed7a-43c8-92d4-87a942bab2d7","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-10-19T09:19:00Z (main): europa ran tasks 0.2.0, which failed to parse current records (just link: tasks projects --paths parse error on a quoted-timestamp field); upgraded to 0.4.0 with cargo install --locked --path ~/d/tasks at b253252, the commit titan runs
