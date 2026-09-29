---
id: tack-273c7a
title: "Attribution rule: guidelines read before work starts; attribution only where explicitly requested, at that level"
status: done
priority: "1"
size: xs
complexity: low
process: direct
owner: main
created: 2026-09-14T14:38:08Z
updated: 2026-09-14T14:38:26Z
started: 2026-09-14T14:38:20Z
completed: 2026-09-14T14:38:26Z
depends: []
tags: [rules]
model: "claude-opus-5[1m]"
agent: "claude-code/claude-opus-5[1m]"
---

Correction to ai-57f4eb. Before beginning work that will be contributed to a repository I do not maintain: read its contributor guidelines (CONTRIBUTING, developer/hacking guides, PR template, repo-level AGENTS.md or CLAUDE.md). If agent attribution is explicitly requested per commit, include the trailer they name in each commit; if requested for PRs, include it in the PR body; otherwise include neither. Harness-injected forms stay out everywhere. Also move the guideline-reading step in the external-PR bullet from 'before opening the PR' to 'before beginning work'.

## Notes

- 2026-09-14T14:38:26Z (ai-273c7a): Attribution bullet rewritten: guidelines read before work begins; attribution per commit or in the PR body only where explicitly requested, otherwise neither. External-PR bullet now refers to those guidelines instead of re-reading at PR time.
