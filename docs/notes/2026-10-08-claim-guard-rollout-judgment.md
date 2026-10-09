# Claim-guard rollout judgment

The judgment §6 of `docs/specs/2026-09-24-turn-boundary-gate-design.md` asks for: every
Stop block since the guard changed, sorted by what the blocked turn did, and a verdict
on the reason text and on ai-c62995's over-parking shape. Task `hq-a558e8`; counted
2026-10-08 on this host (titan). The second host was offline and is not counted.

## Verdict

- **Claude Code: the guard works, and the reason text needs no change.** Blocks fell
  from 34% of turn ends to 1.4%, and every block now produces the action the reason
  asks for. The replies without a tool call that made up 93% of blocks before are gone.
  No vacuous park came back.
- **Codex: nothing to judge.** No Codex turn end that finished normally held a claim,
  so the guard had nothing to block, and it blocked nothing. Before every turn end
  that finished normally, Codex agents had released their claims. Whether
  an interactive Codex session delivers a block remains unobserved, but nothing shows
  that it fails to.
- **ai-c62995's over-parking shape did not recur on Claude Code.** The 2026-09-25 haiku
  park ("ready for next steps") has no successor among 24 blocks. What remains is a cost,
  not a defect: an interactive walkthrough pays a block, a park and a resume on every
  turn (ops-b13db3).

## Window and method

- Claude Code: from 2026-09-29T13:00Z, after the guard began allowing a stop while the
  Stop input lists a running child (ops `2957369`, `bf22a93`, 12:56Z), through
  the count at 2026-10-09T02:15Z. Both Claude homes; main threads, deduplicated by record uuid,
  since `--resume` copies records into a new file.
- Codex: the same window, both Codex homes. The worker SubagentStop guard went live on
  2026-10-08 at 18:41Z (`116b0d7`). Worker rollouts were not counted.
- A block is a `stop_hook_summary` whose `hookErrors` carries a claim-guard reason
  (Claude Code), or a `<hook_prompt hook_run_id="stop:…">` user message (Codex). Codex
  writes nothing for a Stop hook that allows, so its denominator is `task_complete`.
- What the blocked turn did is read from the records between the block and the
  harness's allowed retry, and from what opened the next turn. The two scripts are
  attached to `hq-a558e8` (`judge.py`, `held.py`); they supersede `stops.py`,
  `after.py` and `share.py` there.

## Claude Code

| | Before (2026-09-25 to 09-29, ops-552425) | Since 2026-09-29T13:00Z |
|---|---|---|
| Stops that ran the guard (retries excluded) | 1,144 | 1,693 |
| Blocked | 388 (34%) | 24 (1.4%) |
| Reply with no tool call, then the allowed retry | 359 | 0 |
| Led to a park, done or drop | 11 | 24 |

Blocks by day: 2 on 09-29, 11 on 10-01, 3 on each of 10-02 to 10-04, 2 on 10-05, and
none from 10-06 to 10-09 across 540 guarded stops.

Reason variants: 23 "no child the harness tracks is running"; 1 "the guard cannot see
whether a child is running (the Stop input lists only work not known to wake a
controller)". No claims-read failure, facts-read failure or input defect occurred.

What each blocked turn did, in the classes of §6:

| Class | Blocks |
|---|---|
| Park with an action | 22 |
| Resumed work | 2 |
| Vacuous park | 0 |
| Bounded wait on a child | 0 |
| Report-and-end for a running child | 0 |
| Bare end on retry | 0 |

- **Park with an action (22).** Every one has the same shape: the turn ended with a
  question to the user (approve a merge, pick an edge treatment, judge a clip, accept a
  spec) while the session held the task, and the agent parked `--waiting-on user` with
  a next step naming the person and what follows. In 8 the agent had already parked
  one record earlier in the turn and missed another, a parent or a step still
  claimed. The one "children unseen" block is one of these.
- **Ten of the 22 come from one obs session** that walked the user through ten review
  items, one per turn. Each turn resumed the task, showed an item, asked for a verdict,
  was blocked and parked. The agent named the cost in its fifth reply. This is the rule
  working as written, at two lifecycle notes and one extra model round per item.
- **Resumed work (2).** One agent dropped a claim that a triage subagent had left
  behind from a scratch project. The other found its background research done, went
  on to write two plans, and then parked for their review. That agent also filed
  ops-3dbe63, saying the guard had missed a running child. The block was correct: the
  child's completion notice was already queued three seconds before the stop.

The 2026-10-06 to 10-09 gap is not explained by this count. The guard ran on every one
of those stops, and a replay of this session's own Stop input through the installed
guard blocks. Transcripts do not record the Stop input's `background_tasks`, so the
stops the running-child allow let through cannot be told apart from stops by sessions
that held no claim.

## Codex

- 1,487 turn ends in the window, 825 of them in root threads; 0 blocks.
- Root turn ends at which the session still held a claim it had started: one. `held.py`
  finds candidates from tool calls (a `tasks start` whose result names the id, not yet
  followed by a park, done, drop or shelve of it) and keeps a candidate only while the
  task record's last lifecycle marker before the turn end is `started` or `resumed`.
- That one turn (rollout `01a0f381…`, 2026-10-01, holding the task now `hq-7c8bdb`)
  ended on a `server_overloaded` error with no final answer. It is not a normal Stop.
- In root threads, 401 of 486 `tasks start` commands took a claim. 22 of those released
  it in the same command (start, note, park).
- An independent check from the records alone, in review round 2, agrees. It took every
  `started` or `resumed` marker in the window whose provenance names a Codex root
  session (488) and looked for a turn end before that task's next lifecycle marker. It
  found only the one turn above.
- Some releases never appear as a literal `tasks park <id>` in the tool calls. A Python
  helper calls `tasks(root, 'park', …)`, and a JS template carries the id
  (`tasks start ${task}`). Only the record shows these releases.
- The only Codex blocks ever observed ran under `codex exec`: the 2026-09-25 live check
  on 0.156.1 (`hq-2f1271`) and the 2026-10-08 pilot on 0.161.0 (tasks
  `docs/notes/2026-10-08-claim-guard-acceptance.md`). No rollout in either live Codex
  home holds a `<hook_prompt>` message, which is what a working guard produces when no
  turn ends holding a claim.

The Codex reason text has never been read by a live interactive model, and the count
gives no reason to probe for it. A held claim at a normal Codex turn end would be the
first case worth reading.

## Limits

- One host. The second host's stores were unreachable on 2026-10-08.
- `held.py` finds candidates through tool calls, so it misses a claim taken by another
  process, an id carried by a variable, or a start printed in pretty rather than JSON
  form. The task record confirms each candidate, and the record-only check in review
  round 2 covers what the tool calls miss. Review round 1 caught four defects in the
  first version:
  - it applied a release before the start in the same command;
  - it skipped tool outputs that did not mention `tasks`;
  - it missed a `tasks` command after an escaped newline;
  - it missed flags before the id.

  That version reported 69 held turn ends.
- Claude Code's held-claim rate is not reported. The running-child allow is invisible
  in transcripts, so a held stop it allowed cannot be told from a missed block. The
  tool-call detector also finds only 3 of the 24 known blocks as held.
