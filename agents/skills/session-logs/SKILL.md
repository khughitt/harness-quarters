---
name: session-logs
description: Use when you need to read a coding agent's local session store — find the session behind a task, worktree or commit, read a turn, tell human turns from injected context — or to prepare pre-flow episodes for obs's proxy baseline with session-episodes.
---

# session-logs

Use obs's `bin/session-logs` reader first to find sessions and read what happened.
The store layouts and record shapes below explain the evidence when a targeted
raw read is needed. Keep transcript text local.

## Find and read sessions

Resolve the reader's checkout with `tasks resolve obs --json`. Require one
`resolved` result and set `OBS_ROOT` to its `root`; stop on a resolution error or
a missing `bin/session-logs`. Invoke `"$OBS_ROOT/bin/session-logs"` by explicit
path: it need not be on PATH. Its current contract is `docs/operations.md`,
“Session investigation and diagnosis”, in that obs checkout.

Start with task-based search, or go straight to a known session's skeleton:

```sh
"$OBS_ROOT/bin/session-logs" search --task demo-000001 --pretty
"$OBS_ROOT/bin/session-logs" show SESSION_ID --skeleton --pretty
```

The skeleton gives each turn's span, call count and token totals, then one line
per human or dispatch input, assistant text and tool call. Calls show wall time
and exit status; reasoning and injected context are omitted. Add `--injected`
to see injected context. Token totals use indexed responses timed inside the
turn; they are partial while the index lags and unavailable without it. Codex
call exits depend on the index. Unknown, missing and partial values are not
evidence of success; the reader never indexes or modifies a store.

Follow a returned session or record ref to the relevant evidence:

```sh
"$OBS_ROOT/bin/session-logs" show SESSION_ID --turn --pretty
"$OBS_ROOT/bin/session-logs" show SESSION_ID --lines 120-180
"$OBS_ROOT/bin/session-logs" show 'HOME:PATH#L120#0' --text-bytes 8000
```

Use actual refs from the output, quoting refs containing `#`. Pretty output is
an overview with clipped text; omit `--pretty` for JSON evidence and increase
`--text-bytes` when its text is truncated. `--raw` exposes the source record.
`--expect-sha256 HASH` on a record ref detects a hash mismatch but still emits
the current records and exits 0: check coverage for `outcome: unknown` with
`outcome_basis: line_changed` before treating evidence as unchanged.
A record ref opens its enclosing turn; for just one physical line, use the
session or file target with `--lines 120-120`.

Unscoped store searches default to the last 30 days; use `--all-time` for older
work. Searches scoped by `--task`, `--session` or `--file` have no default
time cutoff; explicit `--since` and `--until` still apply. Use
`--role human|tool_call|tool_output` to narrow a search, `--cwd PATH` for a
worktree, or a commit hash as the search pattern. `--task` selects sessions
with task activity; `--mentions` also includes mere mentions. Search covers
Claude Code and Codex stores, including configured archived homes; the other
harness layouts below do not imply reader support. Inspect the coverage
footer or JSON coverage object for missing/unreadable files and a hit limit.
`--limit` counts turns in the default session and skeleton views, and records
with `--turn`, `--lines` or a record ref; narrow the request or use `--no-limit`
when the limit hides evidence.
No match with incomplete coverage does not establish absence.

For an already prepared episode dataset, use `session-episodes show` as
described below. `~/.agents/bin/session-episodes` (`agents/bin/session-episodes`
in hq) prepares episodes, rather than serving as the general session reader;
its contract is `docs/sessions.md` in hq.

## Stores

| Harness | Store | Unit | Notes |
| --- | --- | --- | --- |
| Claude Code | `~/.claude/projects/<cwd-slug>/<session-uuid>.jsonl` | one JSONL file per session; a subagent transcript is a file whose records are all `isSidechain` | `--resume` forks a new uuid that copies the old records (same `uuid`s and tool ids, `sessionId` rewritten): two files, one conversation |
| Codex | `~/.codex/sessions/YYYY/MM/DD/rollout-<ts>-<uuid>.jsonl` | one rollout per session; `session_meta` first | no session on this host has a second rollout |
| agy | `~/.gemini/antigravity-cli/brain/<conversation-id>/.system_generated/logs/transcript_full.jsonl` | one step per line, one file per conversation; a subagent is a conversation of its own | titles, workspaces and parents live in `~/.gemini/antigravity-cli/conversation_summaries.db`; episodes never reads it |
| pi | `~/.pi/agent/sessions/<cwd-slug>/<timestamp>_<session-uuid>.jsonl` | one JSONL file per session, the `session` header first; every branch of the session tree is in the one file | no index beside the files; `--fork` writes a new file whose header names the old one in `parentSession` and copies its entries with their ids. `--session-dir` or `PI_CODING_AGENT_SESSION_DIR` puts sessions elsewhere |
| opencode | `~/.local/share/opencode/opencode.db` (sqlite; `opencode-local.db` beside it) | rows, not files | store only; tooling arrives with obs-175b10 |
| Crush | `~/.crush/crush.db` and `<project>/.crush/crush.db` (sqlite) | rows, per project | store only; as above |

