---
id: tack-90bf74
title: Replace khughitt/tack history with a squashed fresh root and archive the old history privately
status: doing
priority: 2
size: xs
complexity: low
process: direct
owner: main
created: 2026-09-28T09:27:27Z
updated: 2026-09-29T09:00:41Z
started: 2026-09-29T09:00:41Z
depends: [tack-4cd688, tack-b0197e]
parent: tack-5b608f
tags: []
agent: claude-code/claude-opus-5-5
---

From tack-8062ad: the root commit carries account and org ids in claude/claude.json and work names run through ~25 commits and subjects, so publish from fresh history. Steps: git bundle the full history (and/or push it to private khughitt/tack-history); orphan commit of the remediated tree; rerun gitleaks and the work-name grep over the new history; force-push main after the user confirms (destructive on the remote); every host's checkout resets to the new root. Check: git rev-list --count origin/main is 1; the grep and gitleaks are clean.

## Notes

- 2026-09-29T09:00:41Z (main): started
  provenance: {"harness_session":"claude-code:344dc247-3419-4443-85b2-8c2de56a3ee4","harness_session_source":"CLAUDE_CODE_SESSION_ID"}
