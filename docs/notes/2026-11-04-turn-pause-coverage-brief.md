# Turn-Pause Coverage Across Harnesses, Homes and Child Sessions — Brief

Date: 2026-11-04
Cluster: hq-be1fd6, hq-f247c3, hq-8a11d6, hq-ba40e9, hq-e8a7d5
Originating work: hq-9aa713 (`docs/specs/2026-11-01-turn-pause-design.md`, `docs/notes/2026-11-01-turn-pause-activation.md`)

## Problem

`tools/turn-pause` currently enforces turn budgets (`active_ns`, `root_calls`, `spawns`) and tracks advisory `compactions` across the default Claude Code home (`claude/settings.json`) and both Codex homes (`codex/hooks.json`, `codex/work/hooks.json`). Five follow-up ideas filed at the close of hq-9aa713 address the remaining coverage gaps in that boundary:

1. **Claude Code work home (hq-8a11d6):** `~/.claude-work/settings.json` (`local/claude/settings.work.json`) wires `claude-profile`, `harness-state-refresh`, and `relay`, but has no `turn-pause` entries.
2. **Antigravity (`agy`) coverage (hq-be1fd6):** `agy/hooks.json` routes `SessionStart`, `PreToolUse` (`"matcher": "*"`), and `Stop` to `relay` and `agy/hook`, with no `turn-pause` wiring or `agy` adapter in `tools/turn_pause/adapters.py`.
3. **Shell-launched child sessions (hq-f247c3):** A session launched from a shell tool (`claude -p`, `codex exec`) receives a fresh `session_id` with `agent_id: None`, so `tools/turn-pause` treats it as an independent root session with a fresh allowance and honours any `budget:` line its agent-authored prompt supplies.
4. **Codex compaction hook counter (hq-ba40e9):** Whether Codex fires `PreCompact` or `PostCompact` could not be settled in hq-fe672f because single-turn `codex exec` runs did not compact; `hq pause status` therefore prints `compactions -/2 (advisory, unhooked)` for Codex.
5. **Codex unhooked tools and command-argument surface (hq-e8a7d5):** On `codex-cli 0.166.0`, `write_stdin` and `wait` do not fire `PreToolUse`, and three narrower `0.166.0` questions remain open alongside an upstream feature-request draft and per-version re-probe checklist.

## Current behaviour and evidence

- **Originating provenance:** All five ideas were filed in session `claude-code:536b5ebf-5753-4a8b-ac83-61dde5ef4c79` (`toolu_01EkbGT7CaoUsxQbPkLuFpSu`, L2502/L2508) as controller-authored Task 10 Step 5 follow-ups of hq-9aa713 (`origin: "agent"`).
- **Claude Code work home (hq-8a11d6):**
  - `links.toml` links `~/.claude-work/settings.json` to `local/claude/settings.work.json` (untracked; `.githooks/pre-commit` refuses staged paths under `local/`).
  - `claude/settings.json` wires `tools/turn-pause --harness claude-code <Event>` (`timeout: 5`, `"matcher": "*"` on `PreToolUse`, `PostToolUse`, `PostToolUseFailure`) across all ten Claude Code lifecycle events (`UserPromptSubmit`, `PreToolUse`, `PostToolUse`, `PostToolUseFailure`, `Stop`, `SubagentStop`, `SessionEnd`, `SubagentStart`, `PreCompact`, `PostCompact`).
  - `local/claude/settings.work.json` exists on this host (`6368` bytes) with `SessionStart`, `UserPromptSubmit`, `PreToolUse`, `Notification`, `Stop`, `StopFailure`, and `SessionEnd` hooks, and zero `turn-pause` entries.
  - `tools/turn_pause/hook.py` line 35 already includes `'local/claude/settings.work.json'` in `WIRING` and `'.claude-work/settings.json'` in `HOME_LINKS`. Any tool call in a hooked Claude Code or Codex session that references `local/claude/settings.work.json` is blocked by `tools/turn_pause/protect.py`.
