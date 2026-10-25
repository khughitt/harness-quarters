# ops-check adoption: implementation plan

**Goal:** vendor ops's shared hygiene checker into hq and run it in the pre-commit hook,
with the tree clean on both hosts, as designed in
`docs/specs/2026-10-24-ops-check-adoption-design.md` (accepted at d593f18).

**Architecture:** the checker arrives unchanged through ops `bin/vendored`. Narrow
`layout_allowed` entries cover host configuration and the relay cutover tool. Every
other layout value is rewritten to placeholders, and refused attachments are replaced
through the raw-plus-portable fallback. The hook change lands last, once both host runs
are clean, so record commits during the cleanup are not blocked.

**Task:** hq-c6a149. **Worktree:** .worktrees/ops-check-c6a149, branch
feat/ops-check-hq-c6a149. Every path below is relative to that worktree. Every command
runs there; a failed `cd` stops the step, with no fallback to another directory.

**Values never written into a tracked file:** the two hostnames, the home directory,
WORK_ROOT and the sync root. This plan and every commit on the branch must pass the
checker too. The placeholder mapping is the `mapping:` note on hq-c6a149. The second
host's observed values are the note after it, of 2026-10-24: no WORK_ROOT, no banned
list, and the same checkout paths.

## Setup (before Task 1)

- `tasks start hq-c6a149` in the worktree (the claim is already here once resumed).
- Baseline: `just test` (the full-suite route AGENTS.md names). Note the command, the
  test count and the result on hq-c6a149. A run that selects no tests is not a baseline.
- Shell values used below, set in each shell that needs them (never committed):

```sh
OPS=$(tasks --pretty root ops-88a0fa)
SECOND_HOST=<the host-b name from the mapping note on hq-c6a149>
```

- The D7 pair, used in Tasks 3 to 7. Save it as a script in a temporary directory
  outside the tree, for example `"$(mktemp -d)/d7.sh"`:

```sh
#!/usr/bin/env bash
# Run the vendored checker as is, then with the second host's values banned (spec D7).
set -uo pipefail
: "${SECOND_HOST:?set SECOND_HOST from the mapping note}"
python3 tools/ops-check; first=$?
sim=$(mktemp -d)
trap 'rm -rf "$sim"' EXIT
mkdir -p "$sim/tasks" "$sim/ops"
cp "${XDG_CONFIG_HOME:-$HOME/.config}/tasks/projects.toml" "$sim/tasks/"
python3 - "$sim" "$SECOND_HOST" <<'EOF'
import json, os, pathlib, sys, tomllib
sim, host = pathlib.Path(sys.argv[1]), sys.argv[2]
own = pathlib.Path(os.environ.get("XDG_CONFIG_HOME") or pathlib.Path.home() / ".config") / "ops" / "ops-check.toml"
banned = tomllib.loads(own.read_text())["banned"] if own.is_file() else []
(sim / "ops" / "ops-check.toml").write_text("banned = " + json.dumps(banned + [host]) + "\n")
EOF
XDG_CONFIG_HOME="$sim" python3 tools/ops-check; second=$?
echo "d7: primary=$first simulated=$second"
[ "$first" = 0 ] && [ "$second" = 0 ]
```

The second host has no WORK_ROOT, no banned list of its own, and the same checkout
paths and parents as this host. Its hostname is therefore the only value it adds. If a
fresh read over ssh shows otherwise, add the new values to the banned list in the script
and note the change on hq-c6a149.

### Task 1: Adopt tools/ops-check

**Files:** create tools/ops-check (written by `vendored adopt`); tools/README.md only if
adopt rewrites it.

- [ ] **Step 1:** `python3 "$OPS/bin/vendored" adopt ops-check`.
- [ ] **Step 2:** Verify the copy is landed bytes:
  `git -C "$OPS" show origin/HEAD:bin/ops-check | cmp - tools/ops-check` prints nothing.
  `head -2 tools/ops-check` shows the version line. `test -x tools/ops-check` passes.
  Run `python3 "$OPS/bin/vendored" status` and check that hq's ops-check row is current.
- [ ] **Step 3:** `python3 tools/ops-check; echo rc=$?`. Expected: rc=1, with the same
  291-line inventory the spec records (the hook does not run it yet).
