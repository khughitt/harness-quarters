"""Locked per-root pause state: one JSON file per root session, updated under flock.

The hook imports this module on every call, so paths are str and os.path (pathlib is
built only by state_dir, for its callers), records are plain classes, and the atomic
write makes its own exclusive temp file rather than importing tempfile.
"""
from __future__ import annotations

import contextlib
import fcntl
import json
import math
import os
import stat
import time

from .counters import TurnState
from .limits import Limits
from .record import Record
from .prompt import empty_guards

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


class RootRecord(Record):
    __slots__ = _fields = ('version', 'harness', 'root', 'generation', 'created_at', 'turn_serial',
                           'event_serial', 'state', 'ended_at', 'events', 'dropped_count', 'dropped_through',
                           'prompt_guards')
    _defaults = {'version': 1, 'turn_serial': 0, 'event_serial': 0, 'state': None,
                 'ended_at': None, 'dropped_count': 0, 'dropped_through': None}
    _factories = {'events': list, 'prompt_guards': empty_guards}


def new_record(harness: str, root: str, now: float) -> RootRecord:
    return RootRecord(harness=harness, root=root, generation=os.urandom(16).hex(),
                      created_at=now, state=RootState(harness, root, None))


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
    result = float(_check(value, (int, float), what))
    if not math.isfinite(result) or result < 0:
        raise ValueError(f'{what} must be finite and nonnegative')
    return result


def _opt(value, kind, what):
    return None if value is None else _check(value, kind, what)


def _integer(value, what, minimum=0):
    if _check(value, int, what) < minimum:
        raise ValueError(f'{what} must be at least {minimum}')
    return value


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
    limits = Limits(**{k: _integer(v, f'turn.limits.{k}') for k, v in lim.items()})
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
        calls=_integer(t['calls'], 'turn.calls'),
        spawns=_integer(t['spawns'], 'turn.spawns'),
        compactions=_integer(t['compactions'], 'turn.compactions'),
        last_t=None if t['last_t'] is None else _num(t['last_t'], 'turn.last_t'),
        in_flight=dict(in_flight),
        tools=dict(tools),
        spawn_keys=set(_strs(t['spawn_keys'], 'turn.spawn_keys')),
        warned=set(_strs(t['warned'], 'turn.warned')),
    )


def state_dict(st: RootState) -> dict:
    return {
        'harness': st.harness, 'root': st.root,
        'turn': None if st.turn is None else json.loads(st.turn.to_json()),
        'paused': st.paused, 'grace_used': st.grace_used,
        'workers': sorted(st.workers), 'worker_names': sorted(st.worker_names),
        'cron_jobs': st.cron_jobs,
        'wakeups': [[w.text, w.not_before, w.not_after] for w in st.wakeups],
        'harness_pid': st.harness_pid, 'cwd': st.cwd, 'notified': st.notified,
        'notify_error': st.notify_error, 'budget_note': st.budget_note,
    }


def state_from_dict(d: dict) -> RootState:
    _check(d, dict, 'state')
    if set(d) != set(RootState._fields):
        raise ValueError('active state fields differ')
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


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate JSON key')
        result[key] = value
    return result


def _constant(value):
    raise ValueError('non-JSON numeric constant')


def parse_json(text: str):
    return json.loads(text, object_pairs_hook=_unique, parse_constant=_constant)


def record_json(record: RootRecord) -> str:
    from .history import encode
    data = record._asdict()
    data['state'] = None if record.state is None else state_dict(record.state)
    return encode(data)


def parse_record(text: str) -> RootRecord:
    from .history import MAX_BYTES, MAX_EVENTS, encode, validate_event
    d = _check(parse_json(text), dict, 'root record')
    if 'version' not in d:
        raise ValueError('unversioned pause state needs explicit offline migration')
    if type(d['version']) is not int or d['version'] != 1:
        raise ValueError('unsupported pause record version')
    if set(d) != set(RootRecord._fields):
        raise ValueError('root record fields differ')
    _validate_guards(d['prompt_guards'])
    for name in ('harness', 'root', 'generation'):
        if not _check(d[name], str, name):
            raise ValueError(f'{name} must not be empty')
    if len(d['generation']) != 32 or any(c not in '0123456789abcdef' for c in d['generation']):
        raise ValueError('invalid root generation')
    for name in ('turn_serial', 'event_serial', 'dropped_count'):
        if _check(d[name], int, name) < 0:
            raise ValueError(f'{name} must be nonnegative')
    d['created_at'] = _num(d['created_at'], 'created_at')
    for name in ('ended_at', 'dropped_through'):
        if d[name] is not None:
            d[name] = _num(d[name], name)
    d['state'] = None if d['state'] is None else state_from_dict(d['state'])
    if d['state'] is not None and (d['state'].harness, d['state'].root) != (d['harness'], d['root']):
        raise ValueError('active state identity differs')
    events = _check(d['events'], list, 'events')
    if len(events) > MAX_EVENTS or len(encode(events).encode()) > MAX_BYTES:
        raise ValueError('history exceeds its bounds')
    previous = d['dropped_count']
    for event in events:
        validate_event(event)
        if (event['harness'], event['root'], event['generation']) != (d['harness'], d['root'], d['generation']):
            raise ValueError('history identity differs')
        if event['sequence'] != previous + 1 or event['turn'] > d['turn_serial']:
            raise ValueError('invalid history sequence/turn')
        previous = event['sequence']
    if previous != d['event_serial']:
        raise ValueError('history serial differs')
    return RootRecord(**d)


