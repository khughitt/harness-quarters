"""The turn-pause hook: one native hook call in, at most one JSON decision out.

Every event goes through engine.feed under the root's state lock. The PreToolUse
decision checks, in order: a changed limits file or a crossed limit (the pause), a
protected path, then, while paused, the closing allowlist with its grace. A PreToolUse
the hook cannot judge is refused with the error; no other event is ever blocked or
answered with a decision (a blocked Stop makes the agent continue). Slow work (the
notification) runs after the state is written, and its result is recorded in a second
short locked update. Spec: docs/specs/2026-11-01-turn-pause-design.md.

Every call pays for its imports (they were most of its latency), so this module and
those it imports keep to json, os, sys, time, fcntl and _sha2: no dataclasses, typing,
tempfile, pathlib or hashlib, and the allowlist (with shlex) loads only on the paused
path. tools/test_turn_pause_hook.py checks the import set.
"""
from __future__ import annotations

import os
import sys
import time

from . import adapters, counters, engine, notify
from .engine import Decision
from .events import Event
from .limits import DEFAULTS_FILE, duration, file_sha256, load, with_budget
from .protect import MAX_NODES, TooManyNodes, too_many_nodes, touches_protected
from .record import jdumps, jloads
from .state import RootState, Store, Wakeup, state_path

CHECKOUT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# The hook wiring in this checkout, and the harness home files that link to it
# (links.toml), protected with the state directory, the limits file and the facts
# snapshot (which decides, among other things, whether compactions are counted).
WIRING = ('harnesses/claude/settings.json', 'harnesses/codex/hooks.json', 'harnesses/codex/work/hooks.json', 'local/claude/settings.work.json')
HOME_LINKS = ('.claude/settings.json', '.claude-work/settings.json', '.codex/hooks.json', '.codex-work/hooks.json')
GRACE = 25
# The largest PreToolUse the hook judges; a larger one is refused (fail closed). Bytes
# alone do not bound the time: just under this cap, a payload of tiny elements has some
# sixteen million JSON nodes and took the entry over 5 s to parse and walk, past the hook
# timeout. So a PreToolUse is also refused, paused or not, past protect.MAX_NODES nodes,
# counted on the raw bytes before parsing (about 0.15 s at the cap). Within both bounds
# parsing and the protected-path scan stay well inside the timeout (measured in the Task 6
# report, fix round 2). Every other event is parsed whatever its size, since only
# json.loads (linear, in C) runs over it, so an oversized PostToolUse still closes its
# call and an oversized prompt still starts a turn; only the budget directive of an
# oversized prompt is not parsed.
MAX_PAYLOAD_BYTES = 32 * 1024 * 1024
OUTPUT_EVENTS = ('PreToolUse', 'UserPromptSubmit')

ROOT_TEXT = (
    'turn paused: {limit} over its limit (active {a} of {A}, root calls {c}/{C}, tree spawns {s}/{S}, '
    'root compactions {k}/{K} (advisory)). Start nothing new and stop the work you already started: interrupt '
    'your subagents and the sessions you launched, stop your background calls and processes, '
    'then pause an active goal only if the user explicitly requested its pause. If an active '
    'goal lacks that authorization, leave its status unchanged, name it in the pause report '
    'and include a request for the user to authorize its pause; do not claim it is paused. '
    'Then write the pause report the turn-pause '
    'rule describes, park your task --waiting-on user --reason decision, and end your turn. If '
    'another agent launched this session, park any claim --waiting-on agent for that agent and '
    'return a short status (done, left, running) instead of a pause report. Only bookkeeping, '
    'plain reads and stopping your own work are allowed now; hq pause status shows the counts.')
CHILD_TEXT = (
    "turn paused by your controller's limit ({limit}). Start nothing new and stop the work you "
    'already started (your background calls and processes), park any claim --waiting-on agent '
    'for your controller, and return a short status (done, left, running). Do not write a '
    'pause report.')
