# Harness layout plan: independent review

Task: hq-b77d0c; implementation child hq-7930ee, activation child hq-fd490e.
Verdict: accept, with no blocking findings and one non-blocking implementation note.
Reviewer: `agy`; session `agy:2bd22bfa-4030-42e5-a4f8-7e6dbccd41c3`.
Controller sequence: plan round 2 (the author self-review already occupies round 1).

Reviewed repository: hq.
Reviewed plan commit: `432432185328918540402a4f7ebc00820b7642de`.
Reviewed plan path: `docs/plans/2026-11-05-harness-layout.md`.
Reviewed plan blob: `ecdbef3585d32884107a3310fd4ca75c19733552`.
Binding spec commit: `d1399577ffe0fd65feaaa4393332e4f8b3f26498`.
Binding spec path: `docs/specs/2026-11-05-harness-layout-design.md`.
Binding spec blob: `061cce4524db8eeba690bb09615cdffc2dd9e422`.

The user relayed this full report. No reviewer file was supplied and no execution
workspace exists, so the controller persisted its substantive content here,
normalizing host-specific links to repository paths. The reviewer called this
its round 1 and suggested a note with no findings; the controller counts the
actionable implementation note as Minor 1 and uses the task's cumulative round.
Controller verification and disposition are separate task notes.

## Verdict and execution recommendation

The plan is ready for user approval. The reviewer concurs with inline execution
using executing-plans, followed by an independent whole-branch review before
separately gated live activation. The requested user action is to approve the
implementation plan and inline execution in the parked controller, and pass this
review to it before unblocking hq-7930ee.

## Coverage and structure verification

### Complete inventory and staged-tree atomicity

Plan lines 83–105 and 157–181 cover the five relocations: agy, Claude, Codex and
pi under `harnesses/`, Ponytail under `external/`. Shared root directories and
root manifests stay in place.

The inventory covers:

- `links.toml`, `harnesses.toml`, `.gitattributes`, `.gitignore`,
  `.ops-check.toml`, and `justfile`.
- `.githooks/live-picks`, `.githooks/codex-trust`,
  `.githooks/harness-state-clean`, `.githooks/harness-state-refresh`,
  and `.githooks/harness_state.py`.
- Agy's adapter root depth (`parents[2]`) and hook command paths; pi's launcher;
  21 active capability probe paths; turn-pause `WIRING`; bootstrap `TARGETS`;
  current docs/runbooks and all affected test modules, including worker defaults
  and direct subagent-write/successor-link probe imports.

Both Codex hook JSON files remain byte-identical, preserving hook trust without
synthesizing hashes. The coordinated edit respects staged-tree validation in
`.githooks/pre-commit` lines 114–159.

### Finite key transformation and rehearsal coverage

Plan lines 44–60, 111–150 and 183–265 define the finite
`tools/harness-layout-picks --root PATH --direction forward|reverse [--apply]`
command and `remap_record(record: dict, moves: dict[str, str]) -> dict`.
It uses `local/harness-state.lock`, validates all three records before writing,
rechecks bytes before atomic replacement and refuses symlink files, unknown
keys and old/new key collisions.

All five Review Focus conditions map to named tests in
`tools/test_harness_layout.py`. Subprocess environments are explicitly isolated,
with global/system Git configuration disabled and fixture root/git-dir
containment asserted. The post-sync detached-agy case aligns unfiltered content
across both possible mtime-selected bases before existing adoption runs.

### Decomposition

Plan lines 69–81 and 296–335 correctly separate implementation/rehearsal in the
worktree from approved live activation on main. Inline execution suits Task 1's
coupled moves and manifest/consumer edits, which cannot land piecemeal.

## Non-blocking implementation note: patch context after restored live state

Location: Task 1 Step 4.6, plan lines 207–227.

The reviewer notes that `git diff --binary` produces a clean-filtered patch,
while post-merge immediately restores picks and trust into working files.
TOML picks are prepended and JSON picks appended. The current `agentMode` delta
is away from those appended keys, but the reviewer predicts a patch failure for
an unfiltered delta near a JSON tail or TOML first header.

The suggested remedy is to restore only the patched target paths to the clean
reviewed blob immediately before `git apply --check --directory=harnesses` and
`git apply --directory=harnesses`:

```sh
git -c core.hooksPath=/dev/null restore --source="$REVIEWED" --worktree -- <patched new paths>
```

Then Step 4.7's trust/pick synchronization restores saved state on top of the
patched config. The reviewer asks for this case in the runbook and initiating
host test. This section records the reviewer's claim and recommendation, not a
controller-verified failure or an accepted hook-bypass instruction.

## Metadata and disclosures

The reviewer verified the author self-review document. It reported the plan as
unchanged at `9ea5908297325517545a55521107428561515d4a`. On receipt, the controller
observed `9ea590827a7df2c4460c30247b8cb97ab5fe2832`; the bound plan/spec commits
and blobs matched exactly. The differing incidental HEAD spelling does not
substitute for the verified frozen inputs.

The reviewer reported that `relay model --harness agy --pretty` exited 0 with
`relay: --harness must be one of codex, got "agy"`; no model identity is inferred.
Its review was read-only, with no files, task records, worktrees or host links
modified and no surviving background processes.
