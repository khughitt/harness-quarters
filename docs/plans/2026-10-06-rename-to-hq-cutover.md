# The Rename to hq: Cutover — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Status:** draft 2026-10-06, for review. Task `tack-8b7a28`. Round 1 (Codex GPT-6-Astra): revise, P1 4 and P2 4, all addressed. Round 2 (a Claude reviewer that rebuilt Tasks 1 to 5 and ran the rehearsal): revise, Critical 1, Important 6 (two already fixed by round 1), Minor 5, all addressed: rollback accepts renamed attachment folders, `save` refuses `tasks check` findings, the rehearsal fetches submodules from the live checkouts, copies lock files and stands links in for un-cloned projects, and the runbook clears live records and findings first. Round 3 (the same reviewer, scoped, rebuilding from the revised plan): revise, Important 3 and Minor 4, all addressed: the attachments test attaches through `tasks attach`, stand-in links follow nested mirror paths, Task 11 forgets each distinct old path only where it has a table, and an attempt can be abandoned before `apply`. Round 4 (the same reviewer, scoped): accept, Minor 1, addressed: the abandon block restores the other host's timers only when its `current` link names this attempt. Round 5 (Codex, model unstated): revise, P1 2 and P2 2, all addressed: rollback re-establishes quiescence after Step 13 (sessions closed, timers stopped and drained again); `rolled-back` is written only after both hosts recover; `second-host` always reruns the idempotent adoption, rehearsed at tasks' own `resume_cleanup` boundary; the trial join must include a task of the renamed project. Loops stop their block; the trial join compares raw strings within each run; the other host's timers wait for a synced restore; every clone gets its live hooks; the second host's adoption resumes from a pre-move record and carries its own trust; each attempt has its own directory; trust goes through `codex-trust restore`.

**Goal:** Finish the rename design: `session-episodes` follows ids written under a retired prefix (phase 1 step 4), the consumers' edits are prepared and reviewed without activating (step 5), the rehearsal passes on copies, and the cutover runs on both hosts (phase 2).

**Architecture:** Tasks 1 to 6 land code under the name `tack`, in one worktree, each behaviour-preserving until the cutover calls it.
- `session-episodes` asks `tasks resolve` for the canonical form of every id its anchors name.
- `rename-cutover`'s `verify` asks `tasks resolve` whether the old id, root and storage still answer the new prefix, and the preparation plan's deferred minors are fixed.
- `quiesce-timers` records, stops, waits for and restores user timers.
- `rename-hq-steps` holds this rename's own edits and commits, and the second host's adoption. The rehearsal and the live run both call it, so the rehearsal exercises the live commands.
- `tools/rehearse_rename_hq.py` clones this host's checkouts into two scratch hosts and runs the cutover, the rollbacks, the guard's refusals and the second host's adoption there.

Task 7 reviews and merges. Task 8 adds the flow trial's end-to-end join to the rehearsal once `flows-44890e` and `obs-ff4e76` have landed, and runs the whole rehearsal on the cutover's day. Tasks 9 to 11 are the runbook: this host, the other host, then the forward-only steps.

**Tech Stack:** Python 3 standard library; pytest through `uv run`; the `tasks` CLI 0.2.0 with `[locations]` and `tasks resolve`; git; `just`; systemd user units; ssh to the second host.

**Spec:** `docs/specs/2026-10-06-rename-to-hq-design.md` (accepted at review round 5): §3.1 steps 4 and 5, §3.2 to §3.5, §4 and §5. It reads with tasks' `docs/specs/2026-10-06-project-resolution-design.md` (landed as `tasks-7580d2`): §2.3 adds a pre-move `tasks init --force` on every other host, and §3 defines `tasks resolve`.

## Inputs this plan takes

- **From `tasks-7580d2` (done 2026-10-06).**
  - **The location history.** `[locations.<prefix>]` records each host's storage and former roots. `tasks rename` moves the table, and `init --prefix P --force` at a new root appends the displaced root.
  - **The resolver.** `tasks resolve [--stdin] --json` maps alias ids, alias prefixes and former paths to the live prefix. It has `status` per row and `root` on every resolved row.
  - **The hand-over.** The second host installed the current binary on 2026-10-06. Its pre-move `init --force` is this plan's Task 9 Step 5. Its own `ai` backfill is the user's, and Task 9 reports whether it is there.
- **From `flows-44890e` and `obs-ff4e76` (both open).** Both chose the tasks resolver as their mechanism (their notes of 2026-10-06). Neither has a design yet.
  - Tasks 1 to 7 do not depend on them.
  - Task 8 does, and the runbook's preconditions require both done and the shared identity contract written.
  - Task 8 is written against the trial pipeline's present commands (`trial-arm census`, `obs outcomes report --units`, `trial-verdict --as-of`). If their delivery changes those commands, Task 8 is revised before it runs: that is a plan change, reviewed as one.
- **A probe made while writing this plan (spec §3.2 step 7).** With systemd 262, under `systemctl --root=<scratch> --global`:
  - Re-enabling a timer after its manifest-held link was repointed removed both links and recreated them at the unit link's new target.
  - So on this host a re-enable leaves the manifest-held link as `just link --apply` made it, and the runbook's fallback, a second `just link --apply`, is not expected. The runbook still checks with `just link-check`.
  - The second host's systemd version is read at its step, and the same check and fallback apply there.

## Departures from the spec, decided here

1. **`session-episodes` takes only the alias half of §3.5's mechanism.** It never reads a session's working directory. Ownership is by task id: session-logs design §4.1, "the file's `cwd` is not consulted". So former roots change nothing in it.
   - It resolves every id its anchors name, once per run.
   - Each episode carries the canonical id.
   - The episode id still hashes the id as written, so a review recorded before the rename still matches its episode after it.
   - Cost if wrong: one field's form in `episodes.jsonl`, which only this tool reads.
2. **The consumers' prose ships as one reviewed script in this repository, not as a branch in each.** §3.1 step 5 says each owning project holds a reviewed branch. What ops, lore and flows change at the cutover is prose, the mirror table and generated output. The trial and obs are code, and they land before the cutover under their own tasks, safe either side of the rename.
   - Branches would sit for weeks against moving mains.
   - The script names every edit, refuses any edit whose text has moved, and runs in the rehearsal against clones of each main that same day.
   - Cost if wrong: an owner first sees the edit at the cutover. This plan's review stands in for theirs.
3. **tack's edits are committed at step 4, not step 8.** §3.2 step 7 applies the links "after the commits they depend on", and rollback's second point is "after the commits" (§4). Step 8 commits only the task note that records verification.
4. **The cutover calls `python3 tools/ops-docs write`, `python3 bin/ops-projects pull` and `python3 bin/assemble-instructions write` directly, not their `just` recipes.** The recipes wrap them in `tt`, which writes timing records into the home directory. That would differ between the scratch hosts and this one. The commands themselves are the recipes' own.
5. **The rehearsal clones committed state.** A live checkout's uncommitted edits are not carried. The rehearsal copies `local/` and the two Codex trust files, which the cutover reads. Projects it does not clone are registered in the scratch registry at their live roots, read-only: `tasks check` in ops, lore and flows reads their records, and nothing writes there. The guard, the claims and every write stay in the scratch directories.

## Global Constraints

- The project is called `tack` until Task 9 Step 7 (`apply`), and `hq` from then on. Ids written `tack-<hex>` keep resolving through the alias.
- Tasks 1 to 7 work in `.worktrees/rename-hq-cutover` (branch `feat/rename-hq-cutover`; exists, set up with `just setup`). Task 8 works in a fresh worktree at the same path on branch `feat/rename-hq-trial-join`. Tasks 9 to 11 change live state from a session started in ops: the checkout moves from under any session standing in it (spec §3.2).
- No AI attribution in any commit. Conventional commit subjects. Never bypass a hook. A commit names its paths: `git commit -m … -- <paths>`. The exception is `rename-hq-steps`, which stages everything (`git add -A`), because `save` refused unless every tree was clean.
- A loop inside a block's chain runs in a subshell and stops with `exit 1`: `( for …; do … || exit 1; done ) && next`. A `break` would end the loop with status 0, and the chain would go on past a refusal.
- Shell state does not carry from one block to the next.
  - Every block in Tasks 1 to 8 opens by sourcing `docs/plans/2026-10-06-rename-to-hq-cutover.env.sh`. It sets:
    - `TACK`, `WT`, `BRANCH` and `BRANCH8`;
    - the step record ids `STEP1` to `STEP11`;
    - `STATE`, a git-ignored directory in the worktree;
    - `CUT`, the cutover's host-local directory `~/.local/state/rename-hq`. Each attempt works in `$CUT/attempt-<UTC time>` (`$RUN`), written by Task 9 Step 2;
    - two helpers: `t` (run a command, print its last line, keep its status, name the full log on failure) and `need` (refuse when a named variable is empty).
  - Every block in Tasks 9 to 11 sources `$CUT/env.sh`, which Task 9 Step 2 writes with the roots captured before the move.
  - Each block is one `&&` chain.
- No hostname and no machine-specific absolute path goes into a committed file. The second host's name lives only in `$CUT/second-host` on this host.
- Nothing in Tasks 1 to 8 touches live state. Tests and the rehearsal use scratch `HOME`, `XDG_CONFIG_HOME` and `XDG_STATE_HOME`. The rehearsal reads the live registry, the live checkouts and the live trust files, and writes only under its base directory.
- Never `just --quiet` (in just 1.58 it hides the recipe's output).
- Host steps wait for the user's approval at that moment. A task that reaches one parks with `tasks park … --waiting-on user --reason approval`. This covers Task 9 Step 1, Task 10 Step 1 and Task 11 Step 4.
- Tests:
  - The focused runs are `uv run -q --with pytest pytest tools/<file> -q` and `python3 -m pytest agents/bin/test_session_episodes.py -q`.
  - `just test` runs before every commit that touches code. There is no CI and no pre-push suite here.
  - The rehearsal runs only when named: `uv run -q --with pytest pytest tools/rehearse_rename_hq.py -q --basetemp "$STATE/rehearsal"`. Its name does not match `test_*.py`, so `just test` never collects it.

## Review Focus

Inputs the spec implies and a person will meet. Each has its test in the task that owns the code.

1. **A task started under `tack-` before the rename and closed under `hq-` after it.** The start, the close and the record join into one episode, with the canonical id and the old episode id. Task 1: `test_a_close_written_after_the_rename_closes_a_start_written_before`.
2. **A timer whose service is mid-run when the window opens.** `wait` lets it finish and never stops or kills the service. At the timeout it stops itself, naming the service. Task 4: `test_wait_returns_once_a_running_service_finishes` and `test_wait_stops_at_the_timeout_and_kills_nothing`.
3. **An edit whose text moved since the script was written**, for example `flows-44890e` rewriting `trial-arm`'s header. `rename-hq-steps` stops at that edit, names the file and the text, and writes nothing to it. Task 5: `test_replace_once_refuses_text_that_is_missing_or_repeated`. The rehearsal (Task 6, and again in Task 8 on the cutover's day) runs every edit against the live mains.
4. **The second host adopting before its storage moves, with the link dangling.** Its storage record must come back after the post-move `init --force`, and an adoption on a host that skipped the pre-move `init --force` stops before it changes anything. An adoption interrupted after `tasks rename --adopt` must finish on a rerun. Task 5: `test_second_host_refuses_without_its_pre_move_record`. Task 6: `test_the_cutover_verifies_and_the_second_host_adopts` and `test_the_second_host_finishes_an_interrupted_adoption`.
5. **`verify` on a registry that lost the renamed project's former root.** It refuses, naming the input that no longer answers `hq`. Task 2: `test_verify_refuses_when_the_old_root_no_longer_resolves`.

## Step records and the environment file

One step record per task, children of `tack-8b7a28`, created with this plan's draft. Their ids are in `docs/plans/2026-10-06-rename-to-hq-cutover.env.sh`, committed beside this plan. Every block in Tasks 1 to 8 starts:

```sh
. "$(tasks root tack-8b7a28 --pretty)/.worktrees/rename-hq-cutover/docs/plans/2026-10-06-rename-to-hq-cutover.env.sh" && cd "$WT"
```

Each task's first step starts its record. A code task closes its record in its code commit.

**Order.** Tasks 1 to 5 are independent and can run now. Task 6 runs the tools of Tasks 2, 4 and 5, and its preflight needs the live records committed and `tasks check` clean in tack, ops, lore and flows. On 2026-10-06 that waits on other sessions' untracked records and on ops's `ops-be8b06` shelved dependency, so Task 6, and Task 7 after it, wait on the user's call there. Task 7 merges Tasks 1 to 6. Task 8 waits on `flows-44890e` and `obs-ff4e76`. Tasks 9 to 11 run in one sitting each, in that order.

---

### Task 1: `session-episodes` follows ids written under a retired prefix

**Files:**
- Modify: `agents/bin/session-episodes` (`registry`, `Inputs`, `_Anchor`, `attribute`, `_collect_anchors`, `_confirm`, `build_episodes`, `cmd_extract`; new `resolve_ids`, `anchor_ids`)
- Modify: `agents/bin/test_session_episodes.py`
- Modify: `docs/specs/2026-09-19-session-logs-design.md` (§4 environment line, §4.1 `unregistered`)

**Interfaces:**
- Consumes: `tasks resolve --stdin --json` (tasks spec §3.2): one object, `results` in input order, each with `input`, `status`, and on `resolved` rows `prefix`, `root`, and `id` for an id.
- Produces:
  - `resolve_ids(names: list[str], env: dict) -> tuple[dict[str, Path], dict[str, str]]`: the roots by live prefix, and each resolved name's canonical form (an id for an id, a live prefix for a prefix).
  - `anchor_ids(sessions: list[Session]) -> list[str]`: every task id the sessions' anchors and transitions name, as written.
  - `Inputs` gains a last field, `canonical: dict[str, str]`, defaulting to empty.
  - `attribute(...)` gains `canonical: str | None = None`.

- [ ] **Step 1: Start the record**

```sh
. "$(tasks root tack-8b7a28 --pretty)/.worktrees/rename-hq-cutover/docs/plans/2026-10-06-rename-to-hq-cutover.env.sh" && cd "$WT" && tasks start "$STEP1" >/dev/null && echo started
```

- [ ] **Step 2: Write the failing tests**

In `agents/bin/test_session_episodes.py`, give `inputs()` a `canonical` keyword:

```python
def inputs(tmp_path, sessions, roots, now=ms(60) + 10 * 60 * 1000 + 1, labels=None, anchors=None, window_min=10,
           canonical=None):
    return se.Inputs(sessions, roots, labels or {}, anchors or {}, now, window_min * 60 * 1000, None, None,
                     canonical or {})
```

Give `cli_env()` an `aliases` keyword:

```python
def cli_env(tmp_path, roots, aliases=None):
    cfg = tmp_path / "cfg" / "tasks"
    cfg.mkdir(parents=True, exist_ok=True)
    text = "[projects]\n" + "".join(f'{k} = "{v}"\n' for k, v in roots.items())
    if aliases:
        text += "[aliases]\n" + "".join(f'{k} = "{v}"\n' for k, v in aliases.items())
    (cfg / "projects.toml").write_text(text)
    return {"XDG_CONFIG_HOME": str(tmp_path / "cfg"), "SESSION_LOGS_CLAUDE": str(tmp_path / "claude"),
            "SESSION_LOGS_CODEX": str(tmp_path / "codex"), "HOME": str(tmp_path)}
```

Delete `test_registry_reads_projects_toml`; `registry()` goes in Step 4. Append:

```python
# --- ids under a retired prefix (docs/specs/2026-10-06-rename-to-hq-design.md §3.5) -----

ALIAS = {"tack-000001": "hq-000001"}


def start_js(task_id):
    return f'text(await tools.exec_command({{cmd:"tasks start {task_id}"}}));'


def renamed_project(tmp_path, notes=()):
    root = git_repo(tmp_path / "proj-hq")
    task_file(root, list(notes), task_id="hq-000001")
    return {"hq": root}


def test_a_start_written_under_a_retired_prefix_is_an_episode_of_the_canonical_task(tmp_path):
    # After the rename, `tasks start tack-…` prints the canonical id.
    s = codex_story(tmp_path, start_cmd=start_js("tack-000001"), start_out='{"id":"hq-000001","warnings":[]}\n')
    eps, cands, summary = se.build_episodes(inputs(tmp_path, [s], renamed_project(tmp_path), canonical=ALIAS))
    assert cands == [] and summary["unregistered"] == 0 and len(eps) == 1
    assert eps[0]["task_id"] == "hq-000001" and eps[0]["anchor_source"] == "result"
    assert eps[0]["id"] == se.episode_id("codex", "c1", "tack-000001")


def test_a_start_from_before_the_rename_keeps_its_episode_id_and_finds_the_renamed_record(tmp_path):
    s = codex_story(tmp_path, start_cmd=start_js("tack-000001"), start_out='{"id":"tack-000001","warnings":[]}\n')
    eps, _, summary = se.build_episodes(inputs(tmp_path, [s], renamed_project(tmp_path), canonical=ALIAS))
    assert summary["unregistered"] == 0 and len(eps) == 1
    assert eps[0]["task_id"] == "hq-000001" and eps[0]["join_class"] == "inferred"
    assert eps[0]["id"] == se.episode_id("codex", "c1", "tack-000001")


def test_without_resolution_a_retired_prefix_counts_unregistered(tmp_path):
    s = codex_story(tmp_path, start_cmd=start_js("tack-000001"), start_out='{"id":"tack-000001","warnings":[]}\n')
    eps, _, summary = se.build_episodes(inputs(tmp_path, [s], renamed_project(tmp_path)))
    assert eps == [] and summary["unregistered"] == 1


def test_a_close_written_after_the_rename_closes_a_start_written_before(tmp_path):
    extra = [x_event("task_started", 100, "t2"), x_user("finish it", 100),
             x_custom("c2", 'text(await tools.exec_command({cmd:"tasks done hq-000001 landed"}));', 120),
             x_custom_out("c2", '{"id":"hq-000001","warnings":[]}\n', 130), x_event("task_complete", 131, "t2")]
    s = codex_story(tmp_path, start_cmd=start_js("tack-000001"), start_out='{"id":"tack-000001","warnings":[]}\n',
                    extra=extra, next_text=None)
    eps, _, _ = se.build_episodes(inputs(tmp_path, [s], renamed_project(tmp_path), canonical=ALIAS))
    assert len(eps) == 1 and eps[0]["task_id"] == "hq-000001"
    assert eps[0]["closed_at"] == ms(130) and eps[0]["closure_source"] == "transcript"


def test_anchor_ids_names_the_start_and_the_close(tmp_path):
    extra = [x_custom("c2", 'text(await tools.exec_command({cmd:"tasks done hq-000001 landed"}));', 120),
             x_custom_out("c2", '{"id":"hq-000001","warnings":[]}\n', 130)]
    s = codex_story(tmp_path, start_cmd=start_js("tack-000001"), start_out='{"id":"tack-000001","warnings":[]}\n',
                    extra=extra, next_text=None)
    assert se.anchor_ids([s]) == ["hq-000001", "tack-000001"]


def test_resolve_ids_follows_an_alias_through_tasks_resolve(tmp_path):
    root = git_repo(tmp_path / "proj-hq")
    env = cli_env(tmp_path, {"hq": root}, aliases={"tack": "hq"})
    roots, canonical = se.resolve_ids(["tack-000001", "hq-000002", "tack", "zz-000003"], env)
    assert roots == {"hq": root}
    assert canonical == {"tack-000001": "hq-000001", "hq-000002": "hq-000002", "tack": "hq"}


def test_extract_follows_an_alias_end_to_end(tmp_path):
    codex_story(tmp_path, start_cmd=start_js("tack-000001"), start_out='{"id":"hq-000001","warnings":[]}\n')
    out = tmp_path / "ep" / "episodes.jsonl"
    env = cli_env(tmp_path, renamed_project(tmp_path), aliases={"tack": "hq"})
    code, _, stderr = run_cli(["extract", "--out", str(out)], env)
    assert code == 0 and json.loads(stderr)["unregistered"] == 0
    assert [json.loads(l)["task_id"] for l in out.read_text().splitlines()] == ["hq-000001"]


def test_extract_project_accepts_a_retired_prefix(tmp_path):
    codex_story(tmp_path, start_cmd=start_js("tack-000001"), start_out='{"id":"hq-000001","warnings":[]}\n')
    out = tmp_path / "episodes.jsonl"
    env = cli_env(tmp_path, renamed_project(tmp_path), aliases={"tack": "hq"})
    assert run_cli(["extract", "--project", "tack", "--out", str(out)], env)[0] == 0
    assert len(out.read_text().splitlines()) == 1


def test_extract_refuses_an_unregistered_project(tmp_path):
    codex_story(tmp_path)
    env = cli_env(tmp_path, project(tmp_path))
    # main() turns a SystemExit carrying a message into exit 2 with the message on stderr.
    code, _, err = run_cli(["extract", "--project", "zz", "--out", str(tmp_path / "e.jsonl")], env)
    assert code == 2 and "--project zz is not a registered prefix" in err
```

