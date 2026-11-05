"""Locked per-root pause state: one JSON file per root session, updated under flock.

The hook imports this module on every call, so paths are str and os.path (pathlib is
built only by state_dir, for its callers), records are plain classes, and the atomic
write makes its own exclusive temp file rather than importing tempfile.
"""
from __future__ import annotations

import fcntl
import os
import stat
import time

from .counters import TurnState
from .limits import Limits
from .record import Record, jencode_compact as _ENCODE, jloads_strict

IDLE_SECONDS = 7 * 86400
ENDED_SECONDS = 30 * 86400
MAX_ENDED = 512
MAX_MAINTENANCE = 32
MAX_EVENTS = 128
MAX_BYTES = 131072


class _CM:
    __slots__ = ('_gen',)

    def __init__(self, gen):
        self._gen = gen

    def __enter__(self):
        return next(self._gen)

    def __exit__(self, exc_type, exc, tb):
        if exc_type is None:
            try:
                next(self._gen)
            except StopIteration:
                return False
            raise RuntimeError('generator did not stop')
        try:
            self._gen.throw(exc_type() if exc is None else exc)
        except StopIteration as e:
            return e is not exc
        except BaseException as e:
            if e is exc:
                return False
            raise
        raise RuntimeError('generator did not stop after throw()')


def _contextmanager(fn):
    def helper(*args, **kwargs):
        return _CM(fn(*args, **kwargs))
    return helper


def _empty_guards() -> dict:
    return {'cron': [], 'wakeups': []}


class StateError(Exception):
    """A state file is unreadable, unparsable or unwritable; the hook refuses the call."""


class _LazyEvents:
    __slots__ = ('raw', 'ctx', 'path')

    def __init__(self, raw: str, ctx: tuple, path: str | None = None):
        self.raw = raw
        self.ctx = ctx
        self.path = path

    def load(self) -> list[dict]:
        try:
            return _validate_events(parse_json(self.raw), *self.ctx)
        except Exception as e:
            if self.path is not None:
                raise StateError(f'cannot parse {self.path}: {type(e).__name__}: {e}') from e
            raise


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
    _factories = {'events': list, 'prompt_guards': _empty_guards}

    def __getattribute__(self, name: str):
        val = object.__getattribute__(self, name)
        if type(val) is _LazyEvents:
            val = val.load()
            object.__setattr__(self, name, val)
        return val

    def __reduce__(self):
        return (type(self), self._astuple())


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
    if not (0.0 <= result < float('inf')):
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
        'turn': None if st.turn is None else st.turn.to_dict(),
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


_EVENTS_MARKER = '},"events":['


def parse_json(text: str):
    return jloads_strict(text)


def record_json(record: RootRecord) -> str:
    raw_ev = object.__getattribute__(record, 'events')
    header = {
        'version': record.version,
        'harness': record.harness,
        'root': record.root,
        'generation': record.generation,
        'created_at': record.created_at,
        'turn_serial': record.turn_serial,
        'event_serial': record.event_serial,
        'state': None if record.state is None else state_dict(record.state),
        'ended_at': record.ended_at,
        'dropped_count': record.dropped_count,
        'dropped_through': record.dropped_through,
        'prompt_guards': record.prompt_guards,
    }
    prefix = _ENCODE(header)
    if type(raw_ev) is _LazyEvents:
        return f'{prefix[:-1]},"events":{raw_ev.raw}}}'
    return f'{prefix[:-1]},"events":{_ENCODE(raw_ev)}}}'


def _validate_events(events, harness, root, generation, turn_serial, event_serial, dropped_count) -> list[dict]:
    from .history import validate_event
    events = _check(events, list, 'events')
    if len(events) > MAX_EVENTS or len(_ENCODE(events).encode()) > MAX_BYTES:
        raise ValueError('history exceeds its bounds')
    previous = dropped_count
    ident = (harness, root, generation)
    for event in events:
        validate_event(event)
        if (event['harness'], event['root'], event['generation']) != ident:
            raise ValueError('history identity differs')
        if event['sequence'] != previous + 1 or event['turn'] > turn_serial:
            raise ValueError('invalid history sequence/turn')
        previous = event['sequence']
    if previous != event_serial:
        raise ValueError('history serial differs')
    return events


