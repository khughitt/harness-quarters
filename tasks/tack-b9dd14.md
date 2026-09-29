---
id: tack-b9dd14
title: "Guidance for PRs to external repos: always draft, follow CONTRIBUTING and PR templates"
status: done
priority: "2"
size: s
complexity: low
process: direct
owner: main
created: 2026-09-14T14:11:13Z
updated: 2026-09-14T14:15:45Z
started: 2026-09-14T14:14:25Z
completed: 2026-09-14T14:15:45Z
depends: []
tags: [rules]
source: "https://github.com/anomalyco/opencode/pull/48990"
model: "claude-opus-5[1m]"
agent: "claude-code/claude-opus-5[1m]"
---

Extend the agent guidance (the Git section of AGENTS.md, mirrored into the harness-specific instruction files) for pull requests against repositories the user does not own:

1. Always open such PRs as drafts (`gh pr create --draft`); the user promotes them to ready for review.
2. Before opening the PR, read the repository's contribution guidelines — CONTRIBUTING.md (any casing, at the root or under .github/ or docs/), .github/PULL_REQUEST_TEMPLATE.md or PULL_REQUEST_TEMPLATE/*, and any repo-level AGENTS.md / CLAUDE.md with contributor rules — and make the branch, commits, PR title, and PR body meet every stated convention (title format, base branch, template sections filled with real content, sign-off, changelog entries, tests). If a convention cannot be met, say so before opening the PR rather than opening one that violates it.

Context: an agent recently submitted a bug-fix PR to opencode (see source) as a draft but without reading the contributor guidelines first, and the PR was flagged for it. Draft status alone is not enough; the pre-submission check is the missing step.

Verification: the rule appears in AGENTS.md and every harness instruction file it is mirrored to (check how the existing Git rules are propagated, e.g. ~/.claude/CLAUDE.md), and a dry read of the rule by a fresh session produces the draft flag and the guideline check.

## Notes

- 2026-09-14T14:15:45Z (ai-b9dd14): External-repo PR rule added to the Git section of AGENTS.md (draft always; read CONTRIBUTING / PR template / repo AGENTS.md first and meet every convention). Reaches Claude Code, Codex, and opencode through their AGENTS.md symlinks. Tag dictionary added to tasks/.config.toml with rules, skills, quick-add, obs.
