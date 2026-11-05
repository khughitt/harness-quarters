"""Turn counters: active time with in-flight calls, root calls, tree spawns, compactions."""
from .events import USER_WAIT_TOOLS, Event
from .limits import Limits
from .record import Record, jdumps, jloads

IDLE_GAP_SECONDS = 600
WARN_FRACTION = (3, 4)
COUNTS = ('active', 'calls', 'spawns', 'compactions')
PAUSE_COUNTS = ('active', 'calls', 'spawns')


class TurnState(Record):
    __slots__ = _fields = ('started', 'limits', 'limits_sha', 'active', 'calls', 'spawns', 'compactions',
                           'last_t', 'in_flight', 'tools', 'spawn_keys', 'warned')
    _defaults = {'active': 0.0, 'calls': 0, 'spawns': 0, 'compactions': 0, 'last_t': None}
    _factories = {'in_flight': dict, 'tools': dict, 'spawn_keys': set, 'warned': set}

    def to_dict(self) -> dict:
        data = self._asdict()
        data['limits'] = self.limits._asdict()
        data['in_flight'] = dict(self.in_flight)
        data['tools'] = dict(self.tools)
        data['spawn_keys'] = sorted(self.spawn_keys)
        data['warned'] = sorted(self.warned)
        return data

    def to_json(self) -> str:
        return jdumps(self.to_dict())

    @classmethod
    def from_json(cls, text: str) -> 'TurnState':
        data = jloads(text)
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
    state.last_t = t if state.last_t is None else max(state.last_t, t)


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
    state.tools[ev.call_id] = ev.tool


def _close(state: TurnState, closing) -> None:
    """Drop the open calls `closing(call_id, agent)` selects."""
    state.in_flight = {c: a for c, a in state.in_flight.items() if not closing(c, a)}
    state.tools = {c: t for c, t in state.tools.items() if c in state.in_flight}


def apply(state: TurnState, ev: Event) -> None:
    """Every kind but tool_start and prompt."""
    if ev.kind in ('tool_start', 'prompt'):
        raise ValueError(f'{ev.kind} is not applied')
    _advance(state, ev.t)
    if ev.kind == 'tool_end':
        _close(state, lambda c, a: c == ev.call_id)
    elif ev.kind == 'agent_stop':
        _close(state, lambda c, a: a == ev.agent)
    elif ev.kind == 'agent_close':
        # ev.tool names the one tool whose open calls stay open (None: none do).
        _close(state, lambda c, a: a == ev.agent and (ev.tool is None or state.tools.get(c) != ev.tool))
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
    """The first enforced count strictly above its limit; compactions are advisory."""
    for name in PAUSE_COUNTS:
        if _count(state, name) > _limit(state, name):
            return name
    return None


def due_warnings(state: TurnState) -> list[str]:
    """Counts at or above three quarters of their limit that are not yet warned."""
    num, den = WARN_FRACTION
    return [n for n in COUNTS
            if n not in state.warned and _count(state, n) * den >= _limit(state, n) * num]
