# Session evidence reader Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps
> use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `session-logs search|show`, a read-only reader over Claude Code and Codex
session stores that returns typed evidence with explicit coverage. Before that, add the
acceptance fixtures it is judged against.

**Architecture:** The plan has two parts, which run in two repositories.
- **hq (Task 1).** hq adds the SL11 fixtures to its session-log acceptance corpus. That is
  this task's own step, a child of hq-c411df.
- **obs (obs steps 1–12).** obs gains new `session_logs*.py` modules and their tests. They
  import obs's `stores`, `index` and `shell_clear` read-only and modify no existing module.
  One new obs task carries these steps (see "Handoff").
- **What the reader reads.** The stores natively; obs's index for files that are gone,
  replayed copies, children and task commands; task records through `tasks show --json`.

**Tech Stack:** Python 3.11+, standard library only. Tests:
- obs: unittest (`just test-one`, `just test-fast`, `just gate`);
- hq: pytest (`just test`).

**Spec:** `docs/specs/2026-10-23-session-evidence-reader-design.md`, approved at revision 5
(hq `ae0f8ee`). Every section number below (§) is that spec's.

## Global Constraints

- **Read-only.** The reader never writes to a store, to obs's state directory, or to a
  task record (D3, §11.2).
- **New files only.** The obs steps add files and edit only three non-executed ones:
  - `justfile`: the `check` compile list, and one new recipe, `vendor-session-logs`;
  - `.gitignore`: re-includes for the vendored fixtures;
  - the obs task's own record under `tasks/`.

  No existing `.py` module, systemd unit, README section or the shared CLI table changes
  (§11.2).
- **Module names.** Every new module is `session_logs*.py` at obs's root, and every new test
  is `tests/test_session_logs_*.py` (§11.2).
- **Imports, all unchanged:** `stores.store_roots`, `index.open_index_readonly`,
  `index.read_snapshot`, `shell_clear.chain`. `obs._state_dir` is imported only in a test
  (§11.2).
- **Output.**
  - stdout is the `session-logs/1` stream: one JSON object per line, coverage last;
  - `--pretty` renders the same objects;
  - there is no `--json` (D2).
- **Exit codes** (§6.6):
  - 0: the run completed, whatever its outcome;
  - 1: a failure, with `{"error":{"kind","detail"}}` on stderr. Kinds: `tasks_failed`,
    `unknown_format`, `unreadable_input`, `bad_state_dir`;
  - 2: a usage error, printed as one stderr line with the usage line.
- **Search defaults** (§6.1, §6.3):
  - window: the 30 days ending at `--until` or today;
  - `--limit` 50, `--no-limit` removes it;
  - `--text-bytes` 2000, `--raw-bytes` 16384;
  - a pattern search excludes the `metadata` role unless `--role` names it.
- **`show` defaults:** 200 turns in the session view, 500 records in the turn and line views
  (§7.2).
- **Index staleness:** stale when the last complete run ended more than 2 hours before the
  run started (§5.3).
- **Classifier version:** `session-logs-classifier/1`, recorded in coverage `rules` (§4.6).
- **Matching** (§6.2, plus the deferred round-5 minor):
  - a literal compares `casefold()` of the pattern and of the text;
  - `--regex` compiles with `re.IGNORECASE` unless `--case`, and never folds the
    expression;
  - every file in scope is parsed: there is no byte prefilter.
- **Test environments.** Every subprocess test builds its environment key by key: `PATH`,
  `HOME`, `XDG_STATE_HOME`, `XDG_CONFIG_HOME`, plus the obs stub variables named in step 1.
  It never copies `os.environ`.

## Review Focus

These input classes are not exercised by the spec's cases but will bite a person. Each line
names its test and owning step.

1. **Output cut short.** `session-logs search … | head -1` must exit 0 without a
   traceback: on `BrokenPipeError` it stops writing quietly. Test
   `test_closed_stdout_exits_quietly`, obs step 9.
2. **Invalid UTF-8.** A line holding invalid UTF-8 inside a JSON string is decoded with
   `errors="replace"`. It is a `record`, not `malformed`, and its `sha256` covers the raw
   bytes. Test `test_invalid_utf8_line_is_a_record_with_raw_hash`, obs step 2.
3. **A huge line.** A 5 MB tool output yields a record with `truncated: true`, `text`
   cut to `--text-bytes` and `text_bytes` the full length. Test
   `test_huge_output_is_cut_and_measured`, obs step 3.
4. **Regex characters in a literal.** A literal pattern `a.b*` matches only that text,
   never `axbbb`. A `--regex '\S+'` match is unchanged by case-insensitivity. Test
   `test_literal_is_not_a_regex_and_regex_is_not_folded`, obs step 9.
5. **Blank lines and CRLF.** A blank line still counts toward line numbers, and a CRLF line
   parses with its `\r` kept in the hashed bytes. Test
   `test_blank_and_crlf_lines_keep_physical_numbering`, obs step 2.

---

## Part 1: hq

### Task 1: SL11 fixtures for turn-final messages, task evidence, forks and escapes

Spec §14.3 and §14.2 (escaped text). This is hq-c411df's only child. It runs in
`.worktrees/session-evidence-reader`.

**Files:**
- **Create** under `tools/fixtures/session-logs/`. The short names are for the cases
  document:
  - `turns/.claude/projects/-w-gamma/c0000000-0000-4000-8000-000000000021.jsonl`: CM, the
    marker-rule session;
  - `turns/.claude/projects/-w-gamma/c0000000-0000-4000-8000-000000000022.jsonl`: CT1,
    stamped;
  - `turns/.claude/projects/-w-gamma/c0000000-0000-4000-8000-000000000023.jsonl`: CT2,
    mention only;
  - `turns/.claude/projects/-w-gamma/c0000000-0000-4000-8000-000000000024.jsonl`: CT3,
    three failing calls;
  - `turns/.codex/sessions/2026/10/12/rollout-2026-10-12T10-00-00-01900000-0000-7000-8000-0000000000e1.jsonl`:
    XE, the parent;
  - `turns/.codex/sessions/2026/10/12/rollout-2026-10-12T10-05-00-01900000-0000-7000-8000-0000000000f1.jsonl`:
    XF, the child;
  - `turns/.codex/sessions/2026/10/12/rollout-2026-10-12T11-00-00-01900000-0000-7000-8000-0000000000f2.jsonl`:
    XK, a fork with no parent rollout;
  - `captures/tasks-show-zz-000021.json`: the task document;
  - `captures/escaped.jsonl` and `captures/escaped-malformed.jsonl`.
- **Modify** `docs/notes/session-log-acceptance-cases.md`: add the files to the fixture
  table, give `turns/` its own paragraph after `degraded/`, and add an SL11 section and
  rows to the case and distinction tables.
- **Modify** `tools/test_session_log_cases.py`: SL11 self-check tests.

**Interfaces:**
- **Consumes:** nothing. The fixtures are native-format JSONL, as for SL1–SL10.
- **Produces** fixture facts that obs steps 7, 8 and 11 assert. The ids, refs and values
  below are the contract.

**Rules all the fixture records follow:**
- **Shape.** Every record follows the live shapes the spec cites:
  - Claude records carry `message.id`, `message.stop_reason`, `origin.kind` and
    `promptSource`;
  - Codex assistant messages carry `phase`;
  - Codex children carry `source.subagent.thread_spawn.agent_path`.
- **Timestamps** increase within each file, all on 2026-10-12.
- **Key layout.** Each record kind copies its keys from a live record of that kind, keys
  only and never text. That includes the `system` `local_command`, `stop_hook_summary`,
  `turn_duration`, `scheduled_task_fire` and `attachment` records.
- **Turn ends.** Every `turn_duration` is preceded by a `stop_hook_summary` with empty
  `hookErrors`, as in live files.
- **Content.** All text is synthetic, and no private path appears. The existing tests
  `test_fixtures_hold_no_private_paths_or_identifiers` and
  `test_every_fixture_file_is_listed_by_the_cases_document` must still pass.

**CM's turns.** Each turn is listed with its final line or status:
1. A typed prompt. Commentary text, then a tool call and its result. Then message
   `msg_cm1f`, written as a thinking record and a text record (`end_turn`). Then
   `stop_hook_summary` (empty `hookErrors`) and `turn_duration`.
