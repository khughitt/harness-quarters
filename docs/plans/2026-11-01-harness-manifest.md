# Declarative Harness Manifest Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract a root `harnesses.toml` manifest as the single source of truth for `hq` harness declarations and tracked live-state hygiene rules across `.githooks/` and `tools/harness-facts`, with fail-closed Git clean-filter enforcement.

**Architecture:** `<hq-checkout>/harnesses.toml` (`schema = 1`) declares all six `hq` harnesses (`agy`, `claude-code`, `codex`, `opencode`, `pi`, `pi-durable`) and optional `[harnesses.<slug>.live_state]` subtables. `.githooks/harness_state.py` owns the manifest loader, segment-bounded glob disjointness and `.gitattributes` parity checks, real-repository `filter.harness-state.{clean,required}` verification, staged-blob cleanliness checks, and pure JSON/TOML cleaners consumed directly by `live-picks`, `harness-state-clean`, `harness-state-refresh`, `codex-trust`, and `pre-commit`, while `tools/harness-facts` remains a standalone stdlib reader reading `[harnesses]` from `harnesses.toml` in place of `facts/capabilities.toml`'s duplicate `harnesses` list.

**Tech Stack:** Python 3 standard library (`tomllib`, `dataclasses`, `pathlib`, `re`, `json`, `subprocess`, `argparse`), Git attributes/clean filters/hooks, `just`, `pytest` (`just test`).

**Spec:** `docs/specs/2026-11-01-harness-manifest-design.md` (accepted for planning 2026-11-01 at `077b8f6`, with round-3 staged-blob and linked-worktree refinements folded in). Read it alongside `docs/specs/2026-10-10-live-model-preservation-design.md` and `docs/specs/2026-10-15-pi-live-picks-design.md` before starting any task.

**Task:** hq-2eba07; source hq-6c8a9f.

**Status:** approved for execution, 2026-11-01 (plan review round 1 accepted at `1548d95` by `claude-code/claude-sonnet-5-5`, with round-1 edits 1–3 and minors 1–4 incorporated; no further plan review gate owed).

**Execution:** preserve the user's subagent-driven choice (`superpowers:subagent-driven-development`). Execute Tasks 1–6 strictly sequentially (never in parallel) in the existing locked, hydrated `.worktrees/hq-2eba07/`; do not create another `hq` worktree.

## Global Constraints

- **Authoritative workspace and strictly sequential execution:** execute all work and `tasks` commands inside `.worktrees/hq-2eba07` on branch `feat/hq-2eba07-harness-manifest` (`git -C .worktrees/hq-2eba07 ...`, `tasks -C .worktrees/hq-2eba07 ...`). Tasks 1–6 MUST run strictly one at a time in dependency order (`Task 1 -> Task 2 -> Task 3 -> Task 4 -> Task 5 -> Task 6`), never in parallel, because Tasks 3, 4, and 5 modify shared scratch-repo fixtures (`.githooks/test_live_picks.py`, `.githooks/test_codex_trust.py`, `.githooks/test_harness_state_refresh.py`, `tools/test_agy_hooks.py`, `tools/test_harness_links.py`). Never stash, overwrite, or touch live configs in the main checkout.
- **No host-layout values in tracked files:** never write machine hostnames, home-directory paths, `WORK_ROOT` paths, or sync-root paths into any tracked file (`tools/ops-check` enforces this in `.githooks/pre-commit`). Use checkout-role placeholders (`<hq-checkout>`) in docs and `tmp_path` fixtures in tests.
- **Subprocess and Git fixture isolation (mandatory from the first RED run):** every new test helper that spawns a subprocess builds `env` key by key (`PATH`, temporary `HOME`, `XDG_CONFIG_HOME`, `GIT_CONFIG_GLOBAL`, `GIT_CONFIG_NOSYSTEM="1"`, `GIT_AUTHOR_*`, `GIT_COMMITTER_*`, `PYTHONDONTWRITEBYTECODE="1"`), never copying `os.environ` (`os.environ.copy()` or `{**os.environ, ...}`). Before writing to any scratch Git repository, assert `git rev-parse --show-toplevel` equals `repo.resolve()` and `git rev-parse --absolute-git-dir` lies inside `repo.resolve()`.
- **Sibling-task sequencing (`hq-ece26a` and `hq-7e1e9c`):** `hq-2eba07` (priority 2) sequences ahead of unstarted `hq-ece26a` (priority 3, `todo`, no branch yet): Task 3 owns `.githooks/live-picks` first, and `hq-ece26a` (detached-path parse/type diagnostics, `relink_home` `(st_dev, st_ino)` verification, and `AGY_ANCHORS` / `links.toml` parity) implements on top of (or rebases onto) `hq-2eba07` after `hq-2eba07` merges into `main`. Before starting Task 3, inspect `git -C .worktrees/hq-2eba07 log HEAD..main -- .githooks/live-picks`: if `hq-ece26a` happened to merge into `main` first, merge `main` into `feat/hq-2eba07-harness-manifest` (never rebase across recorded retention checkpoints) before editing `.githooks/live-picks` and preserve its `relink_home` fd-inode check and detached-path parse/type error diagnostics. `hq-7e1e9c` (retiring `tools/relay_cutover_bootstrap/inputs.py`) stays decoupled via Task 4's `CLAUDE_JSON_KEYS` re-export in `.githooks/harness-state-clean`.
- **Clean-filter bisect safety, shared Git config disclosure, and `local/` compatibility:** `harnesses.toml` and `.githooks/harness_state.py` land in Task 1, `.githooks/live-picks` drops `runpy.run_path("harness-state-clean")` in Task 3 before Task 4 removes `harness-state-clean`'s legacy globals (requiring zero temporary compatibility shims), and `justfile` `filter.harness-state.required = true` lands in Task 5 together with `check_filter_config()` enforcement in `harness-state-refresh` and `pre-commit` so `just setup` satisfies every commit on the branch. Running `just setup` inside `.worktrees/hq-2eba07` in Task 5 Step 4 writes `filter.harness-state.required = true` into the shared repository Git config (`commondir`), making it live on this host before merge approval (benign with `main`'s pre-manifest `.githooks/harness-state-clean` and intended to stay); Task 5 Step 4 records an immediate task note on hq-2eba07 and Task 6 carries that disclosure and the cross-host `just setup` requirement into the merge-approval and closeout notes. `local/live-picks*.json`, `local/codex/trust.toml`, and `local/harness-state.lock` formats stay byte-compatible with `6b434eb`.
- **`CLAUDE_JSON_KEYS` and `tools/harness-facts` compatibility:** `.githooks/harness-state-clean` binds `CLAUDE_JSON_KEYS` from `MANIFEST.by_harness["claude-code"].json_clean_keys` only when `claude-code` has JSON `live_state` (leaving it unbound with no `()` fallback otherwise, until hq-7e1e9c retires `tools/relay_cutover_bootstrap/inputs.py`). `tools/harness-facts` stays a single-file stdlib script with no `.githooks/` import, preserving `"schema": 1` in `view()` and positional call compatibility on `validate(path=None, root=None, manifest=None)` and `lookup(fact, harness, path=None, manifest=None)`.
- **TDD and commit gates:** write failing tests first (RED), verify the expected failure message, implement minimal code to pass (GREEN), and run `just test`, `python3 tools/ops-check`, `python3 tools/ops-docs check`, `python3 tools/harness-facts check`, and `tasks check` before each task's commit. Use conventional commits with no AI attribution or emoji. Merging `.githooks/` and `justfile` changes into `main` requires explicit user approval after Task 6's final whole-branch review.

## Review Focus

