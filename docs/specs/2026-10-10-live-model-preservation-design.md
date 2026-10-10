# Live model preservation: keep model picks across Git updates

Status: draft for review 2026-10-10. Task: `hq-14d183` (goal `hq-cc17de`, report
`hq-a77096`). Brief: `docs/notes/2026-10-10-live-model-preservation-brief.md`. Builds
on the trust restore (`docs/specs/2026-09-29-codex-trust-restore-design.md`), whose
hook-coverage probe (§1 there) this design relies on unchanged.

## 1. Problem

The `harness-state` clean filter keeps the model pick out of the index: `model` and
`modelSettings` in `claude/settings*.json`, and the top-level `model` and
`model_reasoning_effort` in `codex/config*.toml`. The homes link to these files, so
the working tree holds the pick and no committed blob ever does. Any Git command that
writes a new blob of the file over the live one therefore drops the pick, and the
harness falls back to its default model until someone picks again. The checkout is
shared through Dropbox, so every host loses it at once.

`hq-a77096` reproduced this in a temporary repository with the real filter, Stop
refresh and restore hooks: a fast-forward merge of a commit that changed only `theme`
removed both Claude keys, and neither `post-merge` nor a later Stop put them back.
Today's only recovery is re-picking by hand; the README documents the loss.

The trust restore cannot be copied as it is. Its sidecar is an append-only union: a
table the live file lacks stays saved and comes back. A pick is a single replaceable
value. A union would resurrect an old pick over a newer one, and would undo a
deliberate return to the default.

### 1.1 What owns which field

| File (tracked, live on the personal home) | Owned fields | Written by | Fate on a Git rewrite |
|---|---|---|---|
| `claude/settings.json` | `model`, `modelSettings` | Claude Code `/model` | dropped (filtered) |
| `claude/settings.json` | `effortLevel` | Claude Code `/effort` | tracked: replaced by the committed value; out of scope (§2) |
| `codex/config.toml` | top-level `model`, `model_reasoning_effort` | Codex `/model` picker | dropped (filtered) |
| `local/claude/settings.work.json`, `local/codex/config.work.toml` | same keys | work home | untracked; Git never writes them; out of scope |

The work home's settings already live under untracked `local/` (`links.toml`), so Git
never replaces them. The tool owns exactly the two tracked files above and refuses any
other path.

## 2. Goals and non-goals

Goals:

- After any Git command that drops the owned fields, the last pick returns: at once
  where a hook runs, at the next turn end where none does.
- A pick made after the last capture is never overwritten by an older saved one.
- A deliberate return to the default stays the default.
- Restoring never changes what Git stages, never touches unrelated settings, and keeps
  Codex trust recovery working as it does now.
- Linked worktrees are never touched: their copies are not live.

Non-goals:

- Moving live settings out of tracked files. Neither harness offers a user-level
  overlay that its picker writes to: Claude Code's `/model` writes the user
  `settings.json`, Codex's picker writes `config.toml`, and both resolve through the
  home links into this checkout. Changing that would route every harness write
  (plugin toggles, hook trust) out of tracking, a far larger change made only to
  simplify this one (brief, alternative 2).
- Claude's `effortLevel`. It is tracked, not filtered, so `/effort` shows as a real
  change and a checkout restores the committed value rather than dropping it. Whether
  it should be filtered like Codex's effort is a separate question; a follow-up idea
  records it.
- Picks lost before the record first exists, and a pick that lost a race with a Git
  command before any capture saw it (§3.5).

## 3. Design

### 3.1 The record

`local/live-picks.json`, untracked and carried between hosts by Dropbox like
`local/codex/trust.toml`. One entry per owned file:

```json
{
  "claude/settings.json": {"state": "set", "values": {"model": "opus"}},
  "codex/config.toml": {"state": "set",
                        "lines": ["model = \"gpt-6.1-sol\"\n",
                                  "model_reasoning_effort = \"high\"\n"]}
}
```

- `set` holds the owned fields the live file had at the last capture: parsed values
  for JSON, the exact source lines for TOML (so a restore writes what Codex wrote).
  Only the fields present are held; `modelSettings` absent at capture stays absent.
- `default` (no values) means the pick was deliberately reset; nothing is restored.
- A file with no entry has never been captured; nothing is restored.

