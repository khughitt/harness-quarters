# Adding an agent harness

Integrating a coding-agent harness spans `hq` (home routing, live-state hygiene,
capability facts, session discovery, transcript archiving) and five consumer
repositories (`lore`, `ops`, `relay`, `tasks`, `obs`). Cross-repository paths below
use `<hq-checkout>`, `<lore-checkout>`, `<ops-checkout>`, `<relay-checkout>`,
`<tasks-checkout>`, and `<obs-checkout>` so examples carry no host layout; paths
without a checkout prefix are relative to `<hq-checkout>`.

Not every harness integrates every layer on day one. Existing harnesses sit at four
incremental depths:

| Depth | Examples | Layers wired |
| --- | --- | --- |
| Minimal instructions + process detection | `opencode` | `links.toml`, `facts/capabilities.toml`, `<relay-checkout>` server-plugin adapter, `<tasks-checkout>` `HARNESS_COMMS`, `agents/skills/session-logs/SKILL.md` |
| Pinned runtime + live-state hygiene + probes | `pi`, `pi-durable` | Adds `pi/` pinned install and launcher, `.gitattributes` + `harness-state-clean` + `live-picks`, `pi/extensions/harness-state.ts` refresh, `pi/probes/` |
| Split homes + workspace trust + hook refresh | `agy` | Splits `[harness.agy]` and `[harness.agy-config]`, links `agy/skills.json`, preserves `trustedWorkspaces` in `live-picks`, triggers `harness-state-refresh` from `agy/hooks.json` `Stop`, maps native tools in `<lore-checkout>` `using-superpowers` |
| Full fleet integration | `claude-code`, `codex` | Adds personal and work homes, `ops-profile` + `SessionStart` hooks, `claim-guard`, `relay` hook installation, `tasks` native session provenance, `tt` test-run provenance, `hq sessions`, `session-archive`, `session-episodes`, `obs` adapters |

## 1. Home routing and surface delivery (`hq`, `lore`)

### Naming

Pick a canonical lowercase slug matching `[a-z][a-z0-9-]*` for
`facts/capabilities.toml` and cross-project `--harness` flags (`claude-code`,
`codex`, `opencode`, `pi`, `agy`). Where a harness has distinct execution modes with
different durability or capability guarantees, declare separate fact slugs (`pi` and
`pi-durable`). Note where existing consumers use short home stems instead of the
canonical fact slug:

- `links.toml` names `[harness.<home>]` groups by home role (`claude`, `claude-work`,
  `codex`, `codex-work`, `opencode`, `pi`, `agy`, `agy-config`).
- `tools/hq_cli/` and `<ops-checkout>/bin/ops-profile` currently key Claude Code as
  `claude` rather than `claude-code`, while `facts/capabilities.toml`,
  `<ops-checkout>/hooks/claim-guard`, `<relay-checkout>`, `<tasks-checkout>`,
  `agents/bin/session-episodes`, and `<obs-checkout>` use `claude-code`. For a new
  harness, keep one slug across every layer unless a split home requires `<slug>-config`
  or `<slug>-work` in `links.toml`.

### Declaring homes in `links.toml`

Add `[harness.<name>]` and `[harness.<name>.links]` in `links.toml`. Targets are
either `<hq-checkout>`-relative or `<project>:<relative-path>`, which
`tools/harness-links` resolves through `tasks projects --paths --json`:

```toml
[harness.<name>]
home = "~/.<harness>"
[harness.<name>.links]
"AGENTS.md" = "lore:instructions/AGENTS.md"
"settings.json" = "<name>/settings.json"
"hooks.json" = "<name>/hooks.json"
```

- **Global instructions**: always target `lore:instructions/AGENTS.md` under the
  filename the harness loads globally (`CLAUDE.md` for Claude Code; `AGENTS.md` for
  Codex, OpenCode, `pi`, and Antigravity).
- **Split homes**: when a harness separates app-data state from customization files,
  declare two groups (for example, `[harness.agy]` at `~/.gemini/antigravity-cli` for
  `settings.json` and `[harness.agy-config]` at `~/.gemini/config` for `AGENTS.md`,
  `hooks.json`, and `skills.json`). Separate work homes get their own group
  (`[harness.<name>-work]`).
- **Pinned CLI runtime (optional)**: when `hq` pins and launches the harness itself
  (as `pi/package.json` + `pi/bin/pi` and `relay/package.json` + `relay/bin/relay`
  do), add `"~/.local/bin/<tool>" = "<name>/bin/<tool>"` under `[required]` in
  `links.toml` and add a `just <name>-install` recipe in `justfile` that installs
  with `npm ci --ignore-scripts` under `~/.local/share/<name>/<version>` outside the
  synced checkout.

### Skills delivery and Superpowers tool mapping

`[required]` in `links.toml` populates `~/.agents/skills/` as one symlink per skill
into its owning checkout (`lore`, `flows`, `tasks`, `ops`, `hq`). Deliver that
surface to the harness by the lightest route it supports:

1. **Native `~/.agents/skills` discovery** (`codex`, `pi`): no per-skill links needed
   in `[harness.<name>.links]`.
2. **Directory manifest** (`agy`): link a tracked manifest such as `agy/skills.json`
   containing `{"entries": [{"path": "~/.agents/skills"}]}`.
3. **Home-local skill directory** (`claude`): link required skills individually under
   `skills/<skill-name>` in `[harness.<name>.links]`.

