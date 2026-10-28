---
id: hq-ef1cb3
title: "session-archive import: bring the 584 pre-2026-08-31 Claude Code sessions from the 2026-08-30 tarball into the archive"
status: todo
priority: 2
size: m
complexity: mid
process: planned
created: 2026-10-28T13:02:05Z
updated: 2026-10-28T13:02:05Z
depends: []
tags: []
agent: claude-code
---

Keith, 2026-10-28. Audit of the same day: /mnt/backup/agent-sessions mirrors the five live roots since 2026-10-01 and covers everything from 2026-08-31 on. /mnt/ssd3/claude-codex-state-2026-08-30.tgz (10.7 GB) is a pre-reset snapshot of ~/.claude and ~/.codex: its Codex rollouts (12,866) and archived sessions (594) are 100% present in the archive already, but .claude/projects/ holds 589 top-level sessions (Jul-Aug 2026, 76 project slugs) plus 934 subagent files, 1.2 GB, of which only 5 are in the archive. The archiver has capture, prune, status, promote and probe-codex, and no import. Scope: an import subcommand that stages a snapshot's .claude/projects/ under a distinct source name (e.g. claude-pre-2026-08-31) with its own manifest rows (sha256, size, mtime, captured_at) rather than dropping files into the live store or editing the mirror rows by hand; keep the archive's longer copy for the 5 overlapping uuids; record the import as a run. Extract only .claude/projects/* from the tarball into a staging directory, never the whole archive. Related: ops-7b325c (second copy of the archive).

## Notes

- 2026-10-28T13:02:05Z (add): created
  provenance: {"harness_session":"claude-code:77c3552c-2013-4e7a-a286-520748289fe9","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
