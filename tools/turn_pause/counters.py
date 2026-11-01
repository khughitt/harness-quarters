"""Turn counters: active time with in-flight calls, root calls, tree spawns, compactions."""
import json
from dataclasses import asdict, dataclass, field

from .events import USER_WAIT_TOOLS, Event
from .limits import Limits

IDLE_GAP_SECONDS = 600
WARN_FRACTION = (3, 4)
COUNTS = ('active', 'calls', 'spawns', 'compactions')


@dataclass
class TurnState:
    started: float
    limits: Limits
    limits_sha: str
    active: float = 0.0
    calls: int = 0
    spawns: int = 0
    compactions: int = 0
    last_t: float | None = None
    in_flight: dict[str, str | None] = field(default_factory=dict)
    spawn_keys: set[str] = field(default_factory=set)
    warned: set[str] = field(default_factory=set)

    def to_json(self) -> str:
        data = asdict(self)
        data['spawn_keys'] = sorted(self.spawn_keys)
        data['warned'] = sorted(self.warned)
        return json.dumps(data)

    @classmethod
    def from_json(cls, text: str) -> 'TurnState':
        data = json.loads(text)
        data['limits'] = Limits(**data['limits'])
        data['spawn_keys'] = set(data['spawn_keys'])
        data['warned'] = set(data['warned'])
        return cls(**data)


def _advance(state: TurnState, t: float) -> None:
    """Add the gap since last_t: in full while a call is in flight, else when under ten minutes."""
    if state.last_t is not None:
        gap = t - state.last_t
        if state.in_flight or gap < IDLE_GAP_SECONDS:
            state.active += max(gap, 0.0)
    state.last_t = t


def attempt(state: TurnState, ev: Event) -> None:
    """A tool_start the hook saw; a root call counts. Never in flight: a refused call gets no end."""
    _advance(state, ev.t)
    if ev.agent is None:
        state.calls += 1


def started(state: TurnState, ev: Event) -> None:
    """A tool_start the hook allowed: in flight unless it waits on the user."""
    _advance(state, ev.t)
    if ev.tool in USER_WAIT_TOOLS:
        return
    if ev.call_id is None:
        raise ValueError('an allowed tool_start needs a call_id')
    state.in_flight[ev.call_id] = ev.agent


def apply(state: TurnState, ev: Event) -> None:
    """Every kind but tool_start and prompt."""
    if ev.kind in ('tool_start', 'prompt'):
        raise ValueError(f'{ev.kind} is not applied')
    _advance(state, ev.t)
    if ev.kind == 'tool_end':
        state.in_flight.pop(ev.call_id, None)
    elif ev.kind == 'agent_stop':
        state.in_flight = {c: a for c, a in state.in_flight.items() if a != ev.agent}
    elif ev.kind == 'compact':
        if ev.agent is None:
            state.compactions += 1
    elif ev.kind == 'spawn':
        if ev.key is None:
            raise ValueError('a spawn needs a key')
        if ev.key not in state.spawn_keys:
            state.spawn_keys.add(ev.key)
            state.spawns += 1
    elif ev.kind != 'tick':
        raise ValueError(f'unknown event kind {ev.kind}')


def _count(state: TurnState, name: str) -> float:
    return getattr(state, name)


def _limit(state: TurnState, name: str) -> int:
    return state.limits.active_seconds if name == 'active' else getattr(state.limits, name)


def crossed(state: TurnState) -> str | None:
    """The first count strictly above its limit."""
    for name in COUNTS:
        if _count(state, name) > _limit(state, name):
            return name
    return None


def due_warnings(state: TurnState) -> list[str]:
    """Counts at or above three quarters of their limit that are not yet warned."""
    num, den = WARN_FRACTION
    return [n for n in COUNTS
            if n not in state.warned and _count(state, n) * den >= _limit(state, n) * num]
