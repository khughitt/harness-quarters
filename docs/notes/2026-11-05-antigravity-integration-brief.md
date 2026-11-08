# Antigravity worker defaults and task-id colors

## Problem

Antigravity should keep unbudgeted runners small and make task references easy to
scan. hq-32317f concerns worker defaults; hq-db39da asks whether reply identifiers
can use project colors. This brief prepares evidence gathering, not activation.

## Current behaviour and evidence

- Installed `agy --version` reports **1.5.1** on 2026-11-05 and **1.5.3** on
  2026-11-08 (ELF BuildID `50b5b6c0ca95a2a401f0c806222ecaa6`). `command -v agy`
  resolves to `~/.local/bin/agy`, outside hq's declared launchers.
- Commit a2ebc48c introduced five defaults of `4` for Claude Code, Codex and pi:
  `PYTEST_XDIST_AUTO_NUM_WORKERS`, `CARGO_BUILD_JOBS`, `RUST_TEST_THREADS`,
  `NEXTEST_TEST_THREADS`, `GOMAXPROCS`. `tools/test_worker_defaults.py` covers
  those three harnesses only. `links.toml` declares agy settings and customization
  links (`harnesses/agy/settings.json`, `harnesses/agy/hooks.json`,
  `harnesses/agy/skills.json`), with no agy launcher; `harnesses/agy/settings.json`
  declares no worker environment. Section 7 below records the completed `1.5.3`
  investigation for hq-a29f17.
- `harnesses/agy/settings.json` configures familiar's statusline (b864334a). That
  configuration does not prove inline reply styling or statusline truecolor rendering.
- hq-db39da's filing session contains the user's question about shared task colors
  and a supplied assessment claiming ANSI stripping. The filing agent explicitly
  left the rendering claims unverified. Binary symbol names do not prove a call path.
- prism-fd46ae already owns renderer implementation across harnesses. The attached
  `reply-color-findings.md` on lore-587c8a covers four other harnesses, not agy;
  it distinguishes source findings from unrun probes. No overlapping open agy
  rendering or worker-default research task was found in the related task searches.

## Constraints

Keep canonical task ids bare; preserve useful bold verdicts and spacing. Read
project colors from public tasks JSON. Keep display styling out of stored model
context. Worker defaults must leave host library-thread settings and budget-grant
markers alone, and allow host-budget to replace defaults with its grant.

Preserve live model picks and the existing local agy settings edit. Home routing
belongs in `links.toml`; applying home links is a separate authorized operation
from main. Coordinate hook changes with hq-7bed89 and hq-c59809 without making
those unrelated questions dependencies. Renderer implementation remains with prism.

## Alternatives

1. Prefer a documented native agy environment setting and a supported display
   extension, if version-bound evidence establishes them.
2. For worker defaults, consider an hq launcher only if native configuration
   cannot deliver them. For color, report a supported statusline surface separately
   if inline styling is unavailable; it does not satisfy inline coloring.
3. Retain current configuration and readable structural formatting while evidence
   is incomplete. This is the current lean until the two bounded investigations
   identify supported routes. No renderer fork, binary patch or parallel color
   implementation is justified by the recorded asks.

## Unanswered questions

- **Resolved (`hq-a29f17`, `agy` `1.5.3`)**: Which supported setting or launch route can
  supply the five defaults to tool shells without interfering with explicit values or
  budget grants?
  Answer: `agy` `1.5.3` has no native settings or hook environment surface; the supported
  route is an `hq`-owned launcher wrapper at `harnesses/agy/bin/agy` (analogous to
  `harnesses/pi/bin/pi`), linked from `~/.local/bin/agy` in `links.toml` and `exec`ing
  the real binary at `${AGY_BIN:-$HOME/.local/share/agy/agy}` (see Worker-default route
  findings below).
- Can the installed renderer color bare ids inline through a supported extension?
  If not, what can the statusline actually render? Answer: documentation/source
  tracing and, only where possible, a headless fixture with canned text.

Research excludes paid model calls, live desktop use and home changes. If a claim
cannot be settled locally without these, record it as unknown and describe the
smallest additional check and its authorization needs; do not build a new runner.

## Proposed decomposition

- hq-49ed70 is the shared coordination and closeout goal. Both existing ideas and
  the two research tasks are its children; their original bodies and sources stay intact.
- hq-a29f17 (completed) determined the supported worker-default route (`harnesses/agy/bin/agy`
  wrapper + `links.toml` entry + `tools/test_worker_defaults.py` coverage) and woke hq-32317f.