LIMITS_CHANGED_HEAD = ('turn paused: the turn limits file changed mid-turn (active {a} of {A}, root calls {c}/{C}, '
                       'tree spawns {s}/{S}, root compactions {k}/{K} (advisory)). ')
WARNING_TEXT = ('turn-pause: warning only: {limit} at {n}% ({used} of {value}). '
                'Continue authorized work; this is not a pause or a new approval gate. '
                'Give a concise status update and prepare to stop only if a limit is exceeded '
                'or a genuine human gate is reached. hq pause status is the authoritative hook snapshot; '
                'do not add worker calls to root calls. Exact limits are allowed, including the root compaction limit.')
COMPACTION_WARNING_TEXT = (
    'turn-pause: compactions at {used} of {value} (advisory). Compaction does not pause the turn; '
    'continue authorized work while active, calls and spawns remain within their limits.')
BUDGET_TEXT = 'turn-pause: budget for this turn: active {a}, {c} root calls, {s} tree spawns, {k} root compactions (advisory).'
MALFORMED_TEXT = ('turn-pause: the first line looks like a budget but does not parse ({reason}); '
                  'the default limits apply. Mention it in your next report; do not stop for it.')
WAKE_TEXT = ('turn-pause: this prompt matches a pending scheduled prompt and was read as a scheduled '
             'wake, not a new turn; if the user typed it, ask them to rephrase.')
PROTECTED_TEXT = ('turn-pause: this call names a protected path (the pause state, the turn limits or '
                  'the hook wiring) without a validated read, so it is refused. Mutations remain '
                  'prohibited. Inspect with native Read/Grep/Glob or a single cat/head/tail/wc/ls '
                  'or readlink -f command using concrete expanded absolute or checkout-relative '
                  'paths, without tilde, globs, composition or extra execution fields. Paused reads '
                  'spend read grace; hq pause status and hq pause limits remain available.')
NODES_TEXT = (f'turn-pause: the tool input has more than {MAX_NODES} JSON nodes, more than any real tool '
              'input needs and more than the hook can check in time, so the call is refused. Split the '
              'work into smaller calls.')
GRACE_TEXT = (f'the {GRACE} allowlisted reads of grace are used up; only bookkeeping and stopping your '
              'own work remain')
HARNESS_NAMES = ('claude', 'codex')
LIMITS_CHANGED = 'limits-changed'


def _deny(reason: str) -> dict:
    return {'hookSpecificOutput': {'hookEventName': 'PreToolUse', 'permissionDecision': 'deny',
                                   'permissionDecisionReason': reason}}


def _context(event: str, text: str) -> dict:
    return {'hookSpecificOutput': {'hookEventName': event, 'additionalContext': text}}


def _turn(rs: RootState):
    if rs.turn is None:
        raise ValueError(f'{rs.harness} {rs.root} has no turn')
    return rs.turn


def _counts(rs: RootState) -> dict:
    t = _turn(rs)
    lim = t.limits
    return dict(a=duration(t.active), A=duration(lim.active_seconds), c=t.calls, C=lim.calls, s=t.spawns,
                S=lim.spawns, k=t.compactions, K=lim.compactions)


def refusal(rs: RootState, agent: str | None) -> str:
    if agent is not None:
        return CHILD_TEXT.format(limit=rs.paused)
    if rs.paused == LIMITS_CHANGED:
        return LIMITS_CHANGED_HEAD.format(**_counts(rs)) + ROOT_TEXT[ROOT_TEXT.index('Start nothing new'):]
    return ROOT_TEXT.format(limit=rs.paused, **_counts(rs))


