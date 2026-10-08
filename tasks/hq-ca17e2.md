---
id: hq-ca17e2
title: "The requirement to run the full pre-commit gate also covers task-record and brief-only scoping passes; it repeats a six-minute code suite with unchanged code. Clarify whether fresh record, document and whitespace checks may reuse the prior code-suite result."
status: idea
priority: 2
created: 2026-10-03T17:50:03Z
updated: 2026-10-08T09:48:44Z
depends: []
tags: [feedback, friction, "from:obs"]
agent: codex
---

## Notes

- 2026-10-08T09:48:44Z (main): scope: drop; misfiled: obs's own AGENTS.md:11-12 requires 'just gate before commits', and its justfile:21 gate runs 'check test'; obs has no pre-commit hook and no docs-only path (ops shipped one in ops-93aa55 / 0686b78), so obs owns the fix, not hq; proposal: refile to obs as feedback (a record- or docs-only commit runs 'just check', not the suite), then drop
