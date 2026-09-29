---
id: tack-58f6b7
title: Make khughitt/tack public
status: doing
priority: 3
size: xs
complexity: low
process: direct
owner: main
created: 2026-09-27T13:35:14Z
updated: 2026-09-29T09:02:54Z
started: 2026-09-29T09:02:54Z
depends: [tack-8062ad, tack-688cda, tack-90bf74]
parent: tack-5b608f
tags: []
agent: claude-code/claude-opus-5-5
---

Why: the goal ends public. Only after the audit sibling's remediation has landed and the user has confirmed the result.

Done: gh repo edit khughitt/tack --visibility public --accept-visibility-change-consequences with khughitt active; README states what the project is for a stranger. Check: gh repo view shows PUBLIC; a logged-out fetch of the README works.

## Notes

- 2026-09-29T09:02:54Z (main): started
  provenance: {"harness_session":"claude-code:344dc247-3419-4443-85b2-8c2de56a3ee4","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