When the harness's built-in tool names differ from Claude Code's (`Bash`, `Read`,
`Write`, `Edit`, `Task`, `TodoWrite`), add a tool mapping document at
`<lore-checkout>/vendor/superpowers/skills/using-superpowers/references/<name>-tools.md`
(following `codex-tools.md` and `antigravity-tools.md`) and link it under **Platform
Adaptation** in
`<lore-checkout>/vendor/superpowers/skills/using-superpowers/SKILL.md`.

### Untracked `local/` files and `.ops-check.toml`

- **Work and host state (`local/`)**: keep work profiles, rule directories, saved
  trust, and machine-owned pick records under `local/` (`local/claude/settings.work.json`,
  `local/codex/config.work.toml`, `local/codex/rules`, `local/live-picks-*.json`).
  `.githooks/pre-commit` refuses any staged path under `local/`. If a public clone
  needs an empty directory under `local/` so `just link --apply` has a target before
  work configs arrive from another host, create that directory in `justfile`'s
  `setup` recipe.
- **Host-layout check (`.ops-check.toml`)**: pre-commit runs `tools/ops-check`, which
  scans tracked files for `$HOME`, the hostname, `$WORK_ROOT`, every registered
  checkout path in `~/.config/tasks/projects.toml`, their parent sync directory, and
  home-relative aliases resolving into them. Add a tracked harness config or hook
  file to `layout_allowed` in `.ops-check.toml` only when the harness reads literal
  host paths at runtime (`claude/settings.json`, `codex/config.toml`,
  `codex/hooks.json`, `codex/work/hooks.json`, `agy/settings.json`). Never widen
  `.ops-check.toml` for documentation or task attachments.

### First-run ordering

`tools/harness-links` applies `[harness.<name>]` only when `home` already exists as a
real directory (`is_dir()` and not a symlink), and refuses to overwrite any existing
real file (`refuse` aborts the entire `--apply` pass with no partial writes).

1. Land every target named in `links.toml` in its owning project's main checkout.
2. From `<hq-checkout>` on `main` (never from a worktree, which would leave live
   harnesses pointing into temporary worktree storage), create the home directory and
   converge links **before** the harness's first interactive run:

   ```sh
   mkdir -p ~/.<harness>
   just link
   just link --apply
   just link-check
   ```

3. If a first run already created a real `settings.json` or `config.toml` in
   `~/.<harness>`, move that file aside, copy any settings worth keeping into the
   tracked `<name>/...` file in `<hq-checkout>`, then rerun `just link --apply`.

## 2. Live-state and session-state hygiene (`hq`)

When a harness writes session picks (`/model`, `/effort`, default thinking level),
installation identifiers (`deviceId`, `trackingId`), UI counters, or workspace trust
in place through its home symlink into a tracked config file, wire the four-part
filter and refresh pipeline so runtime state stays live on disk without polluting the
Git index or disappearing across `git checkout`.

### 1. Route the file through `.gitattributes`

Add the tracked pattern to `.gitattributes` (`just setup` configures
`filter.harness-state.clean` to `.githooks/harness-state-clean %f`; smudge is
identity):

```gitattributes
<name>/settings*.json filter=harness-state
```

### 2. Strip runtime keys in `.githooks/harness-state-clean`

- **JSON configs**: define `<NAME>_JSON_KEYS` and append
  `("<name>/settings*.json", <NAME>_JSON_KEYS)` to `JSON_FILES`. `harness-state-clean`
  exits non-zero if `.gitattributes` sends it a JSON path matching no `JSON_FILES`
  pattern.
- **TOML configs**: add `(table_regex, key)` pairs to `TOML_KEYS` (`re.compile(r"")`
  matches top-level keys before the first header) and full-table patterns to
  `TOML_TABLES`. `harness-state-clean` currently applies `TOML_KEYS` and `TOML_TABLES`
  globally to every `.toml` path (built for `codex/config.toml`); generalize it to
  per-pattern routing like `JSON_FILES` before onboarding a second TOML harness whose
  key names could collide.
- **What to strip vs keep**: strip per-session model/effort keys, host workspace
  trust, transient fetch/UI stamps, and per-installation identifiers (`pi`'s
  `deviceId` and `trackingId`). Keep genuine configuration that should travel through
  Git (enabled model lists, plugin toggles, hook trust hashes, and version-pinned
  changelog markers such as `pi`'s `lastChangelogVersion`).

### 3. Preserve user picks across checkouts in `.githooks/live-picks`

Because the smudge filter is identity, any Git command that rewrites the working-tree
file drops the filtered keys. `.githooks/live-picks` saves live user picks in an
untracked `local/` record and restores them when a unit holds none of its keys:

1. Add the tracked path constant to `OWNED`.
2. Route `RECORDS[<NAME>]` to a dedicated `"local/live-picks-<name>.json"` file.
   Giving each new harness its own machine-owned record isolates parse/refusal errors
   and avoids coupling migrations across harnesses.
3. For JSON configs, define disjoint picker tuples in `JSON_GROUPS[<NAME>]`, one
   tuple per independent UI picker so changing one picker never clobbers another's
   saved state (for example,
   `AGY_GROUPS = (("model",), ("effort", "effortByBase"), ("trustedWorkspaces",))`).
   `live-picks` asserts at startup that a file's `JSON_GROUPS` keys are disjoint and
   a subset of `harness-state-clean`'s `JSON_FILES` keys for that path:
   - Make the sets equal (and add `<NAME>` alongside `(CLAUDE, AGY)` in the equality
     assertion) when every stripped key should be restored across checkouts.
   - Leave `JSON_GROUPS` a strict subset (as `PI` does) when `harness-state-clean`
     also strips installation IDs (`deviceId`, `trackingId`) that must not be saved or
     replayed.
4. Register `<NAME>` in `CLEAN` (`functools.partial(FILTER["clean_json"], keys=...)`
   or `FILTER["clean_toml"]`) and `FIELD` (`"values"` for JSON, `"lines"` for
   top-level TOML key lines). Note that `live-picks`'s TOML path (`TOML_KEYS`,
   `codex_lines()`, and `if name == CODEX:` in `missing()`) is currently specialized
   to `CODEX`: adding a second TOML harness requires generalizing `missing()` (to
   branch on `name not in JSON_GROUPS` rather than `name == CODEX`, which otherwise
   falls through to `JSON_GROUPS[name]` and raises `KeyError`) and routing top-level
   `TOML_KEYS` per file.

