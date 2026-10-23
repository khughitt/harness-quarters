"""Print key skeletons (no values) of one recent live record per kind."""
import json, sys, glob, os
from pathlib import Path

def skel(v, depth=0):
    if isinstance(v, dict):
        return {k: skel(x, depth+1) for k, x in v.items()}
    if isinstance(v, list):
        return [skel(v[0], depth+1)] if v and isinstance(v[0], (dict, list)) else ["…"] if v else []
    if isinstance(v, str): return "s"
    if isinstance(v, bool): return v
    if v is None: return None
    return "n"

def kind_claude(r):
    t = r.get("type")
    if t == "system": return f"system/{r.get('subtype')}"
    if t == "attachment": return f"attachment/{(r.get('attachment') or {}).get('type')}"
    if t == "user":
        c = (r.get("message") or {}).get("content")
        o = (r.get("origin") or {}).get("kind")
        if isinstance(c, list) and c and isinstance(c[0], dict) and c[0].get("type") == "tool_result":
            return "user/tool_result"
        tags = []
        if r.get("isMeta"): tags.append("meta")
        if r.get("sourceToolUseID"): tags.append("srcTool")
        if o: tags.append(f"origin={o}")
        if isinstance(c, str) and c.startswith("[Request interrupted"): tags.append("interrupt")
        if isinstance(c, list) and c and isinstance(c[0], dict) and str(c[0].get("text","")).startswith("[Request interrupted"): tags.append("interrupt-list")
        return "user/" + ",".join(tags)
    if t == "assistant":
        m = r.get("message") or {}
        b = [x.get("type") for x in m.get("content") or [] if isinstance(x, dict)]
        return f"assistant/{m.get('model') == '<synthetic>' and 'synthetic' or 'model'}/{m.get('stop_reason')}/{','.join(b)}"
    return t

def main():
  pass
if __name__ == "__main__":
 want = set(sys.argv[2:])
 seen = {}
 files = sorted(glob.glob(os.path.expanduser(sys.argv[1]), recursive=True), key=os.path.getmtime, reverse=True)[:400]
 for f in files:
     for line in open(f, "rb"):
         try: r = json.loads(line)
         except Exception: continue
         k = kind_claude(r)
         if k not in seen:
             seen[k] = skel(r)
 for k in sorted(seen):
     if not want or any(w in k for w in want):
         print(k, json.dumps(seen[k]))
