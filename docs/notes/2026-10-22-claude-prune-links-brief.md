# Claude transcript links and archive pruning — brief

2026-10-22. Idea: hq-1639fd. Existing retention goal: hq-401088.

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
The code confirms the missing incoming-link check; a two-session reproduction of
hq's prune remains to be run.

obs-396637 is now done: obs skips transcript symlinks and tolerates vanished paths.
That removes the reported indexer crash, but does not preserve a live link's target.
Existing `tools/test_session_archive_prune_claude.py` tests retain nonregular entries
inside quarantine; they do not cover a link from a surviving session into a pruned
unit. The linking unit's own quarantine behaviour also needs checking.

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
  surviving session. Establish how discovery and quarantine handle concurrent links.
- **Prune linked units together, in a safe order.** Potentially reclaims more space,
  but requires every affected unit to qualify and complicates partial failure and
  quarantine rollback. No atomic group operation exists today.
- **Allow and report dangling links, or remove them.** Reporting may be acceptable
  if live readers no longer need them, but that has not been established. Removing
  links changes a surviving session; obs's fix alone does not justify it.

## Unanswered questions

- **Bounded investigation:** reproduce an eligible older target and an ineligible
  younger linking unit; locate the first break and the younger unit's later outcome.
- **Bounded investigation:** can retaining referenced targets fit the existing
  no-follow and quarantine protocols? Check link creation/change around the existing
  test hooks, target resolution, already dangling links and partial failure. Record
  any remaining race explicitly rather than claiming a snapshot prevents it.
- **Later design, if needed:** what contract change and rollout gate does the
  evidence require? Return to hq-1639fd with the recommendation before implementation.

## Proposed decomposition

- Reuse hq-401088 as the retention goal. hq-1639fd stays an idea, briefed and waiting
  on hq-cbcc14, **Establish safe retention for Claude units referenced by successor
  links** (P2 / small / high complexity / direct). Both belong under the existing goal.
  The investigation records its finding with tasks note --no-reviewed on hq-1639fd
  before merging, so scoping can resume with evidence rather than a guessed policy.
- Keep hq-3b9c4c's readiness work and hq-624351's rollout ownership. The investigation
  must identify whether the latter needs an additional gate; this pass does not
  incidentally rewrite either task or add a duplicate design task.

## Findings (hq-cbcc14, 2026-10-22)

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
  - **Evidence:** reproduced by the reviewer with a stub runner. That obs keeps such
    rows is taken from obs-396637's record; the live index was not checked.
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
  exist in the live store's history: two live examples (2026-09-06 and 2026-10-21) and
  four pairs in obs's index. This pass did not survey the live store.
- **The obs-reader halt is a hard gate**, owned by hq-3b9c4c.
- **Rule 2, with rule 3, is a policy gate.** Whether a resumed successor reads the
  linked transcript is unknown, so hq should not break the link sooner (about 30 days)
  than Claude's cleanup would (about 90).

All three need a reviewed revision of the archive spec, covering §3.3 (links are not
archived), §3.4's conditions, §3.4.1 and §3.4.2. They also need a revision of the plan.
That revision can share hq-3b9c4c's, which also amends §3.4.

Check: `just test` in the task worktree at 4f40c52 (all four segments): 228, 1002,
389 and 1 passed. After the review, the fixture file passes all 14 cases, and
`just test` was rerun before merging (see the task notes).
