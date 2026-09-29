# Flow after the first pass: harness gates and retro curation

Scope pass 2026-09-21 over five ideas filed together on 2026-09-15 from
`mindful:thought:48e70c654fd84c6ab72d3f06b6261683`: ai-da52b7 (distilled
flow and blocks), ai-21ea5d (gates as hooks), ai-619958 (baselines),
ai-9dfba9 (the measure), ai-bdff6f (retro loop). Goal: ai-756baa.

## 1. Problem

The explicit task state machine and the `flow` skill landed on 2026-09-15
(ai-f5da3a) with four things deliberately left out (spec §5): hooks, blocks,
measurement, and where the retro goes. Six days of use have produced the data
those deferrals were waiting for. The shared outcome of the five ideas is a
flow that enforces its own gates where a harness can, learns from what its
retros say, and can be shown to work — without ceremony the record does not
justify.

## 2. Current behaviour and evidence

- 16 tasks have closed under the flow (ai 8, obs 8; ops, mindful and
  niri-material carry gate-like prose but no flow closure). Every one ends
  with `gate: verified tree:<f>` and a `retro:` note — zero state-gate
  violations on record. Checked by grep over each registered project's
  `tasks/` on 2026-09-21. The notes being present supports deferring more
  enforcement; it does not independently establish that every review
  occurred or covered the right tree.
- The recorded failure class is the turn boundary, not a state gate, and it
  has two shapes in ai-c62995: (a) an agent repeatedly **parking** a claimed,
  unblocked task between red-green increments because bookkeeping guidance
  read as "pause"; (b) a subagent with all work in hand ending its turn to
  wait on a background test monitor that expired — an **abandoned claim**.
  ai-6c8245 already put the rule in prose ("park or complete the gate before
  a turn ends"). A claim check catches (b) only: a park releases the claim.
- The measure exists in obs, not here. Charter §7
  (`obs/docs/specs/2026-09-17-obs-evals-charter-design.md`) names ai-9dfba9
  and sets the outcome measure — a verified gate before closure with an
  independent reviewer and matching covered tree; costs secondary. obs-e1dd2b
  (done 2026-09-21) reports the pre-flow stall proxy: 505 eligible episodes,
  7 incidents (1.4%; claude-code 0.7%, codex 2.3%),
  `obs/docs/reports/first-baseline.md`. That proxy counts a park as handled
  (117 parks among the non-incidents), so it sees shape (b) and not (a): a
  hook that induces parking could lower the rate while leaving unnecessary
  stops unchanged. obs-a6c7d4 (done) joins gate notes to per-stage turns,
  tokens and tool calls and flags stage revisits.
- No project has taken the per-project opt-in line (spec §4.3); the flow is
  invoked explicitly. obs's `AGENTS.md` says "reuse task gates and parks; do
  not create a second workflow authority".
- 17 `retro:` notes exist (obs-03e018 closed twice). Nothing reads them
  together.

## 3. Constraints

- Spec §5: hooks consume the same machine through `flow-state`; blocks are
  factored only after a second concrete flow exists; the `gate:` log is what
  measurement reads.
- Spec §7: the retro store beyond the note was left to ai-bdff6f. obs already
  joins on task notes, which argues against a second copy.
- Hook placement is in flux: ops owns `claude-pretooluse` and
  `claude-sessionstart` today; relay (ai-539508, P1, blocked on fam/ops/relay
  pieces) is the intended cross-harness dispatch. A gate hook built now must
  not become a third authority.
- A Stop hook that blocks must honour the harness's loop guard
  (`stop_hook_active` in Claude Code) and must not fire on a session that has
  parked (`tasks park` releases the claim: the tasks skill's rule 5 is exactly
  the behaviour the hook would enforce).
- obs: "indexing never runs from a harness hook"; a gate hook may read the
  claim store, never index.

## 4. Alternatives

For enforcing gates from the harness (ai-21ea5d):

1. **Stop hook on an abandoned claim** — refuse to end the turn while this
   session holds a live `tasks` claim that is neither parked nor done. Targets
   shape (b); obs's stall proxy measures that shape from day one, but judging
   the rollout means separating resumed progress, legitimate parks and
   unnecessary parks, which the proxy alone does not. Shape (a) stays a
   guidance problem on ai-c62995. Lean.
2. **Stop hook that runs `tasks check`** — cheap, harness-independent, but
   catches drift the pre-commit already catches at commit time, and the record
   shows no such drift reaching `done`.
3. **Pre-commit without a doing task / code change before a reviewed spec** —
   real gates, but zero recorded violations; defer until a violation appears
   or a project opts in and asks for them.

For the measure (ai-9dfba9): obs owns it; this repository contributes case
files and, later, a runner — only once there is a second flow to run.

For the retro loop (ai-bdff6f): the note stays the store; a listing plus a
recurring human-gated curation pass, no skill until two passes have run.

## 5. Unanswered questions

Answered by the ai-80b836 probe (2026-09-21, throwaway homes, stub hook; the
full log is on the task):

- **Can a Stop hook refuse the stop, and is the retry guarded?** Yes in both
  harnesses: `{"decision":"block","reason":…}` or exit 2 with stderr; the
  retry arrives with `stop_hook_active: true` and must be let through. One
  block, one retry, no loop, observed in Claude Code 2.1.278 and Codex.
- **What does the hook ask `tasks` for?** Nothing new:
  `tasks prime --all-projects` → `.doing[].claim.{session,live}` (0.5 s),
  filtered to `session == input.session_id && live`. Claude Code sets
  `CLAUDE_CODE_SESSION_ID` in the model's shell, `tasks` claims under it, and
  the hook input's `session_id` equals it.
- **Codex claim identity: resolved.** The probe found that `tasks` ignored
  `CODEX_SESSION_ID` (= the hook's `session_id`), recorded
  `sid:<command pid>`, and lost claim liveness when the command exited.
  tasks-3190fb landed on tasks main at `903f04a`; `tasks` was reinstalled.
  Claim identity now reads `CODEX_SESSION_ID` (or `CODEX_THREAD_ID` alone)
  after the explicit tasks and Claude Code identity levels: session is the
  thread id, tagged `codex:<id>`, with no pid, so liveness uses the TTL. A
  disagreeing Codex pair warns and skips that level. The landed regression
  test covers liveness from a later command, rival-thread exclusion, and
  park/provenance agreement. The original hook probe matched with
  `TASKS_SESSION=$CODEX_SESSION_ID`; a hook rerun using native claim identity
  remains unverified. The tasks-side identity blocker is removed.
- **Coverage:** another session's claim is listed and ignored; a `tasks park`
  before the turn end releases the claim and passes; a subagent's
  `tasks start` claims under the **controller's** session (its shell inherits
  the id), so the controller's Stop is refused and it reports the held claim
  — the owner's obligation is visible. Cost: a Stop also fires in the
  subagent context with the same `session_id` and `transcript_path` and no
  `agent_id` (only `SubagentStop` carries one, and it cannot block), so the
  subagent is blocked once too; the reason text should tell a subagent to
  report and stop.
- **Induced parking, observed:** blocked with nothing left to do, the model
  parked with next step "Waiting for next steps". The proxy counts that as
  handled. The design must say what a park's next step must contain (on
  ai-c62995) and the rollout judgment must separate resumed progress,
  legitimate parks and unnecessary parks.

