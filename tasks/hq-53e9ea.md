---
id: hq-53e9ea
title: Detect drift between the records-hook test fixture and the records repository's pre-commit hook
status: shelved
priority: 4
defer: 2026-12-05
created: 2026-11-02T20:00:59Z
updated: 2026-11-05T14:23:31Z
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
- 2026-11-05T14:23:31Z (main): shelved: Revisit when the records repository's pre-commit hook or hq's copied records-hook fixture changes, when an actual mismatch is reported, or at the 2026-12-05 checkpoint. As of this review the hooks match byte-for-byte with mode 0755; the fixture README's manual recopy contract remains in force. Choose an automation owner and invocation route only if new evidence warrants it. The user's 2026-11-02 keep-rename-cutover-for-now decision remains intact.