1. **Already-leaked raw settings blob staged in the Git index before `just setup` (or across a pre-manifest rebase/bisect):** when the index already holds a raw settings blob containing `deviceId`, `trackingId`, `model`, or `[projects."..."]` and `just setup` is subsequently run, `pre-commit` (`harness_state.py check --git-dir <dir> --staged-tree`) must still refuse the commit and name `git add --renormalize <path>`, passing once renormalized (pinned in Task 1 `test_check_clean_tree_refuses_unfiltered_blob_and_names_renormalize` and Task 5 `test_already_leaked_staged_settings_blob_is_refused_until_renormalized`).
2. **Multi-unit top-level TOML picks with comments, duplicate keys, or quoted-key mismatches:** changing one picker unit in a multi-unit TOML config while another unit was saved earlier must merge units in manifest declaration order, preserve `unrestored_keys` on `forget`, keep tracked comments/tables intact, and refuse duplicate or quoted-key lines cleanly without clobbering other harnesses (pinned in Task 3 `test_multi_unit_toml_merges_units_in_declaration_order_and_preserves_unrestored_keys_on_forget` and `test_toml_duplicate_or_quoted_key_mismatch_is_refused`).
3. **`pre-commit` invoked from a linked Git worktree (`git worktree add`):** `git rev-parse --git-dir` in a linked worktree returns `<main>/.git/worktrees/<name>`; `harness_state.py check --git-dir <that> --staged-tree` must read the shared repository filter config via `commondir`, pass when `required = true` and `clean` match `EXPECTED_CLEAN_FILTER`, and refuse with `run 'just setup'` when `required` is unset/`false` or `clean` uses a stale command spelling (pinned in Task 5 `test_pre_commit_runs_from_linked_worktree_and_enforces_shared_filter_config`).
4. **Corrupt or non-UTF-8 `harnesses.toml` during Git `post-*` hooks or invalid CLI invocations:** truncated TOML or invalid UTF-8 bytes in `harnesses.toml` must never emit a Python traceback; bad-arg invocations of `live-picks` still print `usage: live-picks ...`, `live-picks hook` and `codex-trust hook` print `<tool>: ...` plus their retry notice on stderr and exit `0` (and exit `0` silently in linked worktrees), while `harness-state-clean` and direct CLI subcommands exit non-zero (pinned in Task 1 `test_non_utf8_and_malformed_toml_raise_manifest_error`, Task 3 `test_broken_manifest_hook_exits_zero_with_retry_while_cli_fails_and_bad_args_print_usage`, and Task 4 `test_broken_manifest_hook_exits_zero_while_cli_fails`).
5. **Clean-only `live_state` entry (`picks_record` and `pick_units` both omitted):** a harness whose tracked settings are stripped by `harness-state-clean` and stat-refreshed by `harness-state-refresh` without `live-picks` persistence must validate with `unrestored_keys` defaulting to all `filterable_pick_keys`, be skipped by `live-picks` `capture`/`restore`/`sync` and rejected by `forget` without `KeyError`, and strip and refresh cleanly (pinned in Task 1 `test_clean_only_live_state_defaults_unrestored_keys_and_validates`, Task 3 `test_clean_only_live_state_is_skipped_by_live_picks_sync_and_refused_by_forget`, and Task 4 `test_clean_only_harness_is_filtered_and_refreshed_end_to_end`).

---

## File Structure

- Create: `harnesses.toml` — schema-1 declarative manifest of all six `hq` harnesses and the four tracked `live_state` subtables (`agy`, `claude-code`, `codex`, `pi`).
- Modify: `.githooks/harness_state.py` — keep `Checkout`, `write`, and lock mechanics; add `ManifestError`, `TomlKeyRule`, `LiveStateSpec`, `HarnessManifest`, `load_manifest`, `load_manifest_or_exit`, `check_gitattributes`, `check_filter_config`, `check_clean_tree`, `clean_json`, 3-argument `clean_toml`, `clean_for_spec`, and the `check [--git-dir <path>] [--staged-tree]` CLI.
- Create: `.githooks/test_harness_manifest.py` — unit and integration tests for `harnesses.toml`, `harness_state.py` validation/glob-disjointness/parity/config/clean-tree checks, pure cleaners, fail-closed `git add`, and cross-boundary branch switching.
- Modify: `facts/capabilities.toml` — remove top-level `harnesses = [...]` list.
- Modify: `tools/harness-facts` — add `DEFAULT_MANIFEST = CHECKOUT / "harnesses.toml"`, `--manifest <path>` on top-level and `check`/`list`/`get`, manifest validation, and trailing `manifest=None` on `validate` and `lookup`.
- Modify: `tools/test_harness_facts.py` — pair `GOOD` with a 3-harness `GOOD_MANIFEST`, test manifest refusals, `--manifest`, read-only behavior, symlink resolution, and positional `validate`/`lookup` backward compatibility.
- Modify: `.githooks/live-picks` — drop `runpy.run_path`; add lazy `usage()`, deferred pre-lock `load_manifest_or_exit` inside `hook` `try/except SystemExit`, format-generic JSON and multi-unit TOML handling (`merged_lines`, `missing`, `without_pick` preserving `unrestored_keys`, duplicate-key refusal), and `LiveStateSpec`-driven `adopt_detached`.
- Modify: `.githooks/harness-state-clean` — load `MANIFEST` via `load_manifest_or_exit`, re-export `TOML_HEADER`, `TOML_KEY`, `clean_json`, `clean_toml`, and fail-early `CLAUDE_JSON_KEYS` (until hq-7e1e9c retires `tools/relay_cutover_bootstrap/inputs.py`), and route every path through `spec.filter_re`.
- Modify: `.githooks/harness-state-refresh` — defer `load_manifest_or_exit` into `main()` after draining `sys.stdin`, derive `:(glob)<spec.filter_glob>` patterns (Task 4), and enforce `harness_state.check_filter_config()` before restaging (Task 5).
- Modify: `.githooks/codex-trust` — drop `runpy.run_path`; defer `load_manifest_or_exit` into `main()` inside `hook` `try/except SystemExit` before `locked()`, reading `CODEX_SPEC.trust_table` and `harness_state.clean_for_spec`.
- Modify: `justfile` — add `git config filter.harness-state.required true` to `setup`.
- Modify: `.githooks/pre-commit` — resolve `real_git_dir`, export `staged_tree` once in `main()`, and run both `facts_check(tree)` and `manifest_check(tree, git_dir=real_git_dir)` (`--staged-tree`).
- Modify: `.githooks/test_harness_state_clean.py`, `.githooks/test_harness_state_refresh.py`, `.githooks/test_live_picks.py`, `.githooks/test_codex_trust.py`, `.githooks/test_pre_commit.py`, `.githooks/test_pre_commit_facts.py`, `tools/test_agy_hooks.py`, `tools/test_harness_links.py` — update scratch fixtures for `harnesses.toml` and `filter.harness-state.required = true`, and add coverage for every new invariant and failure mode.
- Modify: `AGENTS.md`, `README.md`, `docs/runbooks/adding-a-harness.md` — document `harnesses.toml`, fail-closed `required = true` (`just setup`), broken-manifest recovery (`git checkout -- harnesses.toml`), and staged `pre-commit` checks.

## Setup (before Task 1)

- [ ] Claim the parent task in `.worktrees/hq-2eba07` (`tasks -C .worktrees/hq-2eba07 start hq-2eba07`) and confirm `~/.agents/bin/trial-arm hq-2eba07` prints `flow-trial-1: flow off` (no `gate:` notes).
- [ ] Run the full-suite baseline in `.worktrees/hq-2eba07` before any code edit:
  Run: `cd .worktrees/hq-2eba07 && just test`
  Expected: `tools/harness-facts check` and all `pytest` invocations exit `0` with non-zero test counts.
- [ ] Record the baseline command, test counts, and pass result on hq-2eba07 with `tasks -C .worktrees/hq-2eba07 note hq-2eba07 "baseline: ..."`.

---

### Task 1: Root harnesses.toml and shared harness_state loader, cleaners, and checks

**Files:**
- Create: `harnesses.toml`
- Modify: `.githooks/harness_state.py` (`write`, `Checkout`, and new manifest/cleaner/check surface)
- Test: `.githooks/test_harness_manifest.py`

