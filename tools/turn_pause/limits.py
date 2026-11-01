"""Default turn limits and how a budget directive scales them."""
import hashlib
import math
import tomllib
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path

from .prompt import Budget

DEFAULTS_PATH = Path(__file__).with_name('limits.toml')


@dataclass(frozen=True)
class Limits:
    active_seconds: int
    calls: int
    spawns: int
    compactions: int


def load(path: Path = DEFAULTS_PATH) -> tuple[Limits, str]:
    """The limits in the file and the sha256 of its bytes."""
    raw = path.read_bytes()
    data = tomllib.loads(raw.decode())
    return Limits(data['active_seconds'], data['calls'], data['spawns'], data['compactions']), hashlib.sha256(raw).hexdigest()


def with_budget(defaults: Limits, budget: Budget) -> Limits:
    """Scale unnamed limits by budget.seconds over the default; named counts override."""
    factor = Fraction(budget.seconds, defaults.active_seconds)

    def scaled(value: int) -> int:
        return math.ceil(value * factor)

    return Limits(
        budget.seconds,
        budget.calls if budget.calls is not None else scaled(defaults.calls),
        budget.agents if budget.agents is not None else scaled(defaults.spawns),
        budget.compactions if budget.compactions is not None else scaled(defaults.compactions),
    )
