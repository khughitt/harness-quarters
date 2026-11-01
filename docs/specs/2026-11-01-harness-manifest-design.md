# Declarative harness manifest: one source of truth for live-state hooks and capability facts

Status: accepted for planning, 2026-11-01 (`hq-2eba07`, source `hq-6c8a9f`, accepted at
`077b8f6` with round-3 staged-blob and linked-worktree refinements folded in).
Extends `docs/specs/2026-10-06-residue-design.md` §4 (capability facts) and
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

Onboarding JSON-based `agy` in `hq-6c8a9f` required parallel per-harness constant edits
across five tracked files in `hq`, and a sixth file (`.githooks/codex-trust`) is coupled to
`.githooks/harness-state-clean` via `runpy.run_path`:

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
6. `.githooks/codex-trust`: loads `.githooks/harness-state-clean` via `runpy.run_path` at
   import time to obtain `TOML_HEADER`, `PROJECT_TRUST`, and `clean_toml`.

## 2. Goals, non-goals, and anti-goals

### Goals

- Declare every `hq` harness once in `<hq-checkout>/harnesses.toml` by its canonical
  slug (`agy`, `claude-code`, `codex`, `opencode`, `pi`, `pi-durable`), together with an
  optional `[harnesses.<slug>.live_state]` table for harnesses whose settings are
  tracked and filtered in `hq`.
- Drive `.githooks/harness-state-clean`, `.githooks/harness-state-refresh`,
  `.githooks/live-picks`, and `.githooks/codex-trust`'s trust-table pattern and TOML
  cleaner from `harnesses.toml` through `.githooks/harness_state.py`, eliminating parallel
  per-harness constant tables and `runpy.run_path` hook imports across those scripts.
- Make the clean filter fail closed (`git config filter.harness-state.required true` in
  `just setup`, with the identity `smudge = cat` a required filter needs to check files
  out (amended during implementation: Ruling 2)), actively verify that `filter.harness-state.required == true` and the smudge against the
  real repository's Git config in `.githooks/pre-commit` and
  `.githooks/harness-state-refresh` (so an existing clone that has not re-run `just setup`
  is caught automatically rather than relying on memory), and validate `harnesses.toml`
  (`live_state` rules included) plus `.gitattributes` parity on the staged tree in
  `.githooks/pre-commit`.
- Preserve Git lifecycle hook resilience: on a missing or invalid `harnesses.toml`,
  `harness-state-clean` and `pre-commit` fail hard, whereas `live-picks hook` and
  `codex-trust hook` (`post-checkout`, `post-merge`, `post-rewrite`) report the failure on
  stderr with their retry notice and exit `0` so completed Git operations do not report
  false failure.
- Generalize TOML handling so a second TOML harness requires only a `harnesses.toml`
  entry (and `.gitattributes` line): segment-bounded per-`filter_glob` routing in
  `harness-state-clean` and format-based (`"json"` vs `"toml"`) multi-unit handling in
  `live-picks`.
- Have `tools/harness-facts` read the declared harness list from `harnesses.toml` and
  remove the duplicate top-level `harnesses = [...]` list from `facts/capabilities.toml`,
  keeping `tools/harness-facts`'s CLI (`check`, `list`, `get`) and module (`lookup`,
  `validate`, `view`) output and positional-argument contracts unchanged.
- Update reference documentation (`AGENTS.md`, `README.md`,
  `docs/runbooks/adding-a-harness.md`) to describe the manifest workflow.

### Non-goals

- Folding `links.toml` or `tools/hq.toml` into `harnesses.toml`. Those files key on
  *homes* (`claude`, `claude-work`, `codex`, `codex-work`, `agy`, `agy-config`), whereas
  capability facts key on *runtime/capability slugs* (`claude-code`, home-less
  `pi-durable`) and live-state hygiene keys on *tracked settings files* in `hq` (one
  `claude/settings.json` despite two Claude homes).
- Moving `agy`'s home-symlink atomic-save adoption paths (`~/.gemini/antigravity-cli/settings.json`
  and `~/.gemini/config/{hooks,skills}.json`, shipped on `main` in `hq-b24c39` / `f09a9e0`
  and hardened further under open follow-up `hq-ece26a`) into `harnesses.toml`. Home
  paths belong to `links.toml` and `live-picks`'s anchored home-adoption adapter; putting
  `~/` paths into `harnesses.toml` would duplicate `links.toml`.
- Replacing `.githooks/codex-trust`'s dynamic `[projects."<path>"]` TOML table store
  (`local/codex/trust.toml`), session-discovery adapters (`tools/hq_cli/`), transcript
  archiving (`tools/session_archive/`), or hook protocol adapters (`agy/hook`).
- Cross-repository harness enumerations (`<ops-checkout>/cli.toml`, `relay`, `tasks`,
  `obs`, `familiar`).

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

