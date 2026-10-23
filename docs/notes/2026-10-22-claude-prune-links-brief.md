# Claude transcript links and archive pruning — brief

2026-10-22. Idea: hq-1639fd. Existing retention goal: hq-401088.
Updated after hq-cbcc14's completed investigation and follow-up scoping, and after
hq-d59a7b's live survey and hq-0b8f2c's resume probe.

## Problem

Pruning an old Claude session must account for younger sessions that link to its
subagent transcripts. Keeping the transcript bytes in the archive does not keep a
live successor's link usable. Establish the retention rule before scoping a fix.

## Current behaviour and evidence

Checked hq at `2c4ff59`. `tools/session_archive/capture.py:walk_files` skips
symlinks. `tools/session_archive/inputs.py:claude_units` builds each session from its
transcript and adjacent directory, listing regular files only.
`tools/session_archive/prune.py:evaluate` and `prune_run`
check and process units independently; they do not inventory incoming links.
`delete_claude_unit` renames the target unit into quarantine before final deletion,
so a reference can break at quarantine time, before the bytes are released.

hq-1639fd records Claude successor-to-predecessor transcript links observed on
2026-10-21 and 2026-09-06, and an earlier dangling link after Claude's own cleanup.
Those observations are source evidence, not a fresh live-store survey in this pass.
The code confirms the missing incoming-link check. hq-cbcc14 completed the
two-session reproduction in `4f40c52`, with reviewed findings revised through
`596b706`; the evidence table below records its synthetic-store results.

obs-396637 is now done: obs skips transcript symlinks and tolerates vanished paths.
That removes the reported indexer crash, but does not preserve a live link's target.
Existing `tools/test_session_archive_prune_claude.py` tests retain nonregular entries
inside quarantine. The new `tools/test_session_archive_prune_links.py` covers a
surviving session's link and the linking unit's own quarantine failure.

### Findings (hq-cbcc14, 2026-10-22)

Evidence: `tools/test_session_archive_prune_links.py`, synthetic stores only. Each
fixture is an older unit O holding `subagents/agent-1.jsonl`, and a younger unit N
whose `subagents/agent-1.jsonl` is a symlink to it, relative or absolute. Assertions
marked `current` pin today's behaviour, which a retention rule is meant to change.
Fixtures always visit O before N; no outcome below depends on the order. hq-1639fd's
report does not say whether Claude writes these links relative or absolute, so both
forms are covered.

| Case | Outcome | N's link | Notes |
|---|---|---|---|
| Dry run, O eligible, N active | O `eligible` | resolves | The report says nothing about the link |
| Apply, O eligible, N active | O `pruned` | breaks at quarantine (step 1), stays broken | The hooks read resolves / broken / broken; the archive keeps O's bytes. Relative and absolute links behave the same |
| O held open at settle | O `kept:open` | broken while quarantined, whole after restore | A restore repairs the link |
| O path recreated after quarantine | O `failed:recreated` | broken until a person merges | The leftover quarantine refuses the next run |
| N inactive (O retained, pruned in the same run, or already gone) | dry run: N `eligible`; apply: N `failed:release` | stranded in quarantine | Detail follows the table. With O retained, an absolute link still reaches O from quarantine; O is intact and never followed |
| Link into O created at `after_precheck` | O `pruned` | resolves at creation, then breaks | No current check sees it |
| Link into O created at `after_quarantine` or `before_delete` | O `pruned` | dangling from creation | The target is gone from its live path before the link exists |

The N-inactive row in detail:

- N's regular files are archived and released under rule (b), which is the intended
  prune.
- The link is never released, because `present` comes from `walk_files`
  (`prune.py`, `delete_claude_unit`), which skips links. The link stays under
  `run1/-p/N/N/`, the unit's directory cannot be emptied, and the unit ends
  `failed:release`.
- The current run goes on. Every later run refuses with `LeftoverQuarantine`.

What the current protocol does:

- **Pruning O breaks a live link.** The link breaks at quarantine, not at removal.
  Eligibility never considers incoming links.
- **N's link halts later runs.** Capture and unit discovery skip symlinks, so N's
  eligibility ignores the link. An apply ends in `failed:release` and leaves a
  quarantine that halts every later run, until a person clears it.
