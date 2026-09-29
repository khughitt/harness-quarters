---
name: session-logs
description: Use when you need to read a coding agent's local session store — find the session behind a task, worktree or commit, read a turn, tell human turns from injected context — or to prepare pre-flow episodes for obs's proxy baseline with session-episodes.
---

# session-logs

Where each harness keeps its sessions, what the records look like, and how to
turn them into evidence without pasting transcripts anywhere. The tool is
`~/.agents/bin/session-episodes` (`agents/bin/session-episodes` when standing
in `tack`); nothing puts it on PATH. Its contract is
`docs/specs/2026-09-19-session-logs-design.md` in the `tack` checkout.

## Stores

| Harness | Store | Unit | Notes |
| --- | --- | --- | --- |
| Claude Code | `~/.claude/projects/<cwd-slug>/<session-uuid>.jsonl` | one JSONL file per session; a subagent transcript is a file whose records are all `isSidechain` | `--resume` forks a new uuid that copies the old records (same `uuid`s and tool ids, `sessionId` rewritten): two files, one conversation |
| Codex | `~/.codex/sessions/YYYY/MM/DD/rollout-<ts>-<uuid>.jsonl` | one rollout per session; `session_meta` first | no session on this host has a second rollout |
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

## Human or injected

Not the human, in Claude Code: `isMeta`, `isCompactSummary`, `isSidechain`,
a user record holding only `tool_result` blocks, and text beginning `<`
(system reminders, hook context, `<task-notification>`,
`<local-command-stdout>`). The one `<` that *is* the human: a turn beginning
`<pasted_content id="…">` — the person pasted something and may have typed
after the closing `</pasted_content id="…">`; the wrapper tags are the
harness's, the rest is theirs. Not the human, in Codex: user messages
beginning `# AGENTS.md`, `<environment_context>`, `<INSTRUCTIONS>`,
`<skills_instruct`, `<turn_aborted>`, `<permissions`, `<user_shell`,
`<collaboration_mode`, or any `<`. The same list lives in obs's
`claude_adapter.py` / `codex_adapter.py` and in `session-episodes`; change all
three together.

## Finding the session behind a thing

- **A task id.** Since 2026-09-17 lifecycle notes carry
  `provenance: {"harness_session": "claude-code:<uuid>" | "codex:<uuid>", …}`;
  `tasks show <id>` prints them. Before that, search *tool-call inputs* for
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
- **A worktree.** `cwd` on any timed Claude record; `session_meta.cwd` in Codex.
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
   `note_missing`, `origin_unknown`, `retired`. Keep it with the file. Every
   file in both stores is seen, and `skipped` counts the ones not parsed
   because they cannot hold an anchor (a subagent rollout by its first line,
   a file older than `--since` by mtime, a file without `tasks … start|park|
   done|drop` in its text; about 2 minutes for 23 GB on this host);
   `--since DAYS` and `--project PREFIX` narrow the *episodes*, and `--since`
   also skips older files;
   `--window-minutes N` sets the window (default 10); `--labels` / `--anchors`
   name the sidecars when they are not beside `--out`; `SESSION_LOGS_CLAUDE`
   and `SESSION_LOGS_CODEX` point at other store roots.
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
