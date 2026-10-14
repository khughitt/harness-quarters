---
id: hq-305ede
title: Isolated Claude first-run onboarding can leave an initial command-line prompt unsubmitted. Experiment guidance should finish onboarding and verify a real conversation/tool call before assuming the seed prompt ran.
status: idea
priority: 2
created: 2026-10-14T10:43:34Z
updated: 2026-10-14T10:43:34Z
depends: []
tags: [feedback, gap, "from:trans"]
agent: codex
---

Observed with Claude Code 2.1.296 and a fresh private configuration directory: theme, terms, directory trust and permission-mode notice preceded an idle session with no transcript/tool call; manually entering the same prompt produced the intended tool call and receipt. Prepared preference copy also used a sibling configuration path while this version wrote its config inside the private directory; capture that version-specific path and cleanup contract in capability guidance.
