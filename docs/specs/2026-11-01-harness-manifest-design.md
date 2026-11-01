# Declarative harness manifest: one source of truth for live-state hooks and capability facts

Status: draft for user review, 2026-11-01 (`hq-2eba07`, source `hq-6c8a9f`). Extends
`docs/specs/2026-10-06-residue-design.md` §4 (capability facts) and
`docs/specs/2026-10-10-live-model-preservation-design.md` /
`docs/specs/2026-10-15-pi-live-picks-design.md` (clean filter, refresh, and live-picks
preservation), whose on-disk `local/` record formats, locking, and rollback rules remain
unchanged.

## 1. Intent and provenance

`hq-2eba07` (`origin: mixed`, filed from `hq-6c8a9f`) combines a user ask about harness
compartmentalization with the filing agent's concrete scoping inside `hq`:

- **User's recorded words** (originating `hq-6c8a9f` session, 2026-10-31 and 2026-11-01):
  asked *"Are there ways that we could improve the abstraction/compartmentalization/configuration
  of harnesses, such that adding support for new ones is straightforward, and ad-hoc /
  hardcoded harness logic is minimized"*, and at closeout asked whether follow-up tasks
  should be created.
- **Agent-added framing** (`hq-2eba07` task record): scoped the `hq` slice to extracting
  a declarative harness manifest defining each harness's canonical slug and (where
  applicable) tracked settings path, format, clean-filter keys, and `live-picks` units
  and record file, loaded by `.githooks/harness-state-clean`,
  `.githooks/harness-state-refresh`, `.githooks/live-picks`, and capability-fact
  validation while keeping format and store adapters explicit.

### 1.1 Current duplication and latent onboarding hazards

Onboarding `agy` in `hq-6c8a9f` required parallel per-harness constant edits across five
tracked files in `hq`:

1. `.gitattributes`: `agy/settings*.json filter=harness-state`.
2. `.githooks/harness-state-clean`: `AGY_JSON_KEYS` and `JSON_FILES`; meanwhile
   `TOML_KEYS` and `TOML_TABLES` match every `.toml` path (`elif path.endswith(".toml")`)
   rather than routing per harness pattern (`docs/runbooks/adding-a-harness.md` §3.3).
3. `.githooks/harness-state-refresh`: `PATTERNS` tuple of tracked config globs.
4. `.githooks/live-picks`: `AGY`, `OWNED`, `RECORDS`, `JSON_GROUPS`, the hardcoded
   `name in (CLAUDE, AGY)` filter-key equality check, `CLEAN`, and `FIELD`; meanwhile
   `missing()` branches on `if name == CODEX:` instead of format, so a second TOML
   harness would fall through into `JSON_GROUPS[name]` and raise `KeyError`
   (`docs/runbooks/adding-a-harness.md` §3.4).
5. `facts/capabilities.toml`: top-level `harnesses = [...]` list.

## 2. Goals, non-goals, and anti-goals

### Goals

- Declare every `hq` harness once in `<hq-checkout>/harnesses.toml` by its canonical
  slug (`agy`, `claude-code`, `codex`, `opencode`, `pi`, `pi-durable`), together with an
  optional `[harnesses.<slug>.live_state]` table for harnesses whose settings are
  tracked and filtered in `hq`.
- Drive `.githooks/harness-state-clean`, `.githooks/harness-state-refresh`,
  `.githooks/live-picks`, and `.githooks/codex-trust`'s trust-table pattern from
  `harnesses.toml` through `.githooks/harness_state.py`, eliminating parallel per-harness
  constant tables in those scripts.
- Generalize TOML handling so a second TOML harness requires only a `harnesses.toml`
  entry (and `.gitattributes` line): per-`filter_glob` routing in `harness-state-clean`
  and format-based (`"json"` vs `"toml"`) multi-unit handling in `live-picks`.
- Have `tools/harness-facts` read the declared harness list from `harnesses.toml` and
  remove the duplicate top-level `harnesses = [...]` list from `facts/capabilities.toml`,
  keeping `tools/harness-facts`'s CLI (`check`, `list`, `get`) and module (`lookup`,
  `validate`, `view`) output contract unchanged.
