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
