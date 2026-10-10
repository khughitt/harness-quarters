---
id: hq-cc17de
title: Keep live model choices through Git updates
status: done
priority: 2
created: 2026-10-10T13:19:14Z
updated: 2026-10-10T18:47:09Z
completed: 2026-10-10T18:47:08Z
depends: []
tags: []
source: docs/notes/2026-10-10-live-model-preservation-brief.md
agent: codex
---

Preserve the user's live model and effort choices when Git replaces tracked harness settings, without reviving an intentional reset or overwriting newer choices. The first milestone is a reviewed persistence and reset contract backed by temporary-repository acceptance cases. The originating report is hq-a77096; scope handoff: docs/notes/2026-10-10-live-model-preservation-brief.md. This is a bounded state-hygiene feature, not a general harness configuration manager.

## Notes

- 2026-10-10T18:47:08Z (main): outcome: approved contract and implementation shipped through hq-14d183 and hq-a77096; all descendants closed. The two filtered live picks survive Git rewrites through Stop capture and Git/Stop restoration, newer values win, and deliberate resets use forget. Claude tracked effortLevel remains the explicitly separate hq-47faaa idea.
- 2026-10-10T18:47:08Z (main): done
  provenance: {"harness_session":"codex:01a12670-d6de-7d63-9f73-311c764cbfab","harness_session_source":"CODEX_THREAD_ID"}
- 2026-10-10T18:47:08Z (main): Goal met: reviewed live-pick preservation rolled out into main, exact current picks preserved and saved, 878 main tests passed, fresh integration review accepted. Both child efforts complete.
  provenance: {"harness_session":"codex:01a12670-d6de-7d63-9f73-311c764cbfab","harness_session_source":"CODEX_THREAD_ID"}
