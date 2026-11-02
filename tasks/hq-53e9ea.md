---
id: hq-53e9ea
title: Detect drift between the records-hook test fixture and the records repository's pre-commit hook
status: idea
priority: 4
created: 2026-11-02T20:00:59Z
updated: 2026-11-02T20:00:59Z
depends: []
tags: [rename-cutover]
source: hq-5300fd
agent: claude-code
origin: agent
---

tools/fixtures/records-hook/pre-commit is a byte copy of the records repository's .githooks/pre-commit, so the rename-cutover tests meet the live refusal. Tests cannot read the live file, and its README asks whoever changes the hook to re-copy it, which nothing enforces. Possible routes: a records-repository hook or check that compares the two when both checkouts are present, or an hq check run on a host with the records repository. Source: hq-5300fd Task 1.

## Notes

- 2026-11-02T20:00:59Z (add): created
  provenance: {"harness_session":"claude-code:7104a322-b727-4975-8f34-3d210db837b3","harness_session_source":"CLAUDE_CODE_SESSION_ID","origin":"agent"}