- [ ] **Step 3: Run them to see them fail**

Run: `python3 -m pytest agents/bin/test_session_episodes.py -q -k "retired or alias or anchor_ids or resolve_ids or unregistered_project or the_rename"`

Expected: FAIL.
- The `build_episodes` tests fail with `TypeError`: `Inputs` takes no ninth argument. That includes `test_without_resolution_a_retired_prefix_counts_unregistered`, because `inputs()` now passes `canonical`.
- `resolve_ids` and `anchor_ids` do not exist (`AttributeError`).
- The three extract tests fail on their assertions, because the present `registry()` reads no aliases. The prefix `tack` is unregistered, so there is no episode, and `--project zz` exits 0 with nothing.

- [ ] **Step 4: Implement**

In `agents/bin/session-episodes`:

Replace `registry(env)` with:

```python
def resolve_ids(names: list[str], env: dict) -> tuple[dict[str, Path], dict[str, str]]:
    """Ask `tasks resolve` once about every id and prefix: the root of each project they
    resolve to, by live prefix, and each name's canonical form (an id, or a live prefix).
    An id written under a retired prefix follows its alias (tasks
    docs/specs/2026-10-06-project-resolution-design.md §3). A name that does not resolve
    is left out, so its anchor counts as unregistered."""
    if not names:
        return {}, {}
    try:
        result = subprocess.run(["tasks", "resolve", "--stdin", "--json"], input="".join(f"{n}\n" for n in names),
                                capture_output=True, text=True, env={"PATH": os.environ.get("PATH", ""), **env})
    except FileNotFoundError:
        raise SystemExit("session-episodes: the tasks CLI is not on PATH")
    if result.returncode != 0:
        raise SystemExit(f"session-episodes: tasks resolve failed: {(result.stderr or result.stdout).strip()}")
    roots: dict[str, Path] = {}
    canonical: dict[str, str] = {}
    for row in json.loads(result.stdout)["results"]:
        if row["status"] == "resolved":
            roots[row["prefix"]] = Path(row["root"])
            canonical[row["input"]] = row.get("id", row["prefix"])
    return roots, canonical
```

In `Inputs`, add as the last field:

```python
    canonical: dict[str, str] = field(default_factory=dict)  # an id as written -> its canonical id (resolve_ids)
```

Replace `_Anchor` with:

```python
@dataclass
class _Anchor:
    task_id: str  # canonical: the record read and the episode's task_id
    call_id: str
    holders: list[tuple[Session, int]] = field(default_factory=list)
    nested: bool = False  # the start text sits only in executable heredoc/-c text: review only
    written: str = ""  # the id as the session wrote it; the episode id hashes it, so a review survives a rename
```

Replace `attribute` with:

```python
def attribute(commands: tuple[str, ...], result_text: str, task_id: str, subcommand: str = "start",
              canonical: str | None = None) -> str:
    """Does this call's output prove that its `tasks <subcommand> <task_id>` ran? (§4.2)
    confirmed | outside-grammar | no-id-line | error-output. `canonical` is the id tasks
    prints for an id written under a retired prefix; an id line naming either confirms."""
    if has_error_line(result_text):
        return "error-output"
    if len(commands) != 1:
        return "outside-grammar"  # several literals share one output
    invocation = single_invocation(commands[0])
    if invocation is None:
        return "outside-grammar"
    if invocation.subcommand != subcommand or invocation.task_id != task_id:
        return "outside-grammar"
    named = {task_id, canonical or task_id}
    return "confirmed" if sum(id_lines(result_text, t, invocation.pretty) for t in named) >= 1 else "no-id-line"
```

In `_collect_anchors`:
- Add a line to the docstring: `An id written under a retired prefix joins its canonical id's anchors and transitions; each anchor keeps the id as written.`
- Add `canon = inputs.canonical.get` as its first statement.
- Replace the body of the loop over `e.commands` and the unsupported-wrapper branch with:

```python
            if e.unsupported and not any(start_candidates(c) for c in e.commands):
                result = _result_for(s, i)
                named = ids_in_result(result.text) if result is not None else []
                if not named:
                    summary["unsupported_unknown_task"] += 1
                for task_id in named:
                    key = (s.harness, e.call_id, canon(task_id, task_id))
                    anchors.setdefault(key, _Anchor(key[2], e.call_id, written=task_id)).holders.append((s, i))
            for c in e.commands:
                for task_id in start_candidates(c):
                    key = (s.harness, e.call_id, canon(task_id, task_id))
                    anchors.setdefault(key, _Anchor(key[2], e.call_id, written=task_id)).holders.append((s, i))
                for task_id in nested_start_candidates(c):
                    key = (s.harness, e.call_id, canon(task_id, task_id))
                    anchors.setdefault(key, _Anchor(key[2], e.call_id, nested=True, written=task_id)).holders.append((s, i))
                for sub, task_id in transitions_in(c):
                    result = _result_for(s, i)
                    readable = attributable_commands(e)
                    if result is not None and readable is not None and \
                            attribute(readable, result.text, task_id, sub, canon(task_id, task_id)) == "confirmed":
                        # a fork copies the call under the same id; keep one per (call_id, times)
                        transitions.setdefault((canon(task_id, task_id), sub), {}).setdefault(
                            (e.at_ms, result.at_ms, e.call_id), (s, e, result))
```

In `_confirm`, replace these three lines:
- `elif call.unsupported and not any(anchor.task_id in start_candidates(c) for c in call.commands):` becomes `elif call.unsupported and not any(anchor.written in start_candidates(c) for c in call.commands):`.
- `verdict = attribute(readable, text, anchor.task_id) if readable is not None else "outside-grammar"` becomes `verdict = attribute(readable, text, anchor.written, canonical=anchor.task_id) if readable is not None else "outside-grammar"`.
- `eid = episode_id(session.harness, anchor.call_id, anchor.task_id)` becomes `eid = episode_id(session.harness, anchor.call_id, anchor.written)`.

In `build_episodes`, `eid = episode_id(harness, call_id, task_id)` becomes `eid = episode_id(harness, call_id, anchor.written)`.

After `build_episodes`, add:

```python
def anchor_ids(sessions: list[Session]) -> list[str]:
    """Every task id these sessions' anchors and transitions name, as written: what
    extract asks tasks resolve about before it builds the episodes."""
    probe = Inputs(sessions, {}, {}, {}, 0, 0)
    anchors, transitions = _collect_anchors(probe, _new_summary(probe))
    return sorted({a.written for a in anchors.values()} | {task_id for task_id, _ in transitions})
```

Replace `cmd_extract` with:

```python
def cmd_extract(args, env: dict) -> int:
    out = Path(args.out)
    labels_path = Path(args.labels) if args.labels else sidecar(out, "labels")
    anchors_path = Path(args.anchors) if args.anchors else sidecar(out, "anchors")
    claude_root, codex_root = _roots(env)
    now = int(dt.datetime.now(dt.timezone.utc).timestamp() * 1000)
    since = now - args.since * 86_400_000 if args.since is not None else None
    sessions = scan_stores(claude_root, codex_root, since)
    roots, canonical = resolve_ids(anchor_ids(sessions) + ([args.project] if args.project else []), env)
    project = canonical.get(args.project) if args.project else None
    if args.project and project not in roots:
        raise SystemExit(f"session-episodes: --project {args.project} is not a registered prefix")
    for prefix, root in roots.items():
        if project and prefix != project:
            continue
        if not (root / "tasks").is_dir():
            raise SystemExit(f"session-episodes: registered project {prefix} has no tasks/ under {root}")
    inputs = Inputs(sessions, roots, read_jsonl_map(labels_path), read_jsonl_map(anchors_path),
                    now, args.window_minutes * 60_000, since, project, canonical)
    episodes, candidates, summary = build_episodes(inputs)
    summary["roots"] = {"claude": str(claude_root), "codex": str(codex_root)}
    summary["missing_roots"] = [str(r) for r in (claude_root, codex_root) if not r.is_dir()]
    write_jsonl(out, episodes)
    write_jsonl(sidecar(out, "candidates"), candidates)
    print(json.dumps(summary, sort_keys=True), file=sys.stderr)
    return 0
```

If `tomllib` has no other use left (`grep -n tomllib agents/bin/session-episodes`), remove its import.

In `docs/specs/2026-09-19-session-logs-design.md`:
- §4: replace these lines, as wrapped in the file:

  ```
  and `SESSION_LOGS_CODEX` override the store roots (tests use them); the tasks
  registry `~/.config/tasks/projects.toml` supplies project roots, as `obs-index`
  and obs `stores.py` do.
  ```

  with:

  ```
  and `SESSION_LOGS_CODEX` override the store roots (tests use them); the tasks
  resolver (`tasks resolve --stdin`, one call per run) supplies project roots and
  follows an id written under a retired prefix to its canonical id. (Revised
  2026-10-06 for the rename to hq: an episode carries the canonical id, and its
  episode id still hashes the id as written, so a review keeps its episode.)
  ```

- §4.1: replace these lines:

  ```
  - `unregistered`: an anchor whose task id's prefix is not a registered
    project. Per anchor.
  ```

  with the text below. The old text continues on its last line (` Ownership is the task's, …`), which stays; the replacement is that text without a final newline:

  ```
  - `unregistered`: an anchor whose task id `tasks resolve` does not resolve.
    Per anchor.
  ```

- [ ] **Step 5: Run the tests**

Run: `python3 -m pytest agents/bin/test_session_episodes.py -q`

Expected: every test passes.

- [ ] **Step 6: Full suite and commit**

```sh
. "$(tasks root tack-8b7a28 --pretty)/.worktrees/rename-hq-cutover/docs/plans/2026-10-06-rename-to-hq-cutover.env.sh" && cd "$WT" && t just test && \
tasks done "$STEP1" "session-episodes resolves its anchors' ids through tasks resolve: an id under a retired prefix joins its canonical task" >/dev/null && \
git commit -q -m "feat(session-episodes): follow ids written under a retired prefix (tack-8b7a28)" -- agents/bin/session-episodes agents/bin/test_session_episodes.py docs/specs/2026-09-19-session-logs-design.md "tasks/$STEP1.md" && git log --oneline -1
```

---

### Task 2: `verify` asks the resolver, rollback knows attachments, and the preparation's deferred minors

**Files:**
- Modify: `tools/rename-cutover` (`save`, `preconditions`, `validate_leftovers`, `rollback`, `verify`; new `reset_all`, `sample_task`, `leftover_original`, `remove_leftovers`)
- Modify: `tools/test_rename_cutover.py`

**Interfaces:**
- Consumes: `tasks resolve --json <inputs>`.
- Produces:
  - `reset_all(resets: list[tuple[Path, str, str]], snap: Path) -> None`: every patch is written before any reset.
  - `sample_task(new_root: Path, new: str) -> str`: the hex of one `<new>-<hex>.md`, or `Stop`.
  - `verify` also refuses when the old id, the old root, or a path under the old storage does not resolve to the new prefix.
  - `save` refuses an existing snapshot path and a linked tasks config or state directory, with `Stop`.
  - `preconditions` refuses while `tasks check` prints anything in the checkout or a repository: `verify` and `rollback` both treat any output as findings, so a warning that predates the cutover would fail verification and then the rollback's own final check.
  - `leftover_original(path, old, new) -> str | None` and `remove_leftovers(checkout, leftovers)`. `tasks rename` also renames a task's attachments folder, `tasks/files/<old>-<hex>/`. After rollback's reset the renamed folder is an untracked leftover, accepted when its original exists at the saved head, deleted, and its emptied directories removed.

- [ ] **Step 1: Start the record**

```sh
. "$(tasks root tack-8b7a28 --pretty)/.worktrees/rename-hq-cutover/docs/plans/2026-10-06-rename-to-hq-cutover.env.sh" && cd "$WT" && tasks start "$STEP2" >/dev/null && echo started
```

- [ ] **Step 2: Write the failing tests**

Append to `tools/test_rename_cutover.py`:

```python
# --- the resolver and the preparation's deferred minors --------------------------


def drop_former(registry, prefix):
    """The registry without the renamed project's former roots, as if never recorded."""
    kept, skipping = [], False
    for line in registry.read_text().splitlines(keepends=True):
        if line.startswith("["):
            skipping = line.strip() == f"[[locations.{prefix}.former]]"
        if not skipping:
            kept.append(line)
    registry.write_text("".join(kept))


def test_verify_asks_the_resolver_about_the_old_id_root_and_storage(box):
    box.save()
    box.forward()
    box.cutover("verify", "--snapshot", box.snapshot)
    rows = json.loads(box.run("tasks", "resolve", "--json", str(box.checkout),
                              str(box.sync.parent / ".dropbox-work" / "ai" / ".worktrees" / "x")).stdout)["results"]
    assert [(r["status"], r["prefix"], r["via"]) for r in rows] == [
        ("resolved", "tack", "former_root"), ("resolved", "tack", "former_storage")]


def test_verify_refuses_when_the_old_root_no_longer_resolves(box):
    box.save()
    box.forward()
    registry = box.tmp / "cfg" / "tasks" / "projects.toml"
    assert "[[locations.tack.former]]" in registry.read_text()
    drop_former(registry, "tack")
    result = box.cutover("verify", "--snapshot", box.snapshot, check=False)
    assert result.returncode == 1
    assert "tasks resolve does not answer tack for" in result.stderr and str(box.checkout) in result.stderr


def test_save_refuses_an_existing_snapshot_without_a_traceback(box):
    box.snapshot.mkdir()
    result = box.save(check=False)
    assert result.returncode == 1
    assert "already exists" in result.stderr and "Traceback" not in result.stderr


@pytest.mark.parametrize("which", ["cfg", "state"])
def test_save_refuses_a_linked_tasks_directory(box, which):
    live = box.tmp / which / "tasks"
    real = box.tmp / f"{which}-real"
    live.rename(real)
    live.symlink_to(real)
    result = box.save(check=False)
    assert result.returncode == 1 and "must be a real directory" in result.stderr
    assert not box.snapshot.exists()


def test_save_refuses_a_kept_path_that_is_a_link(hq):
    # The behaviour exists (kept_paths); the preparation's review asked for its test.
    trust = hq.checkout / "local" / "codex" / "trust.toml"
    real = hq.tmp / "elsewhere.toml"
    trust.rename(real)
    trust.symlink_to(real)
    result = hq.save(check=False)
    assert result.returncode == 1 and "no regular file" in result.stderr
    assert not hq.snapshot.exists()


def test_sample_task_stops_without_a_task_under_the_new_prefix(tmp_path):
    cutover = load_cutover()
    (tmp_path / "tasks").mkdir()
    (tmp_path / "tasks" / "ai-123456.md").write_text("x\n")
    with pytest.raises(cutover.Stop, match=r"no tack-\*\.md task"):
        cutover.sample_task(tmp_path, "tack")
    (tmp_path / "tasks" / "tack-abcdef.md").write_text("x\n")
    assert cutover.sample_task(tmp_path, "tack") == "abcdef"


def test_reset_all_writes_every_patch_before_any_reset(tmp_path, monkeypatch):
    cutover = load_cutover()
    calls = []

    def patch(root, head, snap, label):
        if label == "lore":
            raise cutover.Stop("disk full")
        calls.append(("patch", label))

    monkeypatch.setattr(cutover, "save_reset_patch", patch)
    monkeypatch.setattr(cutover, "run", lambda *cmd, cwd=None: calls.append(("run", *map(str, cmd))))
    resets = [(tmp_path / "a", "h1", "checkout"), (tmp_path / "b", "h2", "lore")]
    with pytest.raises(cutover.Stop, match="disk full"):
        cutover.reset_all(resets, tmp_path)
    assert calls == [("patch", "checkout")]


def test_save_refuses_findings_from_tasks_check(box2):
    lore = box2.repos[1]
    a = task_id(box2.run("tasks", "add", "parked idea", "--process", "direct", cwd=lore).stdout)
    b = task_id(box2.run("tasks", "add", "waits on it", "--process", "direct", cwd=lore).stdout)
    box2.run("tasks", "dep", b, "--on", a, cwd=lore)
    box2.run("tasks", "shelve", a, "when it is needed", cwd=lore)
    box2.commit(lore, "a dependency on a shelved task")
    assert "shelved_dep" in box2.run("tasks", "check", cwd=lore).stdout
    result = box2.save(check=False)
    assert result.returncode == 1
    assert "tasks check reports findings" in result.stderr and str(lore) in result.stderr
    assert not box2.snapshot.exists()


def test_rollback_restores_a_renamed_attachments_folder(box):
    """`tasks rename` renames tasks/files/<old>-<hex>/ with its task. After the reset the
    renamed folder is an untracked leftover: removed, emptied folders and all."""
    hex_ = task_id(box.run("tasks", "add", "with files", "--process", "direct", cwd=box.checkout).stdout).split("-", 1)[1]
    source = box.tmp / "notes.txt"
    source.write_text("evidence\n")
    box.run("tasks", "attach", f"ai-{hex_}", source, cwd=box.checkout)
    assert (box.checkout / "tasks" / "files" / f"ai-{hex_}" / "notes.txt").is_file()
    box.commit(box.checkout, "a task with an attachment")
    before = box.fingerprint()
    box.save()
    box.forward()
    assert (box.new_root / "tasks" / "files" / f"tack-{hex_}" / "notes.txt").is_file()
    box.cutover("rollback", "--snapshot", box.snapshot)
    assert box.fingerprint() == before
    assert not (box.checkout / "tasks" / "files" / f"tack-{hex_}").exists()


def test_leftover_original_names_records_and_attachments_only():
    cutover = load_cutover()
    assert cutover.leftover_original("tasks/hq-abc123.md", "tack", "hq") == "tasks/tack-abc123.md"
    assert cutover.leftover_original("tasks/files/hq-abc123/a/b.py", "tack", "hq") == "tasks/files/tack-abc123/a/b.py"
    for path in ("tasks/x/hq-abc123.md", "tasks/files/hq-abc123", "tasks/files/ops-abc123/b.py", "notes/hq-abc123.md"):
        assert cutover.leftover_original(path, "tack", "hq") is None, path


def test_a_retargeted_repository_with_claims_is_a_precondition_message(box2):
    lore = box2.repos[1]
    tid = task_id(box2.run("tasks", "add", "orphaned claim", "--process", "direct", cwd=lore).stdout)
    box2.run("tasks", "start", tid, cwd=lore, env={**box2.env, "TASKS_SESSION": "ghost", "TASKS_SESSION_PID": "999999"})
    box2.commit(lore, "start under a dead session")
    assert "preconditions: a retargeted repository has claims" in box2.save(check=False).stderr
```

- [ ] **Step 3: Run them to see them fail**

Run: `uv run -q --with pytest pytest tools/test_rename_cutover.py -q -k "resolver or no_longer_resolves or existing_snapshot or linked_tasks or kept_path_that_is_a_link or sample_task or reset_all or precondition_message or findings_from_tasks_check or attachments or leftover_original"`

Expected:
- **Fail:**
  - `test_verify_refuses_when_the_old_root_no_longer_resolves`, because verify passes;
  - `test_save_refuses_an_existing_snapshot_without_a_traceback`, which shows a `FileExistsError` traceback;
  - both `test_save_refuses_a_linked_tasks_directory` cases, because save succeeds;
  - `test_sample_task_…` and `test_reset_all_…`, because the names do not exist;
  - `test_a_retargeted_repository_…`, because the message starts `save:`;
  - `test_save_refuses_findings_from_tasks_check`, because save succeeds;
  - `test_rollback_restores_a_renamed_attachments_folder`, which stops with `leftovers: tasks/files/tack-<hex>/notes.txt is not a rename leftover`;
  - `test_leftover_original_…`, because the name does not exist.
- **Pass:** `test_verify_asks_the_resolver_…`, since `tasks` records the history already, and `test_save_refuses_a_kept_path_that_is_a_link`, since the behaviour exists. Both are pins.

- [ ] **Step 4: Implement**

In `save`, make the first statements after `checkout, snap = …`:

```python
    if snap.exists():
        raise Stop(f"save: snapshot {snap} already exists")
```

After the line that sets `config, state`, add:

```python
    for path in (config, state):
        if path.is_symlink() or not path.is_dir():
            raise Stop(f"save: {path} must be a real directory: rollback replaces it whole")
```

In `preconditions`, the message `f"save: a retargeted repository has claims (live or dead): …"` becomes `f"preconditions: a retargeted repository has claims (live or dead): …"`.

Add after `save_reset_patch`:

```python
def reset_all(resets, snap):
    """Keep every repository's discarded changes as a patch before resetting any: a patch
    that cannot be written stops rollback before the first reset, not between two."""
    for root, head, label in resets:
        save_reset_patch(root, head, snap, label)
    for root, head, _ in resets:
        run("git", "-C", root, "reset", "-q", "--hard", head)
```

In `rollback`, replace this loop:

```python
    for root, head, label in resets:
        save_reset_patch(root, head, snap, label)
        run("git", "-C", root, "reset", "-q", "--hard", head)
```