1. **Fail-closed clean filter with active config verification, `REPO` resolution, rollback, and in-flight lock safety**:
   - `just setup` sets `git config filter.harness-state.required true` alongside
     `filter.harness-state.clean '.githooks/harness-state-clean %f'` and
     `git config filter.harness-state.smudge cat` (amended during implementation: Ruling 2): git treats a required filter
     with no smudge as fatal on every checkout, and `cat` changes no content. Without
     `required = true`, Git ignores a non-zero exit from `harness-state-clean` and stages
     the raw working-tree file, which would leak `model`, `effortLevel`, `deviceId`,
     `trackingId`, `trustedWorkspaces`, or Codex `[projects.*]` trust tables if
     `harnesses.toml` failed to load. Because local `.git/config` is not updated by
     `git pull` on an existing clone, both `.githooks/pre-commit` (reading the real
     repository's `--git-dir`, not the exported staged tree) and
     `.githooks/harness-state-refresh` verify `filter.harness-state.clean` and
     `filter.harness-state.required == true` (and `filter.harness-state.smudge ==
     EXPECTED_SMUDGE_FILTER`, `cat` (amended during implementation: Ruling 2)) via `harness_state.check_filter_config()`,
     refusing with `run 'just setup'` whenever `required` is unset or `false` or the
     smudge differs.
   - Every `.githooks/` tool resolves `HERE = Path(__file__).resolve().parent`,
     `REPO = HERE.parent`, and `MANIFEST_PATH = REPO / "harnesses.toml"`. Because
     `core.hooksPath` (`.githooks`) and `filter.harness-state.clean`
     (`.githooks/harness-state-clean %f`) are relative paths in Git config, Git executes
     the script inside whichever checkout or linked worktree invoked Git; `REPO` therefore
     resolves to that invoking tree's root and reads `<invoking-tree>/harnesses.toml`.
     `live-picks` and `codex-trust` continue skipping (`hook`) or refusing (CLI) linked
     worktrees via `CHECKOUT.linked_worktree()` **before** loading `harnesses.toml`, while
     `harness-state-clean` filters files in both the main checkout and linked worktrees
     using each tree's own `harnesses.toml`.
   - `local/` record paths and payloads stay byte-compatible with existing hooks and the
     `6b434eb` rollback suite in `.githooks/test_live_picks.py`. `live-picks` and
     `codex-trust` load `harnesses.toml` inside `main()` **before** acquiring
     `local/harness-state.lock` (and inside `hook` mode's `try ... except SystemExit`
     guard), protecting an **already-spawned** waiter process across a concurrent checkout
     rollback (`test_inflight_pi_capture_remains_safe_after_rollback`) without crashing at
     import time before `hook` error handling runs. After rolling back to a pre-manifest
     commit (or inside a linked worktree checked out at a pre-manifest commit), newly
     spawned hook processes execute that commit's older `.githooks/*` scripts, which
     ignore `harnesses.toml` and read the unchanged `local/` records.
2. **Clean-filter availability and staged-tree commit gating**:
   - Git invokes `.githooks/harness-state-clean %f` whenever staging, diffing, or
     stat-checking dirty filtered paths. `harnesses.toml` and `.githooks/harness_state.py`
     must land before or in the same commit that switches `.githooks/harness-state-clean`
     to read them, so every commit on the branch has a working clean filter during
     `git rebase` or `git bisect`.
   - Because there is no CI and `pre-commit` is the only automatic commit gate,
     `.githooks/pre-commit` runs both `tools/harness-facts check` and
     `.githooks/harness_state.py check --git-dir <real-git-dir>`, refusing any commit
     whose real repository lacks `filter.harness-state.required = true` or whose staged
     `harnesses.toml`, `facts/capabilities.toml`, probes, or `.gitattributes` violate
     `live_state` or capability-fact invariants.
3. **In-process `CLAUDE_JSON_KEYS` reader (`hq-7e1e9c` retirement boundary)**:
   - `tools/relay_cutover_bootstrap/inputs.py` (`claude_keys()`) loads
     `.githooks/harness-state-clean` via `runpy.run_path` and requires `CLAUDE_JSON_KEYS`
     in the module globals as a non-empty `tuple[str, ...]`. Until `hq-7e1e9c` retires
     `relay_cutover_bootstrap`, `.githooks/harness-state-clean` binds `CLAUDE_JSON_KEYS`
     from `MANIFEST.by_harness["claude-code"].json_clean_keys` when `claude-code` has JSON
     `live_state` (and leaves `CLAUDE_JSON_KEYS` unbound otherwise, with no silent empty-
     tuple fallback). Removing `claude-code` from `harnesses.toml`, changing its
     `live_state.format` from `"json"`, or emptying its `clean_keys` will break
     `relay_cutover_bootstrap/inputs.py` until `hq-7e1e9c` lands.
4. **Self-contained `tools/harness-facts` and backward-compatible `SourceFileLoader` API**:
   - `tools/harness-facts` is linked at `~/.agents/bin/harness-facts`, loaded via
     `SourceFileLoader` by external consumers (`agy/hook`, `ops` `claim-guard`), and
     executed inside `.githooks/pre-commit`'s exported staged tree. It must remain a
     standalone single-file stdlib script with no import dependency on `.githooks/`, keep
     `"schema": 1` in `view()`, and preserve positional call compatibility on
     `validate(path=None, root=None, manifest=None)` and
     `lookup(fact, harness, path=None, manifest=None)`.
5. **Integration with landed `hq-b24c39` (`f09a9e0`)**:
   - `main` (`26a1d50`, containing `f09a9e0` `hq-b24c39`) has been merged into
     `feat/hq-2eba07-harness-manifest` (via `git merge main` rather than `git rebase` so
     round-1 frozen spec commit `623f6f4` and retention-checkpoint basis `369f0dc` remain
     reachable in branch ancestry).
   - Inspection of `f09a9e0` confirms `agy`'s `live_state` schema fields (`config`,
     `filter_glob`, `format`, `clean_keys`, `picks_record`, `pick_units`) are unchanged.
     `hq-b24c39` added anchored home-symlink adoption in `links.toml` (`adopt`,
     `anchors`), `tools/harness-links`, `agy/hook`, and `.githooks/live-picks`
     (`detached_home`, `adopt_detached`), plus scratch-checkout fixtures in
     `tools/test_agy_hooks.py` (`make_agy_checkout`) and `tools/test_harness_links.py`
     (`fresh_clone`, `dirty_source`). `live-picks` preserves that home-adoption behavior
     while routing `adopt_detached` through `LiveStateSpec`, and those scratch fixtures
     copy `harnesses.toml` and set `filter.harness-state.required = true`.
6. **Live global surface approval**: merging changes under `.githooks/` and `justfile`
   hook wiring to `main` modifies a live hook surface across hosts sharing the checkout
   and requires explicit user approval at merge time.

## 4. Approaches considered

### Approach 1 (selected, agent call): Root `harnesses.toml` read by `.githooks/` and `tools/harness-facts`, removing `harnesses` from `facts/capabilities.toml`

Place a schema-1 declarative manifest at `<hq-checkout>/harnesses.toml` declaring all
six `hq` harnesses under `[harnesses.<slug>]`, with optional
`[harnesses.<slug>.live_state]` subtables for harnesses with tracked settings.
`.githooks/harness_state.py` houses the shared JSON/TOML cleaners and validates
`live_state` entries, `.gitattributes` parity, and `filter.harness-state.required` Git
config (at hook execution and in `.githooks/pre-commit`); `tools/harness-facts` reads
`[harnesses]` keys from `harnesses.toml` (with `--manifest` override for standalone
fixture tests), and `facts/capabilities.toml` drops its top-level `harnesses = [...]`.