2. A `system` `local_command` record `<command-name>/model</command-name>…`, then a `system`
   `local_command` record `<local-command-stdout>…`, then a typed prompt. One turn,
   triggered by the prompt. It ends `end_turn` with `turn_duration`.
3. A typed prompt, then a tool call. Then an `attachment` `queued_command` with
   `attachment.origin.kind` `human`, then the tool's result, then an `end_turn` final and
   `turn_duration`.
4. A typed prompt. Then:
   - an `end_turn` message;
   - an `isMeta` user record (the Stop feedback);
   - an `attachment` `hook_blocking_error`;
   - a `stop_hook_summary` whose `hookErrors` is non-empty;
   - a tool call and result;
   - an `end_turn` final and `turn_duration`.
5. A typed prompt. Then a `Skill` call, its result, and an `isMeta` user record with
   `sourceToolUseID` equal to that call's id and the turn's `promptId`. Then an `end_turn`
   final and `turn_duration`.
6. After a `system` `scheduled_task_fire`: an `isMeta` user record, then an `end_turn`
   final and `turn_duration`.
7. An `isMeta` user record with `origin.kind` `peer`, then an `end_turn` final and
   `turn_duration`.
8. A typed prompt, a commentary text plus a tool call, its result, then a user record
   `[Request interrupted by user]`.
9. A typed prompt immediately followed by `[Request interrupted by user]`, with no
   response.
10. A typed prompt, then an `AskUserQuestion` call with no result. No `turn_duration`
    follows: the turn waits, and turn 11's prompt comes next.
11. A typed prompt, then one assistant record with model `<synthetic>` and `stop_reason`
    `stop_sequence`, then `turn_duration`.
12. A user record with `origin.kind` `task-notification`, then an `end_turn` final and
    `turn_duration`.
13. A typed prompt, then a tool call with no result, then end of file.

**CT1–CT3** each contain one typed prompt.
- **CT1:** a turn whose span holds the time of the task document's stamped note, at
  2026-10-12T12:00:30Z.
- **CT2:** its prompt mentions `zz-000021`. It calls nothing.
- **CT3:** three Bash calls, each with an `is_error` result:
  - `tasks start zz-000021`;
  - `false && tasks start zz-000021`;
  - `tasks start zz-000021 && false`.

**XE** (parent, root thread):
- **turn `te1`:** a `commentary` message, an `item_completed` `AgentMessage` mirror, a
  `final_answer` message with its mirror, and `task_complete` whose `last_agent_message`
  equals that final;
- **turn `te2`:** a `final_answer` message, its mirror carrying `questions`, and
  `task_complete`;
- **turn `te3`:** a commentary message, then `turn_aborted` with reason `interrupted`;
- **turn `te4`:** a function call and its output, then `task_complete` with
  `last_agent_message` null;
- **turn `te5`:** an assistant message without `phase`, and `task_complete` whose
  `last_agent_message` equals its text;
- **turn `te6`:** a `final_answer` message, then `task_started` `te7` with no
  `task_complete` between;
- **turn `te7`:** `spawn_agent` (call `call_fe_spawn`), the `SubAgentActivity` started item
  binding it to XF, a `response_item` `agent_message` from author `/root/worker` to
  `/root`, then end of file.

**XF** (child): its first `session_meta` has `id` XF, `session_id` XE, and `thread_spawn`
with `parent_thread_id` XE, `agent_path` `/root/worker` and `depth` 1. Then turn `tf1`:
- `agent_message` from author `/root` to `/root/worker`, holding plain text plus one
  encrypted block;
- a `final_answer` message;
- `task_complete`.

**XK** (fork):
- its first `session_meta` has `id` XK;
- its second `session_meta` has `payload.id` `01900000-0000-7000-8000-0000000000f9`, a
  thread with no rollout anywhere in the fixtures;
- then one copied turn: `task_started` `tk-copied`, `turn_context`, a user message, a
  `final_answer` message, and `task_complete`;
- then end of file.

**The task document** `captures/tasks-show-zz-000021.json` has the key structure of a
live `tasks show <id> --json`: `{"task": {...}, "warnings": []}`.
- **How to get the shape.** Capture the key set from a real run of `tasks show
  hq-c411df --json`, then write synthetic values.
- **`task`:** `id` `zz-000021` and `created` `2026-10-12T11:30:00Z`.
- **`notes[0]`:** `at` `2026-10-12T12:00:30Z`, `harness_session`
  `claude-code:c0000000-0000-4000-8000-000000000022`, `harness_session_source` `native`,
  and text `started`.
- **Recording the capture.** The cases document records the `tasks` version whose key set
  was copied.

**`captures/escaped.jsonl`** is one valid Claude `user` record whose
`message.content` is `"needle"`, written with that escape in the file's bytes.

**`captures/escaped-malformed.jsonl`** holds two lines:
1. a valid Claude `user` record with text `hello`;
2. the line `{"type":"user","message":{"content":"needle"` with no closing braces.

- [ ] **Step 1: Write the failing self-check tests**

Add these to `tools/test_session_log_cases.py`, reading bytes with the module's existing
helpers. `TURNS = FIXTURES / "turns"`.

```python
def test_sl11_marker_session_turn_ends_and_markers():
    cm = one(TURNS, ".claude/projects/-w-gamma/c0000000-0000-4000-8000-000000000021.jsonl")
    rs = records(cm)
    assert sum(1 for r in rs if r.get("type") == "system" and r.get("subtype") == "turn_duration") == 9
    blocked = [r for r in rs if r.get("subtype") == "stop_hook_summary" and r.get("hookErrors")]
    assert len(blocked) == 1
    # Stop-hook continuation in live order: end_turn, isMeta feedback, blocking attachment, summary
    i = rs.index(blocked[0])
    assert rs[i - 1]["type"] == "attachment" and rs[i - 1]["attachment"]["type"] == "hook_blocking_error"
    assert rs[i - 2]["type"] == "user" and rs[i - 2]["isMeta"] is True
    assert rs[i - 3]["message"]["stop_reason"] == "end_turn"

def test_sl11_skill_load_record_shares_the_turn_prompt():
    rs = records(one(TURNS, ".claude/projects/-w-gamma/*000021.jsonl"))
    skill = next(r for r in rs if r.get("isMeta") and r.get("sourceToolUseID"))
    call = next(b for r in rs for b in blocks(r) if b.get("type") == "tool_use" and b["id"] == skill["sourceToolUseID"])
    assert call["name"] == "Skill"

def test_sl11_local_commands_and_queued_human_attachment():
    rs = records(one(TURNS, ".claude/projects/-w-gamma/*000021.jsonl"))
    local = [r for r in rs if r.get("type") == "system" and r.get("subtype") == "local_command"]
    assert [r["content"].split(">")[0] for r in local] == ["<command-name", "<local-command-stdout"]  # the live field
    queued = next(r for r in rs if r.get("type") == "attachment" and r["attachment"]["type"] == "queued_command")
    assert queued["attachment"]["origin"]["kind"] == "human"

def test_sl11_codex_statuses_by_closing_event():
    xe = records(codex(TURNS, "01900000-0000-7000-8000-0000000000e1"))
    starts = [r["payload"]["turn_id"] for r in xe if r["type"] == "event_msg" and r["payload"]["type"] == "task_started"]
    ends = {r["payload"]["turn_id"]: r["payload"]["type"] for r in xe
            if r["type"] == "event_msg" and r["payload"]["type"] in ("task_complete", "turn_aborted")}
    assert starts == ["te1", "te2", "te3", "te4", "te5", "te6", "te7"]
    assert ends == {"te1": "task_complete", "te2": "task_complete", "te3": "turn_aborted",
                    "te4": "task_complete", "te5": "task_complete"}

def test_sl11_agent_message_direction():
    xe = records(codex(TURNS, "01900000-0000-7000-8000-0000000000e1"))
    xf = records(codex(TURNS, "01900000-0000-7000-8000-0000000000f1"))
    report = next(r["payload"] for r in xe if r["payload"].get("type") == "agent_message")
    dispatch = next(r["payload"] for r in xf if r["payload"].get("type") == "agent_message")
    assert (report["author"], report["recipient"]) == ("/root/worker", "/root")
    assert (dispatch["author"], dispatch["recipient"]) == ("/root", "/root/worker")
    assert xf[0]["payload"]["source"]["subagent"]["thread_spawn"]["agent_path"] == "/root/worker"

def test_sl11_fork_without_parent_holds_only_copied_history():
    xk = records(codex(TURNS, "01900000-0000-7000-8000-0000000000f2"))
    metas = [r["payload"]["id"] for r in xk if r["type"] == "session_meta"]
    assert metas == ["01900000-0000-7000-8000-0000000000f2", "01900000-0000-7000-8000-0000000000f9"]
    assert not list(FIXTURES.glob("**/rollout-*-01900000-0000-7000-8000-0000000000f9.jsonl"))

def test_sl11_task_document_and_evidence_sessions():
    doc = json.loads((FIXTURES / "captures" / "tasks-show-zz-000021.json").read_text())
    note = doc["task"]["notes"][0]
    assert note["harness_session"] == "claude-code:c0000000-0000-4000-8000-000000000022"
    ct3 = records(one(TURNS, ".claude/projects/-w-gamma/*000024.jsonl"))
    commands = [b["input"]["command"] for r in ct3 for b in blocks(r) if b.get("type") == "tool_use"]
    assert commands == ["tasks start zz-000021", "false && tasks start zz-000021",
                        "tasks start zz-000021 && false"]
    assert all(b.get("is_error") for r in ct3 for b in blocks(r) if b.get("type") == "tool_result")

def test_sl11_escaped_needle_is_absent_from_the_bytes():
    raw = (FIXTURES / "captures" / "escaped.jsonl").read_bytes()
    assert b"needle" not in raw and b"\\u006eeedle" in raw
    assert json.loads(raw)["message"]["content"] == "needle"
    bad = (FIXTURES / "captures" / "escaped-malformed.jsonl").read_bytes().splitlines()
    assert len(bad) == 2 and b"\\u006eeedle" in bad[1]
```