- [ ] **Step 4:** Commit: `git add tools/ops-check tools/README.md` and
  `git commit -m "chore(tools): vendor ops-check from ops"`.

### Task 2: Fix the guide references

**Files:** modify README.md and AGENTS.md (outside the identity regions, which
`just docs` owns).

Apply these rewrites. Line numbers are as of 9738ea0; locate each line by its text.

| Line | Now | Becomes |
| --- | --- | --- |
| README 38, 39, 76 | `local/live-picks.json`, `local/live-picks-pi.json` in backticks | the same paths without backticks |
| README 86, 96 | `local/codex/trust.toml` in backticks | without backticks |
| README 58, AGENTS 39 | `extensions/harness-state.ts` | `pi/extensions/harness-state.ts` |
| README 146, 147 | "in lore at `./instructions/AGENTS.md`", "in lore at `./profiles/`" | "in lore `instructions/AGENTS.md`", "in lore `profiles/`" |
| README 174, 260, 261 | "lore's `./instructions/AGENTS.md`", "lore's `./profiles/`" | "lore `instructions/AGENTS.md`", "lore `profiles/`" |
| README 217 | `auth.json`, `trust.json`, `models-store.json`, `sessions/` | the same names without backticks |
| README 222 | `keybindings.json`, `APPEND_SYSTEM.md`, `prompts/`, `themes/` | without backticks |
| README 238 | `claude/settings.work.json`, `codex/config.work.toml`, `codex/rules/` (under local/) | without backticks |
| README 271, 320 | `history.jsonl` | without backticks; on 320 `state_5.sqlite` loses its backticks too, for consistency |
| README 280, 281 | `prefix/.worktrees`, `hq/tools` | without backticks (examples) |
| README 298 | "ops's `bin/project-colors`" | "ops `bin/project-colors`" |
| README 470 | `.claude-plugin/types/`, `tsconfig.json` | without backticks (the mod engine writes them) |

A prefix is the bare word, one space, then the backtick: no possessive, no "at".
Rewrapping can put a registered prefix word ("tasks", "ops", "hq") at the end of the line
above a reference that opens a line, so the checker runs after every edit.

- [ ] **Step 1:** Make the edits.
- [ ] **Step 2:** `python3 tools/ops-check 2>&1 | grep -E '^(README|AGENTS)\.md'` prints
  nothing. `python3 tools/ops-docs check` exits 0.
- [ ] **Step 3:** Commit: `docs: write guide references the shared checker can resolve`.

### Task 3: Layout policy for host configuration and the relay cutover tool

**Files:** create .ops-check.toml.

