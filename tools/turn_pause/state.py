"""Locked per-root pause state: one JSON file per root session, updated under flock.

The hook imports this module on every call, so paths are str and os.path (pathlib is
built only by state_dir, for its callers), records are plain classes, and the atomic
write makes its own exclusive temp file rather than importing tempfile.
"""
from __future__ import annotations

import contextlib
import fcntl
import json
import os

from .counters import TurnState
from .limits import Limits
from .record import Record

IDLE_SECONDS = 7 * 86400


class StateError(Exception):
    """A state file is unreadable, unparsable or unwritable; the hook refuses the call."""


class Wakeup(Record):
    __slots__ = _fields = ('text', 'not_before', 'not_after')


class RootState(Record):
    __slots__ = _fields = ('harness', 'root', 'turn', 'paused', 'grace_used', 'workers', 'worker_names',
                           'cron_jobs', 'wakeups', 'harness_pid', 'cwd', 'notified', 'notify_error', 'budget_note')
    _defaults = {'paused': None, 'harness_pid': None, 'cwd': None, 'notified': False, 'notify_error': None,
                 'budget_note': None}
    _factories = {'grace_used': dict, 'workers': set, 'worker_names': set, 'cron_jobs': dict, 'wakeups': list}


def state_path(env: Mapping[str, str] = os.environ) -> str:
    """The state directory as a str: $XDG_STATE_HOME/hq/pause, else ~/.local/state/hq/pause."""
    base = env.get('XDG_STATE_HOME')
    if base:
        return os.path.join(base, 'hq', 'pause')
    return os.path.join(env['HOME'], '.local', 'state', 'hq', 'pause')


def state_dir(env: Mapping[str, str] = os.environ):
    """state_path as a pathlib.Path."""
    from pathlib import Path
    return Path(state_path(env))


def _check(value, kind, what):
    kinds = kind if isinstance(kind, tuple) else (kind,)
    if not isinstance(value, kinds) or (isinstance(value, bool) and bool not in kinds):
        names = '/'.join(k.__name__ for k in kinds)
        raise TypeError(f'{what} must be {names}, not {type(value).__name__}')
    return value


def _num(value, what):
    return float(_check(value, (int, float), what))


def _opt(value, kind, what):
    return None if value is None else _check(value, kind, what)


def _strs(value, what):
    _check(value, list, what)
    for v in value:
        _check(v, str, what)
    return value


def _str_map(value, kind, what):
    _check(value, dict, what)
    for k, v in value.items():
        _check(k, str, what)
        _check(v, kind, what)
    return value


def _turn_from_dict(t: dict) -> TurnState:
    expected = set(TurnState._fields)
    if set(t) != expected:
        raise KeyError(f'turn fields differ: missing {sorted(expected - set(t))}, extra {sorted(set(t) - expected)}')
    lim = _check(t['limits'], dict, 'turn.limits')
    if set(lim) != set(Limits._fields):
        raise KeyError(f'turn.limits fields differ: {sorted(lim)}')
    limits = Limits(**{k: _check(v, int, f'turn.limits.{k}') for k, v in lim.items()})
    in_flight = _check(t['in_flight'], dict, 'turn.in_flight')
    for k, v in in_flight.items():
        _check(k, str, 'turn.in_flight key')
        _opt(v, str, 'turn.in_flight value')
    tools = _check(t['tools'], dict, 'turn.tools')
    for k, v in tools.items():
        _check(k, str, 'turn.tools key')
        _opt(v, str, 'turn.tools value')
    return TurnState(
        started=_num(t['started'], 'turn.started'),
        limits=limits,
        limits_sha=_check(t['limits_sha'], str, 'turn.limits_sha'),
        active=_num(t['active'], 'turn.active'),
        calls=_check(t['calls'], int, 'turn.calls'),
        spawns=_check(t['spawns'], int, 'turn.spawns'),
        compactions=_check(t['compactions'], int, 'turn.compactions'),
        last_t=None if t['last_t'] is None else _num(t['last_t'], 'turn.last_t'),
        in_flight=dict(in_flight),
        tools=dict(tools),
        spawn_keys=set(_strs(t['spawn_keys'], 'turn.spawn_keys')),
        warned=set(_strs(t['warned'], 'turn.warned')),
    )


