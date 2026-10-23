"""Leading tag of user-record content per kind (tag names only)."""
import json, sys, glob, os, re, collections
sys.path.insert(0, os.path.dirname(__file__))
from keys import kind_claude
c = collections.Counter()
for f in sorted(glob.glob(os.path.expanduser(sys.argv[1])), key=os.path.getmtime, reverse=True)[:400]:
    for line in open(f, "rb"):
        try: r = json.loads(line)
        except Exception: continue
        k = kind_claude(r)
        if not k.startswith("user/") or k == "user/tool_result": continue
        m = (r.get("message") or {}).get("content")
        t = m if isinstance(m, str) else " ".join(b.get("text", "") for b in m or [] if isinstance(b, dict))
        lead = re.match(r"\s*(<[a-z-]+>|\[Request interrupted[^\]]*\]|Base directory|Stop hook|\S)", t or "")
        c[(k, lead.group(1) if lead and not lead.group(1)[0].isalnum() or (lead and lead.group(1) in ("Base directory","Stop hook")) else "word", isinstance(m, str))] += 1
for k, n in sorted(c.items(), key=str): print(k, n)
