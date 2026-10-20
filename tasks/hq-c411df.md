---
id: hq-c411df
title: "session-episodes reads only the default Claude projects store and Codex sessions store, so a scoping or audit agent cannot reach a report's origin session in a second harness home, Codex archived sessions, the backup archive or another host"
status: idea
priority: 2
created: 2026-10-20T11:19:18Z
updated: 2026-10-20T11:19:18Z
depends: []
tags: [feedback, gap, "from:lore"]
agent: claude-code
---

Found while checking whether stamped friction reports can be traced to their origin sessions: the reader's default roots are the primary Claude projects store and the primary Codex sessions store, each overridable by one environment variable, so one run covers one store per harness. A report whose origin is in another home, an archived rollout or the post-prune archive, or on the other host, gives no result and no explicit unavailable status. Acceptance for the friction-context work needs retrieval from a live transcript, its archived copy and another host, or an explicit unavailable result.