`.githooks/post-checkout`, `post-merge`, and `post-rewrite` call
`live-picks hook <hook-name>` under `local/harness-state.lock` (silently skipping
linked worktrees and in-progress rebases). Because absence in the working tree means
a Git rewrite rather than a user reset, resetting a saved pick to the harness default
uses `.githooks/live-picks forget <file>`.

### 4. Clear Git's stat-dirty marker in `.githooks/harness-state-refresh`

Git marks a tracked file `M` in `git status` whenever its byte size differs from the
index entry without running the clean filter first. Add `"<name>/settings*.json"` (or
`"<name>/config*.toml"`) to `PATTERNS` in `.githooks/harness-state-refresh`, which
runs `live-picks capture`, syncs trust and restores dropped picks when `index.lock`
is free, and runs `git add` on files whose filtered diff is empty.

Trigger `~/.local/bin/harness-state-refresh` (the `[required]` link in `links.toml`,
so hook configs never hardcode `<hq-checkout>`) from whichever lifecycle hook the
harness provides:

- **`Stop` command hook** (`claude/settings.json`, `codex/hooks.json`,
  `codex/work/hooks.json`, `agy/hooks.json`): drains stdin, writes nothing to stdout,
  and refreshes at the end of every turn.
- **In-process extension** (`pi/extensions/harness-state.ts`): schedules a refresh
  via `setImmediate` after `model_select` and `thinking_level_select` (so the
  harness's own settings write lands first), plus on `agent_settled` and
  `session_shutdown`.

### 5. Workspace trust preservation

- **Single JSON key** (`agy/settings.json`'s `trustedWorkspaces`): preserve it as its
  own picker tuple `("trustedWorkspaces",)` in `live-picks` `JSON_GROUPS`.
- **Dynamic TOML tables per directory** (`codex/config.toml`'s
  `[projects."<path>"]`): strip `re.compile(r"projects\..+")` in
  `harness-state-clean` `TOML_TABLES` and persist tables in an untracked
  `local/<name>/trust.toml` helper modeled on `.githooks/codex-trust` (acquiring
  `local/harness-state.lock`, enforcing `0600` permissions on `local/` files, merging
  newly trusted paths without pruning absent ones, exposing `forget <path>` for
  explicit removal, and running from the checkout hooks and `harness-state-refresh`).

Add unit coverage for the new config's clean filter, `live-picks`
capture/restore/forget, and `harness-state-refresh` under `.githooks/` (`just test`).

## 3. Capability facts and probes (`hq`)

`facts/capabilities.toml` records what each harness has been shown to do; consumers
and design decisions gate safety-critical behavior (`claim-guard` controller wakes,
live-pick reset semantics, `answer-*` question-routing design) on those records.

### Declaring the harness and reading facts

1. Edit `facts/capabilities.toml` in a worktree and add `<name>` (matching
   `[a-z][a-z0-9-]*`) in alphabetical order to the top-level `harnesses = [...]`
   list. `.githooks/pre-commit` runs the staged `tools/harness-facts check`.
2. Read facts exclusively through `tools/harness-facts` (linked at
   `~/.agents/bin/harness-facts`), never by parsing `facts/capabilities.toml` in a
   consumer:
   - CLI (used by `<ops-checkout>/hooks/claim-guard` via
     `~/.agents/bin/harness-facts list`): `tools/harness-facts check`,
     `tools/harness-facts list [--pretty]`, `tools/harness-facts get <fact> <harness>`.
   - In-process Python module API (for hooks that cannot afford a subprocess): load
     `tools/harness-facts` with `importlib.machinery.SourceFileLoader` (with
     `sys.dont_write_bytecode = True` so `__pycache__` is not written into `tools/`)
     and call `lookup(fact, harness)`.

### Recording `unknown` vs `probed`

- **Implicit or explicit `unknown`**: a harness with no `[facts.<fact>.harness.<name>]`
  table reads as
  `{"fact": "<fact>", "harness": "<name>", "type": "<type>", "status": "unknown"}`
  (plus `"note"` if set on an explicit `unknown` entry); `"value"`, `"version"`,
  `"date"`, and `"evidence"` are omitted rather than `None`, so consumers check
  `entry["status"] == "probed"` before reading `entry["value"]`. An explicit
  `status = "unknown"` table may carry only `status` and an optional `note` explaining
  why it has not been probed; `tools/harness-facts check` rejects `value`, `version`,
  `date`, or `evidence` on an `unknown` entry.
- **`unknown` is not `false`**: `unknown` means unverified, and each consumer chooses
  its own safe fallback. When a probe proves the harness lacks a capability, record
  `status = "probed"` with `value = false` (for `type = "boolean"`) or `value = []`
  (for `type = "set"`).
- **Required fields for `probed`**:

  ```toml
  [facts.controller-wake.harness.<name>]
  status = "probed"
  value = false
  version = "1.2.0"
  date = 2026-10-31
  evidence = "hq-b2515c"
  note = "Isolated terminal run: background child finished after turn end and no new controller turn started within 170s."
  ```

  `date` must be an unquoted TOML local date (`YYYY-MM-DD`); quoted strings and
  timestamps with time-of-day are rejected (`type(date) is datetime.date`). `evidence`
  names the task ID(s) whose notes or attachments preserve the raw probe output.

### Reproducible probes

Place repeatable probe harnesses under `<name>/probes/` (using temporary config
directories and isolated scratch workspaces rather than live homes) and reference
them with `probe = "<name>/probes/<script>"` on `[facts.<fact>]` (`tools/harness-facts
check` verifies every `probe` path exists inside `<hq-checkout>`). Document the
harness's version-upgrade re-probe procedure in `README.md` alongside "Re-probing a
fact" and "Re-probing pi"; an `inconclusive` probe run leaves `facts/capabilities.toml`
unchanged.

## 4. Hooks, profiles, and turn-boundary guards (`lore`, `ops`, `hq`)

### Standard hook roles

- **Session startup (`SessionStart`)**:
  - `<lore-checkout>/hooks/claude-profile`: loads
    `<ops-checkout>/bin/ops-profile` in-process via
    `importlib.machinery.SourceFileLoader`, passes the hook's stdin JSON `payload` to
    `profiles.resolve(cwd or fallback_cwd, env, payload)` and
    `profiles.session_text(res)` (so `home_of()` can inspect `transcript_path`, which
    the CLI `ops-profile session` command does not accept), prints the `profile:`
    line and profile instructions into model context, and appends
    `export AGENT_PROFILE=<profiles>` to `CLAUDE_ENV_FILE` when provided.
  - `<ops-checkout>/hooks/capture-notice` (personal homes only; omit on work homes):
    prints pending mindful capture counts at startup.
  - Optional startup/model hooks where supported:
    `<ops-checkout>/hooks/claude-sessionstart` (Projects/lore drift check, `halt`
    task notice, synced-root `git-index-health` repair) and
    `<ops-checkout>/hooks/claude-provenance` (`TASKS_MODEL` and `TASKS_AGENT` export
    on `SessionStart` and `PostModelSwitch`).
- **Turn boundary (`Stop`, plus `SubagentStop` where worker subagents fire their own
  stop hook as in Codex)**:
  - `<ops-checkout>/hooks/claim-guard --harness <name>`: blocks turn completion once
    when live `doing` claims remain in `tasks --json claims --all-projects` for this
    session and are not covered by probed `controller-wake` /
    `controller-wake-kinds` / `stop-input-in-flight-statuses` facts.
  - `~/.local/bin/harness-state-refresh`: captures live picks and refreshes stat-dirty
    config files.

### Schema, payload, and stdout differences across harnesses

Probe the harness's exact hook contract before wiring shared scripts directly;
existing harnesses diverge on three axes:

| Axis | Claude Code & Codex | Antigravity (`agy`) |
| --- | --- | --- |
| Config structure | `{"hooks": {"<Event>": [{"matcher": "...", "hooks": [{"type": "command", "command": "...", "timeout": ...}]}]}}` in `claude/settings.json` or `codex/hooks.json` | Top-level hook names in `agy/hooks.json`: `{"<hook-name>": {"enabled": true, "Stop": [{"type": "command", "command": "..."}], "PreToolUse": [{"matcher": "...", "hooks": [...]}]}}` (flat handler lists on `SessionStart`, `PreInvocation`, `PostInvocation`, `Stop`; `matcher` + `hooks` groups only on `PreToolUse` and `PostToolUse`) |
| Stdin payload keys | `snake_case`: `session_id`, `transcript_path`, `cwd`, `hook_event_name`, `stop_hook_active`, `agent_id`, `tool_name`, `tool_input`, `background_tasks` | Protojson `camelCase`: `conversationId`, `workspacePaths`, `transcriptPath`, `artifactDirectoryPath`, `modelName`, `toolCall.name`, `toolCall.args`, `terminationReason`, `fullyIdle` |
| Stdout contract | `SessionStart`: plain text injected into context. `Stop`: `{"decision": "block", "reason": "..."}` blocks stop; empty stdout allows stop. | Empty stdout is a no-op (so silent `~/.local/bin/harness-state-refresh` works unchanged on `Stop`), **but** any non-empty stdout must be event-shaped JSON: `SessionStart` / `PreInvocation` require `{"injectSteps": [{"systemMessage": {"systemMessage": "..."}}]}`, and `Stop` blocks turn end with `{"decision": "continue", "reason": "..."}` (any other `decision` allows stopping). |

Two operational consequences follow:

- **Adapter wrappers for JSON-only stdout harnesses**: do not wire plain-text
  `claude-profile` or `capture-notice` directly to a harness whose `SessionStart`
  parses stdout as JSON, and do not emit `"decision": "block"` to a `Stop` hook where
  only `"decision": "continue"` prevents stopping. Wrap or extend the hook script to
  emit the harness's native JSON envelope.
- **Interactive hook trust (Codex)**: Codex hashes every hook command per home. Any
  edit to `codex/hooks.json` or `codex/work/hooks.json` must land with no Codex TUI or
  `codex app-server` running, followed by an interactive `/hooks` review in each home
  under `--no-daemon` (writing updated `[hooks.state]` hashes into tracked
  `codex/config.toml` and untracked `local/codex/config.work.toml`; see
  [Pinned relay runtime](relay-runtime.md)).

### Extending `ops-profile` and `claim-guard` (`<ops-checkout>`)

1. **`<ops-checkout>/bin/ops-profile`**:
   - Add `"<agent-key>": ("<HOME_ENV_VAR>", "~/.<default-home>")` to `HARNESS`. Keep
     `<agent-key>` identical to the agent string returned by `tt.agent_of(env)` in
     `<ops-checkout>/bin/tt` (which `home_of()` uses directly to index `HARNESS`) and
     registered in `AGENTS` in `<obs-checkout>/tt_runs.py`.
   - Add `<agent-key> = "..."` to **every** `[home.<profile-home>]` table in
     `<ops-checkout>/profiles.toml`: `config_problems()` rejects a profile config
     unless every `[home.*]` entry declares paths for every key in `HARNESS`.
   - Check `home_of(env, config, payload)`: it matches `payload["transcript_path"]`
     against configured homes first, then falls back to `tt.agent_of(env)` and the
     harness's home environment variable. If the harness sends `transcriptPath`
     (`camelCase`) or writes transcripts outside its config home (as `agy` writes
     transcripts under `~/.gemini/antigravity-cli/brain/<id>` while reading hooks from
     `~/.gemini/config`), normalize the payload path or register the transcript root
     so work vs personal home detection resolves deterministically.
2. **`<ops-checkout>/hooks/claim-guard`**:
   - Add `<name>` to `HARNESSES` **and** add an unconditional `BOUNDED_WAIT[<name>]`
     instruction string: `wait_branch(harness, wake)` indexes `BOUNDED_WAIT[harness]`
     for every harness whenever `wake` resolves to `None` (including when
     `read_claims()` or `read_facts()` fails or `controller-wake-kinds` /
     `stop-input-in-flight-statuses` is unprobed, even if `controller-wake` is `true`).
   - Map the harness's second-pass loop-breaker field (`stop_hook_active` vs
     `executionNum` / `terminationReason`), worker identifier (`agent_id`), and
     blocking decision schema (`"block"` vs `"continue"`). If the harness fires
     `SubagentStop` or records worker `root_session` claims, generalize the
     `"codex"`-specific checks in `decide()` (`name == "SubagentStop" and harness !=
     "codex"`) and `held()` (`root_session == f"codex:{event['session_id']}"`).
3. **Hook wiring tests in `hq`**:
   - Add or extend assertions in `tools/test_capture_notice_wiring.py`,
     `tools/test_claim_guard_wiring.py`, and `tools/test_relay_wiring.py` so hook
     command strings and ordering cannot drift silently.

## 5. Process ancestry, provenance, and live observation (`relay`, `tasks`, `ops`, `obs`, `hq`)

### `relay` adapter, hook installer, and runtime pin (`<relay-checkout>`, `<obs-checkout>`, `hq`)

1. **Harness allowlists and adapter (`<relay-checkout>`)**:
   - Register `<name>` across `<relay-checkout>`'s harness allowlists: `HARNESSES` in
     `src/commands.js` (checked by `bin/relay.js` for `relay hook`, `relay install`,
     and `relay ask`), `harnesses` in `src/protocol.js` (along with any
     worker/background/scope invariants in `src/protocol.js` and
     `src/bus/transaction.js`), `HARNESSES` in `src/subscribers.js`, and `harnesses`
     in `src/install/atomic.js`.
   - Implement `<relay-checkout>/src/adapters/<name>.js` and register it in `adapters`
     in `<relay-checkout>/src/adapters/index.js`:
     - Event and state machine: `events` (`nativeEvent -> {kind, level}`),
       `stateForEvent`, `reduceState`, `replies` capability flags, `outerTimeouts`,
       `encodeReply`, and optional `workerIdOf` / `backgroundOf`.
     - Process tree resolution: `isHarness(row, ops)`, `resolveSessionPid`, and
       `resolveTerminalPid`.
     - Transport adaptation: `normalizeEvent` / `parsePayload` reads `session_id`,
       `cwd`, `tool_name`, `tool_input`, and `stop_hook_active`; normalize camelCase
       payloads at the adapter boundary, or use a server-plugin bridge when the
       harness exposes plugin events rather than shell hooks (as
       `src/adapters/opencode.js` does for `init`, `session.busy`, `session.idle`,
       and `dispose`).
   - Add `<name>` to `HARNESSES` in `<obs-checkout>/record.py` whenever `relay`
     publishes envelopes for `<name>`, or `obs ingest` will reject them with
     `ValueError("invalid event identity or metadata")`.
2. **Installer planner and question routes (`<relay-checkout>/src/install/`,
   `<relay-checkout>/src/routes/`)**:
   - Add hook event bindings to `table` in `src/install/hooks.js` (`bindingsFor`,
     `planHooks`), add a `src/install/<name>.js` planner, and add a
     `harness === '<name>'` dispatch branch in `bin/relay.js` (whose `else` branch
     otherwise falls through to `planOpenCode`).
   - Probe and record `answer-*` facts in `facts/capabilities.toml` first, then wire
     `<relay-checkout>`'s own installer evidence gate: `relay install` does not read
     `facts/capabilities.toml`, instead validating `--evidence <file>` JSON in
     `src/install/capabilities.js` (`validateCapabilities`) and `src/install/hooks.js`
     (`ROUTE_EVIDENCE` and `routeBindings()`, plus the `'claude-code'` route guards in
     `hooks.js` and `bin/relay.js`).
3. **Pinned runtime rollout in `hq`**:
   - After merging in `<relay-checkout>`, update `relay/package.json` and
     `relay/package-lock.json` in `<hq-checkout>`, run `just relay-install` before
     merging to `main`, and plan/apply hook images per harness under separate approval
     following [Pinned relay runtime](relay-runtime.md) (updating `HOOK_VERSIONS` and
     expected event tuples in `tools/test_relay_wiring.py`).

### `tasks` ancestry, native session provenance, and environment (`<tasks-checkout>`, `<obs-checkout>`)

1. **Process ancestry (`<tasks-checkout>/src/relay/ancestry.rs`)**:
   - Projects with `[identity] relay = true` bind task claims (`tasks start`) to the
     enclosing harness process. Add `("<comm>", "<name>")` to `HARNESS_COMMS` in
     `src/relay/ancestry.rs`.
   - If the harness runs under versioned binary names, Node/Bun entrypoints, or
     long-lived daemon/PTY-host subcommands (analogous to Claude Code's `daemon` /
     `bg-pty-host` or Codex's `app-server`), extend `harness_of()` and
     `boundary_scope()` so concurrent sessions under a shared daemon do not collapse
     onto one PID, and add representative `/proc` trees to
     `<tasks-checkout>/tests/fixtures/relay/ancestry.json`.
2. **Native session provenance (`<tasks-checkout>/src/provenance.rs`,
   `<obs-checkout>/join.py`)**:
   - Lifecycle transitions and `tasks note --stamp` record
     `provenance: {"harness_session": "<name>:<id>", "harness_session_source": "<ENV_VAR>"}`
     when the harness exports a native session ID environment variable to child
     shells (`CLAUDE_CODE_SESSION_ID`, `CODEX_THREAD_ID`).
   - When a new harness exports a verified session variable, add it to `validate`,
     `validate_session_key`, `resolve_from`, and (if subagent workers carry a
     separate root variable) `resolve_root_from` in `src/provenance.rs` — and in
     lockstep add `<name>` to `HARNESSES` and `<ENV_VAR>` to `SOURCES` in
     `<obs-checkout>/join.py`, or `obs index` will raise
     `ValueError("unknown provenance source")` as soon as a stamped task note lands.
   - `TASKS_SESSION` and `TASKS_SESSION_PID` are claim-ownership overrides only and
     are never recorded as lifecycle provenance. When a harness exports no native
     session ID (`agy`, `pi` without an extension), `--stamp` omits `provenance`;
     callers and retention notes must report session attribution as absent rather
     than inventing a `session:<name>:...` string.
3. **Child-shell environment (`TASKS_FORMAT`, `TASKS_AGENT`, `TASKS_MODEL`)**:
   - Where the harness's settings file supports child environment injection (such as
     `env` in `claude/settings.json`), set `TASKS_FORMAT=json` so CLI mutations emit
     structured output.
   - Export `TASKS_AGENT=<name>/<model>` and `TASKS_MODEL=<model>` only from a hook
     or runtime source that verifies the live model (`claude-provenance`); otherwise
     set `TASKS_AGENT=<name>` (or pass `--agent <name>`) without guessing a model
     from static config defaults.

### Test-run provenance (`<ops-checkout>`, `<obs-checkout>`)

Extend `agent_of(env)` in `<ops-checkout>/bin/tt` to recognize the harness's
environment marker and session ID so test runs appended to
`~/.local/share/ops/runs.jsonl` carry its agent key and session ID (downstream
repositories pick up vendored `ops` updates through their normal adoption pass). Keep
that agent key registered in `HARNESS` in `<ops-checkout>/bin/ops-profile` and in
`AGENTS` (`{'claude': 'claude-code', 'codex': 'codex', ...}`) in
`<obs-checkout>/tt_runs.py` (with the target canonical slug in
`<obs-checkout>/join.py` `HARNESSES`), or `tt_runs` leaves `harness` and
`session_key` as `None` (`unknown_agent_runs`).

## 6. Session discovery, archive, and transcript readers (`hq`, `obs`)

### `hq sessions` listing and `-i` resume (`hq`)

Read `docs/notes/2026-10-15-session-discovery-contract.md` first: `hq sessions` keeps
no index of its own, reads each harness's native metadata directly, and raises
`SourceError` when a present home's metadata is missing, unreadable, or at an
unexpected schema version rather than silently returning an empty list.

1. **`tools/hq_cli/sessions.py`**:
   - Add `Home(name, harness, kind, path)` entries to `homes(user_home)`.
   - Implement `read_<name>(home)` returning `list[Session]` (or
     `(list[Session], Skipped)` if the metadata log carries skippable lines like
     `read_claude(home)`, or taking `(home, archived)` like
     `read_codex(home, archived)`), populating `home`, `id`, `cwd`, `recency_ms`,
     `label`, `transcript`, plus `excluded="non-interactive"` or `"transcript gone"`
     and `archived=True` where applicable. Split JSONL files on `"\n"` rather than
     `str.splitlines()`, which breaks on `U+2028` inside JSON strings.
2. **`tools/hq_cli/cli.py` and `tools/hq_cli/color.py`**:
   - Define a `<NAME> = Colour(oklch(L, C, H), <xterm-256-index>)` constant in
     `tools/hq_cli/color.py` whose 24-bit RGB and xterm-256 stand-in both satisfy
     `contrast(..., DARK) >= 3` and `contrast(..., LIGHT) >= 3`.
   - In `tools/hq_cli/cli.py`: add `<name>` to `--harness` `choices` in `parser()`,
     dispatch `read_<name>` and footer `excluded`/`skipped` counts in `collect()`,
     and register `"<name>": color.<NAME>` in `harness_hue` in `format_rows()`
     (widening `pad(s.home.harness, 6)` if `len(<name>) > 6`).
3. **`tools/hq_cli/launch.py` and `tools/hq.toml`**:
   - Add the resume argv shape in `argv(session, flags)` and, if the harness has a
     work home selected by environment variable, register `<name>: "<HOME_ENV_VAR>"`
     in `HOME_VARIABLES` (`environment()` sets it for `kind == "work"` and unsets
     all `HOME_VARIABLES` for `kind == "personal"`).
   - Add `[homes.<home-name>]` `flags = [...]` to `tools/hq.toml`.

### Transcript capture and pruning (`tools/session_archive/`)

1. Add `Source(name, kind, home, root, pruned=False)` entries to `sources(home)` in
   `tools/session_archive/config.py`. `capture` (`tools/session_archive/capture.py`)
   is `kind`-agnostic: it walks all regular files under `Source.root`, skips files
   mutated mid-copy (`"busy"` via inode/size/mtime recheck), and preserves non-append
   rewrites under `versions/` (`"diverged"`). Scope `Source.root` to the transcript
   subdirectory (`projects`, `sessions`) rather than `home` itself so mutable
   home-level SQLite/WAL databases stay outside `Source.root`.
2. `check_sources()` runs before every `session-archive` command (`capture`, `prune`,
   `status`, `promote`, `probe-codex`) and aborts the entire archive run (`EX_HOST`)
   across all harnesses if any declared `Source.root` is a symlink or missing. Once a
   `Source` lands in `tools/session_archive/config.py`, run `mkdir -p <Source.root>`
   on **every** archive-configured host before the daily capture timer runs.
3. `Source.kind` and open-file checks (`inputs.open_inodes` / `uninspectable_ok`)
   apply only to `prune` (and `probe-codex`):
   - Leave `pruned=False` until `<obs-checkout>` indexes the store at contract-2
     readiness (`device`, `inode`, and SHA-256 digest equality across live bytes,
     archive read-back, and indexed spans; see
     `docs/specs/2026-09-30-session-archive-design.md`), the binary `claude`-else-`codex`
     branches in `tools/session_archive/inputs.py`, `decide.py`, and `prune.py` are
     extended to dispatch `<kind>` explicitly (unit discovery, transcript
     classification, `obs` harness mapping, and deletion), and live pruning is
     separately approved.
   - Never add an agent harness's `comm` to `uninspectable_ok` in
     `~/.config/session-archive/config.toml`: `uninspectable_ok` only exempts
     unrelated non-dumpable same-UID processes whose `/proc/<pid>/fd` cannot be
     inspected, and adding a harness there would suppress `InspectionFailed` during
     `prune` and risk deleting open session files. Archive tests must run against
     temporary directories, never live homes.

### `session-logs`, `session-episodes`, and `obs` adapters (`hq`, `<obs-checkout>`)

1. **`agents/skills/session-logs/SKILL.md`**: document the harness's live store path,
   session unit (JSONL file, SQLite database, or per-conversation directory such as
   `~/.gemini/antigravity-cli/brain/<id>/.system_generated/logs/transcript.jsonl` +
   `transcript_full.jsonl`), record types, subagent storage, and exact markers
   distinguishing human prompts from harness-injected context blocks.
2. **`agents/bin/session-episodes` and `<obs-checkout>`**: `session-episodes`
   currently wires only Claude Code and Codex; extending it to a third store requires
   updating `INTERACTIVE`, `_roots()` / `scan_stores()`, and the binary
   `CLAUDE_HARNESS`-else-Codex branches in `turn_after()` and `_session_for()`,
   keeping interactive entrypoint filters and human-vs-injected prompt stripping
   synchronized with `<obs-checkout>/<name>_adapter.py`.
3. **`<obs-checkout>` adapter and harness registries**:
   - Implement `<obs-checkout>/<name>_adapter.py` extracting session metadata, turns,
     token usage, tool and shell calls, native vs inferred skill reads, hook runs,
     turn-end reasons, and truncation markers.
   - Register the adapter in `<obs-checkout>/stores.py` (`ADAPTERS`, `SKILL_COVERAGE`,
     `store_roots()` with an `OBS_<NAME>_...` environment override so tests never
     read live homes, `_paths()`, `_peek_cwd()`, and `_initial_state()` for subagent
     attribution) and wire `<name>` across `<obs-checkout>`'s remaining harness
     registries:
     - `index.py`: `normalize_usage(harness, usage)`.
     - `obs.py`: `--harness` `choices` on `index` and `report`, **plus** `main()`'s
       default `obs index` harness list (`harnesses = [args.harness] if args.harness
       else [...]`), keeping it equal to `stores.ADAPTERS` so unfiltered `obs index`
       runs index `<name>` and mark `complete=True` (`last_complete_run_ms`).
     - `session_logs*.py`: `session_logs_place.roots()` iterates directly over
       `stores.store_roots()`, so adding a store root in `stores.py` requires
       extending the `session_logs_{place,read,lines,sessions,turns,show}.py`
       placement, format-detection, and turn-span pipeline alongside
       `session_logs.py` `--harness` `choices` (or explicitly excluding `<name>` in
       `session_logs_place.roots()` until `session_logs` supports it).
     - `dashboard.py`: `HARNESSES`, per-harness `("questions_with_rec",
       "rec_accepted")` entries in `MEASURES` (declared outside the `HARNESSES` loop),
       and `SECTIONS["skills"]["evidence"]`.
     - `catalog.py` (`ADAPTERS`), `hook_report.py` (default `obs report hooks`
       coverage harness list), `tt_report.py` (`TOOLS` shell-tool names for `obs
       report tests`), `index_state.py` (`_identity(row)` when contract-2 pruning
       checks filename or thread identity), and (where applicable) `baseline.py`
       (`HARNESSES`) and `sweep.py`, plus `record.py`, `join.py`, and `tt_runs.py`
       from Section 5.
   - Run the adapter against every record in the real local store (`obs index`) and
     verify `tt_runs` session-key joins before enabling archive pruning.

## Rollout order and multi-host convergence

1. **Verify in worktrees first**: land and test consumer changes (`lore`, `ops`,
   `relay`, `tasks`, `obs`) and `<hq-checkout>` changes in task worktrees (`just test`,
   `python3 tools/ops-check`, `python3 tools/ops-docs check`, `tasks check` in
   `<hq-checkout>`). Every target path referenced by `links.toml` must exist on its
   owner's main branch before links are applied.
2. **Respect live-surface approval gates**: edits to `links.toml`, deployed hooks,
   pinned runtimes (`pi/`, `relay/`), and `session-archive` pruning take effect across
   live sessions on this host and every synced host as soon as they merge or apply.
   Obtain explicit rollout approval where the checkout profile or runbook requires it.
3. **Bootstrap each host before first launch**:
   - Install any newly pinned runtime (`just <name>-install`, `just relay-install`)
     from the reviewed tree before merging the pin into `main`, then on each peer host
     as soon as the merge syncs.
   - If `tools/session_archive/config.py` gained a new `Source`, run
     `mkdir -p <Source.root>` on every archive-configured host before the daily
     capture timer runs so `check_sources()` does not abort archive runs.
   - On each host where the harness will be used, run `mkdir -p <home>` and
     `just link --apply` from `<hq-checkout>` on `main` before starting the harness
     interactively, then confirm convergence with `just link-check`.
4. **Post-apply live checks**:
   - Complete any per-home interactive hook trust review (such as Codex `/hooks`).
   - Switch model/effort once in the harness, finish a turn, confirm `git -C
     <hq-checkout> status` shows no dirty marker on the tracked config
     (`harness-state-refresh`), and confirm `local/live-picks-<name>.json` captured
     the pick.

## Onboarding checklist

| Layer | Repository | Key files | Verification |
| --- | --- | --- | --- |
| Home routing & instructions | `hq`, `lore` | `links.toml`, `justfile`, `.ops-check.toml`, `<lore-checkout>/vendor/superpowers/skills/using-superpowers/` | `python3 tools/ops-check`, `just link`, `just link-check` (on `main` after apply) |
| Live-state hygiene | `hq` | `.gitattributes`, `.githooks/harness-state-clean`, `.githooks/live-picks`, `.githooks/harness-state-refresh`, optional trust helper | `just test` (`.githooks` suite), clean `git status` after turn end |
| Capability facts & probes | `hq` | `facts/capabilities.toml`, `<name>/probes/`, `README.md` | `tools/harness-facts check`, `tools/harness-facts list --pretty` |
| Hooks, profiles & claim guard | `lore`, `ops`, `hq` | `<name>/hooks.json` or `settings.json`, `<ops-checkout>/bin/ops-profile`, `<ops-checkout>/profiles.toml`, `<ops-checkout>/hooks/claim-guard`, `tools/test_*_wiring.py` | `<ops-checkout>` tests, `just test` in `<hq-checkout>` |
| Ancestry, provenance & `relay` | `relay`, `tasks`, `ops`, `obs`, `hq` | `<relay-checkout>/src/{commands,protocol,subscribers}.js`, `<relay-checkout>/src/adapters/`, `<relay-checkout>/src/install/`, `<relay-checkout>/bin/relay.js`, `<tasks-checkout>/src/relay/ancestry.rs`, `<tasks-checkout>/src/provenance.rs`, `<ops-checkout>/bin/tt`, `<obs-checkout>/{record,join,tt_runs}.py`, `relay/package*.json` | `<relay-checkout>`, `<tasks-checkout>`, `<ops-checkout>`, and `<obs-checkout>` test suites; `just test` |
| Sessions, archive & `obs` | `hq`, `obs` | `tools/hq_cli/`, `tools/hq.toml`, `tools/session_archive/`, `agents/skills/session-logs/SKILL.md`, `agents/bin/session-episodes`, `<obs-checkout>/<name>_adapter.py`, `<obs-checkout>/{stores,index,obs,catalog,dashboard,hook_report,tt_report,index_state,baseline,sweep}.py`, `<obs-checkout>/session_logs*.py` | `just test`, `hq sessions`, `<obs-checkout>` test suite + live `obs index` |
