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
    with store.locked('claude', 'r1') as st:
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
    with store.locked('claude', 'r1') as st:
        assert st == want


def test_read_missing_is_none(tmp_path):
    assert Store(tmp_path).read('claude', 'nope') is None


def test_fresh_state_on_first_lock(tmp_path):
    with Store(tmp_path).locked('codex', 'r') as st:
        assert (st.harness, st.root, st.turn) == ('codex', 'r', None)


def test_exception_in_body_does_not_write(tmp_path):
    store = Store(tmp_path)
    with pytest.raises(RuntimeError):
        with store.locked('claude', 'r') as st:
            st.paused = 'calls'
            raise RuntimeError
    assert store.read('claude', 'r') is None


def test_parallel_updates_do_not_lose_counts(tmp_path):
    store = Store(tmp_path)
    with store.locked('claude', 'r') as st:
        st.turn = turn()
    errors = []

    def work():
        try:
            for _ in range(50):
                with store.locked('claude', 'r') as st:
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
    with store.locked('claude', 'r') as st:
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
    d[field] = json.loads(bad)
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
    with store.locked('claude', 'r') as st:
        st.turn = turn()
    file = tmp_path / 'claude-r.json'
    d = json.loads(file.read_text())
    target = d['turn']
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
    with store.locked('claude', 'r') as st:
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
    assert store.prune(now) == ['claude-old']
    assert store.read('claude', 'old') is None
    assert store.read('claude', 'young') is not None
    assert not (tmp_path / 'claude-old.lock').exists()


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
        with store.locked(harness, root) as st:
            st.cwd = cwd
        os.utime(tmp_path / f'{harness}-{root}.json', (mt, mt))
    assert store.latest_for_cwd('/p') == ('codex', 'b')
    assert store.latest_for_cwd('/zzz') is None


def test_root_for_agent(tmp_path):
    store = Store(tmp_path)
    with store.locked('codex', 'root1') as st:
        st.workers.add('w1')
    with store.locked('codex', 'root2') as st:
        st.workers.add('w2')
    with store.locked('claude', 'root3') as st:
        st.workers.add('w1')
    assert store.root_for_agent('codex', 'w2') == 'root2'
    assert store.root_for_agent('codex', 'w1') == 'root1'
    assert store.root_for_agent('codex', 'zzz') is None


def test_remove_waits_for_holder_and_waiter_does_not_lose_update(tmp_path):
    """A holds the lock, W waits, remove runs: W must see A's write or a fresh state, and
    W and a later C never hold the lock together."""
    import time
    store = Store(tmp_path)
    with store.locked('claude', 'r') as st:
        st.turn = turn()
    inside = []
    overlap = []
    started = threading.Event()

    def holder():
        with store.locked('claude', 'r') as st:
            started.set()
            time.sleep(0.3)
            st.turn.calls += 1

    def bump():
        with store.locked('claude', 'r') as st:
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
    with store.locked('claude', 'r') as st:
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
    with store.locked('claude', 'r') as st:
        st.paused = 'calls'
        t = threading.Thread(target=lambda: out.append(store.prune(now)))
        t.start()
        time.sleep(0.2)
    os.utime(path, (now, now))
    t.join()
    assert out == [[]]
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
    d['wakeups'] = [['x', 'b', 1]]
    path.write_text(json.dumps(d))
    with pytest.raises(StateError, match='wakeup not_before must be int/float, not str'):
        store.read('claude', 'r')
