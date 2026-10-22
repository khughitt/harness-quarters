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
marked `current` pin today's behaviour, which the retention rule is meant to change.

| Case | Outcome | N's link | Notes |
|---|---|---|---|
| Dry run, O eligible, N active | O `eligible` | resolves | The report says nothing about the link |
| Apply, O eligible, N active | O `pruned` | breaks at quarantine (step 1), stays broken | The hooks read resolves / broken / broken; the archive keeps O's bytes. Relative and absolute links behave the same |
| O held open at settle | O `kept:open` | broken while quarantined, whole after restore | A restore repairs the link |
| O path recreated after quarantine | O `failed:recreated` | broken until a person merges | The leftover quarantine refuses the next run |
| N inactive (O retained, pruned in the same run, or already gone) | dry run: N `eligible`; apply: N `failed:release` | stranded in quarantine | N's regular files are released first, so its live transcript is gone. The link stays under `run1/-p/N/N/`, and every later prune refuses with `LeftoverQuarantine`. A retained O is never followed |
| Link into O created at `after_precheck` | O `pruned` | resolves at creation, then breaks | A pre-check inventory misses it |
| Link into O created at `after_quarantine` or `before_delete` | O `pruned` | dangling from creation | The target is gone from its live path before the link exists |

What the current protocol does:

- **Pruning O breaks a live link.** The link breaks at quarantine, not at removal.
  Eligibility never considers incoming links.
- **N can never prune cleanly.** Capture and unit discovery skip symlinks, so N's
  eligibility ignores the link. Release rule (b) can never hold for a link: the archive
  does not record links.
- **One failed N stops every later prune.** The apply removes N's regular files, ends
  in `failed:release`, and leaves a quarantine that refuses every later run.
- **The dry run hides the problem.** It reports N `eligible`, so the rollout's dry-run
  review (spec §4) would not reveal it.

Recommendation, the minimum change. It keeps no-follow traversal and the quarantine
rules unchanged:

1. **Keep a unit that holds a link** (`kept:has-link`), decided at pre-check before
   anything moves. This removes the `failed:release` and leftover outcome. It needs only
   `lstat` and `readlink`, and follows nothing.
2. **Keep a unit that another unit's link points into** (`kept:linked`).
   - Build an inventory of links in every Claude source on the filesystem during phase
     one.
   - Resolve each link lexically: an absolute target as written, a relative target
     against the link's directory, both with `normpath` and never with `realpath`.
   - Match the result against each unit's live `<sid>.jsonl` and `<sid>/` paths. Match
     under both the configured root and the root's own resolved path, because a link may
     name either.
   - Together with rule 1, a linked pair is never pruned by hq. Claude's own cleanup
     (`cleanupPeriodDays`) eventually removes such a pair.
3. **Repeat the inventory after quarantine.** Run it again at settle, for links resolving
   into the quarantined unit's original paths, and restore the unit as `kept:linked` when
   one appears. This closes the pre-check-to-quarantine window (the `after_precheck`
   case). It can be limited to `subagents/` directories, which is the only place links
   have been observed, to bound its cost.

The race no rule closes: a link created after the last inventory, and before or after
removal, points at a path that is already gone from the live store. The link is dangling
from creation, and no snapshot excludes such a writer. Claude creates these links when it
hands a *running* agent to a successor. A running agent writes its transcript, so its
target should not be 30 days inactive. This is an argument from the observed mechanism.
It does not exclude the race, and it has not been probed.

Rejected for the minimum change:

- **Pruning a pair together.** It would require archiving link targets so that rule (b)
  can hold for a link, plus a group rollback that does not exist.
- **Removing or rewriting a surviving unit's link.** It changes a live session.

hq-624351 needs an additional gate. Rules 1 and 2 must be live before any `--apply`
prune, because the current code turns the first inactive linking unit into a run-wide
halt and the dry run does not show it. Pairs exist in the live store's history: two live
examples (2026-09-06 and 2026-10-21) and four pairs in obs's index. This pass did not
survey the live store. The change needs a reviewed revision of the archive spec (§3.4
conditions, §3.4.2 settle step, and a §3.3 note that links are not archived) and of its
plan. That revision can share hq-3b9c4c's revision, which also amends the §3.4
conditions.