- Enforce parity between `.gitattributes` (`filter=harness-state` patterns) and
  `harnesses.toml` (`filter_glob` entries) in the test suite.
- Update reference documentation (`AGENTS.md`, `README.md`,
  `docs/runbooks/adding-a-harness.md`) to describe the manifest workflow.

### Non-goals

- Folding `links.toml` or `tools/hq.toml` into `harnesses.toml`. Those files key on
  *homes* (`claude`, `claude-work`, `codex`, `codex-work`, `agy`, `agy-config`), whereas
  capability facts key on *runtime/capability slugs* (`claude-code`, home-less
  `pi-durable`) and live-state hygiene keys on *tracked settings files* in `hq` (one
  `claude/settings.json` despite two Claude homes).
- Replacing `.githooks/codex-trust`'s dynamic `[projects."<path>"]` TOML table store
  (`local/codex/trust.toml`), session-discovery adapters (`tools/hq_cli/`), transcript
  archiving (`tools/session_archive/`), or hook protocol adapters (`agy/hook`).
- Cross-repository harness enumerations (`<ops-checkout>/cli.toml`, `relay`, `tasks`,
  `obs`, `familiar`).
- Fixing `agy`'s atomic-save symlink replacement on `settings.json` (tracked and
  in flight separately under `hq-b24c39`).

### Anti-goals

- No generic serialization DSL hiding the structural difference between JSON object
  re-serialization (`indent=2, ensure_ascii=False`) and line-preserving TOML top-level
  key insertion.
- No dual-source fallback where `facts/capabilities.toml` and `harnesses.toml` both list
  harnesses or silently fall back when `harnesses.toml` is missing.
- No change to `local/live-picks.json`, `local/live-picks-pi.json`,
  `local/live-picks-agy.json`, `local/codex/trust.toml`, or `local/harness-state.lock`
  that would break rollback to pre-change commits (including `6b434eb`).

## 3. Constraints

1. **Rollback and in-flight lock safety**: `local/` record paths and payloads stay byte-
   compatible with existing hooks and the `6b434eb` rollback suite in
   `.githooks/test_live_picks.py`. Every `.githooks/` script loads and validates
   `harnesses.toml` once at startup before acquiring `local/harness-state.lock`, so a
   process already waiting on the lock across a checkout rollback completes from
   consistent in-memory definitions without re-reading disk.
2. **Clean-filter availability across commits**: Git invokes
   `.githooks/harness-state-clean %f` whenever staging or diffing filtered paths.
   `harnesses.toml` and its loader in `.githooks/harness_state.py` must land before or
   in the same commit that switches `.githooks/harness-state-clean` to read them, so
   every commit on the branch has a working clean filter during `git rebase` or
   `git bisect`.
3. **In-process `CLAUDE_JSON_KEYS` reader**: `tools/relay_cutover_bootstrap/inputs.py`
   (`claude_keys()`) loads `.githooks/harness-state-clean` via `runpy.run_path` and
   requires `CLAUDE_JSON_KEYS` in the module globals as a non-empty `tuple[str, ...]`.
   Until `hq-7e1e9c` retires `relay_cutover_bootstrap`, `.githooks/harness-state-clean`
   binds `CLAUDE_JSON_KEYS` directly from the loaded `claude-code` manifest entry.
4. **Self-contained `tools/harness-facts` and staged-tree `pre-commit`**:
   `tools/harness-facts` is linked at `~/.agents/bin/harness-facts`, loaded via
   `SourceFileLoader` by external consumers, and executed inside `.githooks/pre-commit`'s
   exported staged tree (`facts_check()`). It must remain a standalone single-file
   stdlib script with no import dependency on `.githooks/`, keep `"schema": 1` in its
   `view()` output, and validate `harnesses.toml` alongside `facts/capabilities.toml`
   inside the staged tree.
