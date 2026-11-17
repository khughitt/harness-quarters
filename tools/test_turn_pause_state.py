import os
import threading

import pytest

from turn_pause.counters import TurnState
from turn_pause.limits import Limits
from turn_pause.state import RootState, StateError, Store, Wakeup, state_dir

LIMITS = Limits(active_seconds=4 * 3600, calls=500, spawns=30, compactions=2)


def turn():
    return TurnState(started=1.0, limits=LIMITS, limits_sha='abc')


def age(path, now, days):
    os.utime(path, (now - days * 86400, now - days * 86400))


def test_state_dir_uses_xdg_then_home(tmp_path):
    assert state_dir({'XDG_STATE_HOME': str(tmp_path)}) == tmp_path / 'hq' / 'pause'
    assert state_dir({'HOME': str(tmp_path)}) == tmp_path / '.local' / 'state' / 'hq' / 'pause'


def test_round_trip(tmp_path):
    store = Store(tmp_path)
    with store.locked('claude', 'r1') as record:
        st = record.state
        st.turn = turn()
        st.turn.in_flight['c1'] = None
        st.turn.spawn_keys.add('k')
        st.paused = 'calls'
        st.grace_used['calls'] = 2
        st.workers.add('w1')
        st.worker_names.add('n1')
        st.cron_jobs['j1'] = 'do it'
        st.wakeups.append(Wakeup('wake', 10.0, 70.0))
        st.harness_pid = 42
        st.cwd = '/x'
        st.notified = True
        st.notify_error = 'e'
        st.budget_note = 'b'
        want = st
    got = store.read('claude', 'r1')
    assert got == want
    assert got.turn.in_flight == {'c1': None}
    assert isinstance(got.wakeups[0], Wakeup)
    with store.locked('claude', 'r1') as record:
        st = record.state
        assert st == want


def test_read_missing_is_none(tmp_path):
    assert Store(tmp_path).read('claude', 'nope') is None


def test_fresh_state_on_first_lock(tmp_path):
    with Store(tmp_path).locked('codex', 'r') as record:
        st = record.state
        assert (st.harness, st.root, st.turn) == ('codex', 'r', None)


def test_exception_in_body_does_not_write(tmp_path):
    store = Store(tmp_path)
    with pytest.raises(RuntimeError):
        with store.locked('claude', 'r') as record:
            st = record.state
            st.paused = 'calls'
            raise RuntimeError
    assert store.read('claude', 'r') is None