- **The dry run shows nothing.** It reports N `eligible`, so the rollout's dry-run
  review (spec §4) would not reveal the problem from this cause.
- **A second, run-wide halt sits in the obs reader.**
  - **Mechanism:** `inputs.py` `load_obs_state` keys rows by `os.path.realpath`. A row
    obs still holds for a link path folds onto its target's key whenever the link
    resolves. The two rows differ at least in `missing_since_ms`, which raises
    `ObsUnavailable`, and that stops dry runs and applies alike.
  - **Evidence:** reproduced by the reviewer with a stub runner, and confirmed against
    the live index by hq-d59a7b (below): it fires today.
  - **Scope:** rules 1–3 below do not fix this halt. It belongs to hq-3b9c4c's reader
    rewrite: key rows by exact path or by obs's device and inode, and ignore link-path
    rows.
- **Claude's own cleanup breaks the link too.** It removes files by mtime
  (`cleanupPeriodDays`, 90 here), and it left a successor's link dangling on
  2026-09-19. Retaining the target therefore defers the break to Claude's horizon; it
  does not prevent it.

Recommendation, the minimum change. It keeps no-follow traversal and the quarantine
rules:

1. **Keep a unit that holds a non-regular entry** (`kept:has-link`), decided at
   pre-check before anything moves. Discovery reads entries with `lstat`, so this
   follows nothing.
   - Pre-check sees only entries present at pre-check. An entry that appears later
     must be caught again, under rule 3.
