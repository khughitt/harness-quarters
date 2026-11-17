"""Reader for obs's published spend-signals.json (schema 1).

Imported on the hook's hot path: keeps imports strictly to os and .record, stats the
signal file once per call, and parses via record.jloads_strict only when the file's
(st_mtime_ns, st_size, st_ino) identity changes.
"""
from __future__ import annotations

import os

from .record import Record, jloads_strict

__all__ = (
    'SIGNAL_NAME',
    'PROTECTED_NAMES',
    'obs_state_dir',
    'protected_paths',
    'Entry',
    'Signal',
    'read',
    'state_of',
    'fresh_entry',
    'entry_to_dict',
    'entry_from_dict',
    'signal_to_dict',
    'signal_from_dict',
)

SIGNAL_NAME = 'spend-signals.json'
PROTECTED_NAMES = (
    'spend-signals.json',
    'spend-baseline.json',
    'spend-state.json',
    'spend.lock',
)

_S_IFMT = 0o170000
_S_IFREG = 0o100000
_INF = float('inf')
_VALID_STATUSES = ('ok', 'partial')
_VALID_BASELINES = ('ok', 'insufficient', 'stale', 'missing')


class Entry(Record):
    __slots__ = _fields = (
        'episode',
        'value',
        'threshold',
        'ratio',
        'window_hours',
        'measured_at',
        'complete',
        'credits_drawn_24h',
    )


class Signal(Record):
    __slots__ = _fields = (
        'identity',
        'generated_at',
        'stale_after_ms',
        'status',
        'baseline',
        'entry',
        'error',
    )
    _defaults = {
        'identity': None,
        'generated_at': None,
        'stale_after_ms': None,
        'status': None,
        'baseline': None,
        'entry': None,
        'error': None,
    }


_ENTRY_FIELDS = set(Entry._fields)
_SIGNAL_FIELDS = set(Signal._fields)


def obs_state_dir(env: Mapping[str, str] = os.environ) -> str:
    """Resolve obs's state directory: $XDG_STATE_HOME/obs when set, else $HOME/.local/state/obs."""
    base = env.get('XDG_STATE_HOME')
    if base:
        if not isinstance(base, str) or not os.path.isabs(base):
            raise ValueError(f'XDG_STATE_HOME must be an absolute path: {base!r}')
        return os.path.join(base, 'obs')
    home = env.get('HOME')
    if not isinstance(home, str) or not home or not os.path.isabs(home):
        raise ValueError('HOME must be set to an absolute path')
    return os.path.join(home, '.local', 'state', 'obs')


def protected_paths(env: Mapping[str, str] = os.environ) -> list[str]:
    """The four obs spend files under obs_state_dir(env), or [] when unresolvable."""
    try:
        directory = obs_state_dir(env)
    except ValueError:
        return []
    return [os.path.join(directory, name) for name in PROTECTED_NAMES]


def _parse_entry_fields(item: dict) -> Entry:
    episode = item.get('episode')
    if type(episode) is not str or not episode:
        raise ValueError(f'invalid entry.episode: {episode!r}')
    value = item.get('value')
    if (type(value) is not int and type(value) is not float) or not (0 <= value < _INF):
        raise ValueError(f'invalid entry.value: {value!r}')
    threshold = item.get('threshold')
    if (type(threshold) is not int and type(threshold) is not float) or not (0 < threshold < _INF):
        raise ValueError(f'invalid entry.threshold: {threshold!r}')
    ratio = item.get('ratio')
    if (type(ratio) is not int and type(ratio) is not float) or not (0 <= ratio < _INF):
        raise ValueError(f'invalid entry.ratio: {ratio!r}')
    window_hours = item.get('window_hours')
    if type(window_hours) is not int or window_hours <= 0:
        raise ValueError(f'invalid entry.window_hours: {window_hours!r}')
    measured_at = item.get('measured_at')
    if type(measured_at) is not int:
        raise ValueError(f'invalid entry.measured_at: {measured_at!r}')
    complete = item.get('complete')
    if type(complete) is not bool:
        raise ValueError(f'invalid entry.complete: {complete!r}')
    if 'credits_drawn_24h' not in item:
        raise ValueError('missing entry.credits_drawn_24h')
    credits = item['credits_drawn_24h']
    if credits is not None and (
        (type(credits) is not int and type(credits) is not float) or not (-_INF < credits < _INF)
    ):
        raise ValueError(f'invalid entry.credits_drawn_24h: {credits!r}')
    return Entry(
        episode=episode,
        value=value,
        threshold=threshold,
        ratio=ratio,
        window_hours=window_hours,
        measured_at=measured_at,
        complete=complete,
        credits_drawn_24h=credits,
    )


