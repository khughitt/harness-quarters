"""Tests for tools/turn_pause/spend.py: signal reader, episode rules, and host latch."""
from __future__ import annotations

import fcntl
import json
import os
import subprocess
import threading
import time
from pathlib import Path

import pytest

from turn_pause import notify, spend
from turn_pause.state import Store
from turn_pause.spend import (
    PROTECTED_NAMES,
    SIGNAL_NAME,
    Entry,
    Signal,
    fresh_entry,
    obs_state_dir,
    protected_paths,
    read,
    signal_from_dict,
    signal_to_dict,
    state_of,
)

TOOLS = Path(__file__).parent
NOW_MS = 1_700_001_000_000
NOW_S = 1_700_001_000.0
OFF_UNTIL = (
    'spend protection is off until the producer runs again '
    '(systemctl --user status obs-spend.timer, journalctl --user -u obs-spend)'
)
HEAVY = ('dataclasses', 'typing', 'tempfile', 'pathlib', 'hashlib', 'shlex', 'string', 'json', 're',
         'turn_pause.allowlist')


def make_env(tmp_path: Path) -> dict[str, str]:
    return {'XDG_STATE_HOME': str(tmp_path), 'HOME': str(tmp_path)}


def make_tree_entry(
    harness: str = 'codex',
    root_session: str = 'R',
    *,
    root: str | None = None,
    root_resolved: bool = True,
    episode: str | None = None,
    value: int | float = 500_000_000,
    threshold: int | float = 350_000_000.0,
    ratio: int | float = 1.43,
    window_hours: int = 72,
    measured_at: int = NOW_MS,
    complete: bool = True,
    credits_drawn_24h: int | float | None = 0.0,
    **overrides,
) -> dict:
    entry = {
        'root': f'{harness}:{root_session}' if root is None else root,
        'harness': harness,
        'root_session': root_session,
        'root_resolved': root_resolved,
        'episode': f'{harness}:{root_session}@1700000000000' if episode is None else episode,
        'metric': 'tokens',
        'window_hours': window_hours,
        'info_window_hours': 24,
        'value': value,
        'threshold': threshold,
        'ratio': ratio,
        'value_info': 100_000_000,
        'first_crossed_at': 1_700_000_000_000,
        'measured_at': measured_at,
        'observed_at': measured_at,
        'complete': complete,
        'children': 1,
        'last_context_tokens': 50_000,
        'responses_last_hour': 12,
        'codex_home': '.codex' if harness == 'codex' else None,
        'credits_drawn_24h': credits_drawn_24h,
    }
    entry.update(overrides)
    return entry


def write_signal(
    state_home: Path,
    trees: list,
    generated_at: int = NOW_MS,
    stale_after_ms: int = 600_000,
    status: str = 'ok',
    schema: object = 1,
    *,
    claude_state: str = 'ok',
    codex_state: str = 'ok',
) -> Path:
    obs_dir = state_home / 'obs'
    obs_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        'schema': schema,
        'generated_at': generated_at,
        'status': status,
        'stale_after_ms': stale_after_ms,
        'baseline': {
            'id': 'baseline-1',
            'computed_at': generated_at,
            'harnesses': {
                'claude-code': {'state': claude_state, 'threshold': 250_000_000.0, 'trees': 40},
                'codex': {'state': codex_state, 'threshold': 350_000_000.0, 'trees': 40},
            },
        },
        'credits': {},
        'coverage': {
            'files_seen': 10,
            'files_unfinished': 0,
            'files_starved': [],
            'files_malformed': [],
            'files_unparsed': [],
            'trees_unfinished': [],
        },
        'trees': trees,
    }
    dest = obs_dir / SIGNAL_NAME
    tmp = obs_dir / f'.{SIGNAL_NAME}.{os.urandom(6).hex()}.tmp'
    tmp.write_text(json.dumps(payload), encoding='utf-8')
    os.replace(tmp, dest)
    return dest


def test_entry_selected_by_harness_root_and_resolved(tmp_path: Path):
    env = make_env(tmp_path)
    trees = [
        make_tree_entry('codex', 'other', episode='ep-other', value=100),
        make_tree_entry('claude-code', 'R', episode='ep-claude', value=200, credits_drawn_24h=None),
        make_tree_entry('codex', 'R', root_resolved=False, episode='ep-unresolved', value=300),
        make_tree_entry('codex', 'R', root_resolved=True, episode='ep-target', value=400, credits_drawn_24h=12.5),
    ]
    write_signal(tmp_path, trees)
    sig = read(env, 'codex', 'R', None)
    assert sig.error is None
    assert sig.entry == Entry(
        episode='ep-target',
        value=400,
        threshold=350_000_000.0,
        ratio=1.43,
        window_hours=72,
        measured_at=NOW_MS,
        complete=True,
        credits_drawn_24h=12.5,
    )

    # Without the resolved matching entry, the unresolved and other entries are not selected.
    write_signal(tmp_path, trees[:3])
    sig_none = read(env, 'codex', 'R', None)
    assert sig_none.error is None
    assert state_of(sig_none, NOW_MS, False) == 'fresh'
    assert sig_none.entry is None

    # Duplicate resolved entries for the same (harness, root) fail closed as unreadable.
    write_signal(tmp_path, [trees[3], make_tree_entry('codex', 'R', root_resolved=True, episode='ep-dup')])
    sig_dup = read(env, 'codex', 'R', None)
    assert sig_dup.error is not None
    assert state_of(sig_dup, NOW_MS, False) == 'unreadable'


def test_root_key_mismatch_is_unreadable(tmp_path: Path):
    env = make_env(tmp_path)
    write_signal(tmp_path, [make_tree_entry('codex', 'R', root='codex:X')])
    sig = read(env, 'codex', 'R', None)
    assert sig.error is not None and 'root' in sig.error
    assert state_of(sig, NOW_MS, False) == 'unreadable'
    assert fresh_entry(sig, NOW_MS) is None


def test_freshness_ms(tmp_path: Path):
    env = make_env(tmp_path)
    write_signal(tmp_path, [make_tree_entry('codex', 'R', measured_at=NOW_MS - 600_000)],
                 generated_at=NOW_MS - 600_000)
    sig_boundary = read(env, 'codex', 'R', None)
    assert state_of(sig_boundary, NOW_MS, False) == 'fresh'
    assert fresh_entry(sig_boundary, NOW_MS) == sig_boundary.entry

    write_signal(tmp_path, [make_tree_entry('codex', 'R', measured_at=NOW_MS)],
                 generated_at=NOW_MS - 600_001)
    sig_stale_file = read(env, 'codex', 'R', None)
    assert state_of(sig_stale_file, NOW_MS, False) == 'stale'
    assert fresh_entry(sig_stale_file, NOW_MS) is None

    write_signal(tmp_path, [make_tree_entry('codex', 'R', measured_at=NOW_MS - 600_001)],
                 generated_at=NOW_MS)
    sig_stale_entry = read(env, 'codex', 'R', None)
    assert state_of(sig_stale_entry, NOW_MS, False) == 'fresh'
    assert fresh_entry(sig_stale_entry, NOW_MS) is None


