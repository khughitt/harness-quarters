---
id: tack-341dcc
title: "Design-doc rule: keep the rule, move the mechanics to the hook message"
status: done
priority: "2"
size: xs
complexity: low
process: direct
owner: main
created: 2026-09-16T15:51:27Z
updated: 2026-09-16T21:48:02Z
started: 2026-09-16T21:47:12Z
completed: 2026-09-16T21:48:02Z
depends: []
parent: tack-9ec1eb
tags: [rules]
source: "mindful:thought:8e45d49e001c4e5eb9b00f159dc60e87"
model: "claude-opus-5[1m]"
agent: "claude-code/claude-opus-5[1m]"
---

Why: AGENTS.md's design-doc bullet is 228 words (audit row A13, removal rank 1); the hook (ops hooks/claude-pretooluse check 4) blocks the staging and its refusal already names the checkout's convention and the instruction-file line to add. The rule did not stop attempts (three sessions on 2026-09-15); the hook did. Done: the bullet says only that specs and plans are not committed by default, that a checkout opts in by naming the directory in its own AGENTS.md/CLAUDE.md or the user says so in session, and that otherwise the doc is written at the skill's path and excluded via .git/info/exclude and copied out before a worktree is removed (~70 words). The docs/superpowers migration clause and the git config escape hatch move into the hook's refusal text if they are not already there (read it first; add nothing the message already says). Where: AGENTS.md Design & Plan Docs; ops hooks/claude-pretooluse lines 18–28 and the message it emits. Check: word count; a scratch repo stage of docs/superpowers/specs/x.md is still blocked and the message still names the opt-in line.

## Notes

- 2026-09-16T21:48:02Z (prune-agents): Design-doc bullet 229 -> 106 words: the rule, the instruction-file opt-in, the in-session opt-in, the exclude recipe and the copy-out-before-worktree-removal clause. The docs/superpowers migration clause and the git config escape hatch were already in the hook's refusal text (ops hooks/claude-pretooluse, three branches), so nothing was added there. Verified: the hook still blocks a docs/superpowers stage in a scratch repo (exit 2) and names the opt-in line.