- [ ] **Step 2: Run them and see them fail**

Run: `uv run -q --with pytest pytest tools/test_session_log_cases.py -q -k sl11`
Expected: FAIL (fixture files missing).

- [ ] **Step 3: Write the fixture files** listed above, following the record rules.

- [ ] **Step 4: Update the cases document.** Add:
  - the fixture rows;
  - the `turns/` paragraph;
  - the SL11 section, with question, expected turn statuses, final refs and bases,
    hard negatives, and the escaped-text and chain cases;
  - the SL11 rows in "Required distinctions".

  The expected values are spec §14.3's.

- [ ] **Step 5: Run the self-check and the full suite**

Run: `uv run -q --with pytest pytest tools/test_session_log_cases.py -q`, then `just test`
Expected: all pass, the two existing listing and privacy tests included.

- [ ] **Step 6: Break-check each new assertion.** Change one fact per test in a scratch copy:
  - move the feedback record after the summary;
  - drop the `Skill` id;
  - swap an author;
  - add an `f9` rollout;
  - write `needle` unescaped.

  Each test must fail, and pass again once the change is reverted.

- [ ] **Step 7: Commit**

```bash
git add tools/fixtures/session-logs docs/notes/session-log-acceptance-cases.md tools/test_session_log_cases.py
git commit -m "test(session-logs): SL11 fixtures for turn finals, task evidence, forks and escapes"
```

---

## Part 2: obs

These steps run in an obs worktree under the obs task (see "Handoff"). They are headed
`obs step N:`, so hq's `tasks check` does not expect hq tasks for them. Each step ends with
`just test-one <its test modules>`, then `just gate` before its commit.

### obs step 1: Vendored fixtures and the test harness

**Files:**
- **Create:**
  - `tests/fixtures/session-logs/`, copied from hq main's
    `tools/fixtures/session-logs/` at the merge of hq-c411df;
  - `tests/fixtures/session-logs/SOURCE.json`;
  - `tests/session_logs_harness.py`;
  - `tests/test_session_logs_vendor.py`.
- **Modify:**
  - `justfile`: a new recipe `vendor-session-logs hq`, and the new modules added to the
    `check` compile list as each step creates them;
  - `.gitignore`: add `!/tests/fixtures/session-logs/*/.claude`, `.claude-work`, `.codex`
    and `.codex-work`, the same four lines hq uses.

**Interfaces:**
- **Produces, in `tests/session_logs_harness.py`:**
  - `FIXTURES: Path`;
  - `materialize(name: str, dest: Path) -> Path`, which copies `home`, `degraded` or `turns`
    and chmods CU to 0 for `degraded`, as hq's `materialize()` does;
  - `cli_env(home: Path, state: Path, tasks_fixture: Path | None) -> dict[str, str]`. It
    builds the environment key by key: `PATH` (stub bin first, then `/usr/bin:/bin`),
    `HOME`, `XDG_STATE_HOME`, `XDG_CONFIG_HOME`, `TASK_FIXTURE`, `TASK_LOG`;
  - `build_index(test, home: Path, state: Path, now_ms: int) -> None`. It runs
    `stores.run(state / "obs", env, ["claude-code", "codex"], None, False, now_ms)` with
    `test_names.scratch(test, {"zz": "/w/alpha"})` and `test_stores.INGEST_STUB` on `PATH`,
    and asserts the run was complete;
  - `run_cli(args: list[str], env: dict, cwd: Path) -> tuple[int, list[dict], str]`,
    which runs `python3 <obs>/session_logs.py` as a subprocess in `cwd` and returns the exit
    code, the parsed stdout objects and stderr;
  - `ref_of(short: str) -> str`, which turns acceptance notation (`"CA:4#0"`, `"XC:1"`,
    `"SDK:4"`) into the reader's refs, from one table of every fixture's short name:
    CA, AG, CW, CW2, XP, XC, XA, XW, CD, CU, XD, SDK, CM, CT1–CT3, XE, XF, XK.
- **How `build_index` builds its environment:**
  1. it calls `test_names.scratch(test, {"zz": "/w/alpha"})`;
  2. it sets `env["HOME"]` to the fixture home, so `store_roots` reads that home;
  3. it writes `INGEST_STUB` to the scratch root's `bin/tasks`, first on `PATH`;
  4. it sets `TASK_FIXTURE` (`{"list": [], "show": {...}}`) and `TASK_LOG`.

  `scratch` keeps the inherited `PATH` value, the only inherited key.
- **`SOURCE.json`:** `{"hq_commit": "<sha>", "files": {"<relative path>": "<sha256>"}}`.

**Deviation from spec §14.5, ruled here.** The spec names the real `tasks` CLI over a
scratch registry. obs's tests already run `stores.run` with the established fakes
(`scratch` and `INGEST_STUB`), and those make the run complete.
- **What answers `tasks show`.** `INGEST_STUB` answers it from `TASK_FIXTURE`, whose `show`
  map holds the captured document's `task` object. That gives the reader and the index the
  same record, as §14.5 requires.
- **Why the field path is still live.** It comes from the live capture (Task 1) and from
  the live check in obs step 12.
- **Why:** it reuses the harness obs already trusts.
- **Cost if wrong:** a difference between the stub and the real CLI. obs step 12's live
  `--task` check exists to catch it.

- [ ] **Step 1: Write the failing test** `tests/test_session_logs_vendor.py`:
  - `test_vendored_files_match_source`: every file under the fixture directory (except
    `SOURCE.json`) appears in `SOURCE.json["files"]` with its sha256, and every listed file
    exists;
  - `test_materialize_makes_cu_unreadable`, skipped when run as root: after `materialize`
    of `degraded`, opening CU raises `PermissionError`.
- [ ] **Step 2:** `just test-one test_session_logs_vendor`. Expected: FAIL (no fixtures).
- [ ] **Step 3: Write the `vendor-session-logs hq` recipe.** Given an hq checkout path, it:
  1. refuses a dirty hq tree;
  2. copies `tools/fixtures/session-logs/` over the vendored directory;
  3. writes `SOURCE.json` with `git -C {{hq}} rev-parse HEAD` and per-file sha256.

  Run it against hq main. Add the `.gitignore` lines.
