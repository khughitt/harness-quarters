---
id: hq-e51fac
title: Make automatic compaction advisory in turn-pause hook and CLI
status: done
priority: 1
size: s
complexity: mid
process: direct
owner: main
created: 2026-11-05T00:36:12Z
updated: 2026-11-05T01:54:32Z
started: 2026-11-05T00:36:32Z
completed: 2026-11-05T01:54:32Z
closed: 2026-11-05T01:54:32Z
depends: []
parent: hq-2dd09b
tags: []
source: hq-1942a1
origin: user
---

The user accepted assessment hq-1942a1 (tasks/files/hq-1942a1/compaction-assessment-report.md) and requested: "file and prepare the advisory-compaction changes from compaction-assessment-report.md first, but make sure we don't let issue persist blocked for too long."

Done: compactions are no longer an independent hard pause/refusal trigger in tools/turn_pause, while active (16h), calls (500), and spawns (30) remain hard limits. Keep compactions in Limits and limits.toml (so limits_sha and stored RootState JSON remain compatible and live sessions do not trip limits-changed on activation) and keep TurnState.compactions and due_warnings for hooked advisory warnings. Update counters.crossed to check only ('active', 'calls', 'spawns'), and update tools/hq_cli/pause.py, tools/turn_pause/hook.py, README.md, and focused tests so human-readable status/limits/refusal text labels compactions as advisory (and unhooked rather than "count your own") while preserving JSON structure. Prepare in a dedicated worktree branched from main so this fix is not blocked behind .worktrees/hq-2dd09b (hq-e60ecb's 25-minute idle-host latency comparison). Coordinate with the paired lore guidance task. Live hook activation remains separately approved after preparation and review.

Where: tools/turn_pause/counters.py, tools/turn_pause/hook.py, tools/hq_cli/pause.py, README.md, and focused tests (tools/test_turn_pause_counters.py, tools/test_turn_pause_hook.py, tools/test_turn_pause_replay.py, tools/test_hq_pause.py). Run focused tests and mandatory just check-hygiene.

## References

- assessment (input, required, kind=report): tasks/files/hq-1942a1/compaction-assessment-report.md — accepted assessment recommending advisory-only compaction

## Notes

- 2026-11-05T00:36:12Z (add): created
  provenance: {"origin":"user"}
- 2026-11-05T00:36:32Z (main): started
- 2026-11-05T00:36:54Z (main): arm: flow-trial-1 — unit tack-2dd09b — flow off
- 2026-11-05T00:36:56Z (fix/hq-e51fac): resumed
- 2026-11-05T00:38:38Z (fix/hq-e51fac): arm: flow-trial-1 — unit tack-2dd09b — flow off
- 2026-11-05T00:38:40Z (fix/hq-e51fac): Hydrated .worktrees/hq-e51fac with just setup; focused baseline just test-one tools/test_turn_pause_counters.py tools/test_turn_pause_hook.py tools/test_turn_pause_limits.py tools/test_turn_pause_replay.py tools/test_hq_pause.py passed (161 passed in 15.61s); broad test suite deliberately omitted under validated .tt.toml policy. Paired lore guidance task filed as lore-d27b9c.
- 2026-11-05T00:53:27Z (fix/hq-e51fac): review: impl round 1 — verdict: revise; findings: 1 minor (label compactions as advisory in ROOT_TEXT, LIMITS_CHANGED_HEAD and _notice in tools/turn_pause/hook.py); reviewer: agy/gemini
- 2026-11-05T00:59:29Z (fix/hq-e51fac): attached: advisory-compaction-r2-report.md (3057 bytes): Accepted Round 2 code review report for hq-e51fac (af5c57ef) and lore-d27b9c (05be4622)
- 2026-11-05T00:59:31Z (fix/hq-e51fac): retained: {"version":1,"host":"titan","kind":"worktree","path":".worktrees/hq-e51fac","state":"kept","verification":"verified","purpose":"Preserve reviewed advisory-compaction hook and CLI changes across user live-activation approval","next_owner":"task:hq-e51fac","cleanup_trigger":"After user-approved live hook activation and integration into main, verify evidence and all worktree removal conditions"}
- 2026-11-05T00:59:33Z (fix/hq-e51fac): review: impl round 2 — verdict: accept; findings: none; reviewer: agy/gemini
- 2026-11-05T00:59:35Z (fix/hq-e51fac): Final preparation: advisory-compaction implementation af5c57ef28ba568bacc9032d0e885217c4c64128 accepted with no findings in Round 2 by agy/gemini; Round 1 report committed at docs/notes/2026-11-04-advisory-compaction-r1-report.md and Round 2 report attached at tasks/files/hq-e51fac/advisory-compaction-r2-report.md. Focused tests (just test-one tools/test_turn_pause_counters.py tools/test_turn_pause_hook.py tools/test_turn_pause_limits.py tools/test_turn_pause_replay.py tools/test_hq_pause.py: 162 passed in 13.87s) and mandatory just check-hygiene, git diff --check, and tasks check passed; broad suite deliberately omitted under validated .tt.toml policy; no remote evidence. Branch fix/hq-e51fac remains unmerged in .worktrees/hq-e51fac (independent of .worktrees/hq-2dd09b so it is not blocked by hq-e60ecb's 25-minute idle-host latency diagnostic); agent integrates with git merge fix/hq-e51fac in main only after explicit live activation approval. Paired lore guidance lore-d27b9c is independently accepted at 05be4622e7f20c2c8463f182b6455e460476154e in lore .worktrees/lore-d27b9c. Complete local retained set for hq-e51fac is this locked worktree (.worktrees/hq-e51fac, with setup-generated local/codex/rules); no scratch, off-tree evidence, host-pointer changes, or surviving processes.
- 2026-11-05T01:01:19Z (fix/hq-e51fac): Retention checkpoint at park: hq-e51fac record committed at 865104c63570501ed3c1e90d59f32170c4a8b4c8 on fix/hq-e51fac (reviewed code commit af5c57ef28ba568bacc9032d0e885217c4c64128); complete local retained set is locked worktree .worktrees/hq-e51fac (recorded above); ignored/untracked state is setup-generated .venv, local/codex/rules and caches; no scratch, off-tree evidence, host-pointer changes, or surviving processes.
- 2026-11-05T01:01:21Z (fix/hq-e51fac): parked (waiting on user, approval): User authorizes live activation of reviewed hq-e51fac (af5c57ef28ba568bacc9032d0e885217c4c64128); agent then refreshes main/checks and merges fix/hq-e51fac from .worktrees/hq-e51fac into main.
- 2026-11-05T01:54:28Z (main): resumed
- 2026-11-05T01:54:30Z (main): retained: {"version":1,"host":"titan","kind":"worktree","path":".worktrees/hq-e51fac","state":"released","verification":"verified","purpose":"Removed .worktrees/hq-e51fac and deleted merged branch fix/hq-e51fac (6e25be8afabf78032a0cb44937af542964e5faa1) after passing all worktree, ignored-file (caches/setup dirs regenerable), tt-report and host-pointer removal checks","next_owner":"none","cleanup_trigger":"none"}
- 2026-11-05T01:54:32Z (main): done
- 2026-11-05T01:54:32Z (main): Activated advisory-compaction turn-pause hook and CLI changes on hq main at 6e25be8afabf78032a0cb44937af542964e5faa1 (reviewed code af5c57ef28ba568bacc9032d0e885217c4c64128) after user approval. Verification: hq pause limits prints 'active 16h00m calls 500 spawns 30 compactions 2 (advisory)'; focused tests (just test-one tools/test_turn_pause_counters.py tools/test_turn_pause_hook.py tools/test_turn_pause_limits.py tools/test_turn_pause_replay.py tools/test_hq_pause.py: 162 passed in 13.38s) and mandatory just check-hygiene, git diff --check, and tasks check passed on main (broad suite deliberately omitted under validated .tt.toml policy; no remote evidence). Deviations: none. Disclosures: pushes=none; surviving_processes=none; others_work=untouched (.worktrees/hq-2dd09b on fix/hq-2dd09b untouched); branch fix/hq-e51fac merged to main and deleted; .worktrees/hq-e51fac removed after full disposal checks.
