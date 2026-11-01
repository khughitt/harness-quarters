"""Replay stored session trees through the hook's own engine.feed: how often would the
limits have paused real work?

The trees are the ones lore-911121's turn-spans-v2.py measured: Claude Code roots under
~/.claude/projects with their subagents/ transcripts, and Codex roots under
~/.codex/sessions and ~/.codex/archived_sessions with every descendant rollout obs's
transcript index links to them (read with mode=ro; the stores are never written). Each
transcript record becomes the events the hook would have received for it, and each tree
runs through engine.prompt_kind, engine.start_turn and engine.feed with a decide that
allows every call and records the first call made after a limit was crossed: the pause
point. Spec: docs/specs/2026-11-01-turn-pause-design.md, "Measured range", "Counters",
"Limits" (the replay) and "Verification".

What the hook sees, and so what the converter emits:

- Claude Code. A prompt (UserPromptSubmit) is a root user record with text that is not
  meta, a compaction summary or an interrupt marker; a typed slash command is its
  command line; a scheduled wake (a meta record with turnOrigin scheduled) is a prompt
  too, which the hook reads as a wake through the same pending-prompt records
  (ScheduleWakeup, CronCreate and CronDelete are recorded with hook._record). A tool_use
  is a PreToolUse (Agent and Task also a spawn; a user-wait call first closes its agent's
  open calls), a tool_result its PostToolUse (none for a call another hook refused, whose
  result reads `PreToolUse:<tool> hook error`; it stays open to the next user wait or Stop), a
  compaction summary the counted PostCompact, an assistant record ending its message
  (stop_reason other than tool_use) the agent's Stop or SubagentStop, and a subagent's
  first record its SubagentStart.
- Codex. A prompt is a root UserMessage item. Calls are hooked calls only: each function
  tool except the unhooked ones (harness fact hook-unhooked-tools: exec and wait), and
  each call nested in an exec, from the item_completed the rollout records for it (id
  exec-<uuid>, the hook's tool_use_id), timed by its started_at_ms and completed_at_ms.
  The outer exec is no call and never in flight. A nested exec_command that yielded gets
  no PostToolUse unless a later write_stdin ended it, so it stays in flight until its
  agent's Stop (see nested_end). Spawns are workers that started: one per descendant
  rollout, at each of its task_started (SubagentStart, keyed by the worker's id). Stops
  are task_complete and turn_aborted. Compactions are not counted (no Codex compaction
  hook event).
"""
from __future__ import annotations

import bisect
import collections
import glob
import json
import os
import re
import sqlite3
import sys
import time
from datetime import datetime, timezone

from . import adapters, counters, engine, hook
from .counters import COUNTS
from .engine import Decision
from .events import Event
from .limits import DEFAULTS_FILE, load, with_budget
from .prompt import Budget, parse_budget
from .record import Frozen, Record
from .state import RootState

CONTROLLER = ('codex', '01a18943-2b9d-7e50-926f-b74169571349')  # the sun-fbaf80 controller
CLAUDE_SPAWN = adapters.SPAWN_TOOLS['claude-code']
WAKE_TOOLS = frozenset({'ScheduleWakeup', 'CronCreate', 'CronDelete'})
INTERRUPTED = '[Request interrupted by user'
COMMAND_NAME = re.compile(r'<command-name>(.*?)</command-name>', re.DOTALL)
COMMAND_ARGS = re.compile(r'<command-args>(.*?)</command-args>', re.DOTALL)
# Codex: the hook's tool_name for a top-level tool that is not namespace+name, and for
# each nested item type (only USER_WAIT_TOOLS membership changes counting; none is one).
CODEX_HOOK_NAMES = {'exec_command': 'Bash'}
CODEX_NESTED_NAMES = {'CommandExecution': 'Bash', 'FileChange': 'apply_patch', 'McpToolCall': 'mcp',
                      'ImageView': 'view_image', 'Extension': 'webrun', 'CollabAgentToolCall': 'collaboration'}
CODEX_NEEDLES = ('"session_meta"', '"item_completed"', '"function_call', '"custom_tool_call', '"task_started"',
                 '"task_complete"', '"turn_aborted"')
