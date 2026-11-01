---
id: hq-2eba07
title: Extract a declarative harness manifest so live-state hooks and capability facts read one source of truth
status: doing
priority: 2
size: m
complexity: mid
process: planned
owner: feat/hq-2eba07-harness-manifest
created: 2026-11-01T01:25:51Z
updated: 2026-11-01T11:42:04Z
started: 2026-11-01T09:55:45Z
depends: []
tags: [hooks]
source: hq-6c8a9f
agent: agy
origin: mixed
spec: docs/specs/2026-11-01-harness-manifest-design.md
---

Why: Onboarding agy in hq-6c8a9f required parallel edits across .githooks/harness-state-clean (JSON_FILES, *_JSON_KEYS), .githooks/harness-state-refresh (PATTERNS), .githooks/live-picks (OWNED, RECORDS, JSON_GROUPS, CLEAN, FIELD), and facts/capabilities.toml (harnesses). A declarative manifest eliminates per-harness constant duplication while keeping format/store adapters explicit.

Done:
- A declarative harness manifest in hq defines each harness's settings path, format, clean-filter keys, and live-picks units and record file.
- .githooks/harness-state-clean, .githooks/harness-state-refresh, and .githooks/live-picks load the manifest instead of maintaining parallel per-harness constant tables.
- Rollback and unit tests continue to pass via just test.

Where: .githooks/{harness-state-clean,harness-state-refresh,live-picks}, facts/capabilities.toml.

## Notes

- 2026-11-01T01:25:51Z (add): created
  provenance: {"origin":"mixed"}
- 2026-11-01T09:55:45Z (main): started
- 2026-11-01T09:56:11Z (feat/hq-2eba07-harness-manifest): resumed
- 2026-11-01T09:56:27Z (feat/hq-2eba07-harness-manifest): trial: flow-trial-1 — enrolled — flow off
- 2026-11-01T09:56:28Z (feat/hq-2eba07-harness-manifest): arm: flow-trial-1 — unit tack-2eba07 — flow off
- 2026-11-01T10:06:10Z (feat/hq-2eba07-harness-manifest): originating ask (agy session fdddf278, 2026-10-31/2026-11-01): user asked how to improve harness abstraction/compartmentalization/configuration so onboarding new harnesses minimizes ad-hoc/hardcoded logic, and asked at hq-6c8a9f closeout for follow-ups; filing agent scoped hq-2eba07 to a declarative manifest driving .githooks/{harness-state-clean,harness-state-refresh,live-picks} and facts/capabilities.toml. Selected Approach 1 (root harnesses.toml read by .githooks/harness_state.py and tools/harness-facts, removing duplicate harnesses list from facts/capabilities.toml); rejected Approach 2 (extending links.toml, which keys on home directories rather than capability slugs or tracked settings files) and Approach 3 (.githooks/harnesses.toml with duplicate harnesses kept in facts/capabilities.toml).
- 2026-11-01T10:14:49Z (feat/hq-2eba07-harness-manifest): frozen spec: hq in-tree . (.worktrees/hq-2eba07) commit 623f6f443a024f906f9d7372a9b19fb4261303aa:docs/specs/2026-11-01-harness-manifest-design.md (sha256 b276a5afa2623591acc950054a809bf6f75d7e9a45bc32f8d82df25e83004b1e); read-only builder-check subagent (agy:2ef562bf-6ac2-4e61-ac1e-632b92a2a20f) reported nothing important left; ops-check, ops-docs check, harness-facts check, and tasks check pass; host-load --section session reports session kitty-3817258-0.scope: nothing left running; nothing pushed; branch feat/hq-2eba07-harness-manifest remains unmerged in .worktrees/hq-2eba07 (do not amend or rebase while spec review is open; final merge to main requires explicit user approval because .githooks/ is a live global hook surface).
- 2026-11-01T10:14:53Z (feat/hq-2eba07-harness-manifest): retained: {"host":"titan","kind":"worktree","path":".worktrees/hq-2eba07","state":"kept","verification":"verified","purpose":"Await the user's review of frozen spec 623f6f443a024f906f9d7372a9b19fb4261303aa:docs/specs/2026-11-01-harness-manifest-design.md on branch feat/hq-2eba07-harness-manifest","next_owner":"task:hq-2eba07","cleanup_trigger":"After user approval and authorized integration of feat/hq-2eba07-harness-manifest into main, harvest test timings and run worktree removal checks"}
- 2026-11-01T10:15:38Z (feat/hq-2eba07-harness-manifest): retention checkpoint: observed 2026-11-01T10:15:17Z on titan; basis hq in-tree . 369f0dcdc86109d61cba0dc421e6a6336b5dab80:tasks/hq-2eba07.md; retained by refs/heads/feat/hq-2eba07-harness-manifest; this host: kept verified 1, kept unknown 0, released 0; changed 1; observer attribution unknown (no session stamp resolved by tasks --stamp under agy). Rechecked all kept/verified items on this host; unknown items remain unverified with actions in basis. Other hosts retain their own dated observations. Next: await user review of frozen spec 623f6f443a024f906f9d7372a9b19fb4261303aa:docs/specs/2026-11-01-harness-manifest-design.md.
- 2026-11-01T10:15:42Z (feat/hq-2eba07-harness-manifest): parked (waiting on user, review): User reviews frozen spec at hq (.worktrees/hq-2eba07) commit 623f6f443a024f906f9d7372a9b19fb4261303aa:docs/specs/2026-11-01-harness-manifest-design.md (sha256 b276a5afa2623591acc950054a809bf6f75d7e9a45bc32f8d82df25e83004b1e); on approval, resume hq-2eba07, write implementation plan docs/plans/2026-11-01-harness-manifest.md, file step children, and request plan review
- 2026-11-01T11:42:04Z (feat/hq-2eba07-harness-manifest): resumed
