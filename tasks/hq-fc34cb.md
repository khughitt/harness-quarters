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
updated: 2026-11-10T02:26:19Z
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
- 2026-11-10T02:19:33Z (fix/hq-fc34cb-shut-rd-socket): gate: scoped — adopted
  provenance: {"harness_session":"claude-code:ec2a27a0-32cf-4bec-9baf-700f147c7283","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-11-10T02:19:36Z (fix/hq-fc34cb-shut-rd-socket): gate: implementing .worktrees/hq-fc34cb
  provenance: {"harness_session":"claude-code:ec2a27a0-32cf-4bec-9baf-700f147c7283","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-11-10T02:19:38Z (fix/hq-fc34cb-shut-rd-socket): approach: instead of the suggested silence-stdout-on-undetected fallback, broken() detects the case exactly: a stream socket whose peer did SHUT_RD shows nothing to poll but a zero-length send fails with EPIPE (probed 2026-11-09 on Linux), so the re-raise for a genuinely undetected EPIPE stays (fail early)
- 2026-11-10T02:26:07Z (fix/hq-fc34cb-shut-rd-socket): review: impl round 1 — verdict: accept; findings: minor 3; reviewer: claude-code
- 2026-11-10T02:26:09Z (fix/hq-fc34cb-shut-rd-socket): gate: verified tree:1a8ae083f4c594e90ba4e1832c88f33df8b39c5d — checks: new listing and fzf-pick SHUT_RD socket tests failed before the fix (exit 120 and a launch) and pass after, live-socket probe test failed against a targeted break sending one byte, just test-one tools/test_hq_sessions.py 166 passed, just check-hygiene rc 0, worktree hq sessions over the real stores piped to head exit 0 with empty stderr, zero-length send EPIPE probed on both hosts; review: minor deferred hq-73665f ENOTCONN from a listening socket escapes broken, minor deferred hq-73665f setdefaulttimeout would set O_NONBLOCK on the shared description, minor addressed kernel dependence checked on europa 7.2.11; reviewer: claude-code
  provenance: {"harness_session":"claude-code:ec2a27a0-32cf-4bec-9baf-700f147c7283","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-11-10T02:26:19Z (fix/hq-fc34cb-shut-rd-socket): retro: probing the kernel behaviour first turned a suggested silent fallback into exact detection, keeping fail-early; the fresh reviewer's cross-host kernel doubt was cheap to settle by one ssh probe
