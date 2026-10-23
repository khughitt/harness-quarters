---
id: hq-ca4cb5
title: Tool runner requires unavailable approval after explicit user authorization
status: idea
priority: 2
created: 2026-10-23T01:34:33Z
updated: 2026-10-23T01:34:33Z
depends: []
tags: [feedback, friction, "from:ops"]
agent: codex
---

The user explicitly authorized a narrowly scoped repository restore and separate path commit. Retrying the authorized restore was rejected before execution with approval required by policy, but AskForApproval is set to Never. The runner cannot surface the required approval and the agent cannot proceed without bypassing the rejection. Provide a supported route for authorized actions or a clear actionable policy error.
