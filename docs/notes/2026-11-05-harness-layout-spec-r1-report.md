# Harness layout design: review round 1

Task: hq-b77d0c. Verdict: revise. Findings: Important 3, Minor 2.
Reviewer identity: `agy`; session `agy:2bd22bfa-4030-42e5-a4f8-7e6dbccd41c3`.
Reviewed repository: hq, branch `refactor/hq-b77d0c-harness-layout`.
Reviewed commit: `bf0256cd5e6fc2fa329db785d741c990f780be8c`.
Reviewed path: `docs/specs/2026-11-05-harness-layout-design.md`.
Reviewed blob: `e831667700bc3369faa6cc1fab0aad65e2039a4e`.

The user relayed this review to the controller. No reviewer-written file was
supplied and no plan workspace exists, so the controller persisted the full
substantive report here, normalizing host-specific links to repository paths.
The review suggested `agy gemini-4-argon` for the task note, but its metadata only
establishes `agy`: the reported `relay model` command exited 0 while printing
`relay: --harness must be one of codex, got "agy"`. No model is inferred.

## Verdict and scope

Revise, or approve with the findings bound into the spec and plan before planning.
The proposed grouping matches the November 5 prompt: move existing agy, Claude,
Codex and pi directories under `harnesses/`, and Ponytail under `external/`.
Keep shared root directories and omit empty Crush/OpenCode directories. Keep
`codex/hooks.json` and `codex/work/hooks.json` byte-identical through their moves
so Codex hook-trust hashes remain valid.

Four mechanics, grouped into three Important findings, can block pre-commit or
activation if implicit. The next action is for the parked controller to tighten
the spec before writing the implementation plan.

## Important 1: preserve the unfiltered agy setting explicitly

Locations: design lines 72–81; main's `agy/settings.json`; `harnesses.toml` agy
live-state declaration.

Main's current diff adds `"agentMode": "auto"`. It is absent from agy's clean
keys (`model`, `effort`, `effortByBase`, `trustedWorkspaces`,
`seasonalThemesOptIn`). The clean filter and live-picks neither strip nor capture
it. A merge moving the settings file can therefore refuse because local changes
would be overwritten. Capture/restore of model picks alone is insufficient.
The design must choose whether this setting becomes tracked at the new path,
joins the live-state declaration, or is explicitly carried across the merge.

## Important 2: detached agy settings and moved anchors block adoption

Locations: design lines 79–93; `tools/harness-links` lines 203–258;
`.githooks/live-picks` anchor declarations and `agy_anchored()`.

After main moves the files, the existing home anchors still point at the old
`agy/hooks.json` and `agy/skills.json` until relinking. If agy's settings home is
a regular file, as happens during normal atomic saves, `is_anchored()` is false.
`first_run()` is also false because the anchors need repointing, not creation.
`just link --apply` therefore refuses the whole run as a first-run file with an
anchor linked elsewhere. Meanwhile `live-picks sync` also sees an unanchored
home and does not adopt it. The same situation can occur after another host
receives the moved checkout through sync.

Synchronize detached agy settings back into a symlink before merging, and allow
no agy save between that step and relinking. The other-host procedure must cover
the post-sync condition explicitly, or repoint the two verified home anchors
before adopting the detached settings file.

## Important 3: name the mandatory path checks

Locations: design lines 53–68; `facts/capabilities.toml` and
`tools/harness-facts` lines 133–138; `tools/turn_pause/hook.py` `WIRING` and
`protected_paths()`; `.githooks/codex-trust` `LIVE_NAME` and `load_codex_spec()`.

- Twenty-one facts have active `probe` fields under the moved Claude, Codex or
  pi directories. `harness-facts check`, including staged pre-commit validation,
  requires each probe to be an existing checkout file. Update these fields in
  the same commit as the moves; preserve historical paths in fact notes and
  fixture source metadata.
- The turn-pause hook's `WIRING` tuple includes the three moved tracked Claude
  and Codex files and the unmoved private Claude work settings. Its
  `protected_paths()` uses these in the live PreToolUse protection boundary.
  Update the moved entries while preserving that boundary.
- `codex-trust` hardcodes `LIVE_NAME = "codex/config.toml"` and fails closed if
  the manifest differs. Update it with the manifest; keep
  `SAVED_NAME = "local/codex/trust.toml"` unchanged.

## Minor 4: account for ignored files left under the old directories

Locations: design lines 79–80 and 97–98; main's ignored Claude contents.

Ignored `claude/mods/cli-pane/.claude-plugin/types/`,
`claude/mods/cli-pane/tsconfig.json`, and `claude/probes/__pycache__/` currently
remain in main. Git will leave `claude/` present while they remain. Move needed
contents, or establish that they are regenerable and remove/regenerate them
explicitly, to meet the old-directory-absence requirement.

## Minor 5: name current runbooks and additional path consumers

Locations: design lines 61–65; `docs/runbooks/adding-a-harness.md`,
`docs/runbooks/relay-runtime.md`; `tools/relay_cutover_bootstrap/inputs.py`
`TARGETS`; `tools/test_worker_defaults.py` lines 40–74.

The two undated runbooks describe current behavior and require updates alongside
README and AGENTS. `docs/runbooks/relay-cutover.md` is historical evidence tied
to hq-7e81ed and should remain historical. Include the still-shipped cutover
bootstrap's target paths and worker-default tests in the plan's edit inventory.
The reviewer reported no external references to the moved hq subdirectories in
its scan of registered projects, and none in the private Claude/Codex work
configs; this is reviewer-reported scope, not a controller fresh host audit.

## Reviewer disclosures

The reviewer used tasks and session-logs to check the originating request and
frozen revision against the tree. It verified the reviewed design blob matched
HEAD `64631149`. The review was read-only: no files, task records, worktrees or
links changed. Its `host-load --section session` reported no surviving process.
