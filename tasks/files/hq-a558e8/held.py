"""Turn ends at which the session still held a claim it had taken, by harness (hq-a558e8).

A claim is taken by a successful `tasks start <id>` tool call (its result names the id and
carries no error) and released by `tasks park|done|drop|shelve <id>`, applied in command
order once the call's output arrives. Each candidate is then confirmed against the task
record's lifecycle markers, which see releases the tool calls do not. A Claude Code turn end
is a stop_hook_summary; a Codex turn end is task_complete. Main threads only: a Claude
subagent file and a Codex worker rollout (thread_source other than user) are skipped,
since their claims are not the root's own.

    python3 judge_held.py [SINCE] > held.json
"""
import glob
import json
import os
import re
import sys

SINCE = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else "2026-09-29T13:00:00Z"
ID = r"([a-z][a-z0-9]*-[0-9a-f]{6})\b"
# One pattern for both verbs, matched in command order, so a call that starts and then parks
# a task leaves it released. Flags may precede the id; Codex list forms ['tasks','done',id] too.
VERB = re.compile(r"\btasks\b(?:\s+-C\s+\S+)?\s+(start|park|done|drop|shelve)\b((?:\s+--?[a-z-]+(?:[ =](?:\"[^\"]*\"|'[^']*'|[^\s-]\S*))?)*)\s+" + ID
                  + r"|[\"']tasks[\"'],\s*[\"'](start|park|done|drop|shelve)[\"'],\s*[\"']" + ID)
TTL_S = 4 * 3600  # Codex claims carry no pid and live by this TTL (tasks README)


def events(cmd):
    """(verb, id) in the order the command runs them; escaped newlines decoded first."""
    cmd = cmd.replace("\\n", "\n").replace('\\"', '"')
    out = []
    for m in VERB.finditer(cmd):
        verb, tid = (m.group(1), m.group(3)) if m.group(1) else (m.group(4), m.group(5))
        out.append(("start" if verb == "start" else "release", tid))
    return out
GUARD = ("live task claim", "Related worker claims", "claim-guard:")


def started_ok(out, tid):
    """The start's result names the id and is not an error; Codex escapes its output twice."""
    flat = out.replace("\\", "").replace(" ", "")
    return f'"id":"{tid}"' in flat and '"error":' not in flat


def apply(held, evs, out, ts):
    """Apply one call's events in order once its output is known; held maps id to start time."""
    for kind, tid in evs:
        if kind == "start":
            if started_ok(out, tid):
                held[tid] = ts
        else:
            held.pop(tid, None)


def age(start, end):
    from datetime import datetime
    parse = lambda x: datetime.fromisoformat(x.replace("Z", "+00:00"))
    return (parse(end) - parse(start)).total_seconds() if start else 0


def claude(roots):
    rows = []
    for f in (f for root in roots for f in glob.glob(root + "/*/*.jsonl")):
        pending, held = {}, {}
        try:
            for n, line in enumerate(open(f, errors="replace"), 1):
                if '"tool_use"' not in line and '"tool_result"' not in line and "stop_hook_summary" not in line:
                    continue
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                if r.get("isSidechain"):
                    continue
                for b in (r.get("message") or {}).get("content") or []:
                    if not isinstance(b, dict):
                        continue
                    if b.get("type") == "tool_use" and b.get("name") == "Bash":
                        evs = events(str((b.get("input") or {}).get("command", "")))
                        if evs:
                            pending[b.get("id")] = evs
                    elif b.get("type") == "tool_result" and b.get("tool_use_id") in pending:
                        c = b.get("content")
                        apply(held, pending.pop(b["tool_use_id"]), c if isinstance(c, str) else json.dumps(c), r.get("timestamp"))
                if r.get("subtype") == "stop_hook_summary" and (r.get("timestamp") or "") >= SINCE:
                    if any("claim-guard" in (h.get("command") or "") for h in r.get("hookInfos") or []):
                        blocked = any(any(g in e for g in GUARD) for e in r.get("hookErrors") or [])
                        rows.append(dict(harness="claude-code", ref=f"{f}#L{n}", ts=r["timestamp"],
                                         held=sorted(held), blocked=blocked))
        except OSError:
            continue
    return rows


