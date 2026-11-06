# Harness and external integration directories

Task: hq-b77d0c. Status: proposed for user review.

## Intent and scope

The user's November 5 request is to reduce root-directory clutter by grouping
harness files under `harnesses/` and external skills under `external/`. Their
example names agy, Claude, Codex, Crush, OpenCode, pi, and Ponytail.

Reading taken: “harness log” means the harness-specific repository files shown in
the example. This proposal does not relocate native session logs or harness homes.
The user supplied the grouping; the scope choices below are the author's calls.

## Layout

Move existing directories as complete units:

| Current | Proposed |
| --- | --- |
| `agy/` | `harnesses/agy/` |
| `claude/` | `harnesses/claude/` |
| `codex/` | `harnesses/codex/` |
| `pi/` | `harnesses/pi/` |
| `ponytail/` | `external/ponytail/` |

`agents/`, `docs/`, `facts/`, `local/`, `relay/`, `systemd/`, `tasks/`, and
`tools/` remain at the root. Shared manifests remain there too.
`agents/` serves multiple harnesses; `relay/` pins shared hook infrastructure.
Keeping them in place avoids expanding this into a shared-tool reorganization.

Crush has no directory or declaration here, and OpenCode currently has a home-link
declaration but no repository directory. Create their `harnesses/<name>/`
directories when they acquire files, without adding placeholder integrations now.

The current Ponytail directory contains its integration configuration, not its
installed skill package. Moving it into `external/` establishes the requested
home for that integration. Installed plugin caches stay managed by their harnesses;
third-party skill sources owned by lore stay with lore. This change does not copy
or vendor additional skills into hq.

## Approaches

The author recommends direct moves with all active references updated together.
This matches the requested layout and leaves one authoritative location per file.
Keeping aliases at the old root paths would retain the clutter and add a
compatibility layer, contrary to the repository rules. A broader move of shared
tools, private state, and other projects' skill sources adds migration work without
being needed for this request.

## Changes required by the move

- Update `links.toml`, `harnesses.toml`, `.gitattributes`, `.gitignore`, and the
  existing path-specific hygiene allowances. Preserve the filter's fail-closed
  behavior and the privacy boundary around `local/`.
- Update hook commands, mod paths, installer recipes, launcher diagnostics,
  probe entry points, and code that calculates the repository root from its own
  file depth. In particular, `agy/hook` currently uses `parents[1]`.
- Update `.githooks/live-picks`' explicit agy paths and its anchor checks.
  Its saved records are keyed by config path and reject unknown keys: moving the
  manifest alone would make existing saved records invalid.
- Update affected tests and fixtures, current README/AGENTS/reference guidance,
  and any active operational consumers found during the path audit. Preserve
  native home paths and historical evidence paths; do not blindly replace every
  occurrence of a harness name. Read capability evidence through `harness-facts`.
- Before activation, audit registered consumers and private work configurations
  for references to the moved paths, without printing private configuration values.
  Any required changes outside hq belong in the concrete activation proposal.

## Preserve live state and activate deliberately

The implementation branch is prepared and tested in its worktree. It must not
repoint home links there. Main currently has live modifications to agy settings
and Codex configuration; they must survive the eventual move.

The implementation plan must specify a bounded, rehearsed transition using the
existing capture/restore and link tools, plus explicit one-time record-key changes.
Do not introduce permanent old-path fallbacks or a general migration framework.
Before main changes, preserve current live config bytes, saved picks, Codex trust,
and relevant ignored/untracked contents of moved directories. Account for detached
agy settings and running sessions that might rewrite them. Verify all saved record
keys and refuse ambiguous collisions rather than overwriting values.

The transition must order those record-key changes, the main merge, hook execution,
and home-link reconciliation so hooks do not consume records under the wrong
manifest. Preserve enough state to restore the prior paths, record keys, and links
if validation fails. Inspect actual merge hooks when writing this sequence.

Changing main's linked hooks and home targets changes the live agent surface.
Present the tested revision and exact activation steps for explicit approval
before that operation. Apply links from main only. Verify one host end to end;
record the adoption instructions for other hosts using the same configuration path.
Design approval alone does not authorize live activation.

## Acceptance and verification

The five old root directories are absent after activation, and their contents live
at the proposed locations. Existing homes, settings, hooks, mods, launchers, and
saved selections continue to work, without stale active references or lost private
state. The default Ponytail mode and pinned runtime versions do not change.

Use fresh focused checks through `just test-one` for links, manifest/filter/trust/
pick preservation, agy root resolution, hook wiring, pi launch/probes, and any
other changed path consumer. Rehearse the transition against isolated fake homes,
Git configuration, and saved records, including old keys and detached settings.
Run mandatory `just check-hygiene`. Automatic broad testing remains disabled by
the checkout's policy; a policy skip is not a test pass. Planning introduces no
runtime test obligation; establish the focused baseline when implementation starts.

After approval, write the implementation plan for its own review. The plan settles
the precise edit inventory, transition commands, rollback sequence, and focused
test selections within this scope.
