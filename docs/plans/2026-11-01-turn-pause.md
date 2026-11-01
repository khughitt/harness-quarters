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
- Produces facts, each per harness `claude-code` and `codex`: `hook-posttooluse` (boolean), `hook-compact-event` (`PreCompact`, `PostCompact`, both, none), `hook-subagent-start` (boolean), `hook-agent-id-on-child-calls` (boolean), `hook-deny-all-tools` (boolean: a deny held for a spawn tool, a wait tool and a shell tool), `hook-prompt-on-wake` (boolean or unknown: UserPromptSubmit fires on a task-notification wake), `codex-exec-nested-pretooluse` (Codex only: PreToolUse fires per nested `tools.*` call), `model-tool-surface` (the list of tool names the runtime offers its model, read from the session's own tool list).

- [ ] **Step 1:** Write the probe hook: read stdin JSON, append it with the hook event name and `time.time()` to `$TURN_PAUSE_PROBE_LOG`; when `tool_name` equals `$TURN_PAUSE_PROBE_DENY`, print the PreToolUse deny JSON from relay `docs/api.md` "Verified native facts".
- [ ] **Step 2:** Run each harness headless in an isolated home per README "Re-probing a fact" (Claude Code with `--settings` naming a temporary settings file; Codex with a temporary `CODEX_HOME` carrying only the probe hooks and the auth the README names), on a prompt that spawns one subagent, waits on it, runs one shell command, and is denied one tool of each kind in turn.
- [ ] **Step 3:** Read the logs and record each fact with `status = "probed"`, `version`, `date`, `evidence = "hq-<child id>"` and a `note` naming the observation; record `unknown` where a run could not show it. Add a note on ops-daf2cd with the nested-PreToolUse observation.
- [ ] **Step 4:** Compare `model-tool-surface` against the spec's cancellation table (Claude Code `TaskStop`/`KillShell`; Codex `interrupt_agent`, `close_agent`, `write_stdin`). A named control the runtime lacks, or a cancellation tool it offers that the table does not name, stops the plan: bring the corrected table to the user before Task 5.
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
  - `@dataclass(frozen=True) Event(t: float, agent: str | None, kind: Literal['prompt', 'tool_start', 'tool_end', 'agent_stop', 'compact', 'tick'], call_id: str | None = None, tool: str | None = None)`; `agent=None` means the root.
  - `events.SPAWN_TOOLS = {'Agent', 'Task', 'spawn_agent'}`; `events.USER_WAIT_TOOLS = {'AskUserQuestion', 'request_user_input', 'request_user_input_async'}`.
  - `@dataclass TurnState(started: float, limits: Limits, limits_sha: str, active: float = 0.0, calls: int = 0, spawns: int = 0, compactions: int = 0, last_t: float | None = None, in_flight: dict[str, str | None] = field(default_factory=dict), warned: set[str] = field(default_factory=set))`, JSON round-trippable through `to_json()`/`from_json()`.
  - `counters.apply(state: TurnState, ev: Event) -> None`: adds the gap since `last_t` (in full while `in_flight` is non-empty, else when under 600 s), then updates: `tool_start` adds to `in_flight` unless the tool is a user-wait tool, counts a root call when `agent is None`, counts a spawn when the tool is a spawn tool; `tool_end` removes the call; `agent_stop` removes that agent's open calls; `compact` counts only for the root. A `prompt` event is never applied (the caller starts a new turn).
  - `counters.crossed(state: TurnState) -> str | None`: the first of `'active'`, `'calls'`, `'spawns'`, `'compactions'` whose count is above its limit.
  - `counters.due_warnings(state: TurnState) -> list[str]`: limits at or above three quarters not yet in `warned` (the caller adds them).

- [ ] **Step 1: Write the failing tests**, building events with a helper `ev(t, kind, agent=None, call=None, tool=None)`:
  - `test_eight_half_hour_calls_count_four_hours`: eight `tool_start`/`tool_end` pairs of 1800 s each, 5 s apart; `state.active == pytest.approx(8 * 1800 + 7 * 5)` and `crossed(state) == 'active'` after one more second of in-flight call.
  - `test_long_wait_on_silent_child_counts`: root `tool_start` of `wait_agent`, `tool_end` 1800 s later, no events between; active grows by 1800.
  - `test_idle_gap_over_ten_minutes_with_nothing_in_flight_counts_nothing`.
  - `test_user_wait_tool_never_in_flight`: `AskUserQuestion` start, end 8 h later; active grows by 0.
  - `test_agent_stop_closes_only_that_agents_calls`: root and child each with an open call; root `agent_stop`; child call still open and a later gap counts in full.
  - `test_children_keep_tree_active_after_root_stop` (Review Focus 1).
  - `test_counts_root_calls_tree_spawns_root_compactions`: child `tool_start` adds no call; child `Agent` start adds a spawn; child `compact` adds nothing.
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
  - `class Store(dir: Path)` with `locked(harness: str, root: str) -> ContextManager[RootState]` (`fcntl.flock` on `<dir>/<harness>-<root>.lock`, load or create, write `<dir>/<harness>-<root>.json` through a temporary file and `os.replace` on exit), `read(harness, root) -> RootState | None` (no lock, for status), `latest_for_cwd(cwd: str) -> tuple[str, str] | None` (harness and root of the newest state whose `cwd` matches), `remove(harness, root)`, `prune(now: float, max_idle: float = 7 * 86400) -> list[str]`.
  - Any unreadable, unparsable or unwritable file raises `StateError` naming the path and the error.

- [ ] **Step 1: Write the failing tests** (every test uses `tmp_path`): round trip of a `RootState` with an open call; `test_parallel_updates_do_not_lose_counts` (Review Focus 2: 8 threads × 50 increments of `turn.calls` under `locked` give 400); corrupt JSON raises `StateError` with the path in its message; a read-only directory raises `StateError`; `prune` removes a state idle 8 days and keeps one idle 6 days; `latest_for_cwd` picks the newest.
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
  - passes: `tasks park lore-1 "next"` → bookkeeping; `tasks show x --no-fetch` → read; `cat a.txt` → read; `kill -TERM <pid of a child the test spawns>` with `harness_pid=os.getpid()` → cancellation; Codex `text(await tools.exec_command({cmd: "tasks note x \"y\""}))` → bookkeeping; `tools.interrupt_agent({id: "w1"})` with `workers={'w1'}` → cancellation; `write_stdin` with `{"session_id": 7, "chars": "\u0003"}` and `exec_sessions={'7'}` → cancellation.
  - refusals: `git diff`, `git status`, `git worktree list`, `tasks show x`, `cat a; rm b`, `cat a | sh`, `cat $(x)`, `cat a > b`, `FOO=1 cat a`, `/bin/cat a`, `tail -f log`, `ls *`, `sed -n 1p a`, `Edit`, `Write`, `apply_patch`, `Agent`, `spawn_agent`, `send_message`, `kill 1`, `kill <own harness pid>`, `interrupt_agent` on `w9` not owned, `write_stdin` with `"ls\n"`, an `exec` body with two statements, with a variable, with a template literal.
  - `touches_protected` true for `cat ~/.local/state/hq/pause/x.json` and for an `Edit` whose `file_path` is the limits file.
- [ ] **Step 2:** Run `uv run -q --with pytest pytest tools/test_turn_pause_allowlist.py -q`; expected: FAIL.
- [ ] **Step 3:** Implement `allowlist.py`. The `exec` grammar is a small hand-written matcher over the stripped source (optional `text(await `…`)` wrapper, one `tools.<name>(` call, one object literal of string/number literals), not a JavaScript parser.
- [ ] **Step 4:** Rerun; expected: PASS.
- [ ] **Step 5:** `just test`; commit `feat(turn-pause): enforced closing allowlist and cancellation`.

### Task 6: Hook entry, decisions and notification

**Files:**
- Create: `tools/turn-pause` (executable entry), `tools/turn_pause/hook.py`, `tools/turn_pause/adapters.py`, `tools/turn_pause/notify.py`
- Test: `tools/test_turn_pause_hook.py`

**Interfaces:**
- Consumes: Tasks 2 to 5; Task 1's facts for which events each harness sends.
- Produces:
  - `tools/turn-pause --harness claude-code|codex <Event>`: reads the native payload on stdin, prints at most one JSON object, exits 0. Events: `UserPromptSubmit`, `PreToolUse`, `PostToolUse`, `PostToolUseFailure`, `Stop`, `SubagentStop`, `SubagentStart`, `PreCompact`, `PostCompact`, `SessionEnd`.
  - `adapters.normalize(harness: str, event: str, payload: dict, now: float) -> tuple[str, Event | None]`: the root id (Codex: `session_id`; a worker's events carry `agent_id` and are grouped under `session_id`; Claude Code: `session_id`, child by `agent_id`) and the event.
  - `hook.decide(harness, event, payload, now, store, limits_path, env) -> dict | None`: the decision JSON (deny or additional context) or nothing.
  - Ownership records kept on `RootState` (Task 5 checks them): every `agent_id` seen under the root is added to `workers`; the session id in the output of an agent's own `exec_command` (read from PostToolUse, where Task 1 shows Codex sends it) is added to `exec_sessions`; `harness_pid` is the nearest ancestor of the hook process whose executable name is `claude` or `codex` (falling back to `node` running either), found once per root from `/proc`. Without PostToolUse, `write_stdin` cancellation stays refused and `kill` remains.
  - `notify.send(title: str, body: str, *, env: Mapping[str, str]) -> str | None`: starts `notify-send` detached with all three standard streams redirected, then writes one relay `notify` request to `$XDG_STATE_HOME/relay/serve.sock` (relay `docs/api.md`, "Local socket protocol" and the notice message shape) with a 300 ms socket timeout; returns the first error or `None`.
- Fixed text. Root refusal: `turn paused: <limit> over its limit (active <h:mm> of <h:mm>, calls <n>/<n>, spawns <n>/<n>, compactions <n>/<n>). Stop work. Write the pause report the turn-pause rule describes, park your task --waiting-on user --reason decision, and end your turn. Only bookkeeping, plain reads and stopping your own work are allowed now; hq pause status shows the counts.` Child refusal: `turn paused by your controller's limit (<limit>). Stop work, park any claim --waiting-on agent for your controller, and return. Do not write a pause report.` Warning: `turn-pause: <limit> at <n>% (<used> of <limit>). Finish a coherent step and prepare your report.` Budget confirmation: `turn-pause: budget for this turn: active <h:mm>, <n> calls, <n> spawns, <n> compactions.` Malformed: `turn-pause: the first line looks like a budget but does not parse (<reason>); the default limits apply. Mention it in your next report; do not stop for it.`

- [ ] **Step 1: Write the failing tests**, driving `hook.decide` with recorded payload fixtures under `tools/fixtures/turn-pause/` (one per harness and event, shaped from Task 1's logs) and a `tmp_path` store:
  - a genuine prompt starts a turn; an injected prompt (`<task-notification>`) does not reset counters;
  - the 501st root call is denied with the root text; a child's next call is denied with the child text;
  - while paused, `tasks park …` is allowed and does not consume grace (Review Focus 3); the 26th read is refused; cancellation after grace is still allowed;
  - `continue` as the next genuine prompt ends the pause, resets counters and sets no budget (Review Focus 4);
  - `budget: 12h` adds the confirmation context and raises the limits; a malformed directive adds the malformed context once; a spec body full of `budget:` examples adds nothing;
  - a changed `limits.toml` sha256 mid-turn pauses with `limits-changed` and calls `notify.send` (Review Focus 5);
  - an `Edit` naming the limits file is denied before the pause;
  - a `StateError` produces a deny whose reason names the state file;
  - `notify.send` failure is stored in `notify_error` and the pause stands;
  - `SessionEnd` removes the root's state.
- [ ] **Step 2:** Run `uv run -q --with pytest pytest tools/test_turn_pause_hook.py -q`; expected: FAIL.
- [ ] **Step 3:** Implement. The entry script inserts `tools/` on `sys.path` as `tools/hq` does and imports nothing outside the standard library. The pause fires inside `PreToolUse`: apply the event, then check `crossed` before deciding.
- [ ] **Step 4:** Rerun; expected: PASS. Then measure latency: 1,000 `PreToolUse` runs of the entry script against a warm state file; record p50 and p99 in the task note; p99 must be under 50 ms.
- [ ] **Step 5:** `just test`; commit `feat(turn-pause): hook entry, decisions and notification`.

### Task 7: `hq pause status` and `hq pause limits`

**Files:**
- Modify: `tools/hq_cli/cli.py`
- Create: `tools/hq_cli/pause.py`
- Test: `tools/test_hq_pause.py`

**Interfaces:**
- Consumes: `Store.read`, `Store.latest_for_cwd` (Task 4); `limits.load` (Task 2).
- Produces: `hq pause status [--session <id>] [--json]` prints one line, `active 1:12/4:00 calls 140/500 spawns 3/30 compactions 0/2 paused:no budget:none notify:ok`, finding the session from `--session`, else `CODEX_THREAD_ID`, else the newest state for the current directory; no state is an error naming what it looked for. `hq pause limits [--json]` prints the defaults.

- [ ] **Step 1:** Write failing tests for both commands (text and `--json`), the `CODEX_THREAD_ID` route, the cwd route, and the no-state error, with `XDG_STATE_HOME` under `tmp_path`.
- [ ] **Step 2:** Run `uv run -q --with pytest pytest tools/test_hq_pause.py -q`; expected: FAIL.
- [ ] **Step 3:** Implement `pause.py` and register the `pause` subcommand in `cli.py`.
- [ ] **Step 4:** Rerun; expected: PASS.
- [ ] **Step 5:** `just test`; commit `feat(hq): pause status and limits commands`.

### Task 8: Replay and the fire-rate gate

**Files:**
- Create: `tools/turn-pause-replay`, `tools/turn_pause/replay.py`
- Test: `tools/test_turn_pause_replay.py`

**Interfaces:**
- Consumes: `counters`, `events`, `limits`, `prompt.is_genuine`.
- Produces: `tools/turn-pause-replay START END [--limits <path>]` reads the same session trees as lore-911121's `turn-spans-v2.py` attachment (Claude Code roots plus `subagents/`; Codex roots plus children through obs's index, read-only), converts transcript records to `Event`s, runs `counters.apply` per turn, and prints the turn count, the paused count, pauses a day, and the sun-fbaf80 controller's pause time.

- [ ] **Step 1:** Write failing tests on two small synthetic transcripts in `tools/fixtures/turn-pause/replay/` (one Claude Code tree with a subagent, one Codex tree with a worker): turn boundaries, in-flight time, and the pause point.
- [ ] **Step 2:** Run `uv run -q --with pytest pytest tools/test_turn_pause_replay.py -q`; expected: FAIL.
- [ ] **Step 3:** Implement the converter and the report.
- [ ] **Step 4:** Rerun; expected: PASS.
- [ ] **Step 5:** Run `tools/turn-pause-replay 2026-10-02T00:00:00Z 2026-11-01T00:00:00Z`. **Gate:** pauses a day within 0.84 to 2.51 (1.67 ± half), and the sun-fbaf80 controller pauses at about 4 h active. Outside that range, stop and bring the numbers to the user; wire nothing. Attach the output to this child.
- [ ] **Step 6:** `just test`; commit `feat(turn-pause): replay over stored sessions`.

### Task 9: Wiring, follow-ups and integration hand-off

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
