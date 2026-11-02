"""One read-only parse per stored tree; replay candidate defaults through the existing engine."""
import collections
import json
import os
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path.cwd() / 'tools'))
from turn_pause import replay
from turn_pause.limits import Limits

START = replay.ts('2026-10-02T00:00:00Z')
END = replay.ts('2026-11-02T20:00:00Z')
HOURS = (4, 8, 12, 16, 24)
CASE = 'c67f4b5f-818d-4533-83b0-172009b992c2'

def summary(turns):
    default = [t for t in turns if t.state.limits == Limits(hours * 3600, 500, 30, 2)]
    active = [t.state.active / 3600 for t in default]
    return dict(turns=len(turns), default_turns=len(default), explicit_budget_turns=len(turns)-len(default),
                paused=dict(collections.Counter(t.pause.limit for t in default if t.pause)),
                active_over=sum(a > hours for a in active),
                active_only=sum(t.state.active > hours*3600 and t.state.calls <= 500 and t.state.spawns <= 30
                                and t.state.compactions <= 2 for t in default),
                active_hours={f'p{q}': round(replay._pct(active, q/100),3) for q in (50,90,99,99.9)},
                max_active_hours=round(max(active, default=0),3))

if __name__ == '__main__':
    pilot = '--pilot' in sys.argv
    turns_by = {h: [] for h in HOURS}
    stats, problems = collections.Counter(), collections.Counter()
    files = roots = 0
    began = time.monotonic()
    for harness, trees in [('claude-code', replay.claude_trees(os.environ, START)),
                            ('codex', replay.codex_trees(os.environ, START))]:
        for path, kids in trees:
            if pilot and CASE not in path and replay.CONTROLLER[1] not in path:
                continue
            if harness == 'claude-code':
                root, steps = replay.read_claude_tree(path, kids)
            else:
                root, steps = replay.read_codex_tree(path, kids, replay.codex_unhooked(), stats)
            roots += 1
            files += 1 + len(kids)
            for hours in HOURS:
                turns_by[hours] += replay.replay(harness, root, steps, Limits(hours*3600,500,30,2),
                                                f'candidate-{hours}h', START, END, problems)
    output = dict(window=['2026-10-02T00:00:00Z','2026-11-02T20:00:00Z'], pilot=pilot,
                  roots=roots, files=files, elapsed_seconds=round(time.monotonic()-began,2),
                  converter=dict(stats), problems=dict(problems), candidates={})
    for hours, turns in turns_by.items():
        output['candidates'][hours] = {h: summary([t for t in turns if t.harness == h]) for h in ('claude-code','codex')}
        assert all(t.state.active >= 0 for t in turns)
    details=[]
    for t in turns_by[16]:
        s=t.state
        if s.active > 8*3600 or t.root in (CASE,replay.CONTROLLER[1]):
            details.append(dict(harness=t.harness,root=t.root,start=replay.iso(t.start),
                                active_hours=round(s.active/3600,3), calls=s.calls,spawns=s.spawns,
                                compactions=s.compactions,limits=s.limits._asdict(),
                                pause=None if not t.pause else dict(limit=t.pause.limit,active_hours=round(t.pause.active/3600,3))))
    output['tail_at_16h']=details
    assert roots > 0 and all(turns_by[h] for h in HOURS)
    print(json.dumps(output,indent=2))
