---
id: hq-7e81ed
title: "Relay cutover tool and runbook: defects the live window exposed"
status: todo
priority: 3
created: 2026-10-22T11:53:35Z
updated: 2026-10-24T22:15:25Z
depends: []
tags: []
agent: claude-code
---

Found during window 20261022T014303Z-a1e7bd47 (hq-f27918); each was worked around live. Fix before the tool runs again (for example the Darwin cutover, relay-848c0f) or retire the tool.

1. Held Claude commands print the real binary path (…/claude/versions/<v>), so the process comm is the version and relay's terminal lookup (relay-cfd24b) fails: familiar never registers the session. Print the ~/.local/bin/claude link after checking it resolves to the prepared executable. The short Claude receipts' normal-exit intent checks passed vacuously because of this; normal-exit should require that the session was in intent earlier.
2. Claude 2.1.304 runs 'sleep 7' with no dialog in manual mode, so the runbook's Claude needs-approval prompt cannot produce one; the window used 'touch approval.marker && sleep 7'.
3. Codex 0.163 fires SessionStart only at the first model turn (fixed in-window: 9b5ae86); start-idle order is still unenforced (ledger minors).
4. niri accepts IPC spawn-sh while the session is locked and runs nothing; restart-surfaces failed on a locked europa. Detect a locked session before consent, and make the pilot's spawn probe prove the spawned command ran, not only niri's exit status.
5. The handoff's controller line resumes an old Codex session with no explanation; say what the controller is and that its role is the hook review plus one record-smoke --observe.
6. The operator found the per-home smoke matrix far too long; verify one host and profile deeply per harness and assume identically configured homes (lore-bb82ac).

## Notes

- 2026-10-22T11:53:44Z (main): concerns: hq-c6c847 defect — the bootstrap tool's printed held Claude commands break familiar registration, its Claude needs-approval prompt cannot raise a dialog, and its surface restart cannot see a locked niri session
- 2026-10-24T22:15:25Z (main): curate-docs: hq-30fd95 at 8686be3 confirms: docs/runbooks/relay-cutover.md still reads as a procedure to run. Its Evidence section says the pilot is pending and nothing ran live, against its own 'Completed 2026-10-22' header, and README Layout describes it as the bootstrap the operator runs. Whichever way this task decides (fix the tool or retire it), restate or move the runbook to match, and update the README bullet and the relay-runtime link.
