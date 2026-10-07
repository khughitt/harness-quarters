import json, glob, os, collections
stops = json.load(open("stops.json"))
FIX = "2026-09-28T10:41"
b = [s for s in stops if s["blocked"]]
ro = [s for s in b if s["resp"] == "reply-only"]
def med(xs): xs = sorted(xs); return xs[len(xs)//2] if xs else None
for name, g in (("before fix", [s for s in ro if s["ts"] < FIX]), ("after fix", [s for s in ro if s["ts"] >= FIX])):
    print(name, "n", len(g), "median out tokens", med([s["out"] for s in g]), "median reply chars", med([s["text_len"] for s in g]), "sum out", sum(s["out"] for s in g))
main = [s for s in stops if s["has_guard"]]
for name, g in (("before fix", [s for s in main if s["ts"] < FIX]), ("after fix", [s for s in main if s["ts"] >= FIX])):
    print(name, "stops", len(g), "blocked", sum(s["blocked"] for s in g), "non-reply responses", collections.Counter(s.get("resp") for s in g if s["blocked"]))
# totals for the sessions with the guard, since 09-24
sids = {s["sid"] for s in main}
files = {s["file"] for s in main}
tot = collections.Counter(); seen = set()
for f in files:
    for line in open(f, errors="replace"):
        if '"assistant"' not in line: continue
        try: r = json.loads(line)
        except Exception: continue
        if r.get("type") != "assistant" or (r.get("timestamp") or "")[:10] < "2026-09-24": continue
        rid = r.get("requestId")
        if rid in seen: continue
        seen.add(rid)
        u = (r.get("message") or {}).get("usage") or {}
        tot["requests"] += 1
        tot["out"] += u.get("output_tokens", 0)
        tot["cache_read"] += u.get("cache_read_input_tokens", 0)
        tot["cache_write"] += u.get("cache_creation_input_tokens", 0)
        tot["uncached"] += u.get("input_tokens", 0)
print("main-thread totals in guarded sessions:", dict(tot))
print("reply-only rounds: requests", len(ro), "out", sum(s["out"] for s in ro), "input(all)", sum(s["inp"] for s in ro), "cache_write", sum(s["cache_w"] for s in ro))
print("share of requests", f"{len(ro)/tot['requests']:.1%}", "share of out", f"{sum(s['out'] for s in ro)/tot['out']:.2%}", "share of input", f"{sum(s['inp'] for s in ro)/(tot['cache_read']+tot['cache_write']+tot['uncached']):.1%}", "share of cache_write", f"{sum(s['cache_w'] for s in ro)/tot['cache_write']:.1%}")
# the 29 that acted
for s in b:
    if s["resp"] != "reply-only":
        print(s["ts"][:16], s["resp"], s["n_tools"], "| BEFORE:", s["prev"][:150].replace("\n", " "))
