---
id: hq-b9a9d1
title: Decide whether the work Codex config takes the request-only notification allowlist
status: todo
priority: 2
size: xs
complexity: low
process: direct
created: 2026-10-17T02:58:30Z
updated: 2026-10-17T15:27:53Z
depends: []
tags: []
source: hq-1ec500
agent: claude-code/claude-opus-5-5
---

The personal codex/config.toml now notifies only for approval-requested, plan-mode-prompt and async-question (accepted live 2026-10-16). The private work config under local/ was deliberately left unchanged. Whether work sessions should drop completion popups too is the user's call.

## Open questions

- Should the work Codex config (local/codex/config.work.toml, untracked) take the same `[tui] notifications = ["approval-requested", "plan-mode-prompt", "async-question"]` allowlist as the personal codex/config.toml? Today it sets no `notifications` key, so every type fires, including `agent-turn-complete` for internal subagents (`multi_agent = true` there too). Unlike the personal config it sets no `approval_policy`, so approval requests can reach you in work sessions and the allowlist would keep them. Taking it means losing ordinary completion popups in work sessions, as on the personal side. Context: docs/notes/2026-10-15-agent-attention-brief.md (Codex section; live acceptance in hq-1ec500).

## Notes

- 2026-10-17T13:09:21Z (main): scope: question; checked local/codex/config.work.toml: [tui] has no notifications key (all types fire, including completions of internal agents under multi_agent = true) and no approval_policy (approvals reachable); added one open question: whether work sessions take the personal request-only allowlist and lose completion popups
- 2026-10-17T15:27:45Z (main): answer (user, 2026-10-17): yes — the work Codex config adopts the personal request-only allowlist.