def _parse_signal(data, harness: str, root: str, identity: tuple[int, int, int]) -> Signal:
    if not isinstance(data, dict):
        raise ValueError('signal payload must be a JSON object')
    schema = data.get('schema')
    if type(schema) is not int or schema != 1:
        raise ValueError(f'unsupported schema: {schema!r}')
    generated_at = data.get('generated_at')
    if type(generated_at) is not int:
        raise ValueError(f'invalid generated_at: {generated_at!r}')
    stale_after_ms = data.get('stale_after_ms')
    if type(stale_after_ms) is not int or stale_after_ms < 0:
        raise ValueError(f'invalid stale_after_ms: {stale_after_ms!r}')
    status = data.get('status')
    if type(status) is not str or status not in _VALID_STATUSES:
        raise ValueError(f'invalid status: {status!r}')

    baseline_obj = data.get('baseline')
    if not isinstance(baseline_obj, dict):
        raise ValueError('invalid baseline: expected object')
    harnesses_obj = baseline_obj.get('harnesses')
    if not isinstance(harnesses_obj, dict):
        raise ValueError('invalid baseline.harnesses: expected object')
    harness_info = harnesses_obj.get(harness)
    if not isinstance(harness_info, dict):
        raise ValueError(f'invalid baseline.harnesses.{harness}: expected object')
    baseline_state = harness_info.get('state')
    if type(baseline_state) is not str or baseline_state not in _VALID_BASELINES:
        raise ValueError(f'invalid baseline.harnesses.{harness}.state: {baseline_state!r}')

    trees = data.get('trees')
    if not isinstance(trees, list):
        raise ValueError('invalid trees: expected array')

    selected = None
    for item in trees:
        if not isinstance(item, dict):
            raise ValueError('invalid trees entry: expected object')
        item_harness = item.get('harness')
        item_root_session = item.get('root_session')
        item_root = item.get('root')
        item_resolved = item.get('root_resolved')
        if type(item_harness) is not str or not item_harness:
            raise ValueError(f'invalid trees entry harness: {item_harness!r}')
        if type(item_root_session) is not str or not item_root_session:
            raise ValueError(f'invalid trees entry root_session: {item_root_session!r}')
        if type(item_root) is not str:
            raise ValueError(f'invalid trees entry root: {item_root!r}')
        if type(item_resolved) is not bool:
            raise ValueError(f'invalid trees entry root_resolved: {item_resolved!r}')
        expected_root = f'{item_harness}:{item_root_session}'
        if item_root != expected_root:
            raise ValueError(f'trees entry root mismatch: {item_root!r} != {expected_root!r}')
        if item_harness == harness and item_root_session == root and item_resolved is True:
            if selected is not None:
                raise ValueError(f'duplicate resolved trees entry for {expected_root}')
            selected = _parse_entry_fields(item)

    return Signal(
        identity=identity,
        generated_at=generated_at,
        stale_after_ms=stale_after_ms,
        status=status,
        baseline=baseline_state,
        entry=selected,
        error=None,
    )


def read(env: Mapping[str, str], harness: str, root: str, cached: Signal | None) -> Signal:
    """Stat spend-signals.json once; return cached on identity match, else parse schema 1."""
    if type(harness) is not str or not harness:
        return Signal(error=f'invalid harness: {harness!r}')
    if type(root) is not str or not root:
        return Signal(error=f'invalid root: {root!r}')
    try:
        directory = obs_state_dir(env)
    except Exception as exc:
        return Signal(error=str(exc))
    path = os.path.join(directory, SIGNAL_NAME)
    try:
        st = os.stat(path)
    except FileNotFoundError:
        return Signal()
    except OSError as exc:
        return Signal(error=f'cannot stat {SIGNAL_NAME}: {exc}')
    if (st.st_mode & _S_IFMT) != _S_IFREG:
        return Signal(error=f'{SIGNAL_NAME} is not a regular file')
    identity = (st.st_mtime_ns, st.st_size, st.st_ino)
    if cached is not None and cached.identity == identity:
        return cached

    flags = os.O_RDONLY | getattr(os, 'O_CLOEXEC', 0) | getattr(os, 'O_NONBLOCK', 0)
    try:
        fd = os.open(path, flags)
    except FileNotFoundError:
        return Signal()
    except OSError as exc:
        return Signal(error=f'cannot open {SIGNAL_NAME}: {exc}')
    try:
        fst = os.fstat(fd)
        if (fst.st_mode & _S_IFMT) != _S_IFREG:
            return Signal(error=f'{SIGNAL_NAME} is not a regular file')
        identity = (fst.st_mtime_ns, fst.st_size, fst.st_ino)
        chunks = []
        while True:
            chunk = os.read(fd, 65536)
            if not chunk:
                break
            chunks.append(chunk)
    except OSError as exc:
        return Signal(error=f'cannot read {SIGNAL_NAME}: {exc}')
    finally:
        os.close(fd)

    raw = chunks[0] if len(chunks) == 1 else b''.join(chunks)
    try:
        text = raw.decode('utf-8')
    except UnicodeDecodeError as exc:
        return Signal(identity=identity, error=f'invalid UTF-8 in {SIGNAL_NAME}: {exc}')
    if not text.strip(' \t\n\r'):
        return Signal(identity=identity, error=f'empty {SIGNAL_NAME}')
    try:
        data = jloads_strict(text)
        return _parse_signal(data, harness, root, identity)
    except (ValueError, TypeError) as exc:
        return Signal(identity=identity, error=str(exc))


