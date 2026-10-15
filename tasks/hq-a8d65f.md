---
id: hq-a8d65f
title: Install the pinned pi on europa and link its agent directory from hq
status: todo
priority: 2
size: xs
complexity: low
process: direct
created: 2026-10-15T21:14:37Z
updated: 2026-10-15T21:14:37Z
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
