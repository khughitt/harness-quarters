---
id: hq-21aaa3
title: "Agent side of the host broadcast: check for signals between turns, pause at a good point, park the task"
status: shelved
priority: "2"
created: 2026-09-16T15:57:15Z
updated: 2026-09-29T21:08:58Z
depends: [ops-998bbb, hq-539508]
tags: [quick-add, hooks, flow]
source: "mindful:thought:34328bb6f74e4517bb0c5a2569ade36b"
agent: "claude-code/claude-opus-5[1m]"
---

A person (or agent) posts one signal to every active agent on the host — pause, a polite resource request — and agents check for it between turns via the hook bus, then respond: stop at the end of the turn or a good stopping point, tasks park the claimed task with the reason, release resources so a benchmark or a restart can proceed. This task is the agent-side protocol (hooks, skill text, park semantics); the transport is the signal bus ops-998bbb is splitting out of familiar, which this depends on. Related: fam-5b276b (session-end hook parks a claimed task), the tasks quiet queue (the resource-wait half from the task side).

Source: mindful:thought:34328bb6f74e4517bb0c5a2569ade36b

## Notes

- 2026-09-22T01:22:16Z (main): ai-80b836 finding 2026-09-21: a Stop hook can refuse the turn end in both harnesses (decision:block / exit 2; stop_hook_active guards the retry), matching claim.session from tasks prime --all-projects against the input session_id — no new tasks command. Claude Code: a subagent's tasks start claims under the controller's session, so the controller's Stop is refused (the owner's obligation is visible); a Stop also fires in the subagent context, indistinguishable by input, blocked once. Codex: blocked by the tasks gap tasks-3190fb — claims are sid:<command pid> and die with the command until identity reads CODEX_SESSION_ID. Observed cost: the blocked model parked with a vacuous next step ('Waiting for next steps'), the induced-park shape the proxy counts as handled. Relevant here: the Stop hook is a turn-boundary hook with the same shape this idea needs (check state between turns, tell the model, guarded retry); the session identity for matching is the hook input's session_id, equal to CLAUDE_CODE_SESSION_ID in the model's shell; under Codex CODEX_SESSION_ID is in the shell but tasks does not yet read it (tasks-3190fb).
- 2026-09-22T01:47:14Z (main): Follow-up to ai-80b836: tasks-3190fb is done at tasks main 903f04a; tasks was reinstalled. Codex claims now use the native thread id and TTL liveness, resolving the tasks-side identity blocker in the earlier finding. Brief §5 records the remaining native-identity Stop-hook rerun and unprobed Codex subagent coverage. Inappropriate parking and rollout judgment remain open.
- 2026-09-29T21:08:58Z (main): shelved: relay cutover tack-539508 lands and a project takes ownership of the host-request store (ops relay spec §6 assigns it to an unowned 'host broadcast feature'), or a benchmark or restart needs running agents paused and parking by hand falls short
- 2026-09-29T21:08:58Z (main): scope: shelved; evidence 2026-09-29: no broadcast transport exists or is owned — relay has no host-state/signal code, docs or task (HEAD bfed7d7), the ops relay design spec §6 defers host requests to a 'host broadcast feature' no project owns, tasks quiet/park --reason quiet is task-side only, host-load stores nothing; turn-boundary spec §8 already defers this to relay and implies a separate Stop hook beside ops hooks/claim-guard (live since ops e402b37); added depends on tack-539508 (relay cutover); related fam-5b276b (idea: session-end park backstop)
