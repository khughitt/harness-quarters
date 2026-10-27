---
id: hq-7e81ed
title: "Relay cutover tool and runbook: defects the live window exposed"
status: todo
priority: 3
size: s
complexity: low
process: direct
created: 2026-10-22T11:53:35Z
updated: 2026-10-27T14:17:15Z
depends: []
tags: []
agent: claude-code
origin: agent
---

Why: the relay cutover bootstrap (tools/relay-cutover-bootstrap, its rehearse and host entries, tools/relay-cutover, the tools/relay_cutover_bootstrap package and three test files, about 24.6k lines) was built for one window: replacing familiar's native hooks with relay v0.1.1 in four targets on titan and europa. That window (20261022T014303Z-a1e7bd47, hq-f27918) completed on 2026-10-22, and nothing is left for the tool to do. Decision (scope pass 2026-10-27): retire the tool rather than fix it. The live window exposed six defects; each was worked around live.

Established, so the next session need not re-derive it:
- No further run is planned. The tool hard-codes titan and europa, systemd timers and niri surfaces, and has no Darwin or launchd path. The Mac cutover (relay-848c0f, gating the Mac part of hq-539508) would need a different procedure whatever happens here.
- Relay upgrades no longer use the tool. docs/runbooks/relay-runtime.md upgrades through just relay-install (now at v0.2.1) and already calls the cutover runbook historical.
- Two of the defects' general lessons already have homes. Item 1's root cause is fixed in relay: resolveTerminalPid accepts a terminal-owning version-binary process (relay-cfd24b, done 2026-10-22). Item 6 is a global rule (lore-bb82ac, done). Item 3 was fixed in the window (9b5ae86).
- The tool's quiesce.py runs tools/quiesce-timers, so hq-ca01cf, which deletes quiesce-timers, cannot land before this deletion.

The defects, kept here as the record of what the window exposed:
1. Held Claude commands print the real binary path (…/claude/versions/<v>), so the process comm is the version and relay's terminal lookup (relay-cfd24b) fails: familiar never registers the session. Print the ~/.local/bin/claude link after checking it resolves to the prepared executable. The short Claude receipts' normal-exit intent checks passed vacuously because of this; normal-exit should require that the session was in intent earlier.
2. Claude 2.1.304 runs 'sleep 7' with no dialog in manual mode, so the runbook's Claude needs-approval prompt cannot produce one; the window used 'touch approval.marker && sleep 7'.
3. Codex 0.163 fires SessionStart only at the first model turn (fixed in-window: 9b5ae86); start-idle order is still unenforced (ledger minors).
4. niri accepts IPC spawn-sh while the session is locked and runs nothing; restart-surfaces failed on a locked europa. Detect a locked session before consent, and make the pilot's spawn probe prove the spawned command ran, not only niri's exit status.
5. The handoff's controller line resumes an old Codex session with no explanation; say what the controller is and that its role is the hook review plus one record-smoke --observe.
6. The operator found the per-home smoke matrix far too long; verify one host and profile deeply per harness and assume identically configured homes (lore-bb82ac).

Items 2 and 4 are facts any future live-desktop or approval-dialog tool should design around; a Mac cutover procedure should read them here.

Done: the two children close: the docs correction now, and the deletion after its flow-trial-1 gate. Then confirm that nothing in the tree references the tool and close this goal.

## Notes

- 2026-10-22T11:53:44Z (main): concerns: hq-c6c847 defect — the bootstrap tool's printed held Claude commands break familiar registration, its Claude needs-approval prompt cannot raise a dialog, and its surface restart cannot see a locked niri session
- 2026-10-24T22:15:25Z (main): curate-docs: hq-30fd95 at 8686be3 confirms: docs/runbooks/relay-cutover.md still reads as a procedure to run. Its Evidence section says the pilot is pending and nothing ran live, against its own 'Completed 2026-10-22' header, and README Layout describes it as the bootstrap the operator runs. Whichever way this task decides (fix the tool or retire it), restate or move the runbook to match, and update the README bullet and the relay-runtime link.
- 2026-10-25T10:35:56Z (feat/ops-check-hq-c6a149): hq .ops-check.toml allows the relay cutover tool, its tests, runbook and window plan by path (hq-c6a149); retiring the tool removes those entries in the same change
- 2026-10-25T15:19:31Z (fix/hq-d5ba0a-tilde-layout): hq-d5ba0a extends the fleet-layout policy to tools/relay-cutover (a prefix covering its sibling executables) and tools/test_relay_cutover.py because their fixed deployed guard and remote entry strings are fleet configuration. Remove these with the other cutover allowances if retiring the tool. The three wiring-test allowances protect the live hook strings and remain while those contracts remain.
- 2026-10-27T12:40:16Z (main): tool behaviour seen while fixing hq-f9c31a: familiar's own 'merge --no-ff' on the live checkout runs without -c maintenance.auto=false, so git (2.56) starts a detached 'git maintenance run --auto' inside the Dropbox-synced .git; the Dropbox hold check looks only at index.lock and MERGE_HEAD. If the tool is kept, pass -c maintenance.auto=false beside NO_HOOKS on its familiar write calls
