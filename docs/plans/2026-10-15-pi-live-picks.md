# pi Live Picks Implementation Plan

Status: draft for review, 2026-10-15. Task: `hq-24416e` (goal `hq-aa9b44`). Execution
method: inline in this session, under the flow gates of the enrolled trial.

**Goal:** pi's default model and thinking level survive every Git command that
rewrites `pi/settings.json`, captured by an hq-owned pi extension and restored by the
existing `live-picks` hooks.

**Architecture:** `.githooks/live-picks` gains `pi/settings.json` as a third owned file,
with JSON handling driven by a per-file table of picker groups instead of `name ==
CLAUDE`. A pi extension, `pi/extensions/harness-state.ts`, linked into
`~/.pi/agent/extensions/`, runs the shared `harness-state-refresh` at pi's picker
events (deferred one macrotask), at `agent_settled`, and at `session_shutdown`, each run
in its own process group under a 10-second limit.

**Tech stack:** Python 3 standard library and pytest (`just test`); TypeScript loaded by
pi's `jiti` with Node's `node:child_process`; tmux for the interactive probe.

**Spec:** `docs/specs/2026-10-15-pi-live-picks-design.md` (approved for planning
2026-10-15). Read it, and the base design
`docs/specs/2026-10-10-live-model-preservation-design.md` §3, before any task.

## Global constraints

- Owned pi fields are exactly `defaultProvider` + `defaultModel` (one unit) and
  `defaultThinkingLevel` (one unit). `deviceId` and `trackingId` stay filtered and are
  never owned (spec §2).
- Owned keys come from the filter's lists (`harness-state-clean`); `live-picks` never
  restates them except as groups, which an import-time check ties to the filter.
- Claude's and Codex's behaviour and every existing `test_live_picks.py` case stay
  unchanged.
- Probes use a scratch agent directory (`PI_CODING_AGENT_DIR`), never `~/.pi/agent`,
  and no request reaches a provider. The interactive probe runs in a detached tmux
  session and kills it on exit, success or failure.
- No home link changes before the rollout task; `just link --apply` runs from main only.
- Each task's tests are written first and seen to fail; `just test` passes before each
  commit.

### Task 1: The pi extension and its probes

Files: `pi/extensions/harness-state.ts` (new), `pi/probes/extension-probe.py` (new),
`facts/capabilities.toml`, `tools/test_pi_extension_probe.py` (new, if the probe's
parsing has logic worth a unit test).

- [ ] Write the extension (spec §3.3). Command: `HQ_HARNESS_STATE_REFRESH`, else
  `~/.local/bin/harness-state-refresh` (resolved with `os.homedir()`). One run at a time;
  a request during a run sets one pending rerun. Spawn with `detached: true`, stdin `""`,
  stdout and stderr captured; on 10 s expiry `process.kill(-pid, "SIGTERM")`, then
  `SIGKILL` after 1 s. `model_select` and `thinking_level_select`: `await new
  Promise(setImmediate)` then start a run, not awaited. `agent_settled`: start a run,
  not awaited. `session_shutdown`: await the run in flight, then one final run. The
  first failure or timeout in a session calls `ctx.ui.notify(<message>, "warning")`;
  later ones are silent.
- [ ] Write `pi/probes/extension-probe.py`. It builds a scratch agent directory (the
  extension linked into `extensions/` through a symlink; a `models.json` with a local
  dummy provider holding two models, no reachable endpoint; a scratch `settings.json`
  naming the first model as the default) and a stub refresh that appends a JSON line
  (time, event context from an env var the stub reads, the settings file's content) to
  a log. It prints one JSON line per check with raw observations, like `rpc-probe.py`.
  - P1a: `pi/bin/pi --mode rpc` with the stub; close stdin; the log has one line from
    shutdown.
  - P1b: a stub that sleeps 60 s after starting a `sleep 60` child; pi exits within
    25 s of stdin closing; no process from the stub's group survives (check by the
    group id the stub recorded).
  - P2: interactive `pi/bin/pi` in `tmux new-session -d` (a `trap` kills the session):
    set the second model as the default, then another thinking level, through the
    model and thinking selectors with `tmux send-keys`; then set the session's current
    model and level as the default, each differing from the saved default (start pi
    with `--model` on a model that is not the default); quit. Expect: a stub line at
    each changing pick holding the new value; none at the unchanged picks; the
    shutdown line holding the unchanged-pick defaults.
  The probe needs no API key. Record the exact key sequence in the script.