## Record shapes

Claude Code — one JSON object per line. The ones that matter:

    {"type":"user","uuid":"…","parentUuid":"…","sessionId":"…","cwd":"…","gitBranch":"…","timestamp":"2026-09-17T12:00:00.000Z",
     "message":{"role":"user","content":"Let's pick up ai-6c8245"}}
    {"type":"assistant","uuid":"…","timestamp":"…","message":{"role":"assistant","content":[
       {"type":"tool_use","id":"toolu_…","name":"Bash","input":{"command":"tasks start ai-6c8245"}}]}}
    {"type":"user","timestamp":"…","message":{"role":"user","content":[
       {"type":"tool_result","tool_use_id":"toolu_…","content":"{\"id\":\"ai-6c8245\",\"warnings\":[]}"}]}}

`message.content` is a string or a list of `text` / `tool_use` / `tool_result`
blocks. `isMeta`, `isCompactSummary`, `isSidechain` mark records that are not
the conversation's main line. There is no `stopReason`; a turn ends where the
next human record begins.

Codex — `{"timestamp","type","payload"}` per line:

    {"type":"session_meta","payload":{"id":"…","cwd":"…","originator":"codex-tui","thread_source":"user"}}
    {"type":"event_msg","payload":{"type":"task_started","turn_id":"…"}}      # also task_complete, turn_aborted, user_message
    {"type":"response_item","payload":{"type":"message","role":"user","content":[{"type":"input_text","text":"…"}]}}
    {"type":"response_item","payload":{"type":"custom_tool_call","call_id":"call_…","input":"const r = await tools.exec_command({cmd:\"tasks start lit-f43833\"}) …"}}
    {"type":"response_item","payload":{"type":"custom_tool_call_output","call_id":"call_…","output":[{"type":"input_text","text":"…"}]}}

Older rollouts use `function_call` (`name: "shell"`, `arguments` JSON with a
`command` array) and `function_call_output` (`output` string). A turn is
bracketed by `task_started` … `task_complete`; `turn_aborted` ends one early.

agy — one step per line, `{"step_index","source","type","status","created_at",…}`:

    {"step_index":0,"source":"USER_EXPLICIT","type":"USER_INPUT","created_at":"2026-11-01T09:16:40Z",
     "content":"<USER_REQUEST>\nLet's take ai-6c8245\n</USER_REQUEST>\n<ADDITIONAL_METADATA>…</ADDITIONAL_METADATA>"}
    {"step_index":1,"source":"MODEL","type":"PLANNER_RESPONSE","content":"…","tool_calls":[
       {"name":"run_command","args":{"CommandLine":"tasks start ai-6c8245","WaitMsBeforeAsync":5000}}]}
    {"step_index":2,"source":"MODEL","type":"GENERIC","status":"DONE","content":"Created At: …\nCommand exited with code 0.\n\nCommand output:\n{\"id\":\"ai-6c8245\",\"warnings\":[]}"}
    {"step_index":3,"source":"SYSTEM","type":"SYSTEM_MESSAGE","content":"… <SYSTEM_MESSAGE>\n[Message] timestamp=… sender=<id>/task-2 … content=Task id \"<id>/task-2\" finished with result:\n…</SYSTEM_MESSAGE>"}
    {"step_index":4,"source":"SYSTEM","type":"ERROR_MESSAGE","error":"API error (attempt 1): …"}

Also `CHECKPOINT` steps. agy records no call ids: the k-th `GENERIC` step after a
`PLANNER_RESPONSE` is the result of its k-th tool call, and session-episodes names
the call `<conversation-id>:<step_index>:<k>`. Three cases the pairing handles:

1. A command that outlives `WaitMsBeforeAsync`: its `GENERIC` has `status: RUNNING`
   and names `background task with task id: <bg-id>`. Its result is the later
   `SYSTEM_MESSAGE` naming `sender=<bg-id>`: the text after `finished with result:`,
   or, after `was canceled with result:`, an error result. A daemon or an
   early-cancelled timer may never get one; its call then has no result.