- hq-7826fd determines supported color surfaces and wakes hq-db39da; resulting
  renderer implementation remains prism-fd46ae.

Each original idea waits only on its own research result. Both investigations are
P2, small, mid complexity and direct process. Research completion updates this
brief and adds a finding with `--no-reviewed` to its waiting idea before integration.
No implementation or separate design task is filed yet.

## Worker-default route findings (hq-a29f17)

Inspected on installed `agy` `1.5.3` (`~/.local/bin/agy`, ELF BuildID
`50b5b6c0ca95a2a401f0c806222ecaa6`) and the bundled `agy-customizations` /
`antigravity_guide` skill docs:

1. **No native settings environment surface in `agy` `1.5.3`**:
   - Reflection metadata for `google3/third_party/jetski/cli/types/types.CliSetting`
     (the struct backing `~/.gemini/antigravity-cli/settings.json` and `--settings`)
     defines 37 exported JSON keys (`colorScheme`, `altScreenMode`, `trustedWorkspaces`,
     `toolPermission`, `permissions`, `historySize`, `model`, `customModelsConfig`,
     `contextWindow`, `notifications`, `editor`, `editorMode`, `vimInsertFirst`,
     `clearScrollbackOnResize`, `allowNonWorkspaceAccess`, `useTerminalCursor`,
     `verbosity`, `artifactReviewPolicy`, `runningLightSpeed`, `statusLine`, `title`,
     `showTips`, `enableTerminalSandbox`, `sandboxProxy`, `gcp`, `showFeedbackSurvey`,
     `useG1Credits`, `hideActiveItems`, `agentMode`, `copyOnSelect`,
     `disableSlashCommands`, `modelProvider`, `pickerGrouping`, `queuedMessages`,
     `seasonalThemesOff`, `seasonalThemesOptIn`, and embedded `voice`), plus
     `unknownFields` (`json:"-"`). None configures child-process environment variables.
   - Although the shared protobuf schemas (`jetbox_state_pb.UserSettings`,
     `exa.project_pb.ProjectSettings`, `exa.cortex_pb.RunCommandToolConfig`) include
     `shell_setup_script`, the CLI settings store implementation
     `google3/third_party/jetski/language_server/settings/settings.(*CliSettingsStore).GetRunCommandSetupScriptForProject`
     (`0x9bc3f40`) is a 5-byte stub (`xor %eax,%eax; xor %ebx,%ebx; ret`) that
     unconditionally returns `""`.

