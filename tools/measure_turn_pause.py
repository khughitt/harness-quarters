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
import threading
import time

from turn_pause.history import append_event, encode, snapshot
from turn_pause.spend import HOST_FILE, SIGNAL_NAME, read_latch
from turn_pause.state import Store, state_dir, write_atomic

__all__ = (
    'TOOLS',
    'ENTRY',
    'FIXTURES',
    'NATIVE_ROOTS',
    'NATIVE_WORKERS',
    'OTHER_ROOT',
    'SPEND_MODES',
    'SPEND_REWRITE_CALLS',
    'STALE_AGE_MS',
    'percentile',
    'native_call_id',
    'loadavg',
    'spend_signal_bytes',
    'call',
    'measure',
    'main',
)

TOOLS = Path(__file__).resolve().parent
ENTRY = TOOLS / 'turn-pause'
FIXTURES = TOOLS / 'fixtures/turn-pause/hooks'
NATIVE_ROOTS = {
    'claude-code': ('7f0c44c1-4c1f-40da-9a15-aa0917fa0728', '7f0c44c1-4c1f-40da-9a15-aa0917fa0729'),
    'codex': ('01a19737-5420-7280-9b27-80cdf4ba57c6', '01a19737-5420-7280-9b27-80cdf4ba57c7'),
}
NATIVE_WORKERS = {
    'claude-code': ('a620dc1cd95e3a1c5', 'general-purpose'),
    'codex': ('01a19737-d284-73c3-a7bf-a465efd1d1d0', 'default'),
}
OTHER_ROOT = '00000000-0000-0000-0000-000000000000'
SPEND_MODES = ('fresh', 'stale', 'none')
SPEND_REWRITE_CALLS = 120
STALE_AGE_MS = 20 * 60 * 1000


def percentile(values, fraction):
    return sorted(values)[math.ceil(len(values) * fraction) - 1]


def native_call_id(harness, root, worker, index):
    if harness == 'claude-code':
        return f'toolu_0169FJKnwvy5sno{root[-1]}{int(worker)}{index:07d}'
    return f'exec-d731f896-35e6-4553-0{root[-1]}0{int(worker)}-{index:012d}'


def loadavg():
    return Path('/proc/loadavg').read_text().strip()


def spend_signal_bytes(harness, generated_at):
    payload = {
        'schema': 1,
        'generated_at': generated_at,
        'status': 'ok',
        'stale_after_ms': 600000,
        'baseline': {
            'id': 'bench',
            'computed_at': generated_at,
            'harnesses': {
                'claude-code': {'state': 'ok', 'threshold': 500_000_000, 'trees': 100},
                'codex': {'state': 'ok', 'threshold': 500_000_000, 'trees': 100},
            },
        },
        'credits': {},
        'coverage': {
            'files_seen': 1,
            'files_unfinished': 0,
            'files_starved': [],
            'files_malformed': [],
            'files_unparsed': [],
            'trees_unfinished': [],
        },
        'trees': [{
            'root': f'{harness}:{OTHER_ROOT}',
            'harness': harness,
            'root_session': OTHER_ROOT,
            'root_resolved': True,
            'episode': f'{harness}:{OTHER_ROOT}@1',
            'value': 700_000_000,
            'threshold': 500_000_000.0,
            'ratio': 1.4,
            'window_hours': 72,
            'measured_at': generated_at,
            'complete': True,
            'credits_drawn_24h': None,
        }],
    }
    return json.dumps(payload).encode()


def call(harness, event, payload, limits, env, entry=ENTRY):
    started = time.perf_counter()
    result = subprocess.run([str(entry), '--harness', harness, '--limits', str(limits), event],
                            input=json.dumps(payload), capture_output=True, text=True, env=env, timeout=10)
    elapsed = 1000 * (time.perf_counter() - started)
    assert result.returncode == 0 and not result.stderr, result.stderr
    assert not result.stdout.strip(), result.stdout
    return elapsed


