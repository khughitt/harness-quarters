---
id: tack-57f4eb
title: "Attribution rule: none by default, the target repo's disclosure policy wins"
status: done
priority: "2"
size: xs
complexity: low
process: direct
owner: main
created: 2026-09-14T14:25:49Z
updated: 2026-09-14T14:26:29Z
started: 2026-09-14T14:26:00Z
completed: 2026-09-14T14:26:29Z
depends: []
tags: [rules]
model: "claude-opus-5[1m]"
agent: "claude-code/claude-opus-5[1m]"
---

Reword the Git rule 'Do NOT add any AI-attribution trailer or footer' so that no attribution is the default behaviour, but a repository's stated contribution policy takes precedence: when the guidelines ask for disclosure of AI assistance, include the model and harness in the form the repository specifies — a PR template section, a named commit trailer such as Assisted-by:, or Co-authored-by:. Harness-injected forms (Claude-Session:, the session URL, 'Generated with Claude Code') are never a repository's request and stay forbidden. The hook exemption that lets a requested Co-Authored-By through in non-owned repos is the ops claude-pretooluse task.

## Notes

- 2026-09-14T14:26:29Z (gh-rules): Attribution rule reworded: none by default, the target repo's disclosure policy wins in the form it specifies; harness-injected forms stay out everywhere.