2. A `GENERIC` with `status: ERROR` (`Encountered error in step execution: …`) is an
   error result: it never confirms a start.
3. Fewer `GENERIC` steps than calls (an interrupted or unfinished step): the unpaired
   calls have no result.

A turn runs from a human `USER_INPUT` to the step before the next one, across the
`SYSTEM_MESSAGE` wake-ups and the planner steps they trigger. It is completed when
it ends on a `PLANNER_RESPONSE` with text and no tool calls (also after starting a
background command), wait when the last planner step's unanswered calls are only
`ask_question`, unknown on an `ERROR_MESSAGE` or any other unanswered tail.

pi — one entry per line, `{"type","id","parentId","timestamp",…}` after the header:

    {"type":"session","version":3,"id":"<uuidv7>","timestamp":"2026-11-01T09:16:40.000Z","cwd":"/work/x"}
    {"type":"model_change","id":"<8 hex>","parentId":null,"provider":"…","modelId":"…"}     # also thinking_level_change
    {"type":"message","id":"…","parentId":"…","message":{"role":"user","content":[{"type":"text","text":"Let's take ai-6c8245"}]}}
    {"type":"message","id":"…","parentId":"…","message":{"role":"assistant","content":[
       {"type":"thinking","thinking":"…"},{"type":"toolCall","id":"call_…","name":"bash","arguments":{"command":"tasks start ai-6c8245"}}],
       "provider":"…","model":"…","usage":{…},"stopReason":"toolUse"}}
    {"type":"message","id":"…","parentId":"…","message":{"role":"toolResult","toolCallId":"call_…","toolName":"bash",
       "content":[{"type":"text","text":"{\"id\":\"ai-6c8245\",\"warnings\":[]}"}],"isError":false}}

Also `session_info` (a name), `label`, `compaction`, `branch_summary`,
`custom`, `custom_message` and `usage` entries. Entries form a tree through
`parentId`, appended in the order written: when the person moves to another
branch, the next entry's `parentId` is not the entry before it. A response's
`stopReason` is one of `stop`, `toolUse`, `length`, `error`, `aborted` (the
person interrupted), `pending` and `deferred`. Call ids come from the provider and need not be unique across
responses; session-episodes names a call `<entry id>:<call id>`. pi writes no
turn-end record; a turn ends at the next human message.

## Human or injected

Not the human, in Claude Code: `isMeta`, `isCompactSummary`, `isSidechain`,
a user record holding only `tool_result` blocks, and text beginning `<`
(system reminders, hook context, `<task-notification>`,
`<local-command-stdout>`). Not the human, in Codex: user messages
beginning `# AGENTS.md`, `<environment_context>`, `<INSTRUCTIONS>`,
`<skills_instruct`, `<turn_aborted>`, `<permissions`, `<user_shell`,
`<collaboration_mode`, or any `<`. In both harnesses the one `<` that *is* the
human: a turn beginning `<pasted_content id="…">` — the person pasted
something and may have typed after the closing `</pasted_content id="…">`; the
wrapper tags are the harness's, the rest is theirs. The same list lives in obs's
`src/obs/harness/_claude.py` / `src/obs/harness/codex.py` and in `session-episodes`; change all
three together.

In agy, the human is a `USER_INPUT` step with `source: USER_EXPLICIT`, and only the
text inside `<USER_REQUEST>…</USER_REQUEST>`: the `<ADDITIONAL_METADATA>` and
`<USER_SETTINGS_CHANGE>` blocks after it are agy's, and so is every other step type,
`SYSTEM_MESSAGE` included (its `[Message] … sender=…` lines are controller and
background-task wake-ups). A conversation with no `USER_EXPLICIT` input is a
subagent's.