def test_baseline_state_read(tmp_path: Path):
    env = make_env(tmp_path)
    for valid_state in ('ok', 'insufficient', 'stale', 'missing'):
        write_signal(tmp_path, [], codex_state=valid_state)
        sig = read(env, 'codex', 'R', None)
        assert sig.error is None
        assert sig.baseline == valid_state

    write_signal(tmp_path, [], codex_state='bogus')
    bad = read(env, 'codex', 'R', None)
    assert bad.error is not None and 'baseline' in bad.error
    assert state_of(bad, NOW_MS, False) == 'unreadable'


def test_partial_file_entry_counts(tmp_path: Path):
    env = make_env(tmp_path)
    write_signal(tmp_path, [make_tree_entry('codex', 'R')], status='partial')
    sig = read(env, 'codex', 'R', None)
    assert sig.error is None
    assert sig.status == 'partial'
    assert state_of(sig, NOW_MS, False) == 'fresh'
    assert fresh_entry(sig, NOW_MS) is not None


def test_absent_and_vanished(tmp_path: Path):
    env = make_env(tmp_path)
    sig = read(env, 'codex', 'R', None)
    assert sig.identity is None
    assert sig.error is None
    assert state_of(sig, NOW_MS, False) == 'absent'
    assert state_of(sig, NOW_MS, True) == 'vanished'
    assert fresh_entry(sig, NOW_MS) is None


def test_bad_fields_are_unreadable(tmp_path: Path):
    env = make_env(tmp_path)

    # Bad schema
    write_signal(tmp_path, [make_tree_entry('codex', 'R')], schema=2)
    sig = read(env, 'codex', 'R', None)
    assert state_of(sig, NOW_MS, False) == 'unreadable' and sig.error is not None and 'schema' in sig.error

    # Bad entry fields
    bad_entries = [
        (make_tree_entry('codex', 'R', value=True), 'value'),
        (make_tree_entry('codex', 'R', threshold='1'), 'threshold'),
        (make_tree_entry('codex', 'R', threshold=0), 'threshold'),
        (make_tree_entry('codex', 'R', credits_drawn_24h='x'), 'credits_drawn_24h'),
        (make_tree_entry('codex', 'R', credits_drawn_24h=False), 'credits_drawn_24h'),
        (make_tree_entry('codex', 'R', ratio=True), 'ratio'),
        (make_tree_entry('codex', 'R', window_hours=0), 'window_hours'),
        (make_tree_entry('codex', 'R', measured_at=True), 'measured_at'),
        (make_tree_entry('codex', 'R', complete=1), 'complete'),
        (make_tree_entry('codex', 'R', episode=''), 'episode'),
    ]
    for entry, field_name in bad_entries:
        write_signal(tmp_path, [entry])
        sig = read(env, 'codex', 'R', None)
        assert state_of(sig, NOW_MS, False) == 'unreadable', field_name
        assert sig.error is not None and field_name in sig.error

    # Missing credits_drawn_24h key
    missing_credits = make_tree_entry('codex', 'R')
    del missing_credits['credits_drawn_24h']
    write_signal(tmp_path, [missing_credits])
    sig = read(env, 'codex', 'R', None)
    assert state_of(sig, NOW_MS, False) == 'unreadable'
    assert sig.error is not None and 'credits_drawn_24h' in sig.error

    # Non-JSON text
    dest = tmp_path / 'obs' / SIGNAL_NAME
    dest.write_text('not valid json {', encoding='utf-8')
    sig = read(env, 'codex', 'R', None)
    assert state_of(sig, NOW_MS, False) == 'unreadable'
    assert sig.error is not None

    # Accepted shapes: credits_drawn_24h null and 0.0, float threshold
    write_signal(tmp_path, [make_tree_entry('codex', 'R', threshold=123456.75, credits_drawn_24h=None)])
    sig_null = read(env, 'codex', 'R', None)
    assert state_of(sig_null, NOW_MS, False) == 'fresh'
    assert sig_null.entry is not None
    assert sig_null.entry.credits_drawn_24h is None
    assert sig_null.entry.threshold == 123456.75

    write_signal(tmp_path, [make_tree_entry('codex', 'R', threshold=99.5, credits_drawn_24h=0.0)])
    sig_zero = read(env, 'codex', 'R', None)
    assert state_of(sig_zero, NOW_MS, False) == 'fresh'
    assert sig_zero.entry is not None
    assert sig_zero.entry.credits_drawn_24h == 0.0
    assert sig_zero.entry.threshold == 99.5


