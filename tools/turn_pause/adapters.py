"""Native hook payloads to turn-pause events, per harness.

The capability facts the adapters read (Task 1) come from tools/harness-facts as a
module, never by parsing its file. A fact that reads `unknown` selects the spec's
fallback: no PostToolUse keeps a call in flight until its agent's next hook event; a
SubagentStop without an agent id closes nothing (the next genuine prompt does); no
compaction event counts no compactions. Validating the fact file costs about 13 ms per
lookup, too much for a hook that runs on every call, so the values are memoised in the
state directory under the sha256 of the fact file and of the tool that reads it.
Imports needed only on a cache miss are local to it: the hook's latency is mostly imports.
"""
import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path

from .events import Event

TOOLS = Path(__file__).resolve().parent.parent
FACTS_TOOL = TOOLS / 'harness-facts'
FACTS_FILE = TOOLS.parent / 'facts' / 'capabilities.toml'
CACHE_NAME = 'facts.cache'
HARNESSES = ('claude-code', 'codex')
SPAWN_TOOLS = {'claude-code': frozenset({'Agent', 'Task'}), 'codex': frozenset()}
EVENTS = frozenset({'UserPromptSubmit', 'PreToolUse', 'PostToolUse', 'PostToolUseFailure', 'Stop',
                    'SubagentStop', 'SubagentStart', 'PreCompact', 'PostCompact', 'SessionEnd'})


@dataclass(frozen=True)
class Facts:
    """Per harness: a probed value, or None for unknown."""
    posttooluse: dict[str, bool | None]
    stop_carries_agent: dict[str, bool | None]
    compact_events: dict[str, frozenset[str] | None]


def _facts_module():
    import importlib.machinery
    import importlib.util
    loader = importlib.machinery.SourceFileLoader('harness_facts', str(FACTS_TOOL))
    spec = importlib.util.spec_from_loader('harness_facts', loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def _looked_up() -> Facts:
    module = _facts_module()

    def value(name, harness):
        entry = module.lookup(name, harness)
        return entry['value'] if entry['status'] == 'probed' else None

    compact = {}
    for h in HARNESSES:
        names = value('hook-compact-event', h)
        compact[h] = None if names is None else frozenset(names)
    return Facts(posttooluse={h: value('hook-posttooluse', h) for h in HARNESSES},
                 stop_carries_agent={h: value('hook-stop-carries-agent', h) for h in HARNESSES},
                 compact_events=compact)


def _key() -> str:
    digest = hashlib.sha256()
    for path in (FACTS_TOOL, FACTS_FILE):
        digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def _to_cache(key: str, facts: Facts) -> str:
    return json.dumps({'key': key, 'posttooluse': facts.posttooluse,
                       'stop_carries_agent': facts.stop_carries_agent,
                       'compact_events': {h: None if v is None else sorted(v) for h, v in facts.compact_events.items()}})


def _from_cache(text: str, key: str) -> Facts | None:
    """The cached facts when the cache is for this key and well formed; else None (a miss)."""
    try:
        data = json.loads(text)
        if data['key'] != key:
            return None
        posttooluse, stops, compact = data['posttooluse'], data['stop_carries_agent'], data['compact_events']
        for table, ok in ((posttooluse, lambda v: v is None or isinstance(v, bool)),
                          (stops, lambda v: v is None or isinstance(v, bool)),
                          (compact, lambda v: v is None or (isinstance(v, list) and all(isinstance(s, str) for s in v)))):
            if set(table) != set(HARNESSES) or not all(ok(v) for v in table.values()):
                return None
        return Facts(posttooluse=dict(posttooluse), stop_carries_agent=dict(stops),
                     compact_events={h: None if v is None else frozenset(v) for h, v in compact.items()})
    except (ValueError, KeyError, TypeError):
        return None


def load_facts(cache_dir: Path | None) -> Facts:
    """The facts, through the cache in cache_dir when one is given."""
    if cache_dir is None:
        return _looked_up()
    key = _key()
    cache = Path(cache_dir) / CACHE_NAME
    try:
        cached = _from_cache(cache.read_text(), key)
    except FileNotFoundError:
        cached = None
    if cached is not None:
        return cached
    import contextlib
    import tempfile
    facts = _looked_up()
    Path(cache_dir).mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, tmp = tempfile.mkstemp(dir=cache_dir, prefix=CACHE_NAME + '.', suffix='.tmp')
    try:
        with os.fdopen(fd, 'w') as f:
            f.write(_to_cache(key, facts))
        os.replace(tmp, cache)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise
    return facts


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
        events = close + [Event(now, agent, 'tool_start', call_id=call, tool=tool)]
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
