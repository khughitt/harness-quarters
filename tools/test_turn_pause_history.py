"""Atomic root/history records, over synthetic state only."""
import importlib
import json
import os
import threading

import pytest

from turn_pause.counters import TurnState
from turn_pause.limits import Limits
from turn_pause.state import StateError, Store


def history():
    return importlib.import_module('turn_pause.history')


def seeded(store, root='r1'):
    with store.locked('codex', root) as record:
        record.state.turn = TurnState(started=1.0, limits=Limits(57600, 500, 60, 2), limits_sha='abc')
        record.turn_serial = 1
    return store.read_record('codex', root)


def add(record, when=2.0):
    return history().append_event(record, 'warning', when, reason='calls',
                                 snapshot=history().snapshot(record.state, compactions_counted=False))


def test_event_bound_and_restart_identity(tmp_path):
    store = Store(tmp_path)
    generation = seeded(store).generation
    with store.locked('codex', 'r1') as record:
        for i in range(129):
            add(record, i + 2)
    got = Store(tmp_path).read_record('codex', 'r1')
    assert len(got.events) == 128 and got.dropped_count == 1
    assert got.generation == generation and got.event_serial == 129
    assert got.dropped_through == 2
    assert got.events[0]['sequence'] == 2 and got.events[-1]['sequence'] == 129


def test_history_byte_bound_counts_utf8_bytes(tmp_path):
    store = Store(tmp_path)
    root = 'é' * 100
    seeded(store, root)
    with store.locked('codex', root) as record:
        record.state.turn.calls = 10**500
        for i in range(128):
            add(record, i + 2)
    got = store.read_record('codex', root)
    encoded = json.dumps(got.events, ensure_ascii=False, separators=(',', ':')).encode()
    assert len(encoded) <= 131072 and len(got.events) < 128
    assert got.dropped_count == 128 - len(got.events)
    assert 'é' in got.events[-1]['root']


def test_history_rejects_single_oversized_event_without_mutating(tmp_path):
    store = Store(tmp_path)
    record = seeded(store)
    snap = history().snapshot(record.state, compactions_counted=False)
    snap['limits_sha'] = 'x' * 140000
    with pytest.raises(ValueError):
        history().append_event(record, 'warning', 2, reason='calls', snapshot=snap)
    assert record.events == [] and record.event_serial == 0


def test_atomic_replace_failure_preserves_state_and_history(tmp_path, monkeypatch):
    store = Store(tmp_path)
    seeded(store)
    path = tmp_path / 'codex-r1.json'
    before = path.read_bytes()

    def fail(*args):
        raise OSError('replace failed')

    monkeypatch.setattr(os, 'replace', fail)
    with pytest.raises(StateError):
        with store.locked('codex', 'r1') as record:
            record.state.turn.calls += 1
            add(record)
    assert path.read_bytes() == before
    assert not list(tmp_path.glob('*.tmp'))


def test_parallel_history_updates_have_unique_sequences(tmp_path):
    store = Store(tmp_path)
    seeded(store)
    errors = []

    def work():
        try:
            for _ in range(10):
                with store.locked('codex', 'r1') as record:
                    record.state.turn.calls += 1
                    add(record)
        except Exception as error:
            errors.append(error)

    threads = [threading.Thread(target=work) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    got = store.read_record('codex', 'r1')
    assert not errors and got.state.turn.calls == 80
    assert sorted(e['sequence'] for e in got.events) == list(range(1, 81))


@pytest.mark.parametrize('field,bad', [('version', True), ('version', 2), ('turn_serial', True),
                                     ('event_serial', -1), ('created_at', float('nan')),
                                     ('state', []), ('events', [1]), ('generation', '')])
def test_invalid_root_record_is_refused(tmp_path, field, bad):
    store = Store(tmp_path)
    seeded(store)
    path = tmp_path / 'codex-r1.json'
    data = json.loads(path.read_bytes())
    data[field] = bad
    path.write_text(json.dumps(data))
    with pytest.raises(StateError):
        store.read_record('codex', 'r1')


def test_duplicate_keys_and_legacy_format_need_explicit_conversion(tmp_path):
    store = Store(tmp_path)
    seeded(store)
    path = tmp_path / 'codex-r1.json'
    text = path.read_text()
    path.write_text(text.replace('"version":1', '"version":1,"version":1', 1))
    with pytest.raises(StateError):
        store.read_record('codex', 'r1')
    path.write_text(json.dumps({'harness': 'codex', 'root': 'r1', 'turn': None}))
    with pytest.raises(StateError, match='migrat'):
        store.read_record('codex', 'r1')


@pytest.mark.parametrize('field,value', [('calls', -1), ('spawns', -1), ('compactions', -1),
                                         ('limits.calls', -1), ('limits.spawns', -1)])
def test_invalid_active_turn_ranges_are_refused(tmp_path, field, value):
    store = Store(tmp_path)
    seeded(store)
    path = tmp_path / 'codex-r1.json'
    data = json.loads(path.read_bytes())
    target = data['state']['turn']
    if field.startswith('limits.'):
        target = target['limits']
    target[field.split('.')[-1]] = value
    path.write_text(json.dumps(data))
    with pytest.raises(StateError):
        store.read_record('codex', 'r1')


def test_snapshot_omits_private_state_and_marks_unknown_compactions(tmp_path):
    record = seeded(Store(tmp_path))
    record.state.cwd = 'PRIVATE_SENTINEL'
    record.state.notify_error = 'PRIVATE_SENTINEL'
    record.state.budget_note = 'PRIVATE_SENTINEL'
    record.state.cron_jobs['secret'] = 'PRIVATE_SENTINEL'
    record.state.turn.in_flight['PRIVATE_SENTINEL'] = None
    event = add(record)
    assert 'PRIVATE_SENTINEL' not in json.dumps(event)
    assert event['snapshot']['compactions']['used'] is None
    assert event['snapshot']['counted']['compactions'] is False
    assert event['snapshot']['scopes']['calls'] == 'root_attempts'


def test_ended_record_has_history_but_no_active_lookup(tmp_path):
    store = Store(tmp_path)
    seeded(store)
    with store.locked('codex', 'r1') as record:
        record.state.cwd = '/portable/work'
        record.state.workers.add('w1')
        add(record)
        record.state = None
        record.ended_at = 3
    assert store.read('codex', 'r1') is None
    assert len(store.read_record('codex', 'r1').events) == 1
    assert store.latest_for_cwd('/portable/work') is None
    assert store.root_for_agent('codex', 'w1') is None


def test_no_create_lock_does_not_resurrect_missing_record(tmp_path):
    store = Store(tmp_path)
    with store.locked('codex', 'missing', create=False) as record:
        assert record is None
    assert not (tmp_path / 'codex-missing.json').exists()


def test_record_storage_is_private_and_has_no_temporary_residue(tmp_path):
    directory = tmp_path / 'state'
    seeded(Store(directory))
    assert directory.stat().st_mode & 0o777 == 0o700
    assert (directory / 'codex-r1.json').stat().st_mode & 0o777 == 0o600
    assert not list(directory.glob('*.tmp'))