- [ ] **Step 4:** `just test-one test_session_logs_vendor`. Expected: PASS. Confirm that
  `git status --porcelain --ignored tests/fixtures` shows no ignored fixture files.
- [ ] **Step 5:** `just gate`, then commit:
  `test(session-logs): vendor hq's session-log fixtures and a test harness`.

### obs step 2: Lines, refs, format detection and lenient unescaping

Spec §4.1, §4.5, §6.7.

**Files:**
- **Create:** `session_logs_lines.py`, `tests/test_session_logs_lines.py`.

**Interfaces:**
- **Produces:**
  - `@dataclass(frozen=True) class Place: harness: str; home: str; profile: str | None;
    store: str; relpath: str; path: Path`;
  - `ref(place: Place, line: int | None = None, block: int | None = None) -> str`. It
    gives `<home>:<relpath>#L<line>[#<block>]`, and `file:<relpath>#L…` for
    `store == "explicit"`;
  - `@dataclass(frozen=True) class Line: number: int; raw: bytes; complete: bool`;
  - `lines(path: Path, size: int) -> Iterator[Line]`. It reads up to `size` bytes and
    yields every physical line, blank ones included. `complete` is False only for a last
    line without a newline;
  - `sha256(line: Line) -> str`, the hash of `raw`;
  - `decode(line: Line) -> dict | None`, which applies UTF-8 `errors="replace"` and then
    `json.loads`. It returns None unless the result is an object;
  - `unescape_lenient(text: str) -> str` (§4.5);
  - `detect_format(path: Path, size: int) -> str`, giving `"claude"`, `"codex"` or `"sdk"`
    and raising `UnknownFormat`;
  - `class UnknownFormat(Exception)`.

- [ ] **Step 1: Write the failing tests:**
  - `test_blank_and_crlf_lines_keep_physical_numbering`: bytes `b'{"a":1}\r\n\n{"b":2}\n'`
    give numbers `[1, 2, 3]`; `decode` of line 1 is `{"a": 1}`; `sha256` of line 1 covers
    `b'{"a":1}\r\n'`.
  - `test_partial_last_line_is_incomplete`: `b'{"a":1}\n{"b"'` gives line 2 with
    `complete` False.
  - `test_size_bound_ignores_later_appends`: `lines(p, 8)` on `b'{"a":1}\n{"b":2}\n'`
    yields one line.
  - `test_invalid_utf8_line_is_a_record_with_raw_hash`: `b'{"t":"a\xffb"}\n'` decodes to
    `{"t": "a�b"}`, and `sha256` covers the original bytes.
  - `test_unescape_lenient_undoes_json_escapes`: `unescape_lenient('{"c":"\\u006eeedle\\/x\\"')`
    contains `needle/x"`.
  - `test_ref_shapes`:
    `ref(Place("claude-code","claude-work","work","live","projects/-w-beta/x.jsonl",p), 3, 0)
    == "claude-work:projects/-w-beta/x.jsonl#L3#0"`, and an explicit place gives
    `"file:cap.jsonl#L4"`.
  - `test_detect_format`:
    - the vendored SDK capture gives `"sdk"`, though its first record is `system`/`init`;
    - XP gives `"codex"`;
    - CA gives `"claude"`;
    - a file starting with a `fork-context-ref` record and no `sessionId` gives
      `"claude"`;
    - `b'{"x":1}\n'` raises `UnknownFormat`.
- [ ] **Step 2:** `just test-one test_session_logs_lines`. Expected: FAIL (no module).
- [ ] **Step 3: Implement** `session_logs_lines.py`, using the signatures above and the
  signature rules of §6.7.
- [ ] **Step 4:** `just test-one test_session_logs_lines`. Expected: PASS.
- [ ] **Step 5:** Add the module to `check`, run `just gate`, then commit:
  `feat(session-logs): physical lines, refs and format detection`.

### obs step 3: The Claude classifier

Spec §8.1, §8.3 (`request_blob` and the Claude fork copy), §4.2, §10.3 (Claude bases).

**Files:**
- **Create:** `session_logs_records.py` (shared helpers plus Claude),
  `tests/test_session_logs_claude.py`.

**Interfaces:**
- **Consumes:** obs step 2's `Place`, `Line`, `lines`, `decode`, `sha256`, `ref`.
- **Produces:**
  - `CLASSIFIER = "session-logs-classifier/1"`;
  - `@dataclass class FileRead: place: Place; records: list[dict]; unparsed: list[dict];
    header: dict`.
    - `records` are §4.2 objects, without `turn`, which obs step 7 sets.
    - `unparsed` are §4.5 objects that keep their raw text in a private key `_raw`.
    - `header` keys: `session`, `agent`, `identity_basis`, `cwd`, `entrypoint`,
      `first_at`, `last_at`, `lines`, `subagent: bool`, `forked: bool`, `uuids:
      dict[str, int]` (uuid → line), `continued_in: str | None`, `markers: bool` (any
      `turn_duration`).
  - `claude_read(place: Place, size: int) -> FileRead`;
  - `pair_calls(records: list[dict]) -> None`. It sets `call.peer` on calls and results by
    id, and marks a call with no result `status: "pending"`. Copies are never paired with
    originals.
  - `cut(text: str, limit: int) -> tuple[str, int, bool]`, returning the text cut to
    `limit` UTF-8 bytes, the full byte length, and whether it was cut.

- [ ] **Step 1: Write the failing tests.** Each reads the vendored fixtures unless it says
  otherwise. `CA = home/.claude/projects/-w-alpha/c0000000-0000-4000-8000-00000000000a.jsonl`.
  - `test_ca_roles_by_origin`:
    - the human records are refs `#L1` and `#L15`, with `role_basis == "origin"`;
    - `#L2` is `injected` (isMeta);
    - `#L14` is `injected` with `origin_kind == "task-notification"`;
    - `#L13` is `metadata`;
    - `#L16` is `unknown` with `kind == "future-record-kind"`.
  - `test_ca_calls_pair_by_id_across_reversed_results`: `pair_calls` gives exactly these
    pairs, with CA:7's result `is_error`:

    ```python
    {"CA:4#0": "CA:7#0", "CA:5#0": "CA:6#0", "CA:8#0": "CA:9#0", "CA:11#0": "CA:12#0", "CA:17#0": "CA:18#0"}
    ```
  - `test_ca_request_blob_blocks_are_copies`: the records at line 10 all have
    `copy == "request_blob"`, and blocks `#1` and `#2` are `tool_call` with ids
    `toolu_fx_park1` and `toolu_fx_status`.
  - `test_ca_message_and_runtime_model`: lines 3–5 share `message_id == "msg_fx_m1"`, and
    every assistant record has `model == {"value": "claude-model-a", "basis": "runtime"}`.
  - `test_subagent_prompt_is_dispatch_and_identity_is_agent`: AG's line 1 is `dispatch`;
    its header has `session == "agent-a0000000000000b01"`, `subagent` True, and the parent
    `c0000000-0000-4000-8000-00000000000a` held as `header["parent"]`.
  - `test_local_command_shapes_in_both_record_types`, on inline records built in the test:
    - `user` and `system` `local_command` records beginning `<command-name>` are `human`
      with `role_basis == "local_command"`;
    - ones beginning `<local-command-stdout>` or `<bash-stdout>` are `injected` with the
      same basis.
  - `test_queued_attachment_takes_its_origin_kind`: inline `queued_command` attachments
    give `human` with `queued: True` for `origin.kind` `human`, and `injected` for
    `task-notification`.
  - `test_synthetic_message_is_marked_and_not_runtime`: an inline assistant record with
    model `<synthetic>` has `synthetic: True` and no `model` field.
  - `test_fork_context_ref_marks_first_response_as_fork_history`: in an inline file
    beginning with `fork-context-ref`, the first assistant record's objects have
    `copy == "fork_history"`.
  - `test_huge_output_is_cut_and_measured`: a 5 MB `tool_result` with `cut(…, 2000)` has
    `truncated` True, `len(text.encode()) <= 2000`, and `text_bytes == 5_000_000`.
  - `test_malformed_and_truncated_lines_are_unparsed`: the degraded CD:2 is `unparsed`
    with `reason "malformed"`. A file ending in a partial line gives `reason "truncated"`.