with `reset_all(resets, snap)`.

Add before `verify`:

```python
def sample_task(new_root, new):
    """One task under the new prefix, whose old-prefix id verify resolves through the alias."""
    found = next((p.stem for p in (Path(new_root) / "tasks").glob(f"{new}-*.md")), None)
    if found is None:
        raise Stop(f"verify: no {new}-*.md task under {Path(new_root) / 'tasks'} to resolve through the alias")
    return found.split("-", 1)[1]
```

In `verify`, replace these two lines:

```python
    any_new = next(p.stem for p in (new_root / "tasks").glob(f"{new}-*.md"))
    run("tasks", "show", f"{old}-{any_new.split('-', 1)[1]}", cwd=new_root)
```

with:

```python
    hex_ = sample_task(new_root, new)
    run("tasks", "show", f"{old}-{hex_}", cwd=new_root)
    # The registry's location history: the old id, the old root and a path under the old
    # storage all answer the new prefix (tasks docs/specs/2026-10-06-project-resolution-design.md §4).
    probes = [f"{old}-{hex_}", meta["checkout"]["root"]]
    if meta["storage_old"]:
        probes.append(str(Path(meta["storage_old"]) / "a-worktree"))
    rows = json.loads(run("tasks", "resolve", "--json", *probes))["results"]
    wrong = [f"{r['input']} ({r['status']} {r.get('prefix', '')})".replace(" )", ")") for r in rows
             if r["status"] != "resolved" or r.get("prefix") != new]
    if wrong:
        raise Stop(f"verify: tasks resolve does not answer {new} for " + ", ".join(wrong))
```

In `preconditions`, after the loop that refuses an unclean tree, add:

```python
    for root in (checkout, *repos):
        if run("tasks", "check", cwd=root).strip():
            raise Stop(f"preconditions: tasks check reports findings in {root}; verify and rollback "
                       f"both require it clean, so resolve them first")
```

Replace the loop in `validate_leftovers` that checks each untracked path with:

```python
    for path in untracked:
        original = leftover_original(path, old, new)
        if original is None:
            raise Stop(f"leftovers: {path} is not a rename leftover")
        check = subprocess.run(["git", "-C", str(checkout), "cat-file", "-e", f"{head}:{original}"],
                               capture_output=True)
        if check.returncode != 0:
            raise Stop(f"leftovers: {path} has no restored original {original}")
```

and add before `validate_leftovers`:

```python
def leftover_original(path, old, new):
    """The pre-rename path a rename leftover replaces, or None. `tasks rename` writes
    tasks/<new>-<hex>.md and moves the task's attachments folder to tasks/files/<new>-<hex>/."""
    parts = Path(path).parts
    if len(parts) == 2 and parts[0] == "tasks" and parts[1].startswith(f"{new}-"):
        return f"tasks/{old}-{parts[1][len(new) + 1:]}"
    if len(parts) >= 4 and parts[:2] == ("tasks", "files") and parts[2].startswith(f"{new}-"):
        return "/".join(("tasks", "files", f"{old}-{parts[2][len(new) + 1:]}", *parts[3:]))
    return None


def remove_leftovers(checkout, leftovers):
    """Delete each validated leftover, then the attachment folders that emptied: an empty
    tasks/files/<new>-<hex>/ would be an orphan to rollback's final tasks check."""
    files = checkout / "tasks" / "files"
    for path in leftovers:
        (checkout / path).unlink()
    for path in leftovers:
        folder = (checkout / path).parent
        while files in folder.parents and folder.is_dir() and not any(folder.iterdir()):
            folder.rmdir()
            folder = folder.parent
```

In `rollback`, replace `for path in leftovers:` / `(checkout / path).unlink()` with `remove_leftovers(checkout, leftovers)`.

- [ ] **Step 5: Run the tests**

Run: `uv run -q --with pytest pytest tools/test_rename_cutover.py -q`

Expected: every test passes, including the 71 already there.

- [ ] **Step 6: Full suite and commit**

```sh
. "$(tasks root tack-8b7a28 --pretty)/.worktrees/rename-hq-cutover/docs/plans/2026-10-06-rename-to-hq-cutover.env.sh" && cd "$WT" && t just test && \
tasks done "$STEP2" "verify asks tasks resolve about the old id, root and storage; save refuses findings from tasks check, an existing snapshot and linked tasks directories; rollback restores renamed attachment folders and writes every patch before any reset" >/dev/null && \
git commit -q -m "feat(rename-cutover): verify the location history; the preparation's deferred minors (tack-8b7a28)" -- tools/rename-cutover tools/test_rename_cutover.py "tasks/$STEP2.md" && git log --oneline -1
```

---

### Task 3: The units test is an allowlist, and the link run reaches the package

**Files:**
- Modify: `tools/test_session_archive_units.py`

**Interfaces:**
- Produces: `paths_off_the_allowlist(text: str) -> list[str]`, a test helper.

- [ ] **Step 1: Start the record**

```sh
. "$(tasks root tack-8b7a28 --pretty)/.worktrees/rename-hq-cutover/docs/plans/2026-10-06-rename-to-hq-cutover.env.sh" && cd "$WT" && tasks start "$STEP3" >/dev/null && echo started
```

- [ ] **Step 2: Write the failing tests**

In `tools/test_session_archive_units.py`, delete `test_no_unit_names_the_checkout` and append:

```python
@pytest.mark.parametrize("line", [
    "ExecStart=/usr/bin/python3 %h/d/tack/tools/session-archive capture",
    "ExecStart=/usr/bin/python3 %h/hq/tools/session-archive capture",
    "ExecStart=/usr/bin/python3 %h/Dropbox/hq/tools/session-archive capture",
    "ExecStart=/home/someone/bin/session-archive capture",
    "Documentation=file://%h/d/tack/docs/specs/x.md",
])
def test_the_allowlist_catches_a_unit_that_names_a_checkout(line):
    assert paths_off_the_allowlist(line)


def test_the_allowlist_passes_the_linked_tool_and_path():
    assert paths_off_the_allowlist("ExecStart=/usr/bin/python3 %h/.local/bin/session-archive capture\n"
                                   "Environment=PATH=%h/.local/bin:/usr/local/bin:/usr/bin:/bin\n"
                                   "# Design: docs/specs/x.md, in the repository that holds this unit.\n") == []


def test_every_path_a_unit_names_is_on_the_allowlist():
    for path in sorted(UNITS.iterdir()):
        assert paths_off_the_allowlist(path.read_text()) == [], path.name
```

Replace `test_the_tool_runs_through_a_link_from_any_directory` with:

```python
def test_the_tool_runs_through_a_link_from_any_directory(tmp_path):
    link = tmp_path / "bin" / "session-archive"
    link.parent.mkdir()
    link.symlink_to(TOOL)
    (tmp_path / "home").mkdir()
    result = subprocess.run(["/usr/bin/python3", str(link), "status"], cwd=tmp_path, text=True,
                            capture_output=True, env={"PATH": "/usr/bin:/bin", "HOME": str(tmp_path / "home")})
    # Past argument parsing and into the package: it reads this host's configuration.
    assert result.returncode == 2, result.stderr
    assert "is not configured on this host" in result.stderr
```

- [ ] **Step 3: Run them to see them fail**

Run: `uv run -q --with pytest pytest tools/test_session_archive_units.py -q`

Expected: the three allowlist tests FAIL with `NameError: name 'paths_off_the_allowlist' is not defined`. The link-run test passes against the present tool. It replaces a `--help` run, and it pins the behaviour the units rely on: the tool, run through a link from elsewhere, finds its package.

- [ ] **Step 4: Implement the helper**

Add `import re` to the imports, and after `unit()`:

```python
ALLOWED = ("%h/.local/bin", "/usr/local/bin", "/usr/bin", "/bin")


def paths_off_the_allowlist(text):
    """Every path a unit names outside comments that is not under an allowed directory.
    A unit that names a checkout, by any spelling, stops working when the checkout moves
    (docs/specs/2026-10-06-rename-to-hq-design.md §3.1)."""
    off = []
    for line in text.splitlines():
        if line.startswith("#"):
            continue
        for token in re.split(r"[\s=:]+", line):
            if "/" in token and not any(token == a or token.startswith(a + "/") for a in ALLOWED):
                off.append(token)
    return off
```

Run: `uv run -q --with pytest pytest tools/test_session_archive_units.py -q`

Expected: every test passes.

- [ ] **Step 5: Full suite and commit**

```sh
. "$(tasks root tack-8b7a28 --pretty)/.worktrees/rename-hq-cutover/docs/plans/2026-10-06-rename-to-hq-cutover.env.sh" && cd "$WT" && t just test && \
tasks done "$STEP3" "units test is an allowlist; the link run reaches the package's configuration read" >/dev/null && \
git commit -q -m "test(session-archive): an allowlist for unit paths; the link run reaches the package (tack-8b7a28)" -- tools/test_session_archive_units.py "tasks/$STEP3.md" && git log --oneline -1
```

---
### Task 4: `quiesce-timers` pauses a window's timers and restores each exactly

**Files:**
- Create: `tools/quiesce-timers` (executable)
- Create: `tools/test_quiesce_timers.py`

**Interfaces:**
- Consumes: `systemctl --user` found on `PATH`. It uses `is-enabled`, `is-active`, `show -p Unit --value`, `stop` and `start`.
- Produces: `quiesce-timers record|stop|wait|restore --state FILE`. Task 9 and Task 10 run it from a copy in `$RUN/bin`, because the checkout moves.

- [ ] **Step 1: Start the record**

```sh
. "$(tasks root tack-8b7a28 --pretty)/.worktrees/rename-hq-cutover/docs/plans/2026-10-06-rename-to-hq-cutover.env.sh" && cd "$WT" && tasks start "$STEP4" >/dev/null && echo started
```

- [ ] **Step 2: Write the failing tests**

Create `tools/test_quiesce_timers.py`:

```python
"""quiesce-timers against a fake systemctl that keeps unit state in a JSON file."""
import json
import os
import subprocess
from pathlib import Path

import pytest

TOOL = Path(__file__).resolve().parent / "quiesce-timers"

FAKE = r'''#!/usr/bin/env python3
import json, os, sys
path = os.environ["FAKE_SYSTEMD"]
state = json.load(open(path))
args = sys.argv[1:]
assert args[0] == "--user", args
verb, unit = args[1], args[-1]
state["log"].append(" ".join(args[1:]))
units = state["units"]
code = 0
if unit not in units:
    print(f"Failed to get unit file state for {unit}: No such file or directory", file=sys.stderr)
    code = 1
else:
    u = units[unit]
    if verb == "is-enabled":
        print(u["enabled"])
        code = 0 if u["enabled"] == "enabled" else 1
    elif verb == "is-active":
        if u.get("runs_for", 0) > 0:
            u["runs_for"] -= 1
            print("active")
        else:
            u["active"] = "inactive" if "runs_for" in u else u["active"]
            print(u["active"])
            code = 0 if u["active"] == "active" else 3
    elif verb == "show":
        print(u["unit"])
    elif verb in ("start", "stop"):
        u["active"] = "active" if verb == "start" else "inactive"
    else:
        code = 1
json.dump(state, open(path, "w"))
sys.exit(code)
'''


@pytest.fixture
def systemd(tmp_path):
    bin_ = tmp_path / "bin"
    bin_.mkdir()
    (bin_ / "systemctl").write_text(FAKE)
    (bin_ / "systemctl").chmod(0o755)
    path = tmp_path / "units.json"
    units = {
        "obs-index.timer": {"enabled": "enabled", "active": "active", "unit": "obs-index.service"},
        "obs-index.service": {"enabled": "static", "active": "inactive", "unit": ""},
        "prune.timer": {"enabled": "linked", "active": "inactive", "unit": "prune.service"},
        "prune.service": {"enabled": "linked", "active": "inactive", "unit": ""},
    }
    path.write_text(json.dumps({"units": units, "log": []}))

    class Systemd:
        state_file = tmp_path / "window" / "timers.json"

        def run(self, *args, check=True):
            env = {**os.environ, "PATH": f"{bin_}:{os.environ['PATH']}", "FAKE_SYSTEMD": str(path)}
            result = subprocess.run([str(TOOL), *args], text=True, capture_output=True, env=env)
            if check and result.returncode != 0:
                raise AssertionError(result.stdout + result.stderr)
            return result

        def units(self):
            return json.loads(path.read_text())["units"]

        def log(self):
            return json.loads(path.read_text())["log"]

        def set(self, unit, **fields):
            data = json.loads(path.read_text())
            data["units"][unit].update(fields)
            path.write_text(json.dumps(data))

    return Systemd()


def test_record_saves_each_timers_enablement_activity_and_service(systemd):
    systemd.run("record", "--state", systemd.state_file, "obs-index.timer", "prune.timer")
    assert json.loads(systemd.state_file.read_text())["timers"] == [
        {"timer": "obs-index.timer", "service": "obs-index.service", "enabled": "enabled", "active": "active"},
        {"timer": "prune.timer", "service": "prune.service", "enabled": "linked", "active": "inactive"},
    ]


def test_record_refuses_an_existing_record(systemd):
    systemd.state_file.parent.mkdir()
    systemd.state_file.write_text("{}")
    result = systemd.run("record", "--state", systemd.state_file, "obs-index.timer", check=False)
    assert result.returncode == 1 and "exists" in result.stderr
    assert systemd.state_file.read_text() == "{}"


def test_record_refuses_a_timer_systemd_does_not_know(systemd):
    result = systemd.run("record", "--state", systemd.state_file, "obs-index.timer", "gone.timer", check=False)
    assert result.returncode == 1 and "gone.timer" in result.stderr
    assert not systemd.state_file.exists()


def test_record_refuses_a_unit_that_is_not_a_timer(systemd):
    result = systemd.run("record", "--state", systemd.state_file, "obs-index.service", check=False)
    assert result.returncode == 1 and "not a timer" in result.stderr


def test_stop_stops_every_recorded_timer(systemd):
    systemd.run("record", "--state", systemd.state_file, "obs-index.timer", "prune.timer")
    systemd.run("stop", "--state", systemd.state_file)
    assert systemd.units()["obs-index.timer"]["active"] == "inactive"
    assert "stop obs-index.timer" in systemd.log() and "stop prune.timer" in systemd.log()


def test_wait_returns_once_a_running_service_finishes(systemd):
    systemd.set("obs-index.service", active="active", runs_for=2)
    systemd.run("record", "--state", systemd.state_file, "obs-index.timer")
    result = systemd.run("wait", "--state", systemd.state_file, "--timeout", "60", "--poll", "0")
    assert "waiting on obs-index.service" in result.stdout and "every service is inactive" in result.stdout
    assert not [line for line in systemd.log() if "obs-index.service" in line and line.split()[0] in ("stop", "kill")]


def test_wait_stops_at_the_timeout_and_kills_nothing(systemd):
    systemd.set("obs-index.service", active="active", runs_for=1000)
    systemd.run("record", "--state", systemd.state_file, "obs-index.timer")
    result = systemd.run("wait", "--state", systemd.state_file, "--timeout", "0", "--poll", "0", check=False)
    assert result.returncode == 1
    assert "obs-index.service" in result.stderr and "nothing was killed" in result.stderr
    assert not [line for line in systemd.log() if line.split()[0] in ("stop", "kill")]


def test_restore_returns_each_timer_to_its_record(systemd):
    systemd.run("record", "--state", systemd.state_file, "obs-index.timer", "prune.timer")
    systemd.run("stop", "--state", systemd.state_file)
    result = systemd.run("restore", "--state", systemd.state_file)
    units = systemd.units()
    assert units["obs-index.timer"]["active"] == "active" and units["prune.timer"]["active"] == "inactive"
    assert "start prune.timer" not in systemd.log()
    assert "every timer matches its record" in result.stdout


def test_restore_reports_a_timer_whose_enablement_changed(systemd):
    systemd.run("record", "--state", systemd.state_file, "obs-index.timer")
    systemd.run("stop", "--state", systemd.state_file)
    systemd.set("obs-index.timer", enabled="disabled")
    result = systemd.run("restore", "--state", systemd.state_file, check=False)
    assert result.returncode == 1
    assert "obs-index.timer is disabled, active; recorded enabled, active" in result.stderr
```

- [ ] **Step 3: Run them to see them fail**

Run: `uv run -q --with pytest pytest tools/test_quiesce_timers.py -q`

Expected: every test FAILS. The tool does not exist (`FileNotFoundError` from `subprocess.run`).

- [ ] **Step 4: Implement**

Create `tools/quiesce-timers`, executable (`chmod +x`):

```python
#!/usr/bin/env python3
"""Pause user timers for a window, and return each to exactly its recorded state.

quiesce-timers record  --state FILE TIMER...   save each timer's enablement, activity, service
quiesce-timers stop    --state FILE            stop every recorded timer
quiesce-timers wait    --state FILE [--timeout SECONDS] [--poll SECONDS]
                                               until every recorded timer's service is inactive
quiesce-timers restore --state FILE            start the timers recorded active, stop the rest,
                                               then check each matches its record

Stopping a timer does not stop a run its service already began. `wait` lets that run finish
and never kills it (docs/specs/2026-10-06-rename-to-hq-design.md §3.2 step 1). Only
`systemctl --user` is called, found on PATH, so a test supplies its own.
"""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path


class Stop(Exception):
    pass


def systemctl(*args):
    return subprocess.run(["systemctl", "--user", *args], text=True, capture_output=True)


def query(verb, unit):
    """is-enabled and is-active answer on stdout, and exit non-zero for a negative answer."""
    result = systemctl(verb, unit)
    answer = result.stdout.strip()
    if not answer:
        raise Stop(f"systemctl --user {verb} {unit}: {result.stderr.strip() or 'no answer'}")
    return answer


def service_of(timer):
    result = systemctl("show", "-p", "Unit", "--value", timer)
    unit = result.stdout.strip()
    if result.returncode != 0 or not unit:
        raise Stop(f"{timer}: no unit it activates ({result.stderr.strip()})")
    return unit


def load(path):
    return json.loads(Path(path).read_text())["timers"]


def record(args):
    state = Path(args.state)
    if state.exists():
        raise Stop(f"record: {state} exists; one record per window")
    timers = []
    for timer in args.timers:
        if not timer.endswith(".timer"):
            raise Stop(f"record: {timer} is not a timer")
        timers.append({"timer": timer, "service": service_of(timer),
                       "enabled": query("is-enabled", timer), "active": query("is-active", timer)})
    state.parent.mkdir(parents=True, exist_ok=True)
    state.write_text(json.dumps({"timers": timers}, indent=2) + "\n")
    for t in timers:
        print(f"{t['timer']}: {t['enabled']}, {t['active']} ({t['service']})")


def stop(args):
    for t in load(args.state):
        result = systemctl("stop", t["timer"])
        if result.returncode != 0:
            raise Stop(f"stop {t['timer']}: {result.stderr.strip()}")
        print(f"stopped {t['timer']}")


def wait(args):
    deadline = time.monotonic() + args.timeout
    while True:
        running = [t["service"] for t in load(args.state)
                   if query("is-active", t["service"]) not in ("inactive", "failed")]
        if not running:
            print("every service is inactive")
            return
        if time.monotonic() >= deadline:
            raise Stop("wait: still running after the timeout: " + ", ".join(running) + "; nothing was killed")
        print("waiting on " + ", ".join(running), flush=True)
        time.sleep(args.poll)


def restore(args):
    timers = load(args.state)
    for t in timers:
        verb = "start" if t["active"] == "active" else "stop"
        result = systemctl(verb, t["timer"])
        if result.returncode != 0:
            raise Stop(f"{verb} {t['timer']}: {result.stderr.strip()}")
    wrong = []
    for t in timers:
        now = (query("is-enabled", t["timer"]), query("is-active", t["timer"]))
        if now != (t["enabled"], t["active"]):
            wrong.append(f"{t['timer']} is {now[0]}, {now[1]}; recorded {t['enabled']}, {t['active']}")
    if wrong:
        raise Stop("restore: " + "; ".join(wrong))
    print("every timer matches its record")


def main(argv):
    parser = argparse.ArgumentParser(prog="quiesce-timers")
    sub = parser.add_subparsers(dest="command", required=True)
    r = sub.add_parser("record")
    r.add_argument("--state", required=True)
    r.add_argument("timers", nargs="+")
    for name in ("stop", "restore"):
        sub.add_parser(name).add_argument("--state", required=True)
    w = sub.add_parser("wait")
    w.add_argument("--state", required=True)
    w.add_argument("--timeout", type=float, default=3600)
    w.add_argument("--poll", type=float, default=30)
    args = parser.parse_args(argv)
    try:
        {"record": record, "stop": stop, "wait": wait, "restore": restore}[args.command](args)
    except Stop as stop_:
        print(f"quiesce-timers: {stop_}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
```

- [ ] **Step 5: Run the tests**

Run: `uv run -q --with pytest pytest tools/test_quiesce_timers.py -q`

Expected: 9 passed.

- [ ] **Step 6: Full suite and commit**