- **Pros**: True single source of truth for both capability facts and live-state hooks;
  `.githooks/pre-commit`'s staged-tree export enforces cross-file consistency across
  `harnesses.toml`, `facts/capabilities.toml`, and `.gitattributes` while checking the
  real repository's fail-closed filter config; keeps `tools/harness-facts` free of
  `.githooks/` imports and keeps `links.toml` focused on home-symlink routing.
- **Cons**: Requires updating scratch-checkout fixtures in `.githooks/test_*.py`,
  `tools/test_harness_facts.py`, `tools/test_agy_hooks.py`, and
  `tools/test_harness_links.py` to include `harnesses.toml` and `required = true`.

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
2. **Paths, segment-bounded glob semantics, and pairwise glob disjointness (`live_state`)**:
   - `config` is a required non-empty directory-qualified relative POSIX path (at least
     one `/`, no leading or trailing `/`, no empty segments, `.`, `..`, or glob
     metacharacters `*`, `?`, `[`, `]`), outside `local/`.
   - `filter_glob` is a required non-empty directory-qualified relative POSIX glob (at
     least one `/`, no leading or trailing `/`, no empty segments, `.`, or `..`, outside
     `local/`). In `schema = 1`, `*` is the only permitted wildcard (`?`, `[`, `]`, and
     `**` are refused), and **each `/` segment contains at most one `*`**. Each segment
     compiles `*` to `[^/]*` (never crossing `/`), matching Git's `FNM_PATHNAME`
     `.gitattributes` rules for slash-containing patterns and `:(glob)<filter_glob>`
     pathspecs in `git diff-files`.
   - Each entry's compiled `filter_re` must full-match its own `config`.
   - Across all `live_state` entries, `config` values are unique, `filter_glob` values are
     unique, and **no two `filter_glob` patterns may overlap on any path**: two patterns
     with the same number of `/` segments overlap iff every corresponding segment pair
     `(seg_a, seg_b)` overlaps, decided by a direct prefix/suffix comparison (`seg_a == seg_b`
     when neither has `*`; `len(lit) >= len(p) + len(s) and lit.startswith(p) and lit.endswith(s)`
     when one is `p*s` and the other is literal `lit`; and
     `(p1.startswith(p2) or p2.startswith(p1)) and (s1.endswith(s2) or s2.endswith(s1))`
     when both are `p1*s1` and `p2*s2`). Overlapping patterns such as
     `agy/settings*.json` and `agy/settings-x*.json` are refused at load time (and in
     `pre-commit`), never deferred until a matching file appears at runtime.
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
   - `picks_record` and `pick_units` must either both be present or both be omitted.
     When both are omitted (a clean-only config with no `live-picks` preservation),
     `unrestored_keys` defaults to all `filterable_pick_keys` if omitted or must equal
     `filterable_pick_keys` if written explicitly.
   - When present, `picks_record` is a relative POSIX path strictly under `local/`
     (`local/<filename>`, no `..`), and `pick_units` is a non-empty list of non-empty
     lists of non-empty strings, pairwise disjoint within and across units.
   - `unrestored_keys` (optional, default `[]` when `pick_units` is present) is a list of
     unique non-empty strings, disjoint from `picked = flatten(pick_units)`.
   - **Partition invariant**: let `filterable_pick_keys` be `set(clean_keys)` for
     `"json"` and the set of top-level keys (`table == ""` in `clean_keys`) for
     `"toml"`. Then `set(picked) | set(unrestored_keys) == filterable_pick_keys` and
     `set(picked) & set(unrestored_keys) == ∅`. Every key dropped by the filter at the
     pickable level belongs to either one `pick_unit` or `unrestored_keys`. Nested TOML
     `clean_keys` (such as Codex's `tui.screen_reader_detection_done` and
     `marketplaces.*.last_*`) and non-trust `clean_tables` (`tui.model_availability_nux`)
     are ephemeral harness bookkeeping dropped by the clean filter and intentionally
     never restored by `live-picks` (`trust_table` is persisted separately by
     `codex-trust`).

#### Partition invariant across shipped `live_state` entries

| Harness | `filterable_pick_keys` | `flatten(pick_units)` | `unrestored_keys` |
| --- | --- | --- | --- |
| `agy` | `{model, effort, effortByBase, trustedWorkspaces}` | `(model, effort, effortByBase, trustedWorkspaces)` | `()` |
| `claude-code` | `{model, modelSettings, effortLevel}` | `(model, modelSettings, effortLevel)` | `()` |
| `codex` | `{model, model_reasoning_effort}` (`table == ""`) | `(model, model_reasoning_effort)` | `()` |
| `pi` | `{defaultProvider, defaultModel, defaultThinkingLevel, deviceId, trackingId}` | `(defaultProvider, defaultModel, defaultThinkingLevel)` | `(deviceId, trackingId)` |

#### Schema-bump policy (`schema = 1`)

`harnesses.toml` has two in-repository readers: `tools/harness-facts` (top-level shape and
harness slugs) and `.githooks/harness_state.py` (full `live_state` schema and
`.gitattributes` parity). Both reject unknown keys and any `schema != 1`. Adding or
removing harness entries or changing values within existing `schema = 1` keys keeps
`schema = 1`. Introducing any new top-level key, harness-table key, `live_state` key,
format, or glob wildcard syntax requires bumping `schema` (e.g. `schema = 2`) and updating
both `tools/harness-facts` and `.githooks/harness_state.py` in the same commit, which
`.githooks/pre-commit` enforces atomically on the staged tree.

### 5.2 Shared loader, config checks, and cleaners in `.githooks/harness_state.py`

`.githooks/harness_state.py` owns the manifest loader/validator, `.gitattributes` parity
check, real-repository filter-config check, and pure JSON/TOML clean-filter functions so
`.githooks/harness-state-clean`, `.githooks/harness-state-refresh`,
`.githooks/live-picks`, `.githooks/codex-trust`, and `.githooks/pre-commit` share one
import path with no `runpy` cycles:

- Constants: `HERE`, `REPO`, `MANIFEST_PATH = REPO / "harnesses.toml"`,
  `GITATTRIBUTES_PATH = REPO / ".gitattributes"`,
  `EXPECTED_CLEAN_FILTER = ".githooks/harness-state-clean %f"`,
  `EXPECTED_SMUDGE_FILTER = "cat"` (amended during implementation: Ruling 2), `TREE_SKIP`, `TOML_HEADER`, `TOML_KEY`.
