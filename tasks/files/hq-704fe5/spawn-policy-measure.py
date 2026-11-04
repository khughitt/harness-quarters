"""Targeted read-only replay; labels come from the accepted seven-case audit."""
import collections
import json
import os
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path.cwd() / 'tools'))
from turn_pause import replay
from turn_pause.limits import Limits

START = '2026-11-01T00:00:00Z'
END = '2026-11-04T04:00:00Z'
CANDIDATES = {'current-30': 30, 'higher-60': 60, 'higher-90': 90,
              'warning-only': 2**63 - 1}
# A large finite surrogate disables only the default spawn stop in this observed
# sample. It is not a proposed configuration value or a new production API.


def measure(pilot):
    began = time.monotonic()
    cases = json.loads(Path('tasks/files/hq-7fb9d5/case-metrics.json').read_text())
    if pilot:
        cases = [c for c in cases if c['case'] in ('fam', 'spawn-tasks')]
    cases.append({'case': 'known-runaway', 'harness': replay.CONTROLLER[0],
                  'session': replay.CONTROLLER[1], 'cutoff': '2026-11-01T00:00:00Z',
                  'turn_start': None})
    selected = {c['session'] for c in cases}
    trees = {}
    for harness, sources in (('claude-code', replay.claude_trees(os.environ, None)),
                             ('codex', replay.codex_trees(os.environ, None))):
        for path, kids in sources:
            sid = next((s for s in selected if s in path), None)
            if sid:
                assert sid not in trees, f'duplicate root {sid}'
                trees[sid] = (harness, path, kids)
    assert selected == set(trees), f'missing roots {selected - set(trees)}'
    stats, problems = collections.Counter(), collections.Counter()
    parsed = {}
    files = 0
    for sid, (harness, path, kids) in trees.items():
        before = [(p, os.stat(p).st_size, os.stat(p).st_mtime_ns) for p in [path, *kids]]
        if harness == 'claude-code':
            root, steps = replay.read_claude_tree(path, kids)
        else:
            root, steps = replay.read_codex_tree(path, kids, replay.codex_unhooked(), stats)
        after = [(p, os.stat(p).st_size, os.stat(p).st_mtime_ns) for p in [path, *kids]]
        assert before == after, f'live source changed while reading {sid}'
        assert root == sid
        parsed[sid] = steps
        files += 1 + len(kids)
    output = {'window': [START, END], 'pilot': pilot, 'roots': len(trees), 'files': files,
              'candidates': CANDIDATES, 'cases': [], 'converter': dict(stats)}
    for case in cases:
        rows = {}
        control = case['case'] == 'known-runaway'
        for name, cap in CANDIDATES.items():
            turns = replay.replay(case['harness'], case['session'], parsed[case['session']],
                                  Limits(57600, 500, cap, 2), name,
                                  None if control else replay.ts(START),
                                  replay.ts(case['cutoff']), problems)
            if control:
                chosen = max(turns, key=lambda t: t.state.active)
            else:
                chosen = next(t for t in turns if replay.iso(t.start) == case['turn_start'])
            state = chosen.state
            assert state.limits == Limits(57600, 500, cap, 2), 'explicit budget needs separate treatment'
            assert state.spawns < 1000000, 'warning-only surrogate too small'
            rows[name] = {'turn_start': replay.iso(chosen.start),
                          'active_hours': round(state.active / 3600, 4),
                          'root_calls': state.calls, 'tree_spawns': state.spawns,
                          'hook_compactions': state.compactions,
                          'remaining_spawns': None if name == 'warning-only' else cap - state.spawns,
                          'first_pause': None if chosen.pause is None else {
                              'reason': chosen.pause.limit,
                              'active_hours': round(chosen.pause.active / 3600, 4),
                              'root_calls': chosen.pause.calls,
                              'tree_spawns': chosen.pause.spawns}}
        output['cases'].append({'case': case['case'], 'harness': case['harness'],
                                'root': case['session'], 'cutoff': case['cutoff'],
                                'out_of_window_control': control, 'results': rows})
    assert not problems, dict(problems)
    control = output['cases'][-1]['results']
    assert all(v['first_pause']['reason'] == 'calls' and v['first_pause']['root_calls'] == 501
               and v['first_pause']['active_hours'] < 16 for v in control.values())
    output['problems'] = dict(problems)
    output['elapsed_seconds'] = round(time.monotonic() - began, 2)
    return output


if __name__ == '__main__':
    pilot = sys.argv[1:] == ['--pilot']
    assert not sys.argv[1:] or pilot, 'only --pilot is supported'
    output = measure(pilot)
    destination = Path(__file__).with_name('spawn-policy-pilot.json' if pilot else 'spawn-policy-measurement.json')
    destination.write_text(json.dumps(output, indent=2) + '\n')
    print(json.dumps(output, indent=2))
