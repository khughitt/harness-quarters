"""The closing allowlist: which calls a paused session may still make.

Spec: docs/specs/2026-11-01-turn-pause-design.md, "Closing allowlist" through
"Limitation: unhooked Codex controls". Once a session tree is paused the hook refuses
every call this module does not classify as bookkeeping, cancellation or (during
grace) read. It is the security boundary of the pause: a shell command that passes
`shell` must run no program other than its argv[0] and write no file, under sh, bash,
dash and zsh alike, because the hook does not see which shell runs it.

Tool names are the ones hook payloads carry (fact hook-tool-names). Codex's outer
`exec`, nested `write_stdin` and top-level `wait` reach no hook (fact
hook-unhooked-tools), so nothing here classifies them.
"""
import os
import re
import shlex
import string
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

Klass = Literal['bookkeeping', 'cancellation', 'read', 'refuse']


@dataclass(frozen=True)
class Verdict:
    klass: Klass
    reason: str


@dataclass(frozen=True)
class Owned:
    """What this session tree started: Codex worker task names (bare and /root/ form),
    pending Claude Code cron job ids, and the harness process the hook runs under."""
    worker_names: frozenset[str]
    cron_jobs: frozenset[str]
    harness_pid: int | None


# Shell programs. `hq pause` passes only as `hq pause status|limits` (ledger ruling R2);
# `tasks show` only with --no-fetch, since it otherwise runs a document provider.
BOOKKEEPING = {('tasks', 'park'), ('tasks', 'note'), ('hq', 'pause')}
HQ_PAUSE = {'status', 'limits'}
RECORD_READS = {('tasks', 'show'), ('tasks', 'claims'), ('tasks', 'list'), ('tasks', 'attach')}
READERS = {
    'cat': {'-n'},
    'head': {'-n', '-c'},
    'tail': {'-n', '-c'},
    'wc': {'-l', '-c', '-w'},
    'ls': {'-l', '-a', '-la', '-al'},
}
HOST_LOAD = ('host-load', '--section', 'session')
SIGNALS = {'-TERM', '-INT', '-KILL', '-HUP'}
PID = re.compile(r'[1-9][0-9]{0,9}')
# head/tail options that take a count, and the only form that count may take. GNU tail
# also reads a leading `+` operand as obsolete syntax (`tail +1f a` follows), so a `+`
# word passes for tail only as the value of -n or -c.
COUNTED = {'head', 'tail'}
COUNT_OPTIONS = {'-n', '-c'}
COUNT = re.compile(r'\+?[0-9]{1,18}')
SHOWN = 200
# The longest shell command or control argument judged while paused. Every allowlisted
# call fits easily; anything longer is refused before it is scanned, because shlex is
# superlinear (a 1 MB command took seconds) and a hook that outlives the harness's
# timeout lets the call proceed. The spec's budget is 50 ms per call.
MAX_TEXT = 4096
# Distinct kill targets per command: each costs a /proc ancestry walk. A larger kill
# splits across calls, which cancellation never runs out of.
MAX_KILL_TARGETS = 64

CLAUDE_READERS = {'Read', 'Grep', 'Glob'}

# Cancellation controls by hook tool name, each with the one argument classify reads
# (None: harness-scoped, nothing to check). Tests bind these to the recorded fixtures.
CONTROLS: dict[str, dict[str, str | None]] = {
    'claude-code': {'TaskStop': None, 'CronDelete': 'id', 'ScheduleWakeup': 'stop', 'ToolSearch': 'query'},
    'codex': {'collaborationinterrupt_agent': 'target', 'update_goal': 'status'},
}
# What a paused Claude Code session may load through ToolSearch: the deferred controls.
SELECTABLE = frozenset(CONTROLS['claude-code']) - {'ToolSearch'}

# Raw-command character sets. Outside quotes: no operator, expansion, glob, brace,
# parenthesis, comment, tilde, backslash or whitespace other than U+0020.
OUTSIDE = frozenset(string.ascii_letters + string.digits + ' _./:@%+,=-')
IN_DOUBLE_FORBIDDEN = frozenset('$`\\!\n')


def _refuse(reason: str) -> Verdict:
    return Verdict('refuse', reason)


def _show(value) -> str:
    """Untrusted value for a reason, never raising: a str as its repr cut to SHOWN
    characters, anything else by its type name (repr of a deeply nested JSON value
    raises RecursionError, which would crash the hook and let the call through)."""
    if not isinstance(value, str):
        return f'<{type(value).__name__}>'
    text = repr(value)
    return text if len(text) <= SHOWN else text[:SHOWN] + '...'