5. **Concurrent `hq-b24c39` work**: `hq-b24c39` is concurrently addressing `agy`'s
   atomic-save symlink replacement (touching `links.toml`, `.githooks/`, or `agy/hook`).
   Before landing, this branch rebases onto `main` if `hq-b24c39` merges first and
   preserves any symlink-convergence logic `hq-b24c39` introduces.
6. **Live global surface approval**: merging changes under `.githooks/` to `main`
   modifies a live hook surface across hosts sharing the checkout and requires explicit
   user approval at merge time.

## 4. Approaches considered

### Approach 1 (selected, agent call): Root `harnesses.toml` read by `.githooks/` and `tools/harness-facts`, removing `harnesses` from `facts/capabilities.toml`

Place a schema-1 declarative manifest at `<hq-checkout>/harnesses.toml` declaring all
six `hq` harnesses under `[harnesses.<slug>]`, with optional
`[harnesses.<slug>.live_state]` subtables for harnesses with tracked settings.
`.githooks/harness_state.py` loads and validates `live_state` entries for the four
`.githooks/` live-state scripts; `tools/harness-facts` reads the `[harnesses]` keys from
`harnesses.toml` (with `--manifest` override for standalone fixture tests), and
`facts/capabilities.toml` drops its top-level `harnesses = [...]`.

- **Pros**: True single source of truth for both capability facts and live-state hooks;
  `.githooks/pre-commit`'s staged-tree export automatically checks cross-file consistency
  between `harnesses.toml` and `facts/capabilities.toml`; keeps `tools/harness-facts`
  free of `.githooks/` imports and keeps `links.toml` focused on home-symlink routing.
- **Cons**: Requires updating scratch-checkout fixtures in `.githooks/test_*.py`,
  `tools/test_harness_facts.py`, and `tools/test_agy_hooks.py` to include a manifest
  fixture.

### Approach 2 (rejected): Extend `links.toml` with live-state and capability-fact metadata

Embed clean-filter keys, `live-picks` units/records, and capability-fact flags inside
`links.toml`.

- **Pros**: Adds no new top-level TOML file.
- **Cons**: Wrong entity boundary. `links.toml` keys on *home directories* (`claude`,
  `claude-work`, `codex`, `codex-work`, `agy`, `agy-config`), whereas capability facts
  key on *capability slugs* (`claude-code`, home-less `pi-durable`) and live-state hooks
  key on *tracked settings files* (`claude/settings.json` serves personal home links
  while `claude-work` points into untracked `local/`). Combining them forces synthetic
  indirections (`facts_slug`, dummy home-less groups) and couples main-checkout-only
  `tools/harness-links` to Git filters and capability facts.

### Approach 3 (rejected): `.githooks/harnesses.toml` for hooks only, keeping `harnesses = [...]` in `facts/capabilities.toml` with a parity check

Scope a `.githooks/harnesses.toml` manifest strictly to `.githooks/` and keep
`harnesses = [...]` in `facts/capabilities.toml`, asserting subset or equality in a test.

- **Pros**: Leaves `tools/harness-facts` and `facts/capabilities.toml` untouched.
- **Cons**: Fails the core single-source-of-truth goal of `hq-2eba07`. Onboarding a new
  harness would still require editing two harness lists in lockstep, and placing a
  repository-wide harness declaration under `.githooks/` buries domain configuration in
  Git hook plumbing.

## 5. Detailed design

### 5.1 `harnesses.toml` schema and shipped contents

`<hq-checkout>/harnesses.toml` is a UTF-8 TOML document with `schema = 1` and a
non-empty `[harnesses]` table keyed by canonical harness slug (`[a-z][a-z0-9-]*`):