In pi, the human is a `message` entry with `role: "user"`. Not the human: the
`system` role (the prompt sections pi records when they change), `bashExecution`
(a `!` command the person ran outside the conversation), `custom` and
`custom_message` entries (extensions), and `compaction` and `branch_summary`
entries (pi's summaries). The header does not say whether a run was interactive:
`pi -p` and `--mode rpc` write the same header and entries.

## Finding the session behind a thing

- **A task id.** First use `session-logs search --task ID` as above. Since
  2026-09-17 lifecycle notes carry
  `provenance: {"harness_session": "claude-code:<uuid>" | "codex:<uuid>" | "agy:<conversation-id>", …}`;
  `tasks show <id>` prints them; an agy id names the `brain/<conversation-id>`
  directory. With no stamp, search tool-call inputs, for example
  `session-logs search 'tasks start demo-000001' --role tool_call --all-time`.
  Raw text searches also match injected instructions; inspect the returned
  call and result before treating a mention as task activity.
  For agy, read the `PLANNER_RESPONSE` steps and search
  `tool_calls[].args.CommandLine` of the `run_command` calls; the conversation id
  is the directory under `~/.gemini/antigravity-cli/brain/`.
  For pi, search the `toolCall` blocks of `assistant` messages whose `name` is
  `bash` for `arguments.command`; the session id is the header's `id`, also the
  end of the file name.
- **A worktree.** `cwd` on any timed Claude record; `session_meta.cwd` in Codex;
  in agy, the `workspace_uris` of the conversation's row in
  `~/.gemini/antigravity-cli/conversation_summaries.db` (`hq sessions --harness agy`
  lists them), or the paths in its `run_command` calls; in pi, the header's `cwd`
  (`hq sessions --harness pi --here` lists them).
- **A commit.** A tool call whose command contains `git commit`, then the sha
  in its result.

## Reading a turn

A turn is one human record through the assistant's last record before the
next human record. Use the reader's skeleton first, then `show --turn` or
`show --lines` to inspect the relevant request, action, result and correction.
The commands and evidence limits are in “Find and read sessions” above.

For a prepared episode, `~/.agents/bin/session-episodes show <id> --episodes
<file>` prints its anchor, result, last assistant text and next human turn
with their refs.

## Preparing pre-flow episodes

The output feeds obs Task 4 (`obs baseline --input episodes.jsonl`). One pass:

1. `~/.agents/bin/session-episodes extract --out <dir>/episodes.jsonl`
   The JSON summary on stderr is the run's provenance: files per harness,
   exclusions, unconfirmed starts by reason, turn outcomes, label sources,
   `note_missing`, `origin_unknown`, `retired`. Keep it with the file. It
   reads Claude Code and Codex; `--harness claude-code|codex|agy|pi`, repeated,
   names the stores instead, and until the flow-trial-1 readout (2027-02-16)
   agy and pi are read only when `--harness` names them, so the default run and
   its summary stay as they were. Every file in the selected stores is seen, and `skipped` counts the ones not parsed
   because they cannot hold an anchor (a subagent rollout by its first line,
   a file older than `--since` by mtime, a file without `tasks … start|park|
   done|drop` in its text; about 2 minutes for 23 GB on this host);
   `--since DAYS` and `--project PREFIX` narrow the *episodes*, and `--since`
   also skips older files;
   `--window-minutes N` sets the window (default 10); `--labels` / `--anchors`
   name the sidecars when they are not beside `--out`; `SESSION_LOGS_CLAUDE`,
   `SESSION_LOGS_CODEX`, `SESSION_LOGS_AGY` (the agy home, holding `brain/`) and
   `SESSION_LOGS_PI` (pi's `sessions/` directory) point at other store roots. The default roots come from hq's
   `tools/harness_stores`, which the script finds from its own real path; a copy
   outside an hq checkout stops with an error naming that path.
2. Hand over `episodes.jsonl` and the summary now: the consumer reports
   coverage per harness and does not wait for the queue.
3. Walk `<dir>/episodes.candidates.jsonl` within the budget the consumer set,
   `stamp_delta_s` candidates first, then `error-output`: for each, `show <id>
   --episodes …`; if the start's `{"id": …, "warnings": …}` line is in the
   result and belongs to this start, `confirm <id> yes`; otherwise `confirm
   <id> no`. The unreviewed remainder stays in the file and in the summary.
4. Re-run `extract`. Review every episode with `status_question: true` and a
   sample of `false` with `show`; correct with `label <id> yes|no`. The
   heuristic is a case-insensitive search of the next human turn for any of
   `still (running|executing|going|working)`,
   `is (it|that|this|the task) (still )?(running|done|finished|complete)`,
   `(did|has) (it|that) (finish|complete|stop)`, `\bstatus\b`,
   `\bprogress\b`, `where (are we|is it|did .* (stop|leave off))`,
   `what('s| is) (left|next|happening)`,
   `(are|is) (you|anything) (still )?(working|running)` — deliberately broad
   (`git status` and `progress bar` match), so expect the `true` set to need
   correction; the list lives in `STATUS_PATTERNS` in the script.
5. Re-run `extract` once more and hand over `episodes.jsonl` with the summary.

What the file contains: ids, timestamps, booleans, `source_refs`. No
transcript text, no commands beyond the task id they named. The refs are
absolute paths under your home — local evidence for a local report; do not
paste the file anywhere public. What it cannot see: a park or close recorded
only on a branch deleted unmerged by a session whose store is not on this
host; `note_missing` in the summary is the measured lower bound on that loss.