- Exception: `ManifestError(ValueError)` carrying `problems: list[str]`.
- Immutable dataclasses:
  - `TomlKeyRule(table_pattern: str, table_re: re.Pattern[str], keys: tuple[str, ...])`
  - `LiveStateSpec(harness: str, config: str, filter_glob: str, filter_re: re.Pattern[str], format: str, json_clean_keys: tuple[str, ...], toml_clean_keys: tuple[TomlKeyRule, ...], toml_clean_tables: tuple[re.Pattern[str], ...], trust_table: re.Pattern[str] | None, unrestored_keys: tuple[str, ...], picks_record: str | None, pick_units: tuple[tuple[str, ...], ...])`
    with derived `pick_keys: tuple[str, ...]` (`sum(pick_units, ())`).
  - `HarnessManifest(schema: int, harnesses: tuple[str, ...], by_harness: dict[str, LiveStateSpec | None], live_state: tuple[LiveStateSpec, ...])`
- Loader, `.gitattributes` parity checker, and real-repository filter-config checker:
  - `load_manifest(path: Path | None = None) -> HarnessManifest`: reads and validates
    `path or MANIFEST_PATH`, raising `ManifestError` on any violation of §5.1.
  - `load_manifest_or_exit(tool: str, path: Path | None = None) -> HarnessManifest`:
    calls `load_manifest(path)` and raises `SystemExit(f"{tool}: {error}")` on
    `ManifestError` (no traceback).
  - `check_gitattributes(manifest: HarnessManifest, path: Path | None = None) -> None`:
    parses non-blank, non-comment lines of `path or GITATTRIBUTES_PATH`, refuses duplicate
    or negated/malformed `harness-state` filter attributes, and raises `ManifestError`
    unless the set of patterns carrying `filter=harness-state` equals
    `{spec.filter_glob for spec in manifest.live_state}`.
  - `check_filter_config(git_dir: Path | None = None) -> None`: checks the **real
    repository's** Git config (using `git --git-dir=<git_dir> config ...` when `git_dir`
    is supplied, or `git -C REPO config ...` otherwise; in a linked worktree, Git resolves
    the shared repository config through `commondir`) and raises `ManifestError` unless
    `filter.harness-state.clean == EXPECTED_CLEAN_FILTER` and
    `git config --bool --get filter.harness-state.required == "true"` and
    `filter.harness-state.smudge == EXPECTED_SMUDGE_FILTER` (amended during implementation: Ruling 2), naming
    `run 'just setup'` in the error message.
  - `check_clean_tree(manifest: HarnessManifest, root: Path | None = None) -> None`: walks
    `root or REPO` (skipping every directory named in `TREE_SKIP`: `.git`, `.worktrees`,
    `.venv`, `node_modules` and `local`, at any depth (amended during implementation: final review)) and, for every file whose relative POSIX path
    full-matches a `spec.filter_re`, verifies the file is valid UTF-8, parses under
    `clean_for_spec(spec, text)`, and satisfies `clean_for_spec(spec, text) == text`,
    raising `ManifestError` naming `git add --renormalize <path>` on any already-leaked
    staged blob.
  - CLI entrypoint
    (`python3 .githooks/harness_state.py check [--git-dir <path>] [--staged-tree]`): runs
    `manifest = load_manifest(MANIFEST_PATH)`,
    `check_gitattributes(manifest, GITATTRIBUTES_PATH)`, `check_filter_config(git_dir)`,
    and (when `--staged-tree` is passed) `check_clean_tree(manifest, REPO)`, printing
    `harness-state: <problem>` lines to stderr and exiting `2` on `ManifestError`.
- Pure cleaners (moved from `harness-state-clean`):
  - `clean_json(text: str, keys: Iterable[str]) -> str`: parses JSON, removes `keys`,
    and serializes with `json.dumps(data, indent=2, ensure_ascii=False) + "\n"`.
  - `clean_toml(text: str, key_rules: Iterable[TomlKeyRule], table_patterns: Iterable[re.Pattern[str]]) -> str`:
    line-preserving TOML cleaner taking explicit `TomlKeyRule` rules and whole-table
    `table_patterns` regexes instead of module globals.
  - `clean_for_spec(spec: LiveStateSpec, text: str) -> str`: dispatches `clean_json` or
    `clean_toml` using `spec`'s rules.

### 5.3 Hook wiring, live-state adapters, `pre-commit`, and failure-mode matrix

1. **`justfile` (`just setup`)**:
   - Adds `git config filter.harness-state.required true` immediately after
     `git config filter.harness-state.clean '.githooks/harness-state-clean %f'`, and
     `git config filter.harness-state.smudge cat` (amended during implementation: Ruling 2).
2. **`.githooks/harness-state-clean`**:
   - Prepends `str(Path(__file__).resolve().parent)` to `sys.path` if missing (so
     `runpy.run_path` callers outside `.githooks/` resolve `import harness_state`), then
     loads `MANIFEST = harness_state.load_manifest_or_exit("harness-state-clean")` at
     module load time (the clean filter must always fail hard on a bad manifest).
   - Re-exports `TOML_HEADER = harness_state.TOML_HEADER`,
     `TOML_KEY = harness_state.TOML_KEY`, `clean_json = harness_state.clean_json`, and
     `clean_toml = harness_state.clean_toml` (3-argument signature
     `(text, key_rules, table_patterns)`). Binds `CLAUDE_JSON_KEYS` from
     `MANIFEST.by_harness["claude-code"].json_clean_keys` **only** when `claude-code` has
     JSON `live_state` (leaving `CLAUDE_JSON_KEYS` unbound otherwise, with no silent `()`
     fallback, so `relay_cutover_bootstrap` fails immediately on a missing global).
   - Routes `argv[1]` by `[spec for spec in MANIFEST.live_state if spec.filter_re.fullmatch(path)]`
     (guaranteed `<= 1` match by §5.1 pairwise disjointness): if `len(matches) != 1`,
     exits non-zero with
     `harness-state-clean: <path> is not a harness config; check .gitattributes`;
     otherwise writes `harness_state.clean_for_spec(matches[0], text)`.
   - Error contract (amended during implementation: final review): under `required = true` an uncaught exception is fatal to git and
     prints a traceback, so `main` catches `ValueError` from `clean_for_spec` (invalid
     JSON, a non-object top level) and exits non-zero with
     `harness-state-clean: <path>: <error>; fix the file, then retry`; a
     `harness_state.py` that will not import (`ImportError`, `SyntaxError`, e.g. conflict
     markers) exits with `harness-state-clean: cannot load .githooks/harness_state.py:
     <error>; resolve or restore it`. `live-picks`, `codex-trust` and
     `harness-state-refresh` guard their import the same way: the two Git-hook tools exit
     `0` in hook mode with the retry notice, and fail with the message otherwise.
   - Mid-merge or mid-rebase recovery (amended during implementation: final review): `git checkout -- harnesses.toml` fails on an
     unmerged path; resolve the conflict or run `git merge --abort` /
     `git rebase --abort`. Never unset `required`.
