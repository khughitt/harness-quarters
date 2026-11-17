"""Tests for tools/turn_pause/spend.py: reading obs spend-signals.json (schema 1)."""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

from turn_pause import spend
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
    write_signal(tmp_path, [make_tree_entry('codex', 'R')])
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
        'assert sig.entry is not None and sig.entry.value == 500_000_000'
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

