# Plan revision 3 scoped self-review

Reviewer: codex/gpt-6.1-sol (self-review), freshly verified by relay model in this
turn. Frozen target: hq 0154323a7b076c62490b205a3b9c85df45a54bf7,
docs/plans/2026-09-30-session-archive.md. Compared the committed diff against
reviewed input 50282b9 and the current fixture/production callers.
Verdict: accept; findings: none. No independent re-review or human plan approval.

- I1: Task 18 now includes conftest.py and the probe tests. The fixture explicitly
  replaces all existing environment contents with named fake/temp values before
  in-process production calls, using monkeypatch operations on the real _Environ
  object. That covers explicit-env copies and native env=None inheritance, with
  regressions for run, Popen, direct version checks and stub control overrides.
  Fixture teardown and existing process cleanup remain required. An isolated
  diagnostic child confirmed the native-environment synchronization distinction;
  the actual proposed fixture and regression remain unimplemented.
- M2: Task 19 now gives the exact hq no-ff merge command, preservation of the
  tested reader commit, post-merge ancestry/consumer-tree checks, and a new paired
  probe verdict whenever the tested/landed reader changes. Review fixes must use
  a new committed strict revision rather than re-probing the old one.
- M3: Both sequence fields are tuples in the frozen record, parsed JSON remains
  lists at the boundary, empty conflicts become (), and expected reason values
  plus hashability are tested. No other retained field is mutable.

The approved design, task headings, dependency order, inline execution choice and
deferred obs-task filing are unchanged. All three findings are corrected in the
plan, none deferred. Full just test passed 1674 unchanged-runtime tests; tasks
check and git diff --check passed. This is plan consistency verification, not
evidence that strict-consumer runtime behavior is implemented or correct.