def state_of(sig: Signal, now_ms: int, seen_fresh: bool) -> str:
    """Classify sig into one of 'absent', 'vanished', 'unreadable', 'stale', 'fresh'."""
    if sig.error is not None:
        return 'unreadable'
    if sig.identity is None:
        return 'vanished' if seen_fresh else 'absent'
    if sig.generated_at is None or sig.stale_after_ms is None:
        return 'unreadable'
    if now_ms - sig.generated_at > sig.stale_after_ms:
        return 'stale'
    return 'fresh'


def fresh_entry(sig: Signal, now_ms: int) -> Entry | None:
    """Return sig.entry when both the signal file and the entry are fresh at now_ms."""
    if state_of(sig, now_ms, False) != 'fresh':
        return None
    entry = sig.entry
    if entry is None:
        return None
    if now_ms - entry.measured_at > sig.stale_after_ms:
        return None
    return entry


def entry_to_dict(entry: Entry) -> dict:
    return {
        'episode': entry.episode,
        'value': entry.value,
        'threshold': entry.threshold,
        'ratio': entry.ratio,
        'window_hours': entry.window_hours,
        'measured_at': entry.measured_at,
        'complete': entry.complete,
        'credits_drawn_24h': entry.credits_drawn_24h,
    }


def entry_from_dict(d: dict) -> Entry:
    if not isinstance(d, dict):
        raise TypeError(f'entry must be dict, not {type(d).__name__}')
    if set(d) != _ENTRY_FIELDS:
        raise ValueError('entry fields differ')
    return _parse_entry_fields(d)


def signal_to_dict(sig: Signal) -> dict:
    return {
        'identity': None if sig.identity is None else list(sig.identity),
        'generated_at': sig.generated_at,
        'stale_after_ms': sig.stale_after_ms,
        'status': sig.status,
        'baseline': sig.baseline,
        'entry': None if sig.entry is None else entry_to_dict(sig.entry),
        'error': sig.error,
    }


def signal_from_dict(d: dict) -> Signal:
    if not isinstance(d, dict):
        raise TypeError(f'signal must be dict, not {type(d).__name__}')
    if set(d) != _SIGNAL_FIELDS:
        raise ValueError('signal fields differ')
    raw_id = d['identity']
    if raw_id is None:
        identity = None
    else:
        if (
            not isinstance(raw_id, (list, tuple))
            or len(raw_id) != 3
            or type(raw_id[0]) is not int
            or type(raw_id[1]) is not int
            or type(raw_id[2]) is not int
        ):
            raise TypeError('signal.identity must be 3 ints or None')
        identity = (raw_id[0], raw_id[1], raw_id[2])

    generated_at = d['generated_at']
    if generated_at is not None and type(generated_at) is not int:
        raise TypeError('signal.generated_at must be int or None')

    stale_after_ms = d['stale_after_ms']
    if stale_after_ms is not None:
        if type(stale_after_ms) is not int:
            raise TypeError('signal.stale_after_ms must be int or None')
        if stale_after_ms < 0:
            raise ValueError('signal.stale_after_ms must be nonnegative')

    status = d['status']
    if status is not None:
        if type(status) is not str:
            raise TypeError('signal.status must be str or None')
        if status not in _VALID_STATUSES:
            raise ValueError(f'invalid signal.status: {status!r}')

    baseline = d['baseline']
    if baseline is not None:
        if type(baseline) is not str:
            raise TypeError('signal.baseline must be str or None')
        if baseline not in _VALID_BASELINES:
            raise ValueError(f'invalid signal.baseline: {baseline!r}')

    raw_entry = d['entry']
    entry = None if raw_entry is None else entry_from_dict(raw_entry)

    error = d['error']
    if error is not None and type(error) is not str:
        raise TypeError('signal.error must be str or None')

    if error is None and identity is not None:
        if generated_at is None or stale_after_ms is None or status is None or baseline is None:
            raise ValueError('parsed signal missing required metadata')
    elif error is None and identity is None:
        if (
            generated_at is not None
            or stale_after_ms is not None
            or status is not None
            or baseline is not None
            or entry is not None
        ):
            raise ValueError('absent signal cannot carry parsed fields')

    return Signal(
        identity=identity,
        generated_at=generated_at,
        stale_after_ms=stale_after_ms,
        status=status,
        baseline=baseline,
        entry=entry,
        error=error,
    )