2. **Keep a unit that another unit's link points into** (`kept:linked`).
   - **Inventory:** during phase one, list the links in both Claude sources (`claude`
     and `claude-work`) at every level, and match each against the units of both
     sources.
   - **Match:** a link targets a unit when its target is `<sid>.jsonl`, or is `<sid>/`
     or lies beneath it.
   - **Resolving links that work:** compare `os.stat(link)`'s device and inode with the
     no-follow inode set that `quarantine.inodes()` gathers for each unit. The stat
     reads metadata only, follows nothing that is deleted, and catches a link written
     through an aliased path (a symlinked prefix, a bind mount), which lexical
     matching misses.
   - **Dangling links:** match lexically with `normpath` (an absolute target as
     written, a relative one against the link's directory). Such a link protects
     nothing today, but matching it keeps the rule stable.
   - **Out of scope:** links from outside the Claude sources.
3. **Repeat the checks just before release.** After re-verify, and before the
   recreation check and release, scan the quarantined tree for non-regular entries
   (rule 1). Then rerun rule 2's inventory lexically against the unit's original live
   paths: the targets are now in quarantine, so device and inode matching cannot see
   them. On either hit, restore the unit (`kept:has-link`, `kept:linked`).
   - This closes the windows from pre-check to quarantine and from quarantine to
     release (the `after_precheck`, `after_quarantine` and `before_delete` rows).
   - It rescans whole sources for every unit deleted. The cost is unmeasured; limiting
     the scan to `subagents/` would cut it, but fails open, and needs a measurement
     first.
   - Section 3.4.1's "a quarantined file or link is removed only when…" should say
     that links are never released.

What no rule closes: a link created between the last scan and the removal, or after
the removal. It names a path that is already gone from the live store, so it is
dangling from creation, and no snapshot excludes such a writer. Claude creates these
links when it hands a *running* agent to a successor. A running agent writes its
transcript, so its target should not be 30 days inactive. This is an argument from the
observed mechanism. It does not exclude the race, and it has not been probed.

Rejected for the minimum change:

- **Pruning a pair together.** It would require archiving link targets so that rule (b)
  could hold for a link, plus a group rollback that does not exist.
- **Removing or rewriting a surviving unit's link.** It changes a live session.

Gates for hq-624351:

- **Rule 1 is a hard gate before any `--apply`.** Without it, the first inactive
  linking unit halts every later run, and the dry run does not show it coming. Pairs
  exist in the live store now: hq-d59a7b found two, and one of them is already past
  30 days on both sides.
- **The obs-reader halt is a hard gate**, owned by hq-3b9c4c.
- **Rule 2, with rule 3, was a policy gate.** It rested on not knowing whether a
  resumed successor reads the linked transcript. hq-0b8f2c found that it does not
  (below), which removes the case for keeping a target only because a link points
  into it.

All three need a reviewed revision of the archive spec, covering §3.3 (links are not
archived), §3.4's conditions, §3.4.1 and §3.4.2. They also need a revision of the plan.
That revision can share hq-3b9c4c's, which also amends §3.4.

Check: `just test` in the task worktree at 4f40c52 (all four segments): 228, 1002,
389 and 1 passed. After the review, the fixture file passes all 14 cases. The rerun of
`just test` before merging is recorded as a note on hq-cbcc14. Round 2's minors (a
non-regular `<sid>.jsonl` or `<sid>/` sibling, lexical-only matching in rule 3,
where rule 3 sits against `before_delete`, inventory error handling, and the obs
reader's wording and fix) are carried to hq-1639fd for the spec revision.

### Live survey (hq-d59a7b, 2026-10-22)

Read-only, on the primary host only. `find -type l` under `~/.claude/projects` and
`~/.claude-work/projects`, with `readlink` and `stat`; then one `obs --json
index-state` snapshot (contract 2, schema 15, 25,475 rows) passed to
`inputs.load_obs_state` through a stub runner. Nothing was pruned or written.

| Store | Links | N (linking unit) | O (target unit) | Form | Resolves | Unit ages |
|---|---|---|---|---|---|---|
| `claude` | 2 | `beliefs` `753f8b81` | `f9e4fdf9` | absolute | yes | both 46 days |
| | | `hq` `0835d699` | `393db06d` | absolute | yes | both under 1 day |
| `claude-work` | 0 | | | | | |

Both stores were readable; `claude-work` (24 projects, 915 transcripts) holds no
link, which is an observed zero. There are no dangling links in either store: the
2026-09-19 one is gone. Each link is a subagent transcript,
`<N>/subagents/agent-<id>.jsonl`, pointing to the same name under `<O>`. In both
pairs the target kept growing after the link was written (link 03:46, target 07:58
on 2026-10-21; 04:53 and 04:56 on 2026-09-06), which fits a running agent handed to
a successor.

Answers:

- **Form:** Claude writes absolute links, in the two observed. The relative fixtures
  remain useful but do not describe a form seen live.
- **Age:** the `beliefs` pair is already past the 30-day horizon on both sides. A
  first apply would prune O and break N's link, then strand N in quarantine
  (`failed:release`), halting every later run. Rule 1 is a gate on real data, not a
  hypothetical.
- **obs reader:** obs still holds a row for each link path, marked missing since
  2026-10-21 06:00, beside the target's row with `missing_since_ms` null. Today
  `load_obs_state` raises `ObsUnavailable` (`conflicting index-state rows` for the
  `beliefs` target), so every dry run and apply on this host halts before any unit
  is evaluated. This is hq-3b9c4c's hard gate, now observed live.

### Resume probe (hq-0b8f2c, 2026-10-22)

`claude/probes/successor-link-probe.py` records the result as the capability fact
`resume-reads-linked-subagent` (claude-code 2.1.304: `false`). It runs in a scratch
`CLAUDE_CONFIG_DIR`, with no live store involved.

How the live pairs arise. In both, N's rows carry `sessionKind: "bg"`: N is a
background session that took over O's running background agent. In the `hq` pair this
happened at a `session_cron_carry` attachment (2026-10-21 07:46Z). N's process then
finished the agent's transcript through the link, and wrote `finished: true` into its
own regular `.meta.json`. So Claude does write through the link, but only while the
agent runs, when the target cannot be 30 days inactive.

What was driven:

- **Harness-made pairs: not reproduced.** `claude --bg --resume O` while O was
  running started a copy that did not take the agent. `/background` offered to stop
  the agent ("1 local agent will be stopped") rather than hand it over.
- **The probe used a hand-made pair instead.** O ran one background agent to
  completion, and N was a `--fork-session` copy of O. N's `subagents/` got an absolute
  link to O's transcript, beside a regular copy of its `.meta.json`, which is the live
  shape.
- **Four resumes per run, under `strace -ff -y`.** N was resumed headless
  (`claude -p --resume`) and in the terminal interface (`claude --resume` in a private
  tmux server), each with the link resolving and with O's whole unit moved aside, as
  quarantine would. The trace covered file syscalls, reads and `getdents64`.

Result, the same in three runs:

- **No reads.** No call named anything under N's `subagents/`, and no io_uring ring was
  set up. The trace did see N's own transcript being read, which is the control.
- **A dangling link is harmless to resume.** Every resume exited 0 and replied, and
  the link was left as it was.
- **No other reader was found.** Claude's session listing (static read of 2.1.304)
  filters `subagents/` entries with `Dirent.isFile()`, which skips links. obs skips
  transcript links since obs-396637.

Limits:

- **Opening the agent's transcript from the agent view** was not driven.
- **Hard links may come later.** 2.1.304 already has a takeover path that hard-links
  the transcript (copying when it cannot), and a relink sweep. On resume, the sweep
  opens a linked target, checks it, and replaces the link with a hard link or copy.
  Both sit behind a storage-v5 gate that was off here, and the 2.1.304 pair on this
  host is a symbolic link. If the gate turns on, links become hard links, and two
  units share an inode: that changes what capture, quarantine and the open-file check
  see, and needs its own look before it lands.

Recommendation: drop rule 2 and rule 3's link inventory. Resume does not justify
keeping a target, and Claude's own cleanup already leaves such links dangling. Keep
rule 1 (`kept:has-link`, with its re-check before release): it prevents the
`failed:release` quarantine halt, which does not depend on whether anyone reads the
link.

## Constraints

The accepted archive design is `docs/specs/2026-09-30-session-archive-design.md`,
especially §§3.2–3.4; its plan is `docs/plans/2026-09-30-session-archive.md`.
Preserve no-follow traversal, exact archive verification, inactivity and open-file
checks, and quarantine recovery. Never follow an arbitrary link to delete its target.

hq-3b9c4c separately owns strict obs-readiness consumption; hq-624351 owns prune
rollout. Neither currently resolves incoming links. This brief authorizes no live
prune, timer change, or mutation of another session's links. The session-reader brief
`docs/notes/2026-10-20-session-store-reach-brief.md` treats this as retention work.

## Alternatives

- **Retain referenced targets.** Keep an older unit while a surviving unit links to
  it. Lean here: it preserves the existing live relationship without rewriting the
  surviving session. Settle the policy and remaining concurrency limits in the
  reviewed revision, using the completed fixture evidence and pending probe.
- **Prune linked units together, in a safe order.** Potentially reclaims more space,
  but requires every affected unit to qualify and complicates partial failure and
  quarantine rollback. No atomic group operation exists today.
- **Allow and report dangling links, or remove them.** Reporting may be acceptable
  if live readers no longer need them, but that has not been established. Removing
  links changes a surviving session; obs's fix alone does not justify it.

## Unanswered questions

- **hq-0b8f2c, isolated harness probe:** answered for 2.1.304 with a hand-made pair;
  see "Resume probe" above. A harness-made pair, the agent view, and storage-v5 hard
  links remain open.
- **hq-d59a7b, read-only survey:** answered; see "Live survey" above. The second
  host's stores were not surveyed.
- **Later reviewed design:** after those results, settle the retention policy and
  revise archive §§3.3–3.4.2 and the implementation plan. Coordinate with
  hq-3b9c4c's readiness revision. The last-scan race and the carried review minors
  in the findings remain explicit limits to resolve, not guarantees established by a fixture.

## Proposed decomposition

- Reuse hq-401088 as the retention goal. hq-1639fd stays an idea, briefed and waiting
  on existing hq-0b8f2c (P2 / small / mid complexity / direct) and hq-d59a7b
  (P2 / extra small / low complexity / direct). Each records its finding with
  `tasks note hq-1639fd --no-reviewed` before its result's branch merges. The
  completed hq-cbcc14 remains evidence, not an open wait. Reuse these records;
  do not duplicate their research or create an implementation task before re-scoping.
- Keep hq-3b9c4c's readiness work and hq-624351's rollout ownership. The investigation
  must identify whether the latter needs an additional gate; this pass does not
  incidentally rewrite either task or add a duplicate design task.