- [ ] **Step 2:** `just test-one test_session_logs_claude`. Expected: FAIL.
- [ ] **Step 3: Implement** `claude_read`, `pair_calls` and `cut`, following §8.1's table
  row by row and §10.3's Claude bases.
  - **Subagent files:** a path under `subagents/`, or a file whose every timed record is
    `isSidechain`.
- [ ] **Step 4:** `just test-one test_session_logs_claude`. Expected: PASS.
- [ ] **Step 5:** `just gate`, then commit: `feat(session-logs): Claude record classifier`.

### obs step 4: The Codex and SDK classifiers

Spec §8.2, §8.3 (`event_mirror`, `compaction_history`, Codex `fork_history`), §10.3
(Codex bases), §6.7 (SDK).

**Files:**
- **Modify:** `session_logs_records.py`, the new file from obs step 3.
- **Create:** `tests/test_session_logs_codex.py`.

**Interfaces:**
- **Consumes:** obs step 3's `FileRead`, `pair_calls` and `cut`.
- **Produces:**
  - `codex_read(place: Place, size: int, inherited_turn_ids: Callable[[str], set[str] |
    None]) -> FileRead`. Its `header` adds `parent`, `agent_path`, `depth`,
    `inherited_id`, `child: bool`, plus `turn_ids` in order;
  - `sdk_read(place: Place, size: int) -> FileRead`. Records carry
    `dispatch: {"kind": "sdk_dispatch", "call": <id>}`.

- [ ] **Step 1: Write the failing tests:**
  - `test_xc_identity_and_models`:
    - XC's header has `session` equal to XC's id, never XP's, and `parent` equal to XP's
      id;
    - XC:3's record has `model == {"value": "codex-model-b", "basis": "runtime"}`;
    - XC:1's creation value appears with `basis == "creation"`.
  - `test_xc_dispatch_is_encrypted_and_by_agent_path`: XC:4 is `dispatch` with
    `role_basis == "agent_path"`, and its encrypted block has `encrypted` True and no
    `text`.
  - `test_xp_injected_prefixes_and_human`: XP:4 and XP:5 are `injected`; XP:6 is `human`.
  - `test_root_thread_agent_message_is_injected`: XE's `agent_message` from
    `/root/worker` is `injected`; XF's from `/root` is `dispatch`.
  - `test_event_mirrors_and_command_executions`, on inline records:
    - `item_completed` `AgentMessage` and `UserMessage` items, and older `event_msg`
      `user_message` and `agent_message`, are `metadata` with `copy == "event_mirror"`;
    - a `CommandExecution` item is `metadata` with `execution == {"command": …,
      "exit_code": …, "cwd": …, "status": …}`.
  - `test_compaction_history_is_copied`: an inline `compacted` record with two
    `replacement_history` messages yields two objects with `copy == "compaction_history"`.
  - `test_fork_history_ends_at_first_unknown_turn`: an inline fork with second
    `session_meta` id `P` and turns `t1`, `t2`, then `own1`, with
    `inherited_turn_ids("P") == {"t1", "t2"}`:
    - records through `t2`'s end are `fork_history`;
    - `own1`'s records carry no `copy`.
  - `test_fork_without_parent_is_ambiguous_to_the_end`: XK, with `inherited_turn_ids`
    returning None, gives every object after line 1 `copy == "ambiguous"`.
  - `test_child_without_agent_path_leaves_agent_messages_unknown`: an inline child thread
    with no `agent_path` gives its `agent_message` the role `unknown`.
  - `test_sdk_dispatch_links`: on the SDK capture, SDK:4 and SDK:5 carry `sdk_dispatch` to
    `toolu_fx_dA` and `toolu_fx_dB`, and SDK:6#0 is paired with SDK:5 with `is_error`.
- [ ] **Step 2:** `just test-one test_session_logs_codex`. Expected: FAIL.
- [ ] **Step 3: Implement** `codex_read` and `sdk_read` per §8.2's table, the
  agent-path rule and the child rule.
  - Ignore copies when collecting `turn_ids`.
- [ ] **Step 4:** `just test-one test_session_logs_codex`. Expected: PASS.
- [ ] **Step 5:** `just gate`, then commit: `feat(session-logs): Codex and SDK record
  classifiers`.

### obs step 5: Location

Spec §5.1–§5.5.

**Files:**
- **Create:** `session_logs_place.py`, `tests/test_session_logs_place.py`.

**Interfaces:**
- **Consumes:** obs step 2's `Place`; `stores.store_roots`; `index.open_index_readonly`;
  `index.read_snapshot`.
- **Produces:**
  - `@dataclass(frozen=True) class Root: harness: str; home: str; profile: str; store: str;
    path: Path`;
  - `roots(env: dict) -> list[Root]`, which follows §5.1's naming and profile rule;
  - `class StateDirError(Exception)`;
  - `state_dir(given: str | None, env: dict) -> Path`;
  - `@dataclass class IndexFacts`, with fields:
    - `state: str`, `reason: str`, `schema: int | None`, `last_complete_run_ms: int | None`;
    - `coverage_start: dict[Path, int | None]`, keyed by root path;
    - `files: dict[str, dict]` (path → file row) and `sessions: list[dict]`;
    - `task_rows: dict[str, list[dict]]`, keyed by task id;
  - `read_index(obs_state: Path, now_ms: int, roots: list[Root], task_ids: list[str]) ->
    IndexFacts`, read in one `read_snapshot`. `obs_state` is the directory that holds
    `index.sqlite`;
  - `@dataclass class Listing: roots: list[dict]; files: list[Path]; aliases: list[Path];
    skipped_by_mtime: int`;
  - `list_files(roots: list[Root], since_ms: int | None) -> Listing`;
  - `place_of(path: Path, roots: list[Root], store: str | None = None) -> Place`;
  - `@dataclass class Candidate: place: Place; relation: str; identity: str;
    identity_basis: str; state: str; missing_since_ms: int | None; read_path: Path | None;
    file_id: int | None`;
  - `candidates(session_id: str, roots: list[Root], facts: IndexFacts) -> list[Candidate]`;
  - `open_listed(path: Path, roots: list[Root]) -> tuple[Path, int] | None`. It returns the
    path read and the size at open. A vanished file is sought once in its home's other
    Codex root; None means vanished;
  - `changed(path: Path, row: dict) -> bool`, per §5.5.

- [ ] **Step 1: Write the failing tests.** Fixture homes come from `materialize`; indexes
  from `build_index`.
  - `test_roots_names_and_profiles`: on `home`, `[(r.home, r.store, r.profile) for r in
    roots(env)]` equals:

    ```python
    [("claude","live","personal"),("claude-work","live","work"),("codex","live","personal"),
     ("codex","archived","personal"),("codex-work","live","work"),("codex-work","archived","work")]
    ```

    `list_files` reports the last of these as `absent`.
  - `test_state_dir_agrees_with_obs`: for `--state-dir`, an absolute `XDG_STATE_HOME`, and
    neither, `state_dir` equals `obs._state_dir` (imported in this test only). A relative
    `XDG_STATE_HOME` raises `StateDirError`.
  - `test_index_absent_stale_schema_and_coverage`:
    - no state directory gives `absent`;
    - after `build_index`, the state is `used`;
    - with `index_runs.finished_ms` rewritten 3 hours back in the test-owned copy, it is
      `stale`;
    - with `PRAGMA user_version` set to 14, it is `unsupported_schema`;
    - `coverage_start` of each root equals the minimum `indexed_at_ms` of its rows.
  - `test_candidates_claude_session_and_children` (O10, Claude): `candidates(CA)` gives CA
    as `own` and AG as `child`. `candidates("agent-a0000000000000b01")` and
    `candidates("a0000000000000b01")` both give AG as `own`.
  - `test_candidates_codex_child_through_index`: with an index, `candidates(XP)` lists XC
    as `child`. Without one, it lists none.
  - `test_missing_with_alternate` (M01):
    1. copy XP's rollout into `.codex/archived_sessions/`;
    2. build the index;
    3. delete the live copy.

    Two `own` candidates result: one `missing`, one `readable`.
  - `test_replayed_copy_and_unreadable_copy`:
    1. index;
    2. copy CW to `archive/claude-work/…`;
    3. delete it;
    4. run `stores.run` with `replay=[(archive, root)]`.

    The candidate is read from `read_path`, with `store "replayed"`. After a `chmod 0` of
    the copy it is `missing`, and its `read_path` is kept.
  - `test_symlink_is_alias`: a symlink to CW under a project directory is listed in
    `aliases`, never in `files`, and its candidate relation is `alias`.
  - `test_vanished_file_is_found_in_archive_or_reported`:
    - XA moved from `archived_sessions/` to `sessions/` between `list_files` and
      `open_listed` is found;
    - a deleted file gives None.
  - `test_changed_prefix`: after the index, rewriting CW:1 in place makes `changed` True.