def test_parallel_updates_do_not_lose_counts(tmp_path):
    store = Store(tmp_path)
    with store.locked('claude', 'r') as record:
        st = record.state
        st.turn = turn()
    errors = []

    def work():
        try:
            for _ in range(50):
                with store.locked('claude', 'r') as record:
                    st = record.state
                    st.turn.calls += 1
        except Exception as e:  # pragma: no cover
            errors.append(e)

    threads = [threading.Thread(target=work) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors
    assert store.read('claude', 'r').turn.calls == 400


def test_no_temporary_files_left(tmp_path):
    store = Store(tmp_path)
    with store.locked('claude', 'r'):
        pass
    assert sorted(p.name for p in tmp_path.iterdir()) == ['claude-r.json', 'claude-r.lock']


def test_write_replaces_atomically(tmp_path):
    store = Store(tmp_path)
    with store.locked('claude', 'r'):
        pass
    inode = (tmp_path / 'claude-r.json').stat().st_ino
    with store.locked('claude', 'r') as record:
        st = record.state
        st.paused = 'calls'
    assert (tmp_path / 'claude-r.json').stat().st_ino != inode


@pytest.mark.parametrize('text', [
    '{not json',
    '[]',
    '{"harness": "claude"}',
    '{"harness": "claude", "root": "r", "turn": null, "workers": "abc"}',
    '{"harness": "claude", "root": "r", "turn": null, "wakeups": [{"text": "x"}]}',
    '{"harness": "claude", "root": "r", "turn": {"started": 1}}',
])
def test_corrupt_file_raises_state_error_with_path(tmp_path, text):
    store = Store(tmp_path)
    path = tmp_path / 'claude-r.json'
    path.write_text(text)
    with pytest.raises(StateError, match=str(path)):
        store.read('claude', 'r')
    with pytest.raises(StateError, match=str(path)):
        with store.locked('claude', 'r'):
            pass
    assert path.read_text() == text


@pytest.mark.parametrize('field,bad', [
    ('workers', '"abc"'), ('workers', '[1]'), ('worker_names', '"abc"'), ('cron_jobs', '[]'),
    ('grace_used', '{"calls": "x"}'), ('notified', '"yes"'), ('harness_pid', '"1"'),
    ('wakeups', '"ab"'), ('paused', '3'),
    ('wakeups', '[["x","b",1]]'), ('wakeups', '["abc"]'), ('wakeups', '[["x",1,"z"]]'),
    ('wakeups', '[["x",1]]'), ('wakeups', '[["x",true,2]]'), ('wakeups', '[[1,1,2]]'),
])
def test_wrong_types_in_complete_file_raise(tmp_path, field, bad):
    store = Store(tmp_path)
    with store.locked('claude', 'r'):
        pass
    path = tmp_path / 'claude-r.json'
    text = path.read_text()
    import json
    d = json.loads(text)
    d['state'][field] = json.loads(bad)
    path.write_text(json.dumps(d))
    with pytest.raises(StateError, match=str(path)):
        store.read('claude', 'r')


@pytest.mark.parametrize('path,bad', [
    (('spawn_keys',), '"abc"'), (('warned',), '"abc"'), (('calls',), '"7"'), (('calls',), 'true'),
    (('active',), '"1"'), (('started',), '"1"'), (('last_t',), '"1"'), (('limits_sha',), '1'),
    (('limits', 'calls'), '"x"'), (('limits', 'active_seconds'), 'null'), (('limits',), '[]'),
    (('limits',), '{"calls": 1}'),
    (('in_flight',), '[]'), (('in_flight',), '{"c": 1}'), (('in_flight',), '{"c": 1}'),
    (('spawn_keys',), '[1]'), (('compactions',), '1.5'),
])
def test_wrong_types_in_turn_raise(tmp_path, path, bad):
    import json
    store = Store(tmp_path)
    with store.locked('claude', 'r') as record:
        st = record.state
        st.turn = turn()
    file = tmp_path / 'claude-r.json'
    d = json.loads(file.read_text())
    target = d['state']['turn']
    for k in path[:-1]:
        target = target[k]
    target[path[-1]] = json.loads(bad)
    file.write_text(json.dumps(d))
    with pytest.raises(StateError, match=str(file)):
        store.read('claude', 'r')


def test_read_only_directory_raises_state_error(tmp_path):
    if os.geteuid() == 0:
        pytest.skip('running as root bypasses directory permissions')
    d = tmp_path / 'ro'
    d.mkdir()
    d.chmod(0o500)
    try:
        with pytest.raises(StateError, match=str(d)):
            with Store(d).locked('claude', 'r'):
                pass
    finally:
        d.chmod(0o700)


def test_fresh_directory_is_created_private(tmp_path):
    d = tmp_path / 'missing' / 'deeper'
    store = Store(d)
    with store.locked('claude', 'r') as record:
        st = record.state
        st.paused = 'calls'
    assert store.read('claude', 'r').paused == 'calls'
    assert (d.stat().st_mode & 0o777) == 0o700


def test_unwritable_parent_raises_state_error(tmp_path):
    if os.geteuid() == 0:
        pytest.skip('running as root bypasses directory permissions')
    parent = tmp_path / 'ro'
    parent.mkdir()
    parent.chmod(0o500)
    try:
        with pytest.raises(StateError, match=str(parent)):
            with Store(parent / 'sub').locked('claude', 'r'):
                pass
    finally:
        parent.chmod(0o700)


def test_directory_path_is_a_file_raises_state_error(tmp_path):
    f = tmp_path / 'f'
    f.write_text('')
    with pytest.raises(StateError, match=str(f)):
        with Store(f).locked('claude', 'r'):
            pass


@pytest.mark.parametrize('harness,root', [
    ('claude', '../x'), ('claude', 'a/b'), ('claude', '.'), ('claude', '..'), ('claude', ''),
    ('', 'r'), ('a/b', 'r'), ('claude', 'a\0b'),
])
def test_bad_names_refused(tmp_path, harness, root):
    store = Store(tmp_path)
    with pytest.raises(StateError, match='invalid state name'):
        with store.locked(harness, root):
            pass
    with pytest.raises(StateError, match='invalid state name'):
        store.read(harness, root)
    with pytest.raises(StateError, match='invalid state name'):
        store.remove(harness, root)


def test_prune_by_idle_time(tmp_path):
    store = Store(tmp_path)
    now = 10_000_000.0
    for root in ('old', 'young'):
        with store.locked('claude', root):
            pass
    age(tmp_path / 'claude-old.json', now, 8)
    age(tmp_path / 'claude-young.json', now, 6)
    assert store.prune(now, compactions_counted={})['cleared'] == 1
    assert store.read('claude', 'old') is None
    assert store.read('claude', 'young') is not None
    assert (tmp_path / 'claude-old.lock').exists()
    assert store.read_record('claude', 'old').state is None


def test_remove(tmp_path):
    store = Store(tmp_path)
    with store.locked('claude', 'r'):
        pass
    store.remove('claude', 'r')
    assert store.read('claude', 'r') is None
    store.remove('claude', 'r')


def test_latest_for_cwd_picks_newest(tmp_path):
    store = Store(tmp_path)
    for harness, root, cwd, mt in [('claude', 'a', '/p', 100), ('codex', 'b', '/p', 300),
                                   ('claude', 'c', '/p', 200), ('claude', 'd', '/q', 400)]:
        with store.locked(harness, root) as record:
            st = record.state
            st.cwd = cwd
        os.utime(tmp_path / f'{harness}-{root}.json', (mt, mt))
    assert store.latest_for_cwd('/p') == ('codex', 'b')
    assert store.latest_for_cwd('/zzz') is None


def test_root_for_agent(tmp_path):
    store = Store(tmp_path)
    with store.locked('codex', 'root1') as record:
        st = record.state
        st.workers.add('w1')
    with store.locked('codex', 'root2') as record:
        st = record.state
        st.workers.add('w2')
    with store.locked('claude', 'root3') as record:
        st = record.state
        st.workers.add('w1')
    assert store.root_for_agent('codex', 'w2') == 'root2'
    assert store.root_for_agent('codex', 'w1') == 'root1'
    assert store.root_for_agent('codex', 'zzz') is None


def test_remove_waits_for_holder_and_waiter_does_not_lose_update(tmp_path):
    """A holds the lock, W waits, remove runs: W must see A's write or a fresh state, and
    W and a later C never hold the lock together."""
    import time
    store = Store(tmp_path)
    with store.locked('claude', 'r') as record:
        st = record.state
        st.turn = turn()
    inside = []
    overlap = []
    started = threading.Event()

    def holder():
        with store.locked('claude', 'r') as record:
            st = record.state
            started.set()
            time.sleep(0.3)
            st.turn.calls += 1

    def bump():
        with store.locked('claude', 'r') as record:
            st = record.state
            inside.append(1)
            if len(inside) > 1:
                overlap.append(1)
            time.sleep(0.05)
            if st.turn is not None:
                st.turn.calls += 1
            inside.pop()

    a = threading.Thread(target=holder)
    a.start()
    started.wait()
    w = threading.Thread(target=bump)
    w.start()
    time.sleep(0.05)
    r = threading.Thread(target=lambda: store.remove('claude', 'r'))
    r.start()
    time.sleep(0.05)
    cs = [threading.Thread(target=bump) for _ in range(4)]
    for c in cs:
        c.start()
    for t in [a, w, r, *cs]:
        t.join()
    assert not overlap


def test_remove_does_not_unlink_while_lock_held(tmp_path):
    import time
    store = Store(tmp_path)
    with store.locked('claude', 'r') as record:
        st = record.state
        st.paused = 'calls'
    done = threading.Event()

    def rm():
        store.remove('claude', 'r')
        done.set()

    with store.locked('claude', 'r'):
        t = threading.Thread(target=rm)
        t.start()
        time.sleep(0.2)
        assert not done.is_set()
        assert (tmp_path / 'claude-r.json').exists()
    t.join()
    assert store.read('claude', 'r') is None


def test_prune_rechecks_idle_under_lock(tmp_path):
    import time
    store = Store(tmp_path)
    now = 10_000_000.0
    with store.locked('claude', 'r'):
        pass
    path = tmp_path / 'claude-r.json'
    age(path, now, 8)
    out = []
    with store.locked('claude', 'r') as record:
        st = record.state
        st.paused = 'calls'
        t = threading.Thread(target=lambda: out.append(store.prune(now, compactions_counted={})))
        t.start()
        time.sleep(0.2)
    os.utime(path, (now, now))
    t.join()
    assert len(out) == 1 and out[0]['affected'] == 0
    assert store.read('claude', 'r').paused == 'calls'


def test_waiter_on_unlinked_lock_file_retries_on_the_new_one(tmp_path):
    """A waiter blocked on a lock file that remove then unlinks must not enter beside a
    process that locks the replacement file."""
    import fcntl
    import time
    store = Store(tmp_path)
    with store.locked('claude', 'r'):
        pass
    lock = tmp_path / 'claude-r.lock'
    fd = os.open(lock, os.O_RDWR)
    fcntl.flock(fd, fcntl.LOCK_EX)
    inside = []
    overlap = []

    def body():
        with store.locked('claude', 'r'):
            inside.append(1)
            if len(inside) > 1:
                overlap.append(1)
            time.sleep(0.3)
            inside.pop()

    w = threading.Thread(target=body)
    w.start()
    time.sleep(0.2)
    lock.unlink()
    fcntl.flock(fd, fcntl.LOCK_UN)
    os.close(fd)
    time.sleep(0.1)
    c = threading.Thread(target=body)
    c.start()
    w.join()
    c.join()
    assert not overlap


def test_wakeup_message_names_the_field(tmp_path):
    import json
    store = Store(tmp_path)
    with store.locked('claude', 'r'):
        pass
    path = tmp_path / 'claude-r.json'
    d = json.loads(path.read_text())
    d['state']['wakeups'] = [['x', 'b', 1]]
    path.write_text(json.dumps(d))
    with pytest.raises(StateError, match='wakeup not_before must be int/float, not str'):
        store.read('claude', 'r')


def test_non_utf8_file_raises_state_error_with_path(tmp_path):
    store = Store(tmp_path)
    path = tmp_path / 'claude-r.json'
    path.write_bytes(b'\xff\xfe{')
    with pytest.raises(StateError, match=str(path)):
        store.read('claude', 'r')
    with pytest.raises(StateError, match=str(path)):
        with store.locked('claude', 'r'):
            pass
    with pytest.raises(StateError, match=str(path)):
        store.latest_for_cwd('/x')
    assert path.read_bytes() == b'\xff\xfe{'


PRE_MERGE_RECORD_JSON = (
    '{"version":1,"harness":"claude","root":"r1",'
    '"generation":"0123456789abcdef0123456789abcdef","created_at":1700000000.0,'
    '"turn_serial":1,"event_serial":1,"state":{"harness":"claude","root":"r1",'
    '"turn":{"started":1.0,"limits":{"active_seconds":14400,"calls":500,"spawns":30,"compactions":2},'
    '"limits_sha":"abc","active":0.0,"calls":3,"spawns":1,"compactions":0,"last_t":2.0,'
    '"in_flight":{"c1":null},"tools":{},"spawn_keys":["k"],"warned":[]},'
    '"paused":null,"grace_used":{},"workers":["w1"],"worker_names":["n1"],'
    '"cron_jobs":{"j1":"do it"},"wakeups":[["wake",10.0,70.0]],"harness_pid":42,'
    '"cwd":"/x","notified":false,"notify_error":null,"budget_note":"b"},'
    '"ended_at":null,"dropped_count":0,"dropped_through":null,'
    '"prompt_guards":{"cron":[],"wakeups":[]},'
    '"events":[{"version":1,"harness":"claude","root":"r1",'
    '"generation":"0123456789abcdef0123456789abcdef","turn":1,"sequence":1,'
    '"host":"test-host","at":1.0,"kind":"turn_start","reason":"genuine_user",'
    '"snapshot":{"limits_sha":"abc","paused":null,'
    '"counted":{"active":true,"calls":true,"spawns":true,"compactions":true},'
    '"scopes":{"active":"tree_active_seconds","calls":"root_attempts",'
    '"spawns":"tree_started","compactions":"root"},'
    '"active":{"used":0.0,"limit":14400},"calls":{"used":0,"limit":500},'
    '"spawns":{"used":0,"limit":30},"compactions":{"used":0,"limit":2}},'
    '"notification":null,"source":"hook"}]}'
)


def test_pre_merge_record_and_state_load(tmp_path):
    import json
    from turn_pause.state import parse_record, record_json, state_dict, state_from_dict

    assert '"spend"' not in PRE_MERGE_RECORD_JSON
    assert '"spend_cache"' not in PRE_MERGE_RECORD_JSON
    assert '"spend_snapshot"' not in PRE_MERGE_RECORD_JSON

    path = tmp_path / 'claude-r1.json'
    path.write_text(PRE_MERGE_RECORD_JSON)
    store = Store(tmp_path)

    loaded_record = store.read_record('claude', 'r1')
    assert loaded_record is not None
    assert loaded_record.version == 1
    assert loaded_record.spend is None
    assert loaded_record.state is not None
    assert loaded_record.state.spend_cache is None
    assert loaded_record.state.spend_snapshot is None

    re_encoded = record_json(loaded_record)
    assert re_encoded == PRE_MERGE_RECORD_JSON
    assert parse_record(re_encoded) == loaded_record

    # Explicit null values for optional fields also parse to None.
    with_nulls = json.loads(PRE_MERGE_RECORD_JSON)
    with_nulls['spend'] = None
    with_nulls['state']['spend_cache'] = None
    with_nulls['state']['spend_snapshot'] = None
    parsed_nulls = parse_record(json.dumps(with_nulls))
    assert parsed_nulls == loaded_record
    assert 'spend_cache' not in state_dict(parsed_nulls.state)
    assert 'spend_snapshot' not in state_dict(parsed_nulls.state)

    # Unknown extra keys or missing required keys still fail closed.
    bad_record_extra = json.loads(PRE_MERGE_RECORD_JSON)
    bad_record_extra['unknown'] = 1
    with pytest.raises(ValueError, match='root record fields differ'):
        parse_record(json.dumps(bad_record_extra))

    bad_state_extra = json.loads(PRE_MERGE_RECORD_JSON)['state']
    bad_state_extra['unknown'] = 1
    with pytest.raises(ValueError, match='active state fields differ'):
        state_from_dict(bad_state_extra)

    bad_state_missing = json.loads(PRE_MERGE_RECORD_JSON)['state']
    del bad_state_missing['budget_note']
    with pytest.raises(ValueError, match='active state fields differ'):
        state_from_dict(bad_state_missing)


def test_spend_record_round_trip(tmp_path, monkeypatch):
    import copy
    import json
    import pickle
    from turn_pause import spend
    from turn_pause.state import state_dict, write_atomic

    entry = spend.Entry(
        episode='codex:r1@1700000000000',
        value=550_000_000,
        threshold=350_000_000.0,
        ratio=1.57,
        window_hours=72,
        measured_at=1_700_001_000_000,
        complete=True,
        credits_drawn_24h=12.5,
    )
    cache = spend.Signal(
        identity=(1_700_001_000_000_000_000, 2048, 999),
        generated_at=1_700_001_000_000,
        stale_after_ms=600_000,
        status='ok',
        baseline='ok',
        entry=entry,
        error=None,
    )
    sr = spend.SpendRecord(
        episode='codex:r1@1700000000000',
        seen_value=550_000_000,
        delivered_value=500_000_000,
        acked_value=None,
    )

    store = Store(tmp_path)
    with store.locked('codex', 'r1') as record:
        record.spend = sr
        record.state.turn = turn()
        record.state.spend_cache = cache
        record.state.spend_snapshot = entry

    got_record = store.read_record('codex', 'r1')
    assert got_record is not None
    assert got_record.version == 1
    assert got_record.spend == sr
    assert got_record.state.spend_cache == cache
    assert got_record.state.spend_snapshot == entry
    assert copy.deepcopy(got_record) == got_record
    assert pickle.loads(pickle.dumps(got_record)) == got_record

    # Partial subset of optional state fields writes only the populated key.
    only_cache = RootState('codex', 'r1', None, spend_cache=cache)
    d_only_cache = state_dict(only_cache)
    assert 'spend_cache' in d_only_cache and 'spend_snapshot' not in d_only_cache
    only_snap = RootState('codex', 'r1', None, spend_snapshot=entry)
    d_only_snap = state_dict(only_snap)
    assert 'spend_snapshot' in d_only_snap and 'spend_cache' not in d_only_snap

    # Durable spend transitions fsync the directory even when serials/ended_at do not change.
    sync_calls = []

    def spy_write_atomic(path, data, *, sync_dir=True):
        sync_calls.append(sync_dir)
        return write_atomic(path, data, sync_dir=sync_dir)

    monkeypatch.setattr('turn_pause.state.write_atomic', spy_write_atomic)
    with store.locked('codex', 'r1') as record:
        record.state.cwd = '/portable/work'
    assert sync_calls[-1] is False

    with store.locked('codex', 'r1') as record:
        record.spend = spend.acknowledge(record.spend)
    assert sync_calls[-1] is True

    # SessionEnd clears active state (cache + snapshot) while preserving durable spend.
    assert store.end('codex', 'r1', 100.0, compactions_counted=False)
    ended = store.read_record('codex', 'r1')
    assert ended.state is None
    assert ended.spend == spend.SpendRecord(
        episode='codex:r1@1700000000000',
        seen_value=550_000_000,
        delivered_value=500_000_000,
        acked_value=550_000_000,
    )

    # Malformed spend field in stored JSON raises StateError.
    path = tmp_path / 'codex-r1.json'
    bad = json.loads(path.read_text())
    bad['spend'] = {'episode': 'x', 'seen_value': True, 'delivered_value': None, 'acked_value': None}
    path.write_text(json.dumps(bad))
    with pytest.raises(StateError, match=str(path)):
        store.read_record('codex', 'r1')


def test_lazy_splice_kept_with_spend(tmp_path):
    import copy
    import pickle
    from turn_pause import history, spend
    from turn_pause.state import _LazyEvents, parse_record, record_json

    store = Store(tmp_path)
    sr = spend.SpendRecord(
        episode='codex:r1@1700000000000',
        seen_value=900_000_000,
        delivered_value=800_000_000,
        acked_value=800_000_000,
    )
    with store.locked('codex', 'r1') as record:
        record.spend = sr
        record.state.turn = turn()
        record.turn_serial = 1
        for i in range(30):
            history.append_event(
                record,
                'warning',
                float(10 + i),
                reason='calls',
                snapshot=history.snapshot(record.state, compactions_counted=False),
            )
        expected_events = list(record.events)

    raw = (tmp_path / 'codex-r1.json').read_text()
    spend_idx = raw.index(',"spend":{')
    guards_idx = raw.index(',"prompt_guards":{"cron":')
    events_idx = raw.index('},"events":[')
    assert spend_idx < guards_idx < events_idx
    assert len(raw) - events_idx > 2048

    lazy = parse_record(raw, lazy_events=True)
    assert type(object.__getattribute__(lazy, 'events')) is _LazyEvents
    assert lazy.spend == sr
    assert record_json(lazy) == raw
    assert type(object.__getattribute__(lazy, 'events')) is _LazyEvents
    assert copy.deepcopy(lazy).spend == sr
    assert pickle.loads(pickle.dumps(lazy)).spend == sr
    assert lazy.events == expected_events


def test_spend_omitted_when_none(tmp_path):
    from turn_pause.state import record_json

    store = Store(tmp_path)
    with store.locked('codex', 'r1') as record:
        assert record.spend is None
        raw = record_json(record)
    assert '"spend"' not in raw
    assert ',"prompt_guards":{"cron":' in raw
    assert raw.index(',"prompt_guards":{"cron":') < raw.index('},"events":[')

