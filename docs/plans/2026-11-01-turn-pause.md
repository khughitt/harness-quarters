# Turn Pause Hook Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. This task runs under the flow skill (trial arm "flow on"): each child is `implementing → verified → closed` in this worktree.

**Goal:** A hook in hq that counts each turn of a Claude Code or Codex session tree and, past its limits, refuses further work (except an enforced closing allowlist) and notifies the user until the user's next message.

**Architecture:** A Python package `tools/turn_pause/` of pure parts (prompt rules, limits, counters, allowlist) behind a thin hook entry `tools/turn-pause` that normalizes each harness's native payload into one event type, applies it to a per-root state file under a lock, and prints the harness's decision JSON. `hq pause status|limits` reads the same state and limits. A replay tool runs the same counters over stored transcripts to gate the approved fire rate before anything is wired.

**Tech Stack:** Python 3 standard library only (`tomllib`, `fcntl`, `shlex`, `json`, `socket`); pytest via `uv run --with pytest`, as hq's justfile does.

**Spec:** `docs/specs/2026-11-01-turn-pause-design.md` (accepted at `8a130e9`, wording fix `ba9178a`). Companion: lore-911121's guidance spec, records `lore/docs/specs/2026-11-01-turn-pause-guidance-design.md` at `fbae8f0d6`.

## Global Constraints