Still open:

- Where the hook lives once relay dispatches hooks: ops for now, relay after
  the cutover — decided when ai-539508 closes.
- Rerun the Codex Stop-hook probe with the installed `tasks`, without a
  `TASKS_SESSION` override, to verify the native identity path end to end.
- Codex subagents were not probed (`SubagentStop` exists there too).
- Should retro curation cross-check self-reports against session logs? —
  obs, when it exposes a per-task view; not in the first passes.

## 6. Proposed decomposition

| Task | What | Waits on / wakes |
| --- | --- | --- |
| ai-756baa | goal holding the follow-ons | — |
| ai-80b836 | done: five-case Stop-hook probe in both harnesses (§5) | woke ai-21ea5d, ai-c62995, ai-21aaa3 |
| ai-21ea5d | briefed; design the hook from §5 | tasks-3190fb resolved at `903f04a`; remaining validation in §5 |
| ai-bdff6f | scoped: `retros` listing across projects, over `tasks show` notes as `flow-state` reads them | — |
| ai-c78706 | recurring (30d): curate the retros, human at promotion | ai-bdff6f |
| ai-9dfba9 | shelved: the measure is in obs; the runner needs a second flow | ai-619958 or ai-b9ab40 |
| ai-619958 | shelved: run the self-authored half when the skill is revised | flow skill revision |
| ai-da52b7 | shelved: blocks after a second flow | ai-619958 or ai-b9ab40 |

Related, not in this batch: ai-c62995 (the stall rule; shape (a) stays open
there), ai-21aaa3 (agent side
of the host broadcast — another turn-boundary hook), ai-b9ab40 (per-kind
lifecycles — the likeliest second flow), ai-fc26cf (cross-harness review at
the verified gate's reviewer seam).
