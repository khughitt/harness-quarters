---
name: flow
description: Use when a project's agent instructions name the flow skill for task work, or when asked to run a task under flow — walks one task through explicit states and gates recorded as notes on the task.
---

# flow

One task, a few states, a gate on every transition. Inside a state you choose
the method; at a gate you produce the artifact, run the check, get the judge's
verdict, and write the record. The record is a note on the task:

    tasks note <id> "gate: <state> — <evidence>"

`~/.agents/bin/flow-state <id>` tells you where a task is;
`~/.agents/bin/flow-state fingerprint` names the content you verified.
`~/.agents` links to the `tack` checkout's `agents/`; nothing puts the script on
PATH, so always call it by that path (or `agents/bin/flow-state` when standing
in `tack`).

## Rules

1. **Find the state.** `~/.agents/bin/flow-state <id>`. `outside` means
   the record predates the flow. An open one is adopted: confirm it is scoped
   (process set, a body that says outcome, approach, verification — scope it
   if not), then `tasks note <id> "gate: scoped — adopted"`. A `done` or
   `dropped` record is never adopted; nothing is backfilled onto closed work.
2. **Work freely inside a state.** The state names the artifact you are
   producing; how you produce it is yours.
3. **Advance only through the gate.** Artifact, check, judge, record, in that
   order. Never write the record without the gate; never move on without the
   record.
4. **Take back edges out loud.** When work in a state shows an earlier gate no
   longer holds, write `gate: scoped — invalidated: <why>` and say so. Every
   later approval is gone; on the direct path also `tasks edit --process planned`.
5. **Park before you stop.** A turn never ends with the task open and work
   still owed unless `tasks park <id> "<next step>"` names who acts next; only
   `closed` needs no park, and a gate record is not one (`gate: implementing`
   is written on entry, with everything still ahead). A step you own — the
   fresh-context review at `implementing → verified`, a check you have not
   rerun, a child not yet dispatched — is parked as *your* next step, never
   reported as pending for the human; `--waiting-on user` is only for a human
   gate or an explicit handoff (`--reason review`). The next step is an action
   and who takes it, never a state ("waiting for next steps"); an unblocked task
   is not parked between increments. Background work follows AGENTS.md
   "Processes": nothing the harness does not track is waited on across a turn. The closing message reports
   what you observed, not what the turn ending implies: which work has stopped,
   what is still running (a background check, a dispatched child) and how its
   result is picked up, and who acts next — "Task 7 is committed; its review
   has not run; nothing is running" — never "review is underway". A host
   pointer a live test repointed into the worktree (a launcher symlink, a
   service unit, a config include) is restored before the park, or the park
   note names it; the next session must not inherit it unknowingly.
6. **Retro before done.** Two or three lines, `tasks note <id> "retro: …"`, on
   which pattern helped or hurt on this task. `~/.agents/bin/retros` lists the
   retros of every registered project, newest first (`--since <date|Nd|Nw>`,
   `--project <prefix>`, `--json`); it is what the curation pass reads. A lesson
   about the tooling rather than the task is also feedback (the Feedback section
   of the global instructions): file it and put the returned id in the retro.

## States

| State | Meaning | Status allowed |
| --- | --- | --- |
| `captured` | unscoped idea | `idea` |
| `scoped` | p/size/complexity/process chosen, work understood | `todo`, `doing` |
| `designed` | spec exists and the human reviewed it | `todo`, `doing` |
| `planned` | plan reviewed, steps filed as children, none started | `todo`, `doing` |
| `implementing` | code changing in a task worktree | leaf `doing`; parent `todo`/`doing` |
| `verified` | checks ran against a named covered tree, fresh-context review done | leaf `doing`; parent `todo`/`doing` |
| `closed` | retro written, `tasks done` in the landing commit | `done` |

`doing` before `implementing` is a claim, nothing more; a parent's status is
only ever a claim and says nothing about its phase. `blocked` counts as
`todo`. `park`/`start` keep the state.

## Gates

