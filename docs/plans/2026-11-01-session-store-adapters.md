# Session-Store Adapters Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Put each harness's session-store knowledge behind one adapter module, move Claude Code and Codex behind it unchanged, and add agy through it to `hq sessions`, `session-archive`, `session-episodes` and the session-logs skill.

**Architecture:** A new package `tools/harness_stores/` holds a frozen `Adapter` per harness and an ordered registry. `hq sessions` and `session-archive` loop over the registry; `session-episodes` takes its store roots from it and keeps its own per-harness transcript parsing. Archive sources gain `required`, `append_only` and directory/file selectors so an optional, non-append source (agy's summaries database) fits the existing capture contract.

**Tech Stack:** Python 3.14 standard library (`sqlite3`, `tomllib`, `urllib.parse`), pytest via `uv run --with pytest`.

**Spec:** `docs/specs/2026-11-01-session-store-adapters-design.md` (accepted at 3c95c8a, sha256 `7e5b073c62b6fc59f42c56d6d6337f907d255e3771106a7907879bb58e265800`).

## Global Constraints

- Claude Code and Codex behaviour is byte-identical: rows, footer segments, launch argv and environment, archive decisions, `hq sessions --harness claude|codex` output, and `session-episodes extract`'s default output and stderr summary.
- `agents/bin/session-episodes` stays standard-library only; it imports `harness_stores` by resolving its own real path to `<hq>/tools` and exits with an error naming the path when the import fails, never falling back to built-in roots.
- Tests never read live homes: temporary directories and fixtures only; a subprocess gets an environment built key by key (`PATH`, `HOME` under `tmp_path`, each variable it reads).
- A present home whose metadata is missing, unreadable or at an unexpected schema raises `SourceError`; no silent fallback.
- Capability facts are edited here and read only through `tools/harness-facts`; `unknown` is an answer, never a default.
- Canonical harness slugs: `claude-code`, `codex`, `agy`. `hq sessions` aliases: `claude`, `codex`, `agy`.
- Until 2027-02-16 (flow-trial-1 readout), `session-episodes extract` reads agy only when `--harness agy` is given.
- Test routes (no `.tt.toml`: suite policy applies): focused `uv run -q --with pytest pytest <file> -q` for `tools/`, `python3 -m pytest agents/bin/test_session_episodes.py -q` for episodes; `just test` before each commit that touches more than one test file and at the end of every task.
- Conventional commits; no AI attribution.

## Review Focus

1. A workspace URI with spaces or `%`-escapes (`file:///home/u/my%20proj`) lists and resumes in `/home/u/my proj` (Task 4).
2. agy's summaries database locked by a writer while `hq sessions` reads it: an error naming the file, not a traceback (Task 4).
3. A host with no agy home: `hq sessions` lists Claude Code and Codex and adds `absent: agy` to the footer, exit 0 (Task 4).
4. An archive host where `just link --apply` created the agy home but agy never ran: capture skips agy and reports `ok`; once agy has been captured, a vanished `brain/` aborts with exit 2 (Task 3, Task 5).
5. `session-episodes extract` with no `--harness` on a host full of agy transcripts: output and stderr identical to a run with no agy home (Task 6).

---

### Task 1: The adapter package, with `hq sessions` on Claude Code and Codex

**Files:**
- Create: `tools/harness_stores/__init__.py`, `tools/harness_stores/model.py`, `tools/harness_stores/claude.py`, `tools/harness_stores/codex.py`
- Create: `tools/test_harness_stores.py`
- Delete: `tools/hq_cli/sessions.py` (its contents move to `model.py`, `claude.py`, `codex.py`)
- Modify: `tools/hq_cli/cli.py` (`parser`, `collect`, `format_rows`, `main`), `tools/hq_cli/launch.py` (`argv`, `environment`, `HOME_VARIABLES` removed), `tools/test_hq_sessions.py` (imports only)

**Interfaces:**
- Produces, in `harness_stores/model.py`:
  - `class SourceError(Exception)` (moved unchanged)
  - `@dataclass(frozen=True) class Home: name: str; harness: str; kind: str; path: Path` (`harness` is the adapter alias, as today)
  - `@dataclass(frozen=True) class Session: home: Home; id: str; cwd: str | None; recency_ms: int; label: str; transcript: Path; excluded: str | None = None; archived: bool = False`
  - `@dataclass(frozen=True) class Adapter:` fields `slug: str`, `alias: str`, `colour: color.Colour`, `home_variable: str | None`, `homes: Callable[[Path], tuple[Home, ...]]`, `list_sessions: Callable[[Home, bool], tuple[list[Session], dict[str, int]]]`, `notes_segment: Callable[[dict[str, int]], str | None]`, `exclusion_reasons: tuple[str, ...]`, `resume_argv: Callable[[Session, list[str]], list[str]]`, `archive_sources: Callable[[Path], tuple]` (Task 2 fills it; Task 1 sets it to return `()`), `episode_env: str`, `episode_root: Callable[[Path], Path]` (default root under the user home)
- Produces, in `harness_stores/__init__.py`: `ADAPTERS: tuple[Adapter, ...]` (claude, codex; agy appended in Task 4), `by_alias(alias: str) -> Adapter`, `by_slug(slug: str) -> Adapter`, `homes(user_home: Path) -> tuple[Home, ...]` (every adapter's, registry order)
- Claude: `exclusion_reasons = ("transcript gone",)`, notes keys `without_id`, `malformed`, `notes_segment` returns `f"skipped claude history lines: {n['without_id']} without sessionId, {n['malformed']} malformed"`, `home_variable = "CLAUDE_CONFIG_DIR"`, `resume_argv = ["claude", *flags, "--resume", id]`, `episode_env = "SESSION_LOGS_CLAUDE"`, root `~/.claude/projects`.
- Codex: `exclusion_reasons = ("non-interactive", "transcript gone")`, `notes_segment` returns `None`, `home_variable = "CODEX_HOME"`, `resume_argv = ["codex", *flags, "resume", id]`, `episode_env = "SESSION_LOGS_CODEX"`, root `~/.codex/sessions`.

- [ ] **Step 1: Write the failing tests** in `tools/test_harness_stores.py`:

```python
def test_every_adapter_slug_is_a_declared_harness():
    declared = json.loads(subprocess.run([str(TOOLS / "harness-facts"), "list"], capture_output=True,
                          text=True, check=True, env=clean_env).stdout)["harnesses"]
    assert {a.slug for a in harness_stores.ADAPTERS} <= set(declared)

def test_aliases_and_slugs_are_unique():
    assert len({a.alias for a in harness_stores.ADAPTERS}) == len(harness_stores.ADAPTERS)
    assert len({a.slug for a in harness_stores.ADAPTERS}) == len(harness_stores.ADAPTERS)

def test_claude_and_codex_order_and_values():
    assert [(a.alias, a.slug) for a in harness_stores.ADAPTERS[:2]] == [("claude", "claude-code"), ("codex", "codex")]
```

`harness-facts list` prints `{"schema": 1, "harnesses": [...], "facts": {...}}`; reading it through the command keeps the test valid when hq-2eba07 moves the list into `harnesses.toml`.

- [ ] **Step 2: Run** `uv run -q --with pytest pytest tools/test_harness_stores.py -q`. Expected: FAIL, `ModuleNotFoundError: harness_stores`.

- [ ] **Step 3: Create the package.** Move `SourceError`, `Home`, `Session`, `claude_recency_ms`, `claude_transcripts`, `read_claude`, `CODEX_COLUMNS`, `check_thread`, `read_codex` out of `hq_cli/sessions.py` into `model.py`, `claude.py`, `codex.py` unchanged in behaviour; `read_claude` returns `(sessions, {"without_id": n, "malformed": m})` in place of `Skipped`. `cli.collect` loops `harness_stores.ADAPTERS`, calls `adapter.list_sessions(home, args.archived)`, filters with `keep` before counting (today's order), sums notes per adapter, and builds the footer: `skipped …` segments from `notes_segment` for present harnesses in registry order, then `excluded: ` + `"; ".join(f"{alias} " + ", ".join(f"{count} {reason}" for reason in exclusion_reasons))`. `--harness` choices are the registry aliases. `format_rows` takes the hue from `by_alias(s.home.harness).colour`. `launch.argv` calls `by_alias(...).resume_argv`; `launch.environment` sets the session adapter's `home_variable` for a work home and pops every adapter's non-None `home_variable` for a personal one. `here_filter` returns False for `cwd is None`.

- [ ] **Step 4: Run** `uv run -q --with pytest pytest tools/test_harness_stores.py tools/test_hq_sessions.py -q`. Expected: all pass with only import lines changed in `test_hq_sessions.py`.

- [ ] **Step 5: Run** `just test`; expected pass. **Commit** `refactor(hq): move hq sessions harness logic behind harness_stores adapters (hq-57d68e)`.

---

### Task 2: Archive sources and prune hooks from the adapters

**Files:**
- Modify: `tools/session_archive/config.py` (`Source`, `sources` removed), `tools/session_archive/prune.py` (`_facts`, `_decide`, `prune_run`), `tools/session_archive/decide.py` (`is_transcript` moves into the hooks; the `f.harness == "codex"` identity rule reads a flag), `tools/session_archive/cli.py` (`main` takes the table from `harness_stores.archive_sources`), `tools/session_archive/testing.py`, `tools/harness_stores/{__init__,claude,codex}.py`
- Test: `tools/test_session_archive_config.py`, the `test_session_archive_prune_*` and `_units`, `_eligibility`, `_decide` tests (fixture wiring only)

**Interfaces:**
- Produces, in `session_archive/config.py`:
  - `@dataclass(frozen=True) class PruneHooks: harness: str; units: Callable[[Source], list[Unit]]; delete_unit: Callable[[Unit, Context], str]; is_transcript: Callable[[str], bool]; thread_id: Callable[[Path], str | None]; needs_probe: bool; thread_identity: bool`
  - `@dataclass(frozen=True) class Source: name: str; harness: str; home: Path; root: Path; prune: PruneHooks | None; required: bool = True; append_only: bool = True; descend: Callable[[str], bool] = ALL; select: Callable[[str], bool] = ALL` (`ALL = lambda relpath: True`; `harness` is the slug; `prune is None` replaces `pruned=False`)
- Produces, in `harness_stores/__init__.py`: `archive_sources(user_home: Path) -> tuple[Source, ...]`, every adapter's in registry order. The Claude and Codex adapters import `session_archive` modules inside their `archive_sources` function to avoid an import cycle.
- Claude/Codex rows keep today's names, homes, roots and prune membership: `claude` and `claude-work` and `codex` pruned; `codex-archived` and `codex-work` not.

- [ ] **Step 1: Update** `test_sources_table_matches_spec` to compare `harness_stores.archive_sources(tmp_path)` with the five rows above (name, harness slug, home, root, `prune is not None`, `required`, `append_only`). Add `test_no_kind_branches_remain`: `grep`-free check that `prune.py`, `decide.py` and `inputs.py` source text contains neither `kind == "claude"` nor `kind == "codex"` nor `.kind ==`.
- [ ] **Step 2: Run** `uv run -q --with pytest pytest tools/test_session_archive_config.py -q`. Expected: FAIL (no `harness_stores.archive_sources`).
- [ ] **Step 3: Implement.** `prune_run` iterates `source.prune.units(source)` for sources with `prune`; `_decide` uses `hooks.needs_probe` (Codex true) for `kind:codex-unprobed` and `hooks.delete_unit`; `_facts` uses `hooks.is_transcript`, `hooks.harness` (`claude-code`/`codex`, the obs label) and `hooks.thread_id`; `decide.py`'s Codex identity rule becomes `f.thread_identity`. `inputs.py`'s `harness == "codex"` check parses obs state, not a source, and stays.
- [ ] **Step 4: Run** `uv run -q --with pytest pytest tools -q -k session_archive`. Expected: all pass.
- [ ] **Step 5: Run** `just test`; **commit** `refactor(session-archive): take sources and prune hooks from harness_stores (hq-57d68e)`.

---

### Task 3: Optional sources, selectors and non-append capture

**Files:**
- Modify: `tools/session_archive/config.py` (`check_sources`), `tools/session_archive/capture.py` (`walk_files`, `capture_file`, `capture_run`), `tools/session_archive/manifest.py` (`has_source`), `tools/session_archive/cli.py` (`main`, `cmd_capture`)
- Test: `tools/test_session_archive_config.py`, `tools/test_session_archive_capture.py`, `tools/test_session_archive_capture_run.py`

**Interfaces:**
- Consumes: `Source` from Task 2.
- Produces:
  - `Manifest.has_source(source: str) -> bool` (any `versions` row with that source)
  - `check_sources(table, captured: Callable[[str], bool]) -> dict[str, str]`: raises `HostGateError` for a symlinked `root` or symlinked `home` (any source), and for a missing root of a required source or of an optional source with `captured(name)`; returns `{name: "root absent, never captured"}` for skipped optional sources. Missing means `not os.path.lexists(root)`. `main` opens the manifest read-only when it exists (absent manifest: nothing captured) and passes `has_source`.
  - `walk_files(top, errors=None, descend: Callable[[str], bool] = ALL)`: does not open a subdirectory whose root-relative path fails `descend`.
  - `capture_file(..., append_only: bool = True)`: when `append_only` is false and the copy does not extend the mirror, rotate as `promote` does (previous mirror hard-linked to `version_location(source, relpath, mirror.captured_at)` and its manifest row moved there, new copy installed at the mirror path), outcome `copied`.
  - `capture_run(root, manifest, sources, skipped: dict[str, str])`: skipped sources get `report[name] = {"skipped": reason}` and are not walked; files failing `source.select` are not counted; `ok` ignores skipped entries.

- [ ] **Step 1: Write the failing tests:**
  - `test_optional_source_with_absent_root_is_skipped_when_never_captured` (returns `{"x": "root absent, never captured"}`, no raise)
  - `test_optional_source_with_absent_root_aborts_once_captured` (`captured` returns True → `HostGateError` naming the root)
  - `test_required_source_with_absent_root_still_aborts`
  - `test_symlinked_home_aborts` (home is a symlink to a real directory holding the root)
  - `test_walk_does_not_open_undescended_directories` (an unreadable `chunks/` directory under a denied path produces no error)
  - `test_non_append_rewrite_replaces_mirror_and_keeps_previous_version`: capture `b"one"`, rewrite to `b"two!"` with a new mtime, capture with `append_only=False` → outcome `copied`, mirror bytes `b"two!"`, one `versions/` file with `b"one"`, `manifest.diverged() == []`
  - `test_append_only_rewrite_still_diverges` (today's behaviour, unchanged)
  - `test_capture_run_reports_skipped_source_and_stays_ok`
- [ ] **Step 2: Run** the three test files; expected FAIL on the new tests.
- [ ] **Step 3: Implement** the interfaces above.
- [ ] **Step 4: Run** the three files; expected PASS.
- [ ] **Step 5: Run** `just test`; **commit** `feat(session-archive): optional sources, directory selectors and non-append capture (hq-57d68e)`.

---

### Task 4: The agy adapter in `hq sessions`

**Files:**
- Create: `tools/harness_stores/agy.py`
- Modify: `tools/harness_stores/__init__.py` (register agy third), `tools/hq_cli/color.py` (`AGY`), `tools/hq.toml` (`[homes.agy]`), `tools/hq` docstring, `tools/hq_cli/cli.py` (`description` names agy)
- Test: `tools/test_harness_stores.py`, `tools/test_hq_sessions.py`

**Interfaces:**
- Produces: `agy.ADAPTER` with `slug = alias = "agy"`, `home_variable = None`, one `Home("agy", "agy", "personal", user_home / ".gemini" / "antigravity-cli")`, `exclusion_reasons = ("non-interactive", "transcript gone", "no workspace")`, `notes_segment` → `None`, `resume_argv = ["agy", *flags, "--conversation", id]`, `episode_env = "SESSION_LOGS_AGY"`, episode root = the home.
- `agy.read_agy(home: Home) -> tuple[list[Session], dict[str, int]]`: reads `conversation_summaries.db` `mode=ro`; required columns `conversation_id, title, preview, workspace_uris, last_modified_time, parent_conversation_id`; missing file, missing table or column, `sqlite3.Error`, or a value of the wrong shape → `SourceError` naming the file and "agy's summary schema changed" for shape problems. `cwd` from the first `workspace_uris` entry via `urlparse` + `unquote` (scheme `file`, netloc `""` or `localhost`, absolute path, else `SourceError`); empty list → `cwd=None`, excluded `no workspace`. `recency_ms` from `last_modified_time` (nanosecond fraction truncated to microseconds before parsing). `label` = `title` or `preview`. `transcript = home/"brain"/id/".system_generated"/"logs"/"transcript_full.jsonl"`. Non-empty parent → `non-interactive`; absent transcript → `transcript gone`.
- `color.AGY = Colour(oklch(L, C, H), index)`, chosen so `test_colors_read_on_dark_and_light_backgrounds` and the extended hue test pass.

- [ ] **Step 1: Write the failing tests** (fixture helper `agy_db(home, rows)` creating the table with the live column set and `agy_transcript(home, id)`):
  - `test_agy_row_shows_harness_cwd_and_title`
  - `test_agy_label_falls_back_to_preview`
  - `test_agy_subagent_rows_are_counted_non_interactive` (footer segment `agy 1 non-interactive, 0 transcript gone, 0 no workspace`)
  - `test_agy_row_without_transcript_is_counted_gone`
  - `test_agy_workspace_uri_is_percent_decoded` (`file:///…/my%20proj` → `…/my proj`; Review Focus 1)
  - `test_agy_row_without_workspace_is_excluded_and_never_matches_here`
  - `test_agy_non_file_uri_is_an_error_naming_the_file`
  - `test_agy_schema_drift_is_an_error_naming_the_file` (parametrized over the six columns)
  - `test_agy_locked_database_is_an_error_naming_the_file` (a second connection holds `BEGIN EXCLUSIVE`; Review Focus 2)
  - `test_absent_agy_home_is_named_not_an_error` (Review Focus 3)
  - `test_launch_agy_passes_flags_and_conversation_id` (stub `agy` records argv: `["agy", "--dangerously-skip-permissions", "--conversation", id]`, cwd the decoded path)
  - `test_filter_harness_agy`
  - extend `test_tracked_launch_config_matches_the_users_aliases` with `"agy": ["--dangerously-skip-permissions"]`
  - change `test_harness_hues_are_apart` to every pair of registered adapter colours, distance `>= 15` (×100 OKLab), both truecolor and 256
  - update existing exact-footer expectations that now gain ` · absent: agy` (the `Env` fixture creates no agy home)
- [ ] **Step 2: Run** `uv run -q --with pytest pytest tools/test_harness_stores.py tools/test_hq_sessions.py -q`; expected FAIL on the new tests.
- [ ] **Step 3: Implement** `agy.py`, the registration, `AGY`, `[homes.agy] flags = ["--dangerously-skip-permissions"]`.
- [ ] **Step 4: Run** the two files; expected PASS. Then a live read-only smoke: `tools/hq sessions --harness agy -n 5` lists this host's agy conversations with their workspaces (no `-i`).
- [ ] **Step 5: Run** `just test`; **commit** `feat(hq): list and resume agy conversations in hq sessions (hq-57d68e)`.

---

### Task 5: agy archive sources

**Files:**
- Modify: `tools/harness_stores/agy.py` (`archive_sources`)
- Test: `tools/test_session_archive_config.py`, `tools/test_session_archive_capture_run.py`

**Interfaces:**
- Consumes: `Source`, `check_sources`, `capture_run` from Tasks 2–3.
- Produces two rows, both `required=False`, `prune=None`:
  - `Source("agy", "agy", home, home/"brain", …, append_only=True, descend=<relpath has 1 part, or is "<id>/.system_generated" or "<id>/.system_generated/logs">, select=<relpath matches ^[^/]+/\.system_generated/logs/transcript(_full)?\.jsonl$>)`
  - `Source("agy-summaries", "agy", home, home, …, append_only=False, descend=lambda r: False, select=lambda r: r == "conversation_summaries.db")`

- [ ] **Step 1: Write the failing tests:**
  - `test_sources_table_matches_spec` gains the two agy rows
  - `test_agy_capture_takes_only_transcripts_and_the_summaries_db`: a fixture home with `brain/<id>/.system_generated/logs/{transcript,transcript_full}.jsonl`, `logs/chunks/transcript/00000000.jsonl`, `steps/1/output.txt`, `scratch/x`, `task.md`, `conversations/<id>.db`, `conversation_summaries.db` → mirror holds exactly the two transcripts and the summaries db
  - `test_agy_summaries_rewrite_replaces_mirror` (rewrite the db between runs → `copied`, `status` lists no `diverged`)
  - `test_linked_never_run_agy_home_is_skipped` (home exists with `settings.json` only; `main capture` exits 0, report `agy: {"skipped": …}`; `agy-summaries` scans 0 files; Review Focus 4)
  - `test_agy_brain_vanishing_after_capture_aborts` (exit 2)
- [ ] **Step 2: Run** the two files; expected FAIL.
- [ ] **Step 3: Implement** `agy.archive_sources`.
- [ ] **Step 4: Run** the two files; expected PASS.
- [ ] **Step 5: Run** `just test`; **commit** `feat(session-archive): capture agy transcripts and its summaries database (hq-57d68e)`.

---

### Task 6: session-episodes roots from the registry, and the agy reader

**Files:**
- Modify: `agents/bin/session-episodes`, `agents/bin/test_session_episodes.py` (loader sets `se.__dict__["__file__"] = str(SCRIPT)` before `exec`), `agents/skills/session-logs/SKILL.md`

**Interfaces:**
- Consumes: `harness_stores.ADAPTERS`, `by_slug`, each adapter's `episode_env`, `episode_root`, `alias`.
- Produces in `session-episodes`:
  - `AGY_HARNESS = "agy"`; `INTERACTIVE[AGY_HARNESS] = ("agy",)`; `AGY_WAIT_TOOLS = {"ask_question"}`
  - `READERS: dict[str, tuple[str, Callable[[Path], Session | None], Callable[[Path], Session], Callable[[Session, int], Turn]]]` mapping slug → (glob relative to the root, header, reader, turn function). agy's glob is `brain/*/.system_generated/logs/transcript_full.jsonl`.
  - `scan_stores(roots: dict[str, Path], since_ms: int | None = None) -> list[Session]` (slug → root, iterated in the given order)
  - `_roots(env: dict, harnesses: tuple[str, ...]) -> dict[str, Path]`: `env[adapter.episode_env]` or `adapter.episode_root(Path(env["HOME"]))`
  - `_tail_turn(session, anchor_index, wait_tools)`: today's `_claude_turn` with `WAIT_TOOLS` made a parameter; Claude passes `WAIT_TOOLS`, agy `AGY_WAIT_TOOLS`. `turn_after` and `_session_for` dispatch through `READERS` by `session.harness` / the ref's harness.
  - `agy_header(path) -> Session`, `read_agy(path) -> Session`. Session id = `path.parents[2].name`; `subagent` = no `USER_INPUT` step with `source == "USER_EXPLICIT"`; `entrypoint = "agy"`; a line that is not a JSON object with `type` and `step_index` raises `SystemExit` naming agy and the file.
  - Events: human = text between `<USER_REQUEST>` and `</USER_REQUEST>`, stripped; assistant per `PLANNER_RESPONSE` (`text_only` = non-empty `content` and no `tool_calls`; `pending` = its call ids); `tool_call` per call with `call_id = f"{conversation}:{step_index}:{k}"`, `commands = (args["CommandLine"],)` for `run_command`; the k-th `GENERIC` after a planner step is call k's result, except: `status == "RUNNING"` with `background task with task id: <bg>` records `<bg> → call_id` and emits nothing; `status == "ERROR"` emits a result whose text is `"error: " + content` so `has_error_line` treats it as an error; a `SYSTEM_MESSAGE` naming `sender=<bg>` emits the pending call's result (`finished with result:` → the text after it; `was canceled with result:` → `"error: canceled: " + text`); `ERROR_MESSAGE` emits `Event("error", …)`; surplus `GENERIC` steps and unpaired calls emit nothing.
  - `extract` takes `--harness` (`action="append"`, choices the registry slugs; default `("claude-code", "codex")`); `summary["roots"]` keyed by alias and `summary["missing_roots"]` in the selected order.

- [ ] **Step 1: Write the failing tests** with fixture builders for agy steps:
  - `test_default_extract_is_identical_with_and_without_agy_home` (same `HOME` fixture twice, the second with agy transcripts holding a `tasks start` anchor; byte-equal outputs and stderr; Review Focus 5)
  - `test_import_failure_names_the_tools_path` (run a copy of the script outside the checkout; non-zero exit, message names the expected `tools` path)
  - `test_agy_human_text_is_the_user_request_only`
  - `test_agy_subagent_is_a_transcript_without_user_explicit_input`
  - `test_agy_backgrounded_tasks_start_confirms_from_its_system_message` (anchor confirmed via `ids_in_result`)
  - `test_agy_cancelled_background_command_is_an_error_result` (never confirms)
  - `test_agy_error_generic_is_an_error_result`
  - `test_agy_unpaired_calls_have_no_result`
  - `test_agy_turn_ending_in_text_after_background_start_is_completed`
  - `test_agy_turn_waiting_on_ask_question_is_wait`
  - `test_agy_turn_ending_in_error_message_is_unknown`
  - `test_show_dispatches_agy_refs_without_harness_flag`
  - `test_malformed_agy_line_stops_the_run_naming_agy`
- [ ] **Step 2: Run** `python3 -m pytest agents/bin/test_session_episodes.py -q`; expected FAIL on the new tests.
- [ ] **Step 3: Implement** the interfaces above. Update `SKILL.md`: an agy row in Stores (`~/.gemini/antigravity-cli/brain/<id>/.system_generated/logs/transcript_full.jsonl`, one step per line, subagents as separate conversations), agy record shapes, its human-or-injected rule, the three pairing cases, finding the session behind a task (`agy:<id>` provenance; tool-call search over `PLANNER_RESPONSE.tool_calls[].args.CommandLine`), and that `extract` reads agy only with `--harness agy` until the readout.
- [ ] **Step 4: Run** the test file; expected PASS. Live read-only smoke: `agents/bin/session-episodes extract --harness agy --since 3 --out <scratch>/agy.jsonl` runs and its stderr summary counts agy files.
- [ ] **Step 5: Run** `just test`; **commit** `feat(session-episodes): read agy transcripts on request, roots from harness_stores (hq-57d68e)`.

---

### Task 7: Capability facts and the runbook

**Files:**
- Modify: `facts/capabilities.toml`, `docs/runbooks/adding-a-harness.md` (section 7), `README.md` (where it lists `hq sessions` homes or session-archive sources)

**Interfaces:**
- Consumes: what Tasks 4–6 found.
- Produces facts (names final here; types per the file's schema):
  - `tool-result-call-ids` (boolean): "A tool result in the harness's transcript names the call it answers." agy `probed` false (1.4.12, 2026-11-01, evidence hq-57d68e, note: positional pairing; backgrounded commands report later in a system message). Claude Code and Codex `probed` true where their readers already rely on it, citing the session-logs skill and this task.
  - `session-metadata-marks-headless` (boolean): "The harness's session metadata tells headless runs from interactive ones." agy from the probe below; Claude Code (`entrypoint`) and Codex (`source`) `probed` true citing `docs/notes/2026-10-15-session-discovery-contract.md`.
  - `transcript-self-describing` (boolean): "A transcript file names its session's working directory without another store." agy `probed` false (cwd and title only in `conversation_summaries.db`); Claude Code and Codex true.
  - `session-archive-complete` (boolean): "hq's session-archive captures everything needed to resume or fully re-read a session." agy `probed` false (not captured: `conversations/<id>.db`, spilled `steps/<N>/output.txt`, model and token metadata); Claude Code and Codex `unknown` unless the archive spec states it.
- Probe for headless runs: follow `README.md` "Re-probing a fact" and how hq-e72097 isolated agy (`tasks show hq-e72097`); run one `agy -p` conversation there and inspect its summaries row. If no isolated home is possible, record `status = "unknown"` with a note saying why, and do not run against the live home.

- [ ] **Step 1: Write the facts** and run `tools/harness-facts check`; expected: no output, exit 0.
- [ ] **Step 2: Rewrite runbook section 7** to the adapter route: create `tools/harness_stores/<name>.py` with an `Adapter`, register it, add its colour and `[homes.<name>]` flags, declare archive sources (`required=False`, selectors, `append_only` for databases), add its reader to `session-episodes` `READERS`, document it in the session-logs skill, record its gaps as facts.
- [ ] **Step 3: Run** `just test` (includes `harness-facts check`) and `tools/ops-docs check`; expected pass.
- [ ] **Step 4: Commit** `docs(hq): agy session-store facts and the adapter route in the harness runbook (hq-57d68e)`.