**Interfaces:**
- Consumes: existing `.gitattributes` (`filter=harness-state` lines) and `.githooks/harness_state.py` (`HERE`, `REPO`, `LOCAL`, `LOCK`, `GIT_HOOKS`, `REBASE_STATE`, `write`, `Checkout`, all preserved unchanged).
- Produces (in `.githooks/harness_state.py`):
  - Constants: `MANIFEST_PATH = REPO / "harnesses.toml"`, `GITATTRIBUTES_PATH = REPO / ".gitattributes"`, `EXPECTED_CLEAN_FILTER = ".githooks/harness-state-clean %f"`, `TOML_HEADER`, `TOML_KEY`.
  - Types:
    - `class ManifestError(ValueError)` with `problems: list[str]`.
    - `@dataclass(frozen=True) class TomlKeyRule: table_pattern: str; table_re: re.Pattern[str]; keys: tuple[str, ...]`.
    - `@dataclass(frozen=True) class LiveStateSpec: harness: str; config: str; filter_glob: str; filter_re: re.Pattern[str]; format: str; json_clean_keys: tuple[str, ...]; toml_clean_keys: tuple[TomlKeyRule, ...]; toml_clean_tables: tuple[re.Pattern[str], ...]; trust_table: re.Pattern[str] | None; unrestored_keys: tuple[str, ...]; picks_record: str | None; pick_units: tuple[tuple[str, ...], ...]` with `@property def pick_keys(self) -> tuple[str, ...]`.
    - `@dataclass(frozen=True) class HarnessManifest: schema: int; harnesses: tuple[str, ...]; by_harness: dict[str, LiveStateSpec | None]; live_state: tuple[LiveStateSpec, ...]`.
  - Functions:
    - `load_manifest(path: Path | None = None) -> HarnessManifest`
    - `load_manifest_or_exit(tool: str, path: Path | None = None) -> HarnessManifest`
    - `check_gitattributes(manifest: HarnessManifest, path: Path | None = None) -> None`
    - `check_filter_config(git_dir: Path | None = None) -> None`
    - `check_clean_tree(manifest: HarnessManifest, root: Path | None = None) -> None`
    - `clean_json(text: str, keys: Iterable[str]) -> str`
    - `clean_toml(text: str, key_rules: Iterable[TomlKeyRule], table_patterns: Iterable[re.Pattern[str]]) -> str`
    - `clean_for_spec(spec: LiveStateSpec, text: str) -> str`
    - `main(argv: Sequence[str] | None = None) -> int` supporting `python3 .githooks/harness_state.py check [--git-dir <path>] [--staged-tree]` (exits `0` when valid, prints `harness-state: <problem>` lines to stderr and exits `2` on `ManifestError`).

- [ ] **Step 1: Write failing unit and integration tests in `.githooks/test_harness_manifest.py`**

Build a key-by-key subprocess environment helper `isolated_env(tmp_path)` (setting only `PATH`, `HOME`, `XDG_CONFIG_HOME`, `GIT_CONFIG_GLOBAL`, `GIT_CONFIG_NOSYSTEM="1"`, `GIT_AUTHOR_*`, `GIT_COMMITTER_*`, `PYTHONDONTWRITEBYTECODE="1"`) and scratch Git initializer asserting `--show-toplevel` and `--absolute-git-dir`. Write tests covering:
- `test_shipped_manifest_loads_and_matches_gitattributes_and_git_check_attr`: `load_manifest()` returns `harnesses == ("agy", "claude-code", "codex", "opencode", "pi", "pi-durable")`, verifies each shipped `LiveStateSpec`'s `pick_keys` and `unrestored_keys` match spec §5.1's partition table, passes `check_gitattributes(manifest)`, and verifies `git check-attr filter` in a scratch repo agrees with `spec.filter_re.fullmatch` across positive (`claude/settings.json`, `claude/settings.work.json`, `codex/config.toml`, `codex/config.work.toml`, `pi/settings.json`, `agy/settings.json`) and negative (`claude/settings/nested.json`, `harnesses.toml`, `links.toml`, `codex/hooks.json`) paths.
- `test_manifest_validation_refuses_each_schema_and_partition_violation` (parametrized): `schema = 2`, `schema = true`, `schema = 1.0`, unknown top-level key, empty `[harnesses]`, invalid slug `Claude`, unknown key under `[harnesses.pi]`, `config` with `*` or `..` or under `local/` or without `/`, `filter_glob` with `?` / `[a]` / `**` / two `*` in one segment (`agy/*settings*.json`), `config` not matching `filter_glob`, duplicate `config` or `filter_glob`, overlapping `filter_glob` pair (`agy/settings*.json` vs `agy/settings-x*.json`), invalid regex in TOML `clean_keys.table` or `clean_tables`, `trust_table` absent from `clean_tables`, `picks_record` without `pick_units` (and vice versa), `picks_record` outside `local/` (`picks.json` or `local/../x.json`), overlapping `pick_units`, and partition violations (a `clean_keys` key missing from both `pick_units` and `unrestored_keys`, or present in both, for both JSON and TOML `table == ""`).
- `test_clean_only_live_state_defaults_unrestored_keys_and_validates` (Review Focus 5): omitting both `picks_record` and `pick_units` sets `unrestored_keys == filterable_pick_keys` and `pick_units == ()`; supplying a partial `unrestored_keys` on a clean-only entry raises `ManifestError`.
- `test_non_utf8_and_malformed_toml_raise_manifest_error` (Review Focus 4): missing file, truncated TOML, and `b"\xff\xfe"` bytes raise `ManifestError`, and `load_manifest_or_exit("tool", path)` raises `SystemExit` starting with `"tool: "` and no traceback.
- `test_check_gitattributes_refuses_drift_duplicates_and_negated_filter`: missing pattern, extra `filter=harness-state` pattern, duplicate pattern, and `-filter=harness-state` or `filter=harness-state` typo lines raise `ManifestError`.
- `test_check_filter_config_and_cli_check`: in an isolated scratch Git repo, `check_filter_config(repo / ".git")` fails naming `run 'just setup'` when `filter.harness-state.clean` is missing or set to `"/abs/path/harness-state-clean %f"` or when `filter.harness-state.required` is unset or `"false"`, and passes when `clean == EXPECTED_CLEAN_FILTER` and `required == "true"`.
- `test_check_clean_tree_refuses_unfiltered_blob_and_names_renormalize` (Review Focus 1): in a scratch directory holding `harnesses.toml`, `.gitattributes`, clean `claude/settings.json`, and unfiltered `pi/settings.json` (`{"theme": "system", "deviceId": "secret"}`) or invalid JSON, `check_clean_tree` and `python3 .githooks/harness_state.py check --git-dir <git_dir> --staged-tree` exit `2` naming `pi/settings.json` and `git add --renormalize pi/settings.json`, and exit `0` once cleaned.
- `test_clean_json_and_three_arg_clean_toml`: direct Python unit tests for `clean_json`, 3-argument `clean_toml(text, key_rules, table_patterns)` (verifying top-level-only key stripping, nested table regex stripping, whole-table stripping with trailing blank lines, and non-matching table preservation), and `clean_for_spec`.

- [ ] **Step 2: Run the new test file to verify RED failure**

Run: `cd .worktrees/hq-2eba07 && uv run -q --with pytest pytest .githooks/test_harness_manifest.py -q`
Expected: FAIL (`AttributeError` / missing `harnesses.toml` and missing `ManifestError` / `load_manifest` on `harness_state`).

- [ ] **Step 3: Create `harnesses.toml` and implement the loader, checkers, and cleaners in `.githooks/harness_state.py`**

Write `harnesses.toml` with the exact shipped schema-1 contents in spec §5.1 (`agy`, `claude-code`, `codex`, `opencode`, `pi`, `pi-durable`). Extend `.githooks/harness_state.py` with:
- Segment-bounded `filter_glob` compiler (`^` + `/`.join(re.escape(p) for `*`-split parts joined by `[^/]*`) + `\Z`, allowing at most one `*` per `/` segment and rejecting `?`, `[`, `]`, empty segments, `.`, `..`, and `local/...`) and the per-segment prefix/suffix overlap check from spec §5.1 item 2 across all pairs of `live_state` entries with equal segment counts.
- Full §5.1 validation in `load_manifest` collecting all findings into `ManifestError(problems)`.
- `check_gitattributes`, `check_filter_config` (`git --git-dir=<git_dir> config --get filter.harness-state.clean` and `git --git-dir=<git_dir> config --bool --get filter.harness-state.required`), `check_clean_tree`, `clean_json`, 3-argument `clean_toml`, `clean_for_spec`, and `argparse`-based `main()` for `check [--git-dir <path>] [--staged-tree]`.

