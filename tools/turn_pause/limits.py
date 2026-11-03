"""Default turn limits and how a budget directive scales them.

The hook imports this module on every call, so it keeps to cheap imports: tomllib and
fractions load only where they are needed, and the sha256 comes from the C module _sha2
rather than hashlib. DEFAULTS_PATH (a pathlib.Path) is built on first access; the hook
uses DEFAULTS_FILE, a str.
"""
from __future__ import annotations

import math
import os

from .record import Frozen

try:
    from _sha2 import sha256
except ImportError:  # an interpreter built without _sha2: same digest, slower import
    from hashlib import sha256

DEFAULTS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'limits.toml')


def __getattr__(name):
    if name == 'DEFAULTS_PATH':
        from pathlib import Path
        return Path(DEFAULTS_FILE)
    raise AttributeError(f'module {__name__!r} has no attribute {name!r}')


class Limits(Frozen):
    __slots__ = _fields = ('active_seconds', 'calls', 'spawns', 'compactions')


def duration(seconds: float) -> str:
    """Active time with its units named (16h00m), never a bare h:mm an agent could read as minutes."""
    minutes = int(seconds) // 60
    return f'{minutes // 60}h{minutes % 60:02d}m'


def sha256_hex(data: bytes) -> str:
    return sha256(data).hexdigest()


def file_sha256(path) -> str:
    with open(path, 'rb') as f:
        return sha256_hex(f.read())


def load(path=DEFAULTS_FILE) -> tuple[Limits, str]:
    """The limits in the file and the sha256 of its bytes."""
    import tomllib
    with open(path, 'rb') as f:
        raw = f.read()
    try:
        data = tomllib.loads(raw.decode())
    except (tomllib.TOMLDecodeError, UnicodeDecodeError) as error:
        raise ValueError(f'{path}: not valid TOML: {error}') from error
    missing = [name for name in Limits._fields if name not in data]
    if missing:
        raise ValueError(f'{path}: missing {", ".join(missing)}')
    values = Limits(*(data[name] for name in Limits._fields))
    for name in Limits._fields:
        value = getattr(values, name)
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ValueError(f'{path}: {name} must be a positive integer, not {value!r}')
    return values, sha256_hex(raw)


def with_budget(defaults: Limits, budget) -> Limits:
    """Scale unnamed limits by budget.seconds over the default; named counts override."""
    from fractions import Fraction
    factor = Fraction(budget.seconds, defaults.active_seconds)

    def scaled(value: int) -> int:
        return math.ceil(value * factor)

    return Limits(
        budget.seconds,
        budget.calls if budget.calls is not None else scaled(defaults.calls),
        budget.agents if budget.agents is not None else scaled(defaults.spawns),
        budget.compactions if budget.compactions is not None else scaled(defaults.compactions),
    )
