---
id: hq-e4e58a
title: Check the flow trial's census/report join live after the rename to hq
status: todo
priority: "2"
size: xs
complexity: low
process: direct
defer: 2026-11-04
created: 2026-10-07T19:31:44Z
updated: 2026-10-07T19:31:44Z
depends: []
tags: []
agent: claude-code/claude-opus-5-5
---

Why: the rename's rehearsal could not exercise the census/report join before obs exports complete-window rows for trial units (enrollment opened 2026-10-05, 30-day windows; obs docs/specs/2026-10-07-follow-renamed-projects-design.md §4). The user chose on 2026-10-07 to cut over with proxies (flows bin/test_trial_rename.py, obs tests/test_rename_follow.py) and check the live join once rows exist (tack-8b7a28, docs/plans/2026-10-06-rename-to-hq-cutover.md Task 8). Done: flows bin/trial-arm census flow-trial-1 and obs outcomes report --json --since 2026-10-05 --until 2027-01-10 --cohort --units, run the same day, share at least one member/row under the exact same task string, including an hq- task; trial-verdict exits 0 on them with --validate; the result is noted here.