- [ ] **Step 4: Run focused tests and full suite to verify GREEN**

Run: `cd .worktrees/hq-2eba07 && uv run -q --with pytest pytest .githooks/test_harness_manifest.py -q && just test && python3 tools/ops-check && python3 tools/ops-docs check && tasks check`
Expected: all tests in `.githooks/test_harness_manifest.py` and `just test` PASS; hygiene and task checks exit `0` with no output.

- [ ] **Step 5: Commit Task 1**

```bash
git -C .worktrees/hq-2eba07 add harnesses.toml .githooks/harness_state.py .githooks/test_harness_manifest.py
git -C .worktrees/hq-2eba07 commit -m "feat(hooks): add harnesses.toml manifest and harness_state loader"
```

---

### Task 2: Migrate tools/harness-facts and facts/capabilities.toml to harnesses.toml

**Files:**
- Modify: `facts/capabilities.toml` (top-level `harnesses` removal)
- Modify: `tools/harness-facts` (`DEFAULT_MANIFEST`, `validate`, `lookup`, `main`)
- Modify: `tools/test_harness_facts.py` (`GOOD`, `GOOD_MANIFEST`, `write`, `REFUSALS`, manifest tests)
- Modify: `tools/test_agy_hooks.py` (`write_facts_fixture`)
- Modify: `.githooks/test_pre_commit_facts.py` (`repo` fixture)

**Interfaces:**
- Consumes: `harnesses.toml` (`schema = 1`, `[harnesses.<slug>]` with optional `live_state` table) from Task 1.
- Produces (in `tools/harness-facts`):
  - `DEFAULT_MANIFEST = CHECKOUT / "harnesses.toml"`
  - `validate(path=None, root=None, manifest=None) -> dict` (when `manifest is None`, reads `pathlib.Path(root) / "harnesses.toml"` if `root is not None` else `DEFAULT_MANIFEST`; attaches `"harnesses": list(manifest_data["harnesses"])` to the returned dict).
  - `lookup(fact, harness, path=None, manifest=None) -> dict`
  - CLI `--manifest <path>` accepted on `harness-facts` and on subcommands `check`, `list`, and `get` (mirroring `--file`).

- [ ] **Step 1: Write failing tests in `tools/test_harness_facts.py`, update `tools/test_agy_hooks.py` and `.githooks/test_pre_commit_facts.py` fixtures**

In `tools/test_harness_facts.py`:
- Remove `harnesses = ["claude-code", "codex", "opencode"]` from `GOOD` and define `GOOD_MANIFEST` declaring `[harnesses.claude-code]`, `[harnesses.codex.live_state]` (`config = "codex/config.toml"`), and `[harnesses.opencode]` under `schema = 1`.
- Update `write(tmp_path, text, manifest_text=GOOD_MANIFEST)` to write both `tmp_path / "capabilities.toml"` and `tmp_path / "harnesses.toml"`, passing `--manifest` in `run(...)` for `GOOD`-based tests and `manifest` to `facts.validate(path, ROOT, manifest)` / `facts.lookup(..., path, manifest)`.
- Replace the three inline `harnesses = ...` rows in `REFUSALS` with:
  - an inline `harnesses = ["claude-code"]` row in `capabilities.toml` refused with `"unknown key harnesses"`;
  - a parametrized `test_manifest_refusals` covering missing manifest file, invalid TOML/non-UTF-8 manifest, `schema = 2` / `true` / `1.0`, unknown top-level manifest key, empty `[harnesses]`, invalid harness slug `Claude`, non-table `[harnesses.codex]`, unknown key under `[harnesses.codex]` (anything other than `live_state`), and non-table `live_state = 1`.
- Add `test_positional_validate_and_lookup_use_root_or_default_manifest`: verifies 1-arg `facts.validate()`, 2-arg `facts.validate(ROOT / "facts/capabilities.toml", ROOT)`, 2-arg `facts.lookup("controller-wake", "agy")`, and 3-arg `facts.lookup("controller-wake", "agy", ROOT / "facts/capabilities.toml")` work without passing `manifest`.
- Update `test_the_file_is_only_read` (chmod `0o444` on both `capabilities.toml` and `harnesses.toml`, `0o555` on `tmp_path`, asserting `sorted(p.name for p in tmp_path.iterdir()) == ["capabilities.toml", "harnesses.toml"]`) and `test_the_default_file_is_found_through_a_link` (writing `checkout / "harnesses.toml"` with `GOOD_MANIFEST`).
In `tools/test_agy_hooks.py` (`write_facts_fixture`): read declared harness slugs from `ROOT / "harnesses.toml"` instead of `doc["harnesses"]` and stop emitting `harnesses = ...` into the generated `capabilities.toml` fixture.
In `.githooks/test_pre_commit_facts.py` (`repo` fixture): include `"harnesses.toml"` in the files copied from `CHECKOUT` into `root`.

- [ ] **Step 2: Run `tools/test_harness_facts.py` to verify RED failure**

Run: `cd .worktrees/hq-2eba07 && uv run -q --with pytest pytest tools/test_harness_facts.py -q`
Expected: FAIL (`TypeError: validate() takes from 0 to 2 positional arguments` / `unrecognized arguments: --manifest`).

- [ ] **Step 3: Update `tools/harness-facts` and `facts/capabilities.toml`**

- Remove `harnesses = [...]` from `facts/capabilities.toml`.
- In `tools/harness-facts`: add `DEFAULT_MANIFEST = CHECKOUT / "harnesses.toml"`; validate `manifest` (`schema == 1` exact `int`, top-level keys `<= {"schema", "harnesses"}`, `harnesses` non-empty dict of valid `NAME` slugs mapping to dicts with keys `<= {"live_state"}` where `live_state` is a dict if present); disallow `"harnesses"` in `capabilities.toml` top-level keys (`{"schema", "facts"}`); populate `result = {**data, "harnesses": harnesses}` in `validate(path=None, root=None, manifest=None)`; thread `manifest=None` through `lookup(fact, harness, path=None, manifest=None)` and `--manifest` through `main(argv)`.

- [ ] **Step 4: Run focused tests and full suite to verify GREEN**

Run: `cd .worktrees/hq-2eba07 && uv run -q --with pytest pytest tools/test_harness_facts.py tools/test_agy_hooks.py .githooks/test_pre_commit_facts.py -q && just test && python3 tools/ops-check && python3 tools/ops-docs check && tasks check`
Expected: PASS across all suites and checks.

- [ ] **Step 5: Commit Task 2**

```bash
git -C .worktrees/hq-2eba07 add facts/capabilities.toml tools/harness-facts tools/test_harness_facts.py tools/test_agy_hooks.py .githooks/test_pre_commit_facts.py
git -C .worktrees/hq-2eba07 commit -m "feat(facts): read declared harnesses from harnesses.toml"
```

---

### Task 3: Migrate live-picks to harnesses.toml

**Files:**
- Modify: `.githooks/live-picks`
- Modify: `.githooks/test_live_picks.py` (`repo` fixture and `live-picks` manifest/TOML/hook/rollback tests)
- Modify: `.githooks/test_harness_state_refresh.py` (`repo` fixture)
- Modify: `.githooks/test_codex_trust.py` (`repo` fixture)
- Modify: `tools/test_agy_hooks.py` (`make_agy_checkout`)
- Modify: `tools/test_harness_links.py` (`fresh_clone`, `test_fresh_clone_strips_live_agy_picks_from_dirty_source_checkout`)