RUNNING = re.compile(r'Script running with cell ID (\S+)')
YIELD_LITERAL = re.compile(r'yield_time_ms\s*:\s*(\d+)')
# exec_command's yield_time_ms: default 10000 ms, effective 250 to 30000 ms (its declaration).
YIELD_DEFAULT_MS, YIELD_MIN_MS, YIELD_MAX_MS = 10000, 250, 30000
# Nested tools for which no stored rollout was seen to record an item; counted from exec
# source so the report can say how many calls the replay cannot see.
UNRECORDED = ('clock__curr_time', 'create_goal', 'get_goal', 'update_goal', 'list_mcp_resources',
              'list_mcp_resource_templates', 'read_mcp_resource', 'image_gen__imagegen', 'request_plugin_install')
UNRECORDED_CALL = re.compile(r'tools\.(' + '|'.join(UNRECORDED) + r')\s*\(')
IDLE = 600


class Step(Record):
    """One hook call's worth of a transcript, at t: events to feed, or a prompt to
    classify, or (event name, payload) for hook._record's scheduled-prompt records."""
    __slots__ = _fields = ('t', 'agent', 'events', 'prompt', 'record')
    _defaults = {'events': (), 'prompt': None, 'record': None}


class Pause(Frozen):
    """The first call the hook would have refused: its time, the limit, the call, and the
    counts the hook judged."""
    __slots__ = _fields = ('t', 'limit', 'call_id', 'agent', 'active', 'calls', 'spawns', 'compactions')


class Turn(Record):
    """A replayed turn: its TurnState after its last event, and its pause point."""
    __slots__ = _fields = ('harness', 'root', 'start', 'state', 'pause')
    _defaults = {'pause': None}


def ts(text: str) -> float:
    return datetime.fromisoformat(text.replace('Z', '+00:00')).timestamp()


