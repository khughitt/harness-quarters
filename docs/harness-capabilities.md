# Harness Capability and Integration Matrix

Cross-harness reference for integration layers in `hq`, hook dispatch in `relay`,
selected probed behaviour in `facts/capabilities.toml`, and session-store coverage.
For step-by-step onboarding and enumeration discovery across repositories, see
[Adding an agent harness](runbooks/adding-a-harness.md). For the full 45-fact table
across all six declared harness slugs, run `tools/harness-facts list --pretty`.

## 1. Integration layers across harnesses

`harnesses.toml` declares six canonical slugs: `claude-code`, `codex`, `agy`, `pi`,
`pi-durable`, and `opencode`. `pi` (the interactive CLI and `pi --mode rpc`) and
`pi-durable` (the SDK's durable `Harness`) have different execution and recovery
guarantees and stay separate slugs; a capability shown for one never applies to the
other. Crush is not declared in `harnesses.toml`: `tools/harness-facts` rejects
`crush` as an undeclared harness (exit `2`) rather than reporting speculative
`unknown` rows.

| Layer | `claude-code` | `codex` | `agy` | `pi` (CLI / RPC) | `pi-durable` (SDK) | `opencode` | Crush |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Declared in `harnesses.toml` | yes (`live_state`) | yes (`live_state`) | yes (`live_state`) | yes (`live_state`) | yes (bare slug) | yes (bare slug) | **not declared** |
| Home routing (`links.toml`) | `~/.claude`, `~/.claude-work` | `~/.codex`, `~/.codex-work` | `~/.gemini/antigravity-cli` (`agy`), `~/.gemini/config` (`agy-config`) | `~/.pi/agent` (plus pinned `~/.local/bin/pi`) | none (library runtime) | `~/.config/opencode.local` | none |
| Global instructions (`lore:instructions/AGENTS.md`) | `CLAUDE.md` in both homes | `AGENTS.md` in both homes | `AGENTS.md` in `~/.gemini/config` | `AGENTS.md` in `~/.pi/agent` | caller-supplied | `AGENTS.md` in home | none |
| Shared skills (`~/.agents/skills`) | non-Superpowers linked in `~/.claude/skills/*`; Superpowers via plugin (`claude-work` links none) | native `~/.agents/skills` discovery | `harnesses/agy/skills.json` (`../../.agents/skills`) | native `~/.agents/skills` discovery | caller-supplied | not wired in `links.toml` | none |
| Live-state filter & `live-picks` | `harnesses/claude/settings*.json` (`model`, `modelSettings`, `effortLevel` -> `local/live-picks.json`); `Stop` refresh | `harnesses/codex/config*.toml` (`model`, `model_reasoning_effort` -> `local/live-picks.json`; `projects\..+` trust -> `local/codex/trust.toml`); `Stop` refresh | `harnesses/agy/settings*.json` (`model`, `effort`, `effortByBase`, `trustedWorkspaces`, `seasonalThemesOptIn` -> `local/live-picks-agy.json`); anchored atomic-save adoption + `SessionStart`/`PreToolUse`/`Stop` refresh | `harnesses/pi/settings*.json` (`defaultProvider`, `defaultModel`, `defaultThinkingLevel` -> `local/live-picks-pi.json`; unrestored `deviceId`, `trackingId`); `harness-state.ts` extension refresh | none | none | none |
| SessionStart profile & capture notice | `<lore-checkout>/hooks/claude-profile`, `<ops-checkout>/hooks/capture-notice`, `<ops-checkout>/hooks/claude-sessionstart` | `<lore-checkout>/hooks/claude-profile`, `<ops-checkout>/hooks/capture-notice` (`~/.codex` only) | `harnesses/agy/hook` wraps `claude-profile` and `capture-notice` as `injectSteps` `systemMessage` | none | none | none | none |
| Command guard (`PreToolUse` -> `ops-guard`) | relayed `Bash` via `relay` | relayed `Bash` via `relay` | relayed `run_command` (mapped to `Bash`) via `relay` | none | none | none (`relay` refuses guard subscribers; no refusal channel) | none |
| Turn-end claim guard (`Stop`) | `<ops-checkout>/hooks/claim-guard --harness claude-code` | `<ops-checkout>/hooks/claim-guard --harness codex` on `Stop` and `SubagentStop` | one-shot `agy:<conversationId>` claim check in `harnesses/agy/hook` (native `claim-guard` tracked in `ops-33cef9` / `hq-c59809`) | none | none | none | none |
| Relay observer bus (`familiar*`) | `familiar`, `familiar-teardown` | `familiar`, `familiar-teardown-codex` | `familiar-agy` (`SessionStart`, `PreToolUse`, `Stop`) | none | none | `familiar-opencode` (server plugin bridge) | none |
| Verified call model stamp | `<ops-checkout>/hooks/claude-provenance` (`TASKS_AGENT` / `TASKS_MODEL`, no effort) | `relay model --harness codex` from rollout `turn_context` (`codex/<model>[@<effort>]`) | `relay model --harness agy` from `conversations/<id>.db` `gen_metadata` on `<relay-checkout>` `main` (pending `hq` relay pin bump past `v0.3.0`; unverified under Linux `--sandbox`) | unassessed | unassessed | unsupported in `relay model` | none |
| Session discovery, archive, episodes | full (`claude` adapter) | full (`codex` adapter) | supported with store caveats (`agy` adapter; see section 4) | intended (`hq-19bd76` / `hq-963ea4`) | not applicable | intended (`hq-19bd76` / `hq-aafc2a`) | intended (`hq-19bd76` / `hq-ce3ab4`) |

## 2. Native hooks, relay dispatch, and installed local policy

Hook and guard behaviour across harnesses separates into three distinct layers:

1. **Native hook capability**: which lifecycle or tool events the harness binary emits,
   what payload fields it writes to stdin, which tools bypass hooks (such as Codex
   `exec`, `exec.write_stdin`, and `wait`; see `hook-unhooked-tools` below), and what
   stdout JSON or exit codes block an action or inject context. Probed native behaviours
   live in `facts/capabilities.toml` (section 3) and `<relay-checkout>/docs/adapters.md`
   ("Verified native facts").
2. **Relay adapter and dispatch support**: what `<relay-checkout>/src/adapters/*.js`
   normalizes into schema-1 transient `Event` records (`claude-code`, `codex`, `agy`,
   and `opencode`), which mapped events expose `replies.<nativeEvent>.refuse` or
   `context`, how process ancestry resolves `sessionId` and terminal handles, and how
   `relay hook` partitions `--outer-ms` across input, registry, subscriber, and
   termination reserves.
   - **Authoritative hook-dispatch matrix**: see `<relay-checkout>/docs/adapters.md`
     ("Event mappings", "`agy` translation rules", "Verified native facts", "Budget",
     and "Failure modes") and the adapter definitions in
     `<relay-checkout>/src/adapters/{index,claude-code,codex,agy,opencode}.js`.
   - Do not treat `relay`'s adapter table as a statement of native harness limits: an
     unmapped event in `relay` (for example `PostToolUse`, `PreCompact`, or `agy`
     `PreInvocation`) or the absence of a `relay` adapter (`pi`, `pi-durable`, Crush)
     means `relay` does not dispatch it today, not that the harness lacks native hook or
     extension events. Broader cross-project assumption alignment is tracked in
     `relay-67b733`.
3. **Installed local policy (`hq`)**: which hooks and subscribers are wired in
   `harnesses/claude/settings.json`, `harnesses/codex/hooks.json`,
   `harnesses/codex/work/hooks.json`, `harnesses/agy/hooks.json`, and
   `relay/subscribers.template.json`:
   - `ops-guard` (`<ops-checkout>/hooks/relay-guard`) runs as a `relay` `before-tool`
     guard on tool `Bash` with a 30 s subscriber budget for `claude-code`, `codex`, and
     `agy` (`agy`'s adapter maps `run_command` with `CommandLine` to `Bash` and raises
     handler timeout and `--outer-ms` to 60 s / `60000` ms).
   - `opencode` uses an in-process server plugin bridge (`<relay-checkout>/integrations/opencode/`)
     whose events carry no refusal channel (`replies = {}`), so `relay` rejects guard
     subscribers for `opencode` and only `familiar-opencode` subscribes.

## 3. Selected probed behaviours (`facts/capabilities.toml`)

Read capability facts only through `tools/harness-facts` (`~/.agents/bin/harness-facts`),
never by parsing `facts/capabilities.toml` directly:

```sh
tools/harness-facts list --pretty          # full 45-fact table across all 6 declared slugs
tools/harness-facts list                   # full machine-readable JSON
tools/harness-facts get <fact> <harness>   # single (fact, harness) JSON entry
```

In every table below:

- **`probed` values** state the recorded value followed by `(v<version>, <date>, <evidence>)`.
- **`false` and `[]` are probed negative results**: a probe ran and showed the harness
  does not provide the capability.
- **`unknown` means unprobed**: no probe has recorded an answer for that slug, and
  consumers must apply their own safe fallback rather than treating `unknown` as `false`
  or `true`.
- **Crush** has no column because it is not declared in `harnesses.toml`.

### 3.1 Turn lifecycle, wakes, and hook coverage

| Fact (`type`) | `claude-code` | `codex` | `agy` | `pi` | `pi-durable` | `opencode` |
| --- | --- | --- | --- | --- | --- | --- |
| `controller-wake` (`boolean`) | `true` (`v2.1.295`, `2026-10-08`, `hq-b2515c`) | `false` (`v0.156.1`, `2026-09-24`, `tack-00ccb6`) | `true` (`v1.4.12`, `2026-10-31`, `hq-e72097`) | `unknown` | `unknown` | `unknown` |
| `controller-wake-kinds` (`set`) | `["shell", "subagent"]` (`v2.1.295`, `2026-10-08`, `hq-b2515c`) | `[]` (`v0.156.1`, `2026-09-24`, `tack-00ccb6`) | `["shell", "subagent"]` (`v1.4.12`, `2026-10-31`, `hq-e72097`) | `unknown` | `unknown` | `unknown` |
| `stop-input-in-flight-statuses` (`set`) | `["pending", "running"]` (`v2.1.295`, `2026-10-08`, `hq-b2515c; ops-ed76fe`) | `unknown` | `unknown` | `unknown` | `unknown` | `unknown` |
| `session-start-before-first-turn` (`boolean`) | `true` (`v2.1.304`, `2026-10-22`, `hq-f27918`) | `false` (`v0.163.0`, `2026-10-22`, `hq-f27918`) | `false` (`v1.4.12`, `2026-10-31`, `hq-e72097`) | `unknown` | `unknown` | `unknown` |
| `hook-deny-all-tools` (`boolean`) | `true` (`v2.1.316`, `2026-11-01`, `hq-fe672f`) | `false` (`v0.166.0`, `2026-11-01`, `hq-fe672f`) | `unknown` | `unknown` | `unknown` | `unknown` |
| `hook-unhooked-tools` (`set`) | `[]` (`v2.1.316`, `2026-11-01`, `hq-fe672f`) | `["exec", "exec.write_stdin", "wait"]` (`v0.166.0`, `2026-11-01`, `hq-fe672f`) | `unknown` | `unknown` | `unknown` | `unknown` |
| `hook-posttooluse` (`boolean`) | `true` (`v2.1.316`, `2026-11-01`, `hq-fe672f`) | `true` (`v0.166.0`, `2026-11-01`, `hq-fe672f`) | `unknown` | `unknown` | `unknown` | `unknown` |
| `hook-subagent-start` (`boolean`) | `true` (`v2.1.316`, `2026-11-01`, `hq-fe672f`) | `true` (`v0.166.0`, `2026-11-01`, `hq-fe672f`) | `unknown` | `unknown` | `unknown` | `unknown` |
| `hook-agent-id-on-child-calls` (`boolean`) | `true` (`v2.1.316`, `2026-11-01`, `hq-fe672f`) | `true` (`v0.166.0`, `2026-11-01`, `hq-fe672f`) | `unknown` | `unknown` | `unknown` | `unknown` |
| `hook-stop-carries-agent` (`boolean`) | `true` (`v2.1.316`, `2026-11-01`, `hq-fe672f`) | `true` (`v0.166.0`, `2026-11-01`, `hq-fe672f`) | `unknown` | `unknown` | `unknown` | `unknown` |
| `hook-compact-event` (`set`) | `["PostCompact", "PreCompact"]` (`v2.1.316`, `2026-11-01`, `hq-fe672f`) | `unknown` | `unknown` | `unknown` | `unknown` | `unknown` |
| `codex-spawn-evidence` (`set`) | `unknown` | `["PreToolUse", "SubagentStart"]` (`v0.166.0`, `2026-11-01`, `hq-fe672f`) | `unknown` | `unknown` | `unknown` | `unknown` |
| `codex-exec-nested-pretooluse` (`boolean`) | `unknown` | `true` (`v0.166.0`, `2026-11-01`, `hq-fe672f`) | `unknown` | `unknown` | `unknown` | `unknown` |
| `subagent-write-refused` (`set`) | `["ANALYSIS*.md", "FINDINGS*.md", "REPORT*.md", "SUMMARY*.md"]` (`v2.1.296`, `2026-10-12`, `hq-7b65dc`) | `unknown` | `unknown` | `unknown` | `unknown` | `unknown` |

Additional `hq-fe672f` turn-pause hook facts (`hook-prompt-text`, `hook-prompt-on-wake`,
`hook-prompt-on-goal-turn`, `hook-prompt-on-scheduled-wake`, `model-tool-surface`, and
`hook-tool-names`) are listed in full by `tools/harness-facts list --pretty`.

### 3.2 Question and answer routing

| Fact (`type`) | `claude-code` | `codex` | `agy` | `pi` | `pi-durable` | `opencode` |
| --- | --- | --- | --- | --- | --- | --- |
| `answer-hook-terminal` (`boolean`) | `true` (`v2.1.296`, `2026-10-11`, `hq-d85ede`) | `false` (`v0.162.1`, `2026-10-11`, `hq-d85ede`) | `false` (`v1.4.12`, `2026-10-31`, `hq-e72097`) | `unknown` | `unknown` | `unknown` |
| `answer-defer-managed` (`boolean`) | `true` (`v2.1.296`, `2026-10-11`, `hq-d85ede`) | `unknown` | `false` (`v1.4.12`, `2026-10-31`, `hq-e72097`) | `unknown` | `unknown` | `unknown` |
| `answer-server-terminal` (`boolean`) | `unknown` | `true` (`v0.162.1`, `2026-10-11`, `hq-d85ede`) | `unknown` | `unknown` | `unknown` | `true` (`v2.0.26`, `2026-10-11`, `hq-d85ede`) |
| `answer-server-managed` (`boolean`) | `unknown` | `true` (`v0.162.1`, `2026-10-11`, `hq-d85ede`) | `unknown` | `unknown` | `unknown` | `true` (`v2.0.26`, `2026-10-11`, `hq-d85ede`) |
| `answer-async-question` (`boolean`) | `unknown` | `true` (`v0.162.1`, `2026-10-11`, `hq-d85ede`) | `false` (`v1.4.12`, `2026-10-31`, `hq-e72097`) | `unknown` | `unknown` | `unknown` |

### 3.3 Headless durability, MCP stdio, and live-pick mechanics (`pi` vs `pi-durable` and others)

`pi` (`harnesses/pi/probes/rpc-probe.py` and `extension-probe.py`) and `pi-durable`
(`harnesses/pi/probes/durable-probe.mjs`) share a pinned package version in
`harnesses/pi/package.json` (`1.1.0`) but differ on idempotent submission, child
conversations, and turn resumption after process death:

| Fact (`type`) | `claude-code` | `codex` | `agy` | `pi` (CLI / RPC) | `pi-durable` (SDK) | `opencode` |
| --- | --- | --- | --- | --- | --- | --- |
| `headless-controls` (`set`) | `unknown` | `unknown` | `unknown` | `["abort", "fork", "prompt", "session-id", "steer"]` (`v1.1.0`, `2026-10-11`, `hq-57132d`) | `["abort", "fork", "prompt", "session-id", "steer"]` (`v1.1.0`, `2026-10-11`, `hq-57132d`) | `unknown` |
| `idempotent-submission` (`boolean`) | `unknown` | `unknown` | `unknown` | `false` (`v1.1.0`, `2026-10-11`, `hq-57132d`) | `true` (`v1.1.0`, `2026-10-11`, `hq-57132d`) | `unknown` |
| `child-conversations` (`boolean`) | `unknown` | `unknown` | `unknown` | `false` (`v1.1.0`, `2026-10-11`, `hq-57132d`) | `true` (`v1.1.0`, `2026-10-11`, `hq-57132d`) | `unknown` |
| `turn-resumes-after-kill` (`boolean`) | `unknown` | `unknown` | `unknown` | `false` (`v1.1.0`, `2026-10-11`, `hq-57132d`) | `true` (`v1.1.0`, `2026-10-11`, `hq-57132d`) | `unknown` |
| `usage-reported` (`set`) | `unknown` | `unknown` | `unknown` | `["cost", "tokens"]` (`v1.1.0`, `2026-10-11`, `hq-57132d`) | `["cost", "tokens"]` (`v1.1.0`, `2026-10-11`, `hq-57132d`) | `unknown` |
| `usage-includes-children` (`boolean`) | `unknown` | `unknown` | `unknown` | `unknown` | `false` (`v1.1.0`, `2026-10-11`, `hq-57132d`) | `unknown` |
| `mcp-stdio` (`boolean`) | `unknown` | `unknown` | `true` (`v1.4.12`, `2026-10-31`, `hq-e72097`) | `true` (`v1.1.0`, `2026-10-11`, `hq-57132d`) | `unknown` | `unknown` |
| `mcp-stdio-revisions` (`set`) | `unknown` | `unknown` | `["2025-11-25", "2026-07-28"]` (`v1.4.12`, `2026-10-31`, `hq-e72097`) | `["2025-11-25"]` (`v1.1.0`, `2026-10-11`, `hq-57132d; hq-501726; sci-b40b23`) | `unknown` | `unknown` |
| `model-pick-event` (`boolean`) | `false` (`v2.1.296`, `2026-10-10`, `hq-f51af7`) | `unknown` | `unknown` | `unknown` | `unknown` | `unknown` |
| `model-reset-clears-pick` (`boolean`) | `true` (`v2.1.296`, `2026-10-10`, `hq-f51af7`) | `false` (`v0.162.1`, `2026-10-10`, `hq-f51af7`) | `unknown` | `unknown` | `unknown` | `unknown` |
| `pi-extension-symlink-load` (`boolean`) | `unknown` | `unknown` | `unknown` | `true` (`v1.1.0`, `2026-10-15`, `hq-24416e`) | `unknown` | `unknown` |
| `pi-shutdown-awaits-handlers` (`boolean`) | `unknown` | `unknown` | `unknown` | `true` (`v1.1.0`, `2026-10-15`, `hq-24416e`) | `unknown` | `unknown` |
| `pi-default-write-before-deferred-select-handler` (`boolean`) | `unknown` | `unknown` | `unknown` | `true` (`v1.1.0`, `2026-10-15`, `hq-24416e`) | `unknown` | `unknown` |
| `pi-unchanged-default-emits-select` (`boolean`) | `unknown` | `unknown` | `unknown` | `false` (`v1.1.0`, `2026-10-15`, `hq-24416e`) | `unknown` | `unknown` |

### 3.4 Session-store and transcript properties

| Fact (`type`) | `claude-code` | `codex` | `agy` | `pi` | `pi-durable` | `opencode` |
| --- | --- | --- | --- | --- | --- | --- |
| `tool-result-call-ids` (`boolean`) | `true` (`v2.1.316`, `2026-11-01`, `hq-57d68e`) | `true` (`v0.166.0`, `2026-11-01`, `hq-57d68e`) | `false` (`v1.4.12`, `2026-11-01`, `hq-57d68e`) | `unknown` | `unknown` | `unknown` |
| `session-metadata-marks-headless` (`boolean`) | `true` (`v2.1.316`, `2026-11-01`, `hq-57d68e`) | `true` (`v0.166.0`, `2026-11-01`, `hq-57d68e`) | `unknown` | `unknown` | `unknown` | `unknown` |
| `transcript-self-describing` (`boolean`) | `true` (`v2.1.316`, `2026-11-01`, `hq-57d68e`) | `true` (`v0.166.0`, `2026-11-01`, `hq-57d68e`) | `false` (`v1.4.12`, `2026-11-01`, `hq-57d68e`) | `unknown` | `unknown` | `unknown` |
| `session-archive-complete` (`boolean`) | `unknown` | `unknown` | `false` (`v1.4.12`, `2026-11-01`, `hq-57d68e`) | `unknown` | `unknown` | `unknown` |
| `resume-reads-linked-subagent` (`boolean`) | `false` (`v2.1.304`, `2026-10-22`, `hq-0b8f2c`) | `unknown` | `unknown` | `unknown` | `unknown` | `unknown` |

## 4. Session discovery, archive, and transcript-reader coverage

`tools/harness_stores/__init__.py` registers three session-store adapters today:
`claude` (`claude-code`), `codex` (`codex`), and `agy` (`agy`). `hq sessions`,
`tools/session-archive`, and `agents/bin/session-episodes` all read this registry
(see [Adding an agent harness](runbooks/adding-a-harness.md) section 7 and
[agents/skills/session-logs/SKILL.md](../agents/skills/session-logs/SKILL.md)).

| Surface | `claude-code` (`tools/harness_stores/claude.py`) | `codex` (`tools/harness_stores/codex.py`) | `agy` (`tools/harness_stores/agy.py`) | `pi`, `opencode`, Crush |
| --- | --- | --- | --- | --- |
| `hq sessions` list & `-i` resume | `~/.claude` and `~/.claude-work` (`history.jsonl` + `projects/*/<id>.jsonl`); resumes `claude <flags> --resume <id>` | `~/.codex` and `~/.codex-work` (`state_5.sqlite` `threads` + `rollout-*.jsonl`); resumes `codex <flags> resume <id>` | `~/.gemini/antigravity-cli/conversation_summaries.db` + `brain/<id>/.system_generated/logs/transcript_full.jsonl`; resumes `agy <flags> --conversation <id>` | **not supported today** (no `tools/harness_stores/` adapter) |
| `tools/session-archive` capture & prune | captures `~/.claude/projects` and `~/.claude-work/projects` (both with `PruneHooks`, live prune gated) | captures `~/.codex/sessions` (with `PruneHooks`, live prune gated), `~/.codex/archived_sessions` (`prune=None`), and `~/.codex-work/sessions` (`prune=None`) | optional (`required=False`, `prune=None`) capture of `brain/*/.system_generated/logs/transcript(_full)?.jsonl` (`append_only=True`) and `conversation_summaries.db` (`append_only=False`); **incomplete** (below) | **not supported today** |
| `agents/bin/session-episodes` | in `DEFAULT_HARNESSES` (`--harness claude-code`) | in `DEFAULT_HARNESSES` (`--harness codex`) | supported via explicit `--harness agy` (omitted from `DEFAULT_HARNESSES` until the 2027-02-16 `flow-trial-1` readout, `obs-f5710b`) | **not supported today** |
| `agents/skills/session-logs/SKILL.md` | full JSONL record & prompt-stripping guide | full rollout JSONL & prompt-stripping guide | full step-JSONL, positional `GENERIC` pairing & `SYSTEM_MESSAGE` background-wake guide | store paths noted for `opencode` (`~/.local/share/opencode/opencode.db`) and Crush (`~/.crush/crush.db`, `<project>/.crush/crush.db`); no reader |

### `agy` archive and transcript limits

As recorded by the `hq-57d68e` facts in section 3.4:

- **Archive completeness (`session-archive-complete = false`)**: `session-archive` captures
  only `brain/<id>/.system_generated/logs/transcript.jsonl`, `transcript_full.jsonl`, and
  `conversation_summaries.db`. It does **not** capture per-conversation SQLite databases
  (`~/.gemini/antigravity-cli/conversations/<id>.db`, which hold generation/model metadata)
  or spilled tool outputs (`brain/<id>/.system_generated/steps/*/output.txt`).
- **Non-self-describing transcripts (`transcript-self-describing = false`)**: a
  `transcript_full.jsonl` file does not carry the conversation's workspace URI, title, or
  `parent_conversation_id`; `hq sessions` reads those from `conversation_summaries.db`.
- **Positional tool results (`tool-result-call-ids = false`)**: `PLANNER_RESPONSE` tool
  calls carry no call IDs; `session-episodes` pairs the *k*-th `GENERIC` step (or later
  `SYSTEM_MESSAGE` matching `sender=<bg-id>`) with the *k*-th tool call.

### Intended session-store parity work (not current capability)

Bringing the remaining harnesses to session-store parity behind `tools/harness_stores/`
is tracked under goal `hq-19bd76` ("Session-store parity across harnesses, with harness
logic behind one adapter per harness"):

- `hq-963ea4`: support `pi` sessions in `hq sessions`, `session-archive`,
  `session-episodes`, and `session-logs`.
- `hq-aafc2a`: support `opencode` sessions in `hq sessions`, `session-archive`,
  `session-episodes`, and `session-logs` (alongside `obs-175b10` for `obs` indexing).
- `hq-ce3ab4`: support Crush sessions in `hq sessions`, `session-archive`,
  `session-episodes`, and `session-logs` (alongside `obs-175b10`).