```toml
# Declarative harness manifest: canonical harness slugs and tracked live-state configs.
# Capability facts (tools/harness-facts) read [harnesses]; Git live-state hooks
# (.githooks/harness_state.py) read [harnesses.<name>.live_state].
schema = 1

[harnesses.agy.live_state]
config = "agy/settings.json"
filter_glob = "agy/settings*.json"
format = "json"
clean_keys = ["model", "effort", "effortByBase", "trustedWorkspaces"]
picks_record = "local/live-picks-agy.json"
pick_units = [["model"], ["effort", "effortByBase"], ["trustedWorkspaces"]]

[harnesses.claude-code.live_state]
config = "claude/settings.json"
filter_glob = "claude/settings*.json"
format = "json"
clean_keys = ["model", "modelSettings", "effortLevel"]
picks_record = "local/live-picks.json"
pick_units = [["model", "modelSettings"], ["effortLevel"]]

[harnesses.codex.live_state]
config = "codex/config.toml"
filter_glob = "codex/config*.toml"
format = "toml"
clean_keys = [
  { table = "", keys = ["model", "model_reasoning_effort"] },
  { table = "tui", keys = ["screen_reader_detection_done"] },
  { table = 'marketplaces\.(?:"[^"]*"|[^."]+)', keys = ["last_updated", "last_revision"] },
]
clean_tables = ['tui\.model_availability_nux', 'projects\..+']
trust_table = 'projects\..+'
picks_record = "local/live-picks.json"
pick_units = [["model", "model_reasoning_effort"]]

[harnesses.opencode]

[harnesses.pi.live_state]
config = "pi/settings.json"
filter_glob = "pi/settings*.json"
format = "json"
clean_keys = ["defaultProvider", "defaultModel", "defaultThinkingLevel", "deviceId", "trackingId"]
unrestored_keys = ["deviceId", "trackingId"]
picks_record = "local/live-picks-pi.json"
pick_units = [["defaultProvider", "defaultModel"], ["defaultThinkingLevel"]]

[harnesses.pi-durable]
```

#### Validation invariants

1. **Top level and harness tables**:
   - Only `schema` (exact integer `1`, rejecting booleans and floats) and `harnesses`
     (non-empty table) are permitted at top level.
   - Every key under `harnesses` matches `^[a-z][a-z0-9-]*$` and maps to a table whose
     only permitted key is `live_state` (a table when present).
2. **Paths and routing (`live_state`)**:
   - `config` and `filter_glob` are required non-empty relative POSIX paths without
     leading `/`, empty segments, `.`, or `..`, and outside `local/`.
   - `fnmatch.fnmatch(config, filter_glob)` must be `True`.
   - Across all `live_state` entries, `config` values and `filter_glob` values are
     unique, and every `config` matches *only* its own entry's `filter_glob` (preventing
     ambiguous routing).
   - `format` is `"json"` or `"toml"`.
3. **Clean-filter fields (`live_state`)**:
   - When `format = "json"`:
     - Allowed keys: `config`, `filter_glob`, `format`, `clean_keys`,
       `unrestored_keys`, `picks_record`, `pick_units`.
     - `clean_keys` is a non-empty list of unique non-empty strings.
   - When `format = "toml"`:
     - Allowed keys: `config`, `filter_glob`, `format`, `clean_keys`, `clean_tables`,
       `trust_table`, `unrestored_keys`, `picks_record`, `pick_units`.
     - `clean_keys` is a list of `{ table = "<regex>", keys = ["<key>", ...] }` tables
       (only `table` and `keys` permitted; `table` compiles with `re.compile`; `keys`
       is a non-empty list of unique non-empty strings; `(table, key)` pairs are unique;
       at least one rule across `clean_keys` or `clean_tables` must exist).
     - `clean_tables` (optional, default `[]`) is a list of unique non-empty regex
       strings compiling with `re.compile`.
     - `trust_table` (optional) is a non-empty regex string that must appear in
       `clean_tables`.
4. **Picker units and partition invariant (`live_state`)**:
   - `picks_record` and `pick_units` must either both be present or both be omitted
     (supporting a future clean-only config with no `live-picks` preservation).
   - When present, `picks_record` is a relative POSIX path strictly under `local/`
     (`local/<filename>`, no `..`), and `pick_units` is a non-empty list of non-empty
     lists of non-empty strings, pairwise disjoint within and across units.
   - `unrestored_keys` (optional, default `[]`) is a list of unique non-empty strings,
     disjoint from `picked = flatten(pick_units)`.
   - **Partition invariant**: let `filterable_pick_keys` be `set(clean_keys)` for
     `"json"` and the set of top-level keys (`table == ""` in `clean_keys`) for
     `"toml"`. Then `set(picked) | set(unrestored_keys) == filterable_pick_keys`.
     Any key dropped by the filter at the pickable level must either belong to exactly
     one `pick_unit` or be explicitly listed in `unrestored_keys`, and no `pick_unit`
     may name an unfiltered key. This replaces the hardcoded `name in (CLAUDE, AGY)`
     check in `live-picks` with a general manifest invariant.