- [ ] Run the probe, keep its output on the task as a note, and add facts through
  `tools/harness-facts` conventions (status, value, version `1.1.0`, date, evidence
  `hq-24416e`, note), probe `pi/probes/extension-probe.py`:
  `pi-extension-symlink-load` (boolean), `pi-shutdown-awaits-handlers` (boolean),
  `pi-default-write-before-deferred-select-handler` (boolean),
  `pi-unchanged-default-emits-select` (boolean, expected false). `tools/harness-facts
  check` passes.
- [ ] If P2 shows the write after the deferred handler, remove the picker handlers and
  note the change on the task and in the spec (§3.3, §4.1) before continuing.

### Task 2: `live-picks` owns `pi/settings.json`

Files: `.githooks/live-picks`, `.githooks/test_live_picks.py`.

- [ ] Tests first, in the existing fixture extended with a tracked `pi/settings.json`
  (`{"lastChangelogVersion": "1.1.0"}` plus a `theme`) and its `.gitattributes` line:
  the base design §4.2 cases 1, 3, 4, 5, 6, 7, 8 and 12 for pi (a parametrised file
  argument where the existing test's shape allows it, a new test otherwise), and spec
  §4.2 cases 1–4. Case 3 loads the tool with patched groups (`runpy` with an edited
  module source, or a helper exposing the check) and expects the import-time refusal.
- [ ] Implement spec §3.2: `PI = "pi/settings.json"`; `OWNED = (CLAUDE, CODEX, PI)`;
  `JSON_GROUPS = {CLAUDE: CLAUDE_GROUPS, PI: (("defaultProvider", "defaultModel"),
  ("defaultThinkingLevel",))}`; owned keys per file are the groups' union; the check
  per JSON file (disjoint groups, union within the filter's keys for that file, equal
  for Claude); `CLEAN[PI]` with the filter's pi keys; `FIELD[PI] = "values"`; every
  `name == CLAUDE` branch becomes a JSON-table lookup. Usage text and the docstring
  name pi.
- [ ] `uv run -q --with pytest pytest .githooks -q`, then `just test`.

### Task 3: Link and docs

Files: `links.toml`, `README.md`, `.githooks/live-picks`, `.githooks/harness-state-clean`,
`.githooks/harness-state-refresh` (docstrings), `AGENTS.md` (the `pi/` entry),
`docs/specs/2026-10-10-live-model-preservation-design.md` (an "Extended by" line).

- [ ] `[harness.pi.links]` gains `"extensions/harness-state.ts" =
  "pi/extensions/harness-state.ts"`. `tools/test_harness_links.py` already covers link
  kinds; add a case only if the nested link path (`extensions/…`, a directory pi may
  not have created yet) is not covered, and check what `harness-links` does when the
  parent directory is missing.
- [ ] Docs per spec §3.5, including the capture window, the bound, `forget
  pi/settings.json`, and the rollback order of spec §5.

### Task 4: Rollback interleaving test

Files: `.githooks/test_live_picks.py` (or a new `test_live_picks_rollback.py`).

- [ ] Spec §4.2 case 5: a temporary repository with this branch's hooks and a record
  holding Claude, Codex and pi entries; replace `.githooks/` with the merge base's
  (`git show <base>:.githooks/<file>` for each file, the base read from the real
  repository's `git merge-base main HEAD` at test time, skipped with a named reason when
  run outside a branch that has one); run the old `capture`, `restore`, `hook
  post-merge` and `harness-state-refresh`, each refusing with the record unchanged byte
  for byte, including after a pi pick appears in the live file; run spec §5 step 2's
  command verbatim (read from the spec's code block, so the test fails if the spec's
  command drifts); then old `capture` exits 0, the Claude and Codex entries are
  unchanged and no pi entry appears.

### Task 5: Rollout

Not code: each step is an action on this host's live state, run after the user approves
the merge (an action outside the repository).

- [ ] Merge into main; `just link --apply` (creates the extension link); `just
  link-check`.
- [ ] Spec §5 check: in pi, set a default model and thinking level, quit; check
  `local/live-picks.json` holds both; `git checkout -- pi/settings.json` in main; the
  defaults are back and `git status` is clean.
- [ ] Note on `hq-a8d65f` that europa's apply now also creates the extension link.
