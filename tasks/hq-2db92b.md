---
id: hq-2db92b
title: A listed coding skill cache path was absent; an installed version was found at a different cache version.
status: shelved
priority: 2
created: 2026-10-04T08:58:53Z
updated: 2026-10-08T10:38:43Z
depends: []
tags: [feedback, friction, "from:mind6"]
agent: codex
---

Observed 2026-10-04 in a mind6 Codex session (01a10620-6c94-7382-a4ad-acf3540e572e): 24 s after the session started, its skill list named /home/keith/.codex/plugins/cache/ponytail/ponytail/4.10.1/skills, but the cache held only 1.0.0, so a cat of the listed ponytail SKILL.md failed and the agent read the 1.0.0 copy instead.

Scope 2026-10-08: the ponytail plugin (git marketplace github.com/DietrichGebert/ponytail, enabled in codex/config.toml) has moved through 4.10.0, 4.10.1, 1.0.0, 4.13.0 and 5.0.0 since 2026-09-20, judged from the roots listed in session starts; Codex replaces the cache directory on each update and keeps one version. Recent sessions (2026-10-08, 5.0.0) list roots that exist. Unknown: whether Codex built the list before a startup refresh replaced the directory, or reads the version from another source than the cache. One recovered read; nothing in hq pins or controls plugin versions. Code hq does not maintain (Codex and the plugin), so the upstream search comes first if it wakes.

## Notes

- 2026-10-08T10:38:41Z (main): shelved: A second report of a listed Codex plugin skill root being absent at read time, or a decision to pin or remove the ponytail plugin
- 2026-10-08T10:38:41Z (main): scope: shelved; one recovered read on 2026-10-04; ponytail changed version five times since 2026-09-20 and current sessions list roots that exist; mechanism (startup refresh vs list source) unknown and upstream-owned; wakes on a second report or a pin/remove decision