### 5.2 Shared loader in `.githooks/harness_state.py`

`.githooks/harness_state.py` defines `MANIFEST_PATH = REPO / "harnesses.toml"`,
`TOML_HEADER`, `TOML_KEY`, `ManifestError(ValueError)`, and immutable dataclasses:

- `TomlKeyRule(table_pattern: str, table_re: re.Pattern[str], keys: tuple[str, ...])`
- `LiveStateSpec(harness: str, config: str, filter_glob: str, format: str, json_clean_keys: tuple[str, ...], toml_clean_keys: tuple[TomlKeyRule, ...], toml_clean_tables: tuple[re.Pattern[str], ...], trust_table: re.Pattern[str] | None, unrestored_keys: tuple[str, ...], picks_record: str | None, pick_units: tuple[tuple[str, ...], ...])`
  with derived `pick_keys: tuple[str, ...]` (`sum(pick_units, ())`).
- `HarnessManifest(schema: int, harnesses: tuple[str, ...], by_harness: dict[str, LiveStateSpec | None], live_state: tuple[LiveStateSpec, ...])`
- `load_manifest(path: Path | None = None) -> HarnessManifest`: reads and validates
  `path or MANIFEST_PATH`, raising `ManifestError` with all problem lines joined. A
  helper `load_manifest_or_exit(tool: str, path: Path | None = None)` exits cleanly with
  `f"{tool}: {error}"` so hook scripts report manifest defects without tracebacks.

### 5.3 Live-state hook adapters

Format and store mechanics stay explicit in each tool; per-harness tables come from
`load_manifest_or_exit(...)` at module load time:

1. **`.githooks/harness-state-clean`**:
   - Imports `harness_state` (adding `Path(__file__).resolve().parent` to `sys.path` if
     invoked via `runpy.run_path` from outside `.githooks/`, such as
     `tools/relay_cutover_bootstrap/inputs.py`).
   - Loads `MANIFEST = harness_state.load_manifest_or_exit("harness-state-clean")`.
   - Exposes `CLAUDE_JSON_KEYS` from `MANIFEST.by_harness["claude-code"].json_clean_keys`
     (when `claude-code` has JSON `live_state`) for `relay_cutover_bootstrap/inputs.py`,
     plus `clean_json(text, keys)` and `clean_toml(text, key_rules, table_patterns)`.
   - Routes `argv[1]` by `[spec for spec in MANIFEST.live_state if fnmatch.fnmatch(path, spec.filter_glob)]`:
     - If `len(matches) != 1`, exits non-zero with
       `harness-state-clean: <path> is not a harness config; check .gitattributes`.
     - Dispatches `clean_json(text, spec.json_clean_keys)` for `"json"` and
       `clean_toml(text, spec.toml_clean_keys, spec.toml_clean_tables)` for `"toml"`.
     - Unconfigured `.toml` paths (e.g., `links.toml`, `harnesses.toml`) are now refused
       instead of passing through Codex's TOML rules.
2. **`.githooks/harness-state-refresh`**:
   - Derives `PATTERNS = tuple(spec.filter_glob for spec in MANIFEST.live_state)`.
   - Keeps its `live-picks capture`, `codex-trust sync`, `live-picks restore`, and
     `index.lock`-guarded restaging pipeline unchanged.
