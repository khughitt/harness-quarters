"""The one path that applies hook events to a turn's counters, and the turn boundary.

The hook feeds it with the real decision; the replay (Task 8) with a recording one. No
other code calls counters.attempt, started or apply. Spec:
docs/specs/2026-11-01-turn-pause-design.md, "The unit" and "Counters".
"""
from __future__ import annotations

from . import counters
from .counters import TurnState
from .record import Frozen

# A ScheduleWakeup prompt is pending from a minute before its fire time to ten after.
WAKE_BEFORE = 60
WAKE_AFTER = 600

class Decision(Frozen):
    """allow: the call proceeds; output: the hook's JSON; paused: the limit this decision
    newly paused the turn on, or None."""
    __slots__ = _fields = ('allow', 'output', 'paused')


def feed(rs: RootState, events: list[Event], decide: Callable[[RootState, Event], Decision]) -> Decision | None:
    """Apply events in order. A tool_start is attempted, decided, and only if allowed
    started, with the spawn events that follow it; a refused call is never in flight and
    spawns nothing. Every other event is applied. Returns the tool_start's decision."""
    if rs.turn is None:
        raise ValueError('feed needs a turn')
    decision = None
    gate = True
    for ev in events:
        if ev.kind == 'tool_start':
            counters.attempt(rs.turn, ev)
            decision = decide(rs, ev)
            gate = decision.allow
            if gate:
                counters.started(rs.turn, ev)
        elif ev.kind == 'prompt':
            raise ValueError('a prompt is classified by prompt_kind, not fed')
        elif ev.kind == 'spawn' and not gate:
            continue
        else:
            counters.apply(rs.turn, ev)
    return decision


def start_turn(rs: RootState, t: float, limits: Limits, limits_sha: str, budget_note: str | None = None) -> None:
    """A new turn: fresh counters timed from t (so the gap to the first call counts), no
    pause, no grace spent, no notification sent."""
    rs.turn = TurnState(started=t, limits=limits, limits_sha=limits_sha, last_t=t)
    rs.paused = None
    rs.grace_used = {}
    rs.notified = False
    rs.notify_error = None
    rs.budget_note = budget_note


def prompt_kind(rs: RootState, harness: str, text: str, now: float, agent: str | None) -> str:
    """'turn', 'wake' or 'injected'. Only a root prompt can be a wake or a turn: 'wake'
    when the text equals a pending scheduled prompt (a ScheduleWakeup inside its window,
    consumed here, or any pending cron job's prompt); 'injected' for a worker's prompt or
    one that is not a genuine human prompt; else 'turn'. Expired wakeups are dropped."""
    rs.wakeups = [w for w in rs.wakeups if w.not_after >= now]
    if agent is not None:
        return 'injected'
    said = text.strip()
    for i, w in enumerate(rs.wakeups):
        if w.text.strip() == said and w.not_before <= now <= w.not_after:
            del rs.wakeups[i]
            return 'wake'
    if any(p.strip() == said for p in rs.cron_jobs.values()):
        return 'wake'
    from .prompt import is_genuine
    if not is_genuine(text, harness):
        return 'injected'
    return 'turn'