def _scan(cmd: str) -> str | None:
    """Why the raw command fails the character scan, or None. Runs before shlex because
    zsh expands words shlex reads as plain text (=(...), glob qualifiers)."""
    quote = None
    for i, ch in enumerate(cmd):
        if ch == '\0':
            return f'NUL at offset {i}'
        if quote is None:
            if ch in '\'"':
                quote = ch
            elif ch not in OUTSIDE:
                return f'{ch!r} outside quotes at offset {i}'
        elif quote == "'":
            if ch == "'":
                quote = None
            elif ch == '\n':
                return f'newline inside single quotes at offset {i}'
        else:
            if ch == '"':
                quote = None
            elif ch in IN_DOUBLE_FORBIDDEN:
                return f'{ch!r} inside double quotes at offset {i}'
    if quote is not None:
        return f'unterminated {quote} quote'
    return None


def shell(cmd: str, owned: Owned) -> Verdict:
    """The shell validator: one simple command of an allowlisted program and options."""
    if len(cmd) > MAX_TEXT:
        return _refuse(f'shell command is {len(cmd)} characters; the limit while paused is {MAX_TEXT}')
    bad = _scan(cmd)
    if bad:
        return _refuse(f'shell command refused while paused: {bad}')
    try:
        argv = shlex.split(cmd)
    except ValueError as e:
        return _refuse(f'shell command does not parse: {e}')
    if not argv:
        return _refuse('empty shell command')
    for word in argv:
        if word[:1] in ('=', '~'):
            return _refuse(f'word {_show(word)} starts with {word[0]!r}, which zsh expands')
    prog = argv[0]
    if '=' in prog:
        return _refuse(f'{_show(prog)}: no environment assignment is allowed while paused')
    if '/' in prog:
        return _refuse(f'{_show(prog)}: the program must be a bare name, not a path')
    if prog == 'kill':
        return _kill(argv[1:], owned)
    if prog in ('tasks', 'hq'):
        return _records(argv)
    if tuple(argv) == HOST_LOAD:
        return Verdict('read', 'host-load --section session')
    if prog in READERS:
        return _reader(prog, argv[1:])
    return _refuse(f'{_show(prog)} is not on the closing allowlist (git in any form is refused while paused)')


def _reader(prog: str, words: list[str]) -> Verdict:
    i = 0
    while i < len(words):
        word = words[i]
        if word.startswith('-'):
            if word not in READERS[prog]:
                return _refuse(f'{prog} option {_show(word)} is not allowed while paused (allowed: {sorted(READERS[prog])})')
            if prog in COUNTED and word in COUNT_OPTIONS:
                if i + 1 == len(words) or not COUNT.fullmatch(words[i + 1]):
                    value = _show(words[i + 1]) if i + 1 < len(words) else 'nothing'
                    return _refuse(f'{prog} {word} takes a plain count, not {value}')
                i += 2
                continue
        elif prog == 'tail' and word.startswith('+'):
            return _refuse(f'tail operand {_show(word)}: a leading + is GNU tail\'s obsolete syntax, which can follow')
        i += 1
    return Verdict('read', f'{prog} reads files')


def _records(argv: list[str]) -> Verdict:
    pair = (argv[0], argv[1] if len(argv) > 1 else '')
    if pair in BOOKKEEPING:
        if pair == ('hq', 'pause') and (len(argv) < 3 or argv[2] not in HQ_PAUSE):
            return _refuse('hq pause passes only as hq pause status or hq pause limits')
        return Verdict('bookkeeping', ' '.join(pair))
    if pair in RECORD_READS:
        if pair == ('tasks', 'show') and '--no-fetch' not in argv[2:]:
            return _refuse('tasks show needs --no-fetch while paused')
        return Verdict('read', ' '.join(pair))
    return _refuse(f'{_show(" ".join(argv[:2]))} is not on the closing allowlist')


def _kill(args: list[str], owned: Owned) -> Verdict:
    if owned.harness_pid is None:
        return _refuse('kill: the harness process is not recorded, so no target can be checked')
    if args and args[0] in SIGNALS:
        args = args[1:]
    if not args:
        return _refuse('kill needs at least one pid')
    for arg in args:
        if not PID.fullmatch(arg):
            return _refuse(f'kill target {_show(arg)} is not a positive pid (signal, if any, must be one of {sorted(SIGNALS)} first)')
    pids = {int(arg) for arg in args}
    if len(pids) > MAX_KILL_TARGETS:
        return _refuse(f'kill names {len(pids)} distinct pids; at most {MAX_KILL_TARGETS} per call while paused, so split it')
    for pid in sorted(pids):
        if not descends_from(pid, owned.harness_pid):
            return _refuse(f'kill target {pid} does not descend from the harness process {owned.harness_pid}')
    return Verdict('cancellation', 'kill of processes this session started')