- Defaults (user-approved 2026-11-01): active 4 h (`14400` s), `500` root tool calls, `30` tree spawns, `2` compactions; a turn pauses when any count goes *above* its limit (the 501st call, the 31st spawn, the third compaction, active time over 14400 s).
- Warning at three quarters of any limit, once per limit per turn.
- Idle gap rule: a gap counts in full while any call in the tree is in flight; otherwise only when under `600` s.
- Closing grace: `25` allowlisted calls per session after the pause; bookkeeping and cancellation never exhausted.
- Budget directive grammar: first non-empty typed line, alone, `budget: <duration>[, <n> calls][, <n> agents][, <n> compactions]`; duration units `m` or `h` (`90m`, `12h`, `1.5h`); unnamed limits scale by `duration / 14400 s`, rounded up.
- No `git` invocation and no `tasks show` without `--no-fetch` while paused.
- State under `$XDG_STATE_HOME/hq/pause/` (default `~/.local/state/hq/pause/`); pruned at SessionEnd and after 7 days without events.
- Hook latency: under 50 ms p99 per call on this host.
- Unreadable or unwritable state refuses the call (fail early); the harness's own hook timeout is the only fail-open path.
- Tests that start subprocesses build their environment key by key with a temporary `HOME` and `XDG_STATE_HOME` (global Tests rule); no test touches the live state directory or the user's harness homes.
- Wiring the hook into `claude/settings.json` or `codex/*hooks.json` on main *is* activation (the homes link to main's files): the branch may carry the wiring, but merging it needs the user's separate approval.
- hq declares no `.tt.toml`, so its test policy is the default: focused runs while working (`uv run -q --with pytest pytest tools/<test file> -q`), `just test` before each commit.

## Review Focus

1. A Claude Code turn that runs background subagents and then sits at its own Stop while they work: the children's events must keep the tree active, and the root's Stop must close only the root's open calls. Test in Task 3.
2. Two tool calls of the same session arriving in parallel: one counter update must not lose the other. Test in Task 4 (concurrent `Store.locked`).
3. A paused session whose first refused call is itself `tasks park`: the park must pass, not count against grace twice, and leave the turn paused. Test in Task 6.
4. A user who answers a paused turn with only `continue`: the pause ends, counters reset, and no budget is set. Test in Task 6.
5. A limits file edited mid-turn (by anyone): the turn pauses and the notification says why, even when no count is near its limit. Test in Task 6.

---

### Task 1: Probe the hook surfaces and record capability facts

The adapters in Tasks 6 and 8 depend on what the installed harnesses actually send. This task runs isolated, headless sessions with a logging probe hook and records each answer through `tools/harness-facts`; `unknown` is a valid answer. It is a live operation: two failed attempts at one probe with no established cause stop for the user (global Decisions rule).

**Files:**
- Create: `claude/probes/turn-pause-probe.py`, `codex/probes/turn-pause-probe.py` (a hook that appends each payload to a file named by `TURN_PAUSE_PROBE_LOG` and denies one named tool)
- Modify: `facts/capabilities.toml`
- Test: `tools/test_harness_facts.py` (existing check covers the new entries)

**Interfaces:**
- Produces facts, each per harness `claude-code` and `codex`, in two classes.

**Mandatory**: the design cannot hold without them. A `false`, an `unknown` or a missing result for any of them stops the plan before Task 5; bring the evidence to the user. No later task may proceed on a fallback for these.

| Fact | Must show |
| --- | --- |
| `hook-deny-all-tools` | a PreToolUse deny held, with the reason shown to the model, for a spawn tool, a wait tool, a shell tool, a file-write tool and (Codex) an outer `exec` |
| `hook-prompt-text` | UserPromptSubmit carries the typed prompt text |
| `hook-agent-id-on-child-calls` | a child's tool calls carry an identifier distinct from the root's (`agent_id`), and the root's `session_id` |
| `model-tool-surface` | the tool names the runtime offers its model **and each cancellation tool's argument schema** (for example Codex `interrupt_agent` takes `{target: …}`), read from the session's own tool list |
| `codex-spawn-evidence` (Codex only) | each worker that actually starts is observed exactly once by a hook event the hook can count: SubagentStart, or a nested `spawn_agent` PreToolUse. The probe runs one code-mode `exec` whose loop spawns three workers and whose source also holds a `tools.spawn_agent(` call in a branch that never runs, plus one direct `spawn_agent` function call; the fact records which source saw exactly four starts. Neither source seeing exactly four is a mandatory failure |

**Optional with a documented fallback**: a `false` or `unknown` selects the fallback named here, which Tasks 3 to 6 implement and test; it does not stop the plan.

| Fact | Fallback when absent |
| --- | --- |
| `hook-posttooluse` | an agent's open call closes at that agent's next hook event or Stop; `write_stdin` cancellation stays refused |
| `hook-compact-event` (`PreCompact`, `PostCompact`, both, none) | no compaction counter for that harness; lore's rule has the agent count |
| `hook-subagent-start` (Claude Code) | workers are recorded from child events only; Claude Code spawns are counted from `Agent`/`Task` calls either way |
| `hook-stop-carries-agent` (Stop/SubagentStop identify which agent stopped) | open calls close at the next genuine prompt only |
| `hook-prompt-on-wake` | the genuine-prompt filter applies regardless, so a wake never starts a turn |
| `codex-exec-nested-pretooluse` (Codex only) | cancellation calls are validated from the outer `exec` source; spawns are never read from source (`codex-spawn-evidence` decides their source) |

- [ ] **Step 1:** Write the probe hook: read stdin JSON, append it with the hook event name and `time.time()` to `$TURN_PAUSE_PROBE_LOG`; when `tool_name` equals `$TURN_PAUSE_PROBE_DENY`, print the PreToolUse deny JSON from relay `docs/api.md` "Verified native facts".
- [ ] **Step 2:** Run each harness headless in an isolated home per README "Re-probing a fact" (Claude Code with `--settings` naming a temporary settings file; Codex with a temporary `CODEX_HOME` carrying only the probe hooks and the auth the README names), on a prompt that spawns one subagent, waits on it, runs one shell command, and is denied one tool of each kind in turn; for Codex, also the `codex-spawn-evidence` run.
- [ ] **Step 3:** Read the logs and record each fact with `status = "probed"`, `version`, `date`, `evidence = "hq-<child id>"` and a `note` naming the observation; record `unknown` where a run could not show it. Add a note on ops-daf2cd with the nested-PreToolUse observation.
- [ ] **Step 4:** Check every mandatory fact holds. Compare `model-tool-surface` against the spec's cancellation table (Claude Code `TaskStop`/`KillShell`; Codex `interrupt_agent`, `close_agent`, `write_stdin`) by name and by argument schema. Any mandatory failure, a named control the runtime lacks, or a cancellation tool it offers that the table does not name, stops the plan: bring the evidence and a corrected table to the user before Task 5. Save each recorded argument schema as a fixture under `tools/fixtures/turn-pause/schemas/<harness>-<tool>.json`; Task 5's tests build their inputs from these files.
- [ ] **Step 5:** `tools/harness-facts check` passes; `just test`; commit `feat(facts): probe the hook surfaces the turn pause needs`.

### Task 2: Prompt rules and limits

**Files:**
- Create: `tools/turn_pause/__init__.py`, `tools/turn_pause/prompt.py`, `tools/turn_pause/limits.py`, `tools/turn_pause/limits.toml`
- Test: `tools/test_turn_pause_prompt.py`, `tools/test_turn_pause_limits.py`

**Interfaces:**
- Produces:
  - `prompt.is_genuine(text: str, harness: str) -> bool`: false when the stripped text is empty, begins with `<` (except `<pasted_content`), or, for `codex`, begins with `# AGENTS.md`.
  - `prompt.typed_text(text: str) -> str`: the text with every `<pasted_content id="…">…</pasted_content id="…">` block removed.
  - `@dataclass(frozen=True) Budget(seconds: int, calls: int | None, agents: int | None, compactions: int | None)`; `@dataclass(frozen=True) Malformed(reason: str)`.
  - `prompt.parse_budget(text: str) -> Budget | Malformed | None`: looks only at the first non-empty line of `typed_text(text)`; `None` when that line does not start with `budget:` (case-insensitive key).
  - `@dataclass(frozen=True) Limits(active_seconds: int, calls: int, spawns: int, compactions: int)`.
  - `limits.DEFAULTS_PATH: Path` (`tools/turn_pause/limits.toml`); `limits.load(path: Path = DEFAULTS_PATH) -> tuple[Limits, str]` returning the limits and the file's sha256.
  - `limits.with_budget(defaults: Limits, budget: Budget) -> Limits`.

- [ ] **Step 1: Write the failing tests**

```python
@pytest.mark.parametrize('text,expected', [
    ('fix the bug', True), ('<task-notification>done</task-notification>', False),
    ('<system-reminder>x</system-reminder>', False), ('<pasted_content id="1">x</pasted_content id="1"> look', True),
])
def test_is_genuine_claude(text, expected): assert prompt.is_genuine(text, 'claude-code') is expected

def test_is_genuine_codex_agents_injection(): assert not prompt.is_genuine('# AGENTS.md instructions', 'codex')

def test_budget_first_line(): assert prompt.parse_budget('budget: 12h\nrun the sweep') == Budget(43200, None, None, None)
def test_budget_named_counts(): assert prompt.parse_budget('budget: 10h, 2000 calls, 80 agents') == Budget(36000, 2000, 80, None)
def test_budget_minutes_and_fraction(): assert prompt.parse_budget('budget: 90m').seconds == 5400 and prompt.parse_budget('budget: 1.5h').seconds == 5400

@pytest.mark.parametrize('text', [
    'please review\nbudget: 100h', '```\nbudget: 100h\n```', '> budget: 100h',
    '<pasted_content id="1">budget: 100h</pasted_content id="1">',
])
def test_budget_examples_are_silent(text): assert prompt.parse_budget(text) is None

def test_second_budget_line_ignored(): assert prompt.parse_budget('budget: 2h\nbudget: 100h') == Budget(7200, None, None, None)
def test_budget_malformed(): assert isinstance(prompt.parse_budget('budget: 12 hours please'), Malformed)

def test_defaults_file(): assert limits.load()[0] == Limits(14400, 500, 30, 2)
def test_budget_scales_unnamed(): assert limits.with_budget(Limits(14400, 500, 30, 2), Budget(43200, None, None, None)) == Limits(43200, 1500, 90, 6)
def test_budget_named_overrides(): assert limits.with_budget(Limits(14400, 500, 30, 2), Budget(36000, 2000, 80, None)) == Limits(36000, 2000, 80, 5)
```

- [ ] **Step 2:** Run `uv run -q --with pytest pytest tools/test_turn_pause_prompt.py tools/test_turn_pause_limits.py -q`; expected: FAIL on import.
- [ ] **Step 3:** Implement both modules and `limits.toml` (`active_seconds = 14400`, `calls = 500`, `spawns = 30`, `compactions = 2`, with a comment naming the spec and the approval date). Scaling rounds up (`math.ceil`).
- [ ] **Step 4:** Rerun; expected: PASS.
- [ ] **Step 5:** `just test`; commit `feat(turn-pause): prompt rules, budget directive and limits`.

### Task 3: Counters

**Files:**
- Create: `tools/turn_pause/events.py`, `tools/turn_pause/counters.py`
- Test: `tools/test_turn_pause_counters.py`

**Interfaces:**
- Consumes: `Limits` (Task 2).
- Produces:
  - `@dataclass(frozen=True) Event(t: float, agent: str | None, kind: Literal['prompt', 'tool_start', 'tool_end', 'agent_stop', 'compact', 'spawn', 'tick'], call_id: str | None = None, tool: str | None = None, nested: bool = False, key: str | None = None)`; `agent=None` means the root; `nested` marks a Codex call made inside an outer `exec`; `key` identifies a spawn for deduplication.
  - `events.USER_WAIT_TOOLS = {'AskUserQuestion', 'request_user_input', 'request_user_input_async'}`.
  - Spawns are their own events, never inferred from a tool start or from source text: a spawn is counted only from evidence that a worker started, and each harness has exactly one counting source. **Claude Code:** each allowed `Agent`/`Task` call, keyed by its tool-use id (one call starts one subagent; Claude Code has no code mode); its SubagentStart only records a worker. **Codex:** the source `codex-spawn-evidence` selected in Task 1: either SubagentStart, keyed by the worker's `agent_id`, or nested and direct `spawn_agent` PreToolUse calls the hook allowed, keyed by call id; the other source only records workers. An outer `exec`'s source is never parsed for spawns: one `tools.spawn_agent(` in a loop can start many workers, and one in an unexecuted branch starts none. With SubagentStart as the source, a spawn is counted when the worker has started, so the 31st worker exists and the tree pauses at its next call.
  - `@dataclass TurnState(started: float, limits: Limits, limits_sha: str, active: float = 0.0, calls: int = 0, spawns: int = 0, compactions: int = 0, last_t: float | None = None, in_flight: dict[str, str | None] = field(default_factory=dict), spawn_keys: set[str] = field(default_factory=set), warned: set[str] = field(default_factory=set))`, JSON round-trippable through `to_json()`/`from_json()`.
  - Every function below first adds the gap since `last_t` (in full while `in_flight` is non-empty, else when under 600 s) and sets `last_t`.
  - `counters.attempt(state: TurnState, ev: Event) -> None` for a `tool_start`: counts a root call when `agent is None` and not `nested`. It does **not** record the call as in flight: a refused call has no completion event, so recording it would keep the tree active forever.
  - `counters.started(state: TurnState, ev: Event) -> None` for a `tool_start` the hook allowed: adds it to `in_flight` unless the tool is a user-wait tool.
  - `counters.apply(state: TurnState, ev: Event) -> None` for every other kind: `tool_end` removes the call; `agent_stop` removes that agent's open calls; `compact` counts only for the root; `spawn` counts once per `key` (`spawn_keys`); `tick` only moves time. A `prompt` is never applied (the caller starts a new turn). The hook applies a call's `spawn` events only after allowing the call.
  - `counters.crossed(state: TurnState) -> str | None`: the first of `'active'`, `'calls'`, `'spawns'`, `'compactions'` whose count is above its limit.
  - `counters.due_warnings(state: TurnState) -> list[str]`: limits at or above three quarters not yet in `warned` (the caller adds them).

- [ ] **Step 1: Write the failing tests**, building events with a helper `ev(t, kind, agent=None, call=None, tool=None)`:
  - `test_eight_half_hour_calls_count_four_hours`: eight `attempt`+`started`/`tool_end` pairs of 1800 s each, 5 s apart; `state.active == pytest.approx(8 * 1800 + 7 * 5)` and `crossed(state) == 'active'` after one more second of in-flight call.
  - `test_long_wait_on_silent_child_counts`: root `tool_start` of `wait_agent`, `tool_end` 1800 s later, no events between; active grows by 1800.
  - `test_idle_gap_over_ten_minutes_with_nothing_in_flight_counts_nothing`.
  - `test_user_wait_tool_never_in_flight`: `AskUserQuestion` start, end 8 h later; active grows by 0.
  - `test_agent_stop_closes_only_that_agents_calls`: root and child each with an open call; root `agent_stop`; child call still open and a later gap counts in full.
  - `test_children_keep_tree_active_after_root_stop` (Review Focus 1).
  - `test_counts_root_calls_tree_spawns_root_compactions`: a child's `attempt` adds no call; a child's `spawn` event adds a spawn; a child's `compact` adds nothing.
  - `test_loop_in_one_exec_counts_each_started_worker`: one root `attempt` of an outer `exec`, then 31 `spawn` events keyed `w1` to `w31`: `calls == 1`, `spawns == 31`, `crossed(state) == 'spawns'`; applying `w7` again leaves `spawns == 31`.
  - `test_unexecuted_spawn_in_source_counts_nothing`: one root `attempt` of an outer `exec` whose input names `tools.spawn_agent(` and no `spawn` event: `spawns == 0`.
  - `test_nested_calls_count_no_root_calls`: `attempt` with `nested=True` leaves `calls` unchanged.
  - `test_refused_call_then_long_idle_counts_nothing`: `attempt` of a root call (never `started`), then a `tick` 3 h later; `active` grows by 0 and `in_flight` is empty.
  - `test_crossing_is_strictly_above`: 500 root calls → `None`; 501 → `'calls'`; 3 compactions → `'compactions'`.
  - `test_warning_once_per_limit`: at 375 calls `due_warnings == ['calls']`; after adding to `warned`, `[]`.
- [ ] **Step 2:** Run `uv run -q --with pytest pytest tools/test_turn_pause_counters.py -q`; expected: FAIL.
- [ ] **Step 3:** Implement `events.py` and `counters.py`.
- [ ] **Step 4:** Rerun; expected: PASS.
- [ ] **Step 5:** `just test`; commit `feat(turn-pause): turn counters with in-flight active time`.

### Task 4: State store

**Files:**
- Create: `tools/turn_pause/state.py`
- Test: `tools/test_turn_pause_state.py`

**Interfaces:**
- Consumes: `TurnState` (Task 3).
- Produces:
  - `@dataclass RootState(harness: str, root: str, turn: TurnState | None, paused: str | None = None, grace_used: dict[str, int] = field(default_factory=dict), workers: set[str] = …, exec_sessions: set[str] = …, harness_pid: int | None = None, cwd: str | None = None, notified: bool = False, notify_error: str | None = None, budget_note: str | None = None)`; `paused` holds the crossed limit's name or `'limits-changed'`.
  - `class StateError(Exception)`.
  - `state.state_dir(env: Mapping[str, str] = os.environ) -> Path`.
  - `class Store(dir: Path)` with `locked(harness: str, root: str) -> ContextManager[RootState]` (`fcntl.flock` on `<dir>/<harness>-<root>.lock`, load or create, write `<dir>/<harness>-<root>.json` through a temporary file and `os.replace` on exit), `read(harness, root) -> RootState | None` (no lock, for status), `latest_for_cwd(cwd: str) -> tuple[str, str] | None` (harness and root of the newest state whose `cwd` matches), `root_for_agent(harness: str, agent_id: str) -> str | None` (the root whose `workers` holds the id), `remove(harness, root)`, `prune(now: float, max_idle: float = 7 * 86400) -> list[str]`.
  - Any unreadable, unparsable or unwritable file raises `StateError` naming the path and the error.

- [ ] **Step 1: Write the failing tests** (every test uses `tmp_path`): round trip of a `RootState` with an open call; `test_parallel_updates_do_not_lose_counts` (Review Focus 2: 8 threads × 50 increments of `turn.calls` under `locked` give 400); corrupt JSON raises `StateError` with the path in its message; a read-only directory raises `StateError`; `prune` removes a state idle 8 days and keeps one idle 6 days; `latest_for_cwd` picks the newest; `root_for_agent` finds a worker's root and returns `None` for an unknown id.
- [ ] **Step 2:** Run `uv run -q --with pytest pytest tools/test_turn_pause_state.py -q`; expected: FAIL.
- [ ] **Step 3:** Implement `state.py`.
- [ ] **Step 4:** Rerun; expected: PASS.
- [ ] **Step 5:** `just test`; commit `feat(turn-pause): locked per-root state store`.

### Task 5: Closing allowlist, shell validator and cancellation

**Files:**
- Create: `tools/turn_pause/allowlist.py`
- Test: `tools/test_turn_pause_allowlist.py`

**Interfaces:**
- Consumes: `RootState.workers`, `RootState.exec_sessions`, `RootState.harness_pid` (Task 4); the cancellation names Task 1 confirmed.
- Produces:
  - `Klass = Literal['bookkeeping', 'cancellation', 'read', 'refuse']`.
  - `@dataclass(frozen=True) Verdict(klass: Klass, reason: str)`.
  - `allowlist.classify(harness: str, tool: str, tool_input: dict, owned: Owned) -> Verdict`, where `@dataclass(frozen=True) Owned(workers: frozenset[str], exec_sessions: frozenset[str], harness_pid: int | None)`.
  - `allowlist.shell(cmd: str, owned: Owned) -> Verdict` (the spec's shell validator; `kill` targets checked with `descends_from`).
  - `allowlist.codex_exec(source: str, owned: Owned) -> Verdict` (the spec's literal-only grammar; anything else `refuse`).
  - `allowlist.descends_from(pid: int, ancestor: int, proc: Path = Path('/proc')) -> bool` (walks `PPid:` in `<proc>/<pid>/status`; false for the ancestor itself).
  - `allowlist.touches_protected(tool_input: dict, paths: Sequence[Path]) -> bool` (any string in the input contains any protected path, expanded and with `~`).
  - Program tables in the module: `BOOKKEEPING = {('tasks', 'park'), ('tasks', 'note'), ('hq', 'pause')}`; `RECORD_READS = {('tasks', 'show'), ('tasks', 'claims'), ('tasks', 'list'), ('tasks', 'attach')}` (`show` requires `--no-fetch`); `READERS = {'cat': {'-n'}, 'head': {'-n', '-c'}, 'tail': {'-n', '-c'}, 'wc': {'-l', '-c', '-w'}, 'ls': {'-l', '-a', '-la', '-al'}}`; `host-load --section session`; Claude Code `Read`, `Grep`, `Glob` as `read`; cancellation names from the spec's table as confirmed by Task 1.

- [ ] **Step 1: Write the failing tests**, table-driven:
  - passes: `tasks park lore-1 "next"` → bookkeeping; `tasks show x --no-fetch` → read; `cat a.txt` → read; `kill -TERM <pid of a child the test spawns>` with `harness_pid=os.getpid()` → cancellation; Codex `text(await tools.exec_command({cmd: "tasks note x \"y\""}))` → bookkeeping; `tools.interrupt_agent({target: "w1"})` with `workers={'w1'}` → cancellation; `write_stdin` with `{"session_id": 7, "chars": "\u0003"}` and `exec_sessions={'7'}` → cancellation. Every cancellation input is built from the argument-schema fixtures Task 1 saved (`tools/fixtures/turn-pause/schemas/`), and a test asserts each fixture's required argument names match what `classify` reads (`target` for `interrupt_agent` today), so a schema change fails a test rather than silently refusing cancellation.
  - refusals: `git diff`, `git status`, `git worktree list`, `tasks show x`, `cat a; rm b`, `cat a | sh`, `cat $(x)`, `cat a > b`, `FOO=1 cat a`, `/bin/cat a`, `tail -f log`, `ls *`, `sed -n 1p a`, `Edit`, `Write`, `apply_patch`, `Agent`, `spawn_agent`, `send_message`, `kill 1`, `kill <own harness pid>`, `interrupt_agent` on `w9` not owned, `write_stdin` with `"ls\n"`, an `exec` body with two statements, with a variable, with a template literal.
  - `touches_protected` true for `cat ~/.local/state/hq/pause/x.json` and for an `Edit` whose `file_path` is the limits file.
- [ ] **Step 2:** Run `uv run -q --with pytest pytest tools/test_turn_pause_allowlist.py -q`; expected: FAIL.
- [ ] **Step 3:** Implement `allowlist.py`. The `exec` grammar is a small hand-written matcher over the stripped source (optional `text(await `…`)` wrapper, one `tools.<name>(` call, one object literal of string/number literals), not a JavaScript parser.
- [ ] **Step 4:** Rerun; expected: PASS.
- [ ] **Step 5:** `just test`; commit `feat(turn-pause): enforced closing allowlist and cancellation`.

### Task 6: Hook entry, decisions and notification

**Files:**
- Create: `tools/turn-pause` (executable entry), `tools/turn_pause/hook.py`, `tools/turn_pause/engine.py`, `tools/turn_pause/adapters.py`, `tools/turn_pause/notify.py`
- Test: `tools/test_turn_pause_hook.py`

**Interfaces:**
- Consumes: Tasks 2 to 5; Task 1's facts for which events each harness sends.
- Produces:
  - `tools/turn-pause --harness claude-code|codex <Event>`: reads the native payload on stdin, prints at most one JSON object, exits 0. Events: `UserPromptSubmit`, `PreToolUse`, `PostToolUse`, `PostToolUseFailure`, `Stop`, `SubagentStop`, `SubagentStart`, `PreCompact`, `PostCompact`, `SessionEnd`.
  - `adapters.normalize(harness: str, event: str, payload: dict, now: float, facts: Facts) -> tuple[str, list[Event]]`: the root id (Codex: `session_id`; a worker's events carry `agent_id` and are grouped under `session_id`; Claude Code: `session_id`, child by `agent_id`) and the events in order. A PreToolUse gives one `tool_start`, followed by a `spawn` only for a Claude Code `Agent`/`Task` call or, when Codex's selected source is PreToolUse, a `spawn_agent` call; a Codex SubagentStart gives a `spawn` only when SubagentStart is the selected source (Task 3's rule). `Facts` holds the Task 1 values that select sources and fallbacks (`posttooluse`, `exec_nested_pretooluse`, `stop_carries_agent`, `codex_spawn_source: Literal['subagent_start', 'pretooluse']`), read once through `tools/harness-facts` as a module.
  - `@dataclass(frozen=True) Decision(allow: bool, output: dict | None, paused: str | None)`.
  - `engine.feed(rs: RootState, events: list[Event], decide: Callable[[RootState, Event], Decision]) -> Decision | None` in `tools/turn_pause/engine.py`: the one path that applies events. For a `tool_start`: `counters.attempt`, then `decide`, then, if allowed, `counters.started` and the call's `spawn` events; for every other event, `counters.apply`. The hook calls it with the real decision; the replay (Task 8) with a recording one. No other code calls `attempt`, `started` or `apply`.
  - `hook.decide(harness, event, payload, now, store, limits_path, env) -> dict | None`: the decision JSON (deny or additional context) or nothing.
  - Ownership records kept on `RootState` (Task 5 checks them): every `agent_id` seen under the root is added to `workers`; the session id in the output of an agent's own `exec_command` (read from PostToolUse, where Task 1 shows Codex sends it) is added to `exec_sessions`; `harness_pid` is the nearest ancestor of the hook process whose executable name is `claude` or `codex` (falling back to `node` running either), found once per root from `/proc`. Without PostToolUse, `write_stdin` cancellation stays refused and `kill` remains.
  - `notify.send(title: str, body: str, *, env: Mapping[str, str]) -> str | None`: starts `notify-send` detached with all three standard streams redirected, then writes one relay `notify` request to `$XDG_STATE_HOME/relay/serve.sock` (relay `docs/api.md`, "Local socket protocol" and the notice message shape) with a 300 ms socket timeout; returns the first error or `None`.
- Fixed text, matching lore's shipped rule (lore `5043bc4`). Root refusal: `turn paused: <limit> over its limit (active <h:mm> of <h:mm>, calls <n>/<n>, spawns <n>/<n>, compactions <n>/<n>). Start nothing new and stop the work you already started: interrupt your subagents and the sessions you launched, stop your background calls and processes. Then write the pause report the turn-pause rule describes, park your task --waiting-on user --reason decision, and end your turn. If another agent launched this session, park any claim --waiting-on agent for that agent and return a short status (done, left, running) instead of a pause report. Only bookkeeping, plain reads and stopping your own work are allowed now; hq pause status shows the counts.` Child refusal: `turn paused by your controller's limit (<limit>). Start nothing new and stop the work you already started (your background calls and processes), park any claim --waiting-on agent for your controller, and return a short status (done, left, running). Do not write a pause report.` Warning: `turn-pause: <limit> at <n>% (<used> of <limit>). Finish a coherent step and prepare your report.` Budget confirmation: `turn-pause: budget for this turn: active <h:mm>, <n> calls, <n> spawns, <n> compactions.` Malformed: `turn-pause: the first line looks like a budget but does not parse (<reason>); the default limits apply. Mention it in your next report; do not stop for it.`

- [ ] **Step 1: Write the failing tests**, driving `hook.decide` with recorded payload fixtures under `tools/fixtures/turn-pause/` (one per harness and event, shaped from Task 1's logs) and a `tmp_path` store:
  - a genuine prompt starts a turn; an injected prompt (`<task-notification>`) does not reset counters;
  - the 501st root call is denied with the root text; a child's next call is denied with the child text;
  - while paused, `tasks park …` is allowed and does not consume grace (Review Focus 3); the 26th read is refused; cancellation after grace is still allowed;
  - `continue` as the next genuine prompt ends the pause, resets counters and sets no budget (Review Focus 4);
  - `budget: 12h` adds the confirmation context and raises the limits; a malformed directive adds the malformed context once; a spec body full of `budget:` examples adds nothing;
  - a changed `limits.toml` sha256 mid-turn pauses with `limits-changed` and calls `notify.send` (Review Focus 5);
  - an `Edit` naming the limits file is denied before the pause;
  - a `StateError` produces a deny whose reason names the state file;
  - a refused call (a protected-path `Edit`) followed by a 3 h gap with nothing else running adds no active time;
  - for each Codex spawn source (parametrized over `codex_spawn_source`): one outer `exec` whose loop starts 31 workers gives 1 root call and 31 spawns from the selected source's events, the other source's events for the same workers add none, and the tree's next call is refused; an outer `exec` whose source names `tools.spawn_agent(` in an unexecuted branch gives 0 spawns;
  - the root refusal text contains the stop-owned-work sentence and the launched-session clause; the child refusal text tells it to stop its own work and return a status;
  - `notify.send` failure is stored in `notify_error` and the pause stands;
  - `SessionEnd` removes the root's state.
- [ ] **Step 2:** Run `uv run -q --with pytest pytest tools/test_turn_pause_hook.py -q`; expected: FAIL.
- [ ] **Step 3:** Implement. The entry script inserts `tools/` on `sys.path` as `tools/hq` does and imports nothing outside the standard library. Every event goes through `engine.feed`; the real `decide` checks `crossed`, then the pause, the allowlist and protected paths. A refused call is never in flight and spawns nothing. The entry also takes `--limits <path>` for tests and isolated runs only; the live wiring never passes it, and the wiring files are added to the protected paths.
- [ ] **Step 4:** Rerun; expected: PASS. Then measure latency: 1,000 `PreToolUse` runs of the entry script against a warm state file; record p50 and p99 in the task note; p99 must be under 50 ms.
- [ ] **Step 5:** `just test`; commit `feat(turn-pause): hook entry, decisions and notification`.

### Task 7: `hq pause status` and `hq pause limits`

**Files:**
- Modify: `tools/hq_cli/cli.py`
- Create: `tools/hq_cli/pause.py`
- Test: `tools/test_hq_pause.py`

**Interfaces:**
- Consumes: `Store.read`, `Store.latest_for_cwd` (Task 4); `limits.load` (Task 2).
- Produces: `hq pause status [--session <id>] [--json]` prints one line, `active 1:12/4:00 calls 140/500 spawns 3/30 compactions 0/2 paused:no budget:none notify:ok`, finding the session from `--session`, else `CODEX_THREAD_ID`, else the newest state for the current directory. A Codex worker's thread id is not a root: the lookup first resolves an id through `Store.root_for_agent(harness: str, agent_id: str) -> str | None` (Task 4: the root whose `workers` holds the id) and reads that root's state, so a worker sees its tree's counts. No state is an error naming what it looked for. `hq pause limits [--json]` prints the defaults.

- [ ] **Step 1:** Write failing tests for both commands (text and `--json`), the `CODEX_THREAD_ID` route for a root, the worker route (`CODEX_THREAD_ID` set to a worker id recorded under root `r1` prints `r1`'s counts), the cwd route, and the no-state error, with `XDG_STATE_HOME` under `tmp_path`.
- [ ] **Step 2:** Run `uv run -q --with pytest pytest tools/test_hq_pause.py -q`; expected: FAIL.
- [ ] **Step 3:** Implement `pause.py` and register the `pause` subcommand in `cli.py`.
- [ ] **Step 4:** Rerun; expected: PASS.
- [ ] **Step 5:** `just test`; commit `feat(hq): pause status and limits commands`.

### Task 8: Replay and the fire-rate gate

**Files:**
- Create: `tools/turn-pause-replay`, `tools/turn_pause/replay.py`
- Test: `tools/test_turn_pause_replay.py`

**Interfaces:**
- Consumes: `engine.feed`, `Decision`, `RootState` (Tasks 4 and 6), `events`, `limits`, `prompt.is_genuine`.
- Produces: `tools/turn-pause-replay START END [--limits <path>]` reads the same session trees as lore-911121's `turn-spans-v2.py` attachment (Claude Code roots plus `subagents/`; Codex roots plus children through obs's index, read-only), converts transcript records to `Event`s and feeds each turn through `engine.feed` with a recording `decide` that allows every call and records the first pause point, and prints the turn count, the paused count, pauses a day, and the sun-fbaf80 controller's pause time.
  - Spawns come from evidence a worker started, as in the hook: Claude Code `Agent`/`Task` tool uses; Codex child sessions started in the turn (one per child rollout, linked through obs's index), never `spawn_agent` occurrences in source. The approved 1.67 a day was measured with source occurrences for Codex code-mode spawns, so this replay is also the check of that difference; the Step 5 gate applies to it.

- [ ] **Step 1:** Write failing tests on two small synthetic transcripts in `tools/fixtures/turn-pause/replay/` (one Claude Code tree with a subagent, one Codex tree whose one `exec` loop starts three workers): turn boundaries, in-flight time, spawns counted from the three child rollouts, and the pause point. Add `test_replay_matches_hook_path`: each fixture tree also has the hook payload sequence it would have produced (`hook/*.json`); feeding those through the hook's adapters and `engine.feed`, and feeding the transcript through the replay converter and `engine.feed`, give equal `TurnState` counters (`active` within 1 s, `calls`, `spawns`, `compactions`) and the same pause point.
- [ ] **Step 2:** Run `uv run -q --with pytest pytest tools/test_turn_pause_replay.py -q`; expected: FAIL.
- [ ] **Step 3:** Implement the converter and the report.
- [ ] **Step 4:** Rerun; expected: PASS.
- [ ] **Step 5:** Run `tools/turn-pause-replay 2026-10-02T00:00:00Z 2026-11-01T00:00:00Z`. **Gate:** pauses a day within 0.84 to 2.51 (1.67 ± half), and the sun-fbaf80 controller pauses at about 4 h active. Outside that range, stop and bring the numbers to the user; wire nothing. Attach the output to this child.
- [ ] **Step 6:** `just test`; commit `feat(turn-pause): replay over stored sessions`.

### Task 9: Isolated end-to-end lifecycle

Unit tests and the probe hook do not show that a real session can be paused, clean up, park and resume. This task runs the finished hook (this worktree's `tools/turn-pause`, by explicit path) in isolated, headless sessions of each harness, never in the live homes. It is a live operation: two failed attempts with no established cause stop for the user.

**Files:**
- Create: `tools/turn-pause-lifecycle` (the driver), `tools/fixtures/turn-pause/lifecycle/limits.toml` (`active_seconds = 3600`, `calls = 6`, `spawns = 3`, `compactions = 2`)
- Test: the driver's own run, recorded on this child

**Interfaces:**
- Consumes: Tasks 2 to 7; Task 1's isolation recipe; the entry's `--limits` flag.
- Produces: `tools/turn-pause-lifecycle --harness claude-code|codex` prints one line per stage and `PASS` or the failing stage.

- [ ] **Step 1:** Write the driver. It creates a temporary `HOME`, `XDG_STATE_HOME`, `XDG_CONFIG_HOME` and harness home (Claude Code `--settings`; Codex `CODEX_HOME`) whose hooks run `<worktree>/tools/turn-pause --limits <fixture> --harness <h> <Event>`, and a throwaway tasks project registered under that `XDG_CONFIG_HOME` holding one claimed task. Every subprocess gets an environment built key by key (global Tests rule).
- [ ] **Step 2:** Stages, each asserted from the state file and the transcript: (1) a prompt makes the agent start a long background command and then run calls until the seventh is refused with the root text; (2) the agent spends its 25 grace calls (the driver's prompt asks it to keep reading), and the 26th read is refused; (3) the agent stops its own background process (Claude Code `TaskStop` or `kill`; Codex `kill` and `interrupt_agent` with `{target: …}` on a worker it spawned before the pause) and the process is gone; (4) `tasks park … --waiting-on user` succeeds and the turn ends; (5) a resumed session with the genuine prompt `continue` ends the pause, resets counters and runs one allowed shell command.
- [ ] **Step 3:** Run it for both harnesses; record the output on this child. A failing stage is a defect in Tasks 2 to 7: fix it there (RED test first) and rerun.
- [ ] **Step 4:** `just test`; commit `test(turn-pause): isolated end-to-end lifecycle driver`.

### Task 10: Wiring, follow-ups and integration hand-off

**Files:**
- Modify: `claude/settings.json`, `codex/hooks.json`, `codex/work/hooks.json`
- Create: `tools/test_turn_pause_wiring.py`

**Interfaces:**
- Consumes: the entry script (Task 6) and Task 1's facts (wire `PostToolUse`, `PreCompact`/`PostCompact` and `SubagentStart` only where probed true).

- [ ] **Step 1:** Write a failing wiring test, in the style of `tools/test_claim_guard_wiring.py`: each of the three files has exactly one `tools/turn-pause --harness <h> <Event>` entry (the command written in the same home-relative form as the existing claim-guard entries), with a `timeout` of 5 s, for each of `UserPromptSubmit`, `PreToolUse`, `PostToolUse`, `PostToolUseFailure`, `Stop`, `SubagentStop` and `SessionEnd` that the harness supports, plus `PreCompact`/`PostCompact` and `SubagentStart` where Task 1 probed them true; PreToolUse and PostToolUse match all tools. Entry order is not relied on: matching hooks may run in parallel, and any deny wins.
- [ ] **Step 2:** Run `uv run -q --with pytest pytest tools/test_turn_pause_wiring.py -q`; expected: FAIL.
- [ ] **Step 3:** Add the entries.
- [ ] **Step 4:** Rerun; expected: PASS. `just test`.
- [ ] **Step 5:** File follow-up tasks in hq: agy coverage; tying shell-launched sessions (`claude -p`, `codex exec`, crew dispatches) to their parent; the Claude Code work home's untracked `local/claude/settings.work.json`. Note their ids on hq-9aa713.
- [ ] **Step 6:** Commit `feat(turn-pause): wire the hook into Claude Code and Codex homes`. Do not merge: merging to main activates the hook in every live session. The parent's integration verification (whole-branch review, `just test`) runs next, then the user decides activation; lore-911121's rule activates after this lands.
