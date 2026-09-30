---
id: tack-451c9a
title: "Check whether upstream superpowers' codex-tools.md still omits the V2 thread cap, and whether it is already reported"
status: todo
priority: 3
size: xs
complexity: low
process: direct
created: 2026-09-30T14:23:53Z
updated: 2026-09-30T14:23:53Z
depends: []
tags: [skills]
source: tack-e3cef2
agent: claude-code/claude-opus-5-5
---

tack-e3cef2 found that multi-agent V2 caps a Codex session at agents.max_concurrent_threads_per_session threads (default 4: root + 3 children), evicts finished children oldest-first, and never evicts running ones. The vendored superpowers v6.4.1 reference (agents/vendor/superpowers/skills/using-superpowers/references/codex-tools.md, Lifecycle bullet) says only that finished children are evicted when slots are needed. The draft upstream issue text is in tack-e3cef2's notes.

Step 1: check the latest upstream release and main of obra/superpowers: does codex-tools.md (or its successor) still omit the default cap, that running children are never evicted, and the config key?
Step 2, only if it does: search obra/superpowers issues and PRs (open and closed) for a report of the thread limit, 'agent thread limit reached', or max_concurrent_threads_per_session.

Done when both findings are in a note with links, and a recommendation for the user: nothing to do (fixed upstream, then consider bumping the vendored submodule), comment on an existing issue or PR, or file the draft as a new issue. Filing or commenting is the user's call, not part of this task.
