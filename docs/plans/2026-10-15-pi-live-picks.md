# pi Live Picks Implementation Plan

Status: approved for execution, 2026-10-15 (hq-24416e planned gate, a66b548);
revised after plan review round 1 (codex/gpt-6.1-sol),
with the spec's separate pi record. Task: `hq-24416e` (goal `hq-aa9b44`). Execution
method: subagent-driven implementation in this session, under the flow gates of the
enrolled trial. Tasks 1–4 are implemented and independently reviewed. The user
separately approved Task 5, and the primary host's live rollout passed on 2026-10-15.

**Goal:** pi's default model and thinking level survive every Git command that
rewrites `pi/settings.json`, captured by an hq-owned pi extension and restored by the
existing `live-picks` hooks.

**Architecture:** `.githooks/live-picks` gains `pi/settings.json` as a third owned file,
saved in its own record, `local/live-picks-pi.json`, with JSON handling driven by a
per-file table of picker groups instead of `name == CLAUDE`. A pi extension, `pi/extensions/harness-state.ts`, linked into
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
- pi's entry lives only in `local/live-picks-pi.json`; `local/live-picks.json` keeps
  exactly the Claude and Codex entries the pre-change tool accepts (spec §3.1).
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

- [x] Write the extension (spec §3.3). Command: `HQ_HARNESS_STATE_REFRESH`, else
  `~/.local/bin/harness-state-refresh` (resolved with `os.homedir()`). One run at a time;
  a request during a run sets one pending rerun. Spawn with `detached: true`, stdin `""`,
  stdout and stderr captured; on 10 s expiry `process.kill(-pid, "SIGTERM")`, then
  `SIGKILL` after 1 s. `model_select` and `thinking_level_select`: `await new
  Promise(setImmediate)` then start a run, not awaited. `agent_settled`: start a run,
  not awaited. `session_shutdown`: await the run in flight, then one final run. The
  first failure or timeout in a session calls `ctx.ui.notify(<message>, "warning")`;
  later ones are silent.
