# Harness and external integration directories

Task: hq-b77d0c. Status: revised after review round 1; proposed for user review.

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
- Update `.githooks/codex-trust`'s hardcoded `LIVE_NAME` with the manifest;
  `load_codex_spec()` refuses a mismatch. Keep its saved trust path
  `local/codex/trust.toml` unchanged.
- Update the active `probe` fields in `facts/capabilities.toml` in the same commit
  as their file moves. `tools/harness-facts check` requires every probe to exist,
  including in staged-tree validation. Preserve historical fact notes and fixture
  `source` metadata; read facts through the tool before editing their declarations.
- Update the three moved tracked entries in `tools/turn_pause/hook.py`'s `WIRING`
  tuple, preserving `protected_paths()` coverage and the unchanged private work
  settings path. Include the still-shipped `tools/relay_cutover_bootstrap/inputs.py`
  `TARGETS` and `tools/test_worker_defaults.py` in the edit inventory.
- Update affected tests and fixtures, current README/AGENTS/reference guidance,
  and any active operational consumers found during the path audit. Preserve
  native home paths and historical evidence paths; do not blindly replace every
  occurrence of a harness name. Read capability evidence through `harness-facts`.
- Update the current `docs/runbooks/adding-a-harness.md` and
  `docs/runbooks/relay-runtime.md`. Keep the historical
  `docs/runbooks/relay-cutover.md` as evidence of its original rollout.
- Move `codex/hooks.json` and `codex/work/hooks.json` byte-for-byte: neither
  needs changed hook commands for this layout. Preserve their existing home link
  names and Codex `[hooks.state]` entries; do not synthesize trust hashes.
- Before activation, audit registered consumers and private work configurations
  for references to the moved paths, without printing private configuration values.
  Any required changes outside hq belong in the concrete activation proposal.

## Preserve live state and activate deliberately

The implementation branch is prepared and tested in its worktree. It must not
repoint home links there. Re-inspect main at activation rather than assuming its
dirty state is unchanged. At round 1 review, main's agy diff adds
`"agentMode": "auto"`, an unfiltered key that live-picks does not capture.
The author's choice is to carry it explicitly to `harnesses/agy/settings.json`
as the same uncommitted setting: do not turn it into a tracked default or extend
the filter's ownership. Preserve its exact source bytes and unfiltered diff
before clearing the old path for merge, then reapply and verify that diff at the
new path. The activation proposal must name this temporary clearing/restoration;
never stash or overwrite main merely to obtain a clean status. Refuse conflicts
with newer tracked or concurrent edits. Apply the same preservation requirement
to any other newly observed unfiltered changes, including Codex configuration.

The implementation plan must specify a bounded, rehearsed transition using the
existing capture/restore and link tools, plus explicit one-time record-key changes.
Do not introduce permanent old-path fallbacks or a general migration framework.
Before main changes, preserve current live config bytes, saved picks, Codex trust,
and relevant ignored/untracked contents of moved directories. Account for detached
agy settings and running sessions that might rewrite them. Verify all saved record
keys and refuse ambiguous collisions rather than overwriting values.

On the initiating host, while old anchors and paths still exist, run the existing
`live-picks sync` and verify detached agy settings became a symlink to the old
tracked file. An approved activation window must prevent agy settings saves
from that point through merge and `just link --apply`; if that condition cannot
be established, stop the activation. Capturing model picks is separate from
carrying unfiltered settings such as `agentMode`.

The other-host procedure must also handle arrival of the new tree before local
links are repaired. With a detached settings file and old anchors, both link
adoption and live-picks adoption refuse or skip: a plain retry is insufficient.
Preserve detached bytes and verify the two old anchor symlinks belonged to this
checkout. After validating/migrating saved record keys for the installed manifest,
explicitly repoint those verified anchors to the new main-checkout targets, then
use live-picks to adopt/relink settings and run full link reconciliation. Refuse
foreign anchors, conflicting records or concurrent saves. Rehearse this post-sync
case as well as the initiating-host sequence. Handle already-migrated shared
records without applying the key rename twice; do not relax first-run ownership
checks or add permanent old-path aliases.

The transition must order those record-key changes, the main merge, hook execution,
and home-link reconciliation so hooks do not consume records under the wrong
manifest. Preserve enough state to restore the prior paths, record keys, and links
if validation fails. Inspect actual merge hooks when writing this sequence.

Inventory ignored/untracked entries in every moved main directory at activation.
For each, carry needed content to the corresponding new path without clobbering
existing content, or document that it is regenerable before discarding it.
Observed Claude entries include mod-generated types, `tsconfig.json`, and probe
`__pycache__`. Do not assume Git moves them, or remove the old directory
recursively. Verify the old directories are absent only after every entry has a
disposition, retaining needed unique bytes and rollback evidence.

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
Git configuration, and saved records, including old/new record keys, conflicting
keys, unfiltered `agentMode`, detached settings before merge and after sync,
foreign anchors, ignored contents, and refusal of concurrent writes. Verify the
two moved Codex hook files' bytes against their pre-move versions and preserve
hook-trust entries. Check capability probes and turn-pause protected-path coverage.
Run mandatory `just check-hygiene`. Automatic broad testing remains disabled by
the checkout's policy; a policy skip is not a test pass. Planning introduces no
runtime test obligation; establish the focused baseline when implementation starts.

After approval, write the implementation plan for its own review. The plan settles
the precise edit inventory, transition commands, rollback sequence, and focused
test selections within this scope.
