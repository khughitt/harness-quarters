# Turn pause: activation notes

Task: hq-9aa713. Branch `feat/hq-9aa713-pause-past-range`. Spec:
`docs/specs/2026-11-01-turn-pause-design.md`. Plan: `docs/plans/2026-11-01-turn-pause.md`.

## What merging does

The Claude Code and Codex homes link to main's `claude/settings.json`,
`codex/hooks.json` and `codex/work/hooks.json`. The branch adds turn-pause entries to
all three, and `tools/turn-pause` itself, so merging the branch into main activates
the hook in every live session of those homes at their next hook event. No
`just link --apply` is needed for these files; the links already exist.

Not covered by the merge: the Claude Code work home's untracked
`local/claude/settings.work.json` (hq-8a11d6), agy (hq-be1fd6), opencode and pi.

## Steps around the merge

1. Codex hook trust. The Codex homes record a trusted hash per hook group in live
   state (`codex/config.toml`, `[hooks.state."<path>:<event>:<group>:<handler>"]`).
   The new groups have none. After the merge, open one Codex session in each Codex
   home (personal and work), review the new turn-pause hooks and trust them;
   otherwise Codex may skip them and the pause does not run there. Trust every
   turn-pause hook group together in each Codex home: UserPromptSubmit, PreToolUse,
   PostToolUse, Stop, SubagentStop, SubagentStart and SessionEnd. If PreToolUse is
   trusted but UserPromptSubmit or SessionEnd is not, a crossed limit can never be
   lifted by the user's reply. A later edit to one group's definition untrusts that
   group alone, so recheck after any edit to the wiring. The branch does not edit
   `codex/config.toml`, which is live state.
2. lore-911121's rule (what a paused agent reports, and the count it keeps where
   the hook keeps none) activates after this lands; its notes carry the two text
   inputs from this branch (the goal clause and the scheduled-wake line).
3. Check each home after activation. In a fresh session of each home (personal and
   work Claude Code, each Codex home) run `hq pause status` and confirm it shows a
   turn. A hook that is silently skipped is the failure the feature exists to
   prevent. Sessions started before the merge may stay uncovered until restarted:
   Claude Code may snapshot hooks at session start (not probed). Hosts that share
   the Dropbox checkout activate at the same moment.
4. Rollback: revert the wiring commit (`feat(turn-pause): wire the hook into Claude
   Code and Codex homes`) on main. Existing state files under
   `~/.local/state/hq/pause/` can then be removed.

## Recovery

When the hook blocks everything (the package fails to load, a state file is
unreadable, a pause cannot be lifted), an agent cannot fix it: the state path is
protected and git needs a tool call. Run these in a terminal.

- An unreadable state file: the refusal names it. Remove it, and the next prompt
  starts a fresh turn: `rm ~/.local/state/hq/pause/<the named file>`. To clear all
  turn state: `rm -r ~/.local/state/hq/pause/`.
- A pause that cannot be lifted (the user's reply does not reach the hook, for
  example an untrusted Codex group): remove the root's state file the same way,
  then trust the missing groups.
- The package fails to load, or anything else: full rollback: in the hq main
  checkout, `git revert <wiring commit>`, where the wiring commit is
  `feat(turn-pause): wire the hook into Claude Code and Codex homes`. Find it with
  `git log --oneline --grep 'wire the hook'`.

## What changes for live sessions

- Every tool call runs the hook. Measured on this host (500-run sets): p50 31 to
  33 ms, p99 47 to 48 ms in four of five sets and 65 ms in one under host load,
  against the spec's 50 ms p99 target; the floor is about 31 ms (interpreter start
  and the json import). A resident process would clear the target with margin; it
  is a host service and needs your approval (hq-33ad66).
- Limits per turn: 4 h active, 500 root calls, 30 tree spawns, 2 compactions (the
  third pauses). The replay over 2026-10-02 to 2026-11-01, counting the hook's way,
  pauses 45 of 5,639 turns, 1.50 a day (approved: 1.67; band 0.84 to 2.51); per
  limit active 34, calls 3, spawns 8; Claude Code 15, Codex 30.
- Calls are refused at all times, not only while paused, when their input names
  the pause state directory, the limits file, `tools/turn_pause/facts.json` or the
  wiring files, including the home links (`~/.claude/settings.json` and the Codex
  hooks files). The list holds the resolved checkout paths, not a symlinked home
  spelling of the checkout, so a call that names a file by that spelling is not caught;
  a limits edit made that way is still caught by the hash-change pause. That covers
  a plain `Read` of those files by the listed paths and edits through the
  update-config skill, and edits to documents that contain the state path.
- Waits for the user count as idle time for `AskUserQuestion`, `ExitPlanMode` and
  Codex `request_user_input`. Permission prompts and Codex escalation approvals still
  count as active while they wait, unless sessions run in bypass mode; a follow-up
  covers it.
- A PreToolUse payload over 32 MiB or with more than about 2 million JSON nodes is
  refused.
- `hq pause status` and `hq pause limits` show counts and defaults; Codex
  compactions show as not counted (count your own).

## Known limits

- Codex: the outer code-mode `exec`, nested `write_stdin` and top-level `wait`
  fire no hook, and the `exec_command` payload carries only `command`; a paused
  Codex agent can still drive a session it opened before the pause (spec,
  Limitation: unhooked Codex controls; hq-e8a7d5).
- Codex `kill` cannot be checked under the workspace sandbox (each `exec_command`
  runs in its own PID namespace), so the hook refuses it; a yielded process is
  stopped with `write_stdin` and an interrupt.
- Codex has no compaction counter until a compaction hook is shown to fire
  (hq-ba40e9).
- A session an agent launches from the shell is a new root with its own counters
  (hq-f247c3).
- The hook reads its state fail-closed: a later change to the state's fields
  would refuse every call of a live session until SessionEnd; such a change needs a
  migration or reset path first (hq-14bab1).
