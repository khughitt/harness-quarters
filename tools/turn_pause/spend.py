"""Reader for obs's published spend-signals.json (schema 1), episode rules, and host latch.

Imported on the hook's hot path: keeps top-level imports strictly to fcntl, os, and .record
(loading state.write_atomic lazily only when writing .spend-host.json), stats the signal file
once per call, and parses via record.jloads_strict only when (st_mtime_ns, st_size, st_ino)
changes.
"""
from __future__ import annotations

import fcntl
import os

from .record import Record, jencode_compact, jloads_strict

__all__ = (
    'SIGNAL_NAME',
    'PROTECTED_NAMES',
    'HOST_FILE',
    'HOST_LOCK',
    'RETRY_SECONDS',
    'obs_state_dir',
    'protected_paths',
    'Entry',
    'Signal',
    'SpendRecord',
    'HostLatch',
    'read',
    'state_of',
    'fresh_entry',
    'reconcile',
    'is_pending',
    'is_due',
    'deliver',
    'acknowledge',
    'inject',
    'read_latch',
    'observe',
    'record_alert',
    'entry_to_dict',
    'entry_from_dict',
    'signal_to_dict',
    'signal_from_dict',
    'spend_record_to_dict',
    'spend_record_from_dict',
    'host_latch_to_dict',
    'host_latch_from_dict',
)

SIGNAL_NAME = 'spend-signals.json'
PROTECTED_NAMES = (
    'spend-signals.json',
    'spend-baseline.json',
    'spend-state.json',
    'spend.lock',
)
HOST_FILE = '.spend-host.json'
HOST_LOCK = '.spend-host.lock'
RETRY_SECONDS = 3600

_S_IFMT = 0o170000
_S_IFREG = 0o100000
_INF = float('inf')
_VALID_STATUSES = ('ok', 'partial')
_VALID_BASELINES = ('ok', 'insufficient', 'stale', 'missing')
_OUTAGE_STATES = ('stale', 'unreadable', 'vanished')
_OUTAGE_OUTCOMES = ('attempted', 'error')
_ALERT_TITLE = 'turn-pause: spend protection off'
_OFF_UNTIL = (
    'spend protection is off until the producer runs again '
    '(systemctl --user status obs-spend.timer, journalctl --user -u obs-spend)'
)


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


class SpendRecord(Record):
    __slots__ = _fields = (
        'episode',
        'seen_value',
        'delivered_value',
        'acked_value',
    )
    _defaults = {
        'delivered_value': None,
        'acked_value': None,
    }


class HostLatch(Record):
    __slots__ = _fields = (
        'seen_fresh',
        'outage',
    )
    _defaults = {
        'seen_fresh': False,
        'outage': None,
    }


_ENTRY_FIELDS = set(Entry._fields)
_SIGNAL_FIELDS = set(Signal._fields)
_SPEND_RECORD_FIELDS = set(SpendRecord._fields)
_HOST_LATCH_FIELDS = set(HostLatch._fields)
_OUTAGE_FIELDS = {'state', 'alerted_at', 'outcome', 'error'}


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


def _nonneg_num(value, name: str) -> int | float:
    if (type(value) is not int and type(value) is not float) or not (0 <= value < _INF):
        raise ValueError(f'invalid {name}: {value!r}')
    return value


def spend_record_to_dict(sr: SpendRecord) -> dict:
    return {
        'episode': sr.episode,
        'seen_value': sr.seen_value,
        'delivered_value': sr.delivered_value,
        'acked_value': sr.acked_value,
    }


def spend_record_from_dict(d: dict) -> SpendRecord:
    if not isinstance(d, dict):
        raise TypeError(f'spend record must be dict, not {type(d).__name__}')
    if set(d) != _SPEND_RECORD_FIELDS:
        raise ValueError('spend record fields differ')
    episode = d['episode']
    if type(episode) is not str or not episode:
        raise ValueError(f'invalid spend.episode: {episode!r}')
    seen_value = _nonneg_num(d['seen_value'], 'spend.seen_value')
    raw_delivered = d['delivered_value']
    delivered_value = None if raw_delivered is None else _nonneg_num(raw_delivered, 'spend.delivered_value')
    raw_acked = d['acked_value']
    acked_value = None if raw_acked is None else _nonneg_num(raw_acked, 'spend.acked_value')
    return SpendRecord(
        episode=episode,
        seen_value=seen_value,
        delivered_value=delivered_value,
        acked_value=acked_value,
    )


def reconcile(sr: SpendRecord | None, entry: Entry | None) -> SpendRecord | None:
    """Reconcile durable spend state against this root's fresh entry (if any)."""
    if entry is None:
        return sr
    if sr is None or sr.episode != entry.episode:
        return SpendRecord(
            episode=entry.episode,
            seen_value=entry.value,
            delivered_value=None,
            acked_value=None,
        )
    return SpendRecord(
        episode=sr.episode,
        seen_value=max(sr.seen_value, entry.value),
        delivered_value=sr.delivered_value,
        acked_value=sr.acked_value,
    )


