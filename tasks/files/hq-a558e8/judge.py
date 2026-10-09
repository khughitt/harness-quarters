"""Claim-guard rollout judgment (hq-a558e8): every Stop the guard ran on, every block, and
what each blocked turn did. Reads both Claude Code homes and both Codex homes on this host.

    python3 judge.py [SINCE] > judge.json      # SINCE defaults to 2026-09-29T13:00:00Z

Prints a JSON report: turn ends with the guard, blocks by day and reason variant, and one
row per block with the evidence a reader needs to check its class (ref, texts, commands).
"""
import collections
import glob
import json
import os
import re
import sys

SINCE = sys.argv[1] if len(sys.argv) > 1 else "2026-09-29T13:00:00Z"
CLAUDE = [os.path.expanduser(p) for p in ("~/.claude/projects", "~/.claude-work/projects")]
CODEX = [os.path.expanduser(p) for p in ("~/.codex/sessions", "~/.codex-work/sessions")]
GUARD_TEXT = ("live task claim", "Related worker claims", "claim-guard:", "claims could not be read")
TASKS_CMD = re.compile(r"\btasks\b[^\n|;&]*?\b(park|done|drop)\b")
# The next step may follow flags: `tasks park <id> --waiting-on user --reason approval "<step>"`.
PARK_TEXT = re.compile(r"\btasks\b[^\n]*?\bpark\s+\S+(?:\s+--?[a-z-]+(?:\s+[a-z]+)?)*\s+(\"(?:[^\"\\]|\\.)*\"|'[^']*')")
WAIT_TOOLS = {"TaskOutput", "BashOutput", "Monitor", "AgentOutput"}


def variant(text):
    """Which branch of the guard wrote the reason."""
    if "No child the harness tracks is running" in text:
        return "own: no child running"
    m = re.search(r"The guard cannot see whether a child is running \(([^)]*)\)", text)
    if m:
        return f"own: children unseen ({m.group(1)[:60]})"
    if "This guard cannot see children" in text:
        return "own: pre-change text (no Stop-input read)"
    if "Wake inputs are unprobed" in text:
        return "own: wake inputs unprobed"
    if "claims could not be read" in text:
        return "claims read failed"
    if "Related worker claims" in text and "live task claim" not in text:
        return "related worker claims"
    if "claim-guard:" in text:
        return "input defect: " + text.split("claim-guard:", 1)[1].strip()[:60]
    if "live task claim" in text:
        return "own: other text"
    return "unrecognized"


