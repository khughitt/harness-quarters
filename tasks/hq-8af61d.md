---
id: hq-8af61d
title: Route agy/hooks.json through pinned relay v0.3.0 and slim agy/hook PreToolUse
status: doing
priority: 3
size: s
complexity: mid
process: direct
owner: feat/hq-8af61d-agy-relay
created: 2026-11-01T08:44:46Z
updated: 2026-11-01T18:56:48Z
started: 2026-11-01T16:09:11Z
depends: [tasks-ba29d3, fam-55f1af]
tags: [hooks, cross-project]
source: hq-e72097
agent: agy
origin: mixed
---

Why: hq-e72097 introduced agy/hook as a local adapter before relay v0.3.0 (relay-7b8340), tasks-ba29d3, and familiar's agy support (fam-d08564, fam-55f1af) shipped. With relay v0.3.0, tasks, and familiar ready while ops-33cef9 remains open, hq should pin relay v0.3.0, upgrade claude/codex/agy hook configs and relay/subscribers.template.json to v0.3.0 (restoring ops-guard and subscribing agy + familiar-agy), and slim agy/hook PreToolUse to hq-owned detached settings.json healing while keeping agy/hook SessionStart and Stop until ops-33cef9 lands (tracked in hq-c59809).

Done:
- relay/ pins relay v0.3.0 and relay/subscribers.template.json reconciles ops-guard (claude-code, codex, agy) with familiar's current entries plus familiar-agy.
- claude/settings.json, codex/hooks.json, codex/work/hooks.json, and agy/hooks.json route through relay v0.3.0 (with agy timeout 60 paired with --outer-ms 60000), and agy/hook PreToolUse retires relay-guard translation while keeping detached settings.json healing and SessionStart/Stop handling.
- Isolated live agy smoke checks (allow permission prompt, ops-guard denial, private registry agy row, familiar observe dispatch) and just test pass, with explicit rollout approval before merging live hook changes or updating ~/.local/share/relay and ~/.config/relay/subscribers.json.

Where: relay/, claude/settings.json, codex/hooks.json, codex/work/hooks.json, agy/hooks.json, agy/hook, tools/test_agy_hooks.py, tools/test_claim_guard_wiring.py, tools/test_relay_wiring.py, tools/test_relay_subscribers.py, README.md, docs/runbooks/.

## Notes

- 2026-11-01T08:44:46Z (add): created
  provenance: {"origin":"mixed"}
