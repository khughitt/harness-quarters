---
id: hq-a56adc
title: Codex work home hooks.json target; land inert prefix and prepare both hosts
status: doing
priority: 1
size: s
complexity: mid
process: direct
owner: feat/relay-cutover
created: 2026-10-19T21:21:24Z
updated: 2026-10-19T23:21:47Z
started: 2026-10-19T23:00:46Z
depends: [hq-1e9103]
parent: hq-539508
tags: []
agent: claude-code/claude-opus-5-5
plan: docs/plans/2026-10-19-relay-cutover.md
step: "Task 5: Give the Codex work home a target the installer accepts, and prepare both hosts"
---

## Notes

- 2026-10-19T23:00:46Z (feat/relay-cutover): started
  provenance: {"harness_session":"codex:01a15664-7cc0-70c0-9a01-d1cef0d8c24b","harness_session_source":"CODEX_THREAD_ID"}
- 2026-10-19T23:00:59Z (feat/relay-cutover): arm: flow-trial-1 — unit tack-539508 — flow off
- 2026-10-19T23:02:09Z (feat/relay-cutover): Steps 1–3: content-identical work hook rename, manifest and README references, plan status metadata. Extra scope: fresh-clone fixture copies codex/work and Codex setup case now includes .codex-work with a synthetic empty work config; observed missing renamed target before fixture fix. Focused RED to GREEN: 52 passed; no host changes.
- 2026-10-19T23:07:24Z (feat/relay-cutover): parked (waiting on agent): Controller: review Task 5 Steps 1–3 commit 8ca6531 in .worktrees/relay-cutover, then perform authorized inert main merge and both-host preparation (Steps 4–6); report .superpowers/sdd/2026-10-19-relay-cutover/task-5-report.md
  provenance: {"harness_session":"codex:01a15664-7cc0-70c0-9a01-d1cef0d8c24b","harness_session_source":"CODEX_THREAD_ID"}
- 2026-10-19T23:09:08Z (feat/relay-cutover): resumed
  provenance: {"harness_session":"codex:01a15627-8959-7223-98d3-1c5a0cf587a9","harness_session_source":"CODEX_THREAD_ID"}
- 2026-10-19T23:09:16Z (feat/relay-cutover): review: impl round 1 — verdict: accept; findings: none; reviewer: codex/gpt-6.1-sol
- 2026-10-19T23:12:08Z (feat/relay-cutover): Host prep: inert prefix merged on main; Titan ready and committed code matches tested branch, live settings/trust SHA unchanged. Europa source hashes match and expected two links converge, but npm 12.2.1 defaults allow-git=none and refused relay-install EALLOWGIT; npm 11.17.0 on Titan defaults all. Upstream checked official v12 install docs, npm/cli latest changelog, issues/9189 and PRs/9206, /9466, /8703: intentional npm12 default-deny; root option supported and HTTPS canonicalization fixed in npm12. Correct own recipe with per-command allow-git=root and regenerate HTTPS lock using installed npm12; no global npm configuration change.
- 2026-10-19T23:13:11Z (feat/relay-cutover): parked (waiting on agent): Task5 implementer: correct npm12 root-Git opt-in and HTTPS lock in .worktrees/relay-cutover, prove tests and return for scoped review before controller retries inert Europa install.
  provenance: {"harness_session":"codex:01a15627-8959-7223-98d3-1c5a0cf587a9","harness_session_source":"CODEX_THREAD_ID"}
- 2026-10-19T23:13:33Z (feat/relay-cutover): resumed
  provenance: {"harness_session":"codex:01a15664-7cc0-70c0-9a01-d1cef0d8c24b","harness_session_source":"CODEX_THREAD_ID"}
- 2026-10-19T23:15:17Z (feat/relay-cutover): Integration correction: upstream default-deny and HTTPS changes confirmed in npm12 docs and npm/cli PRs 9466, 8703, 9206 (controller search already recorded). Real recipe regression RED EALLOWGIT plus SSH URL mismatch; GREEN 8 focused tests. Disposable Europa npm12.2.1 generation and npm ci both succeeded with root-only opt-in; release banner relay 0.1.1; lock unchanged by ci and exact HTTPS release commit retained. No shared install retry or global config change.
- 2026-10-19T23:20:29Z (feat/relay-cutover): parked (waiting on agent): Controller: scoped-review npm12 correction in .worktrees/relay-cutover, then merge reviewed correction and retry inert Europa installation before completing host preparation; evidence in .superpowers/sdd/2026-10-19-relay-cutover/task-5-report.md
  provenance: {"harness_session":"codex:01a15664-7cc0-70c0-9a01-d1cef0d8c24b","harness_session_source":"CODEX_THREAD_ID"}
- 2026-10-19T23:21:47Z (feat/relay-cutover): resumed
  provenance: {"harness_session":"codex:01a15627-8959-7223-98d3-1c5a0cf587a9","harness_session_source":"CODEX_THREAD_ID"}
