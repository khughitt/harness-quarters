"""Key skeletons of recent live Codex records per kind (no values except short enums)."""
import json, sys, glob, os
sys.path.insert(0, os.path.dirname(__file__))
from keys import skel
def kind(r):
    p = r.get("payload") or {}
    t = r.get("type")
    if t == "event_msg":
        if p.get("type") == "item_completed":
            it = p.get("item") or {}
            return f"event/item_completed/{it.get('type')}" + ("/q" if it.get("questions") else "")
        return f"event/{p.get('type')}"
    if t == "response_item":
        return f"ri/{p.get('type')}/{p.get('role','')}/{p.get('phase','-') if p.get('role')=='assistant' else ''}"
    if t == "session_meta":
        return "session_meta/" + ("spawn" if (p.get("source") or {}) and isinstance(p.get("source"), dict) else "root")
    return t
seen = {}
files = sorted(glob.glob(os.path.expanduser("~/.codex/sessions/2026/*/*/*.jsonl")), key=os.path.getmtime, reverse=True)[:150]
for f in files:
    first = True
    for line in open(f, "rb"):
        try: r = json.loads(line)
        except Exception: continue
        k = kind(r)
        if r.get("type") == "session_meta" and not first: k += "/second"
        if r.get("type") == "session_meta": first = False
        seen.setdefault(k, skel(r))
for k in sorted(seen):
    if not sys.argv[1:] or any(a in k for a in sys.argv[1:]):
        print(k, json.dumps(seen[k])[:1500])
