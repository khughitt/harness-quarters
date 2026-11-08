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
- `harnesses/agy/settings.json` configures familiar's statusline (b864334a). Section 8
  below records the `1.5.3` rendering call-path trace for hq-7826fd across inline
  assistant replies, hooks/plugins, statusline output, and tool output.
- hq-db39da's filing session contains the user's question about shared task colors
  and a supplied assessment claiming ANSI stripping. The filing agent explicitly
  left the rendering claims unverified. Binary symbol names do not prove a call path;
  Section 8 traces the actual `1.5.3` call graph from `render.(*itemRenderer).render`
  and `model.StatusLineModel.Render`.
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
- **Resolved (`hq-7826fd`, `agy` `1.5.3`)**: Can the installed renderer color bare ids
  inline through a supported extension? If not, what can the statusline actually render?
  Answer: `agy` `1.5.3` has no supported inline extension or theme hook that can color
  bare `<prefix>-<6 hex>` task IDs per project prefix in assistant replies without
  polluting stored model context (plugins are declarative bundles; Goldmark+Glamour
  strips HTML via `bluemonday.NewPolicy`; `PostInvocation` `injectSteps` can only append
  a separate step, not rewrite the planner response step). Separate truecolor ANSI SGR
  (`\x1b[38;2;R;G;Bm`) is supported on the custom `statusLine.command` surface
  (`model.StatusLineModel.RenderCustom`), which passes stdout lines directly into the
  TUI view without Glamour rendering or ANSI stripping and stays out of stored model
  context (see Task-id color surface findings below).

Research excludes paid model calls, live desktop use and home changes. If a claim
cannot be settled locally without these, record it as unknown and describe the
smallest additional check and its authorization needs; do not build a new runner.

## Proposed decomposition

- hq-49ed70 is the shared coordination and closeout goal. Both existing ideas and
  the two research tasks are its children; their original bodies and sources stay intact.
- hq-a29f17 (completed) determined the supported worker-default route (`harnesses/agy/bin/agy`
  wrapper + `links.toml` entry + `tools/test_worker_defaults.py` coverage) and woke hq-32317f.
- hq-7826fd (completed) determined the `agy` `1.5.3` color surfaces across inline
  assistant replies, hooks/plugins, statusline output, and tool output, and woke
  hq-db39da; resulting renderer implementation remains prism-fd46ae.

Each original idea waits only on its own research result. Both investigations are
P2, small, mid complexity and direct process. Research completion updates this
brief and adds a finding with `--no-reviewed` to its waiting idea before integration.
No implementation or separate design task is filed yet.

Dispositions after the 2026-11-08 scope pass:

- hq-32317f is scoped as the implementation task: the `harnesses/agy/bin/agy`
  launcher, its `links.toml` entry and the four focused tests in Section 7, with the
  one-time binary move and `just link --apply` from main as a host step the user
  approves at the time.
- hq-db39da is proposed for drop: Section 8 answers its assessment. Inline coloring
  is unsupported in `agy` `1.5.3`; statusline coloring is recorded on prism-fd46ae,
  which owns renderer work.

## Worker-default route findings (hq-a29f17)

Inspected on installed `agy` `1.5.3` (`~/.local/bin/agy`, ELF BuildID
`50b5b6c0ca95a2a401f0c806222ecaa6`) and the bundled `agy-customizations` /
`antigravity_guide` skill docs:

1. **No native settings environment surface in `agy` `1.5.3` (Observed)**:
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

