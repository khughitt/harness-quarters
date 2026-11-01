import pytest

from turn_pause import counters
from turn_pause.counters import TurnState
from turn_pause.events import Event
from turn_pause.limits import Limits

LIMITS = Limits(active_seconds=4 * 3600, calls=500, spawns=30, compactions=2)


def ev(t, kind, agent=None, call=None, tool=None, key=None):
    return Event(t, agent, kind, call_id=call, tool=tool, key=key)


def new():
    return TurnState(started=0.0, limits=LIMITS, limits_sha='x')


def call(state, t, cid, agent=None, tool='Bash'):
    e = ev(t, 'tool_start', agent, cid, tool)
    counters.attempt(state, e)
    counters.started(state, e)


def end(state, t, cid, agent=None):
    counters.apply(state, ev(t, 'tool_end', agent, cid))


def test_eight_half_hour_calls_count_four_hours():
    s = new()
    t = 1000.0
    for i in range(8):
        call(s, t, f'c{i}')
        end(s, t + 1800, f'c{i}')
        t += 1805
    assert s.active == pytest.approx(8 * 1800 + 7 * 5)
    call(s, t, 'last')
    counters.apply(s, ev(t + 1, 'tick'))
    assert counters.crossed(s) == 'active'


def test_long_wait_on_silent_child_counts():
    s = new()
    call(s, 0, 'w', tool='wait_agent')
    before = s.active
    end(s, 1800, 'w')
    assert s.active - before == 1800


def test_idle_gap_over_ten_minutes_with_nothing_in_flight_counts_nothing():
    s = new()
    counters.apply(s, ev(0, 'tick'))
    counters.apply(s, ev(601, 'tick'))
    assert s.active == 0
    counters.apply(s, ev(601 + 599, 'tick'))
    assert s.active == 599


def test_user_wait_tool_never_in_flight():
    s = new()
    call(s, 0, 'q', tool='AskUserQuestion')
    assert s.in_flight == {}
    end(s, 8 * 3600, 'q')
    assert s.active == 0


def test_agent_stop_closes_only_that_agents_calls():
    s = new()
    call(s, 0, 'r')
    call(s, 1, 'k', agent='kid')
    counters.apply(s, ev(2, 'agent_stop'))
    assert s.in_flight == {'k': 'kid'}
    before = s.active
    counters.apply(s, ev(2 + 3600, 'tick', agent='kid'))
    assert s.active - before == 3600


def test_children_keep_tree_active_after_root_stop():
    s = new()
    call(s, 0, 'k', agent='kid')
    counters.apply(s, ev(10, 'agent_stop'))
    counters.apply(s, ev(10 + 7200, 'tick', agent='kid'))
    assert s.active == 7210


def test_counts_root_calls_tree_spawns_root_compactions():
    s = new()
    counters.attempt(s, ev(0, 'tool_start', 'kid', 'k', 'Bash'))
    assert s.calls == 0
    counters.attempt(s, ev(1, 'tool_start', None, 'r', 'Bash'))
    assert s.calls == 1
    counters.apply(s, ev(2, 'spawn', 'kid', key='w1'))
    assert s.spawns == 1
    counters.apply(s, ev(3, 'compact', 'kid'))
    assert s.compactions == 0
    counters.apply(s, ev(4, 'compact'))
    assert s.compactions == 1


def test_spawns_count_once_per_key():
    s = new()
    for i in range(1, 32):
        counters.apply(s, ev(i, 'spawn', key=f'w{i}'))
    assert s.spawns == 31
    assert counters.crossed(s) == 'spawns'
    counters.apply(s, ev(40, 'spawn', key='w7'))
    assert s.spawns == 31


def test_codex_nested_calls_each_count():
    s = new()
    for i, tool in enumerate(['Bash', 'Bash', 'apply_patch']):
        counters.attempt(s, ev(i, 'tool_start', None, f'n{i}', tool))
    assert s.calls == 3
    counters.apply(s, ev(10, 'tick'))
    assert s.calls == 3


def test_codex_yielded_call_stays_in_flight_until_agent_stop():
    s = new()
    call(s, 0, 'y')
    counters.apply(s, ev(7200, 'tick'))
    assert s.active == 7200
    counters.apply(s, ev(7201, 'agent_stop'))
    assert s.in_flight == {}
    counters.apply(s, ev(7201 + 7200, 'tick'))
    assert s.active == 7201


def test_tool_end_for_closed_call_is_ignored():
    s = new()
    call(s, 0, 'y')
    counters.apply(s, ev(5, 'agent_stop'))
    before = s.active
    end(s, 5 + 7200, 'y')
    assert s.in_flight == {}
    assert s.active == before


def test_refused_call_then_long_idle_counts_nothing():
    s = new()
    counters.attempt(s, ev(0, 'tool_start', None, 'x', 'Bash'))
    counters.apply(s, ev(3 * 3600, 'tick'))
    assert s.active == 0
    assert s.in_flight == {}


def test_crossing_is_strictly_above():
    s = new()
    for i in range(500):
        counters.attempt(s, ev(i, 'tool_start', None, f'c{i}', 'Bash'))
    assert counters.crossed(s) is None
    counters.attempt(s, ev(500, 'tool_start', None, 'c500', 'Bash'))
    assert counters.crossed(s) == 'calls'
    s2 = new()
    for i in range(3):
        counters.apply(s2, ev(i, 'compact'))
    assert counters.crossed(s2) == 'compactions'


def test_warning_once_per_limit():
    s = new()
    for i in range(375):
        counters.attempt(s, ev(i, 'tool_start', None, f'c{i}', 'Bash'))
    assert counters.due_warnings(s) == ['calls']
    s.warned.add('calls')
    assert counters.due_warnings(s) == []


def test_state_json_round_trip():
    s = new()
    call(s, 0, 'open', agent='kid')
    counters.apply(s, ev(1, 'spawn', key='w1'))
    s.warned.add('calls')
    back = TurnState.from_json(s.to_json())
    assert back == s
    assert back.in_flight == {'open': 'kid'} and back.spawn_keys == {'w1'}
    assert back.warned == {'calls'} and back.limits == LIMITS