- **Antigravity (`agy`) hook surface (hq-be1fd6):**
  - `agy` `1.5.0` is installed. Commit `6273c206` (`2026-11-01`) updated `agy/hooks.json` `PreToolUse` to `"matcher": "*"` for `relay`, superseding the older `run_command`-only matcher note in hq-be1fd6's body.
  - Builtin `agy` hook documentation (`agy-customizations/docs/hooks.md`) documents six lifecycle events: `SessionStart`, `PreInvocation`, `PostInvocation`, `PreToolUse`, `PostToolUse`, and `Stop`. There is no `UserPromptSubmit`, `SubagentStart`, `SubagentStop`, `PreCompact`/`PostCompact`, or `SessionEnd`.
  - `agy` passes camelCase protojson payloads (`conversationId`, `workspacePaths`, `lastUserInput`, `toolCall: {name, args}`, `stepIdx`) and expects `{"decision": "allow"|"deny", "reason": "..."}` on `PreToolUse`, unlike Claude Code and Codex (`session_id`, `cwd`, `tool_name`, `tool_input`, `hookSpecificOutput.permissionDecision`).
- **Shell-launched child sessions (hq-f247c3):**
  - `tools/turn_pause/adapters.py` (`normalize`) identifies the state file strictly from `payload['session_id']` and distinguishes a worker from a root turn strictly by `bool(payload.get('agent_id'))`.
  - When a parent session runs `claude -p` or `codex exec` inside `Bash` or `exec_command`, the child process starts a new harness session with its own `session_id` and `agent_id: None`. It therefore creates a separate `<child-session-id>.json` state file, does not increment the parent's `spawns` or `active_ns`, and accepts a `budget:` first line from the parent agent's prompt.
  - Process-tree walking (`/proc/<pid>/stat` in `tools/turn_pause/state.py:find_harness_pid`) is already known to fail across Codex's `workspace-write` Linux bubblewrap sandbox because each `exec_command` runs in its own PID namespace (`docs/notes/2026-11-01-turn-pause-activation.md` line 112), where PID 1 is `bwrap` and parent PIDs outside the namespace are hidden.
- **Codex compaction and tool hooks (hq-ba40e9, hq-e8a7d5):**
  - `tools/harness-facts get --harness codex hook-compact-event` is `unknown` (probed on `codex-cli 0.166.0` in hq-fe672f; two single-turn `codex exec` runs with `model_auto_compact_token_limit = 20000` ended at 121k and 227k tokens without compacting).
  - Following hq-1942a1 and hq-e51fac (`2026-11-04`), compactions are an advisory context-growth signal across all harnesses (`compactions` warns once at 2 and never sets `paused = True`).
  - `codex-cli` on this host is still `0.166.0`. Three `0.166.0` checks named in `docs/specs/2026-11-01-turn-pause-design.md` (lines 255, 405, 463) and hq-e8a7d5's notes remain unprobed: (a) whether an allowed `exec_command` (`Bash`) that exits non-zero (`false`) still fires `PostToolUse`, (b) whether `exec_command` explicitly given `shell`, `login`, `tty`, or `workdir` drops those keys from `PreToolUse` `tool_input`, and (c) whether `features.shell_snapshot = true` allows a zsh global alias (`alias -g`) to expand inside `exec_command`.
  - hq-e8a7d5 also holds custody of the retained turn-pause probe and implementation artifacts under `$WORK_ROOT/hq/` (`hq-fe672f`, `hq-7203b2`, `hq-77b422`, `hq-9aa713` and their `RETENTION.tsv` manifests), handed over at hq-9aa713's close.

## Constraints

