---
id: tack-dab117
title: Agents write scratchpad files as bare 'scratchpad/<file>' paths that resolve nowhere
status: idea
priority: "2"
created: 2026-09-27T12:19:35Z
updated: 2026-09-27T12:19:35Z
depends: []
tags: [rules]
agent: claude-code/claude-opus-5-5
---

Observed 2026-09-27: an end-of-turn report named a draft as scratchpad/issue-worktree-race.md. It reads as relative to the checkout, but the file lived in the session's scratchpad directory (an absolute path under the host's tmp storage), so the user could not open it and had to ask. The harness's system prompt calls that directory 'the scratchpad', which invites the shorthand. The same class as the worktree rule in AGENTS.md Git (a path the user cannot resolve from the main checkout). Question: does one line in AGENTS.md fix it (a path shown to the user is absolute, or relative to the main checkout when it lives there; never relative to a directory only the agent knows, such as the scratchpad), or should it join the worktree path bullet? Check: a sample of end-of-turn reports naming scratchpad files, before and after, via the session-logs skill.
