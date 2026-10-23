"""Print enum-like field values (short tokens only) for chosen kinds. Never prints free text."""
import json, sys, glob, os, collections
sys.path.insert(0, os.path.dirname(__file__))
from keys import kind_claude
FIELDS = ["promptSource", "turnOrigin", "origin.kind", "origin.producer", "attachment.commandMode",
          "attachment.origin.kind", "attachment.origin.producer", "level", "stopReason", "commandRun.command",
          "renderedRole", "attachment.hookEvent", "userType", "entrypoint", "sessionKind", "queuePriority", "message.stop_sequence", "isApiErrorMessage", "turnCompanion"]
def get(r, p):
    for k in p.split("."):
        r = r.get(k) if isinstance(r, dict) else None
    return r
c = collections.defaultdict(collections.Counter)
files = sorted(glob.glob(os.path.expanduser(sys.argv[1])), key=os.path.getmtime, reverse=True)[:400]
for f in files:
    for line in open(f, "rb"):
        try: r = json.loads(line)
        except Exception: continue
        k = kind_claude(r)
        if not any(a in k for a in sys.argv[2:]): continue
        for p in FIELDS:
            v = get(r, p)
            if v is not None and (not isinstance(v, str) or len(v) < 30):
                c[(k, p)][v] += 1
for (k, p), cnt in sorted(c.items(), key=str):
    print(k, p, dict(cnt.most_common(6)))