- **Self-protection and live activation (`tools/turn_pause/hook.py`, `protect.py`):** `local/claude/settings.work.json`, `agy/hooks.json`, `codex/hooks.json`, and `codex/work/hooks.json` are protected wiring paths (`local/claude/settings.work.json` is already in `WIRING`; adding `agy` or Codex `PreCompact`/`PostCompact` modifies live harness configs). Under the activation protocol (`docs/notes/2026-11-01-turn-pause-activation.md`), wiring changes in `main` or `local/` require explicit user activation approval, and Codex `hooks.json` edits require interactive hook-trust re-approval.
- **Open turn-pause remediation (hq-2dd09b):** hq-2dd09b (`Fix turn-pause follow-ups from hq-9aa713`) is currently open (`todo`, with child hq-c58737 touching `protect.py` and `test_turn_pause_protect.py`). Wiring `local/claude/settings.work.json` (hq-8a11d6) should wait on hq-2dd09b so the `protect.py` fixes land first.
- **Hosted CI zero-new-skip rule (`docs/test-execution.md`, `tools/test_ci_workflow.py`):** Hosted CI enforces an exact skip allowlist of three local-integration skips (`test_default_home_matches_links_toml`, `test_links_have_ converged`, `test_claude_mods`). `local/claude/settings.work.json` is untracked and absent in CI, so `tools/test_turn_pause_wiring.py` must check `local/claude/settings.work.json` conditionally inside existing test functions when `(ROOT / 'local/claude/settings.work.json').is_file()` plus a synthetic `tmp_path` test, never via a new `@pytest.mark.skipif` test function.
- **Capability facts reader (`AGENTS.md`):** Read `facts/capabilities.toml` exclusively via `tools/harness-facts` (`get`, `list`, or `lookup`), and update facts in a worktree after running reproducible probes.
- **Retained-evidence custody:** Keep the retained `$WORK_ROOT/hq/` directories and `RETENTION.tsv` manifests attached to hq-e8a7d5 intact.

## Alternatives

### 1. Parent-session linkage for shell-launched sessions (hq-f247c3)

