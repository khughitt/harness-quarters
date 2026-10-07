import json, os, collections, re, datetime
stops = json.load(open("stops.json"))
def t(s): return datetime.datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()
b = [s for s in stops if s["blocked"]]
ro = [s for s in b if s["resp"] == "reply-only"]
cache = {}
def recs(f):
    if f not in cache:
        out = []
        for line in open(f, errors="replace"):
            try: r = json.loads(line)
            except Exception: continue
            if r.get("timestamp"): out.append(r)
        cache.clear(); cache[f] = out
    return cache[f]
ro.sort(key=lambda s: (s["file"], s["ts"]))
kinds = collections.Counter(); lat = []; gaps = collections.defaultdict(list); pend = collections.Counter()
samples = collections.defaultdict(list)
for s in ro:
    R = recs(s["file"])
    i = next((k for k, r in enumerate(R) if r.get("type") == "system" and r.get("subtype") == "stop_hook_summary" and r["timestamp"] == s["ts"]), None)
    if i is None: continue
    # pending background work before the block: Agent/Bash background launches without a later notification before i
    launched = 0; notified = 0
    for r in R[:i]:
        if r.get("type") == "assistant":
            for blk in (r.get("message") or {}).get("content") or []:
                if isinstance(blk, dict) and blk.get("type") == "tool_use":
                    inp = blk.get("input") or {}
                    if blk.get("name") in ("Agent", "Task", "Workflow") or (blk.get("name") == "Bash" and inp.get("run_in_background")):
                        launched += 1
        elif r.get("type") == "user":
            c = (r.get("message") or {}).get("content")
            txt = c if isinstance(c, str) else " ".join(x.get("text", "") for x in c if isinstance(x, dict) and x.get("type") == "text") if isinstance(c, list) else ""
            notified += txt.count("<task-notification>")
        elif r.get("type") == "queue-operation":
            notified += str(r.get("content", "")).count("<task-notification>") if r.get("operation") == "enqueue" else 0
    s["pending"] = launched - notified
    # closing stop
    j = next((k for k in range(i+1, len(R)) if R[k].get("type") == "system" and R[k].get("subtype") == "stop_hook_summary"), None)
    if j is None: kinds["no-closing-stop"] += 1; continue
    lat.append(t(R[j]["timestamp"]) - t(s["ts"]))
    nxt = None
    for r in R[j+1:]:
        if r.get("type") == "user" and not r.get("isSidechain"):
            c = (r.get("message") or {}).get("content")
            txt = c if isinstance(c, str) else " ".join(x.get("text", "") for x in c if isinstance(x, dict) and x.get("type") == "text") if isinstance(c, list) else ""
            if not txt.strip(): continue
            if r.get("isMeta") and "task-notification" not in txt: continue
            nxt = ("child-notification" if "<task-notification>" in txt else "human" if (not txt.lstrip().startswith("<") or txt.lstrip().startswith("<pasted_content")) else "other-injected:" + txt.lstrip()[:30]); gap = t(r["timestamp"]) - t(R[j]["timestamp"]); break
    if nxt is None: nxt = "session-end"; gap = None
    s["next"] = nxt
    kinds[nxt] += 1
    if gap is not None: gaps[nxt].append(gap)
    if len(samples[nxt]) < 6: samples[nxt].append((s["prev"][:160].replace("\n", " "), s["text"][:160].replace("\n", " ")))
def q(xs):
    xs = sorted(xs)
    return dict(n=len(xs), med=round(xs[len(xs)//2], 1), p90=round(xs[int(len(xs)*.9)], 1), max=round(xs[-1], 1), sum=round(sum(xs))) if xs else None
print("what followed a reply-only block:", kinds)
print("extra round latency s:", q(lat))
for k, v in gaps.items(): print("gap to next input", k, q(v))
print("pending-launch heuristic >0:", sum(1 for s in ro if s.get("pending", 0) > 0), "of", len(ro))
print(collections.Counter((s.get("next"), s.get("pending", 0) > 0) for s in ro))
for k, v in samples.items():
    print("==", k)
    for p, a in v: print("  BEFORE:", p, "\n  AFTER :", a)
# same-session repeated blocks
per = collections.Counter(s["sid"] for s in b)
print("blocks per session:", q(list(per.values())), per.most_common(5))
# projects
print(collections.Counter(re.sub(r"--worktrees.*", "", os.path.basename(os.path.dirname(s["file"]))) for s in b).most_common(12))
json.dump(ro, open("ro.json", "w"))