def test_truncated_file_is_unreadable(tmp_path: Path):
    env = make_env(tmp_path)
    dest = write_signal(tmp_path, [make_tree_entry('codex', 'R')])
    valid_bytes = dest.read_bytes()

    dest.write_bytes(b'')
    sig_empty = read(env, 'codex', 'R', None)
    assert state_of(sig_empty, NOW_MS, False) == 'unreadable'
    assert sig_empty.error is not None

    dest.write_bytes(valid_bytes[: len(valid_bytes) // 2])
    sig_half = read(env, 'codex', 'R', None)
    assert state_of(sig_half, NOW_MS, False) == 'unreadable'
    assert sig_half.error is not None


def test_bad_state_home_is_unreadable(tmp_path: Path):
    for bad_env in ({'XDG_STATE_HOME': 'rel/path', 'HOME': str(tmp_path)}, {'XDG_STATE_HOME': 'rel/path'}, {}):
        with pytest.raises(ValueError):
            obs_state_dir(bad_env)
        assert protected_paths(bad_env) == []
        sig = read(bad_env, 'codex', 'R', None)
        assert sig.identity is None
        assert sig.error is not None
        assert state_of(sig, NOW_MS, False) == 'unreadable'
        assert state_of(sig, NOW_MS, True) == 'unreadable'

    # An OSError on stat other than FileNotFoundError (e.g. NotADirectoryError) also fails closed into error.
    not_a_dir_home = tmp_path / 'not_a_dir_case'
    not_a_dir_home.mkdir()
    (not_a_dir_home / 'obs').write_text('not a directory', encoding='utf-8')
    env_err = {'XDG_STATE_HOME': str(not_a_dir_home), 'HOME': str(not_a_dir_home)}
    sig_err = read(env_err, 'codex', 'R', None)
    assert sig_err.identity is None
    assert sig_err.error is not None
    assert state_of(sig_err, NOW_MS, False) == 'unreadable'


def test_future_generated_at_is_fresh(tmp_path: Path):
    env = make_env(tmp_path)
    write_signal(tmp_path, [make_tree_entry('codex', 'R', measured_at=NOW_MS + 5000)],
                 generated_at=NOW_MS + 5000)
    sig = read(env, 'codex', 'R', None)
    assert state_of(sig, NOW_MS, False) == 'fresh'
    assert fresh_entry(sig, NOW_MS) == sig.entry


def test_identity_cache(tmp_path: Path):
    env = make_env(tmp_path)
    write_signal(tmp_path, [make_tree_entry('codex', 'R', value=100)])
    first = read(env, 'codex', 'R', None)
    assert first.entry is not None and first.entry.value == 100

    second = read(env, 'codex', 'R', first)
    assert second is first
    # Freshness still expires over time from cached timestamps without re-parsing.
    assert state_of(second, NOW_MS + 600_001, False) == 'stale'

    # Rewriting via os.replace (new inode) invalidates the cache and re-parses.
    write_signal(tmp_path, [make_tree_entry('codex', 'R', value=250)])
    third = read(env, 'codex', 'R', first)
    assert third is not first
    assert third.entry is not None and third.entry.value == 250


def test_protected_paths(tmp_path: Path):
    env = make_env(tmp_path)
    expected = [str(tmp_path / 'obs' / name) for name in PROTECTED_NAMES]
    assert PROTECTED_NAMES == ('spend-signals.json', 'spend-baseline.json', 'spend-state.json', 'spend.lock')
    assert protected_paths(env) == expected

    home_only = {'HOME': str(tmp_path)}
    assert obs_state_dir(home_only) == str(tmp_path / '.local' / 'state' / 'obs')
    assert protected_paths(home_only) == [str(tmp_path / '.local' / 'state' / 'obs' / name) for name in PROTECTED_NAMES]


def test_signal_dict_round_trip(tmp_path: Path):
    env = make_env(tmp_path)
    write_signal(tmp_path, [make_tree_entry('codex', 'R', credits_drawn_24h=3.5)])
    fresh_sig = read(env, 'codex', 'R', None)
    absent_sig = read(make_env(tmp_path / 'missing'), 'codex', 'R', None)
    write_signal(tmp_path, [], schema=2)
    unreadable_sig = read(env, 'codex', 'R', None)
    unreadable_no_id = read({}, 'codex', 'R', None)

    for sig in (fresh_sig, absent_sig, unreadable_sig, unreadable_no_id):
        as_dict = signal_to_dict(sig)
        assert signal_from_dict(as_dict) == sig
        via_json = json.loads(json.dumps(as_dict))
        restored = signal_from_dict(via_json)
        assert restored == sig
        if sig.identity is not None:
            assert type(restored.identity) is tuple

    with pytest.raises((TypeError, ValueError)):
        signal_from_dict({'bad': 1})
    bad_id = signal_to_dict(fresh_sig)
    bad_id['identity'] = [1, 2]
    with pytest.raises((TypeError, ValueError)):
        signal_from_dict(bad_id)


def test_spend_hot_path_imports_no_heavy_modules(tmp_path: Path):
    sig_path = write_signal(tmp_path, [make_tree_entry('codex', 'R')])
    pause_dir = tmp_path / 'pause'
    env = make_env(tmp_path)
    warm_sig = read(env, 'codex', 'R', None)
    assert spend.observe(str(pause_dir), warm_sig, str(sig_path), NOW_S) is None
    sub_env = {
        'PYTHONPATH': str(TOOLS),
        'XDG_STATE_HOME': str(tmp_path),
        'HOME': str(tmp_path),
        'PATH': os.defpath,
        'LC_ALL': 'C.UTF-8',
    }
    code = (
        'import os; from turn_pause import spend; '
        'sig = spend.read(os.environ, "codex", "R", None); '
        'assert sig.entry is not None and sig.entry.value == 500_000_000; '
        f'assert spend.observe({str(pause_dir)!r}, sig, {str(sig_path)!r}, {NOW_S!r}) is None'
    )
    r = subprocess.run(
        ['/usr/bin/python3', '-S', '-X', 'importtime', '-c', code],
        env=sub_env,
        capture_output=True,
        timeout=20,
    )
    assert r.returncode == 0, r.stderr.decode()
    imported = {
        line.rsplit('|', 1)[1].strip()
        for line in r.stderr.decode().splitlines()
        if line.startswith('import time:')
    }
    assert 'turn_pause.spend' in imported
    assert 'turn_pause.state' not in imported
    assert sorted(imported & set(HEAVY)) == []
    assert spend.__name__ == 'turn_pause.spend'


def make_entry(
    episode: str = 'ep-1',
    value: int | float = 500,
    *,
    threshold: int | float = 350.0,
    ratio: int | float = 1.43,
    window_hours: int = 72,
    measured_at: int = NOW_MS,
    complete: bool = True,
    credits_drawn_24h: int | float | None = 0.0,
) -> Entry:
    return Entry(
        episode=episode,
        value=value,
        threshold=threshold,
        ratio=ratio,
        window_hours=window_hours,
        measured_at=measured_at,
        complete=complete,
        credits_drawn_24h=credits_drawn_24h,
    )


def test_reconcile_new_episode_replaces():
    e1 = make_entry('E1', 500)
    first = spend.reconcile(None, e1)
    assert first == spend.SpendRecord(
        episode='E1',
        seen_value=500,
        delivered_value=None,
        acked_value=None,
    )

    prev = spend.SpendRecord(
        episode='E1',
        seen_value=900,
        delivered_value=800,
        acked_value=800,
    )
    e2 = make_entry('E2', 420)
    replaced = spend.reconcile(prev, e2)
    assert replaced == spend.SpendRecord(
        episode='E2',
        seen_value=420,
        delivered_value=None,
        acked_value=None,
    )


def test_reconcile_raises_seen_value():
    sr = spend.SpendRecord(
        episode='E1',
        seen_value=500,
        delivered_value=500,
        acked_value=500,
    )
    higher = spend.reconcile(sr, make_entry('E1', 650))
    assert higher == spend.SpendRecord(
        episode='E1',
        seen_value=650,
        delivered_value=500,
        acked_value=500,
    )

    lower = spend.reconcile(higher, make_entry('E1', 400))
    assert lower == spend.SpendRecord(
        episode='E1',
        seen_value=650,
        delivered_value=500,
        acked_value=500,
    )


def test_reconcile_without_entry_keeps_record():
    assert spend.reconcile(None, None) is None
    sr = spend.SpendRecord(
        episode='E1',
        seen_value=700,
        delivered_value=600,
        acked_value=None,
    )
    kept = spend.reconcile(sr, None)
    assert kept == sr


def test_due_when_never_delivered():
    entry = make_entry('E1', 500)
    assert spend.is_due(None, entry) is True
    assert spend.is_due(None, None) is False

    sr = spend.reconcile(None, entry)
    assert spend.is_pending(sr) is False
    assert spend.is_due(sr, entry) is True
    assert spend.is_due(sr, None) is False


def test_due_at_twice_acked():
    sr = spend.SpendRecord(
        episode='E1',
        seen_value=800,
        delivered_value=800,
        acked_value=800,
    )
    below = make_entry('E1', 1599)
    sr_below = spend.reconcile(sr, below)
    assert spend.is_pending(sr_below) is False
    assert spend.is_due(sr_below, below) is False

    at_twice = make_entry('E1', 1600)
    sr_twice = spend.reconcile(sr, at_twice)
    assert spend.is_pending(sr_twice) is False
    assert spend.is_due(sr_twice, at_twice) is True
    assert spend.is_due(sr_twice, None) is False


def test_pending_after_root_delivery():
    assert spend.is_pending(None) is False
    undelivered = spend.SpendRecord(
        episode='E1',
        seen_value=500,
        delivered_value=None,
        acked_value=None,
    )
    assert spend.is_pending(undelivered) is False

    delivered = spend.deliver(undelivered, 500)
    assert delivered == spend.SpendRecord(
        episode='E1',
        seen_value=500,
        delivered_value=500,
        acked_value=None,
    )
    assert spend.is_pending(delivered) is True
    assert spend.is_due(delivered, make_entry('E1', 500)) is False

    acked = spend.acknowledge(delivered)
    assert spend.is_pending(acked) is False


def test_deliver_resets_ack():
    sr = spend.SpendRecord(
        episode='E1',
        seen_value=1650,
        delivered_value=800,
        acked_value=800,
    )
    delivered = spend.deliver(sr, 1650)
    assert delivered.acked_value is None
    assert delivered.delivered_value == 1650
    assert delivered.seen_value == 1650
    assert spend.is_pending(delivered) is True

    # Delivering a snapshot value lower than seen_value keeps seen_value at max.
    from_snap = spend.deliver(
        spend.SpendRecord('E1', seen_value=1800, delivered_value=800, acked_value=800),
        1650,
    )
    assert from_snap.seen_value == 1800
    assert from_snap.delivered_value == 1650
    assert from_snap.acked_value is None


def test_acknowledge_uses_max():
    sr_seen_larger = spend.SpendRecord(
        episode='E1',
        seen_value=1700,
        delivered_value=1650,
        acked_value=None,
    )
    acked = spend.acknowledge(sr_seen_larger)
    assert acked == spend.SpendRecord(
        episode='E1',
        seen_value=1700,
        delivered_value=1650,
        acked_value=1700,
    )
    assert spend.is_pending(acked) is False

    # After resume with no fresh entry, reconcile leaves seen/delivered at 1650 and acks at 1650.
    sr_resumed = spend.reconcile(
        spend.SpendRecord(
            episode='E1',
            seen_value=1650,
            delivered_value=1650,
            acked_value=None,
        ),
        None,
    )
    acked_resume = spend.acknowledge(sr_resumed)
    assert acked_resume == spend.SpendRecord(
        episode='E1',
        seen_value=1650,
        delivered_value=1650,
        acked_value=1650,
    )
    assert spend.is_pending(acked_resume) is False

    # Undelivered record cannot be acknowledged.
    with pytest.raises(ValueError):
        spend.acknowledge(spend.SpendRecord('E1', seen_value=500))


def test_inject_sets_both():
    sr = spend.SpendRecord(
        episode='E1',
        seen_value=500,
        delivered_value=None,
        acked_value=None,
    )
    injected = spend.inject(sr, 550)
    assert injected == spend.SpendRecord(
        episode='E1',
        seen_value=550,
        delivered_value=550,
        acked_value=550,
    )
    assert spend.is_pending(injected) is False
    assert spend.is_due(injected, make_entry('E1', 550)) is False


def test_replacement_before_pending():
    sr_e1 = spend.SpendRecord(
        episode='E1',
        seen_value=500,
        delivered_value=500,
        acked_value=None,
    )
    assert spend.is_pending(sr_e1) is True
    entry_e2 = make_entry('E2', 450)
    sr_e2 = spend.reconcile(sr_e1, entry_e2)
    assert spend.is_pending(sr_e2) is False
    assert spend.is_due(sr_e2, entry_e2) is True
    assert sr_e2 == spend.SpendRecord(
        episode='E2',
        seen_value=450,
        delivered_value=None,
        acked_value=None,
    )


def test_spend_record_and_entry_dict_round_trip():
    records = [
        spend.SpendRecord('E1', seen_value=500),
        spend.SpendRecord('E1', seen_value=500.5, delivered_value=450.0, acked_value=None),
        spend.SpendRecord('E1', seen_value=0, delivered_value=0, acked_value=0),
        spend.SpendRecord('E1', seen_value=1700, delivered_value=1650, acked_value=1700),
    ]
    for sr in records:
        as_dict = spend.spend_record_to_dict(sr)
        assert spend.spend_record_from_dict(as_dict) == sr
        assert spend.spend_record_from_dict(json.loads(json.dumps(as_dict))) == sr

    bad_records = [
        None,
        [],
        {'episode': 'E1'},
        {'episode': 'E1', 'seen_value': 1, 'delivered_value': None, 'acked_value': None, 'extra': 1},
        {'episode': '', 'seen_value': 1, 'delivered_value': None, 'acked_value': None},
        {'episode': 123, 'seen_value': 1, 'delivered_value': None, 'acked_value': None},
        {'episode': 'E1', 'seen_value': True, 'delivered_value': None, 'acked_value': None},
        {'episode': 'E1', 'seen_value': -1, 'delivered_value': None, 'acked_value': None},
        {'episode': 'E1', 'seen_value': float('nan'), 'delivered_value': None, 'acked_value': None},
        {'episode': 'E1', 'seen_value': float('inf'), 'delivered_value': None, 'acked_value': None},
        {'episode': 'E1', 'seen_value': '1', 'delivered_value': None, 'acked_value': None},
        {'episode': 'E1', 'seen_value': 1, 'delivered_value': False, 'acked_value': None},
        {'episode': 'E1', 'seen_value': 1, 'delivered_value': -0.1, 'acked_value': None},
        {'episode': 'E1', 'seen_value': 1, 'delivered_value': float('inf'), 'acked_value': None},
        {'episode': 'E1', 'seen_value': 1, 'delivered_value': 1, 'acked_value': True},
        {'episode': 'E1', 'seen_value': 1, 'delivered_value': 1, 'acked_value': -5},
        {'episode': 'E1', 'seen_value': 1, 'delivered_value': 1, 'acked_value': float('nan')},
    ]
    for bad in bad_records:
        with pytest.raises((TypeError, ValueError)):
            spend.spend_record_from_dict(bad)  # type: ignore[arg-type]

    entry = make_entry('E1', 500, credits_drawn_24h=12.5)
    entry_dict = spend.entry_to_dict(entry)
    assert spend.entry_from_dict(entry_dict) == entry
    with pytest.raises((TypeError, ValueError)):
        spend.entry_from_dict([])  # type: ignore[arg-type]
    with pytest.raises((TypeError, ValueError)):
        spend.entry_from_dict({**entry_dict, 'extra': 1})


# --- host outage latch & desktop alert ------------------------------------------------


def test_one_alert_per_outage(tmp_path: Path):
    env = make_env(tmp_path)
    pause_dir = tmp_path / 'pause'
    sig_path = write_signal(tmp_path, [], generated_at=NOW_MS)
    fresh_sig = read(env, 'codex', 'R1', None)
    assert spend.observe(pause_dir, fresh_sig, str(sig_path), NOW_S) is None
    assert spend.read_latch(pause_dir) == spend.HostLatch(seen_fresh=True, outage=None)

    # First non-fresh observation (stale by 11m01s) fires the single alert for the outage.
    write_signal(tmp_path, [], generated_at=NOW_MS - 661_000)
    stale_sig = read(env, 'codex', 'R1', None)
    alert = spend.observe(pause_dir, stale_sig, str(sig_path), NOW_S)
    assert alert is not None
    st, alerted_at, title, body = alert
    assert st == 'stale'
    assert alerted_at == NOW_S
    assert title == 'turn-pause: spend protection off'
    assert str(sig_path) in body
    assert 'stale' in body
    assert '11m01s' in body
    assert OFF_UNTIL in body
    expected_outage = {
        'state': 'stale',
        'alerted_at': NOW_S,
        'outcome': 'attempted',
        'error': None,
    }
    assert spend.read_latch(pause_dir) == spend.HostLatch(seen_fresh=True, outage=expected_outage)

    # Subsequent unreadable files with new identities every call and another root stay silent.
    write_signal(tmp_path, [], schema=2)
    bad1 = read(env, 'codex', 'R1', None)
    assert bad1.identity is not None and bad1.identity != stale_sig.identity
    assert spend.observe(pause_dir, bad1, str(sig_path), NOW_S + 120) is None

    tmp_bad = sig_path.parent / '.bad2.tmp'
    tmp_bad.write_text('{broken json', encoding='utf-8')
    os.replace(tmp_bad, sig_path)
    bad2 = read(env, 'claude-code', 'R2', None)
    assert bad2.identity is not None and bad2.identity != bad1.identity
    assert spend.observe(pause_dir, bad2, str(sig_path), NOW_S + 240) is None

    # Removing the file transitions the signal state to vanished, still silent within the outage.
    sig_path.unlink()
    vanished = read(env, 'codex', 'R1', None)
    assert vanished.identity is None
    assert state_of(vanished, int((NOW_S + 360) * 1000), True) == 'vanished'
    assert spend.observe(pause_dir, vanished, str(sig_path), NOW_S + 360) is None
    assert spend.read_latch(pause_dir) == spend.HostLatch(seen_fresh=True, outage=expected_outage)


def test_vanished_detected_from_latch(tmp_path: Path):
    env = make_env(tmp_path)
    pause_dir = tmp_path / 'pause'
    sig_path = write_signal(tmp_path, [], generated_at=NOW_MS)
    fresh_sig = read(env, 'codex', 'R', None)
    assert spend.observe(pause_dir, fresh_sig, str(sig_path), NOW_S) is None
    assert spend.read_latch(pause_dir) == spend.HostLatch(seen_fresh=True, outage=None)

    alert = spend.observe(pause_dir, Signal(), str(sig_path), NOW_S + 30)
    assert alert is not None
    st, alerted_at, title, body = alert
    assert st == 'vanished'
    assert alerted_at == NOW_S + 30
    assert title == 'turn-pause: spend protection off'
    assert str(sig_path) in body
    assert 'vanished' in body
    assert 'age unknown' in body
    assert OFF_UNTIL in body
    assert spend.read_latch(pause_dir) == spend.HostLatch(
        seen_fresh=True,
        outage={'state': 'vanished', 'alerted_at': NOW_S + 30, 'outcome': 'attempted', 'error': None},
    )


def test_record_alert_does_not_resurrect(tmp_path: Path):
    env = make_env(tmp_path)
    pause_dir = tmp_path / 'pause'
    sig_path = write_signal(tmp_path, [], generated_at=NOW_MS - 700_000)
    stale_sig = read(env, 'codex', 'R', None)
    alert = spend.observe(pause_dir, stale_sig, str(sig_path), NOW_S)
    assert alert is not None and alert[1] == NOW_S

    # A concurrent fresh observation clears the outage before desktop alert failure is recorded.
    write_signal(tmp_path, [], generated_at=NOW_MS + 10_000)
    fresh_sig = read(env, 'codex', 'R', None)
    assert spend.observe(pause_dir, fresh_sig, str(sig_path), NOW_S + 10) is None
    assert spend.read_latch(pause_dir) == spend.HostLatch(seen_fresh=True, outage=None)

    spend.record_alert(pause_dir, NOW_S, 'err')
    assert spend.read_latch(pause_dir) == spend.HostLatch(seen_fresh=True, outage=None)

    # A stale record_alert for an earlier outage timestamp also leaves a newer outage untouched.
    write_signal(tmp_path, [], generated_at=NOW_MS - 700_000)
    stale2 = read(env, 'codex', 'R', None)
    alert2 = spend.observe(pause_dir, stale2, str(sig_path), NOW_S + 20)
    assert alert2 is not None and alert2[1] == NOW_S + 20
    spend.record_alert(pause_dir, NOW_S, 'old err')
    assert spend.read_latch(pause_dir) == spend.HostLatch(
        seen_fresh=True,
        outage={'state': 'stale', 'alerted_at': NOW_S + 20, 'outcome': 'attempted', 'error': None},
    )


@pytest.mark.parametrize('latch_mode', ['attempted_latch', 'error_latch'])
def test_outage_reads_take_no_lock_or_write(tmp_path: Path, latch_mode: str):
    env = make_env(tmp_path)
    pause_dir = tmp_path / 'pause'
    sig_path = write_signal(tmp_path, [], generated_at=NOW_MS)
    assert spend.observe(pause_dir, read(env, 'codex', 'R', None), str(sig_path), NOW_S - 60) is None

    write_signal(tmp_path, [], generated_at=NOW_MS - 700_000)
    stale_sig = read(env, 'codex', 'R', None)
    alert = spend.observe(pause_dir, stale_sig, str(sig_path), NOW_S)
    assert alert is not None
    if latch_mode == 'error_latch':
        spend.record_alert(pause_dir, NOW_S, 'notify-send: failed')
        assert spend.read_latch(pause_dir).seen_fresh is True

    host_file = pause_dir / spend.HOST_FILE
    lock_file = pause_dir / spend.HOST_LOCK
    os.utime(host_file, (1_000_000, 1_000_000))
    before = (host_file.stat().st_mtime_ns, host_file.stat().st_ino)

    write_signal(tmp_path, [], schema=2)
    unreadable_sig = read(env, 'codex', 'R', None)

    lock_fd = os.open(lock_file, os.O_RDWR)
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        probe_fd = os.open(lock_file, os.O_RDWR)
        try:
            with pytest.raises(BlockingIOError):
                fcntl.flock(probe_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        finally:
            os.close(probe_fd)

        results: list[object] = []
        errors: list[BaseException] = []

        def run_fast_path():
            try:
                results.append(spend.observe(pause_dir, stale_sig, str(sig_path), NOW_S + 3599))
                results.append(spend.observe(pause_dir, unreadable_sig, str(sig_path), NOW_S + 3599))
                results.append(spend.observe(pause_dir, Signal(), str(sig_path), NOW_S + 3599))
            except BaseException as exc:  # pragma: no cover
                errors.append(exc)

        worker = threading.Thread(target=run_fast_path)
        worker.start()
        worker.join(timeout=1.5)
        assert not worker.is_alive(), 'observe blocked on HOST_LOCK during ongoing outage'
        assert errors == []
        assert results == [None, None, None]
    finally:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        os.close(lock_fd)

    after = (host_file.stat().st_mtime_ns, host_file.stat().st_ino)
    assert after == before


def test_fresh_clears_latch(tmp_path: Path):
    env = make_env(tmp_path)
    pause_dir = tmp_path / 'pause'
    sig_path = write_signal(tmp_path, [], generated_at=NOW_MS - (2 * 3600 + 5 * 60) * 1000)
    stale1 = read(env, 'codex', 'R', None)
    alert1 = spend.observe(pause_dir, stale1, str(sig_path), NOW_S)
    assert alert1 is not None and alert1[0] == 'stale'
    assert '2h05m' in alert1[3]

    write_signal(tmp_path, [], generated_at=NOW_MS + 60_000)
    fresh = read(env, 'codex', 'R', None)
    assert spend.observe(pause_dir, fresh, str(sig_path), NOW_S + 60) is None
    assert spend.read_latch(pause_dir) == spend.HostLatch(seen_fresh=True, outage=None)

    write_signal(tmp_path, [], schema=2)
    unreadable = read(env, 'codex', 'R', None)
    alert2 = spend.observe(pause_dir, unreadable, str(sig_path), NOW_S + 120)
    assert alert2 is not None
    st2, alerted_at2, title2, body2 = alert2
    assert st2 == 'unreadable'
    assert alerted_at2 == NOW_S + 120
    assert title2 == 'turn-pause: spend protection off'
    assert str(sig_path) in body2
    assert 'unreadable' in body2
    assert 'age unknown' in body2
    assert 'schema' in body2
    assert OFF_UNTIL in body2


def test_absent_never_alerts(tmp_path: Path):
    pause_dir = tmp_path / 'pause'
    sig_path = tmp_path / 'obs' / SIGNAL_NAME
    for dt in (0, 60, 3600, 86400):
        assert spend.observe(pause_dir, Signal(), str(sig_path), NOW_S + dt) is None
    assert not (pause_dir / spend.HOST_FILE).exists()
    assert spend.read_latch(pause_dir) == spend.HostLatch(seen_fresh=False, outage=None)


def test_absent_before_fresh_is_silent(tmp_path: Path):
    env = make_env(tmp_path)
    pause_dir = tmp_path / 'pause'
    sig_path = tmp_path / 'obs' / SIGNAL_NAME

    # No file and no prior fresh sighting: state is absent, no alert.
    missing = read(env, 'codex', 'R', None)
    assert spend.observe(pause_dir, missing, str(sig_path), NOW_S) is None
    assert spend.read_latch(pause_dir) == spend.HostLatch(seen_fresh=False, outage=None)

    # Even after an unreadable file (seen_fresh stays False), removing it yields absent, not vanished.
    write_signal(tmp_path, [], schema=2)
    bad = read(env, 'codex', 'R', None)
    alert = spend.observe(pause_dir, bad, str(sig_path), NOW_S + 10)
    assert alert is not None and alert[0] == 'unreadable'
    assert spend.read_latch(pause_dir).seen_fresh is False

    sig_path.unlink()
    missing_again = read(env, 'codex', 'R', None)
    assert state_of(missing_again, int((NOW_S + 20) * 1000), spend.read_latch(pause_dir).seen_fresh) == 'absent'
    assert spend.observe(pause_dir, missing_again, str(sig_path), NOW_S + 20) is None


def test_failed_alert_retried_after_hour(tmp_path: Path):
    env = make_env(tmp_path)
    pause_dir = tmp_path / 'pause'
    assert spend.RETRY_SECONDS == 3600
    sig_path = write_signal(tmp_path, [], generated_at=NOW_MS - 700_000)
    stale_sig = read(env, 'codex', 'R', None)

    first = spend.observe(pause_dir, stale_sig, str(sig_path), NOW_S)
    assert first is not None and first[1] == NOW_S
    spend.record_alert(pause_dir, NOW_S, 'notify-send: missing binary')
    assert spend.read_latch(pause_dir) == spend.HostLatch(
        seen_fresh=False,
        outage={
            'state': 'stale',
            'alerted_at': NOW_S,
            'outcome': 'error',
            'error': 'notify-send: missing binary',
        },
    )

    assert spend.observe(pause_dir, stale_sig, str(sig_path), NOW_S + 3599) is None
    assert spend.read_latch(pause_dir).outage == {
        'state': 'stale',
        'alerted_at': NOW_S,
        'outcome': 'error',
        'error': 'notify-send: missing binary',
    }

    retried = spend.observe(pause_dir, stale_sig, str(sig_path), NOW_S + 3600)
    assert retried is not None
    assert retried[0] == 'stale'
    assert retried[1] == NOW_S + 3600
    assert spend.read_latch(pause_dir) == spend.HostLatch(
        seen_fresh=False,
        outage={
            'state': 'stale',
            'alerted_at': NOW_S + 3600,
            'outcome': 'attempted',
            'error': None,
        },
    )
    # Once attempted succeeds (no record_alert), it does not re-fire another hour later.
    assert spend.observe(pause_dir, stale_sig, str(sig_path), NOW_S + 7200) is None


def test_fresh_no_write_when_clear(tmp_path: Path):
    env = make_env(tmp_path)
    pause_dir = tmp_path / 'pause'
    sig_path = write_signal(tmp_path, [], generated_at=NOW_MS)
    fresh_sig = read(env, 'codex', 'R', None)
    assert spend.observe(pause_dir, fresh_sig, str(sig_path), NOW_S) is None

    host_file = pause_dir / spend.HOST_FILE
    lock_file = pause_dir / spend.HOST_LOCK
    os.utime(host_file, (1_000_000, 1_000_000))
    before = (host_file.stat().st_mtime_ns, host_file.stat().st_ino)

    lock_fd = os.open(lock_file, os.O_RDWR)
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        assert spend.observe(pause_dir, fresh_sig, str(sig_path), NOW_S + 60) is None
    finally:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        os.close(lock_fd)

    after = (host_file.stat().st_mtime_ns, host_file.stat().st_ino)
    assert after == before


def test_store_ignores_host_file(tmp_path: Path):
    env = make_env(tmp_path)
    pause_dir = tmp_path / 'pause'
    sig_path = write_signal(tmp_path, [], generated_at=NOW_MS - 700_000)
    stale_sig = read(env, 'codex', 'R', None)
    assert spend.observe(pause_dir, stale_sig, str(sig_path), NOW_S) is not None
    assert spend.HOST_FILE.startswith('.') and spend.HOST_LOCK.startswith('.')
    assert (pause_dir / spend.HOST_FILE).is_file()
    assert (pause_dir / spend.HOST_LOCK).is_file()

    store = Store(pause_dir)
    assert store._files() == []
    with store.locked('codex', 'r1'):
        pass
    assert store._files() == [str(pause_dir / 'codex-r1.json')]
    assert store.retention(NOW_S)['ended_roots'] == 0
    assert store.prune(NOW_S + 30 * 86400, compactions_counted={})['deleted'] == 0
    assert (pause_dir / spend.HOST_FILE).is_file()
    assert spend.read_latch(pause_dir).outage is not None


def test_host_latch_strict_validation(tmp_path: Path):
    assert spend.read_latch(tmp_path / 'nonexistent') == spend.HostLatch(False, None)
    assert spend.HostLatch() == spend.HostLatch(False, None)

    host_file = tmp_path / spend.HOST_FILE
    bad_payloads = [
        '{not json',
        '[]',
        '{}',
        json.dumps({'seen_fresh': False}),
        json.dumps({'seen_fresh': False, 'outage': None, 'extra': 1}),
        json.dumps({'seen_fresh': 1, 'outage': None}),
        json.dumps({'seen_fresh': 'false', 'outage': None}),
        json.dumps({'seen_fresh': None, 'outage': None}),
        json.dumps({'seen_fresh': True, 'outage': []}),
        json.dumps({'seen_fresh': True, 'outage': {'state': 'stale'}}),
        json.dumps({
            'seen_fresh': True,
            'outage': {'state': 'stale', 'alerted_at': 1.0, 'outcome': 'attempted', 'error': None, 'x': 1},
        }),
        json.dumps({
            'seen_fresh': True,
            'outage': {'state': 'fresh', 'alerted_at': 1.0, 'outcome': 'attempted', 'error': None},
        }),
        json.dumps({
            'seen_fresh': True,
            'outage': {'state': 'absent', 'alerted_at': 1.0, 'outcome': 'attempted', 'error': None},
        }),
        json.dumps({
            'seen_fresh': True,
            'outage': {'state': 'stale', 'alerted_at': True, 'outcome': 'attempted', 'error': None},
        }),
        json.dumps({
            'seen_fresh': True,
            'outage': {'state': 'stale', 'alerted_at': -1.0, 'outcome': 'attempted', 'error': None},
        }),
        json.dumps({
            'seen_fresh': True,
            'outage': {'state': 'stale', 'alerted_at': '1.0', 'outcome': 'attempted', 'error': None},
        }),
        json.dumps({
            'seen_fresh': True,
            'outage': {'state': 'stale', 'alerted_at': 1.0, 'outcome': 'pending', 'error': None},
        }),
        json.dumps({
            'seen_fresh': True,
            'outage': {'state': 'stale', 'alerted_at': 1.0, 'outcome': 'attempted', 'error': 'oops'},
        }),
        json.dumps({
            'seen_fresh': True,
            'outage': {'state': 'stale', 'alerted_at': 1.0, 'outcome': 'error', 'error': None},
        }),
        json.dumps({
            'seen_fresh': True,
            'outage': {'state': 'stale', 'alerted_at': 1.0, 'outcome': 'error', 'error': 123},
        }),
    ]
    for raw in bad_payloads:
        host_file.write_text(raw, encoding='utf-8')
        with pytest.raises((TypeError, ValueError)):
            spend.read_latch(tmp_path)

    host_file.unlink()
    host_file.mkdir()
    try:
        with pytest.raises((OSError, ValueError)):
            spend.read_latch(tmp_path)
    finally:
        host_file.rmdir()


def test_notify_desktop_alert(tmp_path: Path):
    bin_dir = tmp_path / 'bin'
    bin_dir.mkdir()
    log_file = bin_dir / 'notify-send.log'
    stub = bin_dir / 'notify-send'
    stub.write_text(
        '#!/bin/sh\nprintf "%s\\n" "$@" >> "$(dirname "$0")/notify-send.log"\n',
        encoding='utf-8',
    )
    stub.chmod(0o755)
    # Point XDG_STATE_HOME at a regular file so any relay socket attempt would fail if called.
    blocker = tmp_path / 'not_a_dir'
    blocker.write_text('x', encoding='utf-8')
    env = {'PATH': f'{bin_dir}:/usr/bin:/bin', 'HOME': str(tmp_path), 'XDG_STATE_HOME': str(blocker)}

    with pytest.raises(TypeError):
        notify.desktop('t', 'b', env)  # type: ignore[misc]

    assert notify.desktop('turn-pause: spend protection off', 'stale signal body', env=env) is None
    for _ in range(150):
        if log_file.exists() and log_file.read_text(encoding='utf-8'):
            break
        time.sleep(0.02)
    logged = log_file.read_text(encoding='utf-8').splitlines()
    assert logged == [
        '--app-name=turn-pause',
        '--urgency=critical',
        'turn-pause: spend protection off',
        'stale signal body',
    ]

    empty_bin = tmp_path / 'empty_bin'
    empty_bin.mkdir()
    missing_env = {'PATH': str(empty_bin), 'HOME': str(tmp_path), 'XDG_STATE_HOME': str(tmp_path)}
    err = notify.desktop('turn-pause: spend protection off', 'stale signal body', env=missing_env)
    assert err is not None and err.startswith('notify-send:')


def test_double_checked_host_latch_prevents_concurrent_duplicate_alert(tmp_path: Path):
    from turn_pause.state import write_atomic

    env = make_env(tmp_path)
    pause_dir = tmp_path / 'pause'
    pause_dir.mkdir(mode=0o700)
    sig_path = write_signal(tmp_path, [], generated_at=NOW_MS - 700_000)
    stale_sig = read(env, 'codex', 'R', None)

    lock_file = pause_dir / spend.HOST_LOCK
    lock_fd = os.open(lock_file, os.O_CREAT | os.O_RDWR, 0o600)
    out: list[object] = []
    errors: list[BaseException] = []
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX)

        def contender():
            try:
                out.append(spend.observe(pause_dir, stale_sig, str(sig_path), NOW_S + 5))
            except BaseException as exc:  # pragma: no cover
                errors.append(exc)

        worker = threading.Thread(target=contender)
        worker.start()
        time.sleep(0.05)
        assert worker.is_alive(), 'contender should wait on HOST_LOCK after lock-free read'

        winner = spend.HostLatch(
            seen_fresh=True,
            outage={'state': 'stale', 'alerted_at': NOW_S, 'outcome': 'attempted', 'error': None},
        )
        write_atomic(
            str(pause_dir / spend.HOST_FILE),
            json.dumps(spend.host_latch_to_dict(winner)).encode('utf-8'),
        )
    finally:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        os.close(lock_fd)

    worker.join(timeout=2.0)
    assert not worker.is_alive()
    assert errors == []
    assert out == [None]
    assert spend.read_latch(pause_dir) == winner


# --- latency measurement gate (tools/measure_turn_pause.py) ---------------------------


def _install_in_process_hook(monkeypatch, mtp, on_pre_tool_use=None):
    import io
    from turn_pause import hook

    monkeypatch.setattr(hook.notify, 'desktop', lambda title, body, *, env: None)

    def fast_call(harness, event, payload, limits, env, entry=mtp.ENTRY):
        if event == 'PreToolUse' and on_pre_tool_use is not None:
            on_pre_tool_use(env)
        out = io.StringIO()
        err = io.StringIO()
        code = hook.main(
            ['--harness', harness, '--limits', str(limits), event],
            stdin=io.BytesIO(json.dumps(payload).encode('utf-8')),
            stdout=out,
            stderr=err,
            env=env,
        )
        assert code == 0 and not err.getvalue(), err.getvalue()
        assert not out.getvalue().strip(), out.getvalue()
        return 0.1

    monkeypatch.setattr(mtp, 'call', fast_call)


@pytest.mark.parametrize(
    ('extra_args', 'expected_spend'),
    [
        (['--spend', 'fresh'], 'fresh'),
        (['--spend', 'stale'], 'stale'),
        ([], 'none'),
    ],
)
def test_measure_pilot_cli_spend_modes(tmp_path: Path, extra_args: list[str], expected_spend: str):
    out_file = tmp_path / f'pilot-{expected_spend}.json'
    sub_env = {
        'PYTHONPATH': str(TOOLS),
        'HOME': str(tmp_path),
        'PATH': '/usr/bin:/bin',
        'OPS_WORKERS': '4',
        'LC_ALL': 'C.UTF-8',
    }
    r = subprocess.run(
        ['/usr/bin/python3', str(TOOLS / 'measure_turn_pause.py'), '--pilot', *extra_args, '--output', str(out_file)],
        env=sub_env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert r.stderr == '', r.stderr
    assert out_file.is_file()
    raw_text = out_file.read_text(encoding='utf-8')
    hostname = os.uname().nodename
    assert str(tmp_path) not in raw_text
    assert str(TOOLS) not in raw_text
    assert '/home/' not in raw_text and '/mnt/' not in raw_text and '/tmp/' not in raw_text
    if len(hostname) >= 3:
        assert hostname not in raw_text

    data = json.loads(raw_text)
    assert set(data) == {
        'version',
        'pilot',
        'workers',
        'target_p99_ms',
        'seed_events',
        'spend',
        'cases',
        'status',
    }
    assert data['version'] == 1
    assert data['pilot'] is True
    assert data['workers'] == 4
    assert data['spend'] == expected_spend
    assert data['status'] in ('passed', 'failed')
    assert r.returncode == (0 if data['status'] == 'passed' else 1)
    assert [(c['harness'], c['case'], c['samples']) for c in data['cases']] == [
        ('claude-code', 'serial', 1),
        ('claude-code', 'concurrent', 4),
        ('codex', 'serial', 1),
        ('codex', 'concurrent', 4),
    ]
    for case in data['cases']:
        expected_roots = 2 if case['case'] == 'concurrent' else 1
        assert len(case['counts']) == expected_roots
        for row in case['counts']:
            assert row['calls'] == 1
            assert row['events'] == 128
            assert row['state_bytes'] > 0

    refused_file = tmp_path / f'refused-{expected_spend}.json'
    refused_env = {**sub_env, 'OPS_WORKERS': '2'}
    refused = subprocess.run(
        [
            '/usr/bin/python3',
            str(TOOLS / 'measure_turn_pause.py'),
            '--pilot',
            *extra_args,
            '--output',
            str(refused_file),
        ],
        env=refused_env,
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert refused.returncode == 77
    refused_data = json.loads(refused_file.read_text(encoding='utf-8'))
    assert refused_data['status'] == 'refused'
    assert refused_data['spend'] == expected_spend


def test_measure_spend_state_and_latch_invariants(tmp_path: Path, monkeypatch):
    import measure_turn_pause as mtp
    from turn_pause.state import state_dir

    _install_in_process_hook(monkeypatch, mtp)

    with pytest.raises(ValueError):
        mtp.measure('codex', False, 1, tmp_path, spend='bogus')

    fresh_base = tmp_path / 'fresh'
    fresh_base.mkdir()
    fresh_res = mtp.measure('codex', True, 2, fresh_base, spend='fresh')
    fresh_case_dir = fresh_base / 'codex-concurrent'
    fresh_env = {'XDG_STATE_HOME': str(fresh_case_dir / 'state'), 'HOME': str(fresh_case_dir / 'home')}
    other_root = '00000000-0000-0000-0000-000000000000'
    other_sig = read(fresh_env, 'codex', other_root, None)
    assert other_sig.error is None
    assert other_sig.status == 'ok'
    assert other_sig.stale_after_ms == 600_000
    assert other_sig.baseline == 'ok'
    assert other_sig.entry is not None
    assert other_sig.entry.episode == f'codex:{other_root}@1'
    assert other_sig.entry.value == 700_000_000
    assert other_sig.entry.threshold == 500_000_000.0
    assert other_sig.entry.ratio == 1.4
    assert other_sig.entry.window_hours == 72
    assert other_sig.entry.complete is True
    assert other_sig.entry.credits_drawn_24h is None
    assert read(fresh_env, 'codex', mtp.NATIVE_ROOTS['codex'][0], None).entry is None
    assert spend.read_latch(state_dir(fresh_env)) == spend.HostLatch(seen_fresh=True, outage=None)

    stale_base = tmp_path / 'stale'
    stale_base.mkdir()
    before_ms = int(time.time() * 1000)
    stale_res = mtp.measure('codex', False, 2, stale_base, spend='stale')
    after_ms = int(time.time() * 1000)
    stale_case_dir = stale_base / 'codex-serial'
    stale_env = {'XDG_STATE_HOME': str(stale_case_dir / 'state'), 'HOME': str(stale_case_dir / 'home')}
    stale_sig = read(stale_env, 'codex', other_root, None)
    assert stale_sig.error is None
    assert stale_sig.generated_at is not None
    assert before_ms - 20 * 60 * 1000 <= stale_sig.generated_at <= after_ms - 20 * 60 * 1000
    assert state_of(stale_sig, after_ms, False) == 'stale'
    stale_latch = spend.read_latch(state_dir(stale_env))
    assert stale_latch.outage is not None and stale_latch.outage['state'] == 'stale'

    none_base = tmp_path / 'none'
    none_base.mkdir()
    none_res = mtp.measure('codex', False, 2, none_base, spend='none')
    none_case_dir = none_base / 'codex-serial'
    assert not (none_case_dir / 'state' / 'obs').exists()
    assert not (none_case_dir / 'state' / 'hq' / 'pause' / spend.HOST_FILE).exists()
    assert stale_res['counts'][0]['state_bytes'] > none_res['counts'][0]['state_bytes']
    assert fresh_res['counts'][0]['state_bytes'] > none_res['counts'][0]['state_bytes']

    # Corrupted signal during client loop fails the post-run spend_cache assertion.
    def corrupt_signal(env):
        (Path(env['XDG_STATE_HOME']) / 'obs' / SIGNAL_NAME).write_text('{bad', encoding='utf-8')

    _install_in_process_hook(monkeypatch, mtp, on_pre_tool_use=corrupt_signal)
    corrupt_base = tmp_path / 'corrupt'
    corrupt_base.mkdir()
    with pytest.raises(AssertionError):
        mtp.measure('codex', False, 1, corrupt_base, spend='fresh')


def test_measure_fresh_rewrites_signal_every_120_calls(tmp_path: Path, monkeypatch):
    import measure_turn_pause as mtp
    from turn_pause.state import state_dir

    observed: list[tuple[tuple[int, int, int], int]] = []
    obs_lock = threading.Lock()

    def record_signal(env):
        sig_path = Path(env['XDG_STATE_HOME']) / 'obs' / SIGNAL_NAME
        st = sig_path.stat()
        ident = (st.st_mtime_ns, st.st_size, st.st_ino)
        gen = json.loads(sig_path.read_text(encoding='utf-8'))['generated_at']
        with obs_lock:
            observed.append((ident, gen))

    _install_in_process_hook(monkeypatch, mtp, on_pre_tool_use=record_signal)

    serial_base = tmp_path / 'serial'
    serial_base.mkdir()
    mtp.measure('claude-code', False, 125, serial_base, spend='fresh')
    assert len(observed) == 125
    id_0, gen_0 = observed[0]
    assert set(observed[:119]) == {(id_0, gen_0)}
    id_1, gen_1 = observed[119]
    assert id_1[2] != id_0[2]
    assert id_1 != id_0
    assert gen_1 > gen_0
    assert set(observed[119:]) == {(id_1, gen_1)}

    serial_env = {
        'XDG_STATE_HOME': str(serial_base / 'claude-code-serial' / 'state'),
        'HOME': str(serial_base / 'claude-code-serial' / 'home'),
    }
    root = mtp.NATIVE_ROOTS['claude-code'][0]
    rec = Store(state_dir(serial_env)).read_record('claude-code', root)
    assert rec is not None and rec.state is not None and rec.state.spend_cache is not None
    assert rec.state.spend_cache.identity == id_1
    assert rec.state.spend_cache.generated_at == gen_1

    observed.clear()
    conc_base = tmp_path / 'conc'
    conc_base.mkdir()
    mtp.measure('codex', True, 65, conc_base, spend='fresh')
    assert len(observed) == 260
    distinct_gens = sorted({gen for _, gen in observed})
    distinct_ids = {ident for ident, _ in observed}
    assert len(distinct_gens) == 3
    assert len(distinct_ids) == 3

