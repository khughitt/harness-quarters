---
id: hq-fc34cb
title: "hq sessions: a unix-socket stdout whose reader did shutdown(SHUT_RD) is not detected as closed"
status: doing
priority: 3
size: xs
complexity: low
process: direct
owner: fix/hq-fc34cb-shut-rd-socket
created: 2026-11-08T16:53:53Z
updated: 2026-11-10T02:19:31Z
started: 2026-11-10T02:18:15Z
depends: []
tags: []
source: hq-d9d059
agent: claude-code/claude-opus-5-5
origin: agent
---

Deferred minor from hq-d9d059's round-2 review (tools/hq_cli/cli.py broken()/main): poll on a unix socket whose peer did shutdown(SHUT_RD) shows neither POLLERR nor POLLHUP, yet writes fail with EPIPE, so the BrokenPipeError branch re-raises (exit 120 with a traceback) where the pre-hq-d9d059 code dup2'd /dev/null over stdout unconditionally and exited quietly. Suggested fix: when a BrokenPipeError arrives and broken() detects neither output, silence stdout (the old assumption) rather than re-raise; a socketpair test with the reader's SHUT_RD, seen to fail first.

## Notes

- 2026-11-08T16:53:53Z (add): created
  provenance: {"harness_session":"claude-code:51fffea7-6ed5-4a54-b2d7-3a0f02c1306a","harness_session_source":"CLAUDE_CODE_SESSION_ID","origin":"agent"}
- 2026-11-10T02:18:15Z (main): started
  provenance: {"harness_session":"claude-code:ec2a27a0-32cf-4bec-9baf-700f147c7283","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-11-10T02:18:41Z (main): trial: flow-trial-1 — enrolled — flow on
- 2026-11-10T02:18:44Z (main): arm: flow-trial-1 — unit tack-fc34cb — flow on
- 2026-11-10T02:19:31Z (fix/hq-fc34cb-shut-rd-socket): resumed
  provenance: {"harness_session":"claude-code:ec2a27a0-32cf-4bec-9baf-700f147c7283","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
