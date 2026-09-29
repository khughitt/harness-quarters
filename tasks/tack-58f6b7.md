---
id: tack-58f6b7
title: Make khughitt/tack public
status: todo
priority: 3
size: xs
complexity: low
process: direct
created: 2026-09-27T13:35:14Z
updated: 2026-09-28T09:27:32Z
depends: [tack-8062ad, tack-688cda, tack-90bf74]
parent: tack-5b608f
tags: []
agent: claude-code/claude-opus-5-5
---

Why: the goal ends public. Only after the audit sibling's remediation has landed and the user has confirmed the result.

Done: gh repo edit khughitt/tack --visibility public --accept-visibility-change-consequences with khughitt active; README states what the project is for a stranger. Check: gh repo view shows PUBLIC; a logged-out fetch of the README works.