def descends_from(pid: int, ancestor: int, proc: Path = Path('/proc')) -> bool:
    """Whether ancestor is a proper ancestor of pid, by PPid in <proc>/<pid>/status.
    False when any status on the way is missing, unreadable or malformed: a kill the
    walk cannot prove is refused, and nothing escapes into the hook."""
    if pid == ancestor:
        return False
    seen = set()
    current = pid
    while current not in seen:
        seen.add(current)
        try:
            ppid = _ppid((proc / str(current) / 'status').read_text(), proc / str(current) / 'status')
        except (OSError, ValueError):
            return False
        if ppid == ancestor:
            return True
        if ppid <= 0:
            return False
        current = ppid
    return False


def _ppid(status: str, where: Path) -> int:
    for line in status.splitlines():
        if line.startswith('PPid:'):
            parts = line.split()
            if len(parts) != 2:
                raise ValueError(f'{where}: malformed PPid line {line!r}')
            return int(parts[1])
    raise ValueError(f'{where}: no PPid line')


def classify(harness: str, tool: str, tool_input: dict, owned: Owned) -> Verdict:
    """The class of a hooked call while paused; 'refuse' for anything not allowlisted."""
    if harness not in CONTROLS:
        raise ValueError(f'unknown harness {harness!r}')
    if not isinstance(tool, str):
        return _refuse(f'tool name {_show(tool)} is not a string')
    if not isinstance(tool_input, dict):
        return _refuse(f'{_show(tool)} input is not a JSON object')
    if tool == 'Bash':
        cmd = tool_input.get('command')
        if not isinstance(cmd, str):
            return _refuse('Bash call without a command string')
        return shell(cmd, owned)
    if harness == 'claude-code' and tool in CLAUDE_READERS:
        return Verdict('read', f'{tool} reads files')
    controls = CONTROLS[harness]
    if tool not in controls:
        return _refuse(f'{_show(tool)} is not on the closing allowlist')
    arg = controls[tool]
    value = None if arg is None else tool_input.get(arg)
    if isinstance(value, str) and len(value) > MAX_TEXT:
        return _refuse(f'{tool} {arg} is {len(value)} characters; the limit while paused is {MAX_TEXT}')
    if tool == 'TaskStop':
        return Verdict('cancellation', 'TaskStop is scoped to this session')
    if tool == 'CronDelete':
        if isinstance(value, str) and value in owned.cron_jobs:
            return Verdict('cancellation', f'CronDelete of pending job {value}')
        return _refuse(f'CronDelete id {_show(value)} is not a pending job of this session')
    if tool == 'ScheduleWakeup':
        if value is True:
            return Verdict('cancellation', 'ScheduleWakeup stop')
        return _refuse('ScheduleWakeup passes only with stop: true')
    if tool == 'ToolSearch':
        return _tool_search(value)
    if tool == 'collaborationinterrupt_agent':
        if isinstance(value, str) and value in owned.worker_names:
            return Verdict('cancellation', f'interrupt_agent on own worker {value}')
        return _refuse(f'interrupt_agent target {_show(value)} is not a worker this session spawned')
    if tool == 'update_goal':
        if set(tool_input) == {'status'} and value == 'paused':
            return Verdict('cancellation', 'update_goal status paused')
        return _refuse('update_goal passes only as {status: paused}, with no other field')
    raise AssertionError(f'control {tool} has no rule')


def _tool_search(query) -> Verdict:
    if not isinstance(query, str) or not query.startswith('select:'):
        return _refuse('ToolSearch passes only as select: naming cancellation tools')
    names = [n.strip() for n in query[len('select:'):].split(',')]
    if not all(n in SELECTABLE for n in names):
        return _refuse(f'ToolSearch may load only {sorted(SELECTABLE)} while paused')
    return Verdict('cancellation', f'ToolSearch loads {",".join(names)}')


def touches_protected(tool_input: dict, paths: Sequence[Path]) -> bool:
    """Whether any string in the input names a protected path, in full or with ~.
    A string match: it raises the bar, it is not a sandbox."""
    home = os.path.expanduser('~')
    needles = set()
    for path in paths:
        full = os.path.expanduser(str(path))
        for form in {full, os.path.realpath(full)}:
            needles.add(form)
            if form.startswith(home + os.sep):
                needles.add('~' + form[len(home):])
    # One search per needle over all strings joined by NUL, which no path contains, so a
    # match never spans two strings: linear, and fast on multi-megabyte inputs.
    text = '\0'.join(_strings(tool_input))
    return any(needle in text for needle in needles)


def _strings(value) -> Iterator[str]:
    """Every string in a JSON value, keys included; iterative, so no depth escapes."""
    stack = [value]
    while stack:
        item = stack.pop()
        if isinstance(item, str):
            yield item
        elif isinstance(item, dict):
            stack.extend(item.keys())
            stack.extend(item.values())
        elif isinstance(item, (list, tuple)):
            stack.extend(item)