def _to_json(st: RootState) -> str:
    return json.dumps({
        'harness': st.harness, 'root': st.root,
        'turn': None if st.turn is None else json.loads(st.turn.to_json()),
        'paused': st.paused, 'grace_used': st.grace_used,
        'workers': sorted(st.workers), 'worker_names': sorted(st.worker_names),
        'cron_jobs': st.cron_jobs,
        'wakeups': [[w.text, w.not_before, w.not_after] for w in st.wakeups],
        'harness_pid': st.harness_pid, 'cwd': st.cwd, 'notified': st.notified,
        'notify_error': st.notify_error, 'budget_note': st.budget_note,
    })


def _from_json(text: str) -> RootState:
    d = _check(json.loads(text), dict, 'state')
    turn = d['turn']
    wakeups = []
    for w in _check(d['wakeups'], list, 'wakeups'):
        if not isinstance(w, list) or len(w) != 3:
            raise TypeError(f'wakeup must be a list of 3, not {w!r}')
        text_, before, after = w
        wakeups.append(Wakeup(_check(text_, str, 'wakeup text'),
                              _num(before, 'wakeup not_before'),
                              _num(after, 'wakeup not_after')))
    return RootState(
        harness=_check(d['harness'], str, 'harness'),
        root=_check(d['root'], str, 'root'),
        turn=None if turn is None else _turn_from_dict(_check(turn, dict, 'turn')),
        paused=_opt(d['paused'], str, 'paused'),
        grace_used=_str_map(d['grace_used'], int, 'grace_used'),
        workers=set(_strs(d['workers'], 'workers')),
        worker_names=set(_strs(d['worker_names'], 'worker_names')),
        cron_jobs=_str_map(d['cron_jobs'], str, 'cron_jobs'),
        wakeups=wakeups,
        harness_pid=_opt(d['harness_pid'], int, 'harness_pid'),
        cwd=_opt(d['cwd'], str, 'cwd'),
        notified=_check(d['notified'], bool, 'notified'),
        notify_error=_opt(d['notify_error'], str, 'notify_error'),
        budget_note=_opt(d['budget_note'], str, 'budget_note'),
    )