def is_pending(sr: SpendRecord | None) -> bool:
    """True when delivered to the root and awaiting a genuine root human prompt."""
    return sr is not None and sr.delivered_value is not None and sr.acked_value is None


def is_due(sr: SpendRecord | None, entry: Entry | None) -> bool:
    """True when there is a fresh entry that has never been delivered or has doubled since ack."""
    if entry is None:
        return False
    if sr is None or sr.delivered_value is None:
        return True
    return sr.acked_value is not None and entry.value >= 2 * sr.acked_value


def deliver(sr: SpendRecord, value: int | float) -> SpendRecord:
    """Record root refusal delivery at value, resetting acked_value to None."""
    if type(sr) is not SpendRecord:
        raise TypeError(f'sr must be SpendRecord, not {type(sr).__name__}')
    checked = _nonneg_num(value, 'spend.delivered_value')
    return SpendRecord(
        episode=sr.episode,
        seen_value=max(sr.seen_value, checked),
        delivered_value=checked,
        acked_value=None,
    )


def acknowledge(sr: SpendRecord) -> SpendRecord:
    """Acknowledge a delivered spend episode at max(seen_value, delivered_value)."""
    if type(sr) is not SpendRecord:
        raise TypeError(f'sr must be SpendRecord, not {type(sr).__name__}')
    if sr.delivered_value is None:
        raise ValueError('cannot acknowledge an undelivered spend episode')
    return SpendRecord(
        episode=sr.episode,
        seen_value=sr.seen_value,
        delivered_value=sr.delivered_value,
        acked_value=max(sr.seen_value, sr.delivered_value),
    )


def inject(sr: SpendRecord, value: int | float) -> SpendRecord:
    """Record prompt injection at value, setting both delivered_value and acked_value."""
    if type(sr) is not SpendRecord:
        raise TypeError(f'sr must be SpendRecord, not {type(sr).__name__}')
    checked = _nonneg_num(value, 'spend.delivered_value')
    return SpendRecord(
        episode=sr.episode,
        seen_value=max(sr.seen_value, checked),
        delivered_value=checked,
        acked_value=checked,
    )


def host_latch_to_dict(latch: HostLatch) -> dict:
    if type(latch) is not HostLatch:
        raise TypeError(f'latch must be HostLatch, not {type(latch).__name__}')
    outage = None if latch.outage is None else {
        'state': latch.outage['state'],
        'alerted_at': latch.outage['alerted_at'],
        'outcome': latch.outage['outcome'],
        'error': latch.outage['error'],
    }
    return {
        'seen_fresh': latch.seen_fresh,
        'outage': outage,
    }


def host_latch_from_dict(d: dict) -> HostLatch:
    if not isinstance(d, dict):
        raise TypeError(f'host latch must be dict, not {type(d).__name__}')
    if set(d) != _HOST_LATCH_FIELDS:
        raise ValueError('host latch fields differ')
    seen_fresh = d['seen_fresh']
    if type(seen_fresh) is not bool:
        raise TypeError(f'host latch seen_fresh must be bool, not {type(seen_fresh).__name__}')
    raw_outage = d['outage']
    if raw_outage is None:
        return HostLatch(seen_fresh=seen_fresh, outage=None)
    if not isinstance(raw_outage, dict):
        raise TypeError(f'host latch outage must be dict or None, not {type(raw_outage).__name__}')
    if set(raw_outage) != _OUTAGE_FIELDS:
        raise ValueError('host latch outage fields differ')
    st = raw_outage['state']
    if type(st) is not str or st not in _OUTAGE_STATES:
        raise ValueError(f'invalid host latch outage.state: {st!r}')
    alerted_at = float(_nonneg_num(raw_outage['alerted_at'], 'outage.alerted_at'))
    outcome = raw_outage['outcome']
    if type(outcome) is not str or outcome not in _OUTAGE_OUTCOMES:
        raise ValueError(f'invalid host latch outage.outcome: {outcome!r}')
    err = raw_outage['error']
    if outcome == 'attempted':
        if err is not None:
            raise ValueError(f'attempted outage must have error=None, got {err!r}')
    elif type(err) is not str:
        raise TypeError(f'error outage must have str error, not {type(err).__name__}')
    return HostLatch(
        seen_fresh=seen_fresh,
        outage={
            'state': st,
            'alerted_at': alerted_at,
            'outcome': outcome,
            'error': err,
        },
    )


def read_latch(store_dir: str | os.PathLike[str]) -> HostLatch:
    """Read .spend-host.json without locking; missing file returns HostLatch(False, None)."""
    directory = os.fspath(store_dir) or '.'
    path = os.path.join(directory, HOST_FILE)
    flags = (
        os.O_RDONLY
        | getattr(os, 'O_CLOEXEC', 0)
        | getattr(os, 'O_NOFOLLOW', 0)
        | getattr(os, 'O_NONBLOCK', 0)
    )
    try:
        fd = os.open(path, flags)
    except FileNotFoundError:
        return HostLatch(False, None)
    try:
        fst = os.fstat(fd)
        if (fst.st_mode & _S_IFMT) != _S_IFREG:
            raise ValueError(f'not a regular host latch file: {path}')
        chunks = []
        while True:
            chunk = os.read(fd, 65536)
            if not chunk:
                break
            chunks.append(chunk)
    finally:
        os.close(fd)
    raw = chunks[0] if len(chunks) == 1 else b''.join(chunks)
    text = raw.decode('utf-8')
    return host_latch_from_dict(jloads_strict(text))