def iso(t: float) -> str:
    return datetime.fromtimestamp(t, timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def records(path, needles=None):
    """The JSON records of a transcript; a line that does not parse is skipped, as the
    measurement did. With needles, only lines containing one of them are parsed."""
    try:
        with open(path, errors='replace') as fh:
            for line in fh:
                if needles is not None and not any(n in line for n in needles):
                    continue
                try:
                    yield json.loads(line)
                except ValueError:
                    continue
    except OSError:
        return


def _merge(lists: list[list[Step]]) -> list[Step]:
    """One time-ordered list; ties keep the root's steps first, then each file's order."""
    out = [s for steps in lists for s in steps]
    out.sort(key=lambda s: s.t)
    return out


# --- Claude Code ----------------------------------------------------------------------

def claude_prompt(r: dict, text: str) -> str | None:
    """The prompt a root user record submits to UserPromptSubmit, or None."""
    if r.get('isMeta'):
        return text if r.get('turnOrigin') == 'scheduled' else None
    if not text.strip() or text.lstrip().startswith(INTERRUPTED):
        return None
    origin = r.get('origin')
    if isinstance(origin, dict) and origin.get('kind') == 'human':
        name = COMMAND_NAME.search(text)
        if name:
            args = COMMAND_ARGS.search(text)
            return f'{name.group(1).strip()} {args.group(1).strip() if args else ""}'.strip()
    return text


def hook_refused(block: dict) -> bool:
    """A tool_result Claude Code wrote for a call a PreToolUse hook refused."""
    content = block.get('content')
    if isinstance(content, list):
        content = ''.join(b.get('text', '') for b in content if isinstance(b, dict))
    return bool(block.get('is_error')) and isinstance(content, str) \
        and content.startswith('PreToolUse:') and ' hook error' in content


def claude_steps(path, agent: str | None = None) -> list[Step]:
    root = agent is None
    steps: list[Step] = []
    wake_calls: dict[str, tuple[str, dict]] = {}
    started = False
    for r in records(path):
        stamp = r.get('timestamp')
        if not stamp:
            continue
        t = ts(stamp)
        if root and r.get('isSidechain'):
            continue
        if not root and not started:
            steps.append(Step(t, agent, (Event(t, agent, 'tick'),)))  # SubagentStart
            started = True
        kind = r.get('type')
        message = r.get('message') or {}
        content = message.get('content')
        if kind == 'user':
            if r.get('isCompactSummary'):
                steps.append(Step(t, agent, (Event(t, agent, 'compact'),)))  # PostCompact
                continue
            if isinstance(content, list):
                blocks = [b for b in content if isinstance(b, dict)]
                for b in blocks:
                    if b.get('type') != 'tool_result':
                        continue
                    call = b.get('tool_use_id')
                    if not hook_refused(b):  # a call another hook refused gets no PostToolUse
                        steps.append(Step(t, agent, (Event(t, agent, 'tool_end', call_id=call),)))
                    if call in wake_calls:
                        name, tool_input = wake_calls.pop(call)
                        event = 'PostToolUseFailure' if b.get('is_error') else 'PostToolUse'
                        steps.append(Step(t, agent, record=(event, _payload(agent, name, tool_input,
                                                                             r.get('toolUseResult')))))
                text = ' '.join(b.get('text', '') for b in blocks if b.get('type') == 'text')
            else:
                text = content if isinstance(content, str) else ''
            if root:
                prompt = claude_prompt(r, text)
                if prompt is not None:
                    steps.append(Step(t, None, prompt=prompt))
            continue
        if kind != 'assistant':
            continue
        for b in content if isinstance(content, list) else ():
            if not isinstance(b, dict) or b.get('type') != 'tool_use':
                continue
            call, name = b.get('id'), b.get('name')
            events = adapters.user_wait_close('claude-code', t, agent, name)
            events.append(Event(t, agent, 'tool_start', call_id=call, tool=name))
            if name in CLAUDE_SPAWN:
                events.append(Event(t, agent, 'spawn', key=call))
            steps.append(Step(t, agent, tuple(events)))
            if name in WAKE_TOOLS:
                tool_input = b.get('input') if isinstance(b.get('input'), dict) else {}
                wake_calls[call] = (name, tool_input)
                steps.append(Step(t, agent, record=('PreToolUse', _payload(agent, name, tool_input))))
        if message.get('stop_reason') not in (None, 'tool_use'):
            steps.append(Step(t, agent, (Event(t, agent, 'agent_stop'),)))  # Stop or SubagentStop
    return steps


def _payload(agent, name, tool_input, response=None) -> dict:
    p = {'tool_name': name, 'tool_input': tool_input}
    if response is not None:
        p['tool_response'] = response
    if agent is not None:
        p['agent_id'] = agent
    return p


def claude_agent(path) -> str:
    name = os.path.basename(path)[:-len('.jsonl')]
    return name[len('agent-'):] if name.startswith('agent-') else name


def read_claude_tree(root_path, child_paths) -> tuple[str, list[Step]]:
    root = os.path.basename(root_path)[:-len('.jsonl')]
    lists = [claude_steps(root_path)] + [claude_steps(c, claude_agent(c)) for c in child_paths]
    return root, _merge(lists)


# --- Codex ----------------------------------------------------------------------------

class Cell(Record):
    """An exec cell: when it was called, its source, and when it finished (its output, or
    for a yielded cell the wait that saw it finish); end None: never seen to finish."""
    __slots__ = _fields = ('t', 'source', 'end')
    _defaults = {'end': None}


class Nested(Record):
    __slots__ = _fields = ('start', 'end', 'call_id', 'kind')


def codex_unhooked() -> frozenset[str]:
    """Top-level Codex tools no hook sees, from the probed harness fact (via
    tools/harness-facts as a module). A nested name (exec.write_stdin) has no item."""
    import importlib.machinery
    import importlib.util
    loader = importlib.machinery.SourceFileLoader('harness_facts', adapters.FACTS_TOOL)
    spec = importlib.util.spec_from_loader('harness_facts', loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    entry = module.lookup('hook-unhooked-tools', 'codex')
    if entry['status'] != 'probed':
        raise ValueError(f'hook-unhooked-tools for codex is {entry["status"]}, not probed')
    return frozenset(name for name in entry['value'] if '.' not in name)


def _output_text(output) -> str:
    if isinstance(output, str):
        return output
    if isinstance(output, list):
        return ''.join(b.get('text', '') for b in output if isinstance(b, dict))
    return ''


def yield_ms(source: str) -> int:
    """The smallest yield_time_ms literal in a cell's source (its first-line exec pragma
    excluded), clamped to exec_command's range; the default when there is none."""
    lines = source.split('\n')
    if lines and lines[0].lstrip().startswith('// @exec:'):
        lines = lines[1:]
    values = [int(v) for v in YIELD_LITERAL.findall('\n'.join(lines))]
    if not values:
        return YIELD_DEFAULT_MS
    return max(YIELD_MIN_MS, min(YIELD_MAX_MS, min(values)))


def nested_end(n: Nested, cells: list[Cell], starts: list[float], stats: collections.Counter) -> float | None:
    """When the hook would close a nested call: its completion, or None (its agent's Stop).

    Only exec_command (CommandExecution) yields. It yielded when the process outlived
    the cell that started it (the yield output went back before the process ended), or,
    ending inside that cell, when it ran past the cell's yield time while the cell calls
    no write_stdin. A yielded call is closed at its completion only when that falls
    inside a later cell that calls write_stdin (the poll or interrupt that ended it, the
    PostToolUse the cancel probe saw); otherwise no PostToolUse comes."""
    if n.kind != 'CommandExecution':
        stats['nested closed at completion'] += 1
        return n.end
    i = bisect.bisect_right(starts, n.start) - 1
    if i < 0:
        stats['nested closed at completion'] += 1
        return n.end
    cell = cells[i]
    cell_end = cell.end if cell.end is not None else float('inf')
    if n.end <= cell_end:
        if 'write_stdin' in cell.source or (n.end - n.start) * 1000 <= yield_ms(cell.source):
            stats['nested closed at completion'] += 1
            return n.end
        stats['exec_command yielded inside its cell, open until Stop'] += 1
        return None
    for later in cells[i + 1:]:
        if later.t > n.end:
            break
        later_end = later.end if later.end is not None else float('inf')
        if n.end <= later_end + 1.0 and 'write_stdin' in later.source:
            stats['exec_command yielded, ended by write_stdin'] += 1
            return n.end
    stats['exec_command yielded, open until Stop'] += 1
    return None


def codex_steps(path, agent: str | None, unhooked: frozenset[str],
                stats: collections.Counter | None = None) -> list[Step]:
    stats = collections.Counter() if stats is None else stats
    root = agent is None
    steps: list[Step] = []
    cells: list[Cell] = []
    cell_of: dict[str, Cell] = {}
    running: dict[str, Cell] = {}
    waits: dict[str, Cell] = {}
    hooked: set[str] = set()
    nested: list[Nested] = []
    for r in records(path, CODEX_NEEDLES):
        stamp = r.get('timestamp')
        if not stamp:
            continue
        t = ts(stamp)
        p = r.get('payload') or {}
        kind, ptype = r.get('type'), p.get('type')
        if kind == 'event_msg':
            if ptype == 'task_started' and not root:
                steps.append(Step(t, agent, (Event(t, agent, 'spawn', key=agent),)))  # SubagentStart
            elif ptype in ('task_complete', 'turn_aborted'):
                steps.append(Step(t, agent, (Event(t, agent, 'agent_stop'),)))  # Stop or SubagentStop
            elif ptype == 'item_completed':
                item = p.get('item') or {}
                if root and item.get('type') == 'UserMessage':
                    text = ' '.join(c.get('text', '') for c in item.get('content') or [] if isinstance(c, dict))
                    steps.append(Step(t, None, prompt=text))
                elif str(item.get('id') or '').startswith('exec-'):
                    start, end = p.get('started_at_ms'), p.get('completed_at_ms')
                    if not isinstance(start, (int, float)) or not isinstance(end, (int, float)):
                        raise ValueError(f'{path}: nested item {item.get("id")} has no start or end time')
                    nested.append(Nested(start / 1000, end / 1000, item['id'], item.get('type')))
            continue
        if kind != 'response_item':
            continue
        call = p.get('call_id')
        if ptype in ('function_call', 'custom_tool_call'):
            name = p.get('name') or ''
            if name == 'exec' and ptype == 'custom_tool_call':
                source = p.get('input') or ''
                cell = Cell(t, source)
                cells.append(cell)
                cell_of[call] = cell
                for m in UNRECORDED_CALL.findall(source):
                    stats[f'unrecorded nested {m}'] += 1
            elif name == 'wait':
                try:
                    args = json.loads(p.get('arguments') or '{}')
                except ValueError:
                    args = {}
                cell = running.get(str(args.get('cell_id')))
                if cell is not None:
                    waits[call] = cell
            if name in unhooked:
                continue
            tool = CODEX_HOOK_NAMES.get(name) or (p.get('namespace') or '') + name
            hooked.add(call)
            events = adapters.user_wait_close('codex', t, agent, tool)
            events.append(Event(t, agent, 'tool_start', call_id=call, tool=tool))
            steps.append(Step(t, agent, tuple(events)))
            stats['function calls'] += 1
        elif ptype in ('function_call_output', 'custom_tool_call_output'):
            if call in cell_of:
                found = RUNNING.match(_output_text(p.get('output')))
                if found:
                    running[found.group(1)] = cell_of[call]
                else:
                    cell_of[call].end = t
            if call in waits and not RUNNING.match(_output_text(p.get('output'))):
                waits.pop(call).end = t
            if call in hooked:
                steps.append(Step(t, agent, (Event(t, agent, 'tool_end', call_id=call),)))
    starts = [c.t for c in cells]
    for n in nested:
        tool = CODEX_NESTED_NAMES.get(n.kind, n.kind)
        steps.append(Step(n.start, agent, (Event(n.start, agent, 'tool_start', call_id=n.call_id, tool=tool),)))
        end = nested_end(n, cells, starts, stats)
        if end is not None:
            steps.append(Step(end, agent, (Event(end, agent, 'tool_end', call_id=n.call_id),)))
    stats['nested calls'] += len(nested)
    steps.sort(key=lambda s: s.t)
    return steps


def codex_meta(path) -> dict:
    first = next(records(path), None) or {}
    return (first.get('payload') or {}) if first.get('type') == 'session_meta' else {}


def read_codex_tree(root_path, child_paths, unhooked, stats=None) -> tuple[str, list[Step]]:
    root = codex_meta(root_path).get('id')
    if not root:
        raise ValueError(f'{root_path}: no session_meta id')
    lists = [codex_steps(root_path, None, unhooked, stats)]
    for child in child_paths:
        agent = codex_meta(child).get('id') or os.path.basename(child)
        lists.append(codex_steps(child, agent, unhooked, stats))
    return root, _merge(lists)


# --- the replay -----------------------------------------------------------------------

def _never(rs, ev):
    raise AssertionError(f'{ev.kind} needs no decision')


def _recorder(turn: Turn):
    """A decide that allows every call and records the first one made past a limit."""
    def decide(rs: RootState, ev: Event) -> Decision:
        if turn.pause is None:
            limit = counters.crossed(rs.turn)
            if limit is not None:
                s = rs.turn
                turn.pause = Pause(ev.t, limit, ev.call_id, ev.agent, s.active, s.calls, s.spawns, s.compactions)
        return Decision(True, None, None)
    return decide


def replay(harness: str, root: str, steps: list[Step], limits, limits_sha: str,
           t0: float | None = None, t1: float | None = None,
           problems: collections.Counter | None = None) -> list[Turn]:
    """The turns of one tree whose genuine prompt falls in [t0, t1). Steps at or after t1
    are dropped, as the measurement did, so no turn starts there. A scheduled-prompt
    record the hook could not read is counted in problems, or raised without it."""
    rs = RootState(harness=harness, root=root, turn=None)
    turns: list[Turn] = []
    decide = None
    for step in steps:
        if t1 is not None and step.t >= t1:
            break
        if step.record is not None:
            event, payload = step.record
            for problem in hook._record(rs, harness, event, dict(payload, session_id=root), step.t, True):
                if problems is None:
                    raise ValueError(f'{harness} {root}: {problem}')
                problems[problem[:80]] += 1
            continue
        if step.prompt is not None:
            kind = engine.prompt_kind(rs, harness, step.prompt, step.t, step.agent)
            if kind == 'turn':
                budget = parse_budget(step.prompt)
                engine.start_turn(rs, step.t, with_budget(limits, budget) if isinstance(budget, Budget) else limits,
                                  limits_sha)
                turns.append(Turn(harness, root, step.t, rs.turn))
                decide = _recorder(turns[-1])
            elif rs.turn is not None:
                engine.feed(rs, [Event(step.t, step.agent, 'tick')], _never)
            continue
        if rs.turn is None:
            continue
        engine.feed(rs, list(step.events), decide)
    return [t for t in turns if t0 is None or t.start >= t0]


# --- the stores -----------------------------------------------------------------------

def _recent(path, t0) -> bool:
    if t0 is None:
        return True
    try:
        return os.path.getmtime(path) >= t0
    except OSError:
        return False


def claude_trees(env, t0):
    base = os.path.join(env['HOME'], '.claude', 'projects')
    for root in sorted(glob.glob(os.path.join(base, '*', '*.jsonl'))):
        if _recent(root, t0):
            yield root, sorted(glob.glob(os.path.join(root[:-len('.jsonl')], 'subagents', '*.jsonl')))


def obs_index(env) -> str:
    state = env.get('XDG_STATE_HOME') or os.path.join(env['HOME'], '.local', 'state')
    return os.path.join(state, 'obs', 'index.sqlite')


def codex_children(env) -> dict[str, list[str]]:
    """Every Codex session's descendants by top ancestor, from obs's index, read-only."""
    index = obs_index(env)
    if not os.path.exists(index):
        raise FileNotFoundError(f'obs transcript index {index} is missing; Codex children cannot be linked')
    db = sqlite3.connect(f'file:{index}?mode=ro', uri=True)
    try:
        parent, path_of = {}, {}
        for sid, par, path in db.execute('select s.session_id, s.parent_session, f.path from sessions s '
                                         "join files f using(file_id) where s.harness='codex'"):
            parent[sid] = par
            path_of.setdefault(sid, path)
    finally:
        db.close()
    children = collections.defaultdict(list)
    for sid, par in parent.items():
        if par is None:
            continue
        top, seen = par, {sid}
        while parent.get(top) and top not in seen:
            seen.add(top)
            top = parent[top]
        children[top].append(path_of[sid])
    return children


def codex_trees(env, t0):
    children = codex_children(env)
    base = os.path.join(env['HOME'], '.codex')
    roots = glob.glob(os.path.join(base, 'sessions', '*', '*', '*', 'rollout-*.jsonl'))
    roots += glob.glob(os.path.join(base, 'archived_sessions', 'rollout-*.jsonl'))
    for root in sorted(roots):
        if not _recent(root, t0):
            continue
        meta = codex_meta(root)
        if not meta or meta.get('thread_source', 'user') != 'user' or meta.get('agent_id'):
            continue
        yield root, [c for c in children.get(meta.get('id'), []) if _recent(c, t0)]


# --- the report -----------------------------------------------------------------------

def _pct(xs, p):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(p * len(xs)))] if xs else 0