def warning(rs: RootState, name: str) -> str:
    t = _turn(rs)
    used = t.active if name == 'active' else getattr(t, name)
    limit = t.limits.active_seconds if name == 'active' else getattr(t.limits, name)
    shown = duration if name == 'active' else (lambda v: str(int(v)))
    if name == 'compactions':
        return COMPACTION_WARNING_TEXT.format(used=shown(used), value=shown(limit))
    label = {'active': 'active time', 'calls': 'root calls', 'spawns': 'tree spawns'}[name]
    return WARNING_TEXT.format(limit=label, n=int(used * 100 // limit) if limit > 0 else 100, used=shown(used), value=shown(limit))


def protected_paths(store_dir, limits_path, env: Mapping[str, str]) -> list[str]:
    paths = [os.fspath(store_dir), os.fspath(limits_path), DEFAULTS_FILE, adapters.SNAPSHOT]
    paths += [os.path.join(CHECKOUT, w) for w in WIRING]
    if env.get('HOME'):
        paths += [os.path.join(env['HOME'], h) for h in HOME_LINKS]
    return paths


def _status(pid: int, proc) -> dict | None:
    try:
        with open(os.path.join(os.fspath(proc), str(pid), 'status')) as f:
            text = f.read()
    except OSError:
        return None
    return dict(line.split(':', 1) for line in text.splitlines() if ':' in line)


def _parent(fields: dict) -> int:
    try:
        return int(fields.get('PPid', '0').strip())
    except ValueError:
        return 0


def find_harness_pid(start: int, proc='/proc') -> int | None:
    """The nearest ancestor (from start) named claude or codex; failing that, the nearest
    node running either; None when neither is found or /proc cannot be read."""
    node = None
    pid, seen = start, set()
    while pid > 0 and pid not in seen:
        seen.add(pid)
        fields = _status(pid, proc)
        if fields is None:
            break
        name = fields.get('Name', '').strip()
        if name in HARNESS_NAMES:
            return pid
        if name == 'node' and node is None:
            import re
            try:
                with open(os.path.join(os.fspath(proc), str(pid), 'cmdline'), 'rb') as f:
                    argv = f.read().decode(errors='replace').split('\0')
            except OSError:
                argv = []
            if any(re.search(r'(^|/)(claude|codex)([-./]|$)', a) for a in argv[1:]):
                node = pid
        pid = _parent(fields)
    return node


def is_ancestor(pid: int, start: int, proc='/proc') -> bool:
    """Whether pid is start or one of its ancestors."""
    current, seen = start, set()
    while current > 0 and current not in seen:
        if current == pid:
            return True
        seen.add(current)
        fields = _status(current, proc)
        if fields is None:
            return False
        current = _parent(fields)
    return False


def current_harness_pid(recorded: int | None, start: int, proc='/proc') -> int | None:
    """The recorded harness pid while it is still an ancestor of start; otherwise (a
    resumed session runs under a new process) the one found again."""
    if recorded is not None and is_ancestor(recorded, start, proc):
        return recorded
    return find_harness_pid(start, proc)


class Judge:
    """The real decision for one PreToolUse's tool_start."""

    def __init__(self, harness: str, payload: dict, limits_sha: str, protected: list[str]):
        self.harness, self.payload, self.limits_sha, self.protected = harness, payload, limits_sha, protected

    def __call__(self, rs: RootState, ev: Event) -> Decision:
        tool_input = self.payload.get('tool_input')
        turn = _turn(rs)
        if rs.paused is None:
            limit = LIMITS_CHANGED if self.limits_sha != turn.limits_sha else counters.crossed(turn)
            if limit is not None:
                rs.paused = limit
                return Decision(False, _deny(refusal(rs, ev.agent)), limit)
        try:
            if touches_protected(tool_input, self.protected):
                from .allowlist import protected_read  # parse only a protected-path match
                if not protected_read(self.harness, ev.tool, tool_input):
                    return Decision(False, _deny(PROTECTED_TEXT), None)
        except TooManyNodes:
            return Decision(False, _deny(NODES_TEXT), None)
        if rs.paused is not None:
            return self._paused(rs, ev, tool_input)
        due = counters.due_warnings(turn)
        if due:
            turn.warned.update(due)
            return Decision(True, _context('PreToolUse', '\n'.join(warning(rs, n) for n in due)), None)
        return Decision(True, None, None)

    def _paused(self, rs: RootState, ev: Event, tool_input) -> Decision:
        from . import allowlist  # with shlex: only a paused turn needs it
        rs.harness_pid = current_harness_pid(rs.harness_pid, os.getppid())
        owned = allowlist.Owned(frozenset(rs.worker_names), frozenset(rs.cron_jobs), rs.harness_pid)
        verdict = allowlist.classify(self.harness, ev.tool, tool_input, owned)
        if verdict.klass in ('bookkeeping', 'cancellation'):
            return Decision(True, None, None)
        if verdict.klass == 'read':
            session = ev.agent or 'root'
            used = rs.grace_used.get(session, 0)
            if used < GRACE:
                rs.grace_used[session] = used + 1
                return Decision(True, None, None)
            why = GRACE_TEXT
        else:
            why = verdict.reason
        return Decision(False, _deny(f'{refusal(rs, ev.agent)} This call: {why}.'), None)


def _never(rs: RootState, ev: Event) -> Decision:
    raise AssertionError(f'{ev.kind} needs no decision')


def _prompt(rs: RootState, harness: str, payload: dict, now: float, limits_path, agent: str | None,
            oversized: bool, record, counted: bool) -> dict | None:
    from . import history
    from .prompt import Budget, Malformed, empty_guards, is_genuine, parse_budget
    text = payload.get('prompt')
    if not isinstance(text, str):
        raise ValueError('UserPromptSubmit payload has no prompt string')
    kind = engine.prompt_kind(rs, harness, text, now, agent)
    if kind == 'turn':
        before = history.snapshot(rs, compactions_counted=counted)
        if before is None and record.ended_at is not None:
            before = next((e['snapshot'] for e in reversed(record.events)
                           if e['turn'] == record.turn_serial and e['snapshot'] is not None), None)
        limits, sha = load(limits_path)
        budget = None if oversized else parse_budget(text)
        note = None
        if isinstance(budget, Budget):
            limits = with_budget(limits, budget)
            note = BUDGET_TEXT.format(a=duration(limits.active_seconds), c=limits.calls, s=limits.spawns,
                                      k=limits.compactions)
        elif isinstance(budget, Malformed):
            note = MALFORMED_TEXT.format(reason=budget.reason)
        engine.start_turn(rs, now, limits, sha, note)
        history.start_turn(record, now, origin='genuine_user', before=before,
                           after=history.snapshot(rs, compactions_counted=counted))
        record.ended_at = None
        record.prompt_guards = empty_guards()
        return None if note is None else _context('UserPromptSubmit', note)
    if rs.turn is None:
        engine.start_turn(rs, now, *load(limits_path))
        history.start_turn(record, now, origin='implicit', before=None,
                           after=history.snapshot(rs, compactions_counted=counted))
    engine.feed(rs, [Event(now, agent, 'tick')], _never)
    if kind == 'wake' and is_genuine(text, harness):
        return _context('UserPromptSubmit', WAKE_TEXT)
    return None


def _response(payload: dict):
    """A tool_response, decoded when Codex sends it as JSON text."""
    response = payload.get('tool_response')
    if isinstance(response, str):
        try:
            return jloads(response)
        except ValueError:
            return response
    return response


def _record(rs: RootState, harness: str, event: str, payload: dict, now: float, allowed: bool) -> list[str]:
    """Ownership and scheduled-prompt records (Task 5 checks the former). Returns the
    payload shapes it could not read, for the caller to raise once the state is written:
    raising here would discard the event's counter update with it."""
    problems = []
    agent = adapters.agent_of(payload)
    if agent is not None and not adapters.is_summarizer(harness, event, payload):
        rs.workers.add(agent)
    if isinstance(payload.get('cwd'), str):
        rs.cwd = payload['cwd']
    tool = payload.get('tool_name')
    tool_input = payload.get('tool_input') if isinstance(payload.get('tool_input'), dict) else {}
    if event == 'PreToolUse' and allowed:
        if harness == 'codex' and tool == 'collaborationspawn_agent':
            name = tool_input.get('task_name')
            if isinstance(name, str) and name:
                rs.worker_names.add(name)
        if harness == 'claude-code' and tool == 'ScheduleWakeup':
            if tool_input.get('stop') is True:
                rs.wakeups.clear()
            elif isinstance(tool_input.get('prompt'), str):
                # Provisional window from the requested delay; PostToolUse sets the real one.
                delay = tool_input.get('delaySeconds')
                fire = now + (delay if isinstance(delay, (int, float)) and not isinstance(delay, bool) else 0)
                rs.wakeups.append(Wakeup(tool_input['prompt'], fire - engine.WAKE_BEFORE, fire + engine.WAKE_AFTER))
    elif event == 'PostToolUse':
        response = _response(payload)
        if harness == 'codex' and tool == 'collaborationspawn_agent':
            if isinstance(response, dict) and isinstance(response.get('task_name'), str):
                rs.worker_names.add(response['task_name'])
            else:
                problems.append(f'spawn_agent response has no task_name: {str(response)[:200]!r}')
        elif harness == 'claude-code' and tool == 'ScheduleWakeup' and isinstance(response, dict):
            fire = response.get('scheduledFor')
            wake = _last_wakeup(rs, tool_input.get('prompt'))
            if isinstance(fire, (int, float)) and wake is not None:
                wake.not_before = fire / 1000 - engine.WAKE_BEFORE
                wake.not_after = fire / 1000 + engine.WAKE_AFTER
        elif harness == 'claude-code' and tool == 'CronCreate':
            job = response.get('id') if isinstance(response, dict) else None
            text = tool_input.get('prompt')
            if isinstance(job, str) and isinstance(text, str):
                rs.cron_jobs[job] = text
            else:
                problems.append(f'CronCreate response has no id or input no prompt: {str(response)[:200]!r}')
        elif harness == 'claude-code' and tool == 'CronDelete':
            rs.cron_jobs.pop(tool_input.get('id'), None)
    elif event == 'PostToolUseFailure':
        if harness == 'claude-code' and tool == 'ScheduleWakeup':
            wake = _last_wakeup(rs, tool_input.get('prompt'))
            if wake is not None:
                rs.wakeups.remove(wake)
    elif event == 'Stop' and harness == 'claude-code' and 'session_crons' in payload:
        crons = payload['session_crons']
        if isinstance(crons, list) and all(
                isinstance(c, dict) and isinstance(c.get('id'), str) and isinstance(c.get('prompt'), str) for c in crons):
            rs.cron_jobs = {c['id']: c['prompt'] for c in crons}
        else:
            problems.append(f'Stop session_crons is not a list of {{id, prompt}}: {str(crons)[:200]!r}')
    return problems


def _last_wakeup(rs: RootState, text) -> Wakeup | None:
    for wake in reversed(rs.wakeups):
        if wake.text == text:
            return wake
    return None


def _notice(rs: RootState, harness: str, root: str, limit: str) -> tuple[str, str]:
    c = _counts(rs)
    body = (f'{harness} session {root} in {rs.cwd or "an unknown directory"}: active {c["a"]} of {c["A"]}, root calls {c["c"]}/{c["C"]}, '
            f'tree spawns {c["s"]}/{c["S"]}, root compactions {c["k"]}/{c["K"]} (advisory). Reply in the session to resume.')
    return f'turn paused ({limit})', body


def decide(harness: str, event: str, payload: dict, now: float, store: Store, limits_path,
           env: Mapping[str, str], *, oversized: bool = False) -> dict | None:
    """The decision JSON (a deny, or added context) or None. A PreToolUse that cannot be
    judged is denied with the error; any other event's error is raised to the entry.
    oversized: the payload was over MAX_PAYLOAD_BYTES, so a prompt's budget is not parsed."""
    limits_path = os.fspath(limits_path)
    if event != 'PreToolUse':
        return _decide(harness, event, payload, now, store, limits_path, env, oversized)
    try:
        return _decide(harness, event, payload, now, store, limits_path, env, oversized)
    except Exception as e:
        return _deny(f'turn-pause could not judge this call, so it is refused: {type(e).__name__}: {e}')


def _decide(harness, event, payload, now, store, limits_path, env, oversized):
    facts = adapters.load_facts()
    root, events = adapters.normalize(harness, event, payload, now, facts)
    agent = adapters.agent_of(payload)
    counted = bool(facts.compact_events.get(harness))
    if event == 'SessionEnd':
        if agent is None:
            store.end(harness, root, now, compactions_counted=counted)
            store.prune(now, compactions_counted={h: bool(v) for h, v in facts.compact_events.items()})
        return None
    limits_sha = file_sha256(limits_path) if event == 'PreToolUse' else None
    protected = protected_paths(store.dir, limits_path, env) if event == 'PreToolUse' else None
    pause = None
    with store.locked(harness, root) as record:
        rs = record.state
        if rs is None:
            if event == 'UserPromptSubmit':
                from .prompt import guarded_prompt_kind, is_genuine
                text = payload.get('prompt')
                if not isinstance(text, str):
                    raise ValueError('UserPromptSubmit payload has no prompt string')
                if agent is not None or not is_genuine(text, harness):
                    return None
                if guarded_prompt_kind(record.prompt_guards, text, now) == 'wake':
                    return _context('UserPromptSubmit', WAKE_TEXT)
                rs = record.state = RootState(harness, root, None)
            elif event == 'PreToolUse':
                return _deny('turn-pause: root session ended; a genuine root prompt is required to resume.')
            else:
                return None
        if rs.harness_pid is None and (rs.turn is None or event == 'UserPromptSubmit'):
            rs.harness_pid = find_harness_pid(os.getppid())
        if rs.turn is None and event != 'UserPromptSubmit':
            from . import history
            engine.start_turn(rs, now, *load(limits_path))
            history.start_turn(record, now, origin='implicit', before=None,
                               after=history.snapshot(rs, compactions_counted=counted))
        output = None
        allowed = False
        if event == 'UserPromptSubmit':
            output = _prompt(rs, harness, payload, now, limits_path, agent, oversized, record, counted)
        elif event == 'PreToolUse':
            warned = set(rs.turn.warned)
            decision = engine.feed(rs, events, Judge(harness, payload, limits_sha, protected))
            output, allowed = decision.output, decision.allow
            new_warned = rs.turn.warned - warned if rs.turn.warned != warned else None
            if new_warned or (decision.paused is not None and not rs.notified):
                from . import history
                snap = history.snapshot(rs, compactions_counted=counted)
                if new_warned:
                    for metric in sorted(new_warned):
                        history.append_event(record, 'warning', now, reason=metric, snapshot=snap)
                if decision.paused is not None and not rs.notified:
                    rs.notified = True
                    notice = dict(outcome='pending', error_code=None, desktop='unknown', relay='unknown',
                                  receipt='unknown', pause_sequence=record.event_serial + 1)
                    transition = history.append_event(record, 'enforced_pause', now, reason=decision.paused,
                                                      snapshot=snap, notification=notice)
                    pause = (_notice(rs, harness, root, decision.paused), record.generation,
                             record.turn_serial, transition['sequence'], snap)
        else:
            engine.feed(rs, events, _never)
        problems = _record(rs, harness, event, payload, now, allowed)
        cwd = rs.cwd
    if pause is not None:
        from . import history
        message, generation, turn, sequence, snap = pause
        error = notify.send(*message, env=env, agent=f'{harness}:{root}', cwd=cwd)
        with store.locked(harness, root, create=False) as record:
            if record is None or record.generation != generation:
                print('turn-pause: notification outcome unknown; original root generation unavailable', file=sys.stderr)
            else:
                notice = dict(outcome='error' if error else 'attempted', error_code='notify_failed' if error else None,
                              desktop='unknown', relay='unknown', receipt='unknown', pause_sequence=sequence)
                history.append_event(record, 'notification', now, reason=None, snapshot=snap,
                                     notification=notice, turn=turn)
                if record.state is not None and record.turn_serial == turn:
                    record.state.notify_error = error
    if problems:
        raise ValueError(f'{event}: state written, records skipped: ' + '; '.join(problems))
    return output


USAGE = (f'usage: turn-pause --harness {"|".join(adapters.HARNESSES)} [--limits PATH] EVENT\n'
         '       turn-pause --write-facts-snapshot [PATH]')


def _args(argv: list[str]) -> tuple[str, str, str]:
    harness, limits_path, rest = None, DEFAULTS_FILE, []
    i = 0
    while i < len(argv):
        if argv[i] in ('--harness', '--limits') and i + 1 < len(argv):
            if argv[i] == '--harness':
                harness = argv[i + 1]
            else:
                limits_path = argv[i + 1]
            i += 2
        else:
            rest.append(argv[i])
            i += 1
    if harness not in adapters.HARNESSES or len(rest) != 1:
        raise ValueError(f'{USAGE}; got {argv!r}')
    return harness, limits_path, rest[0]


def main(argv: list[str], stdin=None, stdout=None, stderr=None, env: Mapping[str, str] = os.environ) -> int:
    """Run one hook call. Prints at most one JSON object and always exits 0: a PreToolUse
    that fails is refused, every other event's failure goes to stderr. With
    --write-facts-snapshot it instead regenerates the facts snapshot (exit 1 on failure)."""
    stdin = stdin or sys.stdin.buffer
    stdout, stderr = stdout or sys.stdout, stderr or sys.stderr
    if argv[:1] == ['--write-facts-snapshot']:
        if len(argv) > 2:
            print(USAGE, file=stderr)
            return 2
        target = argv[1] if len(argv) == 2 else adapters.SNAPSHOT
        adapters.write_snapshot(target)
        print(f'wrote {target}', file=stderr)
        return 0
    event = argv[-1] if argv else ''
    output = None
    try:
        harness, limits_path, event = _args(argv)
        raw = stdin.read()
        oversized = len(raw) > MAX_PAYLOAD_BYTES
        if oversized and event == 'PreToolUse':
            raise ValueError(f'the hook payload is {len(raw)} bytes, over the {MAX_PAYLOAD_BYTES} byte cap; '
                             'split the work into smaller calls')
        if event == 'PreToolUse' and too_many_nodes(raw):
            output = _deny(NODES_TEXT)
            return _emit(output, event, stdout)
        payload = jloads(raw)
        del raw
        output = decide(harness, event, payload, time.time(), Store(state_path(env)), limits_path, env,
                        oversized=oversized)
    except BaseException as e:  # nothing escapes: a crashing hook lets the call through
        if event == 'PreToolUse':
            output = _deny(f'turn-pause could not judge this call, so it is refused: {type(e).__name__}: {e}')
        else:
            print(f'turn-pause: {event or "?"}: {type(e).__name__}: {e}', file=stderr)
            output = None
    return _emit(output, event, stdout)


def _emit(output: dict | None, event: str, stdout) -> int:
    if output is not None and event in OUTPUT_EVENTS:
        stdout.write(jdumps(output) + '\n')
        stdout.flush()
    return 0
