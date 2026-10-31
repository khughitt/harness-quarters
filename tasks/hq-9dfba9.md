---
id: hq-9dfba9
title: "Define the measure: what a flow working means, and an A/B harness over session logs"
status: shelved
priority: 2
defer: 2026-11-30
wake_on: [hq-619958, hq-b9ab40, flows-abf80d]
created: 2026-09-15T01:01:58Z
updated: 2026-10-31T10:48:07Z
depends: []
tags: [flow, obs]
source: "mindful:thought:48e70c654fd84c6ab72d3f06b6261683"
agent: claude-code/claude-opus-5
---

Decide the metrics before comparing flows: rework commits per task, park reasons hit, review findings per task, rounds to converge, time. Then run the same task under superpowers and under the distilled flow and compare from session logs. Without this the distilled flow cannot be shown better or worse.

## Notes

- 2026-09-22T00:31:01Z (main): shelved: A second flow exists to compare against the explicit machine (a self-authored baseline from ai-619958, or a per-kind lifecycle from ai-b9ab40), or obs asks for controlled repeated runs. The measure itself already lives in obs: charter §7 names this task and sets the outcome measure (a verified gate before closure with an independent reviewer and matching covered tree; costs secondary), obs-e1dd2b reports the pre-flow stall proxy (1.4%), obs-a6c7d4 gives cost per stage and stage revisits from the gate notes.
- 2026-09-22T00:31:01Z (main): scope: shelved; the measure is defined and running in obs (charter §7 cites this id, obs-e1dd2b, obs-a6c7d4), what remains is the A/B runner, which needs a second flow to compare; brief: docs/notes/2026-09-21-flow-gates-brief.md
- 2026-09-22T03:05:35Z (main): obs-abfcf9 (obs) defines the case and verdict records a runner would consume; the runner condition here is unchanged.
- 2026-10-31T10:48:05Z (main): shelved: Re-scope when a second concrete flow exists to compare against the explicit machine (a self-authored baseline from hq-619958, a per-kind lifecycle from hq-b9ab40, or the native dev flow under flows-abf80d), or obs records a need for controlled repeated runs with fixed tasks, prompts and starting conditions. The measure already belongs to obs; the open work is that controlled runner. flow-trial-1 compares on/off prospectively and does not itself supply a second flow or repeated runs of the same task.
- 2026-10-31T10:48:07Z (main): scope: shelved; current obs charter section 7 already defines the measure and requires fixed tasks/worktrees/prompts plus repeated executions to earn a runner. Checked flows main 080d86d: flow-trial-1 is a randomized on/off prospective trial, not the originally proposed same-task superpowers-versus-distilled runner; no result is claimed before its 2027-02-16 readout. hq-619958 and hq-b9ab40 remain shelved; flows-91a6b4/flows-abf80d now own another candidate flow, still awaiting design/implementation. Preserved body/source and renewed the full second-flow-or-obs-request condition with checkpoint 2026-11-30 and ANY-of wake targets hq-619958, hq-b9ab40, flows-abf80d; none is currently closed. Reused existing work and historical handoff lore:docs/notes/2026-09-21-flow-gates-brief.md; no duplicate runner or measure task. origin: filing event unavailable (no creation occurrence/stamp in show); older request not applicable (no origin_session). Source resolves but does not establish this metrics/runner proposal as the user's ask; field remains unknown.
  provenance: {"harness_session":"codex:01a1918d-e320-7110-90dd-2422cb01520e","harness_session_source":"CODEX_THREAD_ID"}
