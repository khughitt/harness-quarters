---
id: hq-1adbfe
title: Claude root-session location queries no longer see phantom parent rows from child request records
status: idea
priority: 2
created: 2026-10-20T20:17:51Z
updated: 2026-10-20T20:17:51Z
depends: []
tags: [feedback, positive, "from:obs"]
agent: codex
---

After the child-request routing fix and successful live index renewal, the count of subagent=0 session rows in child transcript files is zero (previously 150). A Claude root ID's subagent=0 rows now live only in its root transcript file; agentId request records without isSidechain route to the child.