3. **`.githooks/live-picks`**:
   - Selects `SPECS = {spec.config: spec for spec in MANIFEST.live_state if spec.picks_record is not None}`,
     `OWNED = tuple(SPECS)`, and `RECORDS = {name: spec.picks_record for name, spec in SPECS.items()}`.
   - Dispatches every operation by `spec.format` (`"json"` vs `"toml"`) and
     `spec.pick_units`:
     - `"json"` uses record field `"values"` (`dict[str, Any]`), merging and restoring
       per unit in `spec.pick_units` and re-serializing with
       `json.dumps(..., indent=2, ensure_ascii=False) + "\n"`.
     - `"toml"` uses record field `"lines"` (`list[str]` of one-line top-level keys
       before the first table header):
       - `toml_lines(spec, text)` extracts one-line top-level assignments whose key is
         in `spec.pick_keys`, in file order.
       - `merged_lines(spec, saved, held)` generalizes multi-unit capture to TOML: for
         each `unit` in `spec.pick_units`, if `held` contains any line whose parsed key
         is in `unit`, keep `held`'s lines for `unit` in their live order; otherwise
         keep `saved`'s lines for `unit`. For a single-unit TOML config (`codex`), this
         reduces identically to replacing the saved lines whenever `held` is non-empty.
       - `missing(spec, text, saved)` generalizes multi-unit restore to TOML: collects
         `saved["lines"]` belonging to units in `spec.pick_units` that have zero keys in
         `held`, returning `{"state": "set", "lines": wanted}` when non-empty and `None`
         otherwise. No `if name == CODEX:` branch remains.
     - Post-write verification (`checked()`) runs `clean_json` or `clean_toml` with
       `spec`'s own filter rules so `live-picks` no longer calls `runpy.run_path` on
       `harness-state-clean`.
4. **`.githooks/codex-trust`**:
   - Reads `TOML_HEADER` and `MANIFEST.by_harness["codex"].trust_table` from
     `harness_state` instead of `runpy.run_path(str(HERE / "harness-state-clean"))`.

### 5.4 Capability facts (`facts/capabilities.toml` and `tools/harness-facts`)

- `facts/capabilities.toml` removes its top-level `harnesses = [...]` line; top-level
  keys allowed in `facts/capabilities.toml` become `{"schema", "facts"}` (an inline
  `harnesses` key in `facts/capabilities.toml` is refused as `unknown key harnesses`).
- `tools/harness-facts`:
  - Adds `DEFAULT_MANIFEST = CHECKOUT / "harnesses.toml"` and an optional
    `--manifest <path>` CLI flag on `harness-facts` (and on `check`, `list`, `get`,
    mirroring `--file`).
  - `validate(path=None, root=None, manifest=None)` loads both `manifest` (defaulting to
    `pathlib.Path(root) / "harnesses.toml"` when `root` is supplied and `manifest` is
    `None`, else `DEFAULT_MANIFEST`) and `path` (defaulting to `DEFAULT`), reporting
    manifest problems (`manifest: ...` or file read/TOML errors) alongside fact-file
    problems through `Invalid`.
  - Validates `manifest` for capability-fact needs: `schema == 1`, top-level keys only
    `{"schema", "harnesses"}`, `harnesses` is a non-empty table whose keys match `NAME`
    and whose values are tables containing at most `"live_state"` (a table when
    present). Detailed `live_state` field validation stays in
    `.githooks/harness_state.py` so `tools/harness-facts` neither imports `.githooks/`
    nor duplicates `live_state` rules.
  - Attaches the validated `list(manifest_data["harnesses"])` to the returned validated
    dict so `view(data)` and `lookup(fact, harness, path=None, manifest=None)` continue
    returning the exact schema-1 structure
    `{"schema": 1, "harnesses": ["agy", "claude-code", "codex", "opencode", "pi", "pi-durable"], "facts": {...}}`.
- `.githooks/pre-commit`: unchanged. Its `facts_check()` exports the full staged tree
  (including staged `harnesses.toml`, `facts/capabilities.toml`, `tools/harness-facts`,
  and probes) and runs `tools/harness-facts check`, refusing any commit that deletes or
  corrupts `harnesses.toml` or leaves an undeclared harness entry in
  `facts/capabilities.toml`.

### 5.5 Verification and documentation updates