3. **`.githooks/harness-state-refresh`**:
   - Does **not** load `harnesses.toml` at import time. Inside `main()`, it drains
     `sys.stdin.read()` first (avoiding `EPIPE` in the calling harness), runs
     `live-picks capture`, and inside its `try ... except SystemExit` block loads
     `MANIFEST = harness_state.load_manifest_or_exit("harness-state-refresh")` and calls
     `harness_state.check_filter_config()` (failing cleanly with `run 'just setup'` and
     skipping `git add` if either the manifest or `filter.harness-state.required` is
     invalid).
   - Derives `PATTERNS = tuple(f":(glob){spec.filter_glob}" for spec in MANIFEST.live_state)`
     so `git diff-files` uses segment-bounded glob matching identical to `.gitattributes`
     and `harness_state.py`, then runs `codex-trust sync`, `live-picks restore`, and
     `index.lock`-guarded restaging when `index.lock` is free, exiting non-zero with all
     collected step failures on stderr (which calling harnesses surface as a non-blocking
     `Stop`-hook warning and `agy/hook` logs best-effort without failing `SessionStart` or
     `PreToolUse`).
4. **`.githooks/live-picks`**:
   - Imports `TOML_HEADER`, `TOML_KEY`, and `clean_for_spec` directly from `harness_state`
     (removing `runpy.run_path` on `harness-state-clean`).
   - Does **not** load `harnesses.toml` at import time (building usage output lazily via a
     `usage()` helper that appends `(files: ...)` when `load_manifest()` succeeds and falls
     back to the static command synopsis otherwise). Inside `main(argv)`:
     1. Validates CLI argument shape (`capture`, `restore`, `sync`, `forget <file>`, or
        `hook post-checkout|post-merge|post-rewrite`) first.
     2. Checks `CHECKOUT.linked_worktree()` (returning `0` silently for `hook` and
        failing for CLI commands) and, for `hook post-checkout`, `CHECKOUT.rebasing()`
        (returning `0` silently).
     3. Loads `MANIFEST = harness_state.load_manifest_or_exit("live-picks")` **inside**
        `hook` mode's `try ... except SystemExit` block (and for CLI commands, directly in
        `main()`), in both cases **before** entering `CHECKOUT.locked()` on
        `local/harness-state.lock`. On a broken manifest, `live-picks hook <event>` prints
        `live-picks: <problem>` and
        `live-picks: a pick was not restored; the next turn end retries` to stderr and
        **exits `0`**; CLI commands exit non-zero.
   - Derives `SPECS = {spec.config: spec for spec in MANIFEST.live_state if spec.picks_record is not None}`,
     `OWNED = tuple(SPECS)`, and
     `RECORDS = {name: spec.picks_record for name, spec in SPECS.items()}` (validating
     `forget <file>` against `OWNED` once `SPECS` is loaded).
   - Dispatches by `spec.format` (`"json"` -> record field `"values"`, `"toml"` -> record
     field `"lines"`) and `spec.pick_units`:
     - **TOML extraction and duplicate-key refusal**: `parse(spec, text)` runs
       `tomllib.loads(text)` (which refuses any duplicate TOML keys in the live file).
       `toml_lines(spec, text)` extracts one-line top-level assignments before the first
       `TOML_HEADER` whose key is in `spec.pick_keys`, in file order. Both `pick()` and
       `invalid()` require duplicate-free keys (`len(keys) == len(set(keys))`), valid
       `tomllib.loads("".join(lines))`, and exact round-trip equality
       (`toml_lines(spec, "".join(lines)) == lines` and, in `pick()`, equality with
       `{k: data[k] for k in spec.pick_keys if k in data}`).
     - **Byte-stable `merged_lines(spec, saved, held)` across TOML units**: iterates
       `unit` in `spec.pick_units` **in manifest declaration order**. For each `unit`, if
       `held` contains at least one line whose parsed key is in `unit`, emits
       `[line for line in held if key_of(line) in unit]` (preserving live order within
       that unit); otherwise emits `[line for line in saved_lines if key_of(line) in unit]`
       (preserving saved order within that unit), where `saved_lines` is
       `saved["lines"]` when `saved` has `state == "set"` and `[]` otherwise. When `held`
       is empty, `capture()` keeps the existing `if held:` guard (writing nothing), and
       for single-unit `codex` (`pick_units = [["model", "model_reasoning_effort"]]`), a
       non-empty `held` produces `list(held)`, byte-identical to pre-manifest records.
     - **Multi-unit TOML `missing(spec, text, saved)`**: iterates `unit` in
       `spec.pick_units` in declaration order and collects
       `[line for line in saved["lines"] if key_of(line) in unit]` for each `unit` having
       zero keys in `held`, returning `{"state": "set", "lines": wanted}` if `wanted` is
       non-empty and `None` otherwise. No `if name == CODEX:` branch remains.
     - **`without_pick(spec, text)` (`forget`) vs `unrestored_keys`**: removes
       `spec.pick_keys` only for **both** JSON and TOML, leaving any live
       `unrestored_keys` (such as `pi`'s `deviceId` and `trackingId` or a future TOML
       installation ID) untouched in the working file so `forget` resets picker defaults
       without wiping installation identity. Because `clean_for_spec` strips both
       `pick_keys` and `unrestored_keys`, `checked()`
       (`clean_for_spec(spec, result) == clean_for_spec(spec, text)`) holds in both
       formats. For `codex` (`unrestored_keys = ()`), `spec.pick_keys` equals all
       filterable top-level keys (`("model", "model_reasoning_effort")`), matching current
       behavior.
     - **Anchored home-symlink adoption (`hq-b24c39`)**: preserves `detached_home`,
       `relink_home`, and `adopt_detached` for `"agy/settings.json"` (`AGY_HOME`,
       `AGY_LINK`, `AGY_ANCHORS`) as an explicit home-adoption adapter while updating
       `adopt_detached` to dispatch through `spec` (`merge_picks(spec, saved, h_picks)`
       and `field(spec)`; the spec's `spec_field` name was left to the builder (amended during implementation: final review)).
5. **`.githooks/codex-trust`**:
   - Does **not** load `harnesses.toml` at import time. Inside `main(argv)`, after
     validating CLI arguments and `linked_worktree()` (and `rebasing()` on
     `hook post-checkout`), loads
     `MANIFEST = harness_state.load_manifest_or_exit("codex-trust")` and resolves
     `CODEX_SPEC = MANIFEST.by_harness.get("codex")` (failing cleanly if `codex` is
     absent, not `"toml"`, or has `trust_table is None`) **inside** `hook` mode's
     `try ... except SystemExit` block and **before** `locked()`. On a broken manifest,
     `codex-trust hook <event>` prints `codex-trust: <problem>` and
     `codex-trust: trust not restored; the next turn end retries` to stderr and **exits
     `0`**; CLI commands exit non-zero.
   - Refuses (`codex-trust: harnesses.toml: codex live_state config is ..., not
     'codex/config.toml'`) when the codex entry's `config` is not `codex/config.toml`,
     the path `LIVE_NAME` it reads and writes (amended during implementation: final review).
   - Uses `harness_state.TOML_HEADER`, `CODEX_SPEC.trust_table`, and
     `harness_state.clean_for_spec(CODEX_SPEC, ...)` instead of `runpy.run_path`.
6. **`.githooks/pre-commit`**:
   - Resolves the real repository's absolute Git directory first
     (`real_git_dir = os.path.abspath(git("rev-parse", "--git-dir"))`), exports
     `staged_tree` once during `main()` with `-c filter.harness-state.smudge=cat` forced on
     the `checkout-index` (amended during implementation: Ruling 2) (so the export never depends on the smudge config that
     `manifest_check` is about to report on), and runs both `facts_check(tree)`
     (`tools/harness-facts check`) and
     `manifest_check(tree, git_dir=real_git_dir)`
     (`python3 <tree>/.githooks/harness_state.py check --git-dir <real_git_dir> --staged-tree`).
   - Because `staged_tree` is a plain directory checkout without `.git`, passing
     `--git-dir <real_git_dir> --staged-tree` checks `harnesses.toml`, `.gitattributes`,
     and the cleanliness of every staged settings blob (`clean_for_spec(spec, blob) == blob`,
     catching blobs staged earlier while `required` was unset or after a rebase/bisect across
     pre-manifest commits) from the **staged tree**, while checking
     `filter.harness-state.clean` and `filter.harness-state.required == true` from the
     **real repository's** Git config (including from linked worktrees via `commondir`).
   - `manifest_check(tree=None, git_dir=None)` (resolving `git_dir` and exporting its own
     staged tree when called directly in tests with `tree=None`, matching
     `facts_check(tree=None)`) refuses if `.githooks/harness_state.py` is unstaged/missing
     in `tree` or if `harness_state.py check` exits non-zero, rewriting `<tree>/` prefixes
     out of stderr.

#### Summary of failure handling when `harnesses.toml` or filter config is invalid

| Entrypoint | Trigger | Exit code and behavior on invalid/missing `harnesses.toml` or missing `required = true` |
| --- | --- | --- |
| `harness-state-clean <path>` | `git add` / `diff` / `status` (`filter=harness-state`, `required = true`) | Prints `harness-state-clean: ...` on stderr and **exits non-zero**; Git fails closed without staging unfiltered bytes. |
| `pre-commit` (`facts_check` + `manifest_check`) | `git commit` | Prints `harness-facts: ...` / `harness-state: ...` on stderr and **exits `1`**, blocking the commit. |
| `live-picks hook <event>` & `codex-trust hook <event>` | Git `post-checkout`, `post-merge`, `post-rewrite` | Skips silently (`0`) in linked worktrees and mid-rebase `post-checkout`; in main checkout, prints `<tool>: ...` + retry notice on stderr and **exits `0`** so the completed Git command succeeds. |
| `live-picks` & `codex-trust` CLI (`capture`, `restore`, `sync`, `forget`) | Direct CLI or child of `harness-state-refresh` | Prints `<tool>: ...` on stderr and **exits non-zero** before taking `local/harness-state.lock`. |
| `harness-state-refresh` | Harness `Stop` hook / `pi` extension / `agy/hook` | Drains stdin first, prints `harness-state-refresh: ...` on stderr without running `git add`, and **exits non-zero** (non-blocking `Stop`-hook warning in harnesses; logged best-effort by `agy/hook`). |

### 5.4 Capability facts (`facts/capabilities.toml` and `tools/harness-facts`)

- `facts/capabilities.toml` removes its top-level `harnesses = [...]` line; top-level
  keys allowed in `facts/capabilities.toml` become `{"schema", "facts"}` (an inline
  `harnesses` key in `facts/capabilities.toml` is refused as `unknown key harnesses`).
- `tools/harness-facts`:
  - Adds `DEFAULT_MANIFEST = CHECKOUT / "harnesses.toml"` and an optional
    `--manifest <path>` CLI flag on `harness-facts` and on `check`, `list`, and `get`
    (mirroring `--file`).
  - Preserves backward-compatible positional signatures for `SourceFileLoader` callers:
    - `validate(path=None, root=None, manifest=None)`
    - `lookup(fact, harness, path=None, manifest=None)`
    Existing 1- or 2-argument positional calls to `validate` and 2- or 3-argument
    positional calls to `lookup` behave identically without code changes.
  - When `manifest is None`, `validate` defaults `manifest` to
    `pathlib.Path(root) / "harnesses.toml"` if `root is not None`, else
    `DEFAULT_MANIFEST`.
  - Validates `manifest` for capability-fact needs: `schema == 1` (exact `int`),
    top-level keys only `{"schema", "harnesses"}`, `harnesses` is a non-empty table whose
    keys match `NAME` and whose values are tables containing at most `"live_state"` (a
    table when present). Detailed `live_state` validation runs in
    `.githooks/harness_state.py` (invoked alongside `harness-facts check` in
    `.githooks/pre-commit`).
  - Attaches `list(manifest_data["harnesses"])` to the validated dict so `view(data)` and
    `lookup(...)` continue returning the exact schema-1 structure
    `{"schema": 1, "harnesses": ["agy", "claude-code", "codex", "opencode", "pi", "pi-durable"], "facts": {...}}`.

### 5.5 Behavior changes and compatibility notes

1. **Clean filter fails closed (`filter.harness-state.required = true`) with active enforcement**:
   `harness-state` defines a `clean` filter and an identity `smudge = cat` (amended during implementation: Ruling 2) (git treats
   a required filter's missing smudge as fatal on checkout). While `harnesses.toml`
   is broken and `required = true`, `git add`, `git diff`, and `git status` (when a
   filtered settings file's working-tree stat differs from the index) fail closed instead
   of staging or diffing unfiltered picks. Recovery requires only fixing `harnesses.toml`
   (e.g. `git checkout -- harnesses.toml`); never unset `filter.harness-state.required`.
   If an existing clone has not re-run `just setup` after pulling (or holds a differently
   spelled `filter.harness-state.clean` command such as a stale absolute path), both
   `harness-state-refresh` (at the next turn end) and `pre-commit` (at the next commit)
   detect the mismatch in the real repository's Git config and refuse with
   `run 'just setup'`; `pre-commit` also refuses any already-staged raw settings blob until
   `git add --renormalize <path>` re-filters the index.
2. **Unconfigured `.toml` paths are refused by `harness-state-clean`**: previously, any
   `.toml` path passed to `harness-state-clean` fell through `elif path.endswith(".toml")`
   and had Codex's TOML rules applied; now only paths matching a declared
   `live_state.filter_glob` are accepted, and unconfigured `.toml` paths (e.g.
   `harnesses.toml`, `links.toml`) exit non-zero like unconfigured `.json` paths.
3. **Segment-bounded `filter_glob` matching**: `harness_state.py` (`*` -> `[^/]*`) and
   `harness-state-refresh` (`:(glob)<filter_glob>`) no longer match across `/`
   (e.g. `claude/settings*.json` does not match `claude/settings/nested.json`), aligning
   with `.gitattributes`.
4. **`CLAUDE_JSON_KEYS` coupling until `hq-7e1e9c`**: `tools/relay_cutover_bootstrap/inputs.py`
   reads `CLAUDE_JSON_KEYS` from `.githooks/harness-state-clean` via `runpy.run_path`;
   `claude-code` must retain a non-empty JSON `live_state.clean_keys` entry in
   `harnesses.toml` until `hq-7e1e9c` retires `relay_cutover_bootstrap`.

### 5.6 Verification and documentation updates

- **Unit and integration tests (`just test`)**:
  - New `.githooks/test_harness_manifest.py`:
    - `harness_state.load_manifest` validation for every §5.1 rule (schema type/value,
      slug regex, partition invariant for JSON/TOML/clean-only entries, bad regexes,
      `trust_table` not in `clean_tables`, `picks_record` outside `local/`, multi-`*`
      segment refusal).
    - Segment-bounded glob matching (`claude/settings/nested.json` rejected), load-time
      prefix/suffix refusal of overlapping `filter_glob` patterns (`agy/settings*.json` vs
      `agy/settings-x*.json`), `check_gitattributes` parity against shipped
      `.gitattributes`, `check_filter_config` refusal when `required` is unset or `false`,
      and `git check-attr filter` agreement across sample paths.
    - Direct Python unit tests for `harness_state.clean_json` and 3-argument
      `harness_state.clean_toml(text, key_rules, table_patterns)`.
    - End-to-end fail-closed Git filter test: with `just setup` (`required = true`),
      corrupting or deleting `harnesses.toml` (or routing an unconfigured `.toml` path
      through `filter=harness-state`) causes `git add` on a dirty `pi/settings.json` /
      `claude/settings.json` to exit non-zero without staging `deviceId`, `trackingId`, or
      `model`.
    - Cross-boundary branch-switch test with `filter.harness-state.required = true`: in a
      scratch repository holding a pre-manifest branch (pre-manifest hooks, no
      `harnesses.toml`) and a post-manifest branch (`harnesses.toml` + manifest-driven
      hooks) with dirty live picks in `claude/settings.json` and `codex/config.toml`,
      verify `git switch` in both directions succeeds cleanly, preserves live picks, and
      leaves `git status` clean.
  - `.githooks/test_harness_state_clean.py`: subprocess CLI tests for unconfigured
    `.toml` refusal (`harnesses.toml`, `links.toml`) and `runpy.run_path` exposure of
    `CLAUDE_JSON_KEYS` (including absence when `claude-code` has no JSON `live_state`),
    `clean_json`, and 3-argument `clean_toml` (existing subprocess tests in
    `test_harness_state_clean.py` and `test_codex_trust.py` invoke the CLI binary and keep
    their call sites).
  - `.githooks/test_live_picks.py`:
    - Copy `harnesses.toml` into `repo` and set `filter.harness-state.required = true`;
      keep `HOOK_FILES` pinned to `6b434eb`'s filenames so `install_pre_pi_hooks`
      installs old hook scripts without needing `harnesses.toml` (including verifying
      `6b434eb` hooks succeed when `harnesses.toml` is absent and that single-unit `codex`
      `local/live-picks.json` bytes are byte-identical across current and `6b434eb`
      hooks).
    - Test broken/missing `harnesses.toml` in both modes: `live-picks hook post-merge`
      (and `git switch` triggering `post-checkout`) reports the manifest error + retry
      notice on stderr and exits `0` (and exits `0` silently in a linked worktree), while
      `live-picks capture` / `sync` / `forget` exit non-zero.
    - Replace `test_json_groups_refuse_overlap_unfiltered_keys_and_missing_claude_keys`
      with manifest-mutation refusal tests, and add multi-unit TOML capture/restore/forget
      tests covering unit declaration-order stability, duplicate-key refusal, and
      `unrestored_keys` preservation on `forget`.
  - `.githooks/test_codex_trust.py` and `.githooks/test_harness_state_refresh.py`:
    - Copy `harnesses.toml` into `repo` and set `filter.harness-state.required = true`.
    - Add broken-manifest hook-mode test in `test_codex_trust.py` (`codex-trust hook`
      reports retry notice and exits `0`, CLI exits non-zero).
    - Add tests in `test_harness_state_refresh.py` verifying `harness-state-refresh`
      drains stdin and exits non-zero without staging when `harnesses.toml` is broken or
      `filter.harness-state.required` is unset/`false`.
  - `.githooks/test_pre_commit.py` and `.githooks/test_pre_commit_facts.py`:
    - Add stub `.githooks/harness_state.py` and `filter.harness-state.{clean,required}`
      to `test_pre_commit.py`'s `world` fixture, plus tests verifying `pre-commit` runs
      cleanly from a linked worktree (`git worktree add`) and refuses when
      `filter.harness-state.required` is unset or `false` or `filter.harness-state.clean`
      drifts in the real repository.
    - Add `harnesses.toml`, `.githooks/harness_state.py`, `.gitattributes`, and
      `filter.harness-state.{clean,required}` to `test_pre_commit_facts.py` with tests
      proving `pre-commit` refuses staged `live_state` violations (bad regex, partition
      violation, overlapping `filter_glob`), staged `.gitattributes` drift, already-leaked
      raw settings blobs staged before `just setup` (until `git add --renormalize <path>`
      cleans the index), missing `filter.harness-state.required = true` in the real repo,
      staged deletion of `harnesses.toml` or `.githooks/harness_state.py`, and undeclared
      harnesses in `facts/capabilities.toml`.
  - `tools/test_harness_facts.py`, `tools/test_agy_hooks.py`, and
    `tools/test_harness_links.py`:
    - Update `tools/test_harness_facts.py` fixtures for `harnesses.toml` / `--manifest`
      and test positional 2- and 3-arg `lookup()` / `validate()` backward compatibility.
    - Update `tools/test_agy_hooks.py` (`write_facts_fixture` to stop reading
      `doc["harnesses"]` from `facts/capabilities.toml`, and `make_agy_checkout` to copy
      `harnesses.toml` and set `filter.harness-state.required = true`).
    - Update `tools/test_harness_links.py` (`fresh_clone` and
      `test_fresh_clone_strips_live_agy_picks_from_dirty_source_checkout` to copy working
      `harnesses.toml`, and `test_setup_is_idempotent_and_creates_only_the_rules_directory`
      to assert `filter.harness-state.required == "true"`).
- **Reference docs**:
  - `AGENTS.md` (Layout and Gates), `README.md`, and
    `docs/runbooks/adding-a-harness.md` (§3.2–3.5 and §4): document `harnesses.toml`,
    `filter.harness-state.required = true` (`just setup`), recovery from a broken
    manifest (`git checkout -- harnesses.toml`), and staged `harness_state.py check`
    validation in `pre-commit`.

## 6. Agent calls and builder latitude

### Calls made in this design (for user review)

1. **Manifest location and scope**: placed at `<hq-checkout>/harnesses.toml` covering
   canonical harness slugs and tracked `live_state` rules, leaving `links.toml` (per-home
   symlinks and `agy` anchored home-adoption declarations) and `tools/hq.toml` (per-home
   resume flags) separate because their entity key is a home rather than a harness slug
   or tracked settings file.
2. **Fail-closed filter, active config verification, and staged-tree `live_state` commit gate**:
   added `filter.harness-state.required = true` to `just setup`, verified it against the
   real repository's Git config in both `harness-state-refresh` and `pre-commit`
   (`harness_state.py check --git-dir`), and gated `live_state` + `.gitattributes` parity
   in `pre-commit`, while keeping Git `post-*` hooks (`live-picks hook`,
   `codex-trust hook`) exit-`0` on manifest errors via deferred pre-lock loading in
   `main()`. The filter's identity `smudge = cat` is part of the verified config (amended during implementation: Ruling 2).
3. **True single source for capability facts**: removed `harnesses = [...]` from
   `facts/capabilities.toml`, adding trailing `manifest=None` / `--manifest` to
   `tools/harness-facts` while preserving positional `SourceFileLoader` compatibility and
   `view()`'s schema-1 JSON output.
4. **Explicit partition invariant (`unrestored_keys`) and `forget` symmetry**: replaced
   `live-picks`'s hardcoded `name in (CLAUDE, AGY)` check with `unrestored_keys` and
   kept `forget` (`without_pick`) scoped to `spec.pick_keys` in both JSON and TOML so
   resetting picker defaults never wipes live installation IDs.
5. **Segment-bounded, single-`*` pairwise-disjoint `filter_glob` and multi-unit TOML picks**:
   matched `.gitattributes` segment-bounded `*` semantics across `harness_state.py` and
   `harness-state-refresh` (`:(glob)`), refused overlapping `filter_glob` patterns at
   load time via per-segment prefix/suffix comparison, and generalized unit-ordered TOML
   `live-picks` without `if name == CODEX:`.
6. **Shared cleaners in `harness_state.py` with `codex-trust` kept as store adapter**:
   moved `clean_json` and 3-argument `clean_toml` into `.githooks/harness_state.py`
   (re-exported by `harness-state-clean` alongside fail-early `CLAUDE_JSON_KEYS`),
   eliminating `runpy.run_path` from `live-picks` and `codex-trust` while keeping dynamic
   `[projects."<path>"]` persistence in `.githooks/codex-trust`.

### Left to the builder

- Exact internal helper decomposition and error-message phrasing inside
  `.githooks/harness_state.py` (subject to existing CLI prefix conventions:
  `<tool>: <problem>` and existing test assertions in `.githooks/test_*.py` and
  `tools/test_harness_facts.py`).
- Staged commit structure in the implementation plan, split into at least three ordered
  lands so each slice is independently reviewable and leaves every commit with a working
  clean filter:
  1. `harnesses.toml`, `.githooks/harness_state.py` (manifest loader, cleaners,
     `.gitattributes` parity and `check_filter_config`), and `tools/harness-facts` +
     `facts/capabilities.toml` (with unit tests).
  2. Live-state hook migration to `harnesses.toml` (`.githooks/harness-state-clean`,
     `.githooks/harness-state-refresh` pattern derivation, `.githooks/live-picks`,
     `.githooks/codex-trust` and their test suites, including rollback tests).
  3. Fail-closed `required = true` setup and enforcement (`justfile`,
     `check_filter_config` enforcement in `.githooks/harness-state-refresh` and
     `.githooks/pre-commit`, fail-closed and cross-boundary branch-switch tests,
     `test_pre_commit*` / `test_harness_links.py`, and reference docs `AGENTS.md`,
     `README.md`, `docs/runbooks/adding-a-harness.md`).