**Interfaces:**
- Consumes: `HarnessManifest`, `LiveStateSpec`, `TOML_HEADER`, `TOML_KEY`, `load_manifest`, `load_manifest_or_exit`, `clean_for_spec` from `.githooks/harness_state.py` (Task 1). (Migrating `live-picks` off `runpy.run_path("harness-state-clean")` before Task 4 removes `harness-state-clean`'s legacy globals keeps `just test` green at both commits with no temporary compatibility shim.)
- Sequencing check with `hq-ece26a`: before editing `.githooks/live-picks`, run `git -C .worktrees/hq-2eba07 log HEAD..main -- .githooks/live-picks`. If empty (`hq-ece26a` still `todo`, the expected state), Task 3 owns `.githooks/live-picks` first and `hq-ece26a` implements on top of `hq-2eba07` after merge; if `hq-ece26a` merged into `main` first, merge `main` into `feat/hq-2eba07-harness-manifest` (never rebase) and preserve its `relink_home` `(st_dev, st_ino)` check and detached-path parse/type error diagnostics.
- Produces (in `.githooks/live-picks`):
  - No import-time manifest load and no `runpy.run_path`; lazy `usage()` helper appending `(files: ...)` when `load_manifest()` succeeds and falling back to the static command synopsis when `harnesses.toml` is broken.
  - Deferred pre-lock `load_specs()` (`load_manifest_or_exit("live-picks")`, selecting `{s.config: s for s in manifest.live_state if s.picks_record is not None}`) inside `hook` mode's `try ... except SystemExit` (and before `CHECKOUT.locked()` in CLI mode), after arg-shape and `linked_worktree()` / `rebasing()` checks.
  - Format-generic JSON and multi-unit TOML `parse`, `toml_lines`, `pick`, `invalid` (enforcing duplicate-free keys and `toml_lines` round-trip equality), `merged_values` and `merged_lines` (iterating `spec.pick_units` in declaration order), `missing` (format-dispatched over `spec.pick_units`), `with_pick`, `without_pick` (stripping `spec.pick_keys` only and preserving `unrestored_keys`), `checked` (via `harness_state.clean_for_spec`), and `LiveStateSpec`-driven `adopt_detached` (keeping `AGY_CONFIG = "agy/settings.json"`, `AGY_HOME`, `AGY_LINK`, `AGY_ANCHORS` explicit).

- [ ] **Step 1: Check `main` for `hq-ece26a`, copy `harnesses.toml` into `live-picks`-calling scratch fixtures, and write failing `live-picks` tests**

Confirm `git -C .worktrees/hq-2eba07 log HEAD..main -- .githooks/live-picks` (merging `main` first only if `hq-ece26a` landed there). Copy `harnesses.toml` into the scratch checkouts that invoke `.githooks/live-picks`:
- `.githooks/test_live_picks.py` (`repo` fixture — keeping `HOOK_FILES` pinned to `6b434eb`'s `.githooks/` filenames so `pre_pi_hooks` / `install_pre_pi_hooks` never look for `6b434eb:harnesses.toml`)
- `.githooks/test_harness_state_refresh.py` (`repo` fixture)
- `.githooks/test_codex_trust.py` (`repo` fixture)
- `tools/test_agy_hooks.py` (`make_agy_checkout`)
- `tools/test_harness_links.py` (`fresh_clone` and `test_fresh_clone_strips_live_agy_picks_from_dirty_source_checkout`)

Add failing tests in `.githooks/test_live_picks.py` (using key-by-key subprocess `env` helpers):
- Replace `test_json_groups_refuse_overlap_unfiltered_keys_and_missing_claude_keys` (which mutated the removed `JSON_GROUPS` AST node) with `test_manifest_partition_and_overlap_violations_are_refused`, mutating `repo / "harnesses.toml"` across overlapping `pick_units`, unfiltered keys, and missing `claude-code` / `agy` / `codex` keys and asserting `picks(repo, "capture")` exits non-zero without creating any `local/live-picks*.json`.
- `test_broken_manifest_hook_exits_zero_with_retry_while_cli_fails_and_bad_args_print_usage` (Review Focus 4): corrupting or deleting `repo / "harnesses.toml"` makes `picks(repo, "hook", "post-merge")` (and `git switch` triggering `post-checkout`) exit `0` with `live-picks:` and `the next turn end retries` on stderr (and exit `0` with empty stderr in a linked worktree), makes `picks(repo, "capture")` / `forget` exit non-zero, and makes `picks(repo, "bogus")` print `usage: live-picks` with no traceback.
- `test_multi_unit_toml_merges_units_in_declaration_order_and_preserves_unrestored_keys_on_forget` (Review Focus 2): add a second TOML harness `[harnesses.extra.live_state]` to `repo / "harnesses.toml"` and `repo / ".gitattributes"` with `pick_units = [["model"], ["effort", "tier"]]`, `unrestored_keys = ["install_id"]`, and `picks_record = "local/live-picks-extra.json"`; verify partial-unit `capture` merges saved unit 1 with live unit 2 in unit declaration order (`["model", "effort", "tier"]`) regardless of reverse key order in the live file, `restore` fills only the missing unit while keeping tracked comments and `[tables]`, and `forget` removes `model`/`effort`/`tier` while keeping `install_id = "abc"` in the live file.
- `test_toml_duplicate_or_quoted_key_mismatch_is_refused` (Review Focus 2): duplicate top-level keys or `"model" = "x"` in a TOML config are refused for that harness while other harnesses still capture/restore.
- `test_clean_only_live_state_is_skipped_by_live_picks_sync_and_refused_by_forget` (Review Focus 5): adding a clean-only JSON entry (no `picks_record` / `pick_units`) in `repo / "harnesses.toml"` lets `live-picks sync` succeed on owned harnesses without `KeyError` and makes `live-picks forget <clean-only-path>` exit non-zero naming `not a file live-picks owns`.
- `test_single_unit_codex_record_bytes_match_pinned_6b434eb_and_rollback_works_without_manifest`: capture Claude + Codex picks with current `live-picks`, save `local/live-picks.json` bytes, delete `repo / "harnesses.toml"` and `install_pre_pi_hooks(repo, pre_pi_hooks)`, run `6b434eb`'s `live-picks capture` and `restore`, and assert `0` exit and byte-identical `local/live-picks.json`.

- [ ] **Step 2: Run `.githooks/test_live_picks.py` to verify RED failure**

Run: `cd .worktrees/hq-2eba07 && uv run -q --with pytest pytest .githooks/test_live_picks.py -q`
Expected: FAIL (mutating `harnesses.toml`, multi-unit TOML, clean-only entry, and broken-manifest tests fail because `live-picks` still reads hardcoded `OWNED` / `JSON_GROUPS` / `runpy`).

- [ ] **Step 3: Implement manifest-driven `.githooks/live-picks`**

Remove `runpy`, `CLAUDE*`, `CODEX`, `PI`, `OWNED`, `RECORDS`, `JSON_GROUPS`, `CLEAN`, `FIELD`; add `usage()` and `load_specs()` (`{s.config: s for s in manifest.live_state if s.picks_record is not None}`); defer `load_specs()` into `main(argv)` after arg-shape and `linked_worktree()` / `rebasing()` checks, inside `hook` mode's `try ... except SystemExit` and before `CHECKOUT.locked()`; generalize `parse`, `toml_lines`, `pick`, `invalid`, `merged_values`, `merged_lines`, `missing`, `with_pick`, `without_pick`, `checked` (via `harness_state.clean_for_spec`), and `adopt_detached(spec, detached, records, from_hook)` (keeping `AGY_CONFIG = "agy/settings.json"`, `AGY_HOME`, `AGY_LINK`, `AGY_ANCHORS` explicit).

- [ ] **Step 4: Run focused tests and full suite to verify GREEN**

Run: `cd .worktrees/hq-2eba07 && uv run -q --with pytest pytest .githooks/test_live_picks.py tools/test_agy_hooks.py tools/test_harness_links.py -q && just test && python3 tools/ops-check && python3 tools/ops-docs check && tasks check`
Expected: PASS across `test_live_picks.py`, rollback tests, `agy`, `harness-links`, and full `just test`.

- [ ] **Step 5: Commit Task 3**

```bash
git -C .worktrees/hq-2eba07 add .githooks/live-picks .githooks/test_live_picks.py .githooks/test_harness_state_refresh.py .githooks/test_codex_trust.py tools/test_agy_hooks.py tools/test_harness_links.py
git -C .worktrees/hq-2eba07 commit -m "feat(hooks): drive live-picks from harnesses.toml with multi-unit TOML support"
```

---

### Task 4: Migrate harness-state-clean, harness-state-refresh, and codex-trust to harnesses.toml

**Files:**
- Modify: `.githooks/harness-state-clean`
- Modify: `.githooks/harness-state-refresh`
- Modify: `.githooks/codex-trust`
- Modify: `.githooks/test_harness_state_clean.py`
- Modify: `.githooks/test_harness_state_refresh.py`
- Modify: `.githooks/test_codex_trust.py`

**Interfaces:**
- Consumes: `HarnessManifest`, `LiveStateSpec`, `TomlKeyRule`, `TOML_HEADER`, `TOML_KEY`, `load_manifest_or_exit`, `clean_json`, `clean_toml`, `clean_for_spec` from `.githooks/harness_state.py` (Task 1); manifest-driven `live-picks` (Task 3, which no longer `runpy.run_path`s `harness-state-clean`).
- Produces:
  - `.githooks/harness-state-clean`: loads `MANIFEST = harness_state.load_manifest_or_exit("harness-state-clean")` at module load; re-exports `TOML_HEADER`, `TOML_KEY`, `clean_json`, 3-arg `clean_toml`, and `CLAUDE_JSON_KEYS` (bound iff `MANIFEST.by_harness.get("claude-code")` has `format == "json"`, kept until hq-7e1e9c retires `tools/relay_cutover_bootstrap/inputs.py`); routes CLI `argv[1]` strictly by `spec.filter_re.fullmatch(path)`.
  - `.githooks/harness-state-refresh`: drains `sys.stdin.read()` first, runs `live-picks capture`, and inside `main()`'s `try ... except SystemExit` loads `MANIFEST = harness_state.load_manifest_or_exit("harness-state-refresh")` and derives `patterns = tuple(f":(glob){spec.filter_glob}" for spec in MANIFEST.live_state)`.
  - `.githooks/codex-trust`: no import-time manifest load and no `runpy.run_path`; deferred pre-lock `load_manifest_or_exit("codex-trust")` inside `hook` mode's `try ... except SystemExit`; uses `CODEX_SPEC.trust_table` and `harness_state.clean_for_spec(CODEX_SPEC, ...)`.

- [ ] **Step 1: Write failing tests for `harness-state-clean`, `harness-state-refresh`, and `codex-trust`**

Add failing tests (using key-by-key subprocess `env` helpers):
- In `.githooks/test_harness_state_clean.py`:
  - `test_unconfigured_toml_and_nested_slash_paths_are_refused`: `clean("harnesses.toml", "schema = 1\n")`, `clean("links.toml", "[required]\n")`, and `clean("claude/settings/nested.json", "{}\n")` exit non-zero naming `is not a harness config`.
  - `test_runpy_exposes_cleaners_and_binds_claude_json_keys_without_silent_fallback`: `runpy.run_path` on `.githooks/harness-state-clean` exposes `CLAUDE_JSON_KEYS == ("model", "modelSettings", "effortLevel")` (preserving compatibility with `tools/relay_cutover_bootstrap/inputs.py` until hq-7e1e9c), `clean_json`, and 3-arg `clean_toml`, and in a scratch copy where `claude-code`'s `live_state` is omitted from `harnesses.toml`, `"CLAUDE_JSON_KEYS" not in namespace`.
- In `.githooks/test_harness_state_refresh.py`:
  - `test_broken_manifest_drains_stdin_skips_staging_and_fails_cleanly`: corrupting `repo / "harnesses.toml"` with a large stdin payload drains stdin without `BrokenPipeError`, exits non-zero with `harness-state-refresh:` and `live-picks:` messages on stderr, and leaves `marked(repo)` `True`.
  - `test_clean_only_harness_is_filtered_and_refreshed_end_to_end` (Review Focus 5): adding a clean-only JSON entry (no `picks_record` / `pick_units`) to `repo / "harnesses.toml"` and `repo / ".gitattributes"` strips its `clean_keys` via `harness-state-clean` and clears its stat-dirty mark in `harness-state-refresh` without creating a `local/live-picks*` file for it.
- In `.githooks/test_codex_trust.py`:
  - `test_broken_manifest_hook_exits_zero_while_cli_fails` (Review Focus 4): corrupting `repo / "harnesses.toml"` makes `trust(repo, "hook", "post-merge")` exit `0` with `codex-trust: trust not restored; the next turn end retries` on stderr (and silent `0` in a linked worktree) while `trust(repo, "capture")` exits non-zero.

- [ ] **Step 2: Run the three hook test suites to verify RED failure**

Run: `cd .worktrees/hq-2eba07 && uv run -q --with pytest pytest .githooks/test_harness_state_clean.py .githooks/test_harness_state_refresh.py .githooks/test_codex_trust.py -q`
Expected: FAIL (`harnesses.toml` passed through `harness-state-clean` instead of being refused; clean-only refresh and broken-manifest hook tests fail against hardcoded tables).

- [ ] **Step 3: Implement manifest-driven `.githooks/{harness-state-clean,harness-state-refresh,codex-trust}`**

- `.githooks/harness-state-clean`: prepend `str(Path(__file__).resolve().parent)` to `sys.path` if absent; `import harness_state`; load `MANIFEST = harness_state.load_manifest_or_exit("harness-state-clean")`; re-export `TOML_HEADER`, `TOML_KEY`, `clean_json`, `clean_toml`; bind `CLAUDE_JSON_KEYS` iff `claude-code` has JSON `live_state` (documenting hq-7e1e9c as the retirement trigger); match `argv[1]` via `[s for s in MANIFEST.live_state if s.filter_re.fullmatch(path)]` and write `harness_state.clean_for_spec(matches[0], text)` or exit with `harness-state-clean: <path> is not a harness config; check .gitattributes`.
- `.githooks/harness-state-refresh`: remove module-level `PATTERNS`; inside `main()` after `sys.stdin.read()` and `run("live-picks capture", ...)`, inside `try ... except SystemExit`, load `manifest = harness_state.load_manifest_or_exit("harness-state-refresh")` and compute `patterns = tuple(f":(glob){s.filter_glob}" for s in manifest.live_state)` before checking `index.lock`.
- `.githooks/codex-trust`: remove `runpy`; add `load_codex_spec()` loading `harness_state.load_manifest_or_exit("codex-trust")` and requiring `codex` TOML `live_state` with `trust_table` and `config == LIVE_NAME`; call `load_codex_spec()` inside `main(argv)` after arg-shape and `linked_worktree()` / `rebasing()` checks, inside `hook` mode's `try ... except SystemExit` and before `locked()`; replace `PROJECT_TRUST` and `CLEAN_TOML` with `spec.trust_table` and `harness_state.clean_for_spec(spec, ...)`.

- [ ] **Step 4: Run focused tests and full suite to verify GREEN**

Run: `cd .worktrees/hq-2eba07 && uv run -q --with pytest pytest .githooks tools/test_relay_cutover_bootstrap.py tools/test_relay_cutover_transport.py -q && just test && python3 tools/ops-check && python3 tools/ops-docs check && tasks check`
Expected: PASS across all `.githooks` and `relay_cutover` suites and full `just test`.

- [ ] **Step 5: Commit Task 4**

```bash
git -C .worktrees/hq-2eba07 add .githooks/harness-state-clean .githooks/harness-state-refresh .githooks/codex-trust .githooks/test_harness_state_clean.py .githooks/test_harness_state_refresh.py .githooks/test_codex_trust.py
git -C .worktrees/hq-2eba07 commit -m "feat(hooks): drive harness-state-clean, refresh, and codex-trust from harnesses.toml"
```

---

### Task 5: Enforce fail-closed filter config, staged-tree pre-commit gate, and reference docs

**Files:**
- Modify: `justfile` (`setup` recipe)
- Modify: `.githooks/harness-state-refresh` (`main`)
- Modify: `.githooks/pre-commit` (`facts_check`, `manifest_check`, `staged_checks`, `main`)
- Modify: `.githooks/test_harness_manifest.py`
- Modify: `.githooks/test_harness_state_refresh.py` (`repo` fixture and `required` refusal test)
- Modify: `.githooks/test_live_picks.py` (`repo` fixture)
- Modify: `.githooks/test_codex_trust.py` (`repo` fixture)
- Modify: `.githooks/test_pre_commit.py` (`world` fixture and linked-worktree filter-config test)
- Modify: `.githooks/test_pre_commit_facts.py` (`repo` fixture, staged `live_state` / `.gitattributes` / already-leaked blob tests)
- Modify: `tools/test_agy_hooks.py` (`make_agy_checkout`)
- Modify: `tools/test_harness_links.py` (`test_setup_is_idempotent_and_creates_only_the_rules_directory`)
- Modify: `AGENTS.md`
- Modify: `README.md`
- Modify: `docs/runbooks/adding-a-harness.md`

**Interfaces:**
- Consumes: `check_filter_config`, `check_clean_tree`, and `python3 .githooks/harness_state.py check --git-dir <path> --staged-tree` from Task 1; manifest-driven hooks from Tasks 3 and 4.
- Produces:
  - `just setup` sets `git config filter.harness-state.required true`.
  - `.githooks/harness-state-refresh` calls `harness_state.check_filter_config()` inside `main()`'s `try ... except SystemExit` before restaging.
  - `.githooks/pre-commit` exposes `facts_check(tree=None)`, `manifest_check(tree=None, git_dir=None)` (invoking `<tree>/.githooks/harness_state.py check --git-dir <real_git_dir> --staged-tree`), and `staged_checks()` exporting `staged_tree` once per `pre-commit` run.

- [ ] **Step 1: Update scratch Git fixtures with `required = true` and write failing enforcement tests**

Add `git config filter.harness-state.required true` to the scratch-repo fixtures in `.githooks/test_harness_state_refresh.py` (`repo`), `.githooks/test_live_picks.py` (`repo`), `.githooks/test_codex_trust.py` (`repo`), `tools/test_agy_hooks.py` (`make_agy_checkout`), `.githooks/test_pre_commit.py` (`world`, along with real `.githooks/harness_state.py`, minimal `harnesses.toml` `schema = 1\n[harnesses.opencode]\n`, and empty `.gitattributes`), and `.githooks/test_pre_commit_facts.py` (`repo`, copying `.githooks/harness_state.py` and `.gitattributes` plus `clean`/`required` config and clean tracked `claude/settings.json`, `codex/config.toml`, `pi/settings.json`, `agy/settings.json`).

Write failing tests:
- In `tools/test_harness_links.py` (`test_setup_is_idempotent_and_creates_only_the_rules_directory`): assert `config("filter.harness-state.required") == "true"`.
- In `.githooks/test_harness_manifest.py`:
  - `test_required_filter_fails_closed_on_broken_manifest_without_leaking_picks`: in a scratch repo configured via `just setup` (`required = true`), write live `deviceId`/`trackingId` into `pi/settings.json` and `model` into `claude/settings.json`, corrupt `harnesses.toml`, assert `git add pi/settings.json` and `git diff` exit non-zero, and assert `git show :pi/settings.json` holds neither `deviceId` nor `trackingId`; restoring `harnesses.toml` lets `git add` succeed cleanly.
  - `test_branch_switch_across_pre_manifest_and_post_manifest_commits_with_required_filter`: in a scratch repo with `filter.harness-state.required = true`, commit a `pre-manifest` branch holding `6b434eb` `.githooks/*` (no `harnesses.toml`, only `claude/settings*.json` and `codex/config*.toml` in `.gitattributes`) and a `post-manifest` branch holding current `.githooks/*` + `harnesses.toml` + all four `.gitattributes` entries, populate live Claude and Codex picks, and verify `git switch pre-manifest` and `git switch post-manifest` both exit `0`, preserve the picks, and leave `git status --porcelain` empty.
- In `.githooks/test_harness_state_refresh.py`:
  - `test_refresh_refuses_when_filter_required_is_unset_or_false`: unsetting `filter.harness-state.required` or setting it to `false` makes `refresh(repo, cwd=tmp_path)` exit non-zero naming `just setup` without clearing `marked(repo)`.
- In `.githooks/test_pre_commit.py`:
  - `test_pre_commit_runs_from_linked_worktree_and_enforces_shared_filter_config` (Review Focus 3): create a linked worktree via `git worktree add`, stage a clean doc change there, assert `run_hook(worktree, env)` exits `0`, then unset `filter.harness-state.required` (and separately set `filter.harness-state.clean` to a stale absolute path) in the shared repo config and assert `run_hook(worktree, env)` exits `1` naming `just setup`.
- In `.githooks/test_pre_commit_facts.py`:
  - `test_staged_live_state_and_gitattributes_violations_are_refused`: staging a bad regex, partition violation, or overlapping `filter_glob` in `harnesses.toml`, staging `.gitattributes` drift, unsetting `filter.harness-state.required` in `repo`, staging deletion of `harnesses.toml` or `.githooks/harness_state.py`, or staging removal of a harness from `harnesses.toml` that `facts/capabilities.toml` still references causes `load_hook().manifest_check()` / `load_hook().staged_checks()` to return `1` with no temp-tree path prefix in stderr.
  - `test_already_leaked_staged_settings_blob_is_refused_until_renormalized` (Review Focus 1): unset `filter.harness-state.required` and `filter.harness-state.clean`, stage `pi/settings.json` containing `"deviceId": "leaked-id"`, restore `clean` and `required = true` (simulating running `just setup` after an earlier leaked `git add`), assert `load_hook().manifest_check()` returns `1` naming `pi/settings.json` and `git add --renormalize pi/settings.json`, run `git add --renormalize pi/settings.json`, and assert `load_hook().manifest_check()` returns `0` with `"leaked-id"` absent from `:pi/settings.json`.

- [ ] **Step 2: Run the failing enforcement tests to verify RED failure**

Run: `cd .worktrees/hq-2eba07 && uv run -q --with pytest pytest .githooks/test_harness_state_refresh.py .githooks/test_pre_commit.py .githooks/test_pre_commit_facts.py tools/test_harness_links.py -k "required or linked_worktree or live_state or leaked" -q`
Expected: FAIL (`just setup` does not set `required`, `harness-state-refresh` does not check `required`, and `pre-commit` has no `manifest_check`).

- [ ] **Step 3: Implement `justfile`, `.githooks/harness-state-refresh`, `.githooks/pre-commit`, and reference docs**

- `justfile`: add `git config filter.harness-state.required true` right after `git config filter.harness-state.clean '.githooks/harness-state-clean %f'` in `setup:`.
- `.githooks/harness-state-refresh`: call `harness_state.check_filter_config()` (converting `harness_state.ManifestError` to `sys.exit(f"harness-state-refresh: {error}")`) right after `load_manifest_or_exit` inside `main()`'s `try ... except SystemExit` block.
- `.githooks/pre-commit`: add `MANIFEST_TOOL = pathlib.Path(".githooks") / "harness_state.py"`; update `facts_check(tree=None)` to accept an already-exported `tree`; add `manifest_check(tree=None, git_dir=None)` executing `[sys.executable, str(tree / MANIFEST_TOOL), "check", "--git-dir", git_dir, "--staged-tree"]` with `cwd=tree` and stripping `f"{tree}/"` from stderr; add `staged_checks()` resolving `real_git_dir = os.path.abspath(git("rev-parse", "--git-dir"))` and exporting `staged_tree` once for `facts_check(tree) or manifest_check(tree, git_dir=real_git_dir)`; call `staged_checks()` in `main(argv)`.
- Reference documentation (keeping `identity.toml`-generated regions untouched and free of host-layout literals):
  - `AGENTS.md`: update `Gates` and `Layout` to name `harnesses.toml`, `.githooks/harness_state.py check` (including staged-blob cleanliness and `filter.harness-state.required = true`), and `tools/harness-facts` reading `[harnesses]` from `harnesses.toml`.
  - `README.md`: update `Setup`, `Usage`, and `Layout` to describe `harnesses.toml`, fail-closed `filter.harness-state.required = true` (`just setup`), recovery from a broken manifest (`git checkout -- harnesses.toml` without unsetting `required`, and `git add --renormalize <path>` if a raw blob was ever staged), cross-host `just setup` after pulling, and `pre-commit`'s staged manifest/filter checks.
  - `docs/runbooks/adding-a-harness.md`: rewrite §§3.2–3.6 and §4.1 around declaring `[harnesses.<name>]` and `[harnesses.<name>.live_state]` in `harnesses.toml` + `.gitattributes`, explaining `clean_keys`, `clean_tables`, `trust_table`, `unrestored_keys`, `picks_record`, `pick_units`, the partition invariant, and why `links.toml` / `tools/hq.toml` / `codex-trust` / `agy` home-adoption stay separate.

- [ ] **Step 4: Run `just setup` in `.worktrees/hq-2eba07`, record the shared Git config write on hq-2eba07, and run full verification**

Run: `cd .worktrees/hq-2eba07 && just setup`
Immediately record a `tasks -C .worktrees/hq-2eba07 note hq-2eba07 "..."` documenting that `just setup` inside `.worktrees/hq-2eba07` wrote `filter.harness-state.required = true` into the shared repository Git config (`commondir`, live on this host before merge approval; benign with `main`'s pre-manifest filter and intended to remain set permanently; rollback command if ever needed before merge: `git config --unset filter.harness-state.required`; other hosts sharing the checkout must run `just setup` once after merge).
Then run: `cd .worktrees/hq-2eba07 && just test && python3 tools/ops-check && python3 tools/ops-docs check && python3 tools/harness-facts check && python3 .githooks/harness_state.py check && tasks check`
Expected: `just setup` sets `filter.harness-state.required = true`; all tests in `just test` PASS; every hygiene, docs, facts, manifest, and task check exits `0` with no output.

- [ ] **Step 5: Commit Task 5**

```bash
git -C .worktrees/hq-2eba07 add justfile .githooks/harness-state-refresh .githooks/pre-commit .githooks/test_harness_manifest.py .githooks/test_harness_state_refresh.py .githooks/test_live_picks.py .githooks/test_codex_trust.py .githooks/test_pre_commit.py .githooks/test_pre_commit_facts.py tools/test_agy_hooks.py tools/test_harness_links.py AGENTS.md README.md docs/runbooks/adding-a-harness.md
git -C .worktrees/hq-2eba07 commit -m "feat(hooks): enforce required clean filter, staged manifest checks, and update docs"
```

---

### Task 6: Whole-branch review, corrective rounds, and merge-approval handoff

**Files:**
- Modify: `docs/specs/2026-11-01-harness-manifest-design.md` (`Status:` line once whole-branch review passes)
- Modify: `docs/plans/2026-11-01-harness-manifest.md` (`Status:` line once whole-branch review passes)

**Interfaces:**
- Consumes: completed commits and task reviews from Tasks 1–5 on `feat/hq-2eba07-harness-manifest`; SDD workspace `.worktrees/hq-2eba07/.superpowers/sdd/<run>/`.
- Produces: accepted whole-branch review (`review: impl round <n> — verdict: accept`), recorded SDD ledger rulings and `minor (deferred)` entries on hq-2eba07, refreshed `retained:` and `retention checkpoint:` notes, and parked merge-approval handoff (plus post-approval integration and worktree-removal checklist).

- [ ] **Step 1: Run pre-review branch verification**

Run: `cd .worktrees/hq-2eba07 && just test && python3 tools/ops-check && python3 tools/ops-docs check && python3 tools/harness-facts check && python3 .githooks/harness_state.py check && tasks check && git status --ignored --porcelain`
Expected: all suites and checks exit `0`; only expected ignored items (`.pytest_cache/`, `.superpowers/`, `local/`, `__pycache__/`) appear under `--ignored`.

- [ ] **Step 2: Dispatch fresh read-only whole-branch review and run corrective rounds**

Dispatch a fresh read-only reviewer subagent over `git -C .worktrees/hq-2eba07 diff main...HEAD` against `docs/specs/2026-11-01-harness-manifest-design.md` and `docs/plans/2026-11-01-harness-manifest.md` (including all five Review Focus items). Save the returned full text in `.worktrees/hq-2eba07/.superpowers/sdd/<run>/final-review-report.md` alongside the reviewer's identity, record `review: impl round <n> — verdict: <revise|accept>; findings: ...; reviewer: ...` on hq-2eba07 before acting, and run up to five corrective rounds (fix pass + fresh read-only scoped re-review, reopening any touched `done` step child via `tasks edit <child> --status todo && tasks start <child>`) until Critical and Important findings reach zero. Record every `Ruling:` (`Why:` and `Cost:`) and `minor (deferred)` item in the SDD ledger and copy/summarize them in a task note on hq-2eba07 (or attach the ledger via `tasks attach`) so every ruling and deferred minor is reachable from hq-2eba07's task record alone.

- [ ] **Step 3: Update spec/plan status, verify ignored files and session load, close Task 6 child, and park hq-2eba07 for merge approval**

- Update `Status:` in `docs/specs/2026-11-01-harness-manifest-design.md` and `docs/plans/2026-11-01-harness-manifest.md` to `implemented on feat/hq-2eba07-harness-manifest, awaiting user merge approval`, run `ops-check`, `ops-docs check`, `harness-facts check`, `harness_state.py check`, and commit.
- Run `~/.local/bin/host-load --section session` and inspect `git -C .worktrees/hq-2eba07 status --ignored --porcelain` and `ls .worktrees/hq-2eba07/.superpowers/sdd/`.
- Close Task 6's step child (`tasks -C .worktrees/hq-2eba07 done <task6-id> "..."`), keeping parent hq-2eba07 open across the merge-approval gate so it continues owning `.worktrees/hq-2eba07`.
- Refresh the `retained:` worktree note and `retention checkpoint:` (`--stamp`) on hq-2eba07, record a pre-merge summary note (verification test counts, rulings/deferred minors, shared `filter.harness-state.required = true` config set on this host and `just setup` required on other hosts after merge, `host-load` output, pushes, unmerged branch `feat/hq-2eba07-harness-manifest`), and park hq-2eba07 (`tasks -C .worktrees/hq-2eba07 park hq-2eba07 "..." --waiting-on user --reason approval`) asking explicit user approval to merge `.githooks/` and `justfile` changes into `main`.

- [ ] **Step 4: Post-approval local integration and worktree cleanup (executed only after explicit user merge approval)**

Once the user approves merging `feat/hq-2eba07-harness-manifest` into `main`:
1. `tasks -C .worktrees/hq-2eba07 start hq-2eba07`, update spec/plan `Status:` to `complete` if needed, record session ownership (`session:<stamped-identity>` when `tasks note --stamp` resolves one, or user handoff/open follow-up otherwise), write the complete closing note (test counts, rulings/deferred minors pointer, shared `filter.harness-state.required = true` disclosure and cross-host `just setup` notice, `host-load --section session`, pushes, others' work in main such as live `codex/config.toml`), and run `tasks -C .worktrees/hq-2eba07 done hq-2eba07 "..."`.
2. From the main checkout (preserving live `codex/config.toml` picks/trust untouched), merge `feat/hq-2eba07-harness-manifest` (`git merge --no-ff feat/hq-2eba07-harness-manifest`) and run `just test` and `just link-check`.
3. Harvest test timings with `tt-report` in `.worktrees/hq-2eba07`; inspect `git -C .worktrees/hq-2eba07 status --ignored --porcelain` and verify every SDD ledger `Ruling:` and `minor (deferred)` line is in hq-2eba07's record; check that no host pointer resolves into `.worktrees/hq-2eba07` (`readlink -f` across `~/bin/*`, `~/.local/bin/*`, `~/.config/systemd/user/*`); run `git worktree unlock .worktrees/hq-2eba07 && git worktree remove .worktrees/hq-2eba07`; verify every recorded checkpoint basis commit is an ancestor of `main` before deleting `feat/hq-2eba07-harness-manifest`; and append the verified `retained:` `state: "released"` note for `.worktrees/hq-2eba07` on hq-2eba07 in `main`.
