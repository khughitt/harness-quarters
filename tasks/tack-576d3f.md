---
id: tack-576d3f
title: Profiles name the per-command gh account form for GitHub writes
status: todo
priority: 2
size: xs
complexity: low
process: direct
created: 2026-10-02T14:52:40Z
updated: 2026-10-02T14:52:40Z
depends: [ops-1d4106]
tags: []
source: ops-1d4106
agent: claude-code/claude-opus-5-5
---

Why: agents/profiles/personal.md and work.md say to check 'gh auth status' and run 'gh auth switch --user <account>' before a write. The active account is global state, and a concurrent session can switch it back between the switch and the write (ops-1d4106).

Done: after ops-1d4106 lands (the ops pretooluse guard accepts 'GH_TOKEN=$(gh auth token --user <account>) gh <write>' when it names the profile's account), personal.md, work.md and external.md recommend that per-command form for gh writes and keep 'gh auth switch' as the fallback. Mirrors regenerated as tack's AGENTS.md requires.

Check: the profile text matches the guard's refusal message, and one real gh write in a personal checkout goes through the per-command form without a refusal.
