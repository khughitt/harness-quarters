import json, glob, os, collections, statistics, sys, re
ROOT = os.path.expanduser("~/.claude/projects")
SINCE = "2026-09-24"
seen = set()
stops = []   # dicts
files = glob.glob(ROOT + "/**/*.jsonl", recursive=True)
for f in files:
    recs = []
    try:
        for line in open(f, errors="replace"):
            if not line.strip(): continue
            try: r = json.loads(line)
            except Exception: continue
            if not r.get("timestamp") or r["timestamp"][:10] < SINCE: continue
            recs.append(r)
    except OSError:
        continue
    idx = [i for i, r in enumerate(recs) if r.get("type") == "system" and r.get("subtype") == "stop_hook_summary"]
    for k, i in enumerate(idx):
        r = recs[i]
        if r["uuid"] in seen: continue
        seen.add(r["uuid"])
        errs = r.get("hookErrors") or []
        guard = [h for h in r.get("hookInfos") or [] if "claim-guard" in h.get("command", "")]
        blocked = any("claim" in e for e in errs)
        other_err = [e for e in errs if "live task claim" not in e]
        d = dict(file=f, ts=r["timestamp"], sid=r.get("sessionId"), side=bool(r.get("isSidechain")) or "/subagents/" in f,
                 blocked=blocked, other_err=other_err, guard_ms=(guard[0].get("durationMs") if guard else None),
                 has_guard=bool(guard), all_ms=[h.get("durationMs") for h in r.get("hookInfos") or []])
        if blocked:
            end = idx[k+1] if k+1 < len(idx) else len(recs)
            seg = recs[i+1:end]
            reqs = {}
            cmds = []; tools = []; text = ""
            human = False
            for s in seg:
                if s.get("type") == "user" and not s.get("isMeta"):
                    c = (s.get("message") or {}).get("content")
                    if isinstance(c, str) and not c.lstrip().startswith("<"):
                        human = True; break
                if s.get("type") != "assistant": continue
                m = s.get("message") or {}
                reqs[s.get("requestId")] = m.get("usage") or {}
                for b in m.get("content") or []:
                    if not isinstance(b, dict): continue
                    if b.get("type") == "tool_use":
                        tools.append(b.get("name"))
                        if b.get("name") == "Bash": cmds.append(str((b.get("input") or {}).get("command", "")))
                    elif b.get("type") == "text": text += b.get("text", "")
            d["closed"] = k+1 < len(idx) and not human
            d["next_ts"] = recs[end]["timestamp"] if end < len(recs) else None
            d["n_req"] = len(reqs)
            d["out"] = sum(u.get("output_tokens", 0) for u in reqs.values())
            d["inp"] = sum(u.get("input_tokens", 0) + u.get("cache_read_input_tokens", 0) + u.get("cache_creation_input_tokens", 0) for u in reqs.values())
            d["cache_w"] = sum(u.get("cache_creation_input_tokens", 0) for u in reqs.values())
            d["tools"] = tools; d["text_len"] = len(text); d["text"] = text[:300]
            joined = "\n".join(cmds)
            park = bool(re.search(r"\btasks\b[^\n]*\bpark\b", joined)); done = bool(re.search(r"\btasks\b[^\n]*\b(done|drop)\b", joined))
            work = [t for t in tools]
            n_other = len(tools) - sum(1 for c in cmds if re.search(r"\btasks\b[^\n]*\b(park|done|drop|show|claims|list|note)\b", c))
            if not tools: d["resp"] = "reply-only"
            elif n_other <= 1 and (park or done): d["resp"] = "park" if park else "done"
            elif park or done: d["resp"] = "work+park/done"
            else: d["resp"] = "work"
            d["n_tools"] = len(tools)
            # preceding assistant text
            prev = ""
            for s in reversed(recs[:i]):
                if s.get("type") == "assistant":
                    for b in (s.get("message") or {}).get("content") or []:
                        if isinstance(b, dict) and b.get("type") == "text": prev = b.get("text", "") + prev
                    if prev: break
            d["prev"] = prev[:300]
        stops.append(d)
json.dump(stops, open("stops.json", "w"))
main = [s for s in stops if s["has_guard"]]
print("files", len(files), "stops", len(stops), "with guard installed", len(main), "sidechain", sum(s["side"] for s in stops))
b = [s for s in main if s["blocked"]]
print("blocked", len(b), f"{len(b)/max(1,len(main)):.1%}")
print("sessions w/ guard", len({s['sid'] for s in main}), "sessions w/ >=1 block", len({s['sid'] for s in b}))
print("other hook errors:", collections.Counter(e[:80] for s in stops for e in s["other_err"]).most_common(8))
by_day = collections.Counter(); bl_day = collections.Counter()
for s in main:
    by_day[s["ts"][:10]] += 1; bl_day[s["ts"][:10]] += s["blocked"]
for dday in sorted(by_day): print(dday, by_day[dday], bl_day[dday], f"{bl_day[dday]/by_day[dday]:.0%}")
print("responses", collections.Counter(s["resp"] for s in b))
def q(xs):
    xs = sorted(xs)
    if not xs: return None
    return dict(n=len(xs), med=xs[len(xs)//2], p90=xs[int(len(xs)*.9)], max=xs[-1], sum=sum(xs))
for resp in ("reply-only", "park", "done", "work+park/done", "work"):
    g = [s for s in b if s["resp"] == resp]
    print(resp, "out", q([s["out"] for s in g]), "\n   inp", q([s["inp"] for s in g]), "\n   reqs", q([s["n_req"] for s in g]), "tools", q([s["n_tools"] for s in g]))
gm = [s["guard_ms"] for s in main if s["guard_ms"] is not None]
print("guard ms (allowed stops)", q(gm))
allh = [sum(x for x in s["all_ms"] if x) for s in stops if s["all_ms"]]
print("all stop hooks ms", q(allh))