def codex(roots):
    rows = []
    for f in (f for root in roots for f in glob.glob(root + "/**/*.jsonl", recursive=True)):
        pending, held, root_thread = {}, {}, True
        try:
            for n, line in enumerate(open(f, errors="replace"), 1):
                if n == 1:
                    try:
                        meta = json.loads(line).get("payload") or {}
                    except ValueError:
                        meta = {}
                    root_thread = meta.get("thread_source", "user") == "user"
                if not root_thread:
                    break
                # An output need not mention tasks (a park prints only {"id": …}), so keep every output.
                if not any(k in line for k in ("tasks", "task_complete", "hook_prompt", "_call_output")):
                    continue
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                p = r.get("payload") or {}
                t = p.get("type")
                if t in ("custom_tool_call", "function_call"):
                    cmd = p.get("input") if t == "custom_tool_call" else p.get("arguments")
                    evs = events(str(cmd))
                    if evs:
                        pending[p.get("call_id")] = evs
                elif t in ("custom_tool_call_output", "function_call_output") and p.get("call_id") in pending:
                    apply(held, pending.pop(p["call_id"]), json.dumps(p.get("output")), r.get("timestamp"))
                elif t == "task_complete" and (r.get("timestamp") or "") >= SINCE:
                    live = sorted(k for k, at in held.items() if age(at, r["timestamp"]) < TTL_S)
                    rows.append(dict(harness="codex", ref=f"{f}#L{n}", ts=r["timestamp"], held=live,
                                     lapsed=sorted(set(held) - set(live)), blocked=False,
                                     final_answer=bool(p.get("last_agent_message"))))
                elif t == "message" and p.get("role") == "user" and "<hook_prompt" in json.dumps(p) and rows:
                    rows[-1]["blocked"] = True
        except OSError:
            continue
    return rows


def confirm(rows):
    """Keep a candidate only while the task record agrees: the claim's last lifecycle marker at
    or before the turn end is started or resumed. Tool calls miss release forms (loops, a park
    run by another process); the record does not."""
    import subprocess
    notes = {}
    for r in rows:
        kept = []
        for tid in r["held"]:
            if tid not in notes:
                out = subprocess.run(["tasks", "--json", "show", tid], capture_output=True, text=True)
                notes[tid] = json.loads(out.stdout)["task"].get("notes", []) if out.returncode == 0 else None
            marks = [n for n in notes[tid] or [] if n.get("at", "") <= r["ts"]
                     and re.match(r"(started|resumed|parked|done|dropped|shelved)\b", n.get("text", ""))]
            if notes[tid] is None or (marks and marks[-1]["text"].startswith(("started", "resumed"))):
                kept.append(tid)
        r["candidates"], r["held"] = r["held"], kept
    return rows


rows = [] if "--codex-only" in sys.argv else claude([os.path.expanduser(p) for p in ("~/.claude/projects", "~/.claude-work/projects")])
rows += codex([os.path.expanduser(p) for p in ("~/.codex/sessions", "~/.codex-work/sessions")])
rows = confirm([r for r in rows if r["held"]]) + [r for r in rows if not r["held"]]
summary = {}
for h in ("claude-code", "codex"):
    mine = [r for r in rows if r["harness"] == h]
    held = [r for r in mine if r["held"]]
    summary[h] = dict(turn_ends=len(mine), held_ends=len(held), held_blocked=sum(r["blocked"] for r in held),
                      unheld_blocked=sum(r["blocked"] for r in mine if not r["held"]))
json.dump(dict(since=SINCE, summary=summary, held=[r for r in rows if r["held"]]), sys.stdout, indent=1)