def _write_latch(directory: str, latch: HostLatch) -> None:
    from .state import write_atomic

    payload = jencode_compact(host_latch_to_dict(latch)).encode('utf-8')
    write_atomic(os.path.join(directory, HOST_FILE), payload, sync_dir=True)


def _open_host_lock(directory: str) -> int:
    lock_path = os.path.join(directory, HOST_LOCK)
    flags = os.O_CREAT | os.O_RDWR | getattr(os, 'O_CLOEXEC', 0)
    while True:
        try:
            fd = os.open(lock_path, flags, 0o600)
        except FileNotFoundError:
            os.makedirs(directory, mode=0o700, exist_ok=True)
            fd = os.open(lock_path, flags, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            try:
                current = os.stat(lock_path).st_ino
            except FileNotFoundError:
                current = None
            if current != os.fstat(fd).st_ino:
                os.close(fd)
                continue
            return fd
        except BaseException:
            os.close(fd)
            raise


def _alert_due(outage: dict | None, now: float) -> bool:
    if outage is None:
        return True
    return outage['outcome'] == 'error' and (now - outage['alerted_at']) >= RETRY_SECONDS


def _format_age(seconds: int) -> str:
    if seconds < 60:
        return f'{seconds}s'
    if seconds < 3600:
        minutes, secs = divmod(seconds, 60)
        return f'{minutes}m{secs:02d}s'
    hours, rem = divmod(seconds, 3600)
    return f'{hours}h{rem // 60:02d}m'


def _format_alert(st: str, sig: Signal, signal_path: str, now_ms: int) -> tuple[str, str]:
    if sig.generated_at is not None:
        age_part = f'age {_format_age(max(0, (now_ms - sig.generated_at) // 1000))}'
    else:
        age_part = 'age unknown'
    if st == 'stale':
        detail = age_part
    elif st == 'unreadable':
        err = sig.error or 'unreadable signal'
        detail = f'{age_part}; {err}'
    else:
        detail = f'{age_part}; missing after prior fresh signal'
    body = f'{signal_path} is {st} ({detail}): {_OFF_UNTIL}.'
    return _ALERT_TITLE, body


def observe(
    store_dir: str | os.PathLike[str],
    sig: Signal,
    signal_path: str | os.PathLike[str],
    now: float,
) -> tuple[str, float, str, str] | None:
    """Observe sig against the host latch; lock and write only when latch state changes."""
    if type(sig) is not Signal:
        raise TypeError(f'sig must be Signal, not {type(sig).__name__}')
    directory = os.fspath(store_dir) or '.'
    sig_path = os.fspath(signal_path)
    now_f = float(_nonneg_num(now, 'now'))
    now_ms = int(now_f * 1000)

    latch = read_latch(directory)
    st = state_of(sig, now_ms, latch.seen_fresh)
    if st == 'absent':
        return None
    if st == 'fresh':
        if latch.seen_fresh and latch.outage is None:
            return None
    elif not _alert_due(latch.outage, now_f):
        return None

    fd = _open_host_lock(directory)
    try:
        latch = read_latch(directory)
        st = state_of(sig, now_ms, latch.seen_fresh)
        if st == 'fresh':
            if not latch.seen_fresh or latch.outage is not None:
                _write_latch(directory, HostLatch(seen_fresh=True, outage=None))
            return None
        if st in _OUTAGE_STATES and _alert_due(latch.outage, now_f):
            outage = {
                'state': st,
                'alerted_at': now_f,
                'outcome': 'attempted',
                'error': None,
            }
            _write_latch(directory, HostLatch(seen_fresh=latch.seen_fresh, outage=outage))
            title, body = _format_alert(st, sig, sig_path, now_ms)
            return (st, now_f, title, body)
        return None
    finally:
        os.close(fd)


def record_alert(
    store_dir: str | os.PathLike[str],
    alerted_at: float,
    error: str,
) -> None:
    """Record a desktop alert failure if the active outage still matches alerted_at."""
    directory = os.fspath(store_dir) or '.'
    checked_at = float(_nonneg_num(alerted_at, 'alerted_at'))
    if type(error) is not str:
        raise TypeError(f'error must be str, not {type(error).__name__}')
    fd = _open_host_lock(directory)
    try:
        latch = read_latch(directory)
        if latch.outage is not None and latch.outage['alerted_at'] == checked_at:
            outage = {
                'state': latch.outage['state'],
                'alerted_at': latch.outage['alerted_at'],
                'outcome': 'error',
                'error': error,
            }
            _write_latch(directory, HostLatch(seen_fresh=latch.seen_fresh, outage=outage))
    finally:
        os.close(fd)
