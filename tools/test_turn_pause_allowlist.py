"""The closing allowlist: what a paused session may still call (spec: Closing allowlist).

Every cancellation input is built from the hook payloads and argument schemas Task 1
recorded under tools/fixtures/turn-pause/, so a naming or schema change in a harness
fails a test here rather than silently refusing cancellation."""
import importlib.machinery
import importlib.util
import json
import os
import signal
import subprocess
from pathlib import Path

import pytest

from turn_pause import allowlist
from turn_pause.allowlist import Owned, Verdict, classify, descends_from, shell, touches_protected

TOOLS = Path(__file__).parent
FIX = TOOLS / 'fixtures' / 'turn-pause'
NOBODY = Owned(worker_names=frozenset(), cron_jobs=frozenset(), harness_pid=None)


def _facts():
    loader = importlib.machinery.SourceFileLoader('harness_facts', str(TOOLS / 'harness-facts'))
    spec = importlib.util.spec_from_loader('harness_facts', loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def fact(name, harness):
    return _facts().lookup(name, harness)


def hook_names(harness):
    """The hook tool names a harness's hook-tool-names fact records (right of '=')."""
    return {v.split('=', 1)[1] for v in fact('hook-tool-names', harness)['value']}


def payload(fixture, tool, event='PreToolUse'):
    data = json.loads((FIX / 'hooks' / fixture).read_text())
    for record in data['records']:
        p = record['payload']
        if p.get('hook_event_name') == event and p.get('tool_name') == tool:
            return p
    raise LookupError(f'{fixture}: no {event} for {tool}')


def schema(fixture):
    data = json.loads((FIX / 'schemas' / fixture).read_text())
    return data, data.get('input_schema') or data.get('parameters')


def spawned_names():
    """The worker names Task 4 records from the spawn fixture: bare and /root/ form."""
    pre = payload('codex-spawn_agent.json', 'collaborationspawn_agent')
    post = payload('codex-spawn_agent.json', 'collaborationspawn_agent', 'PostToolUse')
    return frozenset({pre['tool_input']['task_name'], json.loads(post['tool_response'])['task_name']})


def cron_id():
    post = payload('claude-code-CronDelete.json', 'CronCreate', 'PostToolUse')
    return post['tool_response']['id']


def owned(**kw):
    base = dict(worker_names=frozenset(), cron_jobs=frozenset(), harness_pid=None)
    base.update(kw)
    return Owned(**base)


@pytest.fixture
def child(tmp_path):
    """A real child of this process and a grandchild through sh, both reaped afterwards."""
    env = {'PATH': '/usr/bin:/bin', 'HOME': str(tmp_path)}
    procs, grandchild = [], None
    try:
        procs.append(subprocess.Popen(['sleep', '30'], env=env))
        procs.append(subprocess.Popen(['sh', '-c', 'sleep 30 & echo $!; wait'], env=env,
                                      stdout=subprocess.PIPE, text=True))
        grandchild = int(procs[1].stdout.readline())
        yield procs[0].pid, grandchild
    finally:
        if grandchild is not None:
            try:
                os.kill(grandchild, signal.SIGKILL)
            except ProcessLookupError:
                pass
        for p in procs:
            p.kill()
            p.wait()
            if p.stdout:
                p.stdout.close()


# ---- shell validator: passes -------------------------------------------------------

SHELL_PASSES = [
    ('tasks park lore-1 "next"', 'bookkeeping'),
    ('tasks note x "y"', 'bookkeeping'),
    ('tasks park lore-1 "next" --waiting-on user --reason decision', 'bookkeeping'),
    ('hq pause status', 'bookkeeping'),
    ('hq pause limits', 'bookkeeping'),
    ('tasks show x --no-fetch', 'read'),
    ('tasks claims', 'read'),
    ('tasks list', 'read'),
    ('tasks attach x f.txt --caption "what it shows"', 'read'),
    ('cat a.txt', 'read'),
    ('cat -n a.txt b/c.txt', 'read'),
    ('head -n 5 a', 'read'),
    ('tail -c 10 a', 'read'),
    ('wc -l -w a', 'read'),
    ('ls', 'read'),
    ('ls -la docs/', 'read'),
    ('host-load --section session', 'read'),
    ("tasks note x 'quoted; rm -rf / $(x) `y` | z > w ~ =(a) * \\ !'", 'bookkeeping'),
    ('tasks note x "a; b | c > d & e ( ) * ~ # café → ok"', 'bookkeeping'),
    ("tasks note x 'it'\"'\"'s'", 'bookkeeping'),
]


@pytest.mark.parametrize('cmd, klass', SHELL_PASSES)
def test_shell_passes(cmd, klass):
    v = shell(cmd, NOBODY)
    assert isinstance(v, Verdict) and v.klass == klass and v.reason


# ---- shell validator: refusals -------------------------------------------------------

GIT_AND_PROGRAMS = [
    'git diff', 'git status', 'git worktree list', 'git -c core.pager=cat log',
    'tasks show x', 'tasks show x --no-fetchx', 'tasks start x', 'tasks done x', 'tasks',
    'hq sessions', 'hq pause', 'hq pause resume', 'hq', 'sed -n 1p a', 'sh -c "cat a"',
    'host-load', 'host-load --section all', 'host-load --section session --kill',
    'python3 a.py', 'env cat a', 'command cat a', 'exec cat a', 'xargs cat',
]
OPERATORS = [
    'cat a; rm b', 'cat a | sh', 'cat $(x)', 'cat `x`', 'cat a > b', 'cat a >> b', 'cat < a',
    'cat a & rm b', 'cat a && rm b', 'cat a || rm b', 'cat a\nrm b', 'cat a #c', 'cat $HOME',
    'cat ${x}', 'cat a\\ b', 'cat !x', 'cat {a,b}', 'cat a^b',
]
ENV_AND_PATHS = [
    'FOO=1 cat a', "'FOO=1' cat a", '/bin/cat a', './cat a', 'bin/cat a', '', '   ',
]
OPTIONS = [
    'tail -f log', 'tail -F log', 'tail --follow log', 'tail -n5 a', 'head -n -5 a',
    'cat -v a', 'cat --version', 'ls -R', 'ls --color=always', 'wc --files0-from=x',
    'cat -- a', 'ls -lR',
]
GLOBS = ['ls *', 'cat a?', 'cat [ab]', 'cat a*']
ZSH = [
    'cat =(touch x)', 'cat =ls', "cat ''=ls", 'cat ""=ls', "cat '='ls", 'cat ~/x', 'cat ~',
    "cat a(e:'touch x':)", 'cat a~b', 'cat a(.)', "cat '~'x",
]
CHARS = [
    'cat\ta', 'cat ä', 'cat a\u00a0b', 'cat a\u2028b', 'cat a\rb', "cat 'a\nb'", 'cat "a\nb"',
    "cat 'a", 'cat "a', 'cat "a$b"', 'cat "a`b`"', 'cat "a\\b"', 'cat "a!b"', 'cat a\x00b',
    "cat 'a\x00'",
]


@pytest.mark.parametrize('cmd', GIT_AND_PROGRAMS + OPERATORS + ENV_AND_PATHS + OPTIONS + GLOBS + ZSH + CHARS)
def test_shell_refuses(cmd):
    assert shell(cmd, NOBODY).klass == 'refuse'


@pytest.mark.parametrize('cmd, why', [
    ('cat ""=ls', "starts with '='"), ("cat ''=ls", "starts with '='"), ("cat '~'x", "starts with '~'"),
    ('FOO=1 cat a', 'environment assignment'), ("cat 'a", 'unterminated'),
    ('/bin/cat a', 'bare name'), ('git status', 'not on the closing allowlist'),
])
def test_refusal_reasons(cmd, why):
    v = shell(cmd, NOBODY)
    assert v.klass == 'refuse' and why in v.reason, v.reason


# ---- kill -------------------------------------------------------------------------


def test_kill_own_descendants_is_cancellation(child):
    pid, grandchild = child
    me = owned(harness_pid=os.getpid())
    assert shell(f'kill -TERM {pid}', me).klass == 'cancellation'
    assert shell(f'kill {pid}', me).klass == 'cancellation'
    assert shell(f'kill -KILL {pid} {grandchild}', me).klass == 'cancellation'
    for sig in ('-INT', '-HUP'):
        assert shell(f'kill {sig} {grandchild}', me).klass == 'cancellation'


@pytest.mark.parametrize('template', [
    'kill 1', 'kill 0', 'kill -1', 'kill -TERM -1', 'kill -- -1', 'kill -TERM 0',
    'kill {me}', 'kill -TERM {me}', 'kill {parent}', 'kill {pid} 1', 'kill {pid} {me}',
    'kill', 'kill -TERM', 'kill -9 {pid}', 'kill -s TERM {pid}', 'kill -STOP {pid}',
    'kill -TERM -KILL {pid}', 'kill %1', 'kill 0{pid}', 'kill +{pid}', 'kill -- {pid}',
    'kill -l', 'kill {pid}x', 'kill 99999999999999999999',
])
def test_kill_refusals(child, template):
    pid, _ = child
    cmd = template.format(me=os.getpid(), parent=os.getppid(), pid=pid)
    assert shell(cmd, owned(harness_pid=os.getpid())).klass == 'refuse', cmd


def test_kill_without_known_harness_refused(child):
    pid, _ = child
    assert shell(f'kill {pid}', NOBODY).klass == 'refuse'


# ---- descends_from ----------------------------------------------------------------


def fake_proc(tmp_path, parents):
    proc = tmp_path / 'proc'
    for pid, ppid in parents.items():
        (proc / str(pid)).mkdir(parents=True)
        (proc / str(pid) / 'status').write_text(f'Name:\tx\nPid:\t{pid}\nPPid:\t{ppid}\nUid:\t1\n')
    return proc


def test_descends_from_walks_ppid(tmp_path):
    proc = fake_proc(tmp_path, {1: 0, 10: 1, 20: 10, 30: 20, 40: 1, 50: 50})
    assert descends_from(20, 10, proc)
    assert descends_from(30, 10, proc)
    assert not descends_from(10, 10, proc)
    assert not descends_from(40, 10, proc)
    assert not descends_from(10, 20, proc)
    assert not descends_from(99, 10, proc)
    assert not descends_from(50, 10, proc)
    assert not descends_from(50, 50, proc)


def test_descends_from_real_proc(child):
    pid, grandchild = child
    assert descends_from(pid, os.getpid())
    assert descends_from(grandchild, os.getpid())
    assert not descends_from(os.getpid(), os.getpid())
    assert not descends_from(os.getppid(), os.getpid())


# ---- classify: Claude Code --------------------------------------------------------


def test_claude_bash_goes_through_shell():
    assert classify('claude-code', 'Bash', {'command': 'cat a.txt'}, NOBODY).klass == 'read'
    assert classify('claude-code', 'Bash', {'command': 'git status'}, NOBODY).klass == 'refuse'
    assert classify('claude-code', 'Bash', {}, NOBODY).klass == 'refuse'
    assert classify('claude-code', 'Bash', {'command': ['cat', 'a']}, NOBODY).klass == 'refuse'


@pytest.mark.parametrize('tool', ['Read', 'Grep', 'Glob'])
def test_claude_readers(tool):
    assert classify('claude-code', tool, {'file_path': 'a'}, NOBODY).klass == 'read'


def test_claude_taskstop_from_schema():
    data, sch = schema('claude-code-TaskStop.json')
    assert data['tool'] == 'TaskStop' and 'task_id' in sch['properties']
    assert classify('claude-code', 'TaskStop', {'task_id': 'b1'}, NOBODY).klass == 'cancellation'


def test_claude_crondelete_owned_only():
    p = payload('claude-code-CronDelete.json', 'CronDelete')
    assert p['tool_input']['id'] == cron_id()
    mine = owned(cron_jobs=frozenset({cron_id()}))
    assert classify('claude-code', p['tool_name'], p['tool_input'], mine).klass == 'cancellation'
    assert classify('claude-code', p['tool_name'], p['tool_input'], NOBODY).klass == 'refuse'
    assert classify('claude-code', p['tool_name'], {'id': 'other'}, mine).klass == 'refuse'
    assert classify('claude-code', p['tool_name'], {}, mine).klass == 'refuse'


def test_claude_schedulewakeup_stop_only():
    p = payload('claude-code-ScheduleWakeup.json', 'ScheduleWakeup')
    assert classify('claude-code', p['tool_name'], p['tool_input'], NOBODY).klass == 'refuse'
    assert classify('claude-code', p['tool_name'], {'stop': True}, NOBODY).klass == 'cancellation'
    assert classify('claude-code', p['tool_name'], {'stop': False}, NOBODY).klass == 'refuse'
    assert classify('claude-code', p['tool_name'], {'stop': 'true'}, NOBODY).klass == 'refuse'


@pytest.mark.parametrize('query, klass', [
    ('select:TaskStop', 'cancellation'),
    ('select:TaskStop,CronDelete', 'cancellation'),
    ('select:CronDelete,ScheduleWakeup', 'cancellation'),
    ('select:TaskStop,Write', 'refuse'),
    ('select:Write', 'refuse'),
    ('select:WebFetch', 'refuse'),
    ('select:', 'refuse'),
    ('select:TaskStop,', 'refuse'),
    ('TaskStop', 'refuse'),
    ('+cron delete', 'refuse'),
])
def test_claude_toolsearch(query, klass):
    assert classify('claude-code', 'ToolSearch', {'query': query, 'max_results': 5}, NOBODY).klass == klass


@pytest.mark.parametrize('tool, tool_input', [
    ('Edit', {'file_path': 'a', 'old_string': 'x', 'new_string': 'y'}),
    ('Write', {'file_path': 'a', 'content': 'x'}),
    ('NotebookEdit', {'notebook_path': 'a'}),
    ('Agent', {'prompt': 'x'}),
    ('WebFetch', {'url': 'x'}),
    ('CronCreate', {'cron': '* * * * *', 'prompt': 'x'}),
    ('mcp__x__y', {}),
    ('update_goal', {'status': 'paused'}),
    ('collaborationinterrupt_agent', {'target': 'w0'}),
])
def test_claude_refusals(tool, tool_input):
    mine = owned(worker_names=frozenset({'w0'}))
    assert classify('claude-code', tool, tool_input, mine).klass == 'refuse'


# ---- classify: Codex --------------------------------------------------------------


def test_codex_nested_bash_goes_through_shell():
    assert classify('codex', 'Bash', {'command': 'tasks note x "y"'}, NOBODY).klass == 'bookkeeping'
    p = payload('codex-exec_command-yield.json', 'Bash')
    assert classify('codex', p['tool_name'], p['tool_input'], NOBODY).klass == 'refuse'


def test_codex_interrupt_owned_worker_bare_and_root():
    p = payload('codex-interrupt_agent.json', 'collaborationinterrupt_agent')
    names = spawned_names()
    assert names == {'w0', '/root/w0'}
    mine = owned(worker_names=names)
    for target in sorted(names):
        tool_input = {**p['tool_input'], 'target': target}
        assert classify('codex', p['tool_name'], tool_input, mine).klass == 'cancellation'
    assert classify('codex', p['tool_name'], p['tool_input'], mine).klass == 'refuse'
    assert classify('codex', p['tool_name'], {'target': 'w9'}, mine).klass == 'refuse'
    assert classify('codex', p['tool_name'], {'target': '/root/w9'}, mine).klass == 'refuse'
    assert classify('codex', p['tool_name'], {}, mine).klass == 'refuse'


def test_codex_update_goal_paused_only():
    p = next(r['payload'] for r in json.loads((FIX / 'hooks' / 'codex-remaining-tools.json').read_text())['records']
             if r['payload']['tool_name'] == 'update_goal')
    assert set(p['tool_input']) == {'status'}
    assert classify('codex', p['tool_name'], p['tool_input'], NOBODY).klass == 'refuse'
    assert classify('codex', p['tool_name'], {'status': 'paused'}, NOBODY).klass == 'cancellation'
    for status in ('complete', 'blocked', 'active', 'PAUSED', None):
        assert classify('codex', p['tool_name'], {'status': status}, NOBODY).klass == 'refuse'
    assert classify('codex', p['tool_name'], {}, NOBODY).klass == 'refuse'


def test_codex_nested_mcp_refused():
    p = payload('codex-mcp-nested.json', 'mcp__codex_apps__pets__list_pets')
    assert classify('codex', p['tool_name'], p['tool_input'], NOBODY).klass == 'refuse'


def test_codex_remaining_tools_refused():
    """Every other hooked Codex tool the probes recorded is refused."""
    records = json.loads((FIX / 'hooks' / 'codex-remaining-tools.json').read_text())['records']
    for r in records:
        p = r['payload']
        if p['tool_name'] == 'update_goal':
            continue
        assert classify('codex', p['tool_name'], p['tool_input'], NOBODY).klass == 'refuse', p['tool_name']


@pytest.mark.parametrize('tool, tool_input', [
    ('apply_patch', {'command': '*** Begin Patch\n*** Add File: a\n+x\n*** End Patch'}),
    ('collaborationspawn_agent', {'task_name': 'w1', 'message': 'x'}),
    ('collaborationsend_message', {'target': 'w0', 'message': 'x'}),
    ('collaborationfollowup_task', {'target': 'w0', 'message': 'x'}),
    ('spawn_agent', {'task_name': 'w1'}),
    ('send_message', {'target': 'w0'}),
    ('Read', {'file_path': 'a'}),
    ('TaskStop', {'task_id': 'x'}),
    ('ToolSearch', {'query': 'select:TaskStop'}),
    ('ScheduleWakeup', {'stop': True}),
    ('CronDelete', {'id': 'j1'}),
])
def test_codex_refusals(tool, tool_input):
    mine = owned(worker_names=frozenset({'w0', '/root/w0'}), cron_jobs=frozenset({'j1'}))
    assert classify('codex', tool, tool_input, mine).klass == 'refuse'


def test_codex_spawn_fixture_refused():
    p = payload('codex-spawn_agent.json', 'collaborationspawn_agent')
    assert classify('codex', p['tool_name'], p['tool_input'], owned(worker_names=spawned_names())).klass == 'refuse'


def test_unknown_harness_is_an_error():
    with pytest.raises(ValueError):
        classify('opencode', 'Bash', {'command': 'cat a'}, NOBODY)


# ---- fixtures bind what classify reads ---------------------------------------------


def test_cancellation_controls_match_recorded_names_and_arguments():
    """Each control classify accepts reads the argument its fixture names, under the hook
    name the fixtures and the hook-tool-names fact record."""
    controls = allowlist.CONTROLS
    assert controls == {
        'claude-code': {'TaskStop': None, 'CronDelete': 'id', 'ScheduleWakeup': 'stop', 'ToolSearch': 'query'},
        'codex': {'collaborationinterrupt_agent': 'target', 'update_goal': 'status'},
    }
    _, sch = schema('claude-code-TaskStop.json')
    assert 'task_id' in sch['properties']
    _, sch = schema('claude-code-CronDelete.json')
    assert sch['required'] == ['id']
    assert set(payload('claude-code-CronDelete.json', 'CronDelete')['tool_input']) == {'id'}
    _, sch = schema('claude-code-ScheduleWakeup.json')
    assert sch['properties']['stop']['type'] == 'boolean'
    data, sch = schema('codex-interrupt_agent.json')
    assert (data['namespace'] + data['tool'], sch['required']) == ('collaborationinterrupt_agent', ['target'])
    assert set(payload('codex-interrupt_agent.json', 'collaborationinterrupt_agent')['tool_input']) == {'target'}
    assert {'CronDelete', 'ScheduleWakeup', 'ToolSearch', 'Bash'} <= hook_names('claude-code')
    assert {'collaborationinterrupt_agent', 'update_goal', 'Bash', 'apply_patch'} <= hook_names('codex')
    assert 'exec.exec_command=Bash' in fact('hook-tool-names', 'codex')['value']
    for name in ('claude-code-subagent-bash-denied.json', 'codex-exec_command-yield.json'):
        assert 'command' in payload(name, 'Bash')['tool_input']


def test_unhooked_codex_controls_still_unhooked():
    """write_stdin and wait never reach classify; a Codex that starts hooking them
    must prompt the spec's follow-up."""
    unhooked = fact('hook-unhooked-tools', 'codex')['value']
    assert 'exec.write_stdin' in unhooked and 'wait' in unhooked
    for name in ('codex-write_stdin.json', 'codex-wait.json'):
        assert json.loads((FIX / 'hooks' / name).read_text())['records'] == []


# ---- touches_protected ------------------------------------------------------------


@pytest.fixture
def protected(tmp_path, monkeypatch):
    home = tmp_path / 'home'
    monkeypatch.setenv('HOME', str(home))
    return [home / '.local' / 'state' / 'hq' / 'pause', tmp_path / 'hq' / 'tools' / 'turn_pause' / 'limits.toml']


def test_touches_protected(protected):
    state, limits = protected
    assert touches_protected({'command': 'cat ~/.local/state/hq/pause/x.json'}, protected)
    assert touches_protected({'command': f'cat {state}/x.json'}, protected)
    assert touches_protected({'file_path': str(limits), 'old_string': 'a', 'new_string': 'b'}, protected)
    assert touches_protected({'edits': [{'path': f'x {limits}'}]}, protected)
    assert touches_protected({'file_path': '~/.local/state/hq/pause'}, protected)
    assert not touches_protected({'command': 'cat ~/.local/state/hq/other'}, protected)
    assert not touches_protected({'file_path': 'limits.toml', 'n': 3, 'flag': True, 'none': None}, protected)
    assert not touches_protected({}, protected)