class Store:
    def __init__(self, dir):
        self.dir = os.fspath(dir)

    def _stem(self, harness: str, root: str) -> str:
        for part in (harness, root):
            if not part or '/' in part or part in ('.', '..') or '\0' in part:
                raise StateError(f'{self.dir}: invalid state name {harness!r}/{root!r}')
        return f'{harness}-{root}'

    def _path(self, name: str) -> str:
        return os.path.join(self.dir, name)

    def _load(self, path: str) -> RootState | None:
        try:
            with open(path, 'rb') as f:
                text = f.read().decode()
        except FileNotFoundError:
            return None
        except OSError as e:
            raise StateError(f'cannot read {path}: {e}') from e
        except UnicodeDecodeError as e:
            raise StateError(f'cannot parse {path}: {e}') from e
        try:
            return _from_json(text)
        except Exception as e:  # any malformed content must refuse, never escape raw
            raise StateError(f'cannot parse {path}: {type(e).__name__}: {e}') from e

    def _write(self, path: str, st: RootState) -> None:
        tmp = None
        try:
            name = f'{path}.{os.getpid()}.{os.urandom(6).hex()}.tmp'
            fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC, 0o600)
            tmp = name
            with os.fdopen(fd, 'w') as f:
                f.write(_to_json(st))
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, path)
            tmp = None
        except OSError as e:
            raise StateError(f'cannot write {path}: {e}') from e
        finally:
            if tmp is not None:
                with contextlib.suppress(OSError):
                    os.unlink(tmp)

    @contextlib.contextmanager
    def _flocked(self, stem: str) -> Iterator[str]:
        """Hold the exclusive lock on <stem>.lock. The lock file may be unlinked by remove
        and prune while held, so after flock the fd must still be the file at that path;
        otherwise a newer lock file exists and we retry on it."""
        lock = self._path(f'{stem}.lock')
        try:
            os.makedirs(self.dir, mode=0o700, exist_ok=True)
        except OSError as e:
            raise StateError(f'cannot create state directory {self.dir}: {e}') from e
        while True:
            try:
                fd = os.open(lock, os.O_CREAT | os.O_RDWR | os.O_CLOEXEC, 0o600)
            except OSError as e:
                raise StateError(f'cannot open lock {lock}: {e}') from e
            try:
                try:
                    fcntl.flock(fd, fcntl.LOCK_EX)
                    try:
                        current = os.stat(lock).st_ino
                    except FileNotFoundError:
                        current = None
                except OSError as e:
                    raise StateError(f'cannot lock {lock}: {e}') from e
                if current != os.fstat(fd).st_ino:
                    continue
                yield lock
                return
            finally:
                os.close(fd)

    @contextlib.contextmanager
    def locked(self, harness: str, root: str) -> Iterator[RootState]:
        stem = self._stem(harness, root)
        path = self._path(f'{stem}.json')
        with self._flocked(stem):
            st = self._load(path) or RootState(harness, root, None)
            yield st
            self._write(path, st)

    def read(self, harness: str, root: str) -> RootState | None:
        return self._load(self._path(f'{self._stem(harness, root)}.json'))

    def _files(self) -> list[str]:
        try:
            names = os.listdir(self.dir)
        except FileNotFoundError:
            return []
        except OSError as e:
            raise StateError(f'cannot list {self.dir}: {e}') from e
        return [self._path(n) for n in sorted(names) if n.endswith('.json') and not n.startswith('.')]

    def latest_for_cwd(self, cwd: str) -> tuple[str, str] | None:
        best = None
        for path in self._files():
            st = self._load(path)
            if st is None or st.cwd != cwd:
                continue
            mtime = os.stat(path).st_mtime
            if best is None or mtime > best[0]:
                best = (mtime, st.harness, st.root)
        return None if best is None else (best[1], best[2])

    def root_for_agent(self, harness: str, agent_id: str) -> str | None:
        for path in self._files():
            st = self._load(path)
            if st is not None and st.harness == harness and agent_id in st.workers:
                return st.root
        return None

    @staticmethod
    def _unlink(path: str) -> None:
        try:
            os.unlink(path)
        except FileNotFoundError:
            pass
        except OSError as e:
            raise StateError(f'cannot remove {path}: {e}') from e

    def _delete_locked(self, stem: str, min_idle: float | None, now: float = 0.0) -> bool:
        """Under the lock, unlink the state and its lock file (the lock file last, so a
        waiter notices the swap through the inode check in _flocked)."""
        with self._flocked(stem) as lock:
            path = self._path(f'{stem}.json')
            if min_idle is not None:
                try:
                    idle = now - os.stat(path).st_mtime
                except FileNotFoundError:
                    idle = None
                except OSError as e:
                    raise StateError(f'cannot stat {path}: {e}') from e
                if idle is None or idle <= min_idle:
                    return False
            self._unlink(path)
            self._unlink(lock)
            return True

    def remove(self, harness: str, root: str) -> None:
        self._delete_locked(self._stem(harness, root), None)

    def prune(self, now: float, max_idle: float = IDLE_SECONDS) -> list[str]:
        """Remove states idle longer than max_idle (by file mtime, re-checked under the
        lock); return their stems."""
        removed = []
        for path in self._files():
            try:
                idle = now - os.stat(path).st_mtime
            except FileNotFoundError:
                continue
            except OSError as e:
                raise StateError(f'cannot stat {path}: {e}') from e
            stem = os.path.basename(path)[:-len('.json')]
            if idle > max_idle and self._delete_locked(stem, max_idle, now):
                removed.append(stem)
        return removed