def text_of(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text")
    return ""


def human(rec):
    """A record a person typed (session-logs: not meta, not tool results, not `<` except a paste)."""
    if rec.get("type") != "user" or rec.get("isMeta") or rec.get("isCompactSummary") or rec.get("isSidechain"):
        return False
    c = (rec.get("message") or {}).get("content")
    if isinstance(c, list) and all(isinstance(b, dict) and b.get("type") == "tool_result" for b in c):
        return False
    t = text_of(c).lstrip()
    if t.startswith("Stop hook feedback"):
        return False
    return bool(t) and (not t.startswith("<") or t.startswith("<pasted_content"))


def opener(rec):
    """What began the next turn after the allowed retry."""
    if rec is None:
        return "session end"
    t = text_of((rec.get("message") or {}).get("content")).lstrip()
    if t.startswith("<task-notification>"):
        return "child notification"
    if human(rec):
        return "person"
    return "other: " + t[:40]


def claude():
    seen, ends, blocks = set(), [], []
    files = [f for root in CLAUDE for f in glob.glob(root + "/**/*.jsonl", recursive=True)]
    for f in files:
        try:
            recs = []
            for n, line in enumerate(open(f, errors="replace"), 1):
                if not line.strip():
                    continue
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                if (r.get("timestamp") or "") >= SINCE:
                    r["_line"] = n
                    recs.append(r)
        except OSError:
            continue
        idx = [i for i, r in enumerate(recs) if r.get("type") == "system" and r.get("subtype") == "stop_hook_summary"]
        prev_blocked = False
        for k, i in enumerate(idx):
            r = recs[i]
            if not any("claim-guard" in (h.get("command") or "") for h in r.get("hookInfos") or []):
                prev_blocked = False
                continue
            errs = [e for e in r.get("hookErrors") or [] if any(g in e for g in GUARD_TEXT)]
            # A retry follows a block with no person in between; its stop is the harness's allowed repeat.
            between = recs[idx[k - 1] + 1:i] if k else []
            retry = prev_blocked and not any(human(x) for x in between)
            dup = r["uuid"] in seen
            seen.add(r["uuid"])
            if not dup:
                ends.append(dict(harness="claude-code", day=r["timestamp"][:10], blocked=bool(errs), retry=retry))
            prev_blocked = bool(errs)
            if not errs or dup:
                continue
            nxt = idx[k + 1] if k + 1 < len(idx) else len(recs)
            seg = recs[i + 1:nxt]
            interrupted = next((x for x in seg if human(x)), None)
            if interrupted is not None:
                seg = seg[:seg.index(interrupted)]
            tools, cmds, reply = [], [], ""
            for s in seg:
                if s.get("type") != "assistant":
                    continue
                for b in (s.get("message") or {}).get("content") or []:
                    if not isinstance(b, dict):
                        continue
                    if b.get("type") == "tool_use":
                        tools.append(b.get("name"))
                        if b.get("name") == "Bash":
                            cmds.append(str((b.get("input") or {}).get("command", "")))
                    elif b.get("type") == "text":
                        reply += b.get("text", "")
            after = recs[nxt + 1:] if nxt < len(recs) else []
            first_after = next((x for x in after if x.get("type") == "user" and not x.get("isSidechain")
                                and not (isinstance((x.get("message") or {}).get("content"), list)
                                         and all(isinstance(b, dict) and b.get("type") == "tool_result"
                                                 for b in x["message"]["content"]))), None)
            prev = ""
            for s in reversed(recs[:i]):
                if s.get("type") == "assistant":
                    t = text_of((s.get("message") or {}).get("content"))
                    if t.strip():
                        prev = t
                        break
                if human(s):
                    break
            blocks.append(dict(
                harness="claude-code", ref=f"{f}#L{r['_line']}", ts=r["timestamp"], session=r.get("sessionId"),
                version=r.get("version"), variant=variant(errs[0]), reason=errs[0][:160],
                tools=tools, task_cmds=[c[:300] for c in cmds if TASKS_CMD.search(c)],
                park_text=[m.group(1)[:200] for c in cmds for m in PARK_TEXT.finditer(c)],
                waited=[t for t in tools if t in WAIT_TOOLS] + [c[:80] for c in cmds if re.search(r"\b(sleep|wait)\b", c)],
                reply=reply[:400], prev=prev[-400:], interrupted_by_person=interrupted is not None,
                retry_followed=nxt < len(recs), next_turn=opener(first_after)))
    return ends, blocks


def codex():
    """Codex records a Stop hook only when it blocks: a hook_prompt message. Turn ends are task_complete."""
    ends, blocks = [], []
    files = [f for root in CODEX for f in glob.glob(root + "/**/*.jsonl", recursive=True)
             if os.path.getmtime(f) >= 0]
    for f in files:
        try:
            lines = open(f, errors="replace").read().splitlines()
        except OSError:
            continue
        for n, line in enumerate(lines, 1):
            if '"task_complete"' not in line and "hook_prompt" not in line:
                continue
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if (r.get("timestamp") or "") < SINCE:
                continue
            p = r.get("payload") or {}
            if p.get("type") == "task_complete":
                ends.append(dict(harness="codex", day=r["timestamp"][:10], blocked=False, retry=False))
            elif r.get("type") == "response_item" and p.get("type") == "message" and p.get("role") == "user":
                t = "\n".join(c.get("text", "") for c in p.get("content") or [] if isinstance(c, dict))
                if "<hook_prompt" in t and any(g in t for g in GUARD_TEXT):
                    blocks.append(dict(harness="codex", ref=f"{f}#L{n}", ts=r["timestamp"],
                                       variant=variant(t), reason=t[:300]))
    return ends, blocks


def main():
    c_ends, c_blocks = claude()
    x_ends, x_blocks = codex()
    out = {"since": SINCE, "harnesses": {}}
    for name, ends, blocks in (("claude-code", c_ends, c_blocks), ("codex", x_ends, x_blocks)):
        first = [e for e in ends if not e["retry"]]
        by_day = collections.defaultdict(lambda: [0, 0])
        for e in first:
            by_day[e["day"]][0] += 1
            by_day[e["day"]][1] += e["blocked"]
        out["harnesses"][name] = dict(
            turn_ends=len(ends), first_stops=len(first), blocked=sum(e["blocked"] for e in first),
            by_day={d: dict(stops=v[0], blocked=v[1]) for d, v in sorted(by_day.items())},
            variants=collections.Counter(b["variant"] for b in blocks), blocks=sorted(blocks, key=lambda b: b["ts"]))
    json.dump(out, sys.stdout, indent=1, default=list)


if __name__ == "__main__":
    main()