def parse_record(text: str, *, lazy_events: bool = False, path: str | None = None) -> RootRecord:
    raw_candidate = None
    d = None
    if lazy_events and text.endswith(']}'):
        idx = text.rfind(_EVENTS_MARKER)
        guards_idx = text.rfind(',"prompt_guards":{"cron":')
        if guards_idx != -1 and idx > guards_idx and (len(text) - idx) > 2048:
            raw_candidate = text[idx + len(_EVENTS_MARKER) - 1:-1]
            if len(raw_candidate.encode()) > MAX_BYTES:
                raise ValueError('history exceeds its bounds')
            d = _check(parse_json(text[:idx + 1] + ',"events":[]}'), dict, 'root record')
    if d is None:
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
    ctx = (d['harness'], d['root'], d['generation'], d['turn_serial'], d['event_serial'], d['dropped_count'])
    if raw_candidate is not None:
        count = d['event_serial'] - d['dropped_count']
        prefix = (f'{{"version":1,"harness":{_ENCODE(d["harness"])},"root":{_ENCODE(d["root"])},'
                  f'"generation":{_ENCODE(d["generation"])},"turn":')
        if (0 < count <= MAX_EVENTS
                and raw_candidate.count(prefix) == count
                and raw_candidate.count(',"source":"hook"}') == count):
            d['events'] = _LazyEvents(raw_candidate, ctx, path)
            return RootRecord(**d)
        d['events'] = _validate_events(parse_json(raw_candidate), *ctx)
        return RootRecord(**d)
    d['events'] = _validate_events(d['events'], *ctx)
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


