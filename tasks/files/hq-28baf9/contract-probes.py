"""Read-only controls for revision 8's target-window and ambiguous-final contracts."""
import argparse
import json
from pathlib import Path
import sys
import tempfile
import time
from types import SimpleNamespace


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--obs', required=True, type=Path)
    parser.add_argument('--fixtures', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    sys.path.insert(0, str(args.obs))
    import session_logs_query as query
    import session_logs_show as show
    results = {}
    for name, physical, target, cap, expected in (
        ('late_target', list(range(1, 13)), 9, 1,
         {'records': 12, 'shown': 1, 'before': 8, 'after': 3}),
        ('target_exemption_without_omission', [3, 3, 3], 3, 1,
         {'records': 3, 'shown': 3, 'before': 0, 'after': 0}),
        ('noncontiguous_target', [3, 5, 3], 3, 1,
         {'records': 3, 'shown': 2, 'before': 0, 'after': 0}),
    ):
        items = [{'type': 'record', 'line': line, 'ref': str(i)}
                 for i, line in enumerate(physical)]
        state = SimpleNamespace(target=SimpleNamespace(line=target), limit=cap,
            units=0, hit=False, turn_cut=None,
            _turn_items=lambda *_: items, _turn_object=lambda _: {'type': 'turn'},
            _item=lambda _, item, __: item)
        emitted = list(show._Show._target_turn(state, SimpleNamespace(read=None), {}, {}))
        assert state.turn_cut == expected and state.hit
        assert len(emitted) - 1 == expected['shown']
        results[name] = {'verdict': 'pass', 'turn_cut': state.turn_cut}
    path = args.fixtures / 'turns/.codex/sessions/2026/10/12/rollout-2026-10-12T11-00-00-01900000-0000-7000-8000-0000000000f2.jsonl'
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    pattern = ''.join(block.get('text', '') for block in rows[5]['payload']['content'])
    assert pattern
    with tempfile.TemporaryDirectory(prefix='hq-r26-controls-') as directory:
        env = {'PATH': '/usr/bin:/bin', 'HOME': directory,
               'XDG_CONFIG_HOME': directory + '/config', 'XDG_STATE_HOME': directory + '/state'}
        now = int(time.time() * 1000)
        final = list(query.search(query.Query(pattern=pattern, file=[str(path)], mode='final'), env, now))
        records = list(query.search(query.Query(pattern=pattern, file=[str(path)]), env, now))
        turns = list(query.search(query.Query(file=[str(path)], mode='final'), env, now))
        assert final[-1]['outcome'] == 'not_found' and final[-1]['outcome_basis'] == 'explicit_files'
        assert len(final) == 1
        assert records[-1]['outcome'] == 'found'
        assert any(item.get('copy') == 'ambiguous' for item in records[:-1])
        assert turns[-1]['outcome'] == 'found'
        assert any(item.get('copy') == 'ambiguous' and 'final' not in item for item in turns[:-1])
        results['ambiguous_final'] = {'verdict': 'pass', 'pattern_final': 'not_found',
            'pattern_records': 'found', 'unfiltered_turns': 'found',
            'final_basis': final[-1]['outcome_basis']}
    args.out.write_text(json.dumps(results, indent=2, sort_keys=True) + '\n')
    print(json.dumps(results, sort_keys=True))


if __name__ == '__main__':
    main()