- **Unit and integration tests (`just test`)**:
  - New `.githooks/test_harness_manifest.py` covering `harness_state.load_manifest`
    validation (every refusal rule in §5.1, partition invariant for JSON and TOML,
    clean-only entries without `live-picks`, overlapping `filter_glob` refusal) and
    asserting exact parity between `.gitattributes` `filter=harness-state` lines and
    shipped `harnesses.toml` `filter_glob` patterns.
  - `.githooks/test_harness_state_clean.py`: add refusal test for unconfigured `.toml`
    paths (e.g., `harnesses.toml`, `links.toml`), per-pattern routing across two
    distinct TOML configs in a fixture manifest, and `runpy.run_path` `CLAUDE_JSON_KEYS`
    exposure.
  - `.githooks/test_live_picks.py`: copy `harnesses.toml` into `repo` (keeping
    `HOOK_FILES` pinned to `6b434eb`'s file set for `pre_pi_hooks` rollback tests),
    rewrite `test_json_groups_refuse_overlap_unfiltered_keys_and_missing_claude_keys`
    against `harnesses.toml` mutations, and add a multi-unit TOML capture/restore/forget
    test proving a second TOML harness works without code edits.
  - `.githooks/test_codex_trust.py` and `.githooks/test_harness_state_refresh.py`: copy
    `harnesses.toml` into their scratch `repo` fixtures.
  - `tools/test_harness_facts.py`, `.githooks/test_pre_commit_facts.py`, and
    `tools/test_agy_hooks.py`: update scratch fixtures for `harnesses.toml` +
    `--manifest`, add manifest refusal and cross-file staged deletion/undeclared-harness
    pre-commit tests, and remove direct `tomllib` reading of `doc["harnesses"]` from
    `tools/test_agy_hooks.py`.
- **Reference docs**:
  - `AGENTS.md` (Layout), `README.md`, and `docs/runbooks/adding-a-harness.md` (§3.2–3.5
    and §4): replace instructions to edit constant tables across
    `harness-state-clean`, `harness-state-refresh`, `live-picks`, and
    `facts/capabilities.toml` with editing `harnesses.toml` (plus `.gitattributes`).

## 6. Agent calls and builder latitude

### Calls made in this design (for user review)

1. **Manifest location and scope**: placed at `<hq-checkout>/harnesses.toml` covering
   canonical harness slugs and tracked `live_state` rules, leaving `links.toml` (per-home
   symlinks) and `tools/hq.toml` (per-home resume flags) separate because their entity
   key is a home rather than a harness slug or tracked settings file.
2. **True single source for capability facts**: removed `harnesses = [...]` from
   `facts/capabilities.toml` instead of keeping two lists with a drift test, adding
   `--manifest` to `tools/harness-facts` for standalone fixture tests while preserving
   `view()`'s schema-1 JSON output.
3. **Explicit partition invariant (`unrestored_keys`)**: replaced `live-picks`'s
   hardcoded `name in (CLAUDE, AGY)` check with `unrestored_keys` (used by `pi` for
   `deviceId` and `trackingId`) so every clean-filtered pickable key must be either
   assigned to a `pick_unit` or explicitly marked unrestored.
4. **Generalizing TOML routing and multi-unit picks now**: resolved both second-TOML-
   harness hazards noted in `docs/runbooks/adding-a-harness.md` (§3.3 per-glob TOML
   clean routing and §3.4 multi-unit TOML `live-picks` without `if name == CODEX:`) as
   part of extracting the manifest.
5. **Keeping `codex-trust` separate while reading `trust_table` from the manifest**:
   kept dynamic `[projects."<path>"]` table persistence in `.githooks/codex-trust` as an
   explicit store adapter, sourcing its `trust_table` regex from `harnesses.toml`.

### Left to the builder

- Exact internal helper decomposition and error-message phrasing inside
  `.githooks/harness_state.py` (subject to existing CLI prefix conventions:
  `<tool>: <problem>` and existing test assertions in `.githooks/test_*.py` and
  `tools/test_harness_facts.py`).
- Ordering of commits in the implementation plan, provided `harnesses.toml` and
  `harness_state.py` land before or alongside `.githooks/harness-state-clean`.