```sh
. "$(tasks root tack-8b7a28 --pretty)/.worktrees/rename-hq-cutover/docs/plans/2026-10-06-rename-to-hq-cutover.env.sh" && cd "$WT" && t just test && \
tasks done "$STEP4" "quiesce-timers records, stops, waits for and restores a window's user timers; it never kills a running service" >/dev/null && \
git commit -q -m "feat(tools): quiesce-timers for a rename's window (tack-8b7a28)" -- tools/quiesce-timers tools/test_quiesce_timers.py "tasks/$STEP4.md" && git log --oneline -1
```

---

### Task 5: `rename-hq-steps`: this rename's edits and commits, and the second host's adoption

**Files:**
- Create: `tools/rename-hq-steps` (executable)
- Create: `tools/test_rename_hq_steps.py`

**Interfaces:**
- Consumes:
  - the snapshot's `meta.json` from `rename-cutover save` (`checkout.root`, `new_root`, `repos[].root`, `storage_old`);
  - `rename-cutover retarget` from the snapshot copy;
  - `tasks resolve --json`;
  - `.githooks/codex-trust capture`;
  - `tools/ops-docs write`, ops's `bin/ops-projects pull` and lore's `bin/assemble-instructions write`.
- Produces:
  - `rename-hq-steps tack|ops|lore|flows --snapshot SNAP`, with `--date YYYY-MM-DD` for `ops`;
  - `rename-hq-steps trust --checkout ROOT --old PATH --new PATH [--require]`;
  - `rename-hq-steps second-host-record --root OLD_ROOT --state FILE` (the other host, before the move) and `rename-hq-steps second-host --root NEW_ROOT --state FILE` (after it; a rerun finishes an interrupted adoption).
  - Module functions for the tests: `replace_once(path, old, new)`, `trust_text(text, old, new) -> str | None`, `add_trust(checkout, old, new, require)`, and `Stop`.