- [ ] **Step 1:** Write .ops-check.toml with exactly the D3 and D4 entries, each group
  under a one-line comment giving its reason (the spec's D3 and D4):

```toml
# Host configuration by design: harness homes read these absolute paths literally.
# The relay cutover tool, its tests, runbook and window plan: the two host names are its
# fleet configuration. Remove these entries with the tool if hq-7e81ed retires it.
layout_allowed = [
  "claude/settings.json",
  "codex/config.toml",
  "codex/hooks.json",
  "codex/work/hooks.json",
  "tools/relay_cutover_bootstrap/",
  "tools/relay-cutover-host",
  "tools/test_relay_cutover_bootstrap.py",
  "tools/test_relay_cutover_transport.py",
  "docs/runbooks/relay-cutover.md",
  "docs/plans/2026-10-19-relay-cutover.md",
]
```

  The checker requires the file to hold only `layout_allowed`; comments are TOML and
  allowed. Confirm with a run (a malformed file exits 2).
- [ ] **Step 2:** Run the D7 script. Expected: both runs still exit 1, and no finding
  names any allowed path. Check this with a grep over the output for each entry.
- [ ] **Step 3:** `tasks note hq-7e81ed "<one line: hq .ops-check.toml allows the relay
  cutover tool, tests, runbook and window plan by path (hq-c6a149); retiring the tool
  removes those entries in the same change>"`. Write it in the main checkout's record,
  since hq-7e81ed has no worktree. Write it without backticks, dollar signs or double
  quotes inside.
- [ ] **Step 4:** Commit: `chore: allow host configuration and the relay cutover tool to
  carry the layout`.

### Task 4: Rewrite documents and helpers to placeholders

**Files:** modify docs/notes/2026-10-08-claim-guard-rollout-judgment.md,
docs/notes/2026-10-10-codex-never-rejections-brief.md,
docs/notes/2026-10-20-session-log-survey.md,
docs/notes/data/2026-10-20-session-log-survey.jsonl,
docs/plans/2026-09-30-session-archive.md, docs/plans/2026-10-15-pi-live-picks.md,
docs/plans/2026-10-20-relay-cutover-bootstrap.md,
docs/specs/2026-09-30-session-archive-design.md,
docs/specs/2026-10-15-pi-live-picks-design.md,
docs/specs/2026-10-20-operator-runbooks-design.md, tools/session_archive/testing.py,
tools/test_session_log_cases.py and facts/capabilities.toml. Create
tools/session_log_private.py. Modify .ops-check.toml (one entry).

Use the spec's D5 table. In prose, the hosts are "the primary host" and "the second
host". In commands, JSON and table cells they are `host-a` and `host-b`. The home
becomes `~`, WORK_ROOT becomes `$WORK_ROOT`, and a checkout becomes `~/d/<project>`.
Every spelling of a host name in a rewritten file is replaced, capitalized ones
included.

- [ ] **Step 1:** For each markdown file, list the lines with
  `git grep -n -i -w -e "$(hostname)" -e "$SECOND_HOST" -- <file>`. Then list the path
  values with `git grep -n -F -e "$HOME" -e "$WORK_ROOT" -e "$(dirname "$OPS")" -- <file>`.
  Edit each line by hand, choosing the prose or literal form from the context.
- [ ] **Step 2:** The survey data is mechanical. Run a one-off Python rewrite from a
  temporary directory, never committed. It replaces the JSON `host` value and any path
  values, reading the values from the environment, and writes the file back. Then
  confirm that every line still parses as JSON:
  `python3 -c 'import json,sys; [json.loads(l) for l in open(sys.argv[1])]' <file>`.
  The record count stays 183.
- [ ] **Step 3:** In docs/notes/2026-10-20-session-log-survey.md, the line saying
  `source` is a home-relative glob resolved beneath the named host's home gains: host-a
  is the primary host, and the mapping is on hq-c6a149.
- [ ] **Step 4:** The privacy pattern moves. Create tools/session_log_private.py, which
  holds only the `PRIVATE` compiled pattern, moved verbatim with its comment and
  imports. In tools/test_session_log_cases.py, replace the definition with
  `from session_log_private import PRIVATE`. Add `"tools/session_log_private.py"` to
  .ops-check.toml with a comment: a privacy denylist that names the hosts in order to
  forbid them.
- [ ] **Step 5:** The fact note in facts/capabilities.toml says "across both hosts"
  instead of the two names. The session-archive testing docstring says "on the primary
  host".
- [ ] **Step 6:** Checks:
  - `uv run -q --with pytest pytest tools/test_session_log_cases.py -q` passes, with the
    same count as on the baseline tree;
  - `tools/harness-facts check` exits 0;
  - the D7 script shows no finding outside tasks/files.
- [ ] **Step 7:** Commit: `docs: replace host values with placeholders in historical
  documents and helpers`.

### Task 5: Attachment fallback for the 11 refused files

**Files:** none tracked by hand. `tasks` writes tasks/hq-*.md and tasks/files/, and
commits them under `[git] commit`.

The files: hq-48c5c6 (the two policy-check outputs whose names begin with host-b's name,
forms-probe.out, live-fixture.out), hq-583ac7 (relay-bootstrap-deferred-minors.md),
hq-7a2b95 (the smoke driver and the rollout JSON whose names begin with host-b's name),
hq-7b65dc (subagent-write-probe-2026-10-12.jsonl), hq-7cf7c1 (contamination-red.txt),
hq-c075d0 (relay-cutover-ledger.md) and hq-c6c847 (bootstrap-ledger.md). Confirm the
list against the D7 script's tasks/files findings before starting; the output is the
authority.

- [ ] **Step 1:** File the restoration task, modelled on obs-875105:
  `tasks add "Restore original historical attachments after the verified layout exemption ships" -p 3 --size s --complexity low --process direct --source hq-c6a149 -b "<body adapted from obs-875105: the 11 files, their raw copies under WORK_ROOT, restore through detach/attach after the exemption ships and hq adopts it, release only after verification; design completion alone does not trigger it>"`.
  Then `tasks dep <restore-id> --on ops-6e157a`. Note the id on hq-c6a149.
- [ ] **Step 2:** Create `$WORK_ROOT/hq/<restore-id>/` and note it on the restoration
  task at once: the host, the path in its literal `$WORK_ROOT` form, the purpose, the
  owner task, and that the contents are mutable and not yet checkpointed.
- [ ] **Step 3:** For each file, `git show 9738ea0:tasks/files/<task>/<name>` into
  `$WORK_ROOT/hq/<restore-id>/<task>/<name>`. Check that its SHA-256 equals that of the
  blob (`git show 9738ea0:… | sha256sum`) and that of the working copy.
- [ ] **Step 4:** For each file, make the derivative in a temporary directory, replacing
  every layout value with the D5 literal placeholders. Then run the vendored checker
  over it in a throwaway git repository holding only that file: it must report nothing
  for it. Check the derivative by `diff` against the raw copy, so that only values
  changed.
- [ ] **Step 5:** For each file, on its original task, run three commands in this order:
  1. `tasks note <task> "Portable attachment fallback for <name> under hq-c6a149: exact raw bytes retained by <restore-id> at \$WORK_ROOT/hq/<restore-id>/<task>/<name>, SHA-256 <hash>. Original-to-placeholder mapping: <JSON object of the values replaced>"`;
  2. `tasks detach <task> <name> "Preserved exact raw bytes and SHA-256 under <restore-id>; replace with a labelled portable derivative for shared-checker adoption"`;
  3. `tasks attach <task> <derivative> --name <name> --caption "Portable derivative; raw bytes, SHA-256 and mapping recorded on this task; raw item retained by <restore-id>"`.

  `tasks show <task>` must list it. The real values in the mapping note are exempt:
  task records are not scanned.
- [ ] **Step 6:** On the restoration task, write one `retained:` note per raw file, with
  host, kind `evidence`, path `$WORK_ROOT/hq/<restore-id>/<task>/<name>`, state `kept`,
  verification `verified`, sha256, purpose, next_owner `task:<restore-id>`, and
  cleanup_trigger "After the shipped layout exemption admits the original and hq adopts
  that checker version, restore and verify the original attachment". Then write a
  manifest (relative path and SHA-256 of every file, hidden files included, excluding
  itself) at `$WORK_ROOT/hq/<restore-id>/manifest.json`, plus one scratch `retained:`
  note naming it and its hash. Write each note with single quotes, as the
  retained-item reference's example does.
- [ ] **Step 7:** Checks:
  - the D7 script exits 0 (both runs clean);
  - `tasks check` is clean;
  - every raw copy's hash still matches its blob;
  - `git status` shows no uncommitted tasks/ change (otherwise run `tasks commit`).

### Task 6: Run the checker in the pre-commit hook

**Files:** modify .githooks/pre-commit and .githooks/test_pre_commit.py.

Precondition: the D7 script exits 0 on the current tree. Once this task commits, every
commit on the branch is gated.

- [ ] **Step 1 (fixture):** Rework `world` as the spec's D2 says.
  - Copy the vendored tools/ops-check into the fixture repository (from this worktree's
    tools/, at the test's import time), executable.
  - Build `env` key by key:
    - `PATH` from the parent;
    - `HOME` set to `tmp_path / "home"`, created;
    - `XDG_CONFIG_HOME` set to `tmp_path / "config"`, created empty;
    - `GIT_CONFIG_GLOBAL` set to an empty file under tmp_path;
    - `GIT_CONFIG_NOSYSTEM=1`;
    - `GIT_AUTHOR_NAME`, `GIT_AUTHOR_EMAIL`, `GIT_COMMITTER_NAME` and
      `GIT_COMMITTER_EMAIL` set to test values.
  - `sh()` takes that env for every fixture git call. No other inherited variable
    comes along.
  - Before the first write, assert that `git rev-parse --show-toplevel` is the fixture
    directory and that `git rev-parse --absolute-git-dir` lies inside it.
  - Run the existing six tests against the unchanged hook: they pass. The fixture change
    alone does not change a verdict.
- [ ] **Step 2 (RED):** Add three tests:
  - `test_a_layout_finding_refuses_before_the_docs_check`: write `notes.md` holding the
    fake HOME path, then `git add` it. Use a docs stub that writes `DOCS RAN` to stderr
    and exits 0. Expect exit 1, `machine layout` in stderr, and `DOCS RAN` absent.
  - `test_a_missing_ops_check_refuses`: unlink tools/ops-check. Expect exit 1 and
    `tools/ops-check` in stderr.
  - `test_an_ops_check_that_cannot_run_refuses`: write `.ops-check.toml` as
    `layout_allowed = "x"`. Expect exit 1 and `ops-check:` in stderr; the checker
    itself exits 2.

  Run `uv run -q --with pytest pytest .githooks/test_pre_commit.py -q`. All three fail
  against the current hook, and the failures are recorded in a note.
- [ ] **Step 3 (GREEN):** Add `hygiene_check()` to .githooks/pre-commit, beside
  `docs_check`, and update the module docstring:
  - a missing file fails, naming `vendored adopt ops-check`;
  - otherwise the hook runs `[sys.executable, "tools/ops-check"]` and captures stderr;
  - on rc 1 it writes stderr and fails with "the shared hygiene checks found the
    findings above in the working tree; fix them (AGENTS.md Gates)";
  - on any other non-zero rc it writes stderr and fails with "tools/ops-check could not
    run (exit <rc>)".

  `main()` returns
  `local_layer() or hygiene_check() or docs_check() or facts_check()`. Add a fourth
  test, `test_a_clean_tree_passes_the_hygiene_check`: a clean notes.md, exit 0. The
  whole file passes.
- [ ] **Step 4:** `just test` passes. Note the count beside the baseline.
- [ ] **Step 5:** Commit: `feat(hooks): run the shared hygiene checks in pre-commit`.
  The hook runs on this commit itself, which shows it passing on a clean tree.

### Task 7: Guides, final checks and the planted-commit probe

**Files:** modify AGENTS.md (Gates) and README.md (its checks section and Layout).

- [ ] **Step 1:** Edit the guides, without spelling host values:
  - AGENTS.md Gates: the pre-commit hook runs tools/ops-check after the local/
    refusal, with one line on what it checks. A record commit it refuses means a
    finding somewhere in the working tree. A new attachment carrying host values
    follows the retained-item reference's fallback, and .ops-check.toml is not widened
    for it.
  - README.md: the same in the section that describes the hooks. Layout names
    .ops-check.toml with the D3 and D4 reasons, one line each.
- [ ] **Step 2:** `python3 tools/ops-docs check` and `just docs` leave no diff. The D7
  script exits 0 on the tip.
- [ ] **Step 3:** Time the checker on the clean tree: `time python3 tools/ops-check`,
  three runs. Note the times on hq-c6a149 (the spec's cost risk).
- [ ] **Step 4:** Probe in a temporary clone:
  - `git clone -q . "$probe"` with `probe=$(mktemp -d)/hq`, then `just setup` there;
  - add a file holding `$HOME` and commit: refused, with `machine layout` in stderr;
  - remove the file, add a clean one and commit: succeeds;
  - `rm -rf` the clone.

  Run the probe's git with the same isolated git config the tests use, so the user's
  config is not touched.
- [ ] **Step 5:** Commit: `docs: describe the shared hygiene gate`.
- [ ] **Step 6:** `tasks check` is clean, and `git status` is clean apart from tasks/.

## Verification and closing (flow)

Integration verification follows these children:

- the whole-branch D7 pair;
- `just test`;
- one fresh-context review of the combined diff `9738ea0..HEAD`, against the spec and
  the raw evidence (the checker's code, the hook, the attachment raw copies and their
  hashes);
- the `gate: verified` note.

The branch then merges locally into main (personal profile). Before the merge, the D7
pair runs again if main has moved. The worktree goes through the removal checks, and its
`retained:` record is released.