2. **No native hook environment-injection channel (Observed)**:
   - Per `agy-customizations/docs/hooks.md`, `SessionStart` returns only
     `{"injectSteps": [...]}` (conversation trajectory messages; no `CLAUDE_ENV_FILE`
     equivalent).
   - `PreToolUse` returns `decision`, `reason`, `permissionOverrides`, and `overwrite`
     (a shallow merge into the tool call's `args`). On `run_command`, `args` accepts
     `CommandLine`, `WaitMsBeforeAsync`, `IsDaemon`, and `toolSummary` (no `env` map),
     and mutating `CommandLine` via `overwrite` injects a hook-rewrite notice into
     every tool result.

3. **Tool-shell environment inheritance (`NewLocalTerminal`) (Observed)**:
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
     `JJ_PAGER` are added. Any `DEFAULTS` keys exported before `exec`ing the `agy` binary
     therefore reach every `run_command` shell unchanged.

4. **Supported route (`harnesses/agy/bin/agy` launcher wrapper), precedence, and updater safety (Observed in isolated prototype; Inferred for live home-linked activation)**:
   - Place an `hq`-owned bash launcher at `harnesses/agy/bin/agy` (declared in
     `links.toml` under `[required]` as `"~/.local/bin/agy" = "harnesses/agy/bin/agy"`,
     matching `"~/.local/bin/pi" = "harnesses/pi/bin/pi"`) that checks the target binary,
     exports `DEFAULTS` only when unset or empty, and `exec`s the real ELF binary at
     `bin="${AGY_BIN:-$HOME/.local/share/agy/agy}"`:
     ```bash
     #!/usr/bin/env bash
     set -euo pipefail
     bin="${AGY_BIN:-$HOME/.local/share/agy/agy}"
     if [[ ! -x $bin ]]; then
         echo "agy: binary not found at $bin; move the installed agy binary there or set AGY_BIN" >&2
         exit 127
     fi
     for var in PYTEST_XDIST_AUTO_NUM_WORKERS CARGO_BUILD_JOBS RUST_TEST_THREADS NEXTEST_TEST_THREADS GOMAXPROCS; do
         export "$var=${!var:-4}"
     done
     exec "$bin" "$@"
     ```
   - **Precedence (Observed on isolated wrapper prototype and `host-budget` source)**:
     - Unset or empty in the caller -> exported as `4` for all five `DEFAULTS` keys in
       `tools/test_worker_defaults.py` (`PYTEST_XDIST_AUTO_NUM_WORKERS`,
       `CARGO_BUILD_JOBS`, `RUST_TEST_THREADS`, `NEXTEST_TEST_THREADS`, `GOMAXPROCS`).
     - Explicit caller override (`CARGO_BUILD_JOBS=12 agy ...`) -> preserved by
       `${!var:-4}`.
     - `host-budget run` inside a tool shell -> `host-budget`'s `job_environment(n, threads)`
       (`os.execvpe(..., {**os.environ, **job_environment(...)})`) overwrites the
       inherited `4` on all five `DEFAULTS` keys with `str(n)` (or `"1"` under
       `--threads`), sets `GRANT_VARS` (`OPS_BUDGET=str(n)`, `OPS_WORKERS=str(n)` or
       `"1"`), and sets all seven `LIBRARY_VARS` (`OMP_NUM_THREADS`,
       `OPENBLAS_NUM_THREADS`, `MKL_NUM_THREADS`, `NUMEXPR_NUM_THREADS`,
       `NUMBA_NUM_THREADS`, `RAYON_NUM_THREADS`, `POLARS_MAX_THREADS`) to `"1"` (or
       `str(n)` under `--threads`).
     - `LIBRARY_VARS` (`OMP_NUM_THREADS`, `OPENBLAS_NUM_THREADS`, `MKL_NUM_THREADS`,
       `NUMEXPR_NUM_THREADS`, `NUMBA_NUM_THREADS`, `RAYON_NUM_THREADS`,
       `POLARS_MAX_THREADS`) and `GRANT_VARS` (`OPS_BUDGET`, `OPS_WORKERS`) -> untouched
       by `harnesses/agy/bin/agy`, matching `assert_leaves_alone(env)` in
       `tools/test_worker_defaults.py`.
     - Note (Inferred): exporting `GOMAXPROCS=4` before `exec`ing `agy` also caps the
       `agy` Go process itself to 4 OS threads unless the caller sets `GOMAXPROCS`.
   - **Interaction with `agy update`, background auto-update, and `agentapi` (Observed in binary disassembly; Inferred for live updater runs)**:
     - Disassembly of `updater.triggerUpdateShared` (`0xa4a7ed6`),
       `updater.runUpdateShared` (`0xa4a98e5`), and `GetAgentAPIShellInjection`
       (`0x838ce0f`) shows that all three resolve the binary path via Go's
       `os.Executable()` (`0x6e2d920`, which reads `/proc/self/exe` on Linux) without
       using `argv[0]`.
     - Inferred from `/proc/self/exe` semantics: because `harnesses/agy/bin/agy` is a
       `#!/usr/bin/env bash` script that `exec`s `~/.local/share/agy/agy`,
       `/proc/self/exe` points to `~/.local/share/agy/agy`. Both foreground
       (`agy update`) and background auto-updates swap
       `~/.local/share/agy/agy.new` -> `~/.local/share/agy/agy` in place and leave the
       `~/.local/bin/agy` symlink intact, and `GetAgentAPIShellInjection` writes
       `exec "$HOME/.local/share/agy/agy" agentapi "$@"` to
       `~/.gemini/antigravity-cli/bin/agentapi`.
     - One-time host activation moves the existing ELF binary from `~/.local/bin/agy` to
       `~/.local/share/agy/agy` before running `just link --apply` from `main` (since
       `tools/harness-links` refuses to overwrite a regular file at `~/.local/bin/agy`).

5. **Focused test specification for `hq-32317f` (`tools/test_worker_defaults.py`)**:
   - Add an `agy_installed(tmp_path)` fixture and `agy_env(env)` helper alongside
     `installed` / `pi_env`, plus four focused tests using existing `DEFAULTS`,
     `LIBRARY_VARS`, `GRANT_VARS`, `worker_view(env)`, and `assert_leaves_alone(env)`:
     - `test_agy_launcher_sets_the_defaults(agy_installed)` (mirrors
       `test_pi_launcher_sets_the_defaults`): run `ROOT / "harnesses/agy/bin/agy"` with
       `AGY_BIN` pointing at a `FAKE` (`#!/usr/bin/env bash\nenv\n`) stub and a clean
       environment; assert `worker_view(env) == DEFAULTS` and `assert_leaves_alone(env)`
       (all seven `LIBRARY_VARS` and both `GRANT_VARS` (`OPS_BUDGET`, `OPS_WORKERS`)
       absent).
     - `test_agy_launcher_keeps_a_value_it_was_given(agy_installed)` (mirrors
       `test_pi_launcher_keeps_a_value_it_was_given`): run with
       `{**agy_installed, "CARGO_BUILD_JOBS": "12"}`; assert
       `env["CARGO_BUILD_JOBS"] == "12"` and
       `worker_view(env) == {**DEFAULTS, "CARGO_BUILD_JOBS": "12"}`.
     - `test_agy_launcher_yields_to_host_budget_override(agy_installed)`: start from
       `base = agy_env(agy_installed)` (where all five `DEFAULTS` are `"4"` and
       `LIBRARY_VARS` / `GRANT_VARS` are unset) and overlay a `host-budget` grant
       environment (`OPS_BUDGET="8"`, `OPS_WORKERS="8"`, all five `DEFAULTS` keys set to
       `"8"`, and all seven `LIBRARY_VARS` set to `"1"`); assert `worker_view(merged)`
       has `"8"` for all five keys, `merged["OPS_BUDGET"] == "8"`,
       `merged["OPS_WORKERS"] == "8"`, and all seven `LIBRARY_VARS` equal `"1"`.
     - `test_agy_launcher_fails_closed_when_binary_missing(tmp_path)`: run
       `ROOT / "harnesses/agy/bin/agy"` with `AGY_BIN=str(tmp_path / "missing")`; assert
       `returncode == 127` and a diagnostic on `stderr`.

## Task-id color surface findings (hq-7826fd)

Inspected on installed `agy` `1.5.3` (`~/.local/bin/agy`, ELF BuildID
`50b5b6c0ca95a2a401f0c806222ecaa6`, `.gopclntab` at file offset `0x1714500`, `.text`
base `0x6d15080`) and the bundled `agy-customizations` documentation
(`docs/plugins.md`, `docs/hooks.md`, `docs/json_configs.md`), structured to match
`reply-color-findings.md` on lore-587c8a:

### Summary comparison row for `agy` `1.5.3`

| Surface | `agy` `1.5.3` finding | Evidence status |
|---|---|---|
| Raw SGR in assistant text | Passes into Goldmark + Glamour `ansi.renderText` (`0x9f63980..0x9f64520`), which wraps each text token via `charmbracelet/x/ansi.Style.Styled` (`0x9f640ec`, appending `\x1b[0m` reset after styled tokens) and word-wraps via `lipgloss.Wrap` (`0x9f76bc3`); also stored verbatim in the conversation trajectory (`CORTEX_STEP_TYPE_PLANNER_RESPONSE`), violating the stored-context boundary | Call path **Observed** in disassembly; exact terminal visual interaction with `Style.Styled` resets **Inferred** (not live-probed in TUI); disqualified by stored-context constraint regardless |
| Markdown elements with colour | Headings, bold, italic, links, inline code, blockquotes, lists, alerts, and fenced code blocks styled by `render.glamourStyleForScheme` (`0xa057ca0..0xa058620`) | **Observed** |
| HTML / span markup | Stripped to plain text: Goldmark `ast.RawHTML` and `ast.HTMLBlock` route in `ansi.(*ANSIRenderer).NewElement` (`0x9f6c0b3`, `0x9f6c2b3`) through `ansi.RenderContext.SanitizeHTML` (`0x9f6b9e0..0x9f6ba80`), which calls `bluemonday.(*Policy).Sanitize` (`0x9f6ba0e`, initialized via empty `bluemonday.NewPolicy` at `0x9f771c0` in `ansi.NewRenderer`) followed by `strings.TrimSpace` (`0x9f6ba20`) and `html.UnescapeString` (`0x9f6ba25`) | **Observed** |
| Theme RGB | Fixed scheme-wide palette (`types.ColorScheme`) in `settings.json`, customizable only via 5 seed colors (`customThemeSeedsLight` / `customThemeSeedsDark`: `background`, `primary`, `foregroundOverride`, `primaryForegroundOverride`, `codeForegroundOverride`); no per-regex or per-prefix token scope | **Observed** |
| Display-only rewrite of reply text | None inline: plugins (`docs/plugins.md`, `docs/json_configs.md`) bundle only declarative `skills/`, `rules/`, `hooks/hooks.json`, and `mcp_config.json`, with no markdown transformer or message-renderer API. `PostInvocation` (`hooks.NewPostInvocationHook.func1` at `0x87083e0..0x8708ae0`) receives `modelOutput` via `hookutils.GetLastModelOutputAndThinking` (`0x8708560` -> `0x86ffbc0`), and its `injectSteps` `systemMessage` (`hooks.buildSystemMessageStep` at `0x8705040..0x87055c0`) can set `metadata.user_markdown` (`docs/hooks.md:324-327`), but that appends a new step rendered through the same Glamour pipeline rather than rewriting the assistant reply in place | **Observed** |
| Tool/shell ANSI | `run_command` stdout routes through `render.renderCommandOutput` (`0xa086c60..0xa087ba0`) -> `render.renderOutputLines` (`0xa085aa0..0xa0864e0`), which wraps lines with ANSI-aware `muesli/reflow/wordwrap.(*WordWrap)` (`render.WrapLine` at `0xa085260..0xa085440`) and renders each line via `lipgloss.Style.Render` (`0xa085cd7`, `0xa085f20`, `0xa085fce`, `0xa086285`). Tool output is also recorded in tool-result trajectory steps when invoked by the agent | Call path **Observed** |
| Other coloured surfaces | Custom `statusLine.command` (`store.(*StatusLineRunner).run` at `0xa189440..0xa189b80` -> `model.StatusLineModel.RenderCustom` at `0xa407740..0xa407960` -> `model.StatusLineModel.Render` at `0xa408220..0xa408520`) passes command stdout lines directly into the TUI view via `strings.Join` (`0xa407920`, `0xa4084cb`) without Glamour rendering or ANSI stripping (`render.TruncateAnsiLine` at `0xa0465e0..0xa046700` uses ANSI-aware `lipgloss.Width` at `0xa046621` and `muesli/reflow/truncate.BytesWithTail` at `0xa046682`), completely outside stored model context | **Observed** |

### Detailed rendering path trace (`agy` `1.5.3`)

1. **Inline assistant reply rendering path (`google3/third_party/jetski/cli/render/render`) (Observed)**:
   - Disassembly of `render.(*itemRenderer).render` (`0xa064460..0xa066360`) ->
     `render.stepContentShared` (`0xa0810c0`) -> `render.stepContent`
     (`0xa0811a0..0xa084580`) shows that `CORTEX_STEP_TYPE_PLANNER_RESPONSE` steps invoke
     `render.renderPlannerBody` (`0xa05ee00..0xa05f180`, called at `0xa082a21` and
     `0xa082aca`).
   - `render.renderPlannerBody` calls `render.Markdown` (`0xa0586a0..0xa0587c0`) ->
     `render.(*markdownCache).render` (`0xa05cd60..0xa05cee0`) ->
     `render.renderMarkdownUncached` (`0xa0587c0..0xa059cc0`) -> `render.glamourRender`
     (`0xa059cc0..0xa059fa0`), which constructs a Goldmark + Glamour v2 renderer via
     `glamour.NewTermRenderer` (`0x9f8c2a0`, calling `goldmark.New` at `0x9f089a0` and
     `glamour/v2/ansi.NewRenderer` at `0x9f77180`) and renders the reply via
     `glamour.(*TermRenderer).RenderBytes` (`0x9f8c660`).
   - Why inline project-colored task IDs are unsupported in `agy` `1.5.3`:
     - **No display-only extension API (Observed)**: Unlike `pi`
       (`pi.registerMarkdownTransformer`) or Claude Code (`AssistantMessage` mod),
       `agy` `1.5.3` plugins and hooks expose no callback or extension point on
       `render.renderPlannerBody` or `render.Markdown`.
     - **HTML color markup is stripped (Observed)**: `ansi.NewRenderer` (`0x9f77180`)
       initializes a zero-tag `bluemonday.NewPolicy()` (`0x9f771c0`). When Goldmark
       emits `ast.RawHTML` or `ast.HTMLBlock`, `ansi.(*ANSIRenderer).NewElement`
       (`0x9f6c0b3`, `0x9f6c2b3`) routes the node to `ansi.RenderContext.SanitizeHTML`
       (`0x9f6b9e0..0x9f6ba80`), where `bluemonday.(*Policy).Sanitize` (`0x9f6ba0e`)
       strips `<span style="color:...">` and `<font color="...">` tags down to unstyled
       text.
     - **Markdown elements cannot color bare task IDs per project prefix (Observed)**:
       `render.glamourStyleForScheme` (`0xa057ca0..0xa058620`) assigns one scheme-wide
       color per Markdown element type (such as inline code or links). Furthermore,
       lore-587c8a requires task IDs (`<prefix>-<6 hex>`) to stay bare outside backticks
       and links. Bold status verdicts (`**done**`, `**blocked**`) and structural spacing
       work natively through Goldmark `ast.Emphasis` rendering and require no extension.
     - **Model-emitted raw SGR violates the stored-context constraint (Observed
       constraint; Inferred Glamour reset interaction)**: Having the model emit raw
       `\x1b[38;2;R;G;Bm` sequences in assistant replies stores those escape bytes in
       the conversation transcript (`CORTEX_STEP_TYPE_PLANNER_RESPONSE`) re-sent to the
       model on subsequent turns, violating the requirement to keep display styling out
       of stored model context. In addition, `ansi.renderText` (`0x9f63980..0x9f64520`)
       applies `charmbracelet/x/ansi.Style.Styled` (`0x9f640ec`) per text token with a
       trailing `\x1b[0m` reset.

2. **Hook `injectSteps` / `metadata.user_markdown` surface (Observed call path; Unknown whether Glamour preserves raw SGR in `user_markdown` without a live turn)**:
   - `hooks.NewPostInvocationHook.func1` (`0x87083e0..0x8708ae0`) calls
     `hookutils.GetLastModelOutputAndThinking` (`0x8708560` -> `0x86ffbc0`) and populates
     `PostInvocationHookArgs` (`hooks.proto` descriptor at `0x63d1cec`: `invocationNum`,
     `initialNumSteps`, `modelOutput`, `modelThinking`, plus `HookArgsCommon`; note that
     `agy-customizations/docs/hooks.md:348` omits `modelOutput` and `modelThinking` from
     its example JSON even though the binary populates them).
   - A `PostInvocation` hook can return `injectSteps` with a `systemMessage` step whose
     `metadata.user_markdown` (or `renderInfo.markdown` in `hooks.buildSystemMessageStep`
     at `0x8705040..0x87055c0`) displays an extra UI block after the turn while keeping
     `systemMessage.systemMessage` empty (`""`) in model context (`docs/hooks.md:324-327`).
   - However, this surface **cannot** color bare task IDs inline in the assistant reply
     itself (it appends a separate step below the turn), and `user_markdown` is rendered
     through the same Goldmark + Glamour pipeline where `bluemonday` strips HTML tags.
     Whether raw ANSI SGR bytes inside `metadata.user_markdown` survive Glamour's
     `ansi.Style.Styled` token resets in a live TUI session is **Unknown** without a
     model-turn probe, and even if they did, duplicating task IDs into a second footer
     step does not provide inline reply coloring.

3. **Statusline surface (`statusLine.command` in `harnesses/agy/settings.json`) (Observed)**:
   - `store.(*StatusLineRunner).run` (`0xa189440..0xa189b80`) serializes
     `types.StatusLineData` (`sessionId`, `StepCount`, `model`, `workspace`, `git`,
     `tokens`, `cost`, `duration`, `mcp`, `vimMode`) to JSON (`0xa1895f1`), pipes it to
     `/bin/sh -c <statusLine.command>` (`0xa1896d9..0xa189839`), trims trailing `\r\n`
     (`0xa189912`), and splits stdout on `\n` (`0xa18992c`).
   - `model.StatusLineModel.RenderCustom` (`0xa407740..0xa407960`) reads
     `(*StatusLineRunner).Output()` (`0xa40776a` -> `0xa1890a0`), prepends `Padding()`
     blank lines (`0xa4077c8` -> `0xa189260`), and joins the lines with `"\n"`
     (`0xa407920` -> `strings.Join`) with **no** Glamour pass and **no** ANSI sanitizer.
     `model.StatusLineModel.Render` (`0xa408220..0xa408520`) joins `RenderBuiltIn` and
     `RenderCustom` with `"\n"` (`0xa4084cb`) directly into the Bubble Tea TUI view, and
     width truncation (`render.TruncateAnsiLine` at `0xa0465e0..0xa046700`) uses
     ANSI-aware `lipgloss.Width` (`0xa046621`) and `muesli/reflow/truncate.BytesWithTail`
     (`0xa046682`).
   - Therefore, `statusLine.command` (currently `familiar statusline --harness agy` in
     `harnesses/agy/settings.json`) supports truecolor SGR (`\x1b[38;2;R;G;Bm...\x1b[0m`)
     derived from public `tasks projects --json` `color` hex values (`#RRGGBB`) without
     touching stored model context.

4. **Smallest additional check if runtime confirmation of `metadata.user_markdown` is ever wanted**:
   - Because `agy` `1.5.3` has no local mock-model flag (its language server speaks to
     Google Cloud Code / JetSki backend endpoints), testing `PostInvocation`
     `metadata.user_markdown` rendering in the TUI requires an authenticated single-turn
     `agy` invocation in a disposable workspace with a temporary `PostInvocation` hook
     returning `{"injectSteps":[{"systemMessage":{"systemMessage":"","metadata":{"user_markdown":"\u001b[38;2;115;169;255mhq-7826fd\u001b[0m"}}}]}`
     inside a private `tmux` session captured with `tmux capture-pane -e`. That check
     requires user authorization for a live model turn and cannot enable inline reply
     coloring regardless, so it is not recommended.

### Recommendation for `hq-db39da` and `prism-fd46ae`

1. **Inline assistant replies in `agy` `1.5.3`**: Do **not** attempt inline task-id
   coloring in Antigravity assistant replies. Keep bare `<prefix>-<6 hex>` task IDs,
   bold verdicts (`**done**`, `**blocked**`), and spacing as plain Markdown per
   lore-587c8a; revisit inline coloring for Antigravity only if a future `agy` release
   adds a display-only markdown/message renderer hook (analogous to `pi`'s
   `registerMarkdownTransformer` or Claude Code's `AssistantMessage` mod).
2. **Statusline (`statusLine.command`)**: If project-colored task IDs are wanted on
   Antigravity's statusline (for example, coloring the active task/branch badge in
   `familiar statusline --harness agy` using `tasks projects --json` RGB values), route
   that implementation through prism-fd46ae / familiar rather than adding a parallel
   renderer in `hq`.