def _breakdown(paused: list[Turn]) -> str:
    by = collections.Counter(t.pause.limit for t in paused)
    return ', '.join(f'{name} {by[name]}' for name in COUNTS if by[name])


def report(turns: list[Turn], window: tuple[float, float] | None, limits_path, limits, sha, stats,
           problems, controller_paths, elapsed, files) -> str:
    lines = []
    if window:
        lines.append(f'window [{iso(window[0])}, {iso(window[1])}); limits {limits_path} sha256 {sha}')
        days = (window[1] - window[0]) / 86400
    else:
        lines.append(f'window: every record of the stores read (--all); limits {limits_path} sha256 {sha}')
        starts = [t.start for t in turns]
        days = (max(starts) - min(starts)) / 86400 if len(starts) > 1 else 0.0
    lines.append(f'limits: active {hook.hmm(limits.active_seconds)}, calls {limits.calls}, spawns {limits.spawns}, '
                 f'compactions {limits.compactions}')
    by_harness = {h: [t for t in turns if t.harness == h] for h in adapters.HARNESSES}
    lines.append(f'turns: {len(turns)} (' + ', '.join(f'{h} {len(v)}' for h, v in by_harness.items()) + ')')
    paused = [t for t in turns if t.pause is not None]
    rate = f'{len(paused) / days:.2f} a day over {days:g} days' if days else 'no span to rate'
    lines.append(f'paused: {len(paused)} ({rate})')
    by_limit = collections.Counter(t.pause.limit for t in paused)
    lines.append('per limit: ' + ', '.join(f'{name} {by_limit[name]}' for name in COUNTS))
    parts = []
    for h, v in by_harness.items():
        hp = [t for t in v if t.pause is not None]
        parts.append(f'{h} {len(hp)}' + (f' ({_breakdown(hp)})' if hp else ''))
    lines.append('per harness: ' + ', '.join(parts))
    lines.append('whole turns over each limit alone (counted as the hook counts, nothing refused):')
    for h, v in by_harness.items():
        over = {name: sum(1 for t in v if getattr(t.state, name) > (limits.active_seconds if name == 'active'
                                                                     else getattr(limits, name))) for name in COUNTS}
        lines.append(f'  {h}: ' + ', '.join(f'{name} {over[name]}' for name in COUNTS))
    for h, v in by_harness.items():
        lines.append(f'== {h}: {len(v)} turns')
        for name in COUNTS:
            xs = [getattr(t.state, name) / 60 if name == 'active' else getattr(t.state, name) for t in v]
            label = 'active_min' if name == 'active' else name
            lines.append(f'  {label:12s} ' + '  '.join(f'p{q:g}={_pct(xs, q / 100):.1f}' for q in (50, 90, 99, 99.9))
                         + f'  max={max(xs) if xs else 0:.1f}')
    harness, cid = CONTROLLER
    mine = [t for t in turns if (t.harness, t.root) == CONTROLLER]
    head = f'sun-fbaf80 controller {harness}:{cid}'
    if not mine:
        where = ', '.join(controller_paths) if controller_paths else 'not in the stores read'
        lines.append(f'{head}: no turn in the window; rollout: {where}')
    for t in mine:
        s = t.state
        whole = (f'whole turn active {hook.hmm(s.active)}, calls {s.calls}, spawns {s.spawns}, '
                 f'compactions {s.compactions}')
        if t.pause is None:
            lines.append(f'{head}: turn {iso(t.start)}: not paused; {whole}')
        else:
            p = t.pause
            lines.append(f'{head}: turn {iso(t.start)}: paused at {iso(p.t)} by {p.limit} (active {hook.hmm(p.active)}, '
                         f'calls {p.calls}, spawns {p.spawns}, compactions {p.compactions}); {whole}')
    lines.append('codex converter: ' + ', '.join(f'{k} {v}' for k, v in sorted(stats.items())))
    if problems:
        lines.append('scheduled-prompt records the hook could not read: '
                     + '; '.join(f'{k} x{v}' for k, v in problems.most_common()))
    lines.append(f'read {files} files in {elapsed:.0f} s')
    return '\n'.join(lines) + '\n'


