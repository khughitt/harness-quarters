"""Locked per-root pause state: one JSON file per root session, updated under flock."""
import contextlib
import fcntl
import json
import os
import tempfile
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from pathlib import Path

from .counters import TurnState

IDLE_SECONDS = 7 * 86400


class StateError(Exception):
    """A state file is unreadable, unparsable or unwritable; the hook refuses the call."""


@dataclass
class Wakeup:
    text: str
    not_before: float
    not_after: float


@dataclass
class RootState:
    harness: str
    root: str
    turn: TurnState | None
    paused: str | None = None
    grace_used: dict[str, int] = field(default_factory=dict)
    workers: set[str] = field(default_factory=set)
    worker_names: set[str] = field(default_factory=set)
    cron_jobs: dict[str, str] = field(default_factory=dict)
    wakeups: list[Wakeup] = field(default_factory=list)
    harness_pid: int | None = None
    cwd: str | None = None
    notified: bool = False
    notify_error: str | None = None
    budget_note: str | None = None


def state_dir(env: Mapping[str, str] = os.environ) -> Path:
    base = env.get('XDG_STATE_HOME')
    if base:
        return Path(base) / 'hq' / 'pause'
    return Path(env['HOME']) / '.local' / 'state' / 'hq' / 'pause'


def _check(value, kind, what):
    if not isinstance(value, kind) or (kind is int and isinstance(value, bool)):
        raise TypeError(f'{what} must be {kind.__name__}, not {type(value).__name__}')
    return value


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
        text_, before, after = w
        wakeups.append(Wakeup(_check(text_, str, 'wakeup text'),
                              float(_check(before, (int, float), 'wakeup not_before')),
                              float(_check(after, (int, float), 'wakeup not_after'))))
    return RootState(
        harness=_check(d['harness'], str, 'harness'),
        root=_check(d['root'], str, 'root'),
        turn=None if turn is None else TurnState.from_json(json.dumps(_check(turn, dict, 'turn'))),
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
    def __init__(self, dir: Path):
        self.dir = Path(dir)

    def _stem(self, harness: str, root: str) -> str:
        for part in (harness, root):
            if not part or '/' in part or part in ('.', '..') or '\0' in part:
                raise StateError(f'{self.dir}: invalid state name {harness!r}/{root!r}')
        return f'{harness}-{root}'

    def _load(self, path: Path) -> RootState | None:
        try:
            text = path.read_text()
        except FileNotFoundError:
            return None
        except OSError as e:
            raise StateError(f'cannot read {path}: {e}') from e
        try:
            return _from_json(text)
        except (ValueError, TypeError, KeyError) as e:
            raise StateError(f'cannot parse {path}: {type(e).__name__}: {e}') from e

    def _write(self, path: Path, st: RootState) -> None:
        tmp = None
        try:
            fd, tmp = tempfile.mkstemp(dir=self.dir, prefix=path.name + '.', suffix='.tmp')
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
    def locked(self, harness: str, root: str) -> Iterator[RootState]:
        stem = self._stem(harness, root)
        path = self.dir / f'{stem}.json'
        lock = self.dir / f'{stem}.lock'
        try:
            fd = os.open(lock, os.O_CREAT | os.O_RDWR, 0o600)
        except OSError as e:
            raise StateError(f'cannot open lock {lock}: {e}') from e
        try:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX)
            except OSError as e:
                raise StateError(f'cannot lock {lock}: {e}') from e
            st = self._load(path) or RootState(harness, root, None)
            yield st
            self._write(path, st)
        finally:
            os.close(fd)

    def read(self, harness: str, root: str) -> RootState | None:
        return self._load(self.dir / f'{self._stem(harness, root)}.json')

    def _files(self) -> list[Path]:
        try:
            return sorted(self.dir.glob('*.json'))
        except OSError as e:
            raise StateError(f'cannot list {self.dir}: {e}') from e

    def latest_for_cwd(self, cwd: str) -> tuple[str, str] | None:
        best = None
        for path in self._files():
            st = self._load(path)
            if st is None or st.cwd != cwd:
                continue
            mtime = path.stat().st_mtime
            if best is None or mtime > best[0]:
                best = (mtime, st.harness, st.root)
        return None if best is None else (best[1], best[2])

    def root_for_agent(self, harness: str, agent_id: str) -> str | None:
        for path in self._files():
            st = self._load(path)
            if st is not None and st.harness == harness and agent_id in st.workers:
                return st.root
        return None

    def remove(self, harness: str, root: str) -> None:
        stem = self._stem(harness, root)
        for suffix in ('.json', '.lock'):
            try:
                (self.dir / f'{stem}{suffix}').unlink()
            except FileNotFoundError:
                pass
            except OSError as e:
                raise StateError(f'cannot remove {self.dir / (stem + suffix)}: {e}') from e

    def prune(self, now: float, max_idle: float = IDLE_SECONDS) -> list[str]:
        """Remove states idle longer than max_idle (by file mtime); return their stems."""
        removed = []
        for path in self._files():
            try:
                idle = now - path.stat().st_mtime
            except OSError as e:
                raise StateError(f'cannot stat {path}: {e}') from e
            if idle > max_idle:
                for p in (path, path.with_suffix('.lock')):
                    try:
                        p.unlink()
                    except FileNotFoundError:
                        pass
                    except OSError as e:
                        raise StateError(f'cannot remove {p}: {e}') from e
                removed.append(path.stem)
        return removed