The record is machine-owned and written whole, atomically. It is one record per
checkout, not per host, because the live files it mirrors are themselves shared.

### 3.2 The rule

The owned fields of one file form one unit. Git's filter drops all of them together,
so **all absent** is the only state a Git rewrite produces. Any other state was
written by the harness or a person, and the live file wins.

| Live file holds | Capture does | Restore does |
|---|---|---|
| any owned field | record `set` with exactly the fields present | nothing |
| none, at an explicit pick event (§3.3) | record `default` | nothing |
| none, anywhere else | nothing: absence alone cannot tell reset from rewrite | insert the record's fields if it is `set` |

This settles the precedence questions in the brief:

- **Newer live values win.** Restore only fills an all-absent file, so it can never
  overwrite a pick. A later pick is present at the next capture and replaces the
  record.
- **Reset to default.** A reset is recorded as `default` only from an event that
  proves it was a pick (§3.3), or by `forget` (§3.4). Absence seen at a turn end never
  changes the record.
- **Partial state** (say `model` without `modelSettings`) is a harness choice: it is
  captured as is and never "completed" from the record.

### 3.3 Where it runs

The tool `.githooks/live-picks` works on the checkout it lives in, refuses a linked
worktree as `codex-trust` does, and holds an exclusive `flock` on
`local/live-picks.json.lock` for every read-modify-write of the record or a live file.

- **Turn end, both harnesses.** `harness-state-refresh` (Stop) runs `live-picks sync`
  (capture then restore) beside `codex-trust sync`, before its staging step, under the
  same `index.lock` skip. This is the capture point for Codex and the fallback restore
  for every Git command no hook covers (stash, reset, cherry-pick, revert, aborts, a
  conflicted merge, a fast-forward-only rebase).
- **Claude's pick event.** `PostModelSwitch` in `claude/settings.json` also runs
  `~/.local/bin/harness-state-refresh`, which reads the payload's `hook_event_name`
  and runs `live-picks capture --explicit`. Only this capture may record `default`:
  the event proves a pick happened, so an all-absent file there is a reset. It also
  clears the size-only `M` mark the pick left. Claude Code has no event for `/effort`,
  which this design does not own.
- **After a Git command.** `post-checkout`, `post-merge` and `post-rewrite` run
  `live-picks hook <name>` after `codex-trust hook <name>`, each in its own process so
  one failure never hides the other. Like the trust hook, it restores and restages,
  never captures (the file is already overwritten), skips a linked worktree silently,
  skips `post-checkout` during a rebase, reports failures on stderr and exits 0.

Codex has no event near its picker, so a Codex reset cannot be told from a rewrite at
a turn end. That is acceptable only if the picker never writes the all-absent state
itself; probe P2 (§4.1) settles it, and `forget` covers a hand reset.

### 3.4 Operations

- `capture [--explicit]`: apply §3.2's capture column to each owned file.
- `restore`: apply its restore column. JSON: parse the live file, add the recorded
  keys, write with the clean filter's serialization (`indent=2`, `ensure_ascii=False`,
  final newline). TOML: insert the recorded lines immediately before the first table
  header (at the end when there is none), the same placement rule the trust restore
  uses. Before writing, both check that the result parses, holds exactly the live
  values plus the recorded ones, and has the same clean-filter output as the live
  file; otherwise nothing is written and the command exits non-zero. Writes are atomic
  through the link's target and keep the file's mode.
- `sync`: `capture`, then `restore`, under one lock.
- `forget <file>`: set the entry to `default` and remove the owned fields from the
  live file, keeping its clean-filter output; the way to return Codex to its default,
  and a manual override for either harness.
- `hook <name>`: `restore` as the Git hooks run it, then restage the file when its
  filtered diff is empty and no other Git process holds the index.

Shared mechanics now private to `codex-trust` (the Git helpers, linked-worktree and
rebase checks, atomic mode-preserving write, restage, lock) move to a module both
tools import, `.githooks/harness_state.py`. `codex-trust`'s behaviour and tests are
unchanged by the move.

### 3.5 Failure handling and limits