- [ ] **Step 2:** `just test-one test_session_logs_place`. Expected: FAIL.
- [ ] **Step 3: Implement** the module.
  - `read_index` checks for the file before calling `open_index_readonly`. It maps
    `ValueError` to `unsupported_schema` and `sqlite3.Error` to `unreadable`.
  - It reads `files`, `sessions` and `index_runs`, and the `task_commands` rows for the
    task ids, all inside one `read_snapshot`.
- [ ] **Step 4:** `just test-one test_session_logs_place`. Expected: PASS.
- [ ] **Step 5:** `just gate`, then commit: `feat(session-logs): store location, candidates
  and index facts`.

### obs step 6: Cross-file copies, links and session objects

Spec §8.3 (`resume_history`, `duplicate_file`, `ambiguous`), §10.1, §10.3, §4.3.

**Files:**
- **Create:** `session_logs_sessions.py`, `tests/test_session_logs_sessions.py`.

**Interfaces:**
- **Consumes:** `FileRead` (obs steps 3 and 4), `Candidate` and `IndexFacts` (obs step 5).
- **Produces:**
  - `mark_resume_copies(reads: list[FileRead]) -> None`. It works on Claude reads grouped by
    project directory. `continued-in` is used first, then the timing rule, then
    `ambiguous`. It also adds `continued_in` links.
  - `mark_duplicate_files(reads: list[FileRead]) -> None`. The earlier-root file is the
    original; differing files get `divergent`.
  - `native_links(read: FileRead) -> list[dict]`, giving `{kind, target, basis, ref}` per
    §10.1. Codex dispatch bindings come from `SubAgentActivity`.
  - `session_object(read: FileRead | None, candidate: Candidate, facts: IndexFacts) ->
    dict`, the §4.3 object. It merges index links, keeps both when they disagree, and
    lists every model with its basis.

- [ ] **Step 1: Write the failing tests:**
  - `test_resume_copy_by_timing`: on CW and CW2, CW2's lines 1–3 have
    `copy == "resume_history"` with `original` CW's matching refs; CW's lines carry no
    `copy`.
  - `test_resume_copy_by_continued_in_wins`: an inline pair where timing would choose the
    other file but a `continued-in` record names the second file marks the second file's
    shared records as copies, and adds a `continued_in` link.
  - `test_resume_tie_is_ambiguous`: two inline files with interleaved later activity both
    get `copy == "ambiguous"` on their shared records, and nothing collapses.
  - `test_duplicate_file_collapses_into_earlier_root`: XP copied into `archived_sessions/`
    gives the archived copy's identical lines `copy == "duplicate_file"`. An edit to the
    copy sets `divergent` on both.
  - `test_links_and_non_links`:
    - CA's session object has `parent_to_child` to AG, with basis `native_metadata`, from
      `CA:12`;
    - XC's has `child_to_parent` to XP, from `XC:1`;
    - XP's has a dispatch binding from `XP:7` to XC, via `XP:8`;
    - no link comes from `parentUuid`, `XC:2`'s `parent_turn_id`, or XC's `session_id`.
  - `test_session_models_by_basis`: AG's session object lists `claude-model-b` as
    `runtime`. CA's lists `sonnet` as `requested` (CA:11#0) and `claude-model-b` as
    `resolved` (CA:12).
- [ ] **Step 2:** `just test-one test_session_logs_sessions`. Expected: FAIL.
- [ ] **Step 3: Implement** the module.
- [ ] **Step 4:** `just test-one test_session_logs_sessions`. Expected: PASS.
- [ ] **Step 5:** `just gate`, then commit: `feat(session-logs): resume and duplicate
  copies, links and session objects`.

### obs step 7: Turns, finals and statuses

Spec §9.1–§9.3, §4.4.

**Files:**
- **Create:** `session_logs_turns.py`, `tests/test_session_logs_turns.py`.

**Interfaces:**
- **Consumes:** `FileRead`, with copies already marked by obs steps 4 and 6.
- **Produces:** `turns(read: FileRead) -> list[dict]`, the §4.4 objects. It sets each
  record's `turn`.
  - **Rule.** Claude files use the marker rule when `header["markers"]`, else the derived
    rule. `status_basis` names the rule applied.
  - **Ambiguous turns.** A turn built from `ambiguous` records carries `copy: "ambiguous"`
    and never `final`.

- [ ] **Step 1: Write the failing tests.** These are the expected results for CM, XE, XF
  and XK as Task 1 defines them.
  - `test_cm_marker_rule_statuses`: the statuses in order are:

    ```python
    ["completed","completed","completed","completed","completed","completed","completed",
     "interrupted","interrupted","waiting","no_final","completed","incomplete"]
    ```
  - `test_cm_finals_and_triggers`:
    - turn 1's final is message `msg_cm1f`'s text block, with basis `stop_reason`, while
      its earlier text is in `commentary`;
    - turn 2's trigger is the typed prompt, not a local-command record;
    - turn 3's `inputs` include the queued attachment, and its trigger is the opening
      prompt;
    - turn 4 is one turn, whose first `end_turn` text is commentary;
    - turn 5 keeps its human trigger and final;
    - turns 6, 7 and 12 have `trigger.role == "injected"`;
    - turn 9 has no response and no final;
    - every non-`completed` turn has `last_assistant` and no `final`.
  - `test_ca_derived_rule`: CA yields two turns:
    1. inputs `[CA:1]`, `no_final`;
    2. inputs `[CA:14, CA:15]`, trigger `CA:15`, `completed`, final `CA:19#0`.
  - `test_xe_codex_statuses_need_closing_events`: the XE statuses are
    `["completed","completed","interrupted","no_final","completed","incomplete","incomplete"]`.
    In particular:
    - `te2` has `asks_user` True;
    - `te5`'s final basis is `last_agent_message`;
    - `te6` has no `final` and its `final_answer` as `last_assistant`.
  - `test_xf_dispatch_trigger_and_final`: XF's `tf1` has `trigger.role == "dispatch"` and
    a `final` with basis `phase`.
  - `test_xk_ambiguous_turn_has_no_final`: XK's turn has `copy == "ambiguous"`, no
    `final`, and the copied `final_answer` as `last_assistant`.
  - `test_ca_models_per_turn`: every CA turn has `models == ["claude-model-a"]`.
- [ ] **Step 2:** `just test-one test_session_logs_turns`. Expected: FAIL.
- [ ] **Step 3: Implement** `turns`. Order the status checks exactly as §9.3's table, with
  the Codex closing-event requirement.
- [ ] **Step 4:** `just test-one test_session_logs_turns`. Expected: PASS.
- [ ] **Step 5:** `just gate`, then commit: `feat(session-logs): turns, final messages and
  statuses`.

### obs step 8: Task evidence

Spec §9.4.

**Files:**
- **Create:** `session_logs_tasks.py`, `tests/test_session_logs_tasks.py`.

**Interfaces:**
- **Consumes:** obs step 5's `IndexFacts.task_rows`; the paired records from obs steps 3
  and 4; `shell_clear.chain`.