- [x] Write `pi/probes/extension-probe.py`. It builds a scratch agent directory (the
  extension linked into `extensions/` through a symlink; a `models.json` with a local
  dummy provider holding two models, no reachable endpoint; a scratch `settings.json`
  naming the first model as the default) and a stub refresh that appends a JSON line
  (time, event context from an env var the stub reads, the settings file's content) to
  a log. It prints one JSON line per check with raw observations, like `rpc-probe.py`.
  - P1a: `pi/bin/pi --mode rpc` with the stub; close stdin; the log has one line, from
    shutdown.
  - P1b: a stub that ignores SIGTERM (`trap '' TERM`) and starts a descendant that
    ignores it too, both sleeping 60 s, each recording its pid and the group id; close
    stdin; pi exits within 25 s, and no recorded pid survives (so SIGKILL ran).
  - P1c: a stub that sleeps 3 s and logs start and end times; send two RPC `set_model`
    calls between models A and B in quick succession (one run in flight, one rerun
    pending), then close stdin at once: the log shows no overlapping runs, exactly two
    runs (the one in flight and the final one), and pi exits within 25 s.
  - P2: two interactive sessions in `tmux new-session -d` (a `trap` kills the tmux
    session on any exit), each from a fresh scratch `settings.json` with default A and
    `defaultThinkingLevel: "medium"`:
    - session 1, started with no `--model` (it runs A/medium): set B as the default
      through the model selector, then `high` through the thinking selector; quit.
      Expect a stub line at each pick, each reading the new value.
    - session 2, started with `--model <provider>/B --thinking high`: set the current
      thinking level first, then the current model, as the default; quit. Model saving
      reapplies the saved thinking default, so this order keeps both picks unchanged.
      Expect no stub line at either pick, `settings.json` holding B/high, and the shutdown line reading B/high.
  The probe needs no API key. Record the exact key sequence in the script.
- [x] Run the probe, keep its output on the task as a note, and add facts through
  `tools/harness-facts` conventions (status, value, version `1.1.0`, date, evidence
  `hq-24416e`, note), probe `pi/probes/extension-probe.py`:
  `pi-extension-symlink-load` (boolean), `pi-shutdown-awaits-handlers` (boolean),
  `pi-default-write-before-deferred-select-handler` (boolean),
  `pi-unchanged-default-emits-select` (boolean, expected false). `tools/harness-facts
  check` passes.
- [x] If P2 shows the write after the deferred handler, remove the picker handlers and
  note the change on the task and in the spec (§3.3, §4.1) before continuing.

### Task 2: `live-picks` owns `pi/settings.json`

Files: `.githooks/live-picks`, `.githooks/test_live_picks.py`.

- [x] Extend every fixture that runs `live-picks` or the refresh with a tracked
  `pi/settings.json` (`{"lastChangelogVersion": "1.1.0"}` plus a `theme`) and its
  `.gitattributes` line, since a missing owned file is refused: `test_live_picks.py`,
  `test_codex_trust.py`, and `test_harness_state_refresh.py` (already has the file; add
  the attribute only if missing). Check with `grep -ln 'live-picks\|harness-state-refresh'
  .githooks/test_*.py tools/test_*.py` that no other fixture runs them.
- [x] Tests first, in those fixtures:
  the base design §4.2 cases 1, 3, 4, 5, 6, 7, 8 and 12 for pi (a parametrised file
  argument where the existing test's shape allows it, a new test otherwise), and spec
  §4.2 cases 1–4. Case 3 loads the tool with patched groups (`runpy` with an edited
  module source, or a helper exposing the check) and expects the import-time refusal.
- [x] Tests that pi's entry is written only to `local/live-picks-pi.json`, that
  `local/live-picks.json` never names `pi/settings.json`, that each record is validated
  on its own (an invalid pi record refuses pi and leaves Claude and Codex handled), and
  that a record whose content does not change is not rewritten.
- [x] Implement spec §3.1-§3.2: `PI = "pi/settings.json"`; `OWNED = (CLAUDE, CODEX, PI)`;
  `RECORDS = {CLAUDE: "local/live-picks.json", CODEX: "local/live-picks.json", PI:
  "local/live-picks-pi.json"}`, read and written per record under the one lock;
  `JSON_GROUPS = {CLAUDE: CLAUDE_GROUPS, PI: (("defaultProvider", "defaultModel"),
  ("defaultThinkingLevel",))}`; owned keys per file are the groups' union; the check
  per JSON file (disjoint groups, union within the filter's keys for that file, equal
  for Claude); `CLEAN[PI]` with the filter's pi keys; `FIELD[PI] = "values"`; every
  `name == CLAUDE` branch becomes a JSON-table lookup. Usage text and the docstring
  name pi.
- [x] `uv run -q --with pytest pytest .githooks -q`, then `just test`.

### Task 3: Link and docs

Files: `links.toml`, `README.md`, `.githooks/live-picks`, `.githooks/harness-state-clean`,
`.githooks/harness-state-refresh` (docstrings), `AGENTS.md` (the `pi/` entry),
`docs/specs/2026-10-10-live-model-preservation-design.md` (an "Extended by" line).

- [x] `[harness.pi.links]` gains `"extensions/harness-state.ts" =
  "pi/extensions/harness-state.ts"`. `tools/test_harness_links.py` already covers link
  kinds; add a case only if the nested link path (`extensions/…`, a directory pi may
  not have created yet) is not covered, and check what `harness-links` does when the
  parent directory is missing.
- [x] Docs per spec §3.5, including the capture window, the bound, `forget
  pi/settings.json`, the separate pi record, and the recovery of spec §5.

### Task 4: Rollback interleaving test

Files: `.githooks/test_live_picks.py` (or a new `test_live_picks_rollback.py`).

- [x] Spec §4.2 case 5, against the pre-change tool pinned at `6b434eb` (a constant in
  the test, with a comment naming it main before this change). The test reads each
  `.githooks/` file at that commit with `git -C <hq checkout> show 6b434eb:<path>` and
  skips with a named reason only when the commit is absent (a shallow clone); it never
  derives the commit from `merge-base`, so it keeps covering the old tool after this
  change lands.
  - In a temporary repository whose `local/` holds a Claude and Codex record and a pi
    record, the pinned `capture`, `restore`, `hook post-merge` and
    `harness-state-refresh` all exit 0, and `local/live-picks-pi.json` is unchanged
    byte for byte.
  - Interleaving: hold the host lock in the test, start this change's `capture` (it
    blocks on the lock with the new code loaded), swap `.githooks/` to the pinned files,
    release the lock; once the blocked capture finishes, it has written only the pi
    record, and the pinned `capture` then exits 0 with `local/live-picks.json` naming
    no pi entry.

### Task 5: Rollout

Not code: each step is an action on this host's live state, run after the user approves
the merge (an action outside the repository).

- [x] Merge into main; `just link --apply` (creates the extension link); `just
  link-check`.
- [x] Spec §5 check: in pi, set a default model and thinking level, quit; check
  `local/live-picks-pi.json` holds both; `git checkout -- pi/settings.json` in main; the
  defaults are back and `git status` is clean.
- [x] Note on `hq-a8d65f` that the second host's apply now also creates the extension link.

Rollout evidence: merge `c48ee06` installed the reviewed implementation; the home
extension and refresh command resolve into main. A private offline pi 1.1.0 session
saved its current thinking and model defaults, exited successfully and captured all
three owned fields. Checkout restored those same fields with an empty filtered diff.
The check then used `live-picks forget pi/settings.json` to restore the user's
original automatic defaults; all unowned settings were unchanged and no children
survived. Private backup and raw evidence are retained under
`local/pi-live-picks-rollout/20261016T003823Z/`. The second host remains a separate host apply.