The edit tables below are the reviewed text of spec §3.2 steps 4 to 6 and §3.3. The rehearsal (Task 6, and again in Task 8 on the cutover's day) runs every edit against clones of the live mains.

- [ ] **Step 1: Start the record**

```sh
. "$(tasks root tack-8b7a28 --pretty)/.worktrees/rename-hq-cutover/docs/plans/2026-10-06-rename-to-hq-cutover.env.sh" && cd "$WT" && tasks start "$STEP5" >/dev/null && echo started
```

- [ ] **Step 2: Write the failing tests**

Create `tools/test_rename_hq_steps.py`:

```python
"""The pure parts of rename-hq-steps; the rehearsal runs the rest against clones."""
import importlib.machinery
import importlib.util
import os
import shutil
import subprocess
from pathlib import Path

import pytest

TOOL = Path(__file__).resolve().parent / "rename-hq-steps"


def load_steps():
    loader = importlib.machinery.SourceFileLoader("rename_hq_steps", str(TOOL))
    module = importlib.util.module_from_spec(importlib.util.spec_from_loader(loader.name, loader))
    loader.exec_module(module)
    return module


def test_replace_once_replaces_text_found_exactly_once(tmp_path):
    steps = load_steps()
    path = tmp_path / "README.md"
    path.write_text("# tack\n\nserved by tack's links\n")
    steps.replace_once(path, "tack's links", "hq's links")
    assert path.read_text() == "# tack\n\nserved by hq's links\n"


@pytest.mark.parametrize("text", ["nothing here\n", "tack's links and tack's links\n"])
def test_replace_once_refuses_text_that_is_missing_or_repeated(tmp_path, text):
    steps = load_steps()
    path = tmp_path / "README.md"
    path.write_text(text)
    with pytest.raises(steps.Stop, match=r"README.md: expected exactly one \"tack's links\""):
        steps.replace_once(path, "tack's links", "hq's links")
    assert path.read_text() == text


def test_trust_text_appends_a_copy_of_the_old_table_to_the_saved_copy():
    steps = load_steps()
    saved = '[projects."/elsewhere"]\ntrust_level = "trusted"\n\n[projects."/s/tack"]\ntrust_level = "trusted"\n'
    assert steps.trust_text(saved, "/s/tack", "/s/hq") == saved + '\n[projects."/s/hq"]\ntrust_level = "trusted"\n'


def test_trust_text_leaves_a_trusted_new_path_alone():
    steps = load_steps()
    text = '[projects."/s/tack"]\ntrust_level = "trusted"\n\n[projects."/s/hq"]\ntrust_level = "trusted"\n'
    assert steps.trust_text(text, "/s/tack", "/s/hq") == text


def test_trust_text_has_nothing_to_copy_without_the_old_table():
    steps = load_steps()
    assert steps.trust_text('[projects."/elsewhere"]\ntrust_level = "trusted"\n', "/s/tack", "/s/hq") is None


def test_add_trust_keeps_what_git_stages_when_a_table_ends_the_live_config(tmp_path):
    """The live config ends with a non-trust table: an appended trust table would leave a
    blank line the clean filter keeps. Through codex-trust restore it does not."""
    steps = load_steps()
    repo = tmp_path / "tack"
    (repo / ".githooks").mkdir(parents=True)
    for name in ("codex-trust", "harness-state-clean"):
        shutil.copy2(TOOL.parent.parent / ".githooks" / name, repo / ".githooks" / name)
    git = ["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t"]
    subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
    subprocess.run([*git, "config", "filter.harness-state.clean", ".githooks/harness-state-clean %f"], check=True)
    (repo / ".gitattributes").write_text("codex/config*.toml filter=harness-state\n")
    (repo / ".gitignore").write_text("local/\n")
    (repo / "codex").mkdir()
    config = repo / "codex" / "config.toml"
    config.write_text(f'model = "m"\n\n[projects."{repo}"]\ntrust_level = "trusted"\n\n[tui]\nx = 1\n')
    config.chmod(0o600)
    subprocess.run([*git, "add", "-A"], check=True)
    subprocess.run([*git, "commit", "-qm", "init"], check=True)
    assert subprocess.run([*git, "diff", "--quiet"]).returncode == 0
    (repo / "local" / "codex").mkdir(parents=True)
    new = tmp_path / "hq"
    steps.add_trust(repo, repo, new, require=True)
    assert f'[projects."{new}"]' in config.read_text() and f'[projects."{repo}"]' in config.read_text()
    assert f'[projects."{new}"]' in (repo / "local" / "codex" / "trust.toml").read_text()
    assert subprocess.run([*git, "diff", "--quiet"]).returncode == 0


def test_second_host_refuses_without_its_pre_move_record(tmp_path):
    (tmp_path / "cfg" / "tasks").mkdir(parents=True)
    (tmp_path / "cfg" / "tasks" / "projects.toml").write_text(f'[projects]\ntack = "{tmp_path / "tack"}"\n')
    root = tmp_path / "hq"
    (root / "tasks").mkdir(parents=True)
    (root / "tasks" / ".config.toml").write_text('prefix = "hq"\n')
    env = {**os.environ, "XDG_CONFIG_HOME": str(tmp_path / "cfg"), "HOME": str(tmp_path)}
    result = subprocess.run([str(TOOL), "second-host", "--root", str(root), "--state", str(tmp_path / "s.json")],
                            text=True, capture_output=True, env=env)
    assert result.returncode == 1 and "no record at" in result.stderr and "second-host-record" in result.stderr
    assert (tmp_path / "cfg" / "tasks" / "projects.toml").read_text() == f'[projects]\ntack = "{tmp_path / "tack"}"\n'


def test_second_host_record_refuses_a_root_that_is_not_the_old_project(tmp_path):
    root = tmp_path / "tack"
    (root / "tasks").mkdir(parents=True)
    (root / "tasks" / ".config.toml").write_text('prefix = "hq"\n')
    result = subprocess.run([str(TOOL), "second-host-record", "--root", str(root), "--state", str(tmp_path / "s.json")],
                            text=True, capture_output=True,
                            env={**os.environ, "XDG_CONFIG_HOME": str(tmp_path / "cfg"), "HOME": str(tmp_path)})
    assert result.returncode == 1 and "has the prefix 'hq', not 'tack'" in result.stderr
    assert not (tmp_path / "s.json").exists()


def test_second_host_refuses_before_the_sync_has_carried_the_rename(tmp_path):
    root = tmp_path / "hq"
    (root / "tasks").mkdir(parents=True)
    (root / "tasks" / ".config.toml").write_text('prefix = "tack"\n')
    result = subprocess.run([str(TOOL), "second-host", "--root", str(root), "--state", str(tmp_path / "s.json")],
                            text=True, capture_output=True,
                            env={**os.environ, "XDG_CONFIG_HOME": str(tmp_path / "cfg"), "HOME": str(tmp_path)})
    assert result.returncode == 1 and "has the prefix 'tack', not 'hq'" in result.stderr
```

- [ ] **Step 3: Run them to see them fail**

Run: `uv run -q --with pytest pytest tools/test_rename_hq_steps.py -q`

Expected: every test FAILS. The tool does not exist (`FileNotFoundError`).

- [ ] **Step 4: Implement**

Create `tools/rename-hq-steps`, executable (`chmod +x`):

```python
#!/usr/bin/env python3
"""The rename to hq's own edits and commits, shared by the rehearsal and the live cutover.

rename-hq-steps tack  --snapshot SNAP                    cutover step 4, in the renamed checkout
rename-hq-steps ops   --snapshot SNAP --date YYYY-MM-DD  step 5
rename-hq-steps lore  --snapshot SNAP                    step 6
rename-hq-steps flows --snapshot SNAP                    step 6
rename-hq-steps trust --checkout ROOT --old PATH --new PATH [--require]
rename-hq-steps second-host-record --root ROOT --state FILE   on the other host, before the move
rename-hq-steps second-host --root ROOT --state FILE          its adoption, after the sync carried it

docs/specs/2026-10-06-rename-to-hq-design.md §3.2 and §3.3;
docs/plans/2026-10-06-rename-to-hq-cutover.md, Tasks 5, 9 and 10. Paths come from the
snapshot's meta.json, and every git, tasks and python call inherits the environment, so the
rehearsal runs exactly these steps against its clones. Each edit replaces text that must
occur exactly once and stops otherwise: a sentence that moved since this was written is a
finding for the rehearsal, never a silent skip. Each step stages its repository whole,
because `rename-cutover save` refused unless every tree was clean. This tool names this
rename's text; it is removed once the rename has landed.
"""
import argparse
import json
import os
import re
import subprocess
import sys
import tomllib
from pathlib import Path

OLD, NEW, NAME = "tack", "hq", "harness-quarters"


class Stop(Exception):
    pass


def run(*cmd, cwd=None):
    result = subprocess.run([str(c) for c in cmd], cwd=cwd, text=True, capture_output=True)
    if result.returncode != 0:
        raise Stop(f"{' '.join(map(str, cmd))}: {(result.stderr or result.stdout).strip()}")
    return result.stdout


def replace_once(path, old, new):
    text = Path(path).read_text()
    count = text.count(old)
    if count != 1:
        raise Stop(f"{path}: expected exactly one {json.dumps(old)}, found {count}")
    Path(path).write_text(text.replace(old, new))


def apply_edits(root, edits):
    for rel, old, new in edits:
        replace_once(Path(root) / rel, old, new)


def load_meta(snap):
    return json.loads((Path(snap) / "meta.json").read_text())


def prefix_of(root):
    return tomllib.loads((Path(root) / "tasks" / ".config.toml").read_text())["prefix"]


def repo_for(meta, prefix):
    for repo in meta["repos"]:
        if prefix_of(repo["root"]) == prefix:
            return Path(repo["root"])
    raise Stop(f"no repository with the prefix {prefix} in the snapshot")


def retarget(snap, root):
    print(run(Path(snap) / "rename-cutover", "retarget", "--snapshot", snap, "--repo", root), end="")


def commit(root, message):
    run("git", "-C", root, "add", "-A")
    run("git", "-C", root, "commit", "-q", "-m", message)
    print(f"{root}: {run('git', '-C', root, 'log', '--oneline', '-1').strip()}")


# --- the edits (spec §3.2 steps 4 to 6, §3.3) -----------------------------------------

RENAME_NOTE_OLD = """## Renamed from ai

This project was `ai` until 2026-09. Old `ai-<hex>` task ids resolve through the tasks
alias. On a host that synced the rename, run once in this checkout, with no harness
session open: `tasks rename ai tack --adopt`, `just link --apply`, and
`work-link --ensure .worktrees` after moving `.dropbox-work/ai` to `.dropbox-work/tack`.
Until then that host's harness sessions start without instructions, skills or hooks.
"""

RENAME_NOTE_NEW = """## Renamed from tack

This project was `tack` until 2026-10, and `ai` before 2026-09. Old `tack-<hex>` and
`ai-<hex>` task ids resolve through the tasks aliases, and `tasks resolve` maps the old
directories and their worktree storage to `hq`. On a host that synced the rename, with no
harness session open and the host's timers paused, run in this checkout:
`tasks rename tack hq --adopt`; move `.dropbox-work/tack` to `.dropbox-work/hq`;
`work-link --ensure .worktrees`; `tasks init --prefix hq --force`; `just link --apply`;
`systemctl --user daemon-reload`; and `systemctl --user reenable` for each session-archive
timer the host had enabled. `tools/rename-hq-steps second-host` did the tasks part of this
on 2026-10. Until then that host's harness sessions start without instructions, skills or
hooks.
"""

TACK_EDITS = [
    ("identity.toml", 'name = "tack"', f'name = "{NAME}"'),
    ("AGENTS.md", "# tack — agent guide", f"# {NAME} — agent guide"),
    ("AGENTS.md", "file is tack's project guide", "file is hq's project guide"),
    ("README.md", "# tack\n", f"# {NAME}\n"),
    ("README.md", "lore; tack delivers them", "lore; hq delivers them"),
    ("README.md", "ops, or tack's", "ops, or hq's"),
    ("README.md", "`AGENTS.md`: tack's project guide", "`AGENTS.md`: hq's project guide"),
    ("README.md", "`docs/`: tack's specs", "`docs/`: hq's specs"),
    ("README.md", "declared owner links from tack.", "declared owner links from hq."),
    ("README.md", "consume tack's capture", "consume hq's capture"),
    ("README.md", "home link into tack or another", "home link into hq or another"),
    ("README.md", "harness/session tools target tack.", "harness/session tools target hq."),
    ("README.md", "through an old tack skill link", "through an old skill link into this checkout"),
    ("README.md", RENAME_NOTE_OLD, RENAME_NOTE_NEW),
    ("agents/skills/session-logs/SKILL.md", "in `tack`); nothing puts it on PATH", "in `hq`); nothing puts it on PATH"),
    ("agents/skills/session-logs/SKILL.md", "in the `tack` checkout.", "in the `hq` checkout."),
]


def ops_edits(date):
    status_old = "(§7.3 deviation, plan Task 3)."
    gate_old = "(adjusted 2026-10-04 at plan review round 5; the plan's Task 1 records the choice)."
    renamed = (f"renamed from `tack` at the cutover on {date} "
               "(hq docs/specs/2026-10-06-rename-to-hq-design.md)")
    spec = "docs/specs/2026-10-03-agent-layer-split-design.md"
    return [
        ("identity-mirror.toml", '[tack]\nname = "tack"\n', f'[hq]\nname = "{OLD}"\n'),
        ("identity-mirror.toml", 'path = "tack"\n', 'path = "hq"\n'),
        ("README.md", "wired from the tack repository's", "wired from the hq repository's"),
        ("README.md", "registered by\ntack's Claude settings.", "registered by\nhq's Claude settings."),
        ("README.md", "Design: tack `docs/specs/2026-09-19-project-profiles-design.md`.",
         "Design: hq `docs/specs/2026-09-19-project-profiles-design.md`."),
        ("README.md", "in the `tack` repository's Claude settings", "in the `hq` repository's Claude settings"),
        (spec, status_old, f"{status_old} The residue is named harness quarters (prefix and directory `hq`), {renamed}."),
        (spec, gate_old, f"{gate_old} Named 2026-10-06: harness quarters, prefix `hq`; {renamed}."),
    ]


LORE_EDITS = [
    ("AGENTS.md", "served through tack\n  `./links.toml`", "served through hq\n  `./links.toml`"),
    ("AGENTS.md", "wired from tack's hook files", "wired from hq's hook files"),
    ("AGENTS.md", "declaration in tack `./links.toml`", "declaration in hq `./links.toml`"),
    ("README.md", "the files tack's home links serve", "the files hq's home links serve"),
    ("README.md", "Every harness home through tack's declared links", "Every harness home through hq's declared links"),
    ("README.md", "session; tack's hook files name it", "session; hq's hook files name it"),
    ("skills/README.md", "tack's `links.toml` declares `~/.agents/skills`", "hq's `links.toml` declares `~/.agents/skills`"),
    ("skills/README.md", "declarations in tack's `links.toml`, so the skills", "declarations in hq's `links.toml`, so the skills"),
    ("skills/README.md", "served from the flows and tack checkouts", "served from the flows and hq checkouts"),
    ("skills/README.md", "its declaration in tack's `links.toml`", "its declaration in hq's `links.toml`"),
]

FLOWS_EDITS = [
    ("AGENTS.md",
     "  tack `docs/specs/2026-10-02-flow-trial-design.md`, by a path that resolves only in tack; that design and "
     "its plan stay there until the tack tasks\n  that carry them (`tack-7d9375`, `tack-c4a4da`) close;",
     "  hq `docs/specs/2026-10-02-flow-trial-design.md`, by a path that resolves only in hq; that design and "
     "its plan stay there until the hq tasks\n  that carry them (`hq-7d9375`, `hq-c4a4da`) close;"),
    ("README.md", "through the links tack declares in its links.toml", "through the links hq declares in its links.toml"),
    ("bin/trial-arm", "(tack docs/specs/2026-10-02-flow-trial-design.md, until it moves here)",
     "(hq docs/specs/2026-10-02-flow-trial-design.md, until it moves here)"),
    ("bin/trial-verdict", "Spec tack docs/specs/2026-10-02-flow-trial-design.md §6",
     "Spec hq docs/specs/2026-10-02-flow-trial-design.md §6"),
]


# --- Codex project trust (README, "Codex's project trust") ------------------------------

def trust_text(text, old, new):
    """The saved copy (local/codex/trust.toml: tables separated by one blank line) with a
    table for `new` that copies `old`'s, appended; the text unchanged when `new` is already
    there; None when there is no table for `old` to copy."""
    if f'[projects."{new}"]' in text:
        return text
    match = re.search(re.escape(f'[projects."{old}"]') + r"\n((?:(?!\[).*\n?)*)", text)
    if match is None:
        return None
    body = match.group(1).rstrip("\n") + "\n"
    return text.rstrip("\n") + f'\n\n[projects."{new}"]\n{body}'


def add_trust(checkout, old, new, require):
    """An entry for the new path beside the old one, so Codex does not ask to trust the
    directory. The table goes into the saved copy, and codex-trust restore inserts it into
    the live config where the clean filter's output, and so what git stages, stays the
    same: before a table header, never appended after the last table."""
    checkout = Path(checkout)
    trust = checkout / ".githooks" / "codex-trust"
    run("python3", trust, "capture", cwd=checkout)
    saved = checkout / "local" / "codex" / "trust.toml"
    text = saved.read_text() if saved.exists() else ""
    updated = trust_text(text, str(old), str(new))
    if updated is None:
        if require:
            raise Stop(f"trust: {saved} has no table for {old}")
        print(f"trust: no table for {old}; nothing to add")
        return
    if updated != text:
        saved.write_text(updated)
    run("python3", trust, "restore", cwd=checkout)
    if f'[projects."{new}"]' not in (checkout / "codex" / "config.toml").read_text():
        raise Stop(f"trust: codex-trust restore did not put {new} into codex/config.toml")
    if subprocess.run(["git", "-C", str(checkout), "diff", "--quiet", "--", "codex/config.toml"]).returncode:
        raise Stop("trust: codex/config.toml changed beyond its trust tables")
    # git calls a filtered file modified when only its size changed; staging it, as
    # harness-state-refresh does, refreshes the entry and stages nothing.
    run("git", "-C", checkout, "add", "--", "codex/config.toml")
    print(f"trust: {new} trusted as {old} is")


# --- the steps --------------------------------------------------------------------------

def step_tack(args):
    meta = load_meta(args.snapshot)
    root, old_root = Path(meta["new_root"]), Path(meta["checkout"]["root"])
    if not root.is_dir():
        raise Stop(f"tack: {root} does not exist; run rename-cutover apply first")
    apply_edits(root, TACK_EDITS)
    run("python3", root / "tools" / "ops-docs", "write", cwd=root)
    add_trust(root, old_root, root, require=True)
    commit(root, f"refactor: tack is {NAME}, prefix and directory hq (hq-8b7a28)")


def step_ops(args):
    meta = load_meta(args.snapshot)
    ops = repo_for(meta, "ops")
    apply_edits(ops, ops_edits(args.date))
    run("python3", ops / "bin" / "ops-projects", "pull", cwd=ops)
    retarget(args.snapshot, ops)
    commit(ops, f"chore: tack is {NAME} (hq) in the mirror, the projects block and the split design (hq-8b7a28)")


def step_lore(args):
    meta = load_meta(args.snapshot)
    lore = repo_for(meta, "lore")
    apply_edits(lore, LORE_EDITS)
    run("python3", lore / "bin" / "assemble-instructions", "write", cwd=lore)
    retarget(args.snapshot, lore)
    commit(lore, "chore: tack is hq in the prose; assemble ops's regenerated projects block (hq-8b7a28)")


def step_flows(args):
    meta = load_meta(args.snapshot)
    flows = repo_for(meta, "flows")
    apply_edits(flows, FLOWS_EDITS)
    retarget(args.snapshot, flows)
    commit(flows, "chore: tack is hq in the prose (hq-8b7a28)")


def step_trust(args):
    add_trust(args.checkout, args.old, args.new, args.require)


def registry_path():
    return Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "tasks" / "projects.toml"


def check_resolves(probes):
    rows = json.loads(run("tasks", "resolve", "--json", *probes))["results"]
    wrong = [f"{r['input']} ({r['status']})" for r in rows if r["status"] != "resolved" or r.get("prefix") != NEW]
    if wrong:
        raise Stop(f"tasks resolve does not answer {NEW} for " + ", ".join(wrong))


def step_second_host_record(args):
    """Before the move, on the other host (Task 9 Step 5; tasks spec §2.3): refresh this
    host's storage record, and keep the old root and its storage in a state file that
    outlives the registry entry `tasks rename --adopt` removes."""
    root, state = Path(args.root).resolve(), Path(args.state)
    if state.exists():
        raise Stop(f"second-host-record: {state} exists")
    if prefix_of(root) != OLD:
        raise Stop(f"second-host-record: {root} has the prefix {prefix_of(root)!r}, not {OLD!r}")
    run("tasks", "init", "--prefix", OLD, "--force", cwd=root)
    if run("git", "-C", root, "status", "--porcelain").strip():
        raise Stop(f"second-host-record: {root} is not clean after init --force")
    registry = tomllib.loads(registry_path().read_text())
    storage = registry.get("locations", {}).get(OLD, {}).get("storage")
    if Path(registry["projects"][OLD]).resolve() != root or storage is None:
        raise Stop(f"second-host-record: the registry has no storage record for {OLD} at {root}")
    state.parent.mkdir(parents=True, exist_ok=True)
    state.write_text(json.dumps({"old_root": str(root), "storage_old": storage}, indent=2) + "\n")
    print(f"second-host-record: {root}, storage {storage}")


def step_second_host(args):
    """The other host's adoption after the sync has carried the move (spec §3.2, the other
    host): adopt, move this host's storage, relink it, record it, link, carry its Codex
    trust. Each part checks whether it is already done, so a rerun after a failure
    finishes the adoption from the state file second-host-record wrote."""
    root, state = Path(args.root).resolve(), Path(args.state)
    if prefix_of(root) != NEW:
        raise Stop(f"second-host: {root} has the prefix {prefix_of(root)!r}, not {NEW!r}; "
                   f"wait for the sync to carry the rename")
    if not state.exists():
        raise Stop(f"second-host: no record at {state}; run second-host-record at the old root "
                   f"before the move (Task 9 Step 5)")
    recorded = json.loads(state.read_text())
    old_root, storage_old = Path(recorded["old_root"]), Path(recorded["storage_old"])
    storage_new = storage_old.parent.parent / root.name / storage_old.name
    old_present, new_present = storage_old.parent.exists(), storage_new.parent.exists()
    if old_present == new_present:
        raise Stop(f"second-host: {'both' if old_present else 'neither'} of {storage_old.parent} and "
                   f"{storage_new.parent} exist")
    link = root / ".worktrees"
    if link.exists() and not link.is_symlink():
        raise Stop(f"second-host: {link} is not a link")
    projects = tomllib.loads(registry_path().read_text()).get("projects", {})
    if OLD not in projects and (NEW not in projects or Path(projects[NEW]).resolve() != root):
        raise Stop(f"second-host: the registry maps neither {OLD} nor {NEW} to {root}")
    # Always: the adoption is idempotent, and a rerun finishes its own interrupted cleanup
    # (tasks' resume_cleanup: the registry adopted, the old claim store not yet removed).
    print(run("tasks", "rename", OLD, NEW, "--adopt", cwd=root), end="")
    if old_present:
        os.rename(storage_old.parent, storage_new.parent)
    if not (link.is_symlink() and link.resolve() == storage_new.resolve()):
        if link.is_symlink():
            link.unlink()
        run("work-link", "--root", root.parent, "--ensure", ".worktrees", cwd=root)
    if link.resolve() != storage_new.resolve():
        raise Stop(f"second-host: {link} resolves to {link.resolve()}, not {storage_new}")
    print(run("tasks", "init", "--prefix", NEW, "--force", cwd=root), end="")
    run(root / "tools" / "harness-links", "--apply")
    add_trust(root, old_root, root, require=False)
    sample = next(p.stem for p in (root / "tasks").glob(f"{NEW}-*.md"))
    check_resolves([f"{OLD}-{sample.split('-', 1)[1]}", OLD, str(old_root), str(storage_old / "a-worktree")])
    print(f"second-host: adopted at {root}; storage at {storage_new}")


def main(argv):
    parser = argparse.ArgumentParser(prog="rename-hq-steps")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("tack", "lore", "flows"):
        sub.add_parser(name).add_argument("--snapshot", required=True)
    o = sub.add_parser("ops")
    o.add_argument("--snapshot", required=True)
    o.add_argument("--date", required=True)
    tr = sub.add_parser("trust")
    tr.add_argument("--checkout", required=True)
    tr.add_argument("--old", required=True)
    tr.add_argument("--new", required=True)
    tr.add_argument("--require", action="store_true")
    for name in ("second-host-record", "second-host"):
        h = sub.add_parser(name)
        h.add_argument("--root", required=True)
        h.add_argument("--state", required=True)
    args = parser.parse_args(argv)
    steps = {"tack": step_tack, "ops": step_ops, "lore": step_lore, "flows": step_flows,
             "trust": step_trust, "second-host-record": step_second_host_record,
             "second-host": step_second_host}
    try:
        steps[args.command](args)
    except Stop as stop:
        print(f"rename-hq-steps: {stop}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
```

Two notes on the edits. The mirror table is renamed to `[hq]` and keeps `name = "tack"`, because `ops-projects pull` rewrites `name`, `aliases` and `purpose` from hq's `identity.toml`, which step 4 has already committed (ops `bin/ops-projects`, `DECLARED`). `path` is ops's own field, so the edit sets it.

- [ ] **Step 5: Run the tests**

Run: `uv run -q --with pytest pytest tools/test_rename_hq_steps.py -q`

Expected: 10 passed.

- [ ] **Step 6: Check every edit's text against the live mains, read-only**

Before the rehearsal, a dry check. It only reads files, and changes nothing.

```sh
. "$(tasks root tack-8b7a28 --pretty)/.worktrees/rename-hq-cutover/docs/plans/2026-10-06-rename-to-hq-cutover.env.sh" && cd "$WT" && python3 - <<'EOF'
import importlib.machinery, importlib.util, json, subprocess
from pathlib import Path
loader = importlib.machinery.SourceFileLoader("s", "tools/rename-hq-steps")
s = importlib.util.module_from_spec(importlib.util.spec_from_loader("s", loader)); loader.exec_module(s)
root = lambda p: Path(json.loads(subprocess.run(["tasks", "resolve", "--json", p], capture_output=True, text=True).stdout)["results"][0]["root"])
bad = [(p, rel, old[:60]) for p, edits in (("tack", s.TACK_EDITS), ("ops", s.ops_edits("2026-01-01")),
       ("lore", s.LORE_EDITS), ("flows", s.FLOWS_EDITS)) for rel, old, _ in edits
       if (root(p) / rel).read_text().count(old) != 1]
print("every edit matches once" if not bad else bad)
EOF
```

Expected: `every edit matches once`. A mismatch names the repository, the file and the text. Correct the table from the file as it stands, and rerun the check.

- [ ] **Step 7: Full suite and commit**

```sh
. "$(tasks root tack-8b7a28 --pretty)/.worktrees/rename-hq-cutover/docs/plans/2026-10-06-rename-to-hq-cutover.env.sh" && cd "$WT" && t just test && \
tasks done "$STEP5" "rename-hq-steps holds the cutover's reviewed edits and commits for tack, ops, lore and flows, the Codex trust entry, and the second host's adoption" >/dev/null && \
git commit -q -m "feat(tools): rename-hq-steps, the cutover's edits and the second host's adoption (tack-8b7a28)" -- tools/rename-hq-steps tools/test_rename_hq_steps.py "tasks/$STEP5.md" && git log --oneline -1
```

---

### Task 6: The rehearsal

**Files:**
- Create: `tools/rehearse_rename_hq.py`

**Interfaces:**
- Consumes:
  - `rename-cutover` (save, apply, link, verify, rollback) from this worktree, then from its snapshot copy;
  - `rename-hq-steps`;
  - the live registry, read with `tomllib`;
  - the live checkouts of tack, ops, lore, flows, tasks and obs (cloned, each given its live `core.hooksPath`, so commits meet the same hooks);
  - the live `local/` and Codex config (copied).
- Produces: a passing rehearsal, recorded on `tack-8b7a28` as a note `rehearsal: passed <date>; …`. Task 8 adds the trial join and reruns all of it on the cutover's day, and Task 9's preconditions read that note.

What it covers, against spec §4:

| Spec §4 asks for | Test |
|---|---|
| The cutover, then the second host's adoption against a second pair of scratch directories, with its own checkout path and its own trust table | `test_the_cutover_verifies_and_the_second_host_adopts` |
| An adoption interrupted after `tasks rename --adopt`, finished by a rerun, and a rerun of a finished one | `test_the_second_host_finishes_an_interrupted_adoption` |
| Rollback before the commits: the guard passes on the rename's own alias retarget and group rewrite, and both trust files come back byte for byte with their modes | `test_rollback_before_the_commits_restores_everything` |
| Rollback after the commits, with the same checks | `test_rollback_after_the_commits_restores_everything` |
| The guard stops on a planted foreign entry, alias and group | `test_the_guard_stops_on_a_foreign_change[projects/aliases/groups]` |
| A planted dead claim in a retargeted repository is refused | `test_save_refuses_a_dead_claim_in_a_retargeted_repository` |
| Each restored sandbox matches its saved originals, and `tasks check` is clean in all four | The two rollback tests compare a fingerprint of the four repositories (head, branch, status and every file outside `.git`), the tasks config and state, the kept files' modes, the `.worktrees` link, every home link, and the timer's enable link |
| The trial's join, end to end | Task 8 |

- [ ] **Step 1: Start the record**

```sh
. "$(tasks root tack-8b7a28 --pretty)/.worktrees/rename-hq-cutover/docs/plans/2026-10-06-rename-to-hq-cutover.env.sh" && cd "$WT" && tasks start "$STEP6" >/dev/null && echo started
```

- [ ] **Step 2: Write the rehearsal**

Create `tools/rehearse_rename_hq.py`:

```python
"""The rename's rehearsal (docs/specs/2026-10-06-rename-to-hq-design.md §4).

Run only when named; `just test` never collects it, since its name does not match test_*.py:

    uv run -q --with pytest pytest tools/rehearse_rename_hq.py -q --basetemp <scratch dir>

It clones this host's tack, ops, lore, flows, tasks and obs (their committed state) into two
scratch hosts. Each host has its own HOME, XDG_CONFIG_HOME, XDG_STATE_HOME and worktree
storage, and a scratch registry in the live one's shape: the ai alias, the agent-layer
group, and tack's former roots. Projects it does not clone stay registered at their live
roots, read-only. Then it runs the cutover through the tools the live run uses:
rename-cutover from its snapshot copy, and rename-hq-steps. It reads the live registry,
checkouts and trust files, and writes only under the base directory. It never calls
systemctl: the timer's enable link is a fixture, checked by its target. Every scenario
starts from one pristine copy restored at the same path, because the scratch registries
hold absolute paths.
"""
import datetime
import json
import os
import shutil
import stat
import subprocess
import tomllib
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parent
CUTOVER, STEPS = TOOLS / "rename-cutover", TOOLS / "rename-hq-steps"
LIVE_REGISTRY = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "tasks" / "projects.toml"
CLONED = ("tack", "ops", "lore", "flows", "tasks", "obs")
REPOS = ("ops", "lore", "flows")
KEPT = ("codex/config.toml", "local/codex/trust.toml")
OLD, NEW = "tack", "hq"
UNIT = Path(".config/systemd/user/session-archive-capture.timer")
WANTS = Path(".config/systemd/user/timers.target.wants/session-archive-capture.timer")
GIT_ID = {"GIT_AUTHOR_NAME": "rehearsal", "GIT_AUTHOR_EMAIL": "rehearsal@localhost",
          "GIT_COMMITTER_NAME": "rehearsal", "GIT_COMMITTER_EMAIL": "rehearsal@localhost"}
# The hooks the commits meet run uv; the live cache lets them resolve offline, as they do live.
UV_CACHE = subprocess.run(["uv", "cache", "dir"], text=True, capture_output=True, check=True).stdout.strip()
TODAY = datetime.date.today().isoformat()


def live():
    return tomllib.loads(LIVE_REGISTRY.read_text())


def toml(value):
    return json.dumps(str(value))


class Host:
    """One scratch host: <base>/<name>/{d, .dropbox-work, home, cfg, state}."""

    def __init__(self, base, name):
        self.root = base / name
        self.sync = self.root / "d"
        self.home, self.cfg, self.state = self.root / "home", self.root / "cfg", self.root / "state"
        self.registry = self.cfg / "tasks" / "projects.toml"
        self.env = {**os.environ, "HOME": str(self.home), "XDG_CONFIG_HOME": str(self.cfg),
                    "XDG_STATE_HOME": str(self.state), "UV_CACHE_DIR": UV_CACHE, **GIT_ID}
        for name_ in ("WORK_ROOT", "TASKS_SESSION", "TASKS_SESSION_PID", "GIT_DIR", "GIT_WORK_TREE"):
            self.env.pop(name_, None)

    def path(self, name):
        return self.sync / name

    def run(self, *cmd, cwd=None, check=True, env=None):
        result = subprocess.run([str(c) for c in cmd], cwd=cwd, env=env or self.env, text=True, capture_output=True)
        if check and result.returncode != 0:
            raise AssertionError(f"{cmd}: {result.stdout}{result.stderr}")
        return result

    def storage(self, name):
        return self.root / ".dropbox-work" / name / ".worktrees"

    @property
    def second_state(self):
        return self.root / "second-host.json"


def write_registry(host, roots, extra_former):
    """The live registry's shape over this host's roots: aliases and groups as they are,
    each live project's location history, and `extra_former` appended per prefix."""
    data = live()
    lines = ["[projects]"] + [f"{k} = {toml(v)}" for k, v in sorted(roots.items())]
    if data.get("aliases"):
        lines += ["", "[aliases]"] + [f"{k} = {toml(v)}" for k, v in sorted(data["aliases"].items())]
    if data.get("groups"):
        lines += ["", "[groups]"] + [f"{k} = [{', '.join(toml(m) for m in v)}]" for k, v in sorted(data["groups"].items())]
    locations = data.get("locations", {})
    for prefix in sorted(set(locations) | set(extra_former)):
        table = locations.get(prefix, {})
        former = list(table.get("former", [])) + extra_former.get(prefix, [])
        storage = table.get("storage") if prefix not in CLONED else None
        if not former and storage is None:
            continue
        lines += ["", f"[locations.{prefix}]"] + ([f"storage = {toml(storage)}"] if storage else [])
        for entry in former:
            lines += ["", f"[[locations.{prefix}.former]]"] + [f"{k} = {toml(v)}" for k, v in entry.items()]
    host.registry.parent.mkdir(parents=True, exist_ok=True)
    host.registry.write_text("\n".join(lines) + "\n")


def copy_local(host, clone, live_tack):
    """local/ is ignored and the trust tables are filtered: copy them as the cutover finds
    them, with this host's checkout in place of the live one in each trust table's key."""
    # Lock files too: codex-trust creates trust.toml.lock, and the live checkout has one.
    shutil.copytree(live_tack / "local", clone / "local", dirs_exist_ok=True)
    for rel in KEPT:
        text = (live_tack / rel).read_text()
        key = f'[projects."{live_tack}"]'
        assert text.count(key) == 1, f"live {rel} has no single trust table for {live_tack}"
        (clone / rel).write_text(text.replace(key, f'[projects."{clone}"]'))
        os.chmod(clone / rel, stat.S_IMODE((live_tack / rel).stat().st_mode))
    host.run("git", "add", "codex/config.toml", cwd=clone)
    assert host.run("git", "status", "--porcelain", "--untracked-files=all", cwd=clone).stdout == ""


def init_submodules(host, clone, live_root):
    """A clone does not fetch submodules (lore's vendor/superpowers, which links.toml
    targets). Fetch each from the live checkout's own copy, never from the network."""
    listed = host.run("git", "config", "-f", ".gitmodules", "--get-regexp", r"submodule\..*\.path",
                      cwd=clone, check=False).stdout.split()
    for key, path in zip(listed[::2], listed[1::2]):
        name = key[len("submodule."):-len(".path")]
        host.run("git", "config", f"submodule.{name}.url", live_root / path, cwd=clone)
        host.run("git", "-c", "protocol.file.allow=always", "submodule", "update", "--init", "--", path, cwd=clone)


def stand_in_for_the_rest(host, live_roots):
    """ops-projects check, which ops's commit hook runs, reads every registered project at
    its mirror path under the sync root. Each project this does not clone stands there
    as a link to its live checkout, read-only by everything the rehearsal runs."""
    live_sync = Path(live_roots["ops"]).resolve().parent
    for prefix, root in live_roots.items():
        live = Path(root).resolve()
        if prefix in CLONED or not live.exists() or live_sync not in live.parents:
            continue
        link = host.sync / live.relative_to(live_sync)  # mirror paths can nest: mindful/v3
        if not link.exists():
            link.parent.mkdir(parents=True, exist_ok=True)
            link.symlink_to(live)


def install_hooks(host, clone, live_root):
    """A clone does not carry core.hooksPath: give each the live checkout's, so the
    rehearsal's commits meet the gates the live run's do."""
    hooks = subprocess.run(["git", "-C", str(live_root), "config", "core.hooksPath"], text=True,
                           capture_output=True).stdout.strip()
    if hooks:
        host.run("git", "config", "core.hooksPath", hooks, cwd=clone)
        assert (clone / hooks).is_dir(), f"{clone}: no {hooks}"
    assert host.run("git", "config", "core.hooksPath", cwd=clone, check=False).stdout.strip() == hooks


def link_home(host):
    host.run(host.path("tack") / "tools" / "harness-links", "--apply")
    wants = host.home / WANTS
    wants.parent.mkdir(parents=True, exist_ok=True)
    wants.symlink_to(os.readlink(host.home / UNIT))


def build_first(host, live_roots):
    host.sync.mkdir(parents=True)
    for d in (host.home, host.cfg, host.state):
        d.mkdir(parents=True)
    roots = dict(live_roots)
    for prefix in CLONED:
        clone = host.path(Path(live_roots[prefix]).name)
        host.run("git", "clone", "-q", "--no-hardlinks", Path(live_roots[prefix]).resolve(), clone)
        roots[prefix] = clone
    for prefix in CLONED:
        init_submodules(host, roots[prefix], Path(live_roots[prefix]).resolve())
        if prefix != "tack":
            install_hooks(host, roots[prefix], Path(live_roots[prefix]).resolve())
    stand_in_for_the_rest(host, live_roots)
    tack, live_tack = roots["tack"], Path(live_roots["tack"]).resolve()
    host.run("just", "setup", cwd=tack)
    copy_local(host, tack, live_tack)
    # The trust files are shared through the sync, so they also hold the other host's
    # table for its own checkout path, which differs from this one's.
    host.run("python3", STEPS, "trust", "--checkout", tack, "--old", tack, "--new",
             Host(host.root.parent, "h2").path("tack"), "--require")
    host.run("work-link", "--root", host.sync, "--ensure", ".worktrees", cwd=tack)
    # Sessions recorded under the live checkout resolve to the clone (Task 8's trial join).
    live_storage = (live_tack / ".worktrees").resolve()
    write_registry(host, roots, {OLD: [{"root": str(live_tack), "storage": str(live_storage), "until": TODAY}]})
    for prefix in CLONED:
        host.run("tasks", "init", "--prefix", prefix, "--force", cwd=roots[prefix])
    link_home(host)


def build_second(first, host, live_roots):
    """The other host: the same synced files, its own registry, storage and home. Its
    pre-move second-host-record refreshes and keeps its storage (tasks spec §2.3; Task 9 Step 5)."""
    host.sync.mkdir(parents=True)
    for d in (host.home, host.cfg, host.state):
        d.mkdir(parents=True)
    roots = dict(live_roots)
    for prefix in CLONED:
        name = Path(live_roots[prefix]).name
        subprocess.run(["cp", "-a", str(first.path(name)), str(host.path(name))], check=True)
        roots[prefix] = host.path(name)
    (host.path("tack") / ".worktrees").unlink()
    host.run("work-link", "--root", host.sync, "--ensure", ".worktrees", cwd=host.path("tack"))
    stand_in_for_the_rest(host, live_roots)
    write_registry(host, roots, {})
    for prefix in CLONED:
        if prefix != "tack":
            host.run("tasks", "init", "--prefix", prefix, "--force", cwd=roots[prefix])
    host.run("python3", STEPS, "second-host-record", "--root", host.path("tack"), "--state", host.second_state)
    link_home(host)


@pytest.fixture(scope="module")
def pristine(tmp_path_factory):
    base = tmp_path_factory.getbasetemp().resolve()
    run_dir = base / "run"
    live_roots = live()["projects"]
    first = Host(run_dir, "h1")
    build_first(first, live_roots)
    build_second(first, Host(run_dir, "h2"), live_roots)
    subprocess.run(["cp", "-a", str(run_dir), str(base / "pristine")], check=True)
    return base


@pytest.fixture
def hosts(pristine):
    run_dir = pristine / "run"
    shutil.rmtree(run_dir)
    subprocess.run(["cp", "-a", str(pristine / "pristine"), str(run_dir)], check=True)
    return Host(run_dir, "h1"), Host(run_dir, "h2")


class Cutover:
    """The live runbook's calls (Task 9 Steps 6 to 12), against the first scratch host."""

    def __init__(self, host):
        self.host = host
        self.snap = host.root.parent / "snap"

    def tool(self):
        copy = self.snap / "rename-cutover"
        return copy if copy.exists() else CUTOVER

    def save(self, check=True):
        h = self.host
        args = ["save", "--snapshot", self.snap, "--checkout", h.path("tack"), "--new-root", h.path("hq"),
                "--old", OLD, "--new", NEW]
        for rel in KEPT:
            args += ["--keep", rel]
        for name in REPOS:
            args += ["--repo", h.path(name)]
        return h.run(self.tool(), *args, check=check)

    def cut(self, command, check=True):
        return self.host.run(self.tool(), command, "--snapshot", self.snap, check=check)

    def step(self, *args):
        self.host.run("python3", STEPS, *args, "--snapshot", self.snap)

    def forward(self):
        self.cut("apply")
        self.step("tack")
        self.step("ops", "--date", TODAY)
        self.step("lore")
        self.step("flows")
        self.cut("link")
        reenable(self.host)
        self.cut("verify")


def reenable(host):
    """What `systemctl --user reenable` did in the plan's probe (systemd 262): the enable
    link follows the manifest-held unit link."""
    wants = host.home / WANTS
    wants.unlink()
    wants.symlink_to(os.readlink(host.home / UNIT))


def resolve(host, inputs):
    return json.loads(host.run("tasks", "resolve", "--json", *map(str, inputs)).stdout)["results"]


def fingerprint(host):
    """Everything rollback must restore on the first host, as comparable data."""
    def tree(root):
        return {str(p.relative_to(root)): p.read_bytes() for p in sorted(root.rglob("*"))
                if ".git" not in p.relative_to(root).parts and p.is_file() and not p.is_symlink()}

    def git(root, *args):
        return host.run("git", *args, cwd=root).stdout

    tack = host.path("tack")
    return {
        "repos": {name: {"head": git(host.path(name), "rev-parse", "HEAD"),
                         "branch": git(host.path(name), "symbolic-ref", "-q", "HEAD"),
                         "status": git(host.path(name), "status", "--porcelain", "--untracked-files=all"),
                         "files": tree(host.path(name))} for name in ("tack", *REPOS)},
        "cfg": tree(host.cfg / "tasks"), "state": tree(host.state / "tasks"),
        "modes": {rel: stat.S_IMODE((tack / rel).stat().st_mode) for rel in KEPT},
        "worktrees": os.readlink(tack / ".worktrees"),
        "home": {str(p.relative_to(host.home)): os.readlink(p) for p in sorted(host.home.rglob("*")) if p.is_symlink()},
    }


def carry(first, second):
    """What the file sync does to the other host: its checkouts become the first host's."""
    for name in ("tack", *REPOS):
        shutil.rmtree(second.path(name))
    for name in ("hq", *REPOS):
        subprocess.run(["cp", "-a", str(first.path(name)), str(second.path(name))], check=True)


# --- the scenarios ---------------------------------------------------------------------


def test_the_cutover_verifies_and_the_second_host_adopts(hosts):
    h1, h2 = hosts
    cutover = Cutover(h1)
    cutover.save()
    cutover.forward()
    for name in ("hq", *REPOS):
        assert h1.run("tasks", "check", cwd=h1.path(name)).stdout == "", name
        assert h1.run("git", "status", "--porcelain", "--untracked-files=all", cwd=h1.path(name)).stdout == "", name
    rows = resolve(h1, ["tack-dcb11a", "ai-4b1878", h1.path("tack"), h1.storage("tack") / "a-worktree"])
    assert [(r["status"], r.get("prefix")) for r in rows] == [("resolved", NEW)] * 4
    for rel in KEPT:
        text = (h1.path("hq") / rel).read_text()
        assert f'[projects."{h1.path("hq")}"]' in text and f'[projects."{h1.path("tack")}"]' in text
    assert tomllib.loads((h1.path("hq") / "identity.toml").read_text())["name"] == "harness-quarters"
    mirror = tomllib.loads((h1.path("ops") / "identity-mirror.toml").read_text())
    assert "tack" not in mirror and mirror["hq"]["name"] == "harness-quarters" and mirror["hq"]["path"] == "hq"
    assert "`hq` — harness-quarters" in (h1.path("lore") / "instructions" / "AGENTS.md").read_text()
    assert Path(os.readlink(h1.home / WANTS)).resolve() == (h1.path("hq") / "systemd/user/session-archive-capture.timer")

    first_host = {p: p.read_bytes() for d in (h1.cfg, h1.state) for p in sorted(d.rglob("*")) if p.is_file()}
    carry(h1, h2)
    h2.run("python3", STEPS, "second-host", "--root", h2.path("hq"), "--state", h2.second_state)
    assert_adopted(h2)
    assert {p: p.read_bytes() for d in (h1.cfg, h1.state) for p in sorted(d.rglob("*")) if p.is_file()} == first_host


def assert_adopted(h2):
    location = tomllib.loads(h2.registry.read_text())["locations"]["hq"]
    assert location["storage"] == str(h2.storage("hq"))
    assert {"root": str(h2.path("tack")), "storage": str(h2.storage("tack"))} in [
        {k: e.get(k) for k in ("root", "storage")} for e in location["former"]]
    rows = resolve(h2, ["tack-dcb11a", OLD, h2.path("tack"), h2.storage("tack") / "a-worktree"])
    assert [(r["status"], r.get("prefix")) for r in rows] == [("resolved", NEW)] * 4
    trust = (h2.path("hq") / "codex" / "config.toml").read_text()
    assert f'[projects."{h2.path("hq")}"]' in trust and f'[projects."{h2.path("tack")}"]' in trust
    for name in ("hq", *REPOS):
        assert h2.run("tasks", "check", cwd=h2.path(name)).stdout == "", name
        assert h2.run("git", "status", "--porcelain", "--untracked-files=all", cwd=h2.path(name)).stdout == "", name


def test_the_second_host_finishes_an_interrupted_adoption(hosts):
    h1, h2 = hosts
    cutover = Cutover(h1)
    cutover.save()
    cutover.forward()
    carry(h1, h2)
    # second-host got as far as the adoption, then stopped: the registry no longer names tack.
    h2.run("tasks", "rename", OLD, NEW, "--adopt", cwd=h2.path("hq"))
    # And tasks itself stopped between adopting the registry and removing the old claim
    # store: its resume_cleanup state, which only a rerun of the adoption finishes.
    old_store = h2.state / "tasks" / "claims" / f"{OLD}.toml"
    old_store.parent.mkdir(parents=True, exist_ok=True)
    old_store.write_text("")
    explained = json.loads(h2.run("tasks", "rename", OLD, NEW, "--adopt", "--explain", cwd=h2.path("hq")).stdout)
    assert "resume_cleanup" in json.dumps(explained), explained
    h2.run("python3", STEPS, "second-host", "--root", h2.path("hq"), "--state", h2.second_state)
    assert not old_store.exists()
    assert_adopted(h2)
    # A rerun of a finished adoption changes nothing and passes.
    h2.run("python3", STEPS, "second-host", "--root", h2.path("hq"), "--state", h2.second_state)
    assert_adopted(h2)


def test_rollback_before_the_commits_restores_everything(hosts):
    h1, _ = hosts
    cutover = Cutover(h1)
    before = fingerprint(h1)
    cutover.save()
    cutover.cut("apply")
    cutover.cut("rollback")
    reenable(h1)
    assert fingerprint(h1) == before


def test_rollback_after_the_commits_restores_everything(hosts):
    h1, _ = hosts
    cutover = Cutover(h1)
    before = fingerprint(h1)
    cutover.save()
    cutover.forward()
    cutover.cut("rollback")
    reenable(h1)
    assert fingerprint(h1) == before


@pytest.mark.parametrize("table, plant", [
    ("projects", lambda t: t.replace("[projects]\n", '[projects]\nzz = "/elsewhere"\n', 1)),
    ("aliases", lambda t: t.replace("[aliases]\n", '[aliases]\nzz = "hq"\n', 1)),
    ("groups", lambda t: t.replace("[groups]\n", '[groups]\nzz = ["ops"]\n', 1)),
])
def test_the_guard_stops_on_a_foreign_change(hosts, table, plant):
    h1, _ = hosts
    cutover = Cutover(h1)
    cutover.save()
    cutover.cut("apply")
    text = h1.registry.read_text()
    h1.registry.write_text(plant(text))
    assert h1.registry.read_text() != text
    result = cutover.cut("rollback", check=False)
    assert result.returncode == 1
    assert "guard: the registry changed" in result.stderr and f"{table}.zz" in result.stderr
    assert h1.path("hq").exists() and not h1.path("tack").exists()


def test_save_refuses_a_dead_claim_in_a_retargeted_repository(hosts):
    h1, _ = hosts
    ops = h1.path("ops")
    added = json.loads(h1.run("tasks", "add", "orphaned claim", "--process", "direct", cwd=ops).stdout)
    tid = added.get("id") or added["task"]["id"]
    h1.run("tasks", "start", tid, cwd=ops, env={**h1.env, "TASKS_SESSION": "ghost", "TASKS_SESSION_PID": "999999"})
    h1.run("git", "add", "-A", cwd=ops)
    h1.run("git", "commit", "-qm", "a claim under a dead session", cwd=ops)
    result = Cutover(h1).save(check=False)
    assert result.returncode == 1 and "a retargeted repository has claims" in result.stderr and tid in result.stderr
    assert not Cutover(h1).snap.exists()
```

- [ ] **Step 3: Run it**

The clones hold committed state only (Departure 5). The rehearsal's `save` refuses what the live `save` would. So first check the live checkouts:
- every task record in tack, ops, lore, flows and obs is committed, since a clone without one finds a dependency unreachable;
- `tasks check` prints nothing in tack, ops, lore and flows.

```sh
. "$(tasks root tack-8b7a28 --pretty)/.worktrees/rename-hq-cutover/docs/plans/2026-10-06-rename-to-hq-cutover.env.sh" && \
( for p in tack ops lore flows obs; do r="$(root_of "$p")" || exit 1; \
  [ -z "$(git -C "$r" status --porcelain --untracked-files=all -- tasks)" ] || { echo "UNCOMMITTED RECORDS in $r:"; git -C "$r" status --short -- tasks; exit 1; }; \
  case "$p" in obs) ;; *) [ -z "$(tasks -C "$r" check)" ] || { echo "FINDINGS in $r:"; tasks -C "$r" check; exit 1; };; esac; done ) && echo "live records committed and checks clean"
```

A record left uncommitted by another session, or a finding, belongs to its owner. Ask the user, who decides whether to commit it, resolve it, or wait. On 2026-10-06 the review found two: ops warned `ops-be8b06` depends on the shelved `material-764d8c`, and four other sessions' records were untracked in flows and obs. The two records this task filed (`flows-44890e`, `obs-ff4e76`) were committed then. The live cutover's `save` refuses the same things (Task 2's precondition), so they are worth clearing now.

Then run the rehearsal (in the background with a 60-minute timeout; the build clones six repositories twice, and each scenario restores a copy):

```sh
. "$(tasks root tack-8b7a28 --pretty)/.worktrees/rename-hq-cutover/docs/plans/2026-10-06-rename-to-hq-cutover.env.sh" && cd "$WT" && rm -rf "$STATE/rehearsal" && \
uv run -q --with pytest pytest tools/rehearse_rename_hq.py -q -x --basetemp "$STATE/rehearsal" > "$STATE/rehearsal.log" 2>&1; echo "exit $?"; tail -n 30 "$STATE/rehearsal.log"
```

Expected: `8 passed`.

A failure is a finding about the cutover, not about the rehearsal: an edit's text, a hook that refuses a step's commit, a check that is not clean, a byte that rollback does not restore. Each is fixed in the tool that owns it:
- an edit table, or a step's order, in `rename-hq-steps` (Task 5);
- a restore in `rename-cutover` (Task 2), with a test in `tools/test_rename_cutover.py` that fails first.

Record each fix as a ruling in the ledger, and rerun until all eight pass. The rehearsal changes no live state: `git -C "$TACK" status --porcelain` and `tasks claims` read the same before and after.

- [ ] **Step 4: Record and commit**

```sh
. "$(tasks root tack-8b7a28 --pretty)/.worktrees/rename-hq-cutover/docs/plans/2026-10-06-rename-to-hq-cutover.env.sh" && cd "$WT" && \
tasks note tack-8b7a28 "rehearsal: passed $(date -u +%F) without the trial join (Task 6): cutover and second-host adoption, rollback before and after the commits, the guard on three foreign changes, a dead claim refused; $(tail -n 1 "$STATE/rehearsal.log")" >/dev/null && \
tasks done "$STEP6" "the rehearsal clones the live checkouts into two scratch hosts and passes: cutover, adoption, both rollbacks, the guard, the dead claim" >/dev/null && \
git commit -q -m "test(rename): the rehearsal on clones of the live checkouts (tack-8b7a28)" -- tools/rehearse_rename_hq.py "tasks/$STEP6.md" tasks/tack-8b7a28.md && git log --oneline -1
```

---
### Task 7: Review, merge, and wait for the trial and obs

- [ ] **Step 1: Whole-branch review**

```sh
. "$(tasks root tack-8b7a28 --pretty)/.worktrees/rename-hq-cutover/docs/plans/2026-10-06-rename-to-hq-cutover.env.sh" && cd "$WT" && tasks start "$STEP7" >/dev/null && git log --oneline main..HEAD
```

A fresh-context reviewer on the most capable model reads the spec, this plan, the ledger's rulings and `git diff main...HEAD`. Two questions come above the others:
- Can any step of `rename-hq-steps`, or anything the rehearsal does, write outside the snapshot's repositories, its scratch base, or (for `second-host`) the adopting host's own registry, storage and home?
- Does each rollback in the rehearsal compare everything spec §4 says must come back?

Note the round on `tack-8b7a28` (`review: impl round <n> — …`). Then run corrective rounds, each one fix dispatch and one scoped re-review, while the re-review reproduces Critical or Important findings, up to five. Each fixed finding gets a test that fails first. A fix to a tool the rehearsal runs is followed by a rerun of the rehearsal (Task 6 Step 3).

- [ ] **Step 2: Record the status, close the step, merge, and remove the worktree**

In `docs/specs/2026-10-06-rename-to-hq-design.md`, extend the status line's last sentence:
- before: `steps 4 and 5 and phase 2 get their own plan once tasks-7580d2 has landed.`
- after: `steps 4 and 5 and the rehearsal's tools landed <date> by docs/plans/2026-10-06-rename-to-hq-cutover.md (Tasks 1 to 7); the trial join and the cutover follow it once flows-44890e and obs-ff4e76 have landed.`

In this plan, set the status line to `approved <date>; Tasks 1 to 7 executed <date>`, with the review rounds and any rulings. Then:

```sh
. "$(tasks root tack-8b7a28 --pretty)/.worktrees/rename-hq-cutover/docs/plans/2026-10-06-rename-to-hq-cutover.env.sh" && cd "$WT" && \
tasks done "$STEP7" "reviewed and merged; the rehearsal passes without the trial join" >/dev/null && \
git commit -q -m "docs: the cutover's tools and rehearsal landed (tack-8b7a28)" -- docs/specs/2026-10-06-rename-to-hq-design.md docs/plans/2026-10-06-rename-to-hq-cutover.md "tasks/$STEP7.md" && \
cd "$TACK" && [ -z "$(git status --porcelain --untracked-files=no -- tools agents docs justfile tasks)" ] && \
git merge --no-ff "$BRANCH" -m "Merge branch '$BRANCH' (the rename's cutover tools)" && t just test && \
WT_REAL="$(cd "$WT" && pwd -P)" && [ -z "$(git -C "$WT" status --porcelain)" ] && \
! readlink -f ~/bin/* ~/.local/bin/* ~/.config/systemd/user/* 2>/dev/null | grep -qF "$WT_REAL" && \
tt-report && git worktree unlock "$WT" && git worktree remove "$WT" && git branch -d "$BRANCH" && git log --oneline -3
```

Expected: the merge, `just test` green, and the worktree removed. A tracked task record modified on main (a note written there and not yet committed) stops the guard before `git merge` would abort on it. Commit it on main first, then merge main into the branch if they touch the same record. `tt-report` harvests the worktree's test timings before removal. The rehearsal's scratch base was under the worktree's state directory, so it goes with it.

- [ ] **Step 3: Park on the trial and obs**

```sh
. "$(tasks root tack-8b7a28 --pretty)/docs/plans/2026-10-06-rename-to-hq-cutover.env.sh" && cd "$TACK" && \
tasks park tack-8b7a28 "When flows-44890e and obs-ff4e76 are done and their identity contract is written, a tack session runs docs/plans/2026-10-06-rename-to-hq-cutover.md Task 8 (the trial join, and the whole rehearsal that day); then an ops session runs Task 9." --reason dependency >/dev/null && \
git commit -q -m "chore(tasks): park tack-8b7a28 on flows-44890e and obs-ff4e76 for the cutover" -- tasks/tack-8b7a28.md && git log --oneline -1
```

---

### Task 8: The trial's join in the rehearsal, and the rehearsal on the cutover's day

Runs once `flows-44890e` and `obs-ff4e76` are done, from a tack session, on the day of the window (Task 9 refuses a rehearsal note from another day).

**Files:**
- Modify: `tools/rehearse_rename_hq.py`

**Interfaces:**
- Consumes:
  - flows' `bin/trial-arm census flow-trial-1` (units with `root`, `arm` and `members[].task`);
  - `bin/trial-arm <id>`;
  - `bin/trial-verdict <trial file> --census FILE --as-of DATE`, with the report on stdin;
  - obs's `obs.py index --json [--full] --project P`;
  - `obs.py outcomes report --json --since --until --cohort --units` (a `units` list of rows keyed by `task`);
  - the shared identity contract that `flows-44890e` and `obs-ff4e76` write, which says which id form a member and a row carry.

  These are the commands as of 2026-10-06. Before Step 3, check them against the two tasks' completion notes and the contract. Where they changed, this task's code changes to match, and that is a plan change, noted on `tack-8b7a28` and reviewed before the run.

- [ ] **Step 1: Worktree and record**

```sh
. "$(tasks root tack-8b7a28 --pretty)/docs/plans/2026-10-06-rename-to-hq-cutover.env.sh" && cd "$TACK" && \
( for t in flows-44890e obs-ff4e76; do [ "$(tasks show "$t" | python3 -c 'import json,sys; print(json.load(sys.stdin)["task"]["status"])')" = done ] || { echo "REFUSE: $t is not done"; exit 1; }; done ) && \
tasks start tack-8b7a28 >/dev/null && work-link --ensure .worktrees && git worktree add -q "$WT" -b "$BRANCH8" && \
git worktree lock --reason "on WORK_ROOT storage (host: $(uname -n))" "$WT" && cd "$WT" && just setup >/dev/null && mkdir -p "$STATE" && tasks start "$STEP8" >/dev/null && echo ready
```

- [ ] **Step 2: Write the trial-join scenario**

Append to `tools/rehearse_rename_hq.py` (and add `import hashlib` to its imports):

```python
# --- the trial's join (spec §4, "And the trial's join, end to end") --------------------

TRIAL, ENROLL_FROM, CLOSE_BY, READ_ON = "flow-trial-1", "2026-10-05", "2027-01-10", "2027-02-16"


def arm_of(unit):
    """flow-trial-1's rule (evals/trials/flow-trial-1.md): sha256("flow-trial-1:<root>")[0] & 1."""
    return ("on", "off")[hashlib.sha256(f"{TRIAL}:{unit}".encode()).digest()[0] & 1]


def share_stores(host):
    """obs reads the live session stores, read-only, through the scratch home."""
    for rel in (".claude/projects", ".codex/sessions"):
        (host.home / rel).parent.mkdir(parents=True, exist_ok=True)
        (host.home / rel).symlink_to(Path.home() / rel)


def plant_unit(host):
    """A unit enrolled before the rename whose two id forms hash to different arms."""
    tack = host.path("tack")
    while True:
        added = json.loads(host.run("tasks", "add", "planted trial unit", "--process", "direct", cwd=tack).stdout)
        tid = added.get("id") or added["task"]["id"]
        hex_ = tid.split("-", 1)[1]
        if arm_of(f"tack-{hex_}") != arm_of(f"hq-{hex_}"):
            break
        host.run("tasks", "drop", tid, "not a flipping unit", cwd=tack)
    host.run("tasks", "start", tid, cwd=tack)
    first = host.run(host.path("flows") / "bin" / "trial-arm", tid).stdout.splitlines()[0]
    assert first.startswith(f"{TRIAL}: flow {arm_of(tid)} "), first
    host.run("tasks", "park", tid, "rehearsal", cwd=tack)
    host.run("git", "add", "-A", cwd=tack)
    host.run("git", "commit", "-qm", "a planted trial unit", cwd=tack)
    return hex_


def judge(host, projects, full):
    flows, obs = host.path("flows"), host.path("obs")
    census = host.run(flows / "bin" / "trial-arm", "census", TRIAL).stdout
    for project in projects:
        host.run("python3", obs / "obs.py", "index", "--json", *(["--full"] if full else []), "--project", project)
    report = host.run("python3", obs / "obs.py", "outcomes", "report", "--json", "--since", ENROLL_FROM,
                      "--until", CLOSE_BY, "--cohort", "--units").stdout
    census_file = host.root / f"census-{projects[0]}.json"
    census_file.write_text(census)
    verdict = subprocess.run([str(flows / "bin" / "trial-verdict"), str(flows / "evals" / "trials" / f"{TRIAL}.md"),
                              "--census", str(census_file), "--as-of", READ_ON], input=report, text=True,
                             capture_output=True, env=host.env)
    assert verdict.returncode == 0, verdict.stdout + verdict.stderr
    return json.loads(census), json.loads(report)


def canonical(host, ids):
    rows = resolve(host, sorted(ids))
    return {r["input"]: r["id"] for r in rows if r["status"] == "resolved"}


def test_the_trial_join_survives_the_rename(hosts):
    h1, _ = hosts
    share_stores(h1)
    hex_ = plant_unit(h1)
    census_b, report_b = judge(h1, [OLD, "obs"], full=False)
    cutover = Cutover(h1)
    cutover.save()
    cutover.forward()
    census_a, report_a = judge(h1, [NEW, "obs"], full=True)

    def joined(census, report):
        """What trial-verdict joins: each census member with a report row under exactly
        its string. Comparing canonical forms here would hide a census that says tack-…
        beside a report that says hq-…, the mismatch the spec asks this to catch."""
        rows = {r["task"]: {k: v for k, v in r.items() if k != "task"} for r in report["units"]}
        return {m["task"]: rows[m["task"]] for u in census["units"] for m in u["members"] if m["task"] in rows}

    before, after = joined(census_b, report_b), joined(census_a, report_a)
    assert before, "no census member joined a report row before the rename: the join was not exercised"
    ids = {x for c in (census_b, census_a) for u in c["units"] for x in (u["root"], *(m["task"] for m in u["members"]))}
    names = canonical(h1, ids)
    assert ids <= set(names), f"ids tasks resolve does not know: {sorted(ids - set(names))}"
    assert any(names[t].startswith(f"{NEW}-") for t in before), \
        "no task of the renamed project joined a report row before the rename: coverage came from obs alone"
    after_member = {names[m["task"]]: m["task"] for u in census_a["units"] for m in u["members"]}
    for task, row in before.items():
        now = after_member.get(names[task])
        assert now is not None, f"{task} left the census"
        assert now in after, f"{task}: the census says {now} and the report has no row under that string"
        assert after[now] == row, f"{task}: its outcome row changed"

    def units(census):
        return {names[u["root"]]: (u["arm"], sorted(names[m["task"]] for m in u["members"])) for u in census["units"]}

    after_units = units(census_a)
    for root, (arm, members) in units(census_b).items():
        assert after_units.get(root) == (arm, members), f"unit {root}: arm or membership changed"
    first = h1.run(h1.path("flows") / "bin" / "trial-arm", f"hq-{hex_}").stdout.splitlines()[0]
    assert first.startswith(f"{TRIAL}: flow {arm_of(f'tack-{hex_}')} "), first
```

The cross-run comparison goes through canonical ids, so it holds whichever single id form the contract picked. The join inside each run does not: there, a census member counts only when the report has a row under exactly its string, as `trial-verdict` reads it, and that join must be non-empty. The test requires:
- the join is exercised for the renamed project: at least one of its tasks joins a row before the rename, since obs's rows alone would pass every other condition;
- every member that joined a row before still joins one after, under the string the census now gives it, with the same values. So no member becomes unknown;
- every unit enrolled before keeps its arm and its members;
- the planted unit, whose two id forms hash to different arms, keeps the arm of the listed prefix.

`trial-verdict` must exit 0 on both runs, with the read date met.

- [ ] **Step 3: Run the whole rehearsal**

Run in the background, with a two-hour timeout. Indexing the live stores for two projects, twice, is most of it.

```sh
. "$(tasks root tack-8b7a28 --pretty)/.worktrees/rename-hq-cutover/docs/plans/2026-10-06-rename-to-hq-cutover.env.sh" && cd "$WT" && rm -rf "$STATE/rehearsal" && \
uv run -q --with pytest pytest tools/rehearse_rename_hq.py -q -x --basetemp "$STATE/rehearsal" > "$STATE/rehearsal.log" 2>&1; echo "exit $?"; tail -n 30 "$STATE/rehearsal.log"
```

Expected: `9 passed`. A failure is handled as in Task 6 Step 3: fixed in the tool that owns it, with a test that fails first where that tool has a suite, then the whole rehearsal rerun.

- [ ] **Step 4: Record, review, merge, remove the worktree**

The change is one scenario in the rehearsal. A fresh-context reviewer reads it against spec §4's trial paragraph and the identity contract. Note the round on `tack-8b7a28`.

```sh
. "$(tasks root tack-8b7a28 --pretty)/.worktrees/rename-hq-cutover/docs/plans/2026-10-06-rename-to-hq-cutover.env.sh" && cd "$WT" && \
tasks note tack-8b7a28 "rehearsal: passed $(date -u +%F) with the trial join (Task 8): $(tail -n 1 "$STATE/rehearsal.log")" >/dev/null && \
tasks done "$STEP8" "the rehearsal's trial join passes: arms, outcome rows and the planted unit survive the rename" >/dev/null && \
git commit -q -m "test(rename): the rehearsal runs the flow trial's join end to end (tack-8b7a28)" -- tools/rehearse_rename_hq.py "tasks/$STEP8.md" tasks/tack-8b7a28.md && \
cd "$TACK" && git merge --no-ff "$BRANCH8" -m "Merge branch '$BRANCH8' (the rehearsal's trial join)" && t just test && \
WT_REAL="$(cd "$WT" && pwd -P)" && ! readlink -f ~/bin/* ~/.local/bin/* ~/.config/systemd/user/* 2>/dev/null | grep -qF "$WT_REAL" && \
tt-report && git worktree unlock "$WT" && git worktree remove "$WT" && git branch -d "$BRANCH8" && \
tasks park tack-8b7a28 "An ops session runs docs/plans/2026-10-06-rename-to-hq-cutover.md Task 9 today: the user picks the window and attests first (Step 1)." --waiting-on user --reason approval >/dev/null && \
git commit -q -m "chore(tasks): tack-8b7a28 is ready for its cutover window" -- tasks/tack-8b7a28.md && git log --oneline -3
```

---

### Task 9: The cutover on this host

From a session started in ops, never in tack: step 7 moves the checkout. Every block from Step 2 on sources `$HOME/.local/state/rename-hq/env.sh`.

`save` refuses any live claim and any unclean tree. So this session claims nothing before Step 13: its step record `$STEP9` is started and closed there, after verification. Notes up to Step 5 go on `tack-8b7a28`, which stays parked, and Step 6 commits them before the snapshot.

**Rollback** is defined from Step 7 until the other host adopts (Task 10 Step 2). If any step from 7 to 12 fails, run the rollback block at the end of this task, and stop. Nothing in Tasks 9 and 10 writes outside the snapshot's repositories, both hosts' registries, storage and homes, and the timers.

- [ ] **Step 1: Preconditions from the records, and the user's window**

```sh
. "$(tasks root tack-8b7a28 --pretty)/docs/plans/2026-10-06-rename-to-hq-cutover.env.sh" && cd "$(root_of ops)" && \
( for t in tasks-7580d2 flows-44890e obs-ff4e76 "$STEP1" "$STEP2" "$STEP3" "$STEP4" "$STEP5" "$STEP6" "$STEP7" "$STEP8"; do \
  [ "$(tasks show "$t" | python3 -c 'import json,sys; print(json.load(sys.stdin)["task"]["status"])')" = done ] || { echo "REFUSE: $t is not done"; exit 1; }; done ) && \
tasks show tack-8b7a28 | grep -qF "rehearsal: passed $(date -u +%F) with the trial join" && echo "records ready"
```

Then open the identity contract named in `flows-44890e`'s completion note, and confirm `obs-ff4e76`'s completion note cites it. `tack-8b7a28` is already parked for the user (Task 8 Step 4). Ask the user to pick the window and to attest three things no tool here can see:
- no harness session runs on this host except this ops session;
- the other host is idle in tack, ops, lore and flows;
- the file sync is up to date on both hosts.

On the user's answer, record it verbatim before going on: `tasks note tack-8b7a28 "attest: <the user's words>, <time>"`.

- [ ] **Step 2: The host-local directory, the tools' copies, the second host's name**

```sh
. "$(tasks root tack-8b7a28 --pretty)/docs/plans/2026-10-06-rename-to-hq-cutover.env.sh" && \
{ [ ! -e "$CUT/env.sh" ] || { last="$(. "$CUT/env.sh" && printf %s "$RUN")"; [ -e "$last/rolled-back" ] || [ -e "$last/abandoned" ]; } || { echo "REFUSE: the last attempt was neither rolled back nor abandoned; read $CUT/env.sh"; false; }; } && \
ATTEMPT="attempt-$(date -u +%Y%m%dT%H%M%SZ)" && RUN="$CUT/$ATTEMPT" && mkdir -p "$RUN/bin" && ln -sfn "$ATTEMPT" "$CUT/current" && \
cp "$TACK/tools/rename-cutover" "$TACK/tools/quiesce-timers" "$TACK/tools/rename-hq-steps" "$RUN/bin/" && \
( for p in ops lore flows relay tasks obs; do r="$(root_of "$p")" && [ -d "$r" ] || { echo "REFUSE: no root for $p" >&2; exit 1; }; \
  printf '%s_ROOT=%q\n' "$(printf %s "$p" | tr a-z A-Z)" "$r"; done ) > "$RUN/roots.env" && \
{ printf 'CUT=%q\nATTEMPT=%q\nRUN=%q\nOLD_ROOT=%q\nNEW_ROOT=%q\nSNAP=%q\nT_LOG=%q\n' "$CUT" "$ATTEMPT" "$RUN" "$TACK" "$(dirname "$TACK")/hq" "$RUN/snapshot" "$RUN/last.log"; \
  cat "$RUN/roots.env"; \
  printf 'STEP9=%s\nSTEP10=%s\nSTEP11=%s\n' "$STEP9" "$STEP10" "$STEP11"; \
  sed -n '/^# --- helpers/,$p' "$TACK/docs/plans/2026-10-06-rename-to-hq-cutover.env.sh"; } > "$RUN/env.sh" && cp "$RUN/env.sh" "$CUT/env.sh" && \
printf '%s\n' "<the second host's name, from tailscale status>" > "$CUT/second-host" && cat "$CUT/env.sh" | head -16
```

Replace the placeholder with the host's name before running; the name never enters a committed file. Each attempt gets its own directory, `$RUN`, under `$CUT`, holding the tools' copies, the snapshot, the timers' record and every saved listing. A rolled-back attempt keeps its directory as evidence. Step 2 refuses to start a new attempt unless the last one was rolled back or abandoned. `$CUT/current` links to the attempt in progress, and the other host keeps the same layout. Expected: the roots of tack, ops, lore, flows, relay, tasks and obs, each an existing directory.

- [ ] **Step 3: Preconditions the tool leaves to the runbook**

```sh
. "$HOME/.local/state/rename-hq/env.sh" && cd "$OPS_ROOT" && \
git -C "$OLD_ROOT" worktree list --porcelain | grep '^worktree ' | tail -n +2; \
for b in $(git -C "$OLD_ROOT" for-each-ref --format='%(refname:short)' refs/heads); do echo "$b ahead=$(git -C "$OLD_ROOT" rev-list --count "main..$b")"; done; \
git -C "$OPS_ROOT" grep -l -w tack -- tests/ ; \
need SECOND && on_second 'tasks resolve --help >/dev/null && for d in ~/.config/tasks ~/.local/state/tasks; do [ -d "$d" ] && [ ! -L "$d" ] || echo "NOT A REAL DIRECTORY: $d"; done; systemctl --version | head -1'
```

Act on what it prints. Every item below must hold before Step 4.
- **Extra worktrees.** Each worktree other than the main one is removed, one at a time: its branch has no commits main lacks, no host pointer resolves into it (`readlink -f ~/bin/* ~/.local/bin/* ~/.config/systemd/user/*`), then `tt-report`, `git worktree unlock`, `git worktree remove`. A worktree whose branch is ahead of main stops the runbook: its owner merges it first. On 2026-10-06 the extra worktree was `session-retention-job`, its branch level with main.
- **Branches.** Every local branch other than main is either level with main and deleted, or stops the runbook.
- **Clean trees and clean checks.** `save` refuses an unclean tree and, since Task 2, any `tasks check` output in tack, ops, lore or flows. Clear them now, so the refusal does not come at Step 6:
  - task records other sessions left untracked are committed by their owners, or the user decides;
  - a tracked harness setting the clean filter keeps in the index on purpose (on 2026-10-06, a plugin toggle in `claude/settings.json`) is committed on main as its own change. AGENTS.md rules out stashing it;
  - each `tasks check` finding is resolved with its owner (on 2026-10-06, `ops-be8b06` depended on the shelved `material-764d8c`).
- **ops tests.** The files that name `tack` are exactly the fixtures spec §1 keeps: `test_claim_guard.py`, `test_ops_profile.py`, `test_ops_projects.py` and `test_sessionstart.py`. Any other file is the residue's mirror test or something like it. It gets its edit in `rename-hq-steps`'s ops table and a rehearsal rerun, the same day, before going on.
- **The other host.** It answers, its `tasks` has `resolve`, and both of its tasks directories are real. Its systemd version is recorded in a note on `tack-8b7a28`.

- [ ] **Step 4: Quiesce the timers, on both hosts, before anything shared changes**

List each host's timers with what their services run:

```sh
. "$HOME/.local/state/rename-hq/env.sh" && list_timers && echo "--- second host" && on_second "$(declare -f list_timers); list_timers"
```

Choose each timer whose service does one of these:
- runs `tasks` or `git` across checkouts;
- runs a tool from tack, ops, lore or flows;
- works over the Dropbox tree;
- reads the session stores.

When unsure, include it: pausing a timer costs one missed run. On 2026-10-06 the listing chose this host's `obs-index.timer`, `tt-latency.timer`, `work-link.timer`, `dropbox-ignore-flux.timer` and `session-archive-capture.timer`. It left out the wallpaper, phone-sync, backup, cache-mirror, tmp-clean, recertify, kernel-nudge and pet-reaper timers, after reading what each runs. Write this host's choice to `$RUN/timers` and the other host's to `$RUN/timers.second`, one name per line. Then:

```sh
. "$HOME/.local/state/rename-hq/env.sh" && \
t "$RUN/bin/quiesce-timers" record --state "$RUN/timers.json" $(cat "$RUN/timers") && \
t "$RUN/bin/quiesce-timers" stop --state "$RUN/timers.json" && \
on_second "mkdir -p ~/.local/state/rename-hq/$ATTEMPT/bin && ln -sfn $ATTEMPT ~/.local/state/rename-hq/current" && \
scp -4 -q "$RUN/bin/quiesce-timers" "$RUN/bin/rename-hq-steps" "$SECOND:.local/state/rename-hq/current/bin/" && \
on_second "~/.local/state/rename-hq/current/bin/quiesce-timers record --state ~/.local/state/rename-hq/current/timers.json $(tr '\n' ' ' < "$RUN/timers.second") && ~/.local/state/rename-hq/current/bin/quiesce-timers stop --state ~/.local/state/rename-hq/current/timers.json" && echo "both hosts stopped"
```

Then wait on both, in the background with a timeout of 65 minutes. The obs index can run for 45, and the window starts after it:

```sh
. "$HOME/.local/state/rename-hq/env.sh" && t "$RUN/bin/quiesce-timers" wait --state "$RUN/timers.json" --timeout 3600 && \
on_second '~/.local/state/rename-hq/current/bin/quiesce-timers wait --state ~/.local/state/rename-hq/current/timers.json --timeout 3600' && echo "both hosts quiet"
```

- [ ] **Step 5: The other host's pre-move record and saves**

```sh
. "$HOME/.local/state/rename-hq/env.sh" && on_second 'R="$(tasks root tack-8b7a28 --pretty)" && C=~/.local/state/rename-hq/current && \
python3 "$C/bin/rename-hq-steps" second-host-record --root "$R" --state "$C/second-host.json" && \
cp -a ~/.config/tasks "$C/config" && cp -a ~/.local/state/tasks "$C/state" && \
systemctl --user list-unit-files "session-archive*" --no-legend > "$C/archive-units.txt" && \
find "$HOME" -maxdepth 6 -xtype l 2>/dev/null | sort > "$C/broken-before.txt" && \
python3 -c "import tomllib,os; t=tomllib.load(open(os.path.expanduser(\"~/.config/tasks/projects.toml\"),\"rb\")).get(\"locations\",{}).get(\"tack\",{}); print(\"storage:\", t.get(\"storage\")); print(\"former:\", [e[\"root\"] for e in t.get(\"former\",[])])"'
```

Expected:
- **The storage record.** `second-host-record` ran `init --prefix tack --force` there, found the tree clean, and kept the old root and its storage in `second-host.json`, which Task 10 reads. `storage:` names that host's `.dropbox-work/tack/.worktrees`.
- **`former:`** shows whether that host's own `ai` backfill is there (tasks spec §6, user-owned). If it is absent, note it on `tack-8b7a28` as the stated limit: that host's `ai` paths stay unregistered. It does not stop the cutover.

- [ ] **Step 6: This host's saves, then the snapshot**

```sh
. "$HOME/.local/state/rename-hq/env.sh" && cd "$OPS_ROOT" && \
{ [ -z "$(git -C "$OLD_ROOT" status --porcelain -- tasks)" ] || git -C "$OLD_ROOT" commit -q -m "chore(tasks): the cutover's attestation and preconditions (tack-8b7a28)" -- tasks/; } && \
find "$HOME" -maxdepth 6 -xtype l 2>/dev/null | sort > "$RUN/broken-before.txt" && \
{ readlink "$HOME/.config/systemd/user/timers.target.wants/session-archive-capture.timer" || echo none; } > "$RUN/enable-link.txt" && \
systemctl --user list-unit-files 'session-archive*' --no-legend > "$RUN/archive-units.txt" && \
t "$RUN/bin/rename-cutover" save --snapshot "$SNAP" --checkout "$OLD_ROOT" --new-root "$NEW_ROOT" --old tack --new hq \
  --repo "$OPS_ROOT" --repo "$LORE_ROOT" --repo "$FLOWS_ROOT" --keep codex/config.toml --keep local/codex/trust.toml
```

Expected: `saved <snapshot>`. A refusal names its precondition. Fix that, and rerun this step; nothing has changed yet.

**Abandon before Step 7.** If Steps 3 to 6 refuse and the fix will not fit the window, nothing shared has changed yet, only the timers. Restore both hosts' timers and mark the attempt abandoned. Each restore runs only if that host's timers were recorded:

```sh
. "$HOME/.local/state/rename-hq/env.sh" && [ -d "$OLD_ROOT" ] && [ ! -e "$NEW_ROOT" ] && \
{ [ ! -e "$RUN/timers.json" ] || t "$RUN/bin/quiesce-timers" restore --state "$RUN/timers.json"; } && \
on_second '[ "$(readlink ~/.local/state/rename-hq/current)" = '"$ATTEMPT"' ] || exit 0; [ ! -e ~/.local/state/rename-hq/current/timers.json ] || ~/.local/state/rename-hq/current/bin/quiesce-timers restore --state ~/.local/state/rename-hq/current/timers.json' && \
touch "$RUN/abandoned" && echo "abandoned before apply; both hosts' timers restored"
```

Use this only before Step 7 runs. After `apply`, the rollback block below is the only way back. A snapshot from Step 6 can stay where it is: the next attempt saves its own.

- [ ] **Step 7: Rename and move (irreversible; rollback restores saved originals)**

```sh
. "$HOME/.local/state/rename-hq/env.sh" && cd "$OPS_ROOT" && t "$SNAP/rename-cutover" apply --snapshot "$SNAP"
```

Expected: `applied: tack -> hq at <new root>`.

- [ ] **Step 8: Spec step 4, in hq**

```sh
. "$HOME/.local/state/rename-hq/env.sh" && cd "$OPS_ROOT" && t python3 "$RUN/bin/rename-hq-steps" tack --snapshot "$SNAP" && git -C "$NEW_ROOT" show --stat --oneline HEAD | tail -n 5
```

- [ ] **Step 9: Spec step 5, in ops**

```sh
. "$HOME/.local/state/rename-hq/env.sh" && cd "$OPS_ROOT" && t python3 "$RUN/bin/rename-hq-steps" ops --snapshot "$SNAP" --date "$(date -u +%F)" && git -C "$OPS_ROOT" show --stat --oneline HEAD | tail -n 5
```

- [ ] **Step 10: Spec step 6, in lore and flows**

```sh
. "$HOME/.local/state/rename-hq/env.sh" && cd "$OPS_ROOT" && t python3 "$RUN/bin/rename-hq-steps" lore --snapshot "$SNAP" && t python3 "$RUN/bin/rename-hq-steps" flows --snapshot "$SNAP" && echo "lore and flows committed"
```

- [ ] **Step 11: Spec step 7: links and units**

```sh
. "$HOME/.local/state/rename-hq/env.sh" && cd "$OPS_ROOT" && t "$SNAP/rename-cutover" link --snapshot "$SNAP" && systemctl --user daemon-reload && \
( for u in $(awk '$1 ~ /\.timer$/ && $2 == "enabled" {print $1}' "$RUN/archive-units.txt"); do systemctl --user reenable "$u" || exit 1; done ) && \
{ (cd "$NEW_ROOT" && just link-check >/dev/null) || { (cd "$NEW_ROOT" && just link --apply >/dev/null && just link-check >/dev/null) && echo "converged after the fallback apply"; }; } && echo converged
```

Expected: `converged`. The plan's probe expects no fallback on this host. If it ran, say so in Step 13's note.

- [ ] **Step 12: Verify (spec §5)**

```sh
. "$HOME/.local/state/rename-hq/env.sh" && cd "$OPS_ROOT" && t "$SNAP/rename-cutover" verify --snapshot "$SNAP" && \
find "$HOME" -maxdepth 6 -xtype l 2>/dev/null | sort > "$RUN/broken-after.txt" && \
comm -13 "$RUN/broken-before.txt" "$RUN/broken-after.txt" > "$RUN/broken-new.txt" && [ ! -s "$RUN/broken-new.txt" ] && \
! find "$HOME" -maxdepth 6 -type l -print0 2>/dev/null | xargs -0 readlink -m | grep -qF "$OLD_ROOT/" && \
[ "$(readlink -f "$HOME/.config/systemd/user/timers.target.wants/session-archive-capture.timer")" = "$NEW_ROOT/systemd/user/session-archive-capture.timer" ] && \
systemctl --user list-unit-files 'session-archive*' --no-legend | diff - "$RUN/archive-units.txt" && \
tasks show tack-dcb11a >/dev/null && tasks show ai-4b1878 >/dev/null && \
systemctl --user start session-archive-capture.service && [ "$(systemctl --user show -p Result --value session-archive-capture.service)" = success ] && \
~/.agents/bin/trial-arm hq-dcb11a | head -n 1 | grep -q '^flow-trial-1: flow off (unit ' && ~/.agents/bin/trial-arm status flow-trial-1 >/dev/null && \
(cd "$NEW_ROOT" && t just test) && (cd "$OPS_ROOT" && t just test-fast) && (cd "$LORE_ROOT" && t just test-fast) && (cd "$FLOWS_ROOT" && t just test-fast) && echo "this host verified"
```

Expected: `this host verified`. Its parts are:
- `rename-cutover verify` checks the link drift, `tasks check` in the four, the alias, the `.worktrees` link, and the resolver's answers for the old id, root and storage.
- The broken links: none new since Step 6, and none whose path, read through any link, passes through the old directory.
- The enable link follows the moved unit.
- The archive units match their saved listing, and the capture unit runs cleanly by hand.
- The trial gives `hq-dcb11a` its recorded arm, and its status exits 0. If `flows-44890e` chose a halt, replace those two checks with the halt's own (spec §5).
- The four suites pass. If the residue's mirror test has landed, ops's log shows it ran and was not skipped.

A failure here goes to the rollback block.

- [ ] **Step 13: Restore this host's timers, carry Claude's memory, record**

```sh
. "$HOME/.local/state/rename-hq/env.sh" && cd "$OPS_ROOT" && t "$RUN/bin/quiesce-timers" restore --state "$RUN/timers.json" && \
( for home in "$HOME/.claude" "$HOME/.claude-work"; do old="$home/projects/$(printf %s "$OLD_ROOT" | tr / -)"; new="$home/projects/$(printf %s "$NEW_ROOT" | tr / -)"; \
  [ -d "$old/memory" ] || continue; [ ! -e "$new/memory" ] || { echo "REFUSE: $new/memory exists"; exit 1; }; \
  mkdir -p "$new" && cp -a "$old/memory" "$new/memory" && echo "memory carried in $home" || exit 1; done ) && \
tasks start "$STEP9" >/dev/null && \
tasks done "$STEP9" "this host: renamed, moved, committed in hq, ops, lore and flows, linked, verified (suites green), timers restored, Claude memory carried; rollback stays defined until the other host adopts" >/dev/null && \
tasks park hq-8b7a28 "The user confirms the file sync has carried hq to the other host; then this ops session runs Task 10. Until then the other host's timers stay paused and its sessions start without instructions." --waiting-on user --reason approval >/dev/null && \
git -C "$NEW_ROOT" commit -q -m "chore(tasks): the cutover verified on this host (hq-8b7a28)" -- tasks/ && echo recorded
```

Then ask the user to open one fresh session in each of the four homes in `hq`:
- Claude Code asks once to trust the folder, which is expected.
- Each session's profile line names `[hq]`.
- Codex does not ask to re-trust a hook or the directory.

Record what they report on `hq-8b7a28`.

**Rollback (from Step 7 until Task 10 Step 2).** After Step 13, this host's timers run again, and the user has opened fresh sessions in `hq`. So rollback starts by re-establishing quiescence:
- the user closes every harness session opened since Step 13, and attests again that only this ops session runs (note it on `hq-8b7a28`);
- this host's timers are stopped and drained again, under a fresh record. Before Step 13 that record finds them already stopped, which is harmless.

Then this host rolls back:

```sh
. "$HOME/.local/state/rename-hq/env.sh" && cd "$OPS_ROOT" && RB="$RUN/rollback-$(date -u +%Y%m%dT%H%M%SZ)" && mkdir -p "$RB" && \
t "$RUN/bin/quiesce-timers" record --state "$RB/timers.json" $(cat "$RUN/timers") && \
t "$RUN/bin/quiesce-timers" stop --state "$RB/timers.json" && t "$RUN/bin/quiesce-timers" wait --state "$RB/timers.json" --timeout 3600 && \
t "$SNAP/rename-cutover" rollback --snapshot "$SNAP" && systemctl --user daemon-reload && \
( for u in $(awk '$1 ~ /\.timer$/ && $2 == "enabled" {print $1}' "$RUN/archive-units.txt"); do systemctl --user reenable "$u" || exit 1; done ) && \
[ "$({ readlink "$HOME/.config/systemd/user/timers.target.wants/session-archive-capture.timer" || echo none; })" = "$(cat "$RUN/enable-link.txt")" ] && \
(cd "$OLD_ROOT" && just link-check >/dev/null) && t "$RUN/bin/quiesce-timers" restore --state "$RUN/timers.json" && \
for r in "$OLD_ROOT" "$OPS_ROOT" "$LORE_ROOT" "$FLOWS_ROOT"; do printf '%s %s\n' "$(basename "$r")" "$(git -C "$r" rev-parse HEAD)"; done > "$RUN/restored-heads.txt" && \
echo "rolled back on this host; the attempt is not finished until the other host recovers"
```

The other host's timers stay paused until the sync has carried the restored checkouts there. Its writers would otherwise run against a renamed or half-restored tree. Then, once the user says the sync has settled:

```sh
. "$HOME/.local/state/rename-hq/env.sh" && \
on_second 'R="$(tasks resolve tack --json | python3 -c "import json,sys; print(json.load(sys.stdin)[\"results\"][0][\"root\"])")"; \
test -d "$R" && test ! -e "$(dirname "$R")/hq" && grep -q "^prefix = \"tack\"" "$R/tasks/.config.toml" && \
while read -r name head; do [ "$(git -C "$(dirname "$R")/$name" rev-parse HEAD)" = "$head" ] && [ -z "$(git -C "$(dirname "$R")/$name" status --porcelain)" ] || { echo "NOT YET: $name"; exit 1; }; done && \
cd "$R" && just link-check >/dev/null && echo "the other host sees the restored checkouts"' < "$RUN/restored-heads.txt" && \
on_second '~/.local/state/rename-hq/current/bin/quiesce-timers restore --state ~/.local/state/rename-hq/current/timers.json' && \
touch "$RUN/rolled-back" && echo "the other host's timers restored; the attempt is rolled back"
```

`NOT YET` means the sync has not finished. Wait and rerun, and never restore its timers before this passes. `rolled-back` is written only here, after both hosts have recovered. Step 2 accepts no new attempt before then, so a new attempt cannot repoint `current` and record the other host's still-paused timers as their original state. Then note on `tack-8b7a28` what failed and where. A new attempt starts at Step 1 with a fresh window, and Step 2 gives it its own directory beside this one, which stays as evidence. The other host's `second-host-record` needs no undo: it re-registered the root it already had. The next attempt's Step 5 writes a new record in the new attempt's directory.

---

### Task 10: The other host adopts

On the other host, over ssh, from the same ops session.

- [ ] **Step 1: The sync has carried the move**

```sh
. "$HOME/.local/state/rename-hq/env.sh" && tasks start "$STEP10" >/dev/null && \
on_second 'R="$(tasks resolve tack --json | python3 -c "import json,sys; print(json.load(sys.stdin)[\"results\"][0][\"root\"])")"; N="$(dirname "$R")/hq"; \
test ! -e "$R" && test -d "$N" && grep -q "^prefix = \"hq\"" "$N/tasks/.config.toml" && [ "$(git -C "$N" rev-parse HEAD)" = "'"$(git -C "$NEW_ROOT" rev-parse HEAD)"'" ] && echo "carried to $N"'
```

Expected: `carried to <that host's hq>`. Otherwise wait for the sync, or ask the user to look at it. Do not continue on a partial sync.

- [ ] **Step 2: Adopt (rollback ends here)**

```sh
. "$HOME/.local/state/rename-hq/env.sh" && \
on_second 'R="$(tasks resolve tack --json | python3 -c "import json,sys; print(json.load(sys.stdin)[\"results\"][0][\"root\"])")"; N="$(dirname "$R")/hq"; \
python3 ~/.local/state/rename-hq/current/bin/rename-hq-steps second-host --root "$N" --state ~/.local/state/rename-hq/current/second-host.json && systemctl --user daemon-reload && \
( for u in $(awk '"'"'$1 ~ /\.timer$/ && $2 == "enabled" {print $1}'"'"' ~/.local/state/rename-hq/current/archive-units.txt); do systemctl --user reenable "$u" || exit 1; done ) && \
cd "$N" && { just link-check >/dev/null || { just link --apply >/dev/null && just link-check >/dev/null && echo "converged after the fallback apply"; }; } && echo "second host adopted and converged"' && \
tasks note "$STEP10" "the other host adopted; rollback has ended" >/dev/null
```

`second-host` stops before changing anything if that host's pre-move record is missing or its storage is ambiguous. Rollback has ended at this step. A failure that a rerun cannot finish is left for a person. They work from the attempt directory there: the registry and state copies Step 5 saved, and the record. It is safe to rerun: each part checks whether it is done, so a run interrupted after `tasks rename --adopt` finishes from the record. It also copies that host's own Codex trust table for its old path to its new one, when the shared trust files have one (`trust`, not required). A `File exists` from `work-link` means the `.worktrees` link arrived before its storage: run `work-link` there once and rerun.

- [ ] **Step 3: Verify the other host**

```sh
. "$HOME/.local/state/rename-hq/env.sh" && \
on_second 'N="$(tasks resolve hq --json | python3 -c "import json,sys; print(json.load(sys.stdin)[\"results\"][0][\"root\"])")"; C=~/.local/state/rename-hq/current; \
for p in hq ops lore flows; do r="$(tasks resolve $p --json | python3 -c "import json,sys; print(json.load(sys.stdin)[\"results\"][0][\"root\"])")"; [ -z "$(tasks -C "$r" check)" ] || { echo "findings in $r"; exit 1; }; done; \
tasks show tack-dcb11a >/dev/null && tasks show ai-4b1878 >/dev/null && \
systemctl --user list-unit-files "session-archive*" --no-legend | diff - "$C/archive-units.txt" && \
find "$HOME" -maxdepth 6 -xtype l 2>/dev/null | sort > "$C/broken-after.txt" && [ -z "$(comm -13 "$C/broken-before.txt" "$C/broken-after.txt")" ] && \
! find "$HOME" -maxdepth 6 -type l -print0 2>/dev/null | xargs -0 readlink -m | grep -qF "$(dirname "$N")/tack/" && echo "second host verified"'
```

- [ ] **Step 4: Restore its timers, carry its Claude memory, record**

```sh
. "$HOME/.local/state/rename-hq/env.sh" && \
on_second 'N="$(tasks resolve hq --json | python3 -c "import json,sys; print(json.load(sys.stdin)[\"results\"][0][\"root\"])")"; O="$(dirname "$N")/tack"; \
~/.local/state/rename-hq/current/bin/quiesce-timers restore --state ~/.local/state/rename-hq/current/timers.json && \
for home in "$HOME/.claude" "$HOME/.claude-work"; do old="$home/projects/$(printf %s "$O" | tr / -)"; new="$home/projects/$(printf %s "$N" | tr / -)"; \
  [ -d "$old/memory" ] || continue; [ ! -e "$new/memory" ] || { echo "REFUSE: $new/memory exists"; exit 1; }; \
  mkdir -p "$new" && cp -a "$old/memory" "$new/memory" && echo "memory carried in $home" || exit 1; done' && \
tasks done "$STEP10" "the other host adopted and verified; its timers restored" >/dev/null && \
git -C "$NEW_ROOT" commit -q -m "chore(tasks): the other host adopted hq (hq-8b7a28)" -- tasks/ && echo recorded
```

Then ask the user to open one fresh session per home on that host, as in Task 9 Step 13, and record the result on `hq-8b7a28`.

---

### Task 11: Forward only, then close

- [ ] **Step 1: Retarget the projects outside the snapshot (spec §3.2 step 9)**

```sh
. "$HOME/.local/state/rename-hq/env.sh" && cd "$OPS_ROOT" && tasks start "$STEP11" >/dev/null && \
( for r in $(tasks projects --json | python3 -c 'import json,sys; [print(p["root"]) for p in json.load(sys.stdin)["projects"] if p.get("reachable", True)]'); do \
  case "$r" in "$NEW_ROOT"|"$OPS_ROOT"|"$LORE_ROOT"|"$FLOWS_ROOT") continue;; esac; \
  tasks -C "$r" check 2>/dev/null | grep -qF 'through retired prefix \"tack\"' || continue; \
  t "$SNAP/rename-cutover" retarget --snapshot "$SNAP" --repo "$r" --forward && \
  git -C "$r" commit -q -m "chore(tasks): retarget dependencies on retired tack- ids (hq-8b7a28)" -- $(git -C "$r" diff --name-only -- tasks) && \
  echo "retargeted in $r" || exit 1; done )
```

Expected on 2026-10-06's evidence: relay and tasks. Each commit names only the task files the retarget changed. Then `tasks check` is clean in each.

- [ ] **Step 2: Forget the old directories' Codex trust, on both hosts' paths**

The trust files are shared through the sync. So one `forget` per old path removes it for both hosts, and the second host's old path comes from its record. The two paths are the same when both hosts keep the checkout at the same path, and the second host's may never have been trusted. So each distinct path is forgotten only where it has a table, as `second-host` copies one only where it has one.

```sh
. "$HOME/.local/state/rename-hq/env.sh" && \
SECOND_OLD="$(on_second 'python3 -c "import json,os; print(json.load(open(os.path.expanduser(\"~/.local/state/rename-hq/current/second-host.json\")))[\"old_root\"])"')" && need SECOND_OLD && \
( for old in $(printf '%s\n' "$OLD_ROOT" "$SECOND_OLD" | sort -u); do \
    grep -qF "[projects.\"$old\"]" "$NEW_ROOT/codex/config.toml" "$NEW_ROOT/local/codex/trust.toml" || { echo "no trust table for $old"; continue; }; \
    python3 "$NEW_ROOT/.githooks/codex-trust" forget "$old" || exit 1; done ) && \
! grep -qF -e "[projects.\"$OLD_ROOT\"]" -e "[projects.\"$SECOND_OLD\"]" "$NEW_ROOT/codex/config.toml" "$NEW_ROOT/local/codex/trust.toml" && echo forgotten
```

- [ ] **Step 3: obs follows the rename on live data**

The obs index timer is back in its recorded state. Run the index once by hand, in the background with a 60-minute timeout, and read its result:

```sh
. "$HOME/.local/state/rename-hq/env.sh" && systemctl --user start obs-index.service && [ "$(systemctl --user show -p Result --value obs-index.service)" = success ] && echo "obs index completed"
```

Then run, against live data, the check `obs-ff4e76`'s completion note names: a session recorded before the rename joins its task, and that task appears in the outcome rows. Its output goes in a note on `$STEP11`.

- [ ] **Step 4: GitHub (gated, outward-facing)**

Ask the user at this moment whether to rename the repository now, or to record it as deferred.
- **On a yes:**
  1. Run `gh auth status` and confirm the active account owns `khughitt/tack`.
  2. Then: `gh repo rename harness-quarters -R khughitt/tack --yes`, then `git -C "$NEW_ROOT" remote set-url origin git@github.com:khughitt/harness-quarters.git`, then `git -C "$NEW_ROOT" ls-remote origin HEAD`.
  3. The other host shares `.git` through the sync and needs nothing.
- **On a deferral:** `tasks note "$STEP11" "GitHub rename deferred by the user, <date>"`.

- [ ] **Step 5: Remove this rename's own tools, record the status, close**

In a worktree of hq (`work-link --ensure .worktrees`, then `git worktree add .worktrees/rename-hq-close -b chore/rename-hq-close`, lock it, `just setup`):
- Remove `tools/rename-hq-steps`, `tools/test_rename_hq_steps.py` and `tools/rehearse_rename_hq.py`. They name this rename's text, and the next rename writes its own. `rename-cutover` and `quiesce-timers` stay.
- In `docs/specs/2026-10-06-rename-to-hq-design.md`, the status line records the cutover date, both hosts, and the GitHub outcome.
- In this plan, the status line reads `executed <dates>`, with an execution record: review rounds, rulings, deferred minors, the fallback apply if it ran, and the other host's `ai` backfill state.

Then run `just test`, commit, review the diff (small: deletions and status lines), merge, `tt-report`, and remove the worktree. Close:

```sh
. "$HOME/.local/state/rename-hq/env.sh" && cd "$NEW_ROOT" && \
tasks done "$STEP11" "forward retargets in relay and tasks; old trust forgotten; obs follows on live data; GitHub <renamed|deferred>; this rename's tools removed" >/dev/null && \
tasks done ops-593133 "the rename to hq ran on both hosts (hq-8b7a28)" >/dev/null && \
tasks done hq-8b7a28 "tack is harness-quarters (hq) on both hosts: four repositories committed and tasks check clean, relay and tasks retargeted, the parent spec records the name, GitHub <renamed|deferred>" >/dev/null && \
git -C "$NEW_ROOT" commit -q -m "chore(tasks): close the rename to hq (hq-8b7a28)" -- tasks/ && \
git -C "$OPS_ROOT" commit -q -m "chore(tasks): close ops-593133" -- tasks/ops-593133.md && \
rm -rf "$CUT" && on_second 'rm -rf ~/.local/state/rename-hq' && echo closed
```

The host-local directories go last, once both hosts are verified and the task is closed. They hold a registry copy and the snapshot, and nothing reads them after this.
