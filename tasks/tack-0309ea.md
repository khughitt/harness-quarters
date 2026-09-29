---
id: tack-0309ea
title: "session-episodes: tighten the status-question heuristic after the first labelled pass"
status: done
priority: 3
size: xs
complexity: low
process: direct
owner: main
created: 2026-09-19T16:15:45Z
updated: 2026-09-29T20:33:46Z
started: 2026-09-29T20:32:18Z
completed: 2026-09-29T20:33:46Z
depends: []
tags: [obs]
model: claude-sonnet-5-5
agent: claude-code/claude-opus-5
---

STATUS_PATTERNS includes bare \bstatus\b and \bprogress\b, which label 'run git status and commit' and 'the progress bar is broken' as status questions. The spec calls the list a starting point corrected by review. After the first pass of label yes|no on real episodes, use the labels file as the test set and anchor the two bare words (e.g. (what's the|any|task) (status|progress)); measure precision/recall against the reviewed labels before changing the list.

## Notes

- 2026-09-21T12:49:29Z (main): Baseline label review 2026-09-21 (obs docs/reports/first-baseline.md): of 51 heuristic trues 17 were status questions (34 false positives: review findings mentioning status/progress, pasted systemctl status, 'What's next?' after a completion report); 3 misses among 66 unhandled falses: 'Did it get stuck?', 'Is `mind6` currently executing?', 'How are things progressing?' — the patterns lack stuck, 'currently executing' with a backticked subject, and progressing.
- 2026-09-29T20:32:18Z (main): started
  provenance: {"harness_session":"claude-code:0db1579c-fd74-4ccd-9baa-5c0562180ad5","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-09-29T20:33:46Z (fix/status-patterns): measured on the 2026-09-21 labels (115 recovered of 117; 20 yes; 17 are 4 distinct messages, so recall is a small sample): old list tp17 fp32 fn3 (precision .35, recall .85); new list tp20 fp2 fn0 (precision .91, recall 1.00). The 2 remaining fps are statements matching 'still running'; left as is.
- 2026-09-29T20:33:46Z (fix/status-patterns): done
  provenance: {"harness_session":"claude-code:0db1579c-fd74-4ccd-9baa-5c0562180ad5","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
- 2026-09-29T20:33:46Z (fix/status-patterns): bare status/progress anchored, what's next dropped, stuck/progressing/currently executing added; measured against the reviewed labels: precision .35 to .91, recall .85 to 1.00; tests pin the baseline's misses and false positives
  provenance: {"harness_session":"claude-code:0db1579c-fd74-4ccd-9baa-5c0562180ad5","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
