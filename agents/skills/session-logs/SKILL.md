---
name: session-logs
description: Use when you need to read a coding agent's local session store — find the session behind a task, worktree or commit, read a turn, tell human turns from injected context — or to prepare pre-flow episodes for obs's proxy baseline with session-episodes.
---

# session-logs

Where each harness keeps its sessions, what the records look like, and how to
turn them into evidence without pasting transcripts anywhere. The tool is
`~/.agents/bin/session-episodes` (`agents/bin/session-episodes` when standing
in `hq`); nothing puts it on PATH. Its contract is
`docs/specs/2026-09-19-session-logs-design.md` in the `hq` checkout.

## Stores

| Harness | Store | Unit | Notes |
| --- | --- | --- | --- |
| Claude Code | `~/.claude/projects/<cwd-slug>/<session-uuid>.jsonl` | one JSONL file per session; a subagent transcript is a file whose records are all `isSidechain` | `--resume` forks a new uuid that copies the old records (same `uuid`s and tool ids, `sessionId` rewritten): two files, one conversation |
| Codex | `~/.codex/sessions/YYYY/MM/DD/rollout-<ts>-<uuid>.jsonl` | one rollout per session; `session_meta` first | no session on this host has a second rollout |
| agy | `~/.gemini/antigravity-cli/brain/<conversation-id>/.system_generated/logs/transcript_full.jsonl` | one step per line, one file per conversation; a subagent is a conversation of its own | titles, workspaces and parents live in `~/.gemini/antigravity-cli/conversation_summaries.db`; episodes never reads it |
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
`claude_adapter.py` / `codex_adapter.py` and in `session-episodes`; change all
three together.

In agy, the human is a `USER_INPUT` step with `source: USER_EXPLICIT`, and only the
text inside `<USER_REQUEST>…</USER_REQUEST>`: the `<ADDITIONAL_METADATA>` and
`<USER_SETTINGS_CHANGE>` blocks after it are agy's, and so is every other step type,
`SYSTEM_MESSAGE` included (its `[Message] … sender=…` lines are controller and
background-task wake-ups). A conversation with no `USER_EXPLICIT` input is a
subagent's.

## Finding the session behind a thing

- **A task id.** Since 2026-09-17 lifecycle notes carry
  `provenance: {"harness_session": "claude-code:<uuid>" | "codex:<uuid>" | "agy:<conversation-id>", …}`;
  `tasks show <id>` prints them; an agy id names the `brain/<conversation-id>`
  directory. Before that, search *tool-call inputs* for
  `tasks start <id>` — never the raw text, which also matches the tasks
  skill's own instructions and Codex's AGENTS.md injection (a text grep hits
  ~1,400 Codex files; tool calls are the real ones):

      python3 - <<'EOF'
      import json, glob, os
      for f in glob.glob(os.path.expanduser("~/.claude/projects/*/*.jsonl")):
          for n, line in enumerate(open(f, errors="replace"), 1):
              if '"tool_use"' not in line or "tasks start ai-6c8245" not in line: continue
              r = json.loads(line)
              for b in (r.get("message") or {}).get("content") or []:
                  if isinstance(b, dict) and b.get("type") == "tool_use" and "tasks start ai-6c8245" in str((b.get("input") or {}).get("command", "")):
                      print(f"{f}#L{n}", r.get("sessionId"))
      EOF

  For Codex, filter `response_item` lines whose payload type is
  `function_call`/`custom_tool_call` and search their `arguments`/`input`.
  For agy, read the `PLANNER_RESPONSE` steps and search
  `tool_calls[].args.CommandLine` of the `run_command` calls; the conversation id
  is the directory under `~/.gemini/antigravity-cli/brain/`.
- **A worktree.** `cwd` on any timed Claude record; `session_meta.cwd` in Codex;
  in agy, the `workspace_uris` of the conversation's row in
  `~/.gemini/antigravity-cli/conversation_summaries.db` (`hq sessions --harness agy`
  lists them), or the paths in its `run_command` calls.
- **A commit.** A tool call whose command contains `git commit`, then the sha
  in its result.

## Reading a turn

A turn is one human record through the assistant's last record before the
next human record. Print one Claude turn's texts by line range:

    sed -n '120,180p' ~/.claude/projects/<slug>/<uuid>.jsonl | python3 -c '
    import json,sys
    for l in sys.stdin:
        r=json.loads(l); c=(r.get("message") or {}).get("content")
        t=c if isinstance(c,str) else " ".join(b.get("text","") for b in c if isinstance(b,dict) and b.get("type")=="text") if isinstance(c,list) else ""
        if t.strip(): print(r["type"], r["timestamp"], t[:200])'

`session-episodes show <id> --episodes <file>` prints a known episode's anchor,
result, last assistant text and next human turn with their refs; prefer it
over hand-reading when an id exists.

## Preparing pre-flow episodes

The output feeds obs Task 4 (`obs baseline --input episodes.jsonl`). One pass:

1. `~/.agents/bin/session-episodes extract --out <dir>/episodes.jsonl`
   The JSON summary on stderr is the run's provenance: files per harness,
   exclusions, unconfirmed starts by reason, turn outcomes, label sources,
   `note_missing`, `origin_unknown`, `retired`. Keep it with the file. It
   reads Claude Code and Codex; `--harness claude-code|codex|agy`, repeated,
   names the stores instead, and until the flow-trial-1 readout (2027-02-16)
   agy is read only when `--harness agy` is given, so the default run and its
   summary stay as they were. Every file in the selected stores is seen, and `skipped` counts the ones not parsed
   because they cannot hold an anchor (a subagent rollout by its first line,
   a file older than `--since` by mtime, a file without `tasks … start|park|
   done|drop` in its text; about 2 minutes for 23 GB on this host);
   `--since DAYS` and `--project PREFIX` narrow the *episodes*, and `--since`
   also skips older files;
   `--window-minutes N` sets the window (default 10); `--labels` / `--anchors`
   name the sidecars when they are not beside `--out`; `SESSION_LOGS_CLAUDE`,
   `SESSION_LOGS_CODEX` and `SESSION_LOGS_AGY` (the agy home, holding `brain/`)
   point at other store roots. The default roots come from hq's
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
