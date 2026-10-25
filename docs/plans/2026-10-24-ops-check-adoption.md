# ops-check adoption: implementation plan

Status: revision 4, 2026-10-24.
- **Revision 1** (996f187) went through a fresh-context agent review: 5 important
  findings and 12 minor.
- **Revision 2** addresses all of them:
  - byte identity is checked against the ref `vendored adopt` writes from, and
    `vendored status` moves after the merge;
  - the ordering test records its run in a marker file, and the clean case runs
    against the old hook;
  - main is merged into the branch before the hook change and before final
    verification, and the attachments it brings in get the same fallback;
  - each raw item's `retained:` record is written before its original is detached;
  - the D7 script lives at a fixed path, takes the repository and checker as inputs,
    and reads the second host fresh on every run;
  - quoting follows the retained-item reference's heredoc form.

  The user's review of it (round 2, reviewer `codex/gpt-6.1-sol`) found 3 important
  findings and 1 minor.
- **Revision 3** addresses those:
  - D7 collects the second host's HOME and configured config directory, bans a
    differing HOME, and fails on any read error except an absent banned file;
  - the clone probe is isolated before its first command, under a temporary HOME and
    config, and plants the hostname instead of the real home path;
  - every throwaway repository asserts both its top level and its git directory;
  - the tag dictionary gains `docs` and `session-logs`, so `tasks check` can be judged
    by printing nothing.

  The user's review of it (round 3, reviewer `codex/gpt-6.1-sol`) found 2 important
  findings.
- **Revision 4** addresses those:
  - the clone probe's isolated config holds the minimal registry the cleaned guides
    cite (lore and ops), copied from the real one, so the clean commit can pass;
  - the D7 merger validates every ops-check.toml against the checker's contract
    (exactly `banned`, a list of non-empty strings) and refuses other shapes.

  Both were checked in scratch runs. The merger refused a string, an empty item and an
  extra key, and kept a valid list. In an isolated clone with Task 2's lore and ops
  rewrites, the minimal registry left no reference finding, where an empty one left six.

**Goal:** vendor ops's shared hygiene checker into hq and run it in the pre-commit hook,
with the tree clean on both hosts, as designed in
`docs/specs/2026-10-24-ops-check-adoption-design.md` (accepted at d593f18).

**Architecture:** the checker arrives unchanged through ops `bin/vendored`. Narrow
`layout_allowed` entries cover host configuration and the relay cutover tool. Every
other layout value is rewritten to placeholders, and refused attachments are replaced
through the raw-plus-portable fallback. The hook change lands last, once both host runs
are clean on a tree that includes main, so record commits made during the cleanup are
not blocked.

**Task:** hq-c6a149. **Worktree:** .worktrees/ops-check-c6a149, branch
feat/ops-check-hq-c6a149. Every repository path below is relative to that worktree,
and every command runs there unless a step names another directory. A failed `cd`
stops the step, with no fallback to another directory.

**Values never written into a tracked file:** the two hostnames, the home directory,
WORK_ROOT and the sync root. This plan and every commit on the branch must pass the
checker too. The placeholder mapping is the `mapping:` note on hq-c6a149. Task
records are exempt from the checker, and `retained:` notes use the real observed
hostname (`$(hostname)`), as the retained-item reference asks.