- **Missing record**: nothing to restore; capture creates it. **Invalid record**
  (not JSON, unknown file, unknown state, wrong value shape): every operation refuses
  and names the file; it is never overwritten, so a person decides. Deleting it is the
  reset.
- **Invalid live file** (JSON or TOML that does not parse, a TOML owned key spanning
  lines): refuse for that file, leave both files untouched, report.
- **Missing `local/`**: an error naming `just setup`.
- **Capture window.** A Codex pick is saved at the next turn end. A Git command that
  drops the file in between restores the previous pick. Claude picks are saved at
  the pick event, so the window there is only probe P1's ordering (§4.1).
- **Racing writes.** Restore re-reads the live file under the lock just before its
  atomic replace; a harness write in that instant can still be overwritten. The lock
  serializes this host's hooks only. Two hosts acting on the shared file at once can
  leave a Dropbox conflicted copy, as with trust.
- **No hook** for the commands listed in the trust spec's §1 probe: the next turn end
  restores. A main checkout parked on a branch without these hooks restores nothing
  until it returns.
- **Main versus worktree.** All operations refuse a linked worktree, and the Git
  hooks skip it, so a worktree's merge or checkout never writes a live file. The merge
  into main that brings a worktree's change runs main's `post-merge`.

### 3.6 Docs

README Setup replaces "the harness runs on its default model until the next pick" with
the restore behaviour, `forget`, and the limits above. The `harness-state-clean` and
`harness-state-refresh` docstrings name `live-picks`. `hq-a77096` gets a finding note
and the brief a "settled by" line in the commit that completes this design and plan.

## 4. Testing

### 4.1 Probes before implementation

Each answer goes into `facts/capabilities.toml` through `tools/harness-facts`, with
its record:

- **P1 — Claude ordering.** In a scratch Claude home whose `settings.json` is a
  throwaway file, does `PostModelSwitch` fire after the new `model` is on disk, and
  does choosing the default remove `model` (rather than write a resolved id)? If the
  hook fires first, `--explicit` cannot see the pick: Claude resets fall back to
  `forget`, and the plan says so before implementing §3.3's second bullet.
- **P2 — Codex picker.** In a scratch `CODEX_HOME`, does any picker action leave the
  config with neither owned key? If yes, a Codex reset is undone at the next turn end;
  the README states it and `forget` is the reset.

No probe touches the live homes.

### 4.2 Acceptance cases

Temporary repositories built like `test_codex_trust.py`'s, with the real filter and
hooks, and no live file:

1. A settings-changing fast-forward merge, a `git checkout -- <file>`, a branch switch
   and a replaying rebase each drop the fields; the hook restores them and the file is
   not marked modified.
2. `git stash` / `git reset --hard` drop them; no hook runs; the next `sync` restores.
3. A later pick (new value present) is captured and survives the next rewrite; the
   older value never returns.
4. `capture --explicit` on an all-absent file records `default`; a rewrite then
   restores nothing. `forget` does the same and removes the fields.
5. All-absent at a plain `capture` leaves a `set` record unchanged.
6. Partial state is captured as is and never completed.
7. Missing record: nothing restored, no error. Invalid record: refused, untouched.
8. A rewrite that also changes an unrelated setting keeps that setting; clean-filter
   output before and after restore is identical.
9. In a linked worktree, hooks do nothing and direct operations refuse.
10. Codex trust is restored in the same rewrite, and `test_codex_trust.py` passes
    unchanged after the module extraction.
11. A conflicted merge leaves the file for the next `sync`, which restores on disk
    without disturbing the merge's staged result.

## 5. Rollout and recovery

The main checkout's `.githooks/` is live: merging into main activates the hooks, and
that merge is a separately approved step. It lands in two merges so the second proves
the first:

1. **Tool and hooks**, with no change to `claude/settings.json` or `codex/`. Before
   merging, `git diff main... -- claude/ codex/` is empty. After it, the next turn end
   creates `local/live-picks.json`; check it holds the current picks.
2. **`PostModelSwitch` wiring** in `claude/settings.json`. This merge rewrites the live
   settings, so `post-merge` must restore the pick: check `model` is present afterward.

Recovery: revert the merge commits, delete `local/live-picks.json`, and re-pick by
hand, which is today's behaviour. A wrongly restored pick is undone with
`live-picks forget <file>` or a new pick.
