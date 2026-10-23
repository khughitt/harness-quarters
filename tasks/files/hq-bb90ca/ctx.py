"""Print kind sequences (and key skeletons of chosen neighbours) around anchor kinds. No text values."""
import json, sys, glob, os, re
sys.path.insert(0, os.path.dirname(__file__))
from keys import kind_claude, skel
anchor = sys.argv[2]; before = int(sys.argv[3]); after = int(sys.argv[4]); maxn = int(sys.argv[5])
files = sorted(glob.glob(os.path.expanduser(sys.argv[1]), recursive=True), key=os.path.getmtime, reverse=True)[:400]
n = 0
for f in files:
    rs = []
    for line in open(f, "rb"):
        try: rs.append(json.loads(line))
        except Exception: pass
    ks = [kind_claude(r) for r in rs]
    for i, k in enumerate(ks):
        if anchor in k:
            print("--", n)
            for j in range(max(0, i-before), min(len(rs), i+after+1)):
                extra = ""
                r = rs[j]
                if r.get("type") == "system" and r.get("subtype") == "stop_hook_summary":
                    extra = f" hookErrors={skel(r.get('hookErrors'))} prevented={r.get('preventedContinuation')}"
                if r.get("type") == "system" and r.get("subtype") == "local_command":
                    extra = " tags=" + ",".join(re.findall(r"<([a-z-]+)>", r.get("content",""))) + f" keys={sorted(r)}"
                if r.get("type") == "user" and r.get("isMeta"):
                    extra = f" keys={sorted(r)}"
                print(("> " if j == i else "  ") + ks[j] + extra)
            n += 1
            if n >= maxn: sys.exit()