**Where records are written:** every `tasks` write in this plan runs in the worktree,
so the records land with the merge. That includes notes, detaches and attaches on
other tasks (hq-48c5c6, hq-583ac7, hq-7a2b95, hq-7b65dc, hq-7cf7c1, hq-c075d0,
hq-c6c847, hq-7e81ed, and any task Task 6's merge adds) and the new restoration task.
Their main-checkout copies are then stale until the merge: a write to them from main
refuses with `stale_copy`. Of these, hq-583ac7 and hq-7e81ed are open. Before writing
to an open task, check `tasks claims` for a live claim held by another session. If one
exists, leave that task to its holder and note the conflict on hq-c6a149 instead.

## Setup (before Task 1)

- `tasks start hq-c6a149` in the worktree.
- Baseline: `just test` (the full-suite route AGENTS.md names). Note the command, the
  test count and the result on hq-c6a149. A run that selects no tests is not a baseline.
- Create `$WORK_ROOT/hq/hq-c6a149/` and note it on hq-c6a149 at once: the host, the
  path in its literal `$WORK_ROOT` form, the purpose (the three D7 files, a per-run tool
  regenerable from this plan), owner task:hq-c6a149, and that the contents are mutable
  and not yet checkpointed. At closing, the directory is discarded and its release is
  noted.
- Write the three D7 files below into `$WORK_ROOT/hq/hq-c6a149/` (d7.sh and
  d7-remote.zsh executable). In every shell that runs them, set:

```sh
OPS=$(tasks --pretty root ops-88a0fa)
export SECOND_HOST=<the host-b name from the mapping note on hq-c6a149>
D7=$WORK_ROOT/hq/hq-c6a149/d7.sh
```

- Correct the tag dictionary, so that `tasks check` can be judged by "prints nothing".
  Today it warns on nine records tagged `docs` (hq-30fd95, hq-c6a149 and its seven
  children) and four tagged `session-logs` (hq-7b131a, hq-a60cf5, hq-c1fecb,
  hq-cff824), because neither tag has a dictionary entry. Add both to `[tags]` in
  tasks/.config.toml, in alphabetical order:
  - `docs = "Guides and reference documents, and the checks that keep them true."`
  - `session-logs = "Reading harness session stores: the session-logs skill and its tools."`

  Commit with `chore(tasks): define the docs and session-logs tags`. Then
  `tasks check` prints nothing and exits 0. Every later "`tasks check` is clean" in this
  plan means that. A new warning that appears later is dispositioned in a note on
  hq-c6a149, never passed over.

`d7.sh`, the entry point:

```bash
#!/usr/bin/env bash
# Spec D7: run the checker in a repository as is, then with the second host's values banned.
# Usage: SECOND_HOST=<name> d7.sh [repo]. CHECKER overrides the checker (default: the repo's tools/ops-check).
# Reads the second host fresh on every run with d7-remote.zsh and merges its values with d7_values.py.
set -uo pipefail
here=$(dirname "$(realpath "$0")")
: "${SECOND_HOST:?export SECOND_HOST from the mapping note on hq-c6a149}"
while IFS= read -r name; do unset "$name"; done < <(compgen -e | grep '^GIT_')
repo=$(cd "${1:-.}" && pwd -P) || exit 2
[ "$(git -C "$repo" rev-parse --show-toplevel)" = "$repo" ] || { echo "d7: $repo is not a repository top level" >&2; exit 2; }
checker=$(realpath "${CHECKER:-$repo/tools/ops-check}") || exit 2
config=${XDG_CONFIG_HOME:-$HOME/.config}
sim=$(mktemp -d); trap 'rm -rf "$sim"' EXIT
mkdir -p "$sim/tasks" "$sim/ops"
cp "$config/tasks/projects.toml" "$sim/tasks/" || exit 2
ssh -4 -o BatchMode=yes "$SECOND_HOST" zsh -l -s < "$here/d7-remote.zsh" > "$sim/remote" \
  || { echo "d7: reading $SECOND_HOST failed" >&2; exit 2; }
python3 "$here/d7_values.py" "$sim/remote" "$config" "$sim/ops/ops-check.toml" || exit 2
cd "$repo" || exit 2
python3 "$checker"; first=$?
XDG_CONFIG_HOME="$sim" python3 "$checker"; second=$?
echo "d7: primary=$first simulated=$second" >&2
[ "$first" = 0 ] && [ "$second" = 0 ]
```

`d7-remote.zsh`, run on the second host by a login zsh fed on stdin. Any read error
fails it. Only an absent banned file counts as an absent list:

```zsh
# Read on the second host by a login zsh (ssh <host> zsh -l -s < remote.zsh). Any read error fails.
setopt err_exit no_unset pipe_fail
h=$(hostname)
cfg=${XDG_CONFIG_HOME:-$HOME/.config}
print -r -- "host=$h"
print -r -- "home=$HOME"
print -r -- "work_root=${WORK_ROOT-}"
print -r -- "config=$cfg"
print -r -- "---registry"
cat -- "$cfg/tasks/projects.toml"
print -r -- "---banned"
f=$cfg/ops/ops-check.toml
if [[ -e $f || -L $f ]]; then
  print -r -- "present"
  cat -- "$f"
else
  print -r -- "absent"
fi
```

`d7_values.py`, which merges that host's values into the simulated banned list:

```python
"""Spec D7: merge the second host's layout values into a banned list for a simulated run.
Usage: python3 d7_values.py <remote-output> <local-config-dir> <out-ops-check.toml>. Exits 2 on any malformed input."""
import json, os, pathlib, sys, tomllib

def fail(message):
    sys.exit(f"d7: {message}")


def banned_list(text, where):
    """The checker's contract for ops-check.toml: exactly `banned`, a list of non-empty strings."""
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as error:
        fail(f"{where}: {error}")
    values = data.get("banned")
    if set(data) != {"banned"} or not isinstance(values, list) or not all(isinstance(v, str) and v for v in values):
        fail(f"{where}: expected exactly `banned = [...]`, a list of non-empty strings")
    return values

remote, config, out = map(pathlib.Path, sys.argv[1:4])
head, sep, rest = remote.read_text().partition("---registry\n")
registry, sep2, banned_part = rest.partition("---banned\n")
if not (sep and sep2):
    fail("remote output lacks its sections")
fields = dict(line.split("=", 1) for line in head.splitlines())
if set(fields) != {"host", "home", "work_root", "config"} or not fields["host"] or not fields["home"]:
    fail(f"remote header is malformed: {sorted(fields)}")
state, _, banned_text = banned_part.partition("\n")
if state not in ("present", "absent"):
    fail(f"remote banned state is {state!r}")

roots = lambda text: {str(pathlib.Path(r)) for r in tomllib.loads(text)["projects"].values()}
here = roots((config / "tasks" / "projects.toml").read_text())
there = roots(registry)
own = config / "ops" / "ops-check.toml"
values = banned_list(own.read_text(), own) if own.exists() else []

extra = [fields["host"]]
if fields["home"].rstrip("/") != str(pathlib.Path.home()):
    extra.append(fields["home"].rstrip("/"))
if fields["work_root"]:
    extra.append(fields["work_root"].rstrip("/"))
for root in sorted(there - here):
    extra += [root, str(pathlib.Path(root).parent)]
if state == "present":
    extra += banned_list(banned_text, "the second host's ops-check.toml")
values += [v for v in extra if v not in values]
out.write_text("banned = " + json.dumps(values) + "\n")
print(f"d7: {len(extra)} second-host values banned (home {'differs' if fields['home'].rstrip('/') != str(pathlib.Path.home()) else 'same'}, "
      f"WORK_ROOT {'set' if fields['work_root'] else 'unset'}, {len(there - here)} differing checkouts, banned list {state})", file=sys.stderr)
```

The second host's values are collected from its login environment:
- its hostname;
- its HOME, banned when it differs from this host's;
- its WORK_ROOT, when set;
- its configured config directory (`${XDG_CONFIG_HOME:-$HOME/.config}`), from which
  the registry and the banned list are read;
- each registered checkout that differs from this host's, with its parent;
- its banned list.

Every inherited `GIT_*` variable is unset first, and the repository must be its own top
level.

The files were prototyped on 2026-10-24:
- live against the worktree, the second host contributed one value (the hostname): its
  HOME is the same, its WORK_ROOT is unset, no checkouts differ, and it has no banned
  list;
- the collector exited non-zero when the banned path was a directory and when the
  registry was missing;
- the merger banned a differing HOME, WORK_ROOT, checkout and banned list from a crafted
  remote, and failed on malformed input;
- the run ignored an inherited `GIT_DIR`.

Each run prints its `d7:` summary line. A summary that differs from the live one above
is noted on hq-c6a149.

### Task 1: Adopt tools/ops-check

**Files:** create tools/ops-check (written by `vendored adopt`); tools/README.md only if
adopt rewrites it.

- [ ] **Step 1:** `python3 "$OPS/bin/vendored" adopt ops-check`.
- [ ] **Step 2:** Verify that the copy holds the bytes `vendored adopt` writes from,
  ops's local default branch (`landed_head()`, not `origin/HEAD`, which lags):
  - `git -C "$OPS" show main:bin/ops-check | cmp - tools/ops-check` prints nothing;
  - `git -C "$OPS" ls-tree main -- bin/ops-check` shows mode 100755, and
    `test -x tools/ops-check` passes;
  - `head -2 tools/ops-check` shows the version line. Note the version and the ops
    commit on hq-c6a149.
- [ ] **Step 3:** `python3 tools/ops-check; echo rc=$?`. Expected: rc=1, with the same
  291-line inventory the spec records. The hook does not run the checker yet.
- [ ] **Step 4:** Commit: `git add tools/ops-check tools/README.md` and
  `git commit -m "chore(tools): vendor ops-check from ops"`.

`vendored status` judges registered roots (the main checkout), so it cannot show the
copy before the merge. It runs at closing.

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
| README 271, 320 | `history.jsonl` | without backticks; `state_5.sqlite` (not a checked extension) is left as it is on both of its lines |
| README 280, 281 | `prefix/.worktrees`, `hq/tools` | without backticks (examples) |
| README 298 | "ops's `bin/project-colors`" | "ops `bin/project-colors`" |
| README 470 | `.claude-plugin/types/`, `tsconfig.json` | without backticks (the mod engine writes them) |

A prefix is the bare word, then one space, then the backtick: no possessive, no "at".
Rewrapping can put a registered prefix word ("tasks", "ops", "hq") at the end of the line
above a reference that opens a line, so the checker runs after every edit.

- [ ] **Step 1:** Make the edits.
- [ ] **Step 2:** Checks:
  - `python3 tools/ops-check 2>&1 | grep -E '^(README|AGENTS)\.md'` prints nothing;
  - `python3 tools/ops-docs check` exits 0.
- [ ] **Step 3:** Commit: `docs: write guide references the shared checker can resolve`.

### Task 3: Layout policy for host configuration and the relay cutover tool

**Files:** create .ops-check.toml.

- [ ] **Step 1:** Write .ops-check.toml with exactly the D3 and D4 entries. A comment
  above each group gives its reason, from the spec's D3 and D4:

```toml
layout_allowed = [
  # Host configuration by design: harness homes read these absolute paths literally.
  "claude/settings.json",
  "codex/config.toml",
  "codex/hooks.json",
  "codex/work/hooks.json",
  # The relay cutover tool, its tests, runbook and window plan: the two host names are
  # its fleet configuration. Remove these entries with the tool if hq-7e81ed retires it.
  "tools/relay_cutover_bootstrap/",
  "tools/relay-cutover-host",
  "tools/test_relay_cutover_bootstrap.py",
  "tools/test_relay_cutover_transport.py",
  "docs/runbooks/relay-cutover.md",
  "docs/plans/2026-10-19-relay-cutover.md",
]
```

  The checker requires the file to hold only `layout_allowed`. Comments are not keys,
  so they are allowed; a malformed file exits 2, which a run confirms.
- [ ] **Step 2:** Run `"$D7" .`. Expected: both runs still exit 1, and no finding names
  an allowed path. Check this with a grep over the output for each entry.
- [ ] **Step 3:** In the worktree, after checking `tasks claims` for hq-7e81ed, run
  `tasks note hq-7e81ed "hq .ops-check.toml allows the relay cutover tool, its tests, runbook and window plan by path (hq-c6a149); retiring the tool removes those entries in the same change"`.
  The note lands with the merge, together with the entries it describes.
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
included. The review of revision 1 found that these files carry only hostnames, so the
path grep in Step 1 is expected to find nothing.

- [ ] **Step 1:** For each markdown file, list the lines with
  `git grep -n -i -w -e "$(hostname)" -e "$SECOND_HOST" -- <file>` and the path values
  with `git grep -n -F -e "$HOME" -e "$WORK_ROOT" -e "$(dirname "$OPS")" -- <file>`.
  Edit each line by hand, choosing the prose or the literal form from its context.
- [ ] **Step 2:** The survey data is mechanical. Run a one-off Python rewrite from a
  temporary directory, never committed. It replaces each record's `host` value
  (`host-a`) and any path values, reads the real values from the environment, and
  writes the file back. Then confirm every line still parses:
  `python3 -c 'import json,sys; [json.loads(l) for l in open(sys.argv[1])]' <file>`.
  The record count stays 183.
- [ ] **Step 3:** In docs/notes/2026-10-20-session-log-survey.md, the line saying
  `source` is a home-relative glob resolved beneath the named host's home gains: host-a
  is the primary host, and the mapping is on hq-c6a149.
- [ ] **Step 4:** The privacy pattern moves. Create tools/session_log_private.py with a
  one-line docstring (a privacy denylist the session-log fixtures must not match),
  `import re`, and the `PRIVATE` compiled pattern, moved verbatim. In
  tools/test_session_log_cases.py, replace the definition with
  `from session_log_private import PRIVATE`, and drop `re` there only if nothing else in
  the file uses it. Add `"tools/session_log_private.py"` to .ops-check.toml, under its
  own comment: a privacy denylist that names the hosts in order to forbid them.
- [ ] **Step 5:** facts/capabilities.toml: three notes change.
  - Line 220's note says "across both hosts" instead of naming the two.
  - The notes at lines 228 and 240 begin with the capitalized primary hostname; they
    begin "The primary host's" instead.

  The session-archive testing docstring says "on the primary host". Run
  `git grep -n -i -w "$(hostname)" -- facts/capabilities.toml tools/session_archive/testing.py`
  afterwards; it prints nothing.
- [ ] **Step 6:** Checks:
  - `uv run -q --with pytest pytest tools/test_session_log_cases.py -q` passes, with the
    same count as on the baseline tree;
  - `tools/harness-facts check` exits 0;
  - `"$D7" .` shows no finding outside tasks/files.
- [ ] **Step 7:** Commit: `docs: replace host values with placeholders in historical
  documents and helpers`.

### Task 5: Attachment fallback for the refused files

**Files:** none tracked by hand. `tasks` writes tasks/hq-*.md and tasks/files/ in the
worktree, and commits them under `[git] commit`.

The files as of 9738ea0 (11 on 7 tasks):

| Task | Files |
| --- | --- |
| hq-48c5c6 | the two policy-check outputs whose names begin with host-b's name, forms-probe.out, live-fixture.out |
| hq-583ac7 | relay-bootstrap-deferred-minors.md |
| hq-7a2b95 | the smoke driver and the rollout JSON whose names begin with host-b's name |
| hq-7b65dc | subagent-write-probe-2026-10-12.jsonl |
| hq-7cf7c1 | contamination-red.txt |
| hq-c075d0 | relay-cutover-ledger.md |
| hq-c6c847 | bootstrap-ledger.md |

Before starting, confirm the list against the tasks/files findings of `"$D7" .`; the
output is the authority. Task 6 Step 1 runs this same sequence for any file main adds.

- [ ] **Step 1:** File the restoration task, modelled on obs-875105:
  `tasks add "Restore original historical attachments after the verified layout exemption ships" -p 3 --size s --complexity low --process direct --source hq-c6a149 -b "<body adapted from obs-875105>"`.
  The body says:
  - the files it owns are those its `retained:` notes list;
  - their raw copies are under WORK_ROOT;
  - they are restored through detach and attach after the exemption ships and hq adopts
    that checker version;
  - each is released only after verification;
  - design completion alone does not trigger it.

  Then run `tasks dep <restore-id> --on ops-6e157a` and note the id on hq-c6a149.
- [ ] **Step 2:** Create `$WORK_ROOT/hq/<restore-id>/` and note it on the restoration
  task at once: the host, the path in its literal `$WORK_ROOT` form, the purpose, the
  owner task, and that the contents are mutable and not yet checkpointed.
- [ ] **Step 3 (preserve):** For each file, write `git show 9738ea0:tasks/files/<task>/<name>`
  to `$WORK_ROOT/hq/<restore-id>/<task>/<name>`. For a file main added after 9738ea0, use
  the merge commit that brought it in. Check that the copy's SHA-256 equals both the
  blob's (`git show <commit>:… | sha256sum`) and the working copy's.
- [ ] **Step 4 (record):** For each file, before anything is detached, write its
  evidence record on the restoration task in the reference's heredoc form:

```sh
tasks note <restore-id> "$(cat <<'EOF'
retained: {"host":"<hostname output>","kind":"evidence","path":"$WORK_ROOT/hq/<restore-id>/<task>/<name>","state":"kept","verification":"verified","sha256":"<hash>","purpose":"Exact raw bytes of <task> attachment <name>, replaced on that task by a portable derivative for shared-checker adoption","next_owner":"task:<restore-id>","cleanup_trigger":"After the shipped layout exemption admits the original and hq adopts that checker version, restore and verify the original attachment"}
EOF
)"
```

  The `$WORK_ROOT` stays literal: the heredoc is quoted.
- [ ] **Step 5 (derive):** For each file, make the derivative in a temporary directory,
  replacing every layout value with the D5 literal placeholders. `diff` it against the
  raw copy: only values change. Then check it in a throwaway repository:
  - make a temporary directory and `git init` it with every inherited `GIT_*` variable
    unset, `GIT_CONFIG_GLOBAL` set to an empty temporary file, `GIT_CONFIG_NOSYSTEM=1`,
    and `GIT_AUTHOR_*` and `GIT_COMMITTER_*` set to test values;
  - before its first write, assert both that `git -C <throwaway> rev-parse --show-toplevel`
    is the directory (physical path, `pwd -P`) and that
    `git -C <throwaway> rev-parse --absolute-git-dir` lies inside it;
  - put the derivative at its root under its own name (never under tasks/, where
    records are exempt) and `git add` it, since the checker reads tracked files;
  - run `CHECKER="$PWD/tools/ops-check" "$D7" <throwaway>` from the worktree. Both runs
    exit 0.
- [ ] **Step 6 (replace):** For each file, on its original task, in this order:
  1. the mapping note, in the heredoc form:

```sh
tasks note <task> "$(cat <<'EOF'
Portable attachment fallback for <name> under hq-c6a149: exact raw bytes retained by <restore-id> at $WORK_ROOT/hq/<restore-id>/<task>/<name>, SHA-256 <hash>. Original-to-placeholder mapping: <JSON object of the values replaced>
EOF
)"
```

  2. `tasks detach <task> <name> "Preserved exact raw bytes and SHA-256 under <restore-id>; replace with a labelled portable derivative for shared-checker adoption"`;
  3. `tasks attach <task> <derivative> --name <name> --caption "Portable derivative; raw bytes, SHA-256 and mapping on this task; raw item retained by <restore-id> (its retained: record for <task>/<name>)"`.

  `tasks show <task>` must list it. The real values in the mapping note are exempt,
  since task records are not scanned.
- [ ] **Step 7 (checkpoint):** Write a manifest at
  `$WORK_ROOT/hq/<restore-id>/manifest.json`. It lists the relative path and SHA-256 of
  every file, hidden files included, and excludes itself. Then add one scratch
  `retained:` note on the restoration task naming the manifest and its hash, in the
  heredoc form.
- [ ] **Step 8:** Checks:
  - `"$D7" .` shows no tasks/files finding;
  - `tasks check` is clean;
  - every raw copy's hash still matches its blob;
  - `git status` shows no uncommitted tasks/ change (otherwise run `tasks commit`).

### Task 6: Run the checker in the pre-commit hook

**Files:** modify .githooks/pre-commit and .githooks/test_pre_commit.py.

- [ ] **Step 1 (merge main):** `git merge main` into the branch and resolve any conflict.
  Run `"$D7" .` on the result. Any new tasks/files finding (main already holds one:
  hq-83c787's windows-refined.txt) goes through Task 5 Steps 3 to 8 on the same
  restoration task, with the open-task claim check from the header. Any other new
  finding is fixed by the rule its kind follows (Task 2, 3 or 4). Precondition for the
  rest of this task: `"$D7" .` exits 0.
- [ ] **Step 2 (fixture):** Rework `world` as the spec's D2 says.
  - Copy the vendored tools/ops-check into the fixture repository from this
    worktree's tools/ (the path next to the test file's parent), executable.
  - Build `env` key by key:
    - `PATH` from the parent;
    - `HOME` set to `tmp_path / "home"`, created;
    - `XDG_CONFIG_HOME` set to `tmp_path / "config"`, created empty;
    - `GIT_CONFIG_GLOBAL` set to an empty file under tmp_path;
    - `GIT_CONFIG_NOSYSTEM=1`;
    - `GIT_AUTHOR_NAME`, `GIT_AUTHOR_EMAIL`, `GIT_COMMITTER_NAME` and
      `GIT_COMMITTER_EMAIL` set to test values.
  - `sh()` takes that env for every fixture git call, so no other inherited variable
    comes along.
  - Before the first write, assert that `git rev-parse --show-toplevel` is the fixture
    directory and that `git rev-parse --absolute-git-dir` lies inside it.
  - Run the existing six tests against the unchanged hook: they pass. The fixture change
    alone changes no verdict. test_pre_commit_facts.py has its own fixture and is not
    touched.
- [ ] **Step 3 (RED):** Add four tests and run
  `uv run -q --with pytest pytest .githooks/test_pre_commit.py -q` against the
  unchanged hook:
  - `test_a_layout_finding_refuses_before_the_docs_check`: write `notes.md` holding the
    fake HOME path and `git add` it. Use a docs stub that touches a marker file
    (`tmp_path / "docs-ran"`) and exits 0. Expect exit 1, `machine layout` in stderr,
    and the marker absent. Against the old hook it fails: exit 0, and the marker exists.
  - `test_a_missing_ops_check_refuses`: unlink tools/ops-check. Expect exit 1 and
    `tools/ops-check` in stderr.
  - `test_an_ops_check_that_cannot_run_refuses`: write `.ops-check.toml` as
    `layout_allowed = "x"`. Expect exit 1 and `ops-check:` in stderr; the checker
    itself exits 2.
  - `test_a_clean_tree_passes_the_hygiene_check`: a clean notes.md, exit 0. This one
    passes against the old hook, which is its point.

  The first three fail, and the fourth passes. Record the outcome in a note on
  hq-f49c42.
- [ ] **Step 4 (GREEN):** Add `hygiene_check()` to .githooks/pre-commit, beside
  `docs_check`, and update the module docstring:
  - a missing file fails, naming `vendored adopt ops-check`;
  - otherwise the hook runs `[sys.executable, "tools/ops-check"]` and captures stderr;
  - on rc 1 it writes that stderr and fails with "the shared hygiene checks found the
    findings above in the working tree; fix them (AGENTS.md Gates)";
  - on any other non-zero rc it writes that stderr and fails with "tools/ops-check could
    not run (exit <rc>)".

  `main()` returns
  `local_layer() or hygiene_check() or docs_check() or facts_check()`. The whole file
  passes.
- [ ] **Step 5:** `just test` passes. Note the count beside the baseline.
- [ ] **Step 6:** Commit: `feat(hooks): run the shared hygiene checks in pre-commit`.
  The hook runs on this commit itself, which shows it passing on a clean tree.

From here on, every commit on the branch, record commits included, runs the checker.

### Task 7: Guides, final checks and the planted-commit probe

**Files:** modify AGENTS.md (Gates) and README.md (`## Setup`, which describes the
hooks, and `## Layout`).

- [ ] **Step 1:** Edit the guides, without spelling host values:
  - AGENTS.md Gates: the pre-commit hook runs tools/ops-check after the local/
    refusal, with one line on what it checks. A record commit it refuses means a
    finding somewhere in the working tree. A new attachment carrying host values
    follows the retained-item reference's fallback, and .ops-check.toml is not widened
    for it.
  - README.md `## Setup`: the same. `## Layout` names .ops-check.toml with the D3 and
    D4 reasons, one line each.
- [ ] **Step 2:** Checks:
  - `python3 tools/ops-docs check` passes, and `just docs` leaves no diff;
  - `python3 tools/ops-check` exits 0.
- [ ] **Step 3:** Commit: `docs: describe the shared hygiene gate`.
- [ ] **Step 4:** Merge main again if it has moved since Task 6 (`git merge main`), with
  the same handling as Task 6 Step 1. Then run `"$D7" .` on the tip; it exits 0.
- [ ] **Step 5:** Time the checker on the clean tip: `time python3 tools/ops-check`,
  three runs. Note the times on hq-c6a149, against the spec's cost risk.
- [ ] **Step 6:** Probe the tip in a temporary clone, isolated before its first command.
  - `base=$(mktemp -d)`. Create `$base/home`, an empty `$base/gitconfig`, and
    `$base/config/tasks/projects.toml` holding the minimal registry the cleaned guides
    need. Those are the projects whose prefix comes before a backticked reference after
    Task 2: `lore` (README's `instructions/AGENTS.md` and `profiles/` references) and
    `ops` (`bin/project-colors`). No other reference in README.md or AGENTS.md carries a
    registered prefix today; a scan of 3173288's guides found none.
    Write it from the real registry:

```sh
python3 - "$base/config/tasks/projects.toml" lore ops <<'EOF'
import os, pathlib, sys, tomllib
out, keep = pathlib.Path(sys.argv[1]), sys.argv[2:]
real = pathlib.Path(os.environ.get("XDG_CONFIG_HOME") or pathlib.Path.home() / ".config") / "tasks" / "projects.toml"
projects = tomllib.loads(real.read_text())["projects"]
missing = [p for p in keep if p not in projects]
if missing:
    sys.exit(f"probe: {missing} not registered")
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text("[projects]\n" + "".join(f'{p} = "{projects[p]}"\n' for p in keep))
EOF
```

    The checker only reads those checkouts (their file existence and `git ls-files`),
    so they stay untouched. The registry gives it no route to anything else. No
    `ops/ops-check.toml` goes into `$base/config`: the planted value is the hostname,
    which needs no banned list. If the clean commit below is refused on a reference
    finding, the finding names a prefix the list lacks. Add that prefix, rerun, and note
    it on hq-c6a149.
  - Run every probe command (clone, `just setup`, add, commit) under
    `env -i PATH="$PATH" HOME="$base/home" XDG_CONFIG_HOME="$base/config" GIT_CONFIG_GLOBAL="$base/gitconfig" GIT_CONFIG_NOSYSTEM=1 GIT_AUTHOR_NAME=probe GIT_AUTHOR_EMAIL=probe@example.invalid GIT_COMMITTER_NAME=probe GIT_COMMITTER_EMAIL=probe@example.invalid`.
    No other variable comes along: no credentials, no real HOME, and no inherited
    `GIT_*`.
  - Under that env, `git clone -q --no-local <worktree> "$base/hq"`, then `just setup`
    in the clone.
  - Before the first write, assert in the clone both that
    `git rev-parse --show-toplevel` is `$base/hq` (physical path) and that
    `git rev-parse --absolute-git-dir` lies inside it.
  - Plant this host's name. Add a file whose content is the output of `hostname`, and
    commit: refused, with `machine layout` and `(the hostname)` in stderr. The hostname
    is a layout value under any HOME, so the probe needs no real home path.
  - Remove that file, add a clean one and commit: succeeds.
  - `rm -rf "$base"`.
- [ ] **Step 7:** `tasks check` is clean, and `git status` is clean.

## Verification and closing (flow)

Integration verification follows these children:

- the whole-branch D7 pair on the tip;
- `just test`;
- one fresh-context review of the combined diff (`main...HEAD`), against the spec and
  the raw evidence: the checker's code, the hook, and the raw attachment copies with
  their hashes;
- the `gate: verified` note.

The branch then merges locally into main (personal profile). If main moved after the
verified tip, merge it into the branch first and rerun the D7 pair.

After the merge, in the main checkout:

- `python3 "$OPS/bin/vendored" status --project hq` shows `hq ops-check current`, with
  no `uncommitted` mark.
- Discard `$WORK_ROOT/hq/hq-c6a149/`. It holds only the regenerable D7 script.
- Run the worktree removal checks: ignored files, `tt-report`, and host pointers.
- Write the `released` notes for the scratch directory and the worktree on hq-c6a149's
  main-checkout record, as the retained-item reference says.