- **Produces:**
  - `class TasksFailed(Exception)`;
  - `read_task(task_id: str, env: dict) -> dict`, which runs `tasks show <id> --json` and
    returns its `task`. Anything else raises `TasksFailed`;
  - `earliest_ms(task: dict) -> int`, the smaller of `created` and the first note's `at`;
  - `evidence(task: dict, rows: list[dict], calls: dict[str, tuple[dict, dict | None]]) ->
    list[dict]`, giving `{kind, session, ref, at_ms, basis}`. The kinds are
    `provenance_stamp`, `successful_task_command`, `unsuccessful_task_command` and
    `task_command`;
  - `single_tasks_segment(command: str) -> bool`, which is
    `(c := shell_clear.chain(command)) is not None and len(c["segments"]) == 1 and
    c["segments"][0][:1] == ["tasks"]`.

- [ ] **Step 1: Write the failing tests:**
  - `test_stamp_from_notes_field_path`: the vendored document's note gives
    `provenance_stamp` for session `c0000000-0000-4000-8000-000000000022` with
    `at_ms` 2026-10-12T12:00:30Z.
  - `test_ca_park_success_and_hook_denial` (SL2): with the index built over `home`:
    - CA:8 is `successful_task_command`, from an index `ok` row;
    - CA:4 is `unsuccessful_task_command`, with basis `result_is_error`.
  - `test_ct3_chain_errors_stay_uncertain`, with the index built over `turns`:
    - `tasks start zz-000021` is `unsuccessful_task_command`;
    - both chain forms are `task_command`.
  - `test_indexed_failed_on_a_chain_is_uncertain`: an inline row with `status "failed"`
    whose call command is `tasks start zz-000001 && false` gives `task_command`.
  - `test_read_task_failure_raises`: a stub `tasks` exiting 1 raises `TasksFailed`.
  - `test_earliest_ms`: the vendored document gives 2026-10-12T11:30:00Z.
- [ ] **Step 2:** `just test-one test_session_logs_tasks`. Expected: FAIL.
- [ ] **Step 3: Implement** the module.
- [ ] **Step 4:** `just test-one test_session_logs_tasks`. Expected: PASS.
- [ ] **Step 5:** `just gate`, then commit: `feat(session-logs): task evidence tiers`.

### obs step 9: `search`, coverage, outcomes and the CLI

Spec §6, §4.6, §2 D2.

**Files:**
- **Create:**
  - `session_logs_query.py`, with selection, matching, coverage and outcomes;
  - `session_logs.py`, the CLI entry: argparse, the stream writer, `--pretty`, exit codes;
  - `tests/test_session_logs_search.py`.

**Interfaces:**
- **Consumes:** everything above.
- **Produces:**
  - `@dataclass class Query`, with one field per §6.1 option, plus `mode`
    (`"records" | "sessions" | "final"`), `limit: int | None`, `text_bytes`, `raw`,
    `raw_bytes`, `sort`, `reverse`;
  - `matcher(pattern: str | None, regex: bool, case: bool) -> Callable[[str], bool]`;
  - `search(q: Query, env: dict, now_ms: int, between: Callable[[], None] | None = None) ->
    Iterator[dict]`. It yields objects lazily, with coverage last. `between` is the test
    hook that runs between listing and reading (§14.2);
  - `outcome(cov: dict, scope: str) -> tuple[str, str]`, which applies §6.5;
  - `main(argv: list[str], env: dict) -> int`, in `session_logs.py`.

- [ ] **Step 1: Write the failing tests:**
  - `test_literal_is_not_a_regex_and_regex_is_not_folded`:
    - `matcher("a.b*", False, False)` matches `"x A.B* y"` and not `"axbbb"`;
    - `matcher(r"\S+", True, False)` matches `"x"` and not `"   "`;
    - `matcher("NEEDLE", False, False)` matches `"needle"`, and with `case=True` it does
      not.
  - `test_default_window_and_until`:
    - with `now` 2026-10-23, the default window is 2026-09-23..2026-10-23;
    - with `--until 2026-09-01` alone it is 2026-08-02..2026-09-01;
    - `--all-time` together with `--since` is a usage error, exit 2.
  - `test_pattern_search_excludes_metadata_by_default`: on XE, `search te1` emits no
    `metadata` object until `--role metadata` is given.
  - `test_session_scope_is_own_files_only` (SL1): `search --session CA --no-limit --all-time`
    returns five `tool_call` objects that are not copies, and none from AG.
  - `test_escaped_needle_found_and_unparsed_escape_unknown`:
    - `search needle --file captures/escaped.jsonl` gives outcome `found`;
    - on `escaped-malformed.jsonl` it gives zero parsed matches, one `unparsed` object
      with `raw_match` True, and outcome `unknown`.
  - `test_degraded_home_is_unknown` (SL10A): the coverage on `degraded` is:
    - three roots `searched` and three `absent`;
    - CU unreadable;
    - CD:2 malformed and XD:3 truncated, both with `raw_match`;
    - index `absent`;
    - outcome `unknown`.
  - `test_not_found_inside_coverage` (§14.2):
    1. build the index over `home`;
    2. rewrite every `files.indexed_at_ms` in the test-owned index to 2026-09-01;
    3. run `search zzz-absent --home claude-work --since 2026-10-01`.

    The outcome is `not_found`. The same with `--all-time` is `unknown`, with basis
    `before_index_coverage`. With `index_runs` aged 3 hours it is `unknown`, with basis
    `stale_index`.
  - `test_session_without_candidate_is_unknown`: `search x --session c0000000-0000-4000-8000-00000000000f`
    with an index gives `unknown`.
  - `test_change_during_run`: with a `between` hook that deletes CW2 and moves XA from
    `archived_sessions/` to `sessions/`, coverage lists CW2 as vanished and XA is still
    read.
  - `test_cli_errors`, with the kinds and exit codes of §6.6:
    - an unknown-format `--file` exits 1, with `{"error": {"kind": "unknown_format", …}}`
      on stderr and empty stdout;
    - a relative `XDG_STATE_HOME` exits 1 with `bad_state_dir`;
    - an unknown option exits 2.
  - `test_closed_stdout_exits_quietly`: `main` writing to a closed pipe returns 0 and
    prints no traceback.
  - `test_cli_failure_kinds`:
    - `--task zz-999999`, which the stub fails, exits 1 with `tasks_failed`;
    - a `--file` with mode 0 exits 1 with `unreadable_input`, skipped as root.
  - `test_missing_without_copy_names_routes_and_cwd_narrows`:
    1. build the index over `home`;
    2. delete CA;
    3. search with `--since 2026-10-01`.

    Coverage lists CA under `files.missing` with `routes == ["file", "replay"]`, and the
    outcome is `unknown`. With `--cwd /w/beta`, CA is out of scope, and it is not listed.
  - `test_copies_flag_shows_request_blobs`: `search --session CA --copies --all-time
    --no-limit` includes CA:10's blocks with `copy == "request_blob"`.
  - `test_final_mode_and_task_selection`: on `turns`, with the index and the document in
    `TASK_FIXTURE`:
    - `search --final --session CM --all-time` emits 13 turn objects;
    - `search --task zz-000021 --sessions` lists CT1 (`provenance_stamp`) and CT3
      (`unsuccessful_task_command` and `task_command`);
    - `--mentions` adds CT2, labelled `textual_mention`;
    - every CT1 turn outside the note's span carries `task_evidence: session`.
  - `test_task_scope_before_coverage_is_unknown`: rewrite every `files.indexed_at_ms` in
    the test-owned index to 2026-10-12T11:45:00Z, which is after the task's `created`
    (11:30). Then `search zzz-absent --task zz-000021` gives `unknown`, with basis
    `before_index_coverage`.
  - `test_sort_and_reverse`:
    - `--sort path` orders CW before CW2;
    - `--sort path --reverse` orders CW2 first;
    - the default `activity` order is newest mtime first.
  - `test_limit_hit_is_recorded`: `search --session CA --all-time -n 1` emits one record,
    then coverage with `limits.hit` True.
  - `test_pretty_renders_refs`: `--pretty` exits 0, and its output names `ref_of("CA:1")`.
  - `test_coverage_fields`: a run's last object has `type "coverage"`, `format
    "session-logs/1"` and `rules.classifier == "session-logs-classifier/1"`. Lists longer
    than 20 are cut, with their counts kept.
- [ ] **Step 2:** `just test-one test_session_logs_search`. Expected: FAIL.
- [ ] **Step 3: Implement** the two modules.
  - Record selection follows §6.1. `--sort` takes `activity` (the default) or `path`.
  - `--pretty` prints one line per record: `ref role at text-excerpt`. Turns and
    sessions print as short blocks, and coverage as a closing summary.
- [ ] **Step 4:** `just test-one test_session_logs_search`. Expected: PASS.
- [ ] **Step 5:** `just gate`, then commit: `feat(session-logs): search, coverage and the
  CLI`.

### obs step 10: `show`

Spec §7.

**Files:**
- **Modify:** `session_logs_query.py` and `session_logs.py`, both new files.
- **Create:** `tests/test_session_logs_show.py`.

**Interfaces:**
- **Produces:**
  - `@dataclass class ShowOptions: view: str ("session"|"turn"|"lines"); lines: tuple[int,
    int] | None; links: bool; copies: bool; raw: bool; text_bytes: int; raw_bytes: int;
    limit: int | None; expect_sha256: str | None; state_dir: str | None`;
  - `show(target: str, opts: ShowOptions, env: dict, now_ms: int) -> Iterator[dict]`.

- [ ] **Step 1: Write the failing tests:**
  - `test_show_record_ref_prints_its_turn_with_pairs` (SL2): `show CA:4#0` emits the turn
    object, then every record of the turn, and `CA:4#0`'s `call.peer` is `CA:7#0`.
  - `test_show_session_view_orders_candidates`: `show CA` emits CA's session object
    (`own`), then AG's (`child`), then CA's turn objects. The file ref
    `show claude:projects/-w-alpha/<CA>.jsonl` gives the same objects.
  - `test_show_links_adds_bindings` (SL3, SL8):
    - `show agent-a0000000000000b01 --links` includes CA's session object and the binding
      records `CA:11#0` and `CA:12`;
    - `show XC --links` includes `XP:7` and `XP:8`.
  - `test_show_lines_and_explicit_file`:
    - `show --file captures/sdk-stream.jsonl --lines 4-5` emits exactly SDK:4 and SDK:5;
    - `show file:captures/sdk-stream.jsonl#L4` emits SDK:4's turn.
  - `test_show_never_not_found` (SL10B): `show CF` on `degraded` gives outcome `unknown`.
    `show <random uuid>` on `home` with an index also gives `unknown`.
  - `test_show_changed_and_absent_lines`:
    - `show CA:99` gives `unknown` with basis `line_absent`;
    - `show CA:4#0 --expect-sha256 0000` gives `unknown` with basis `line_changed`, and
      still emits the line.