def measure(harness, concurrent, samples, base, entry=ENTRY, seed_events=True, spend='none'):
    if spend not in SPEND_MODES:
        raise ValueError(f'unsupported spend mode: {spend!r}')
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
    signal_path = None
    last_signal_ms = 0
    if spend != 'none':
        obs_dir = directory / 'state' / 'obs'
        obs_dir.mkdir(mode=0o700)
        signal_path = obs_dir / SIGNAL_NAME
        initial_ms = int(time.time() * 1000) - (STALE_AGE_MS if spend == 'stale' else 0)
        last_signal_ms = initial_ms
        write_atomic(str(signal_path), spend_signal_bytes(harness, initial_ms))
    filename = 'claude-code-subagent-bash-denied.json' if harness == 'claude-code' else 'codex-exec_command-yield.json'
    fixture = json.loads((FIXTURES / filename).read_text())
    native = next(row['payload'] for row in fixture['records']
                  if row['payload'].get('hook_event_name') == 'PreToolUse' and row['payload'].get('tool_name') == 'Bash')
    roots = list(NATIVE_ROOTS[harness][:2 if concurrent else 1])
    worker_id, worker_type = NATIVE_WORKERS[harness]
    store = Store(state_dir(env))
    for root in roots:
        prompt = dict(native, session_id=root, cwd=str(directory / 'work'), prompt='synthetic benchmark turn')
        prompt.pop('agent_id', None); prompt.pop('agent_type', None)
        call(harness, 'UserPromptSubmit', prompt, limits, env, entry=entry)
        state_path = Path(state_dir(env)) / f'{harness}-{root}.json'
        raw = json.loads(state_path.read_text())
        if seed_events and raw.get('version') == 1:
            with store.locked(harness, root) as record:
                for _ in range(128):
                    append_event(record, 'warning', time.time(), reason='calls',
                                 snapshot=snapshot(record.state, compactions_counted=harness == 'claude-code'))
    load_before = loadavg()
    call_lock = threading.Lock()
    signal_lock = threading.Lock()
    call_num = 0
    def client(root, worker):
        nonlocal call_num, last_signal_ms
        durations = []
        for i in range(samples):
            payload = dict(native, session_id=root, cwd=str(directory / 'work'),
                           tool_name='Bash', tool_input={'command': 'true'},
                           tool_use_id=native_call_id(harness, root, worker, i), hook_event_name='PreToolUse')
            payload.pop('agent_id', None); payload.pop('agent_type', None)
            if worker:
                payload['agent_id'], payload['agent_type'] = worker_id, worker_type
            if spend == 'fresh':
                with call_lock:
                    call_num += 1
                    should_rewrite = call_num % SPEND_REWRITE_CALLS == 0
                if should_rewrite:
                    with signal_lock:
                        last_signal_ms = max(int(time.time() * 1000), last_signal_ms + 1)
                        now_ms = last_signal_ms
                        write_atomic(str(signal_path), spend_signal_bytes(harness, now_ms))
            durations.append(call(harness, 'PreToolUse', payload, limits, env, entry=entry))
            payload.update(hook_event_name='PostToolUse', tool_response='')
            call(harness, 'PostToolUse', payload, limits, env, entry=entry)
        return durations
    if concurrent:
        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = [pool.submit(client, root, worker) for root in roots for worker in (False, True)]
            durations = [value for future in futures for value in future.result()]
    else:
        durations = client(roots[0], False)
    load_after = loadavg()
    counts = []
    for root in roots:
        state_path = Path(state_dir(env)) / f'{harness}-{root}.json'
        raw = json.loads(state_path.read_text())
        if spend != 'none':
            assert raw.get('version') == 1
        if raw.get('version') == 1:
            record = store.read_record(harness, root)
            assert record.state.turn.calls == samples and not record.state.turn.in_flight
            if seed_events:
                assert len(record.events) == 128 and len(encode(record.events).encode()) <= 131072
            if spend != 'none':
                assert record.state.spend_cache is not None and record.state.spend_cache.error is None
            counts.append(dict(root=root, calls=record.state.turn.calls, events=len(record.events),
                               state_bytes=state_path.stat().st_size))
        else:
            assert raw['turn']['calls'] == samples and not raw['turn']['in_flight']
            counts.append(dict(root=root, calls=raw['turn']['calls'], events=0,
                               state_bytes=state_path.stat().st_size))
    if spend == 'fresh':
        assert (Path(state_dir(env)) / HOST_FILE).is_file()
        latch = read_latch(state_dir(env))
        assert latch.seen_fresh is True and latch.outage is None
    elif spend == 'stale':
        assert (Path(state_dir(env)) / HOST_FILE).is_file()
        latch = read_latch(state_dir(env))
        assert latch.outage is not None and latch.outage['state'] == 'stale'
    p99 = percentile(durations, .99)
    return dict(harness=harness, case='concurrent' if concurrent else 'serial', samples=len(durations),
                p50_ms=percentile(durations, .5), p95_ms=percentile(durations, .95), p99_ms=p99,
                max_ms=max(durations), mean_ms=sum(durations) / len(durations),
                loadavg_before=load_before, loadavg_after=load_after, counts=counts, passed=p99 < 50)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pilot', action='store_true')
    parser.add_argument('--samples', type=int, default=1000)
    parser.add_argument('--entry', type=Path, default=ENTRY)
    parser.add_argument('--no-seed-events', action='store_true')
    parser.add_argument('--spend', choices=SPEND_MODES, default='none')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.samples < 1:
        parser.error('--samples must be positive')
    entry = args.entry.resolve()
    seed_events = not args.no_seed_events
    workers = int(os.environ.get('OPS_WORKERS', '0'))
    result = dict(version=1, pilot=args.pilot, workers=workers, target_p99_ms=50,
                  seed_events=seed_events, spend=args.spend, cases=[])
    if workers < 4:
        result.update(status='refused', reason='four positive OPS_WORKERS required for concurrency')
        code = 77
    else:
        with tempfile.TemporaryDirectory(prefix='turn-pause-measure-') as temporary:
            for harness in ('claude-code', 'codex'):
                for concurrent in (False, True):
                    result['cases'].append(measure(harness, concurrent, 1 if args.pilot else args.samples,
                                                   Path(temporary), entry=entry, seed_events=seed_events,
                                                   spend=args.spend))
        result['status'] = 'passed' if all(case['passed'] for case in result['cases']) else 'failed'
        code = 0 if result['status'] == 'passed' else 1
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))
    return code


if __name__ == '__main__':
    raise SystemExit(main())
