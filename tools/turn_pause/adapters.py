"""Native hook payloads to turn-pause events, per harness.

The capability facts the adapters read (Task 1) come from facts.json beside this
module: a checked-in snapshot of exactly the facts the hook reads, taken through
tools/harness-facts as a module (never by parsing its file). The hook loads it at no
cost on every call; a test fails when it no longer equals what harness-facts returns.
Regenerate it with `tools/turn-pause --write-facts-snapshot`. A fact that reads
`unknown` (null in the snapshot) selects the spec's fallback: no PostToolUse keeps a
call in flight until its agent's next hook event; a SubagentStop without an agent id
closes nothing (the next genuine prompt does); no compaction event counts no
compactions.
"""
from __future__ import annotations

import os

from .events import USER_WAIT_TOOLS, Event
from .record import Frozen, jloads

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
FACTS_TOOL = os.path.join(TOOLS, 'harness-facts')
SNAPSHOT = os.path.join(HERE, 'facts.json')
HARNESSES = ('claude-code', 'codex')
FACT_NAMES = {'posttooluse': 'hook-posttooluse', 'stop_carries_agent': 'hook-stop-carries-agent',
              'compact_events': 'hook-compact-event'}
SPAWN_TOOLS = {'claude-code': frozenset({'Agent', 'Task'}), 'codex': frozenset()}
EVENTS = frozenset({'UserPromptSubmit', 'PreToolUse', 'PostToolUse', 'PostToolUseFailure', 'Stop',
                    'SubagentStop', 'SubagentStart', 'PreCompact', 'PostCompact', 'SessionEnd'})


class Facts(Frozen):
    """Per harness: a probed value, or None for unknown."""
    __slots__ = _fields = ('posttooluse', 'stop_carries_agent', 'compact_events')


def _from_data(data) -> Facts:
    """Facts from the snapshot's JSON; anything malformed raises (the hook fails closed)."""
    if not isinstance(data, dict) or set(data) != set(FACT_NAMES):
        raise ValueError(f'{SNAPSHOT}: keys must be {sorted(FACT_NAMES)}')
    out = {}
    for key, table in data.items():
        if not isinstance(table, dict) or set(table) != set(HARNESSES):
            raise ValueError(f'{SNAPSHOT}: {key} must name {list(HARNESSES)}')
        for harness, value in table.items():
            ok = value is None or (isinstance(value, list) and all(isinstance(v, str) for v in value)
                                   if key == 'compact_events' else isinstance(value, bool))
            if not ok:
                raise ValueError(f'{SNAPSHOT}: {key}.{harness} is {value!r}')
        out[key] = ({h: None if v is None else frozenset(v) for h, v in table.items()}
                    if key == 'compact_events' else dict(table))
    return Facts(**out)


def load_facts() -> Facts:
    """The facts the hook reads, from the checked-in snapshot."""
    fd = os.open(SNAPSHOT, os.O_RDONLY | os.O_CLOEXEC)
    try:
        raw = os.read(fd, 65536)
    finally:
        os.close(fd)
    return _from_data(jloads(raw))


def snapshot_text() -> str:
    """The snapshot as tools/harness-facts reports the facts now."""
    import importlib.machinery
    import importlib.util
    import json
    loader = importlib.machinery.SourceFileLoader('harness_facts', FACTS_TOOL)
    spec = importlib.util.spec_from_loader('harness_facts', loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    data = {}
    for key, fact in FACT_NAMES.items():
        data[key] = {}
        for harness in HARNESSES:
            entry = module.lookup(fact, harness)
            value = entry['value'] if entry['status'] == 'probed' else None
            data[key][harness] = sorted(value) if isinstance(value, list) else value
    return json.dumps(data, indent=2, sort_keys=True) + '\n'


def write_snapshot(path: str = SNAPSHOT) -> None:
    with open(path, 'w') as f:
        f.write(snapshot_text())


def _text(payload: dict, key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f'hook payload has no {key} string')
    return value


def agent_of(payload: dict) -> str | None:
    """The payload's agent_id: a worker or subagent; None for the root."""
    agent = payload.get('agent_id')
    if agent is None:
        return None
    if not isinstance(agent, str) or not agent:
        raise ValueError(f'hook payload agent_id is not a non-empty string: {type(agent).__name__}')
    return agent


def is_summarizer(harness: str, event: str, payload: dict) -> bool:
    """Claude Code's compaction summarizer: a SubagentStop with an empty agent_type and no
    SubagentStart (fact hook-compact-event). It closes nothing and is no worker."""
    return harness == 'claude-code' and event == 'SubagentStop' and payload.get('agent_type') == ''


def user_wait_close(harness: str, now: float, agent: str | None, tool: str) -> list[Event]:
    """The close before a call that waits on the user: this agent's open calls are ones
    another hook refused (no PostToolUse), except a Codex nested exec_command (hook name
    Bash), which may stay open with none after a yield."""
    if tool not in USER_WAIT_TOOLS:
        return []
    return [Event(now, agent, 'agent_close', tool='Bash' if harness == 'codex' else None)]


def normalize(harness: str, event: str, payload: dict, now: float, facts: Facts) -> tuple[str, list[Event]]:
    """The root session id and the events of one hook call, in order. Workers and
    subagents report under their root's session_id with their own agent_id."""
    if harness not in HARNESSES:
        raise ValueError(f'unknown harness {harness!r}')
    if event not in EVENTS:
        raise ValueError(f'unknown hook event {event!r}')
    if not isinstance(payload, dict):
        raise ValueError('hook payload is not a JSON object')
    root = _text(payload, 'session_id')
    agent = agent_of(payload)
    if event == 'UserPromptSubmit':
        return root, [Event(now, agent, 'prompt')]
    if event == 'SessionEnd':
        return root, []
    if event in ('PreCompact', 'PostCompact'):
        names = facts.compact_events.get(harness) or frozenset()
        counted = 'PostCompact' if 'PostCompact' in names else 'PreCompact' if 'PreCompact' in names else None
        if counted is None:
            return root, [Event(now, agent, 'tick')]
        return root, [Event(now, agent, 'compact')] if event == counted else []
    if is_summarizer(harness, event, payload):
        return root, []
    # Without a PostToolUse, a call stays in flight until its agent's next hook event.
    close = [] if facts.posttooluse.get(harness) is True else [Event(now, agent, 'agent_stop')]
    if event == 'PreToolUse':
        call, tool = _text(payload, 'tool_use_id'), _text(payload, 'tool_name')
        events = close + user_wait_close(harness, now, agent, tool)
        events.append(Event(now, agent, 'tool_start', call_id=call, tool=tool))
        if tool in SPAWN_TOOLS[harness]:
            events.append(Event(now, agent, 'spawn', key=call))
        return root, events
    if event in ('PostToolUse', 'PostToolUseFailure'):
        return root, close + [Event(now, agent, 'tool_end', call_id=_text(payload, 'tool_use_id'))]
    if event == 'Stop':
        return root, [Event(now, agent, 'agent_stop')]
    if event == 'SubagentStop':
        if agent is not None and facts.stop_carries_agent.get(harness) is True:
            return root, [Event(now, agent, 'agent_stop')]
        return root, [Event(now, None, 'tick')]
    # SubagentStart: Codex counts its spawns here; Claude Code counted the Agent call.
    if agent is None:
        raise ValueError('SubagentStart without an agent_id')
    if harness == 'codex':
        return root, [Event(now, agent, 'spawn', key=agent)]
    return root, [Event(now, agent, 'tick')]
