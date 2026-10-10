# Preserve live model choices across Git updates

Scoped 2026-10-10. Report: hq-a77096. Goal: hq-cc17de.

## Problem

A merge that changes tracked harness settings can silently replace the user's
live model choice with the harness default. Preserve the choice while allowing an
intentional reset and subsequent model changes. Recovery must not stage live
values or alter unrelated settings.

## Current behaviour and evidence

- `.githooks/harness-state-clean` removes Claude's `model` and `modelSettings`,
  and Codex's top-level `model` and `model_reasoning_effort`, from Git's index.
  There is no smudge restore; README.md Setup documents losing the pick when
  Git checks out a new settings blob.
- `harness-state-refresh` calls `codex-trust sync` and clears size-only modified
  marks. The post-checkout, post-merge, and post-rewrite hooks restore only
  Codex project trust. Trust persistence landed in 982283a, 7c80ea6, and c4ca64c;
  its append-only union of trusted projects is unsuitable for replaceable picks.
- Temporary-repository reproduction on 2026-10-10 copied the real filter,
  refresh, and restore hooks. A saved settings commit changed a harmless
  `theme` value. Main then received synthetic `model` and `modelSettings`
  values and ran the Stop refresh: both remained live and the filtered diff was
  empty. A fast-forward merge of the settings commit removed both fields.
  Neither post-merge nor another Stop restored them. The temporary directory
  was removed by its context manager; no live home was read or written.
- `links.toml` routes personal settings to the tracked files; work settings
  already live under untracked `local/`. The current Codex trust store is also
  under `local/` and shared with the checkout's synchronization.

## Constraints

Preserve the clean-filter contract, Codex trust recovery, unrelated staged and
unstaged edits, and newer live choices. Worktree copies are not live homes.
Saved state remains untracked. A missing model key can mean either Git replacement
or an intentional return to the default; absence alone cannot decide which.
Tests and design probes use synthetic repositories, not live model changes.
Related hq-e18255 reports version drift; it does not solve or gate this work.

## Alternatives

1. **Capture and restore through the existing lifecycle — current lean.** Save
   only the owned live fields and restore after known Git replacement events.
   Requires explicit reset and precedence rules; adding post-merge alone cannot
   recover values already lost before capture.
2. **Separate live settings from tracked settings.** Avoid Git replacement by
   using a supported harness overlay. Feasibility and precedence must be checked;
   do not assume Claude and Codex support the same mechanism or change routing
   merely to make the design simpler.
3. **Keep manual re-selection.** Matches today's documented behavior but leaves
   the reported disruption. Retain as the baseline when assessing complexity.

## Unanswered questions

- When can every choice, including effort and reset-to-default, be captured
  reliably? hq-14d183 traces the actual hook and write lifecycle.
- How does recovery distinguish deliberate deletion from Git replacement and
  avoid restoring an older value over a later choice? Settle in the design.
- Should the first change cover Claude only or both filtered harnesses? Design
  compares the same acceptance cases before proposing the smallest complete scope.
- What happens across synchronized hosts, concurrent writes, missing or malformed
  snapshots, and Git operations with no restore hook? Design names the ownership
  and recovery limits. The user reviews those proposed semantics in the spec.

## Proposed decomposition

| Task | Disposition or next result |
| --- | --- |
| hq-a77096 | Briefed; remains an idea under hq-cc17de |
| hq-14d183 | P2, medium size, high complexity, planned: reviewed persistence/reset design, then implementation plan |

No extra research task: the loss is reproduced, and the remaining questions are
one interacting persistence contract. Design completion records its finding on
hq-a77096 in the same commit. Implementation and live-hook activation are later
steps, each subject to the normal gates.