- 2026-11-01T08:44:47Z (main): concerns: hq-e72097 extension — migrate agy/hooks.json from the local agy/hook shim to pinned relay and native ops hooks after relay-7b8340 and ops-33cef9 land
- 2026-11-01T10:25:54Z (main): relay-7b8340's spec (records ea04df242:relay/docs/specs/2026-11-01-agy-hook-adapter.md, section 'Rollout prerequisites') lists four gates for routing agy through relay: tasks must accept agy rows in its relay snapshot reader on every relay-identity host first; every relay runtime before the subscriber file names agy; familiar before it subscribes to agy; and agy handler timeout 60 paired with --outer-ms 60000.
- 2026-11-01T11:43:21Z (main): hq-b24c39 added hq-owned detached ~/.gemini/antigravity-cli/settings.json healing (`refresh_detached_settings` running .githooks/harness-state-refresh when settings.json is a regular file) on SessionStart and PreToolUse in agy/hook; preserve that trigger (as a slimmed hq handler or relay subscriber) when routing agy/hooks.json through relay.
- 2026-11-01T12:00:26Z (main): Rollout prerequisite from relay-7b8340 final review: a malformed agy hook command (relay usage error, exit 2, e.g. relative --subscribers or a relay without agy) fails open on agy, which ignores exit 2; after wiring, verify one guard deny through each installed agy PreToolUse command on each host. Handler timeout and --outer-ms must be raised together (see relay spec Rollout prerequisites).
- 2026-11-01T12:36:09Z (main): fam-55f1af now depends on fam-d08564 (familiar's relay pin upgrade) and relay-9bb31c (a relay tag with the agy adapter): relay v0.1.1, familiar's pin, rejects any snapshot holding an agy row.
- 2026-11-01T15:18:05Z (main): familiar side landed (fam-55f1af, familiar main c037b11): familiar accepts agy rows. The entry hq's subscribers template needs is setupDocument('relay', bin, { agy: true })'s familiar-agy: role observer, harnesses [agy], kinds [session-start, before-tool, turn-end], argv [<familiar>/bin/familiar, observe], timeoutMs 2000. No reconcile kind (the familiar entry already receives reconcile). agy PreToolUse --outer-ms must stay at least 8000 with this entry, or relay's budget refuses every agy tool call. fam-8244b1 makes it familiar's default output.
- 2026-11-01T16:09:11Z (main): started
- 2026-11-01T16:09:27Z (main): trial: flow-trial-1 — enrolled — flow on
- 2026-11-01T16:09:28Z (main): arm: flow-trial-1 — unit tack-8af61d — flow on
- 2026-11-01T16:14:14Z (main): Scope assessment: hq-8af61d came from an agent-proposed follow-up in hq-e72097 (transcript 9fdda05b, user prompt 'Approved. Then, are there any follow-up tasks that we should create?') that bundled relay-7b8340 and ops-33cef9 while recording depends only on tasks-ba29d3 and fam-55f1af. Upstream today: relay v0.3.0 (ed0cb95, tag 271358b), tasks-ba29d3 (installed tasks 0.4.0 e9f0f7c..21db638), and fam-d08564 + fam-55f1af (familiar e4abd45) have all landed, and relay v0.3.0 translates run_command to Bash so ops/hooks/relay-guard works for agy with zero ops changes; however ops-33cef9 is still status idea in ops (claim-guard lacks --harness agy and claude-profile/capture-notice output plain text rather than injectSteps JSON, plus hq-b24c39 requires keeping detached settings.json healing on SessionStart and PreToolUse). Two host rollout findings also apply: (a) claude/settings.json (v0.1.1) and codex/{,work/}hooks.json (v0.2.1) reject any agents.json with agy rows and any subscribers.json naming agy, so they must move to v0.3.0 with or before live agy relay activation (requiring a zero-Codex-process window and /hooks re-trust); and (b) live ~/.config/relay/subscribers.json drifted at 2026-11-01 05:39 -0500 to standalone familiar setup output and currently lacks ops-guard. Options: (1, recommended) scope hq-8af61d to the relay v0.3.0 cutover now (pin relay v0.3.0, upgrade claude/codex/agy hook configs and subscribers.template.json restoring ops-guard + familiar-agy, slim agy/hook PreToolUse to detached-settings healing only while keeping SessionStart/Stop in agy/hook until ops-33cef9, file a narrow ops-33cef9 follow-up, and park before main merge/live install for rollout approval); (2) add depends on ops-33cef9 and park hq-8af61d (--reason dependency) until ops-33cef9 lands; (3) split the claude/codex v0.3.0 hook-image upgrade into a separate prerequisite hq task first.
- 2026-11-01T17:29:32Z (main): User scope decision: approved Option 1 — scope hq-8af61d to the relay v0.3.0 cutover now (upgrade relay pin to v0.3.0, upgrade claude/settings.json, codex/hooks.json, codex/work/hooks.json, and agy/hooks.json to relay v0.3.0, reconcile relay/subscribers.template.json to restore ops-guard + add agy and familiar-agy, slim agy/hook PreToolUse to detached settings.json healing while keeping agy/hook SessionStart and Stop until ops-33cef9 lands, split ops-33cef9 Stop/SessionStart migration to follow-up hq-c59809, and pause before main merge/live rollout for explicit approval).
- 2026-11-01T17:29:35Z (main): gate: scoped — adopted
- 2026-11-01T17:30:11Z (feat/hq-8af61d-agy-relay): resumed
- 2026-11-01T17:44:27Z (feat/hq-8af61d-agy-relay): gate: implementing .worktrees/hq-8af61d — baseline just test 1959 passed (agents/bin 268, .githooks+tools 1299, relay-cutover xdist 391, signal cancel 1; harness-facts check exit 0)
- 2026-11-01T18:20:04Z (feat/hq-8af61d-agy-relay): attached: agy-relay-smoke.json (17035 bytes): Portable isolated live agy 1.4.12 smoke summary (echo ok interactive prompt, ops-guard trailer denial, private agents.json working->done->dead row, familiar-agy session projection, and PreToolUse detached settings.json healing)
- 2026-11-01T18:35:48Z (feat/hq-8af61d-agy-relay): review: impl round 1 — verdict: revise; findings: Important 1, Minor 2; reviewer: agy
- 2026-11-01T18:56:48Z (feat/hq-8af61d-agy-relay): review: impl round 2 — verdict: accept; findings: Minor 1; reviewer: agy
