#!/usr/bin/env python3
"""Isolated real-entry latency gate; --pilot exercises every case before a long run."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import math
import os
from pathlib import Path
import subprocess
import tempfile
import time

from turn_pause.history import append_event, encode, snapshot
from turn_pause.state import Store, state_dir

TOOLS = Path(__file__).resolve().parent
ENTRY = TOOLS / 'turn-pause'
FIXTURES = TOOLS / 'fixtures/turn-pause/hooks'


def percentile(values, fraction):
    return sorted(values)[math.ceil(len(values) * fraction) - 1]


def call(harness, event, payload, limits, env):
    started = time.perf_counter()
    result = subprocess.run([str(ENTRY), '--harness', harness, '--limits', str(limits), event],
                            input=json.dumps(payload), capture_output=True, text=True, env=env, timeout=10)
    elapsed = 1000 * (time.perf_counter() - started)
    assert result.returncode == 0 and not result.stderr, result.stderr
    assert not result.stdout.strip(), result.stdout
    return elapsed


def measure(harness, concurrent, samples, base):
    directory = base / (harness + ('-concurrent' if concurrent else '-serial'))
    directory.mkdir()
    for name in ('home', 'state', 'run', 'bin', 'work'):
        (directory / name).mkdir()
    stub = directory / 'bin/notify-send'
    stub.write_text('#!/bin/sh\nexit 0\n'); stub.chmod(0o700)
    env = {'PATH': str(directory / 'bin') + ':/usr/bin:/bin', 'HOME': str(directory / 'home'),
           'XDG_STATE_HOME': str(directory / 'state'), 'XDG_RUNTIME_DIR': str(directory / 'run')}
    limits = directory / 'limits.toml'
    limits.write_text('active_seconds = 100000000\ncalls = 100000000\nspawns = 100000000\ncompactions = 100000000\n')
    filename = 'claude-code-subagent-bash-denied.json' if harness == 'claude-code' else 'codex-exec_command-yield.json'
    fixture = json.loads((FIXTURES / filename).read_text())
    native = next(row['payload'] for row in fixture['records']
                  if row['payload'].get('hook_event_name') == 'PreToolUse' and row['payload'].get('tool_name') == 'Bash')
    roots = ['bench-' + str(i) for i in range(2 if concurrent else 1)]
    store = Store(state_dir(env))
    for root in roots:
        prompt = dict(native, session_id=root, cwd=str(directory / 'work'), prompt='synthetic benchmark turn')
        prompt.pop('agent_id', None); prompt.pop('agent_type', None)
        call(harness, 'UserPromptSubmit', prompt, limits, env)
        with store.locked(harness, root) as record:
            for i in range(128):
                append_event(record, 'warning', time.time(), reason='calls',
                             snapshot=snapshot(record.state, compactions_counted=harness == 'claude-code'))
    def client(root, worker):
        durations = []
        for i in range(samples):
            payload = dict(native, session_id=root, cwd=str(directory / 'work'),
                           tool_name='Bash', tool_input={'command': 'true'},
                           tool_use_id=f'{root}-{worker}-{i}', hook_event_name='PreToolUse')
            payload.pop('agent_id', None); payload.pop('agent_type', None)
            if worker:
                payload['agent_id'], payload['agent_type'] = 'bench-worker', 'general-purpose'
            durations.append(call(harness, 'PreToolUse', payload, limits, env))
            payload.update(hook_event_name='PostToolUse', tool_response='')
            call(harness, 'PostToolUse', payload, limits, env)
        return durations
    if concurrent:
        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = [pool.submit(client, root, worker) for root in roots for worker in (False, True)]
            durations = [value for future in futures for value in future.result()]
    else:
        durations = client(roots[0], False)
    counts = []
    for root in roots:
        record = store.read_record(harness, root)
        assert record.state.turn.calls == samples and not record.state.turn.in_flight
        assert len(record.events) == 128 and len(encode(record.events).encode()) <= 131072
        counts.append(dict(root=root, calls=record.state.turn.calls, events=len(record.events)))
    p99 = percentile(durations, .99)
    return dict(harness=harness, case='concurrent' if concurrent else 'serial', samples=len(durations),
                p50_ms=percentile(durations, .5), p99_ms=p99, counts=counts, passed=p99 < 50)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pilot', action='store_true')
    parser.add_argument('--samples', type=int, default=1000)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.samples < 1:
        parser.error('--samples must be positive')
    workers = int(os.environ.get('OPS_WORKERS', '0'))
    result = dict(version=1, pilot=args.pilot, workers=workers, target_p99_ms=50, cases=[])
    if workers < 4:
        result.update(status='refused', reason='four positive OPS_WORKERS required for concurrency')
        code = 77
    else:
        with tempfile.TemporaryDirectory(prefix='turn-pause-measure-') as temporary:
            for harness in ('claude-code', 'codex'):
                for concurrent in (False, True):
                    result['cases'].append(measure(harness, concurrent, 1 if args.pilot else args.samples,
                                                   Path(temporary)))
        result['status'] = 'passed' if all(case['passed'] for case in result['cases']) else 'failed'
        code = 0 if result['status'] == 'passed' else 1
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))
    return code


if __name__ == '__main__':
    raise SystemExit(main())
