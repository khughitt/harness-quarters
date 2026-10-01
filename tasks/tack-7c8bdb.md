---
id: tack-7c8bdb
title: "Session archive: Capture rollout on titan"
status: done
priority: 2
size: s
complexity: low
process: direct
owner: main
created: 2026-09-30T16:53:58Z
updated: 2026-10-01T14:14:32Z
started: 2026-10-01T10:57:53Z
completed: 2026-10-01T14:14:31Z
depends: [tack-0b328c]
parent: tack-401088
tags: [obs]
agent: claude-code/claude-opus-5-5
plan: docs/plans/2026-09-30-session-archive.md
step: "Task 16: Capture rollout on titan"
---

## Notes

- 2026-10-01T10:57:53Z (session-retention-job): started
  provenance: {"harness_session":"codex:01a0f381-ccbb-7391-b11a-a5ffa55c6bce","harness_session_source":"CODEX_SESSION_ID"}
- 2026-10-01T10:57:53Z (session-retention-job): gate: Proposed /mnt/backup/agent-sessions; current source directories total about 27G, and /mnt/backup has about 2.0T available. No host state changed.
- 2026-10-01T10:57:53Z (session-retention-job): parked (waiting on user, approval): After user approves /mnt/backup/agent-sessions and about 27G initial copy, merge reviewed branch, link units, then run the one-case pilot before full capture.
  provenance: {"harness_session":"codex:01a0f381-ccbb-7391-b11a-a5ffa55c6bce","harness_session_source":"CODEX_SESSION_ID"}
- 2026-10-01T11:18:47Z (main): resumed
  provenance: {"harness_session":"codex:01a0f381-ccbb-7391-b11a-a5ffa55c6bce","harness_session_source":"CODEX_SESSION_ID"}
- 2026-10-01T11:18:47Z (main): run: merged reviewed branch to main at 728c03b after just test passed 434 + 419 on branch and merged tree; just link reported four new unit links, just link --apply created them, and just link-check exited 0.
- 2026-10-01T11:19:53Z (main): run: /mnt/backup is mounted rw on ext4 with about 2.0T free. Created /mnt/backup/agent-sessions (0700), marker (0600), and ~/.config/session-archive/config.toml (0600) with the approved archive root and obs command. No timer enabled yet.
- 2026-10-01T11:21:54Z (main): run: pilot on the mounted backup disk passed end to end with one temporary file in each of five source roots: first capture copied 1/1 per source with failed 0, read-back SHA-256 matched all five, second capture unchanged 1/1 per source, and status was healthy (81 archive bytes). Temporary pilot trees were cleaned. Live status before first capture exited 1 with missing-manifest JSON and created no manifest.
- 2026-10-01T11:36:21Z (main): run: first foreground capture was deliberately stopped after 683s because its 1-hour timeout was too short at the observed backup-disk rate. It had durably recorded 2,225 Claude versions totaling 1,137,496,233 bytes; there was no completed run record and no .capture temporary file. One stored file matched its manifest SHA-256. Resume with an 8-hour foreground timeout; the existing versions make the run incremental.
- 2026-10-01T11:42:29Z (main): run: resumed foreground capture under 8-hour timeout after inspecting the stopped partial copy; current process is tracked by the active terminal session, with no detached job or timer.
- 2026-10-01T11:55:55Z (main): run: resumed capture is tracked as exec session 7356, process PID 792320, foreground timeout 8h; initial archive had 2,225 Claude versions and 1.14G. No timer enabled while it runs.
- 2026-10-01T14:09:47Z (main): run: 152 min (est 480, idle); first full capture 152, verification 1; success: all five sources failed 0, 21,319 copied and 2,223 unchanged, archive_bytes 28,962,997,392, status ok true with no quarantine or divergence. SHA-256 spot checks matched live, archive, and manifest for one Claude and one Codex file. First aborted 11-minute attempt is noted separately.
- 2026-10-01T14:11:12Z (main): run: second capture completed in 24.19s with failed 0: unchanged 6,170 Claude, 1,293 Claude-work, 14,983 Codex, 594 archived Codex, 483 work Codex; copied 68 and diverged 5 across concurrently changing Claude files. This is predominantly unchanged and confirms incremental operation.
- 2026-10-01T14:14:31Z (main): run: capture timer enabled and active; next trigger 2026-10-02 04:00 EDT. Prune timer inactive. Manual systemd capture service invocation exited 0, Result=success, with failed 0 across all sources; status remains ok true. After scheduled runs on Oct 2 and Oct 3, the next session owner checks status and journal.
- 2026-10-01T14:14:31Z (main): done
  provenance: {"harness_session":"codex:01a0f381-ccbb-7391-b11a-a5ffa55c6bce","harness_session_source":"CODEX_SESSION_ID"}
