---
id: tack-dab117
title: Agents write scratchpad files as bare 'scratchpad/<file>' paths that resolve nowhere
status: todo
priority: 2
size: xs
complexity: low
process: direct
created: 2026-09-27T12:19:35Z
updated: 2026-10-02T15:29:13Z
depends: []
tags: [rules]
agent: claude-code/claude-opus-5-5
---

Why: an end-of-turn report named a draft as `scratchpad/issue-worktree-race.md` (observed 2026-09-27). It reads as relative to the checkout, but the file lived in the session's scratchpad directory under the host's tmp storage, so the user could not open it and had to ask. The harness system prompt calls that directory "the scratchpad", which invites the shorthand. It is the same class as the worktree path bullet in AGENTS.md Git: a path the user cannot resolve from where they stand.

Done when the global AGENTS.md says, in the Communication section (not Git: the scratchpad is not a git concept): a path shown to the user is one they can open from the main checkout, so relative to the main checkout when it lives there and absolute otherwise, never relative to a directory only the agent knows, such as the scratchpad. Keep the existing Git bullet's "avoid machine-specific absolute paths in code comments and docs" distinct: that rule covers committed text, this one covers what the agent tells the user. Check how AGENTS.md's mirrors are generated before editing, and that the line renders in each.

Where to look: AGENTS.md "Communication" and the worktree path bullet under "Git"; the session-logs skill if a before/after sample of reports naming scratchpad files is wanted (optional, not the gate).

## Notes

- 2026-10-02T15:29:12Z (main): scope: scoped; todo P2 xs/low/direct; one Communication-section line for paths shown to the user, distinct from the committed-text absolute-path rule; the session-logs sample made optional