USAGE = 'usage: turn-pause-replay START END [--limits PATH] | turn-pause-replay --all [--limits PATH]'


def main(argv: list[str], env=os.environ, stdout=None) -> int:
    stdout = stdout or sys.stdout
    limits_path, rest = DEFAULTS_FILE, []
    i = 0
    while i < len(argv):
        if argv[i] == '--limits' and i + 1 < len(argv):
            limits_path = argv[i + 1]
            i += 2
        else:
            rest.append(argv[i])
            i += 1
    if rest == ['--all']:
        window = None
    elif len(rest) == 2 and not any(a.startswith('-') for a in rest):
        window = (ts(rest[0]), ts(rest[1]))
    else:
        print(USAGE, file=sys.stderr)
        return 2
    t0, t1 = window if window else (None, None)
    limits, sha = load(limits_path)
    unhooked = codex_unhooked()
    began = time.monotonic()
    turns: list[Turn] = []
    stats, problems = collections.Counter(), collections.Counter()
    files, controller_paths = 0, []
    for root_path, kids in claude_trees(env, t0):
        root, steps = read_claude_tree(root_path, kids)
        files += 1 + len(kids)
        turns += replay('claude-code', root, steps, limits, sha, t0, t1, problems)
    for root_path, kids in codex_trees(env, t0):
        root, steps = read_codex_tree(root_path, kids, unhooked, stats)
        files += 1 + len(kids)
        if root == CONTROLLER[1]:
            controller_paths.append(root_path)
        turns += replay('codex', root, steps, limits, sha, t0, t1, problems)
    stdout.write(report(turns, window, limits_path, limits, sha, stats, problems, controller_paths,
                        time.monotonic() - began, files))
    return 0
