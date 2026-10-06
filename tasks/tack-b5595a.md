---
id: tack-b5595a
title: "The second host has an undeclared Codex skill directory, security-best-practices: declare it or remove it"
status: idea
priority: 3
size: xs
created: 2026-10-06T16:00:08Z
updated: 2026-10-06T16:00:08Z
depends: []
tags: []
source: tack-dcb11a
agent: claude-code/claude-opus-5-5
---

The residue's surface audit (tack-dcb11a, second host) found ~/.codex/skills/security-best-practices: a real directory (SKILL.md and LICENSE.txt, dated 2026-02-17), not a link and not a harness-owned name like .system. No manifest line declares it and this host has no such skill, so the two hosts' Codex sessions differ. Decide: give it an owner and declare it in links.toml (and in lore's corpus if it is kept), or remove it from that host.