def _validate_guards(value) -> None:
    _check(value, dict, 'prompt_guards')
    if set(value) != {'cron', 'wakeups'}:
        raise ValueError('prompt_guards fields differ')

    def digest(key):
        if not isinstance(key, str) or len(key) != 64 or any(c not in '0123456789abcdef' for c in key):
            raise ValueError('invalid prompt_guards digest')

    cron = _check(value['cron'], list, 'prompt_guards.cron')
    for key in cron:
        digest(key)
    if cron != sorted(set(cron)):
        raise ValueError('prompt_guards.cron must be sorted and unique')
    wakeups = _check(value['wakeups'], list, 'prompt_guards.wakeups')
    for row in wakeups:
        if not isinstance(row, list) or len(row) != 3:
            raise ValueError('invalid prompt_guards wake row')
        digest(row[0])
        before = _num(row[1], 'prompt_guards.not_before')
        after = _num(row[2], 'prompt_guards.not_after')
        if before > after:
            raise ValueError('reversed prompt_guards window')
    if wakeups != [list(row) for row in sorted(set(tuple(row) for row in wakeups))]:
        raise ValueError('prompt_guards.wakeups must be sorted and unique')


def write_atomic(path: str, data: bytes) -> None:
    """One durable replacement, also used by the explicit offline converter."""
    temporary = None
    try:
        temporary = f'{path}.{os.getpid()}.{os.urandom(6).hex()}.tmp'
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC, 0o600)
        with os.fdopen(fd, 'wb') as output:
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
        temporary = None
        directory = os.open(os.path.dirname(path), os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    except OSError as error:
        raise StateError(f'cannot write {path}: {error}') from error
    finally:
        if temporary is not None:
            with contextlib.suppress(OSError):
                os.unlink(temporary)


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

    def _load(self, path: str) -> RootRecord | None:
        try:
            fd = os.open(path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_NONBLOCK)
            with os.fdopen(fd, 'rb') as f:
                if not stat.S_ISREG(os.fstat(f.fileno()).st_mode):
                    raise StateError(f'not a regular pause record: {path}')
                text = f.read().decode()
        except FileNotFoundError:
            return None
        except OSError as e:
            raise StateError(f'cannot read {path}: {e}') from e
        except UnicodeDecodeError as e:
            raise StateError(f'cannot parse {path}: {e}') from e
        try:
            record = parse_record(text)
            if os.path.basename(path) != self._stem(record.harness, record.root) + '.json':
                raise ValueError('record filename and identity differ')
            return record
        except Exception as e:  # any malformed content must refuse, never escape raw
            raise StateError(f'cannot parse {path}: {type(e).__name__}: {e}') from e

    def _write(self, path: str, record: RootRecord) -> None:
        write_atomic(path, record_json(record).encode())

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
    def locked(self, harness: str, root: str, *, create: bool = True) -> Iterator[RootRecord | None]:
        stem = self._stem(harness, root)
        path = self._path(f'{stem}.json')
        with self._flocked(stem):
            record = self._load(path)
            if record is None and create:
                record = new_record(harness, root, time.time())
            yield record
            if record is not None:
                self._write(path, record)

    def read(self, harness: str, root: str) -> RootState | None:
        record = self.read_record(harness, root)
        return None if record is None else record.state

    def read_record(self, harness: str, root: str) -> RootRecord | None:
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
            record = self._load(path)
            st = None if record is None else record.state
            if st is None or st.cwd != cwd:
                continue
            mtime = os.stat(path).st_mtime
            if best is None or mtime > best[0]:
                best = (mtime, st.harness, st.root)
        return None if best is None else (best[1], best[2])

    def root_for_agent(self, harness: str, agent_id: str) -> str | None:
        for path in self._files():
            record = self._load(path)
            st = None if record is None else record.state
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
