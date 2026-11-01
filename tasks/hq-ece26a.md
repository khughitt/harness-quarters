---
id: hq-ece26a
title: "Harden detached agy settings adoption diagnostics, relink inode check, and anchor parity"
status: todo
priority: 3
size: s
complexity: low
process: direct
created: 2026-11-01T11:43:17Z
updated: 2026-11-01T11:43:18Z
depends: []
tags: [hooks]
source: hq-b24c39
agent: agy
origin: agent
---

Why: Round 1 code review of hq-b24c39 deferred three minor gaps in detached ~/.gemini/antigravity-cli/settings.json adoption: (1) parse and type refusals on a malformed detached ~/.gemini/antigravity-cli/settings.json blame tracked agy/settings.json in .githooks/live-picks, and tools/harness-links --apply omits `still <state> after live-picks sync` when `detail` is non-empty; (2) `relink_home` in .githooks/live-picks checks `S_ISREG` before `os.replace` rather than comparing `(st_dev, st_ino)` from the read-time file descriptor, leaving a narrow concurrent-save overwrite window; and (3) `HOME_LINKS` and `AGY_ANCHORS` in .githooks/live-picks have no automated parity check against `[harness.agy]` `adopt` and `anchors` in links.toml while hq-2eba07 is still open.

Done:
- Parse and type refusals on a detached home settings file in .githooks/live-picks name the detached home path rather than `agy/settings.json`, and tools/harness-links --apply includes `still <state> after live-picks sync` alongside non-empty `detail` when an `adopt` entry remains unconverged.
- `relink_home` verifies `(st_dev, st_ino)` matches the open file descriptor read during adoption before `os.replace`, refusing cleanly (`changed before relinking`) instead of overwriting a concurrent atomic save.
- Regression tests prove RED-to-GREEN for both fixes and assert parity between .githooks/live-picks (`HOME_LINKS` / `AGY_ANCHORS`) and links.toml (`[harness.agy]` `adopt` / `anchors`) unless already unified by hq-2eba07; `just test` passes.

Where: .githooks/live-picks, .githooks/test_live_picks.py, tools/harness-links, tools/test_harness_links.py, links.toml.

## Notes

- 2026-11-01T11:43:17Z (add): created
  provenance: {"origin":"agent"}
- 2026-11-01T11:43:18Z (main): concerns: hq-b24c39 defect — harden detached settings parse and post-sync diagnostics, relink inode race check, and links.toml anchor parity deferred from hq-b24c39 round 1 review