- **Option A — Exported environment token from parent hook or wrapper (lean):** Have the parent harness session or an environment-injecting hook/wrapper set `HQ_TURN_PAUSE_ROOT_SESSION=<session_id>` (or read the parent's exported harness session variable if Claude Code / Codex already exports one to child shells). When `turn-pause` sees `HQ_TURN_PAUSE_ROOT_SESSION` differing from `payload['session_id']`, it routes the child session's events as a subagent/child of that root state and ignores any `budget:` line in the child's `UserPromptSubmit`.
  - *Pros:* Survives Codex's `bwrap` PID namespace isolation if `shell_environment_policy` passes the variable through (or if `turn-pause` / wrapper sets it).
  - *Cons:* `PreToolUse` stdout cannot export environment variables into the parent harness process; requires either an existing harness-exported env var, a `SessionStart`/`CLAUDE_ENV_FILE` mechanism, or a `PATH` wrapper around `claude`/`codex`.
- **Option B — `/proc` ancestry walk to a parent harness process (`find_harness_pid`):** Walk `/proc/<pid>/stat` above the child harness PID to detect an ancestor `claude` or `codex` process and map its PID to an existing `<session_id>.json` state file (`active_Call` PIDs or recorded root harness PID).
  - *Pros:* Needs no environment variable or `PATH` wrapper when `/proc` ancestry is intact (such as unsandboxed Claude Code `Bash`).
  - *Cons:* Fails inside Codex's `workspace-write` bubblewrap PID namespace, where ancestor PIDs outside the container are invisible.
- **Option C — Hybrid (`/proc` ancestry + `CLAUDE_ENV_FILE` / wrapper fallback):** Use `CLAUDE_ENV_FILE` / environment inheritance where supported and fall back to `/proc` ancestry when outside a PID namespace.
- **Current lean:** Probe what environment variables and `/proc` ancestry survive across the 2x2 matrix (`claude -p` and `codex exec` launched from Claude Code `Bash` and Codex `exec_command`) before choosing between Option A and Option C.

### 2. Antigravity (`agy`) turn-pause integration (hq-be1fd6)

- **Option A — Direct `agy` adapter in `tools/turn_pause/adapters.py` + `agy/hooks.json` entries (lean if `PreInvocation` / `PreToolUse` / `PostToolUse` payloads suffice):** Map `conversationId` -> `session_id`, `workspacePaths[0]` -> `cwd`, `PreInvocation` -> prompt boundary (if payload distinguishes user turns from background wakes), `PreToolUse` (`{"decision": "deny", "reason": ...}`) -> `PreToolUse`, `PostToolUse` -> `PostToolUse`, and `Stop` -> `Stop`.
- **Option B — Route through `agy/hook` wrapper:** Have `agy/hook` translate `agy` JSON into `turn-pause` calls alongside `SessionStart`/`Stop`.
- **Current lean:** Option A keeps all harness normalization inside `tools/turn_pause/adapters.py`, conditional on a probe of `agy 1.5.0`'s live `PreInvocation`, `PreToolUse`, `PostToolUse`, and `invoke_subagent` payloads.

## Unanswered questions

1. **What exact JSON payloads does `agy 1.5.0` pass to `PreInvocation`, `PreToolUse` (`"matcher": "*"`), `PostToolUse` (`"matcher": "*"`), and `Stop`, including during `invoke_subagent`?** Specifically: does `PreInvocation` fire once per user turn or on every background/subagent wake, does `lastUserInput` carry raw user text suitable for `budget:` parsing, does `{"decision": "deny", "reason": "..."}` on `PreToolUse` block non-`run_command` tools, and does an `invoke_subagent` child carry any link to the parent `conversationId`?
   - *Who/what answers it:* Bounded live probe on `agy 1.5.0` (follow-up task under the cluster goal, waking hq-be1fd6).
2. **What environment variables (`CLAUDE_ENV_FILE`, `CLAUDECODE`, `CODEX_*`, custom `HQ_*`) and `/proc` ancestry are visible inside a child `claude -p` or `codex exec` launched from Claude Code `Bash` and from Codex `exec_command`?**
   - *Who/what answers it:* Bounded probe across the 2x2 parent/child matrix (follow-up task under the cluster goal, waking hq-f247c3).
3. **On `codex-cli 0.166.0`, does a two-turn `codex exec` + `codex exec resume` session with `model_auto_compact_token_limit = 20000` fire `PreCompact` or `PostCompact`, and how do failed `exec_command` `PostToolUse`, explicit `exec_command` arguments (`shell`, `login`, `tty`, `workdir`), and `features.shell_snapshot = true` global aliases behave?**
   - *Who/what answers it:* Bounded probe extending `codex/probes/turn-pause-probe.py` on `codex-cli 0.166.0` (follow-up task under the cluster goal, waking hq-ba40e9 and hq-e8a7d5).

## Proposed decomposition

- **Cluster goal:** hq-8f5670 — `Extend turn-pause coverage across harnesses, homes and child sessions` (`todo`, P2, `m`, `mid`, `direct`)
  - **Scoped implementation task:**
    - hq-8a11d6 (`scoped` -> `todo`, P2, `xs`, `low`, `direct`, blocked on hq-2dd09b): Wire the ten `turn-pause` hook entries into `local/claude/settings.work.json` and extend `tools/test_turn_pause_wiring.py` without adding a CI skip.
  - **Research follow-ups (created in this pass) and waiting ideas (`briefed`):**
    - hq-7bed89 (`todo`, P2, `s`, `mid`, `direct`): Probe `agy 1.5.0` `PreInvocation`, `PreToolUse`, `PostToolUse` and subagent hook payloads -> wakes hq-be1fd6.
    - hq-2bc2d6 (`todo`, P2, `s`, `mid`, `direct`): Probe environment inheritance and process ancestry for shell-launched Claude Code and Codex child sessions -> wakes hq-f247c3.
    - hq-a5a449 (`todo`, P2, `s`, `mid`, `direct`): Probe Codex `0.166.0` two-turn compaction, failed `exec_command` `PostToolUse`, dropped arguments and shell-snapshot aliases -> wakes hq-ba40e9 and hq-e8a7d5.