| From → To | Artifact | Check | Judge | Record |
| --- | --- | --- | --- | --- |
| captured → scoped | scope brief in the body | `tasks check` clean; p/size/complexity/process set | you | `tasks edit … --process`, `gate: scoped` |
| scoped → designed (planned) | design spec | file exists, no placeholders | **human** | `tasks edit --spec`, `gate: designed <path>` |
| designed → planned (planned) | plan with `### Task N:` headings, one child per heading filed scoped | `tasks check` clean | **human** | `tasks edit --plan`, children with `--step`, `gate: planned <path>` |
| scoped → implementing (direct) | task worktree | `git worktree list` | you | `tasks start`, `gate: implementing <worktree>` |
| implementing → verified | verification output; each review finding with severity and disposition | commands ran against covered tree `<f>`; tests exist before the code they cover, and each new test was seen to fail against a targeted break of the behaviour it checks; code that reads a live store (task records, session stores, an index) ran over every record of the real store it reads, and `checks:` names that run; the note parses (`agents/flow/gate-notes.md`) | a reviewer without your context, dispatched by you, read the diff at `<f>` against the raw evidence it rests on (sources, transcripts, records, not your summary), hand-traced its hardest assertions, and tried its failure paths and, where it touches files or hooks, the delete and rename cases; then you | `gate: verified tree:<f> — checks: <commands and result>; review: none \| <severity> <disposition> <text>, …; reviewer: <harness/model \| human \| none> [session:<harness:id>]` |
| verified → closed | retro, the landing commit | `tasks check` clean; covered tree still `<f>` | you | `retro:`, `tasks done`, one commit (below) |

A finding is `important` or `minor`, `addressed` or `deferred`; its text has no
comma or semicolon. `important deferred` is not a verdict: address it or do not
write the gate. The reviewer label says what kind of reviewer was used and
nothing more; add `session:<harness:id>` when the reviewer ran in its own
session (a Codex thread, a cross-harness review). A Claude Code subagent shares
your session id, so it gets the label only. `none` means no independent
review happened; the skill does not close on it.

## Planned parent and children

The parent reaches `planned`; its children are filed there with `--parent`,
`--step`, `--complexity`, `--process` and a body that is their scope brief,
plus `gate: scoped — step of <parent> plan`. Each direct child runs
`implementing → verified → closed` in the parent's worktree. The parent is
`implementing` from the first child that starts until its own integration
verification (whole branch, full suite, one fresh review of the combined
diff), which needs every child closed. A child whose invalidation changes the
plan writes `gate: scoped — invalidated` on the parent too.

Any brief that hands work to an implementer (a child's scope brief, a subagent
dispatch) carries the contract the piece must satisfy, or its path, and a
one-line why for each detail that looks removable: an implementer who does not
know why a detail exists simplifies it away.

## Where the record lives

From `git worktree add` until the merge, the task's record lives in the
worktree it works in (a direct child's is its parent's; a planned child with
its own worktree uses that one), because the record lands with the code. Read
and write it there, from inside the worktree or with
`tasks -C .worktrees/<name>` and `flow-state` run inside it: the main
checkout's copy is as of the last merge, and a note written to it diverges and
comes back as a merge conflict. `start` and `park` write the record too, so
run them there; only the claim they take or release is shared across
checkouts. A note on another task (a planned child invalidating its parent)
goes where that task's record lives. Every brief you dispatch gives
absolute worktree paths and says to stop on a failed `cd` rather than fall
back to another directory.

## Closing sequence

`<f>` is `~/.agents/bin/flow-state fingerprint` at the moment verification ran. It hashes
the working tree, uncommitted edits included, minus `tasks/`, `docs/specs/`,
`docs/plans/`; a dirty submodule makes it refuse until clean.

1. Verify; any fix moves `<f>`, so re-run until the checks pass on the tree you will land.
2. `tasks note <id> "gate: verified tree:<f> — checks: …; review: …; reviewer: …"` (the shape above; `~/.agents/bin/flow-state <id>` must then print `verified (findings: …)`, not `inconsistent`)
3. `tasks note <id> "retro: …"`
4. Stage what will land; require `fingerprint --index` = `fingerprint` = `<f>` (both via `~/.agents/bin/flow-state`). A half-staged file fails here — fix it before anything is closed.
5. `tasks done <id> "…"`; stage the `tasks/` change.
6. One commit: code and every `tasks/` change from 2–5.
7. `~/.agents/bin/flow-state fingerprint --head` must equal `<f>`.

If 7 fails, or the commit itself fails for a reason that needs a covered
change: `tasks edit <id> --status todo`, `tasks start <id>`, then
`tasks note <id> "gate: implementing — reopened: commit <sha> landed tree:<g>, verified tree:<f>"`
(head check failed) or
`tasks note <id> "gate: implementing — reopened: commit failed: <reason>, verified tree:<f>"`
(commit failed), and start again at 1. A commit that failed for a reason outside the covered
tree (signing, a hook's own dependency) is retried at 6 with no record change — after
`~/.agents/bin/flow-state fingerprint` still reads `<f>`; if it does not, the tree changed
and you are back at 1.

## Opting in

One line in a project's `AGENTS.md`:

> This project uses the `flow` skill for task work. Superpowers process skills
> (brainstorming, writing-plans, executing-plans) do not trigger here; their
> implementation skills may be used inside a state when they fit.

The reference machine is `docs/specs/2026-09-15-flow-state-machine-design.md`
in the `tack` checkout.