2. **No native hook environment-injection channel**:
   - Per `agy-customizations/docs/hooks.md`, `SessionStart` returns only
     `{"injectSteps": [...]}` (conversation trajectory messages; no `CLAUDE_ENV_FILE`
     equivalent).
   - `PreToolUse` returns `decision`, `reason`, `permissionOverrides`, and `overwrite`
     (a shallow merge into the tool call's `args`). On `run_command`, `args` accepts
     `CommandLine`, `WaitMsBeforeAsync`, `IsDaemon`, and `toolSummary` (no `env` map),
     and mutating `CommandLine` via `overwrite` injects a hook-rewrite notice into
     every tool result.

3. **Tool-shell environment inheritance (`NewLocalTerminal`)**:
   - Disassembly of `google3/third_party/jetski/terminal/terminal.NewLocalTerminal`
     (`0x7e71b40..0x7e72480`) and `(*RunCommandHandler).Handle` (`0x91b9360..0x91bbba0`)
     shows that `run_command` builds the child shell environment from `syscall.Environ()`
     (`0x7e71c40`) on the `agy` process, merges `GetAgentAPIShellInjection` (`0x838cc80`),
     and spawns the shell inside `exebox`.
   - Direct comparison of `/proc/<agy-pid>/environ` with a live `run_command` child shell
     in `agy` `1.5.3` confirms that `0` environment keys are stripped from `agy`'s
     process environment: only `PAGER`, `PATH` (prepended with
     `~/.gemini/antigravity-cli/bin`), `TERM`, and `_` are modified, while
     `ANTIGRAVITY_*` and `GIT_EDITOR` / `GIT_PAGER` / `HGEDITOR` / `JJ_EDITOR` /
     `JJ_PAGER` are added. Any `WORKER_VARS` exported before `exec`ing the `agy` binary
     therefore reach every `run_command` shell unchanged.

4. **Supported route (`harnesses/agy/bin/agy` launcher wrapper) and updater safety**:
   - Place an `hq`-owned bash launcher at `harnesses/agy/bin/agy` (declared in
     `links.toml` under `[required]` as `"~/.local/bin/agy" = "harnesses/agy/bin/agy"`,
     matching `"~/.local/bin/pi" = "harnesses/pi/bin/pi"`) that exports defaults only
     when unset or empty and `exec`s the real ELF binary at
     `bin="${AGY_BIN:-$HOME/.local/share/agy/agy}"`:
     ```bash
     for var in PYTEST_XDIST_AUTO_NUM_WORKERS CARGO_BUILD_JOBS RUST_TEST_THREADS NEXTEST_TEST_THREADS GOMAXPROCS; do
         export "$var=${!var:-4}"
     done
     exec "$bin" "$@"
     ```
   - **Precedence**:
     - Unset or empty in the caller -> exported as `4` for all five `WORKER_VARS`
       (`PYTEST_XDIST_AUTO_NUM_WORKERS`, `CARGO_BUILD_JOBS`, `RUST_TEST_THREADS`,
       `NEXTEST_TEST_THREADS`, `GOMAXPROCS`).
     - Explicit caller override (`PYTEST_XDIST_AUTO_NUM_WORKERS=2 agy ...`) ->
       preserved by `${!var:-4}`.
     - `host-budget run` inside a tool shell -> overwrites the inherited `4` in its
       budgeted child environment with `HOST_BUDGET_GRANT_WORKERS` /
       `HOST_BUDGET_GRANT_CARGO_BUILD_JOBS` and sets `LIBRARY_VARS` to `1`.
     - `LIBRARY_VARS` (`OPENBLAS_NUM_THREADS`, `MKL_NUM_THREADS`, `OMP_NUM_THREADS`,
       `RAYON_NUM_THREADS`, `POLARS_MAX_THREADS`, `NUMEXPR_MAX_THREADS`,
       `TOKIO_WORKER_THREADS`) and `GRANT_VARS` (`HOST_BUDGET_*`) -> untouched by
       `harnesses/agy/bin/agy`.
     - Note: exporting `GOMAXPROCS=4` before `exec`ing `agy` also caps the `agy` Go
       process itself to 4 OS threads unless the caller sets `GOMAXPROCS`.
   - **Interaction with `agy update`, background auto-update, and `agentapi`**:
     - Disassembly of `updater.triggerUpdateShared` (`0xa4a7ed6`),
       `updater.runUpdateShared` (`0xa4a98e5`), and `GetAgentAPIShellInjection`
       (`0x838ce0f`) shows that all three resolve the binary path via Go's
       `os.Executable()` (`0x6e2d920`, which reads `/proc/self/exe` on Linux) without
       using `argv[0]`.
     - Because `harnesses/agy/bin/agy` is a `#!/usr/bin/env bash` script that `exec`s
       `~/.local/share/agy/agy`, `/proc/self/exe` points to `~/.local/share/agy/agy`.
       Both foreground (`agy update`) and background auto-updates swap
       `~/.local/share/agy/agy.new` -> `~/.local/share/agy/agy` in place and leave the
       `~/.local/bin/agy` symlink intact, and `GetAgentAPIShellInjection` writes
       `exec "$HOME/.local/share/agy/agy" agentapi "$@"` to
       `~/.gemini/antigravity-cli/bin/agentapi`.
     - One-time host activation moves the existing ELF binary from `~/.local/bin/agy` to
       `~/.local/share/agy/agy` before running `just link --apply` from `main` (since
       `tools/harness-links` refuses to overwrite a regular file at `~/.local/bin/agy`).

5. **Focused test specification for `hq-32317f` (`tools/test_worker_defaults.py`)**:
   - Add `test_agy_launcher_defaults_and_preserves_caller_env(tmp_path)` alongside
     `test_pi_launcher_defaults_and_preserves_caller_env`:
     - Create an executable stub at `tmp_path / "agy"` that prints `sys.argv[1:]` and
       `dict(os.environ)` as JSON.
     - Run `ROOT / "harnesses/agy/bin/agy"` with `AGY_BIN=str(stub)` and a clean
       environment (all `WORKER_VARS`, `LIBRARY_VARS`, and `GRANT_VARS` stripped):
       assert all five `WORKER_VARS` equal `"4"`, all `LIBRARY_VARS` and `GRANT_VARS`
       are absent, and arguments are forwarded verbatim.
     - Re-run with `PYTEST_XDIST_AUTO_NUM_WORKERS="2"` and `GOMAXPROCS="6"` in `env`:
       assert those two keep `"2"` and `"6"` while the remaining three `WORKER_VARS`
       equal `"4"`.
     - Run with `AGY_BIN=str(tmp_path / "missing")`: assert exit code `127` and a diagnostic on `stderr`.