def write_atomic(path: str, data: bytes, *, sync_dir: bool = True) -> None:
    """One durable replacement, also used by the explicit offline converter."""
    temporary = None
    try:
        temporary = f'{path}.{os.getpid()}.{os.urandom(6).hex()}.tmp'
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC, 0o600)
        try:
            view = memoryview(data)
            while view:
                view = view[os.write(fd, view):]
            os.fsync(fd)
        finally:
            os.close(fd)
        os.replace(temporary, path)
        temporary = None
        if sync_dir:
            directory = os.open(os.path.dirname(path), os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
    except OSError as error:
        raise StateError(f'cannot write {path}: {error}') from error
    finally:
        if temporary is not None:
            try:
                os.unlink(temporary)
            except OSError:
                pass


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

    def _load(self, path: str, *, lazy_events: bool = False) -> RootRecord | None:
        try:
            fd = os.open(path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_NONBLOCK)
            try:
                st = os.fstat(fd)
                if not stat.S_ISREG(st.st_mode):
                    raise StateError(f'not a regular pause record: {path}')
                chunks = []
                while True:
                    chunk = os.read(fd, max(65536, st.st_size + 1))
                    if not chunk:
                        break
                    chunks.append(chunk)
                text = (chunks[0] if len(chunks) == 1 else b''.join(chunks)).decode()
            finally:
                os.close(fd)
        except FileNotFoundError:
            return None
        except OSError as e:
            raise StateError(f'cannot read {path}: {e}') from e
        except UnicodeDecodeError as e:
            raise StateError(f'cannot parse {path}: {e}') from e
        try:
            record = parse_record(text, lazy_events=lazy_events, path=path)
            if os.path.basename(path) != self._stem(record.harness, record.root) + '.json':
                raise ValueError('record filename and identity differ')
            return record
        except Exception as e:  # any malformed content must refuse, never escape raw
            raise StateError(f'cannot parse {path}: {type(e).__name__}: {e}') from e

    def _write(self, path: str, record: RootRecord, *, sync_dir: bool = True) -> None:
        write_atomic(path, record_json(record).encode(), sync_dir=sync_dir)

    @_contextmanager
    def _flocked(self, stem: str) -> Iterator[str]:
        """Hold the exclusive lock on <stem>.lock. The lock file may be unlinked by remove
        and prune while held, so after flock the fd must still be the file at that path;
        otherwise a newer lock file exists and we retry on it."""
        lock = self._path(f'{stem}.lock')
        while True:
            try:
                fd = os.open(lock, os.O_CREAT | os.O_RDWR | os.O_CLOEXEC, 0o600)
            except FileNotFoundError:
                try:
                    os.makedirs(self.dir, mode=0o700, exist_ok=True)
                except OSError as e:
                    raise StateError(f'cannot create state directory {self.dir}: {e}') from e
                try:
                    fd = os.open(lock, os.O_CREAT | os.O_RDWR | os.O_CLOEXEC, 0o600)
                except OSError as e:
                    raise StateError(f'cannot open lock {lock}: {e}') from e
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

    @_contextmanager
    def locked(self, harness: str, root: str, *, create: bool = True) -> Iterator[RootRecord | None]:
        stem = self._stem(harness, root)
        path = self._path(f'{stem}.json')
        with self._flocked(stem):
            record = self._load(path, lazy_events=True)
            creating = record is None
            if creating and create:
                record = new_record(harness, root, time.time())
            before = None if record is None else (record.turn_serial, record.event_serial, record.ended_at)
            yield record
            if record is not None:
                sync_dir = creating or (record.turn_serial, record.event_serial, record.ended_at) != before
                self._write(path, record, sync_dir=sync_dir)

    def read(self, harness: str, root: str) -> RootState | None:
        record = self._load(self._path(f'{self._stem(harness, root)}.json'), lazy_events=True)
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
            record = self._load(path, lazy_events=True)
            st = None if record is None else record.state
            if st is None or st.cwd != cwd:
                continue
            mtime = os.stat(path).st_mtime
            if best is None or mtime > best[0]:
                best = (mtime, st.harness, st.root)
        return None if best is None else (best[1], best[2])

    def root_for_agent(self, harness: str, agent_id: str) -> str | None:
        for path in self._files():
            record = self._load(path, lazy_events=True)
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

    @staticmethod
    def _end_record(record, now, compactions_counted, reason):
        from .history import append_event, snapshot
        from .prompt import capture_guards
        closing = snapshot(record.state, compactions_counted=compactions_counted)
        record.prompt_guards = capture_guards(record.state)
        if record.turn_serial:
            append_event(record, 'session_end', now, reason=reason, snapshot=closing)
        record.state = None
        record.ended_at = now

    def end(self, harness: str, root: str, now: float, *,
            compactions_counted: bool, reason: str = 'session_end') -> bool:
        stem = self._stem(harness, root)
        path = self._path(stem + '.json')
        with self._flocked(stem):
            record = self._load(path)
            if record is None or record.state is None:
                return False
            self._end_record(record, now, compactions_counted, reason)
            self._write(path, record)
            return True

    def _eligible(self, now):
        idle, ended = [], []
        for path in self._files():
            record = self._load(path)
            if record is None:
                continue
            if record.state is None:
                if record.ended_at is None:
                    raise StateError('ended pause record has no ended_at')
                ended.append((record.ended_at, path, record.generation))
            else:
                try:
                    mtime = os.stat(path).st_mtime
                except FileNotFoundError:
                    continue
                if now - mtime > IDLE_SECONDS:
                    idle.append((mtime, path, record.generation))
        ended.sort()
        excess = max(0, len(ended) - MAX_ENDED)
        deletions = [row for i, row in enumerate(ended)
                     if i < excess or now - row[0] > ENDED_SECONDS]
        return sorted(idle), deletions, len(ended)

    def retention(self, now: float) -> dict:
        idle, deletions, ended = self._eligible(now)
        return dict(idle_seconds=IDLE_SECONDS, ended_seconds=ENDED_SECONDS,
                    max_ended=MAX_ENDED, max_mutations=MAX_MAINTENANCE,
                    ended_roots=ended, cleanup_debt=len(idle) + len(deletions))

    def prune(self, now: float, *, compactions_counted: dict[str, bool]) -> dict:
        cleared = deleted = 0
        with self._flocked('.catalog'):
            idle, deletions, _ = self._eligible(now)
            candidates = [(False, row) for row in idle] + [(True, row) for row in deletions]
            for deleting, (when, path, generation) in candidates[:MAX_MAINTENANCE]:
                stem = os.path.basename(path)[:-5]
                with self._flocked(stem) as lock:
                    record = self._load(path)
                    if record is None or record.generation != generation:
                        continue
                    if deleting:
                        if record.state is not None or record.ended_at != when:
                            continue
                        self._unlink(path)
                        self._unlink(lock)
                        deleted += 1
                    elif record.state is not None and now - os.stat(path).st_mtime > IDLE_SECONDS:
                        self._end_record(record, now, compactions_counted.get(record.harness, False), 'idle')
                        self._write(path, record)
                        cleared += 1
            debt = self.retention(now)['cleanup_debt']
        return dict(affected=cleared + deleted, cleared=cleared, deleted=deleted, cleanup_debt=debt)