- [ ] **Step 2:** `just test-one test_session_logs_show`. Expected: FAIL.
- [ ] **Step 3: Implement** `show` and its CLI subcommand.
- [ ] **Step 4:** `just test-one test_session_logs_show`. Expected: PASS.
- [ ] **Step 5:** `just gate`, then commit: `feat(session-logs): show`.

### obs step 11: Acceptance replay

Spec §14.1 and §14.2. SL11 is covered through obs steps 7 and 8.

**Files:**
- **Create:** `tests/test_session_logs_cases.py`.

**Interfaces:**
- **Consumes:** `run_cli` and `build_index` from obs step 1.

- [ ] **Step 1: Write one test per §14.1 row,** SL1 to SL10B. Each runs the row's command
  through `run_cli` against a `materialize`d copy and asserts the row's expectations by
  ref:
  - `test_sl1_calls_blocks_and_unknown_kind`;
  - `test_sl2_block_release_and_human_records`;
  - `test_sl3_models_and_controller`;
  - `test_sl4_homes_and_archive`, which also asserts that coverage lists `codex-work`
    archived as `absent`;
  - `test_sl5_human_turns_and_resume_copy`;
  - `test_sl6_three_hook_outputs`, which groups `tool_output` records by `call.id` in
    Python and asserts `{"toolu_fx_push1","toolu_fx_push2","toolu_fx_push3"}`;
  - `test_sl7_filing_chain`;
  - `test_sl8_reviewer_before_notice`;
  - `test_sl9_sdk_dispatch`;
  - `test_sl10a_degraded_coverage`;
  - `test_sl10b_missing_session_unknown`.

  Then add the §14.2 controls not already covered in obs steps 5 and 9:
  - `test_o10_codex_inherited_rows`, which records the fixture shapes the index holds under
    another id and asserts their relation;
  - `test_a01_archive_store`.
- [ ] **Step 2:** `just test-one test_session_logs_cases`. Expected: these pass, since the
  features exist. Break-check at least SL2, SL6 and SL10A by perturbing a vendored copy
  inside the test's scratch directory; each must fail.
- [ ] **Step 3:** `just gate`, then commit: `test(session-logs): acceptance replay of
  SL1–SL10 and the location controls`.

### obs step 12: Live-store run and gate evidence

Spec §14.4 and §11.2. This step is verification only: it adds no file.

- [ ] **Step 1: Run the reader's module API over every record of this host's six roots,**
  with a scratch script outside the repository. It counts objects by role and kind and
  keeps no text. Record:
  - files, lines, unknown kinds, unparsed lines and elapsed time;
  - any exception, which fails the step;
  - each wait tool's pending-at-turn-end count;
  - each root's coverage start;
  - the time, outcome and missing-file count of `session_logs.py search zzz-not-there`
    with the default window.
- [ ] **Step 2: Live cases.** Each must hold:
  - **Model bases.** Take one Codex child whose runtime and creation models differ; its
    session object lists both, with their bases.
  - **Candidates.** One audited origin from `hq:docs/notes/data/2026-10-20-session-index-reach.jsonl`
    has candidates matching its `source_path_sha256`.
  - **Task evidence.** `session_logs.py search --task hq-c411df --sessions` lists the
    sessions named by `tasks show hq-c411df --json` stamped notes.
  - **Forks.** For 20 sampled forks whose parent rollout is present, the copied range ends
    where the parent's turn ids end. Each copied alone into a scratch home then comes out
    wholly `ambiguous`, with no finals.
- [ ] **Step 3: Gate evidence.**
  - `git diff --stat <base>` shows only added `session_logs*` modules, tests and vendored
    fixtures, plus the `justfile`, `.gitignore` and the task record;
  - `just gate` passes.
- [ ] **Step 4:** Note the run's figures on the obs task, per the global rules' `run:`
  form if any part was refused or aborted, and attach the counts file.

---

## Handoff

These records are made after this plan is approved, before the `planned` gate is written.

1. **The hq child.** File Task 1 as hq-c411df's child:

   ```bash
   tasks add "SL11 fixtures for turn-final messages, task evidence, forks and escapes" --parent hq-c411df \
     --plan docs/plans/2026-10-23-session-evidence-reader.md --step "Task 1: SL11 fixtures for turn-final messages, task evidence, forks and escapes" \
     -p 2 --size s --complexity mid --process direct
   ```

   Its body is this task's scope brief and cites the spec and plan.
2. **The obs task.** File it in obs, with no parent:

   ```bash
   tasks add "Build the session-logs reader (Stage A) per hq's reviewed spec and plan" --project obs \
     -p 2 --size l --complexity high --process direct --source "hq:<merge sha>:docs/plans/2026-10-23-session-evidence-reader.md"
   ```

   - **Its body** names the spec and the plan by hq commit and path, and says they live in
     hq's `docs/specs/` and `docs/plans/`, not obs's.
   - **It restates** the Global Constraints, and carries the gate and treatment rules of
     §11.2: no README section, no skill or link, briefs name the reader only for its own
     work.
   - **Ordering.** `tasks dep <obs id> --on hq-c411df`, so vendoring waits for this merge.
3. **Stage B notes.** Note the Stage B items (§11.3) on obs-f5710b, obs-081ded and
   hq-19580c, each naming its item.
4. **hq-b95324.** Before this branch merges, run `tasks note hq-b95324 --no-reviewed` with
   the reviewed contract (§9 and §14.3) and the remaining work: the skill text, after
   readout.

**Execution of Task 1:** in this worktree, then hq-c411df's own verification:
- the whole branch (spec, plan, fixtures);
- `just test`;
- one fresh review of the combined diff;
- then retro, `tasks done` and a local merge (personal profile).
