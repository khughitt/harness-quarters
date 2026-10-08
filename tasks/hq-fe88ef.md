---
id: hq-fe88ef
title: Hook commands name the lore and ops checkouts by path; link them under ~/.local/bin so a rename of either costs no Codex re-trust
status: todo
priority: 3
size: s
complexity: mid
process: direct
created: 2026-10-06T13:23:04Z
updated: 2026-10-08T10:19:52Z
depends: []
parent: hq-72fd4b
tags: []
source: tack-8b7a28
agent: claude-code/claude-fable-5-1
---

Why: the September rename moved harness-state-refresh behind a ~/.local/bin link so its command string survives a rename. The profile hook (~/d/lore/hooks/claude-profile) and ops's five hooks (claim-guard, claude-sessionstart, claude-provenance, claude-pretooluse, claude-posttooluse) are still named by checkout path in claude/settings.json, codex/hooks.json, codex/hooks.work.json and the untracked local/claude/settings.work.json. Codex keys hook trust by a hash of the command ([hooks.state.*] trusted_hash in codex/config*.toml), so renaming lore or ops would change those strings and cost a re-trust in every Codex home on both hosts. Changing them now costs one re-trust. From the rename design §3.

Decision (scope 2026-10-08): declare the six links in links.toml [required] beside harness-state-refresh, targets lore:hooks/claude-profile and ops:hooks/<name>, keeping each hook's own name. Rejected: adding them to ops's just install, since home routing is declared in hq. familiar's hooks (~/d/familiar/bin/familiar) have the same exposure but an npm-installed familiar is already on PATH, so a ~/.local/bin link would shadow it or be shadowed; that stays with fam.

Done: the six ~/.local/bin links declared and applied with just link --apply from main on both hosts; every command in the four settings files names ~/.local/bin, not ~/d/lore or ~/d/ops (a test in just test asserts this for the tracked files); each Codex home on each host re-trusted once, its saved trust kept by the README's procedure; a Claude and a Codex session on each host show the profile line and claim-guard still fires on Stop.

Where: links.toml [required]; claude/settings.json; codex/hooks*.json; local/claude/settings.work.json; README.md (Codex trust); docs/specs/2026-10-06-rename-to-hq-design.md §3; docs/notes/2026-10-08-declared-surface-drift-brief.md.

## Notes

- 2026-10-08T10:19:50Z (main): scope: scoped; todo under hq-72fd4b, P3 s mid direct; six hook links (lore claude-profile, five ops hooks) declared in links.toml [required], ops's just install rejected, familiar left to fam (npm familiar already on PATH); brief: docs/notes/2026-10-08-declared-surface-drift-brief.md
