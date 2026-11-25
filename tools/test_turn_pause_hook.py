"""The turn-pause hook: payloads in, decisions out (spec: The unit, Counters, Warning,
pause, notification, Resuming and granting more, State and integrity).

Payloads are the recorded hook fixtures under tools/fixtures/turn-pause/hooks/ with the
fields a case needs replaced. Shapes no fixture holds (Claude Code PreCompact,
PostCompact, the compaction summarizer's SubagentStop, Codex prompts and stops) are
built from the raw probe logs' keys and say so where they are built."""
import copy
import json
import os
import shlex
import shutil
import socket
import subprocess
import threading
import time
from pathlib import Path

import pytest

from turn_pause import adapters, engine, hook, notify
from turn_pause.counters import TurnState
from turn_pause.events import Event
from turn_pause.limits import DEFAULTS_PATH, Limits, load
from turn_pause.prompt import Malformed, parse_budget
from turn_pause.state import RootState, Store, state_dir

TOOLS = Path(__file__).parent
CHECKOUT = TOOLS.parent
ENTRY = TOOLS / 'turn-pause'
HOOKS = TOOLS / 'fixtures' / 'turn-pause' / 'hooks'
T0 = 1_793_539_000.0
CLAUDE_ROOT = '7f0c44c1-4c1f-40da-9a15-aa0917fa0728'
CODEX_ROOT = '01a19737-5420-7280-9b27-80cdf4ba57c6'

ROOT_TEXT = (
    'turn paused: {limit} over its limit (active {a} of {A}, root calls {c}/{C}, tree spawns {s}/{S}, '
    'root compactions {k}/{K} (advisory)). Start nothing new and stop the work you already started: interrupt '
    'your subagents and the sessions you launched, stop your background calls and processes, '
    'then pause an active goal only if the user explicitly requested its pause. If an active '
    'goal lacks that authorization, leave its status unchanged, name it in the pause report '
    'and include a request for the user to authorize its pause; do not claim it is paused. '
    'Then record the durable pause report the turn-pause rule describes with single-line '
    'tasks note calls (file writes are refused while paused; split across notes past 16,384 '
    'characters), park your task --waiting-on user --reason decision, and end your turn '
    'with the continuation decision and any exact budget: line in your closing message '
    '(question tools are refused while paused). If '
    'another agent launched this session, park any claim --waiting-on agent for that agent and '
    'return a short status (done, left, running) instead of a pause report. Only bookkeeping, '
    'plain reads and stopping your own work are allowed now; hq pause status shows the counts.')
CHILD_TEXT = (
    "turn paused by your controller's limit ({limit}). Start nothing new and stop the work you "
    'already started (your background calls and processes), park any claim --waiting-on agent '
    'for your controller, and return a short status (done, left, running). Do not write a '
    'pause report.')
LIMITS_CHANGED_TEXT = (
    'turn paused: the turn limits file changed mid-turn (active {a} of {A}, root calls {c}/{C}, tree spawns {s}/{S}, '
    'root compactions {k}/{K} (advisory)). ' + ROOT_TEXT[ROOT_TEXT.index('Start nothing new'):])
OWNER_LINE = (
    '(owner: hq; a wrong or unclear block is feedback: '
    'tasks feedback --project hq — see Feedback in your instructions)'
)
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
PARK = 'tasks park hq-123456 "paused at calls" --waiting-on user --reason decision'


# --- payloads -------------------------------------------------------------------------

def fixture(name, event, tool=None, nth=0):
    found = [r['payload'] for r in json.loads((HOOKS / name).read_text())['records']
             if r['payload'].get('hook_event_name') == event
             and (tool is None or r['payload'].get('tool_name') == tool)]
    return copy.deepcopy(found[nth])


def claude_pre(tool, tool_input, call_id, agent=None):
    p = fixture('claude-code-subagent-bash-denied.json', 'PreToolUse', 'Bash')
    del p['agent_id'], p['agent_type']
    p.update(session_id=CLAUDE_ROOT, tool_name=tool, tool_input=tool_input, tool_use_id=call_id)
    if agent:
        p.update(agent_id=agent, agent_type='general-purpose')
    return p


def post(pre, response='', event='PostToolUse'):
    p = copy.deepcopy(pre)
    p.update(hook_event_name=event, tool_response=response)
    return p


def claude_prompt(text):
    p = fixture('claude-code-ScheduleWakeup.json', 'UserPromptSubmit')
    p.update(session_id=CLAUDE_ROOT, prompt=text)
    return p


def claude_stop(crons=None):
    p = fixture('claude-code-CronCreate.json', 'Stop')
    p['session_id'] = CLAUDE_ROOT
    if crons is not None:
        p['session_crons'] = crons
    return p


def claude_bare(event, **extra):
    """Shapes from the raw log claude-compact-1/hooks.jsonl (no fixture holds them)."""
    base = fixture('claude-code-ScheduleWakeup.json', 'UserPromptSubmit')
    p = {k: base[k] for k in ('session_id', 'transcript_path', 'cwd')}
    p.update(session_id=CLAUDE_ROOT, hook_event_name=event, **extra)
    return p


def codex_pre(tool, tool_input, call_id, agent=None):
    p = fixture('codex-exec_command-yield.json', 'PreToolUse', 'Bash')
    p.update(session_id=CODEX_ROOT, tool_name=tool, tool_input=tool_input, tool_use_id=call_id)
    if agent:
        p.update(agent_id=agent, agent_type='default')
    return p


def codex_bare(event, **extra):
    """Codex prompt, Stop and SubagentStop: the keys raw logs codex-main-1 and
    codex-spawn-direct-1 show for them."""
    base = fixture('codex-exec_command-yield.json', 'PreToolUse', 'Bash')
    p = {k: base[k] for k in ('session_id', 'turn_id', 'transcript_path', 'cwd', 'model', 'permission_mode')}
    p.update(session_id=CODEX_ROOT, hook_event_name=event, **extra)
    return p


def codex_prompt(text):
    return codex_bare('UserPromptSubmit', prompt=text)


def codex_subagent_start(agent):
    p = fixture('codex-spawn_agent.json', 'SubagentStart')
    p.update(session_id=CODEX_ROOT, agent_id=agent)
    return p


def codex_spawn(task_name, call_id, agent=None):
    p = fixture('codex-spawn_agent.json', 'PreToolUse', 'collaborationspawn_agent')
    p.update(session_id=CODEX_ROOT, tool_use_id=call_id)
    p['tool_input']['task_name'] = task_name
    if agent:
        p.update(agent_id=agent, agent_type='default')
    return p


# --- outputs --------------------------------------------------------------------------

def denied(out):
    return out is not None and out['hookSpecificOutput'].get('permissionDecision') == 'deny'


def reason(out):
    return out['hookSpecificOutput']['permissionDecisionReason']


def context(out):
    return None if out is None else out['hookSpecificOutput'].get('additionalContext')


def write_limits(path, **over):
    values = dict(active_seconds=14400, calls=500, spawns=30, compactions=2)
    values.update(over)
    path.write_text(''.join(f'{k} = {v}\n' for k, v in values.items()))


def make_env(tmp_path, notify_send=True):
    """Built key by key: nothing inherited, a stub notify-send first on PATH."""
    home, run, bin_ = tmp_path / 'home', tmp_path / 'run', tmp_path / 'bin'
    for d in (home, run, bin_):
        d.mkdir(exist_ok=True)
    if notify_send:
        stub = bin_ / 'notify-send'
        stub.write_text('#!/bin/sh\nprintf "%s\\n" "$@" >> "$(dirname "$0")/notify-send.log"\n')
        stub.chmod(0o755)
        path = f'{bin_}:/usr/bin:/bin'
    else:
        path = str(bin_)
    return {'PATH': path, 'HOME': str(home), 'XDG_STATE_HOME': str(tmp_path / 'state'),
            'XDG_RUNTIME_DIR': str(run)}


class Driver:
    def __init__(self, tmp_path, harness, notify_send=True):
        self.tmp = tmp_path
        self.env = make_env(tmp_path, notify_send)
        self.store = Store(state_dir(self.env))
        self.limits = tmp_path / 'limits.toml'
        self.limits.write_bytes(DEFAULTS_PATH.read_bytes())
        self.harness = harness
        self.root = CLAUDE_ROOT if harness == 'claude-code' else CODEX_ROOT
        self.t = T0
        self.n = 0

    def __call__(self, event, payload, dt=1.0):
        """One hook call at self.t + dt; every payload is put under this driver's root."""
        self.t += dt
        payload = dict(payload, session_id=self.root)
        return hook.decide(self.harness, event, payload, self.t, self.store, self.limits, self.env)

    def call_id(self):
        self.n += 1
        return f'call-{self.n}'

    def prompt(self, text, dt=1.0):
        maker = claude_prompt if self.harness == 'claude-code' else codex_prompt
        return self('UserPromptSubmit', maker(text), dt)

    def pre(self, tool, tool_input, agent=None, dt=1.0):
        maker = claude_pre if self.harness == 'claude-code' else codex_pre
        payload = maker(tool, tool_input, self.call_id(), agent)
        return self('PreToolUse', payload, dt), payload

    def bash(self, cmd, agent=None, dt=1.0):
        return self.pre('Bash', {'command': cmd}, agent, dt)[0]

    def state(self):
        return self.store.read(self.harness, self.root)

    def pause_on_calls(self, limit=2):
        """Start a turn whose call limit is `limit` and make calls until one is refused."""
        write_limits(self.limits, calls=limit)
        self.prompt('do the work')
        for _ in range(limit):
            assert not denied(self.bash('ls'))
        out = self.bash('ls')
        assert denied(out)
        return out


@pytest.fixture
def notices(monkeypatch):
    sent = []
    monkeypatch.setattr(hook.notify, 'send', lambda title, body, **kw: sent.append((title, body, kw)) or None)
    return sent


# --- turns ----------------------------------------------------------------------------

def test_genuine_prompt_starts_turn_with_last_t_at_the_prompt(tmp_path):
    d = Driver(tmp_path, 'claude-code')
    assert d.prompt('fix the parser') is None
    st = d.state()
    assert st.turn.started == d.t and st.turn.last_t == d.t
    d.bash('ls', dt=30)
    assert d.state().turn.active == 30 and d.state().turn.calls == 1


def test_injected_prompt_does_not_reset_counters(tmp_path):
    d = Driver(tmp_path, 'claude-code')
    d.prompt('fix the parser')
    d.bash('ls')
    d.bash('ls')
    assert d.prompt('<task-notification>\n<task-id>a1</task-id>\n</task-notification>') is None
    assert d.state().turn.calls == 2


def test_schedule_wakeup_inside_window_is_a_wake_and_consumed(tmp_path, notices):
    d = Driver(tmp_path, 'claude-code')
    write_limits(d.limits, calls=3)
    pre = fixture('claude-code-ScheduleWakeup.json', 'PreToolUse', 'ScheduleWakeup')
    after = fixture('claude-code-ScheduleWakeup.json', 'PostToolUse', 'ScheduleWakeup')
    wake = fixture('claude-code-ScheduleWakeup.json', 'UserPromptSubmit')
    fire = after['tool_response']['scheduledFor'] / 1000
    d.t = fire - 120
    d.prompt('loop on this')
    assert not denied(d('PreToolUse', pre))
    d('PostToolUse', after)
    assert [(w.text, w.not_before, w.not_after) for w in d.state().wakeups] == \
        [(pre['tool_input']['prompt'], fire - 60, fire + 600)]
    d.bash('ls')
    d.bash('ls')
    assert denied(d.bash('ls'))
    calls = d.state().turn.calls
    d.t = fire + 5
    out = d('UserPromptSubmit', wake, dt=0)
    assert context(out) == WAKE_TEXT
    st = d.state()
    assert st.paused == 'calls' and st.turn.calls == calls and st.wakeups == []
    # the same text typed after the window is a genuine prompt
    d.t = fire + 700
    assert d('UserPromptSubmit', wake, dt=0) is None
    st = d.state()
    assert st.paused is None and st.turn.calls == 0


def test_a_worker_prompt_never_matches_or_consumes_a_wake(tmp_path, notices):
    d = Driver(tmp_path, 'claude-code')
    write_limits(d.limits, calls=1)
    pre = fixture('claude-code-ScheduleWakeup.json', 'PreToolUse', 'ScheduleWakeup')
    after = fixture('claude-code-ScheduleWakeup.json', 'PostToolUse', 'ScheduleWakeup')
    wake = fixture('claude-code-ScheduleWakeup.json', 'UserPromptSubmit')
    fire = after['tool_response']['scheduledFor'] / 1000
    d.t = fire - 120
    d.prompt('loop on this')
    d('PreToolUse', pre)
    d('PostToolUse', after)
    d('Stop', claude_stop())  # its cron list also holds the wake prompt and a recurring job
    assert denied(d.bash('ls'))
    d.t = fire + 5
    worker = dict(wake, agent_id='a620dc1cd95e3a1c5', agent_type='general-purpose')
    assert d('UserPromptSubmit', worker, dt=0) is None
    cron = dict(worker, prompt=claude_stop()['session_crons'][0]['prompt'])
    assert d('UserPromptSubmit', cron, dt=0) is None
    st = d.state()
    assert st.paused == 'calls' and len(st.wakeups) == 1
    # the root's own wake still matches and is consumed, and does not lift the pause
    assert context(d('UserPromptSubmit', wake, dt=0)) == WAKE_TEXT
    st = d.state()
    assert st.paused == 'calls' and st.wakeups == []


def test_cron_prompt_is_a_wake_until_its_delete(tmp_path):
    d = Driver(tmp_path, 'claude-code')
    d.prompt('set a cron')
    pre = fixture('claude-code-CronDelete.json', 'PreToolUse', 'CronCreate')
    d('PreToolUse', pre)
    d('PostToolUse', fixture('claude-code-CronDelete.json', 'PostToolUse', 'CronCreate'))
    assert d.state().cron_jobs == {'808dcbf2': pre['tool_input']['prompt']}
    d.bash('ls')
    assert context(d.prompt(pre['tool_input']['prompt'])) == WAKE_TEXT
    assert d.state().turn.calls == 2
    d('PreToolUse', fixture('claude-code-CronDelete.json', 'PreToolUse', 'CronDelete'))
    d('PostToolUse', fixture('claude-code-CronDelete.json', 'PostToolUse', 'CronDelete'))
    assert d.state().cron_jobs == {}
    assert d.prompt(pre['tool_input']['prompt']) is None
    assert d.state().turn.calls == 0


def test_cron_prompt_is_a_wake_until_a_stop_no_longer_lists_it(tmp_path):
    d = Driver(tmp_path, 'claude-code')
    d.prompt('set a cron')
    stop = claude_stop()
    d('Stop', stop)
    assert d.state().cron_jobs == {c['id']: c['prompt'] for c in stop['session_crons']}
    text = stop['session_crons'][0]['prompt']
    d.bash('ls')
    assert context(d.prompt(text)) == WAKE_TEXT
    assert d.state().turn.calls == 1
    d('Stop', claude_stop(crons=stop['session_crons'][1:]))
    assert d.prompt(text) is None
    assert d.state().turn.calls == 0


# --- pause ----------------------------------------------------------------------------

@pytest.mark.parametrize('harness', ['claude-code', 'codex'])
def test_warning_allows_work_at_the_limit_and_excludes_worker_calls(tmp_path, notices, harness):
    d = Driver(tmp_path, harness)
    write_limits(d.limits, calls=4)
    d.prompt('execute the authorized plan')
    for _ in range(6):
        assert not denied(d.bash('worker-check', agent='worker-1'))
    assert d.state().turn.calls == 0
    for _ in range(2):
        assert not denied(d.bash('check'))
    out = d.bash('check')
    assert not denied(out)
    assert 'warning only: root calls at 75%' in context(out)
    assert 'Continue authorized work' in context(out)
    assert 'not a pause or a new approval gate' in context(out)
    assert d.state().paused is None
    assert not denied(d.bash('check'))  # exactly four root calls
    assert d.state().paused is None
    assert denied(d.bash('check'))
    assert d.state().paused == 'calls'


def test_2001st_root_call_is_denied_with_the_root_text_after_one_warning(tmp_path, notices):
    d = Driver(tmp_path, 'claude-code')
    d.prompt('a long job')
    with d.store.locked('claude-code', CLAUDE_ROOT) as record:
        record.state.turn.calls = 1498
    assert d.bash('ls', dt=240) is None  # 1499: below 75%
    out = d.bash('ls', dt=60)  # 1500: 75% warning
    assert not denied(out)
    assert context(out) == WARNING_TEXT.format(limit='root calls', n=75, used=1500, value=2000)
    assert d.bash('ls', dt=60) is None  # 1501: warning is not repeated
    with d.store.locked('claude-code', CLAUDE_ROOT) as record:
        record.state.turn.calls = 1999
    assert d.bash('ls', dt=60) is None  # 2000: exact limit is allowed
    out = d.bash('ls', dt=60)  # 2001: refused
    assert denied(out)
    assert reason(out) == (
        ROOT_TEXT.format(limit='calls', a='0h08m', A='16h00m', c=2001, C=2000, s=0, S=60, k=0, K=2)
        + f'\n{OWNER_LINE}'
    )
    assert 'stop the work you already started: interrupt your subagents and the sessions you launched' in reason(out)
    assert 'If another agent launched this session, park any claim --waiting-on agent' in reason(out)
    assert d.state().paused == 'calls' and len(notices) == 1


@pytest.mark.parametrize('harness', ['claude-code', 'codex'])
def test_long_turn_continues_through_sixteen_hours_then_pauses(tmp_path, notices, harness):
    d = Driver(tmp_path, harness)
    d.prompt('execute the plan')
    assert d.bash('long-job') is None  # an in-flight call keeps the wait active
    assert d.bash('ls', dt=4 * 3600) is None
    out = d.bash('ls', dt=8 * 3600 - 1)
    assert context(out) == WARNING_TEXT.format(limit='active time', n=75, used='12h00m', value='16h00m')
    assert d.bash('ls', dt=4 * 3600) is None
    assert d.state().turn.active == 16 * 3600
    out = d.bash('ls', dt=1)
    assert denied(out) and d.state().paused == 'active'
    assert len(notices) == 1


def test_child_next_call_is_denied_with_the_child_text(tmp_path, notices):
    d = Driver(tmp_path, 'claude-code')
    d.pause_on_calls()
    out = d.bash('touch x', agent='a620dc1cd95e3a1c5')
    assert denied(out)
    assert reason(out).startswith(CHILD_TEXT.format(limit='calls'))
    assert 'stop the work you already started (your background calls and processes)' in reason(out)
    assert 'return a short status (done, left, running). Do not write a pause report.' in reason(out)


def test_paused_park_spends_no_grace_reads_stop_at_25_cancellation_stays(tmp_path, notices):
    d = Driver(tmp_path, 'claude-code')
    d.pause_on_calls()
    assert d.bash(PARK) is None
    assert d.state().grace_used.get('root', 0) == 0
    for i in range(25):
        out, _ = d.pre('Read', {'file_path': f'/srv/notes/{i}.md'})
        assert not denied(out), i
    assert d.state().grace_used['root'] == 25
    out, _ = d.pre('Read', {'file_path': '/srv/notes/26.md'})
    assert denied(out)
    assert not denied(d.pre('TaskStop', {'task_id': 'b7od2qy27'})[0])
    assert d.bash(PARK) is None


@pytest.mark.parametrize('harness', ['claude-code', 'codex'])
@pytest.mark.parametrize('reads', [0, 25])
def test_scoped_tasks_preserve_bookkeeping_and_read_grace(tmp_path, notices, harness, reads):
    d = Driver(tmp_path, harness)
    d.pause_on_calls()
    for _ in range(reads):
        assert not denied(d.bash('tasks -C .worktrees/task claims'))
    for command in ('park hq-123456 next', 'note hq-123456 paused'):
        assert d.bash(f'tasks -C .worktrees/task {command}') is None
    assert d.state().grace_used.get('root', 0) == reads
    assert denied(d.bash('tasks -C .worktrees/task claims')) == (reads == 25)
    assert denied(d.bash('tasks -C .worktrees/task show hq-123456'))
    assert denied(d.bash('tasks -C .worktrees/task start hq-123456'))
    assert denied(d.bash(f'tasks -C "{d.limits}" note hq-123456 paused'))


@pytest.mark.parametrize('harness', ['claude-code', 'codex'])
def test_paused_scoped_tasks_write_note_and_release_claim(tmp_path, notices, harness):
    tasks_cli = shutil.which('tasks')
    assert tasks_cli is not None, 'the tasks CLI is required for the closing-path test'
    d = Driver(tmp_path, harness)
    project = tmp_path / 'project worktree'
    project.mkdir()
    outside = tmp_path / 'outside'
    outside.mkdir()
    env = {'PATH': f'{Path(tasks_cli).parent}:/usr/bin:/bin', 'HOME': d.env['HOME'],
           'USER': 'fixture', 'XDG_CONFIG_HOME': str(tmp_path / 'config'),
           'XDG_STATE_HOME': d.env['XDG_STATE_HOME'], 'XDG_DATA_HOME': str(tmp_path / 'data'),
           'XDG_RUNTIME_DIR': d.env['XDG_RUNTIME_DIR'], 'TASKS_SESSION': 'pause-park-test',
           'TASKS_OWNER': 'fixture', 'GIT_CONFIG_GLOBAL': '/dev/null',
           'GIT_CONFIG_NOSYSTEM': '1', 'GIT_CEILING_DIRECTORIES': str(tmp_path)}

    def run(*args):
        result = subprocess.run(['tasks', '-C', str(project), *args], cwd=outside, env=env,
                                text=True, capture_output=True, timeout=15)
        assert result.returncode == 0, result.stdout + result.stderr
        return json.loads(result.stdout)

    run('init', '--prefix', 'pause')
    added = run('add', 'closing fixture', '--process', 'direct')
    tid = added.get('id') or added['task']['id']
    run('start', tid)
    assert run('show', tid)['claim']['live']
    d.pause_on_calls()
    for _ in range(25):
        assert not denied(d.bash('ls'))
    assert denied(d.bash('ls'))
    for args in [('note', tid, 'paused from another directory'),
                 ('park', tid, 'resume after review', '--waiting-on', 'user', '--reason', 'decision')]:
        command = shlex.join(['tasks', '-C', str(project), *args])
        assert d.bash(command) is None
        run(*args)
    shown = run('show', tid)
    assert any(n['text'] == 'paused from another directory' for n in shown['task']['notes'])
    assert not shown.get('claim', {}).get('live', False)
    assert d.state().grace_used['root'] == 25


@pytest.mark.parametrize('harness', ['claude-code', 'codex'])
def test_paused_long_tasks_note_persists_durable_handoff_after_grace_exhausted(tmp_path, notices, harness):
    tasks_cli = shutil.which('tasks')
    assert tasks_cli is not None, 'the tasks CLI is required for the closing-path test'
    d = Driver(tmp_path, harness)
    project = tmp_path / 'project worktree'
    project.mkdir()
    outside = tmp_path / 'outside'
    outside.mkdir()
    env = {'PATH': f'{Path(tasks_cli).parent}:/usr/bin:/bin', 'HOME': d.env['HOME'],
           'USER': 'fixture', 'XDG_CONFIG_HOME': str(tmp_path / 'config'),
           'XDG_STATE_HOME': d.env['XDG_STATE_HOME'], 'XDG_DATA_HOME': str(tmp_path / 'data'),
           'XDG_RUNTIME_DIR': d.env['XDG_RUNTIME_DIR'], 'TASKS_SESSION': 'pause-long-note-test',
           'TASKS_OWNER': 'fixture', 'GIT_CONFIG_GLOBAL': '/dev/null',
           'GIT_CONFIG_NOSYSTEM': '1', 'GIT_CEILING_DIRECTORIES': str(tmp_path)}

    def run(*args):
        result = subprocess.run(['tasks', '-C', str(project), *args], cwd=outside, env=env,
                                text=True, capture_output=True, timeout=15)
        assert result.returncode == 0, result.stdout + result.stderr
        return json.loads(result.stdout)

    run('init', '--prefix', 'pause')
    added = run('add', 'long pause handoff fixture', '--process', 'direct')
    tid = added.get('id') or added['task']['id']
    run('start', tid)
    d.pause_on_calls()
    for _ in range(25):
        assert not denied(d.bash('ls'))
    assert denied(d.bash('ls'))
    report = 'pause report: status, evidence, remaining work and custody — ' + ('detail ' * 919) + 'end'
    assert len(report) > 6000 and '\n' not in report
    note_args = ('note', tid, report, '--stamp')
    command = shlex.join(['tasks', '-C', str(project), *note_args])
    assert 4096 < len(command) <= 16384
    assert d.bash(command) is None
    run(*note_args)
    over_cmd = "tasks note " + tid + " '" + ('z' * 16384) + "'"
    over_out = d.bash(over_cmd)
    assert denied(over_out)
    assert 'split a longer pause report across multiple single-line tasks note calls' in reason(over_out)
    shown = run('show', tid)
    assert any(n['text'] == report for n in shown['task']['notes'])
    assert d.state().grace_used['root'] == 25


@pytest.mark.parametrize('harness, tool, tool_input, expected', [
    ('claude-code', 'Write', {'file_path': 'report.md', 'content': 'pause'}, 'tasks note'),
    ('claude-code', 'Edit', {'file_path': 'report.md', 'old_string': 'a', 'new_string': 'b'}, 'tasks note'),
    ('claude-code', 'NotebookEdit', {'notebook_path': 'report.ipynb'}, 'tasks note'),
    ('codex', 'apply_patch', {'command': '*** Begin Patch\n*** Add File: r.md\n+x\n*** End Patch'}, 'tasks note'),
    ('claude-code', 'AskUserQuestion', {'questions': [{'question': 'Continue?'}]}, 'closing message'),
    ('codex', 'request_user_input', {'questions': [{'question': 'Continue?'}]}, 'closing message'),
    ('codex', 'request_user_input_async', {'questions': [{'question': 'Continue?'}]}, 'closing message'),
])
def test_paused_write_and_question_denials_name_sanctioned_substitutes(
    tmp_path, notices, harness, tool, tool_input, expected
):
    d = Driver(tmp_path, harness)
    d.pause_on_calls()
    out, _ = d.pre(tool, tool_input)
    assert denied(out)
    text = reason(out)
    assert text.startswith('turn paused: calls over its limit')
    assert 'This call:' in text and expected in text
    assert text.endswith(OWNER_LINE)


@pytest.mark.parametrize('harness', ['claude-code', 'codex'])
@pytest.mark.parametrize('agent', [None, 'worker-1'])
@pytest.mark.parametrize('reads', [0, 25])
def test_paused_tasks_feedback_is_bookkeeping_for_root_and_child_at_any_grace(tmp_path, notices, harness, agent, reads):
    d = Driver(tmp_path, harness)
    d.pause_on_calls()
    session = agent or 'root'
    for _ in range(reads):
        assert not denied(d.bash('ls', agent=agent))
    for cmd in (
        'tasks feedback --project hq --category friction --origin user -b "single line detail" "wrong block"',
        'tasks -C .worktrees/task feedback --project hq --category friction --origin agent -b "detail" "wrong block"',
        'tasks -C "project worktree" feedback "wrong block" --project hq --category gap',
    ):
        assert d.bash(cmd, agent=agent) is None
    assert d.state().grace_used.get(session, 0) == reads
    assert d.state().paused == 'calls'
    assert denied(d.bash('ls', agent=agent)) == (reads == 25)
    assert denied(d.bash('tasks add "new work"', agent=agent))
    assert denied(d.bash('tasks -C .worktrees/task add "new work"', agent=agent))
    assert denied(d.bash('tasks feedback --project hq --category friction "msg" && ls', agent=agent))
    assert denied(d.bash(f'tasks feedback --project hq --category friction {shlex.quote(str(d.limits))}', agent=agent))
    assert denied(d.bash(f'tasks -C {shlex.quote(str(d.limits))} feedback --project hq --category friction "msg"',
                         agent=agent))
    assert d.state().paused == 'calls'


@pytest.mark.parametrize('harness', ['claude-code', 'codex'])
def test_paused_tasks_feedback_creates_isolated_record_after_grace_exhausted(tmp_path, notices, harness):
    tasks_cli = shutil.which('tasks')
    assert tasks_cli is not None, 'the tasks CLI is required for the closing-path test'
    d = Driver(tmp_path, harness)
    caller = tmp_path / 'caller worktree'
    owner = tmp_path / 'owner'
    outside = tmp_path / 'outside'
    for directory in (caller, owner, outside):
        directory.mkdir()
    env = {'PATH': f'{Path(tasks_cli).parent}:/usr/bin:/bin', 'HOME': d.env['HOME'],
           'USER': 'fixture', 'XDG_CONFIG_HOME': str(tmp_path / 'config'),
           'XDG_STATE_HOME': d.env['XDG_STATE_HOME'], 'XDG_DATA_HOME': str(tmp_path / 'data'),
           'XDG_RUNTIME_DIR': d.env['XDG_RUNTIME_DIR'], 'TASKS_SESSION': 'pause-feedback-test',
           'TASKS_OWNER': 'fixture', 'GIT_CONFIG_GLOBAL': '/dev/null',
           'GIT_CONFIG_NOSYSTEM': '1', 'GIT_CEILING_DIRECTORIES': str(tmp_path)}

    def run(cwd_target, *args):
        result = subprocess.run(['tasks', '-C', str(cwd_target), *args], cwd=outside, env=env,
                                text=True, capture_output=True, timeout=15)
        assert result.returncode == 0, result.stdout + result.stderr
        return json.loads(result.stdout)

    run(caller, 'init', '--prefix', 'src')
    run(owner, 'init', '--prefix', 'own')
    with (owner / 'tasks' / '.config.toml').open('a') as f:
        f.write('\n[feedback]\nscope = "Isolated pause feedback fixture."\n')
    d.pause_on_calls()
    for _ in range(25):
        assert not denied(d.bash('ls'))
    assert denied(d.bash('ls'))
    feedback_args = [
        'feedback', '--project', 'own', '--category', 'friction', '--origin', 'user',
        '-b', 'paused session filed feedback after grace exhausted',
        'closing allowlist blocked required tooling feedback',
    ]
    command = shlex.join(['tasks', '-C', str(caller), *feedback_args])
    assert d.bash(command) is None
    created = run(caller, *feedback_args)
    fid = created['id']
    assert created['action'] == 'created'
    records = list((owner / 'tasks').glob('*.md'))
    assert [p.name for p in records] == [f'{fid}.md']
    assert (tmp_path / 'config' / 'tasks' / 'projects.toml').is_file()
    shown = run(owner, 'show', fid)
    task = shown['task']
    assert task['status'] == 'idea'
    assert task['origin'] == 'user'
    assert {'feedback', 'friction', 'from:src'} <= set(task['tags'])
    assert 'paused session filed feedback after grace exhausted' in task['body']
    assert d.state().grace_used['root'] == 25
    assert d.state().paused == 'calls'


def test_continue_ends_the_pause_resets_counters_and_sets_no_budget(tmp_path, notices):
    d = Driver(tmp_path, 'claude-code')
    d.pause_on_calls()
    assert d.prompt('continue') is None
    st = d.state()
    assert st.paused is None and st.turn.calls == 0 and st.grace_used == {}
    assert st.turn.limits == load(d.limits)[0]
    assert st.budget_note is None and st.notified is False


@pytest.mark.parametrize('hours, calls, spawns, compactions', [(8, 1000, 30, 1), (12, 1500, 45, 2), (48, 6000, 180, 6)])
def test_budget_directive_scales_from_default(tmp_path, hours, calls, spawns, compactions):
    d = Driver(tmp_path, 'claude-code')
    out = d.prompt(f'budget: {hours}h\nRun the whole migration.')
    assert context(out) == BUDGET_TEXT.format(a=f'{hours}h00m', c=calls, s=spawns, k=compactions)
    assert d.state().turn.limits == Limits(hours * 3600, calls, spawns, compactions)


def test_malformed_budget_adds_its_context_once(tmp_path):
    d = Driver(tmp_path, 'claude-code')
    text = 'budget: soon\nRun the whole migration.'
    bad = parse_budget(text)
    assert isinstance(bad, Malformed)
    assert context(d.prompt(text)) == MALFORMED_TEXT.format(reason=bad.reason)
    assert d.state().turn.limits == load(d.limits)[0]
    assert d.bash('ls') is None


@pytest.mark.parametrize('zero', ['spawns', 'compactions', 'calls', 'active_seconds'])
def test_a_zero_limit_never_raises_on_a_pre_tool_use(tmp_path, zero):
    d = Driver(tmp_path, 'claude-code')
    d.prompt('work')
    with d.store.locked('claude-code', CLAUDE_ROOT) as record:
        rs = record.state
        rs.turn.limits = Limits(**{**rs.turn.limits._asdict(), zero: 0})
    out = d.bash('ls')
    assert 'could not judge' not in (reason(out) if denied(out) else '')


def test_budget_examples_in_a_spec_body_add_nothing(tmp_path):
    d = Driver(tmp_path, 'claude-code')
    body = ('Review this spec.\n\n```\nbudget: 10h, 2000 calls\n```\n> budget: 3h\n'
            'A line like budget: 12h sets the limits.\nbudget: 2h\n')
    assert d.prompt(body) is None
    assert d.state().turn.limits == load(d.limits)[0]


def test_changed_limits_file_pauses_with_limits_changed_and_notifies(tmp_path, notices):
    d = Driver(tmp_path, 'claude-code')
    d.prompt('work')
    assert d.bash('ls') is None
    write_limits(d.limits, calls=5000)
    out = d.bash('ls')
    assert denied(out)
    assert reason(out) == (
        LIMITS_CHANGED_TEXT.format(a='0h00m', A='16h00m', c=2, C=2000, s=0, S=60, k=0, K=2)
        + f'\n{OWNER_LINE}'
    )
    assert reason(out).startswith('turn paused: the turn limits file changed mid-turn (active 0h00m of 16h00m, '
                                  'root calls 2/2000, tree spawns 0/60, root compactions 0/2 (advisory)). Start nothing new and stop')
    assert d.state().paused == 'limits-changed'
    assert len(notices) == 1
    assert denied(d.bash('touch y'))
    assert len(notices) == 1


@pytest.mark.parametrize('target', ['limits', 'state', 'wiring', 'home-link', 'facts'])
def test_a_call_naming_a_protected_path_is_denied_before_any_pause(tmp_path, target):
    d = Driver(tmp_path, 'claude-code')
    d.prompt('work')
    path = {'limits': d.limits,
            'state': state_dir(d.env) / f'claude-code-{CLAUDE_ROOT}.json',
            'wiring': CHECKOUT / 'harnesses/codex/hooks.json',
            'home-link': Path(d.env['HOME']) / '.claude' / 'settings.json',
            'facts': Path(adapters.SNAPSHOT)}[target]
    out, _ = d.pre('Edit', {'file_path': str(path), 'old_string': '500', 'new_string': '5000'})
    assert denied(out)
    assert 'protected' in reason(out)
    assert d.state().paused is None


@pytest.mark.parametrize('harness', ['claude-code', 'codex'])
@pytest.mark.parametrize('paused', [False, True])
def test_protected_bash_read_accepts_real_metadata_and_spends_grace(tmp_path, notices, harness, paused):
    d = Driver(tmp_path, harness)
    if paused:
        d.pause_on_calls()
    else:
        d.prompt('inspect configuration')
    data = dict(fixture('claude-code-subagent-bash-denied.json', 'PreToolUse', 'Bash')['tool_input'])
    data.update(command='cat ' + shlex.quote(str(d.limits)), timeout=1000)
    count = 25 if paused else 1
    for _ in range(count):
        out, _ = d.pre('Bash', data)
        assert not denied(out)
    assert d.state().paused == ('calls' if paused else None)
    if paused:
        assert d.state().grace_used['root'] == 25
        assert denied(d.pre('Bash', data)[0])


@pytest.mark.parametrize('tool,operand', [('Read', 'file_path'), ('Grep', 'pattern'), ('Glob', 'pattern')])
def test_protected_native_read_allows_inspection_without_clearing_pause(tmp_path, notices, tool, operand):
    d = Driver(tmp_path, 'claude-code')
    d.pause_on_calls()
    data = {operand: str(d.limits)}
    if tool == 'Grep':
        data['path'] = str(d.limits)
    assert not denied(d.pre(tool, data)[0])
    assert d.state().paused == 'calls' and d.state().grace_used['root'] == 1


@pytest.mark.parametrize('command', ['touch {path}', 'cat {path} > /srv/out',
                                    'tasks attach hq-123456 {path}', 'tasks note hq-123456 {path}',
                                    'cat {path}; touch /srv/out'])
def test_protected_side_effects_stay_denied(tmp_path, command):
    d = Driver(tmp_path, 'codex')
    d.prompt('inspect')
    assert denied(d.bash(command.format(path=shlex.quote(str(d.limits)))))


def test_state_error_is_a_deny_naming_the_state_file(tmp_path):
    d = Driver(tmp_path, 'claude-code')
    d.prompt('work')
    path = state_dir(d.env) / f'claude-code-{CLAUDE_ROOT}.json'
    path.write_text('{not json')
    out = d.bash('ls')
    assert denied(out)
    assert str(path) in reason(out)


def test_refused_call_then_a_three_hour_gap_adds_no_active_time(tmp_path):
    d = Driver(tmp_path, 'claude-code')
    d.prompt('work')
    out, _ = d.pre('Edit', {'file_path': str(d.limits), 'old_string': 'a', 'new_string': 'b'}, dt=10)
    assert denied(out)
    assert d.bash('ls', dt=3 * 3600) is None
    assert d.state().turn.active == 10


def test_claude_spawn_counts_at_the_allowed_agent_call_and_subagent_start_only_records(tmp_path, notices):
    d = Driver(tmp_path, 'claude-code')
    d.prompt('work')
    agent = fixture('claude-code-subagent-bash-denied.json', 'PreToolUse', 'Agent')
    assert d('PreToolUse', agent) is None
    start = fixture('claude-code-subagent-bash-denied.json', 'SubagentStart')
    d('SubagentStart', start)
    d('SubagentStart', start)
    st = d.state()
    assert st.turn.spawns == 1 and st.turn.spawn_keys == {agent['tool_use_id']}
    assert start['agent_id'] in st.workers


def test_claude_refused_agent_call_spawns_nothing(tmp_path, notices):
    d = Driver(tmp_path, 'claude-code')
    d.pause_on_calls()
    agent = fixture('claude-code-subagent-bash-denied.json', 'PreToolUse', 'Agent')
    assert denied(d('PreToolUse', agent))
    assert d.state().turn.spawns == 0


# --- Codex ----------------------------------------------------------------------------

@pytest.mark.parametrize('harness', ['claude-code', 'codex'])
@pytest.mark.parametrize('worker', [False, True])
def test_default_spawns_warn_at_45_allow_60_then_pause_after_61(tmp_path, notices, harness, worker):
    d = Driver(tmp_path, harness)
    d.prompt('fan out')
    for i in range(61):
        agent = 'parent-worker' if worker else None
        if harness == 'codex':
            pre = codex_spawn(f'w{i}', d.call_id(), agent=agent)
        else:
            data = fixture('claude-code-subagent-bash-denied.json', 'PreToolUse', 'Agent')['tool_input']
            pre = claude_pre('Agent', data, d.call_id(), agent=agent)
        out = d('PreToolUse', pre)
        assert not denied(out), i
        if i == 45:
            assert context(out) == WARNING_TEXT.format(limit='tree spawns', n=75, used=45, value=60)
        if harness == 'codex':
            d('SubagentStart', codex_subagent_start(f'01a19708-0000-0000-0000-{i:012d}'))
        if i == 59:
            assert d.state().turn.spawns == 60 and d.state().paused is None
    st = d.state()
    assert st.turn.calls == (0 if worker else 61) and st.turn.spawns == 61
    out = d.bash('ls', agent='01a19708-0000-0000-0000-000000000003')
    assert denied(out)
    assert d.state().paused == 'spawns'


def test_codex_spawn_without_subagent_start_or_refused_adds_no_spawn(tmp_path, notices):
    d = Driver(tmp_path, 'codex')
    d.prompt('fan out')
    pre = codex_spawn('w0', d.call_id())
    assert not denied(d('PreToolUse', pre))
    d('PostToolUse', post(pre, '{"task_name":"/root/w0"}'))
    assert d.state().turn.spawns == 0
    d('SubagentStart', codex_subagent_start('01a19708-33c7-7081-8565-d4e918bd4284'))
    d('SubagentStart', codex_subagent_start('01a19708-33c7-7081-8565-d4e918bd4284'))
    assert d.state().turn.spawns == 1


def test_codex_spawn_refused_while_paused_adds_no_spawn_or_name(tmp_path, notices):
    d = Driver(tmp_path, 'codex')
    d.pause_on_calls()
    assert denied(d('PreToolUse', codex_spawn('late', d.call_id())))
    st = d.state()
    assert st.turn.spawns == 0 and 'late' not in st.worker_names


def test_codex_yielded_bash_stays_in_flight_until_stop_and_late_post_adds_nothing(tmp_path):
    d = Driver(tmp_path, 'codex')
    d.prompt('run the server')
    out, pre = d.pre('Bash', {'command': 'sleep 30; echo late'}, dt=10)
    assert out is None
    d('Stop', codex_bare('Stop', stop_hook_active=False), dt=3 * 3600)
    st = d.state()
    assert st.turn.active == 10 + 3 * 3600 and st.turn.in_flight == {}
    d.prompt('next thing', dt=60)
    d('PostToolUse', post(pre), dt=3600)
    st = d.state()
    assert st.turn.active == 0 and st.turn.calls == 0 and st.turn.in_flight == {}


def test_claude_call_without_a_post_is_closed_when_the_agent_starts_a_user_wait(tmp_path):
    """A call another hook refused gets no PostToolUse; the question after it is not work."""
    d = Driver(tmp_path, 'claude-code')
    d.prompt('work')
    out, _ = d.pre('Bash', {'command': 'ls'}, dt=10)
    assert out is None
    out, ask = d.pre('AskUserQuestion', {'questions': []}, dt=3)
    assert out is None and d.state().turn.in_flight == {}
    d('PostToolUse', post(ask), dt=5 * 3600)
    assert d.state().turn.active == 13


def test_a_five_hour_plan_approval_wait_adds_no_active_time(tmp_path):
    d = Driver(tmp_path, 'claude-code')
    d.prompt('work')
    out, plan = d.pre('ExitPlanMode', {'plan': 'x'}, dt=10)
    assert out is None and d.state().turn.in_flight == {}
    d('PostToolUse', post(plan), dt=5 * 3600)
    assert d.bash('ls') is None
    assert d.state().turn.active == 11


def test_codex_user_wait_keeps_a_yielded_bash_open_and_the_wait_counts(tmp_path):
    d = Driver(tmp_path, 'codex')
    d.prompt('run the server')
    out, bash = d.pre('Bash', {'command': 'sleep 30'}, dt=10)
    assert out is None
    out, ask = d.pre('request_user_input', {'questions': []}, dt=3)
    assert out is None and list(d.state().turn.in_flight) == [bash['tool_use_id']]
    d('PostToolUse', post(ask), dt=2 * 3600)
    assert d.state().turn.active == 13 + 2 * 3600


def test_codex_user_wait_closes_an_open_call_that_is_not_bash(tmp_path):
    d = Driver(tmp_path, 'codex')
    d.prompt('work')
    d.pre('apply_patch', {'input': 'x'}, dt=10)
    out, _ = d.pre('request_user_input', {'questions': []}, dt=3)
    assert out is None and d.state().turn.in_flight == {}


def test_a_user_wait_leaves_another_agents_open_call_open(tmp_path):
    d = Driver(tmp_path, 'claude-code')
    d.prompt('work')
    _, sub = d.pre('Bash', {'command': 'make long'}, agent='sub1', dt=10)
    d.pre('Bash', {'command': 'ls'}, dt=1)
    d.pre('AskUserQuestion', {'questions': []}, dt=1)
    assert list(d.state().turn.in_flight) == [sub['tool_use_id']]


def test_codex_paused_update_goal_passes_only_as_status_paused(tmp_path, notices):
    d = Driver(tmp_path, 'codex')
    d.pause_on_calls()
    assert not denied(d.pre('update_goal', {'status': 'paused'})[0])
    assert denied(d.pre('update_goal', {'status': 'complete'})[0])


def test_codex_worker_spawn_records_its_full_path_and_bare_name(tmp_path):
    d = Driver(tmp_path, 'codex')
    d.prompt('fan out')
    pre = codex_spawn('w1', d.call_id(), agent='01a19708-33c7-7081-8565-d4e918bd4284')
    assert not denied(d('PreToolUse', pre))
    d('PostToolUse', post(pre, '{"task_name":"/root/w0/w1"}'))
    assert {'w1', '/root/w0/w1'} <= d.state().worker_names
    assert '/root/w1' not in d.state().worker_names


def test_codex_spawn_names_from_fixture_let_a_paused_interrupt_pass(tmp_path, notices):
    d = Driver(tmp_path, 'codex')
    d.prompt('fan out')
    pre = fixture('codex-spawn_agent.json', 'PreToolUse', 'collaborationspawn_agent')
    after = fixture('codex-spawn_agent.json', 'PostToolUse', 'collaborationspawn_agent')
    for p in (pre, after):
        p['session_id'] = CODEX_ROOT
    d('PreToolUse', pre)
    d('PostToolUse', after)
    assert {'w0', '/root/w0'} <= d.state().worker_names
    write_limits(d.limits, calls=1)
    d.prompt('next')
    d.bash('ls')
    assert denied(d.bash('ls'))
    interrupt = fixture('codex-interrupt_agent.json', 'PreToolUse', 'collaborationinterrupt_agent')
    interrupt['session_id'] = CODEX_ROOT
    for target in ('w0', '/root/w0'):
        interrupt['tool_input'] = {'target': target}
        assert not denied(d('PreToolUse', interrupt)), target
    interrupt['tool_input'] = {'target': 'probe_worker'}
    assert denied(d('PreToolUse', interrupt))


def test_codex_nested_calls_count_each_and_are_judged_alone(tmp_path, notices):
    d = Driver(tmp_path, 'codex')
    write_limits(d.limits, calls=3)
    d.prompt('edit things')
    assert d.bash('ls') is None
    assert not denied(d.bash('cat a'))  # 3/4 of 3 calls warns
    assert not denied(d.pre('apply_patch', {'command': '*** Begin Patch\n*** End Patch\n'})[0])
    assert d.state().turn.calls == 3
    assert denied(d.bash('ls'))
    assert d.bash(PARK) is None
    assert denied(d.pre('apply_patch', {'command': '*** Begin Patch\n*** End Patch\n'})[0])


# --- Claude Code compaction -----------------------------------------------------------

def test_claude_compaction_counts_once_and_the_summarizer_stop_changes_nothing(tmp_path):
    d = Driver(tmp_path, 'claude-code')
    d.prompt('work')
    _, child = d.pre('Bash', {'command': 'sleep 100'}, agent='a620dc1cd95e3a1c5')
    workers = set(d.state().workers)
    assert d('PreCompact', claude_bare('PreCompact', trigger='manual', custom_instructions=None)) is None
    assert d('SubagentStop', claude_bare('SubagentStop', agent_id='af9a844781e1df4ba', agent_type='',
                                         stop_hook_active=False, background_tasks=[], session_crons=[])) is None
    assert d('PostCompact', claude_bare('PostCompact', trigger='manual', compact_summary='...')) is None
    st = d.state()
    assert st.turn.compactions == 1
    assert st.workers == workers and child['tool_use_id'] in st.turn.in_flight


def test_claude_third_compaction_warns_once_as_advisory_and_never_pauses(tmp_path, notices):
    d = Driver(tmp_path, 'claude-code')
    d.prompt('work')
    for _ in range(2):
        assert d('PostCompact', claude_bare('PostCompact', trigger='auto', compact_summary='...')) is None
    out = d.bash('ls')
    assert not denied(out)
    assert context(out) == COMPACTION_WARNING_TEXT.format(used=2, value=2)
    assert d('PostCompact', claude_bare('PostCompact', trigger='auto', compact_summary='...')) is None
    out = d.bash('ls')
    assert out is None
    st = d.state()
    assert st.turn.compactions == 3 and st.paused is None and notices == []
    record = d.store.read_record('claude-code', d.root)
    assert [e['kind'] for e in record.events] == ['turn_start', 'warning']
    assert record.events[1]['reason'] == 'compactions'


# --- notification and state -----------------------------------------------------------

def test_notify_failure_is_stored_and_the_pause_stands(tmp_path):
    d = Driver(tmp_path, 'claude-code', notify_send=False)
    d.pause_on_calls()
    st = d.state()
    assert st.paused == 'calls' and st.notified is True
    assert 'notify-send' in st.notify_error
    assert denied(d.bash('touch x'))


def test_pause_notifies_once_through_notify_send(tmp_path):
    d = Driver(tmp_path, 'claude-code')
    d.pause_on_calls()
    denied(d.bash('ls'))
    log = tmp_path / 'bin' / 'notify-send.log'
    for _ in range(100):
        if log.exists() and log.read_text():
            break
        time.sleep(0.02)
    assert 'calls' in log.read_text()
    assert d.state().notify_error is None
    time.sleep(0.2)
    assert log.read_text().count('turn paused') == 1


def test_session_end_removes_the_root_state(tmp_path):
    d = Driver(tmp_path, 'claude-code')
    d.prompt('work')
    assert d.state() is not None
    assert d('SessionEnd', claude_bare('SessionEnd', reason='other')) is None
    assert d.state() is None


def test_history_late_scheduled_wake_cannot_resume_after_session_end(tmp_path):
    """The captured wake is ordinary prompt text with no provenance marker."""
    d = Driver(tmp_path, 'claude-code')
    d.prompt('work')
    wake = fixture('claude-code-ScheduleWakeup.json', 'UserPromptSubmit')
    text = wake['prompt']
    d('Stop', claude_stop([{'id': 'portable-wake', 'prompt': text}]))
    before = d.state()
    assert engine.prompt_kind(before, d.harness, text, d.t, None) == 'wake'
    d('SessionEnd', claude_bare('SessionEnd', reason='other'))
    assert d.state() is None
    d('UserPromptSubmit', wake)
    assert d.state() is None, 'a late unmarked wake must not create a new human turn'


@pytest.mark.parametrize('harness', ['claude-code', 'codex'])
@pytest.mark.parametrize('implicit', [False, True])
def test_history_initial_turn_and_reset(tmp_path, harness, implicit):
    d = Driver(tmp_path, harness)
    d.bash('ls') if implicit else d.prompt('work')
    record = d.store.read_record(harness, d.root)
    assert record.turn_serial == 1
    assert [(e['kind'], e['reason']) for e in record.events] == [
        ('turn_start', 'implicit' if implicit else 'genuine_user')]
    d.prompt('next')
    record = d.store.read_record(harness, d.root)
    assert record.turn_serial == 2
    assert [e['kind'] for e in record.events] == ['turn_start', 'turn_reset', 'turn_start']
    assert record.events[1]['snapshot']['calls']['used'] == int(implicit)


@pytest.mark.parametrize('harness,metric,value', [('codex', 'active', 43200), ('codex', 'calls', 1500),
                                                ('codex', 'spawns', 45), ('claude-code', 'compactions', 2)])
def test_history_first_warning_only(tmp_path, harness, metric, value):
    d = Driver(tmp_path, harness)
    d.prompt('work')
    with d.store.locked(harness, d.root) as record:
        setattr(record.state.turn, metric, value)
    d.bash('ls')
    d.bash('ls')
    record = d.store.read_record(harness, d.root)
    warnings = [e for e in record.events if e['kind'] == 'warning']
    assert len(warnings) == 1 and warnings[0]['reason'] == metric


@pytest.mark.parametrize('harness,metric,value', [('codex', 'active', 57601), ('codex', 'calls', 2000),
    ('codex', 'spawns', 61), ('codex', 'limits-changed', 0)])
def test_history_pause_transition_is_atomic_and_not_repeated(tmp_path, harness, metric, value):
    d = Driver(tmp_path, harness)
    d.prompt('work')
    if metric == 'limits-changed':
        d.limits.write_text(d.limits.read_text() + '\n# changed\n')
    else:
        with d.store.locked(harness, d.root) as record:
            setattr(record.state.turn, metric, value)
    assert denied(d.bash('touch /srv/x'))
    assert denied(d.bash('touch /srv/x'))
    record = d.store.read_record(harness, d.root)
    pauses = [e for e in record.events if e['kind'] == 'enforced_pause']
    assert len(pauses) == 1 and pauses[0]['reason'] == metric == record.state.paused
    assert pauses[0]['notification']['outcome'] == 'pending'
    notice = [e for e in record.events if e['kind'] == 'notification']
    assert len(notice) == 1 and notice[0]['notification']['receipt'] == 'unknown'


@pytest.mark.parametrize('end', [False, True])
def test_history_notification_after_reset_or_end_names_original_turn(tmp_path, monkeypatch, end):
    d = Driver(tmp_path, 'claude-code')
    def deliver(*args, **kwargs):
        if end:
            d('SessionEnd', claude_bare('SessionEnd'))
        else:
            d.prompt('new human turn')
        return 'PRIVATE_NOTIFY_ERROR'
    monkeypatch.setattr(notify, 'send', deliver)
    d.pause_on_calls()
    record = d.store.read_record(d.harness, d.root)
    event = record.events[-1]
    assert event['kind'] == 'notification' and event['turn'] == 1
    assert event['notification']['error_code'] == 'notify_failed'
    assert 'PRIVATE_NOTIFY_ERROR' not in json.dumps(record.events)
    assert record.state is None if end else record.state.notify_error is None


@pytest.mark.parametrize('replace', [False, True])
def test_history_notification_missing_generation_does_not_resurrect(tmp_path, monkeypatch, capsys, replace):
    d = Driver(tmp_path, 'codex')
    def deliver(*args, **kwargs):
        d.store.remove(d.harness, d.root)
        if replace:
            d.prompt('new generation')
        return 'PRIVATE_NOTIFY_ERROR'
    monkeypatch.setattr(notify, 'send', deliver)
    d.pause_on_calls()
    record = d.store.read_record(d.harness, d.root)
    assert (record is None) if not replace else all(e['kind'] != 'notification' for e in record.events)
    assert 'unknown' in capsys.readouterr().err


@pytest.mark.parametrize('harness', ['claude-code', 'codex'])
@pytest.mark.parametrize('idle', [False, True])
def test_history_ended_guards_restart_resume_and_worker_isolation(tmp_path, harness, idle):
    from turn_pause.state import Wakeup
    d = Driver(tmp_path, harness)
    d.prompt('work')
    with d.store.locked(harness, d.root) as record:
        record.state.cron_jobs = {'cron': 'known cron'}
        record.state.wakeups = [Wakeup('one shot', d.t, d.t + 100)]
    maker = claude_bare if harness == 'claude-code' else codex_bare
    if idle:
        path = Path(d.store.dir) / f'{harness}-{d.root}.json'
        os.utime(path, (d.t - 8 * 86400, d.t - 8 * 86400))
        d.store.prune(d.t, compactions_counted={'claude-code': True, 'codex': False})
    else:
        d('SessionEnd', maker('SessionEnd'))
    d.store = Store(d.store.dir)
    before = d.store.read_record(harness, d.root)
    assert before.state is None and before.prompt_guards['wakeups']
    d('UserPromptSubmit', maker('UserPromptSubmit', prompt='one shot', agent_id='worker'))
    d.prompt('<system-reminder>one shot</system-reminder>')
    assert d.store.read_record(harness, d.root).prompt_guards == before.prompt_guards
    assert context(d.prompt('one shot')) == WAKE_TEXT
    assert context(d.prompt('known cron')) == WAKE_TEXT
    assert denied(d.bash('ls', agent='worker'))
    ended = d.store.read_record(harness, d.root)
    assert ended.state is None and ended.turn_serial == 1 and ended.ended_at == before.ended_at
    d.prompt('different genuine prompt')
    resumed = d.store.read_record(harness, d.root)
    assert resumed.state is not None and resumed.turn_serial == 2 and resumed.ended_at is None
    assert resumed.prompt_guards == {'cron': [], 'wakeups': []}
    assert [e['kind'] for e in resumed.events][-2:] == ['turn_resume', 'turn_start']


def test_history_directory_fsync_failure_keeps_committed_pause_unknown(tmp_path, monkeypatch):
    import stat
    d = Driver(tmp_path, 'codex')
    d.prompt('work')
    with d.store.locked(d.harness, d.root) as record:
        record.state.turn.calls = 2000
    real = os.fsync
    def fail_directory(fd):
        if stat.S_ISDIR(os.fstat(fd).st_mode):
            raise OSError('synthetic directory fsync failure')
        real(fd)
    monkeypatch.setattr(os, 'fsync', fail_directory)
    assert denied(d.bash('ls'))
    record = d.store.read_record(d.harness, d.root)
    assert record.state.paused == 'calls'
    assert record.events[-1]['kind'] == 'enforced_pause'
    assert record.events[-1]['notification']['outcome'] == 'pending'


@pytest.mark.parametrize('end_first', [False, True])
def test_history_end_resume_guards_commit_in_serial_order(tmp_path, monkeypatch, end_first):
    from contextlib import contextmanager
    d = Driver(tmp_path, 'codex')
    d.prompt('work')
    with d.store.locked(d.harness, d.root) as record:
        record.state.cron_jobs = {'job': 'known cron'}
    acquired, proceed = threading.Event(), threading.Event()
    real = d.store._flocked
    @contextmanager
    def ordered(stem):
        with real(stem) as lock:
            if threading.current_thread().name == 'winner' and stem == f'{d.harness}-{d.root}':
                acquired.set()
                assert proceed.wait(5)
            yield lock
    monkeypatch.setattr(d.store, '_flocked', ordered)
    failures = []
    def run(ending):
        try:
            d('SessionEnd', codex_bare('SessionEnd')) if ending else d.prompt('new human prompt')
        except Exception as error:
            failures.append(error)
    first = threading.Thread(name='winner', target=run, args=(end_first,))
    second = threading.Thread(name='second', target=run, args=(not end_first,))
    first.start()
    assert acquired.wait(5)
    second.start()
    proceed.set()
    first.join(5); second.join(5)
    assert not first.is_alive() and not second.is_alive() and not failures
    record = d.store.read_record(d.harness, d.root)
    assert record.turn_serial == 2
    if end_first:
        assert record.state is not None and record.prompt_guards == {'cron': [], 'wakeups': []}
    else:
        assert record.state is None and len(record.prompt_guards['cron']) == 1


def test_measurement_call_honors_entry_site_disabled_startup(tmp_path):
    from measure_turn_pause import NATIVE_ROOTS, NATIVE_WORKERS, call, measure, native_call_id
    env = make_env(tmp_path)
    probe = tmp_path / 'site-probe'
    probe.mkdir()
    (probe / 'sitecustomize.py').write_text("raise RuntimeError('SITE_STARTUP_MUST_BE_DISABLED')\n")
    env['PYTHONPATH'] = str(probe)
    elapsed = call('claude-code', 'PreToolUse', claude_pre('Bash', {'command': 'ls'}, 'c1'),
                   DEFAULTS_PATH, env)
    assert elapsed > 0
    assert all(len(root) == 36 for roots in NATIVE_ROOTS.values() for root in roots)
    assert len(NATIVE_WORKERS['claude-code'][0]) == 17 and len(NATIVE_WORKERS['codex'][0]) == 36
    assert len(native_call_id('claude-code', NATIVE_ROOTS['claude-code'][0], False, 0)) == 30
    assert len(native_call_id('codex', NATIVE_ROOTS['codex'][0], True, 0)) == 41
    case = measure('claude-code', False, 1, tmp_path)
    assert case['counts'][0]['root'] == NATIVE_ROOTS['claude-code'][0]
    assert case['counts'][0]['calls'] == 1 and case['counts'][0]['events'] == 128


def test_post_tool_use_failure_closes_the_call(tmp_path):
    d = Driver(tmp_path, 'claude-code')
    d.prompt('work')
    _, pre = d.pre('Bash', {'command': 'false'})
    d('PostToolUseFailure', post(pre, event='PostToolUseFailure'))
    assert d.state().turn.in_flight == {}


# --- engine and adapters --------------------------------------------------------------

def _rs():
    limits, sha = load(DEFAULTS_PATH)
    return RootState('claude-code', CLAUDE_ROOT, TurnState(started=T0, limits=limits, limits_sha=sha, last_t=T0))


def test_feed_refused_call_is_not_in_flight_and_spawns_nothing():
    rs = _rs()
    events = [Event(T0 + 5, None, 'tool_start', call_id='c1', tool='Agent'),
              Event(T0 + 5, None, 'spawn', key='c1')]
    no = engine.Decision(allow=False, output={'x': 1}, paused=None)
    assert engine.feed(rs, events, lambda rs, ev: no) is no
    assert rs.turn.calls == 1 and rs.turn.spawns == 0 and rs.turn.in_flight == {}
    yes = engine.Decision(allow=True, output=None, paused=None)
    events = [Event(T0 + 6, None, 'tool_start', call_id='c2', tool='Agent'),
              Event(T0 + 6, None, 'spawn', key='c2')]
    assert engine.feed(rs, events, lambda rs, ev: yes) is yes
    assert rs.turn.calls == 2 and rs.turn.spawns == 1 and rs.turn.in_flight == {'c2': None}


def test_normalize_spawn_sources():
    facts = adapters.load_facts()
    pre = fixture('claude-code-subagent-bash-denied.json', 'PreToolUse', 'Agent')
    root, events = adapters.normalize('claude-code', 'PreToolUse', pre, T0, facts)
    assert root == pre['session_id']
    assert [(e.kind, e.key) for e in events] == [('tool_start', None), ('spawn', pre['tool_use_id'])]
    start = fixture('claude-code-subagent-bash-denied.json', 'SubagentStart')
    assert [e.kind for e in adapters.normalize('claude-code', 'SubagentStart', start, T0, facts)[1]] == ['tick']
    spawn = fixture('codex-spawn_agent.json', 'PreToolUse', 'collaborationspawn_agent')
    assert [e.kind for e in adapters.normalize('codex', 'PreToolUse', spawn, T0, facts)[1]] == ['tool_start']
    cstart = fixture('codex-spawn_agent.json', 'SubagentStart')
    root, events = adapters.normalize('codex', 'SubagentStart', cstart, T0, facts)
    assert root == cstart['session_id']
    assert [(e.kind, e.key) for e in events] == [('spawn', cstart['agent_id'])]
    worker = fixture('codex-worker-bash-denied.json', 'PreToolUse', 'Bash')
    root, events = adapters.normalize('codex', 'PreToolUse', worker, T0, facts)
    assert root == worker['session_id'] and events[0].agent == worker['agent_id']
    summarizer = claude_bare('SubagentStop', agent_id='af9a844781e1df4ba', agent_type='',
                             stop_hook_active=False, background_tasks=[], session_crons=[])
    assert adapters.normalize('claude-code', 'SubagentStop', summarizer, T0, facts)[1] == []
    assert adapters.normalize('claude-code', 'PreCompact', claude_bare('PreCompact', trigger='manual'), T0, facts)[1] == []
    assert [e.kind for e in adapters.normalize('claude-code', 'PostCompact', claude_bare('PostCompact', trigger='manual'), T0, facts)[1]] == ['compact']


def _facts_module():
    import importlib.machinery
    import importlib.util
    loader = importlib.machinery.SourceFileLoader('harness_facts', str(TOOLS / 'harness-facts'))
    spec = importlib.util.spec_from_loader('harness_facts', loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def test_facts_snapshot_equals_what_harness_facts_reads_now():
    """The hook reads a checked-in snapshot, not the fact file; it must stay equal to the
    lookups. Regenerate after a facts edit with: tools/turn-pause --write-facts-snapshot"""
    module = _facts_module()

    def value(name, harness):
        entry = module.lookup(name, harness)
        return entry['value'] if entry['status'] == 'probed' else None

    want = adapters.Facts(
        posttooluse={h: value('hook-posttooluse', h) for h in adapters.HARNESSES},
        stop_carries_agent={h: value('hook-stop-carries-agent', h) for h in adapters.HARNESSES},
        compact_events={h: None if value('hook-compact-event', h) is None else frozenset(value('hook-compact-event', h))
                        for h in adapters.HARNESSES})
    assert adapters.load_facts() == want, (
        f'{adapters.SNAPSHOT} differs from tools/harness-facts; regenerate it with: tools/turn-pause --write-facts-snapshot')
    assert want.compact_events == {'claude-code': frozenset({'PreCompact', 'PostCompact'}), 'codex': None}


def test_write_facts_snapshot_regenerates_the_file(tmp_path):
    target = tmp_path / 'facts.json'
    r = subprocess.run([str(ENTRY), '--write-facts-snapshot', str(target)], env=make_env(tmp_path),
                       capture_output=True, timeout=20)
    assert r.returncode == 0, r.stderr
    assert target.read_bytes() == Path(adapters.SNAPSHOT).read_bytes()


def test_the_hook_keeps_nothing_but_state_in_the_state_dir(tmp_path):
    d = Driver(tmp_path, 'claude-code')
    d.prompt('work')
    d.bash('ls')
    assert sorted(p.name for p in state_dir(d.env).iterdir()) == [f'claude-code-{CLAUDE_ROOT}.json',
                                                                  f'claude-code-{CLAUDE_ROOT}.lock']


def test_unknown_posttooluse_keeps_a_call_in_flight_until_the_agents_next_event():
    facts = adapters.Facts(posttooluse={'claude-code': None, 'codex': None},
                           stop_carries_agent={'claude-code': True, 'codex': True},
                           compact_events={'claude-code': None, 'codex': None})
    pre = claude_pre('Bash', {'command': 'ls'}, 'c9', agent='a1')
    _, events = adapters.normalize('claude-code', 'PreToolUse', pre, T0, facts)
    assert [(e.kind, e.agent) for e in events] == [('agent_stop', 'a1'), ('tool_start', 'a1')]
    _, events = adapters.normalize('claude-code', 'PostCompact', claude_bare('PostCompact', trigger='manual'), T0, facts)
    assert [e.kind for e in events] == ['tick']


# --- notify ---------------------------------------------------------------------------

class Relay:
    """A fake relay serve on $XDG_STATE_HOME/relay/serve.sock answering one request."""

    def __init__(self, env, reply):
        self.path = Path(env['XDG_STATE_HOME']) / 'relay' / 'serve.sock'
        self.path.parent.mkdir(parents=True)
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.bind(str(self.path))
        self.sock.listen(1)
        self.requests = []
        self.reply = reply
        self.thread = threading.Thread(target=self._serve, daemon=True)
        self.thread.start()

    def _serve(self):
        conn, _ = self.sock.accept()
        with conn:
            data = b''
            while not data.endswith(b'\n'):
                chunk = conn.recv(65536)
                if not chunk:
                    break
                data += chunk
            req = json.loads(data)
            self.requests.append(req)
            if self.reply is not None:
                conn.sendall((json.dumps(self.reply(req)) + '\n').encode())
            else:
                time.sleep(1.5)

    def close(self):
        self.thread.join(3)
        self.sock.close()


def _wait_for(path):
    for _ in range(150):
        if path.exists() and path.read_text():
            return path.read_text()
        time.sleep(0.02)
    raise AssertionError(f'{path} never written')


def test_notify_send_starts_notify_send_and_sends_a_relay_notice(tmp_path):
    env = make_env(tmp_path)
    relay = Relay(env, lambda req: {'reqId': req['reqId'], 'ok': True, 'entry': {}})
    assert notify.send('Turn paused (calls)', 'claude-code session s1 in /w: calls 501/500',
                       env=env, agent='claude-code:s1', cwd='/w') is None
    relay.close()
    assert 'Turn paused (calls)' in _wait_for(tmp_path / 'bin' / 'notify-send.log')
    (req,) = relay.requests
    assert req['op'] == 'notify' and isinstance(req['reqId'], str)
    m = req['message']
    assert m['schema'] == 1 and m['kind'] == 'notice' and m['correlationId'] == m['id']
    assert m['id'] == m['id'].lower() and len(m['id']) == 36
    assert m['from'] == {'kind': 'agent', 'agentId': 'claude-code:s1'} and m['to'] == {'kind': 'user'}
    assert isinstance(m['createdAt'], int) and m['context'] == {'project': None, 'taskId': None, 'cwd': '/w'}
    b = m['body']
    assert b['title'] == 'Turn paused (calls)' and b['level'] == 'warn'
    assert isinstance(b['expiresAt'], int) and b['expiresAt'] > m['createdAt']


def test_notify_reports_a_relay_refusal(tmp_path):
    env = make_env(tmp_path)
    relay = Relay(env, lambda req: {'reqId': req['reqId'], 'ok': False,
                                    'error': {'code': 'INVALID_MESSAGE', 'message': 'invalid notice'}})
    err = notify.send('t', 'b', env=env)
    relay.close()
    assert 'INVALID_MESSAGE' in err


def test_notify_times_out_on_a_silent_relay(tmp_path):
    env = make_env(tmp_path)
    relay = Relay(env, None)
    start = time.monotonic()
    err = notify.send('t', 'b', env=env)
    assert time.monotonic() - start < 1.0
    relay.close()
    assert 'relay' in err and 'timed out' in err


def test_notify_without_relay_serve_is_not_an_error(tmp_path):
    env = make_env(tmp_path)
    assert notify.send('t', 'b', env=env) is None


def test_notify_without_notify_send_is_an_error(tmp_path):
    env = make_env(tmp_path, notify_send=False)
    assert 'notify-send' in notify.send('t', 'b', env=env)


# --- the entry script -----------------------------------------------------------------

def run_entry(tmp_path, event, stdin, harness='claude-code', limits=None):
    env = make_env(tmp_path)
    args = [str(ENTRY), '--harness', harness]
    if limits is not None:
        args += ['--limits', str(limits)]
    data = stdin if isinstance(stdin, bytes) else json.dumps(stdin).encode()
    return subprocess.run(args + [event], input=data, env=env, capture_output=True, timeout=20)


def test_entry_denies_past_the_limit_and_exits_zero(tmp_path):
    limits = tmp_path / 'limits.toml'
    write_limits(limits, calls=1)
    r = run_entry(tmp_path, 'UserPromptSubmit', claude_prompt('work'), limits=limits)
    assert r.returncode == 0 and r.stdout == b''
    pre = claude_pre('Bash', {'command': 'ls'}, 'c1')
    r = run_entry(tmp_path, 'PreToolUse', pre, limits=limits)
    assert r.returncode == 0 and not denied(json.loads(r.stdout))  # allowed, with the 100% warning
    pre['tool_use_id'] = 'c2'
    r = run_entry(tmp_path, 'PreToolUse', pre, limits=limits)
    assert r.returncode == 0
    out = json.loads(r.stdout)
    assert reason(out).startswith('turn paused: calls over its limit')
    assert 'turn paused' in _wait_for(tmp_path / 'bin' / 'notify-send.log')


def test_entry_fails_closed_on_a_bad_pretooluse_payload(tmp_path):
    r = run_entry(tmp_path, 'PreToolUse', b'{not json')
    assert r.returncode == 0
    out = json.loads(r.stdout)
    assert denied(out) and 'turn-pause' in reason(out)


@pytest.mark.parametrize('event', ['Stop', 'SubagentStop', 'UserPromptSubmit', 'PostToolUse', 'SessionEnd'])
def test_entry_never_blocks_other_events(tmp_path, event):
    r = run_entry(tmp_path, event, b'{not json')
    assert r.returncode == 0 and r.stdout == b'' and b'turn-pause' in r.stderr


def test_entry_stop_with_a_broken_state_file_prints_nothing(tmp_path):
    env = make_env(tmp_path)
    path = state_dir(env) / f'claude-code-{CLAUDE_ROOT}.json'
    path.parent.mkdir(parents=True)
    path.write_text('{not json')
    r = run_entry(tmp_path, 'Stop', claude_stop())
    assert r.returncode == 0 and r.stdout == b'' and str(path).encode() in r.stderr


def test_entry_refuses_a_pretooluse_over_32_mib_quickly(tmp_path):
    assert hook.MAX_PAYLOAD_BYTES == 32 * 1024 * 1024
    pre = claude_pre('Write', {'file_path': '/srv/x', 'content': 'a' * (hook.MAX_PAYLOAD_BYTES + 1)}, 'c1')
    start = time.monotonic()
    r = run_entry(tmp_path, 'PreToolUse', pre)
    assert time.monotonic() - start < 5
    assert r.returncode == 0
    out = json.loads(r.stdout)
    assert denied(out) and str(hook.MAX_PAYLOAD_BYTES) in reason(out)


def test_entry_allows_a_5_mb_write_while_not_paused(tmp_path):
    r = run_entry(tmp_path, 'UserPromptSubmit', claude_prompt('write the dump'))
    pre = claude_pre('Write', {'file_path': '/srv/dump.txt', 'content': 'a' * 5_300_000}, 'c1')
    r = run_entry(tmp_path, 'PreToolUse', pre)
    assert r.returncode == 0 and r.stdout == b''


def _entry_state(tmp_path):
    return Store(state_dir(make_env(tmp_path))).read('claude-code', CLAUDE_ROOT)


def test_entry_oversized_genuine_prompt_still_starts_a_turn_without_its_budget(tmp_path):
    limits = tmp_path / 'limits.toml'
    write_limits(limits, calls=1)
    run_entry(tmp_path, 'UserPromptSubmit', claude_prompt('work'), limits=limits)
    for call in ('c1', 'c2'):
        r = run_entry(tmp_path, 'PreToolUse', claude_pre('Bash', {'command': 'touch x'}, call), limits=limits)
    assert denied(json.loads(r.stdout)) and _entry_state(tmp_path).paused == 'calls'
    big = 'budget: 12h\n' + 'x' * (hook.MAX_PAYLOAD_BYTES + 1)
    r = run_entry(tmp_path, 'UserPromptSubmit', claude_prompt(big), limits=limits)
    assert r.returncode == 0 and r.stdout == b'', r.stderr
    st = _entry_state(tmp_path)
    assert st.paused is None and st.turn.calls == 0 and st.turn.limits == load(limits)[0]


def test_entry_oversized_post_tool_use_still_closes_its_call(tmp_path):
    run_entry(tmp_path, 'UserPromptSubmit', claude_prompt('work'))
    pre = claude_pre('Bash', {'command': 'cat big.log'}, 'c1')
    run_entry(tmp_path, 'PreToolUse', pre)
    assert _entry_state(tmp_path).turn.in_flight == {'c1': None}
    r = run_entry(tmp_path, 'PostToolUse', post(pre, {'stdout': 'y' * (hook.MAX_PAYLOAD_BYTES + 1)}))
    assert r.returncode == 0 and r.stdout == b'', r.stderr
    assert _entry_state(tmp_path).turn.in_flight == {}


HEAVY = ('dataclasses', 'typing', 'tempfile', 'pathlib', 'hashlib', 'shlex', 'string', 'json', 're',
         'turn_pause.allowlist')


def test_entry_hot_path_imports_none_of_the_heavy_modules(tmp_path):
    env = make_env(tmp_path)
    run_entry(tmp_path, 'UserPromptSubmit', claude_prompt('work'))
    run_entry(tmp_path, 'PreToolUse', claude_pre('Bash', {'command': 'ls'}, 'warm'))
    payload = json.dumps(claude_pre('Bash', {'command': 'ls'}, 'c1')).encode()
    r = subprocess.run(['/usr/bin/python3', '-S', '-X', 'importtime', str(ENTRY), '--harness', 'claude-code',
                        'PreToolUse'], input=payload, env=env, capture_output=True, timeout=20)
    assert r.returncode == 0 and r.stdout == b''
    imported = {line.rsplit('|', 1)[1].strip() for line in r.stderr.decode().splitlines() if line.startswith('import time:')}
    assert 'turn_pause.hook' in imported
    assert sorted(imported & set(HEAVY)) == []
    shebang = ENTRY.read_text().splitlines()[0]
    assert shebang.split()[-1] == '-S' and '-E' not in shebang


def _proc(root, pid, name, ppid, cmdline=None):
    d = root / str(pid)
    d.mkdir(parents=True)
    (d / 'status').write_text(f'Name:\t{name}\nUmask:\t0022\nPPid:\t{ppid}\n')
    (d / 'cmdline').write_bytes('\0'.join(cmdline or [name]).encode() + b'\0')


def test_a_recorded_harness_pid_that_is_no_longer_an_ancestor_is_found_again(tmp_path):
    proc = tmp_path / 'proc'
    _proc(proc, 50, 'sh', 40)
    _proc(proc, 40, 'claude', 1)
    _proc(proc, 1, 'systemd', 0)
    assert hook.current_harness_pid(40, 50, proc) == 40
    assert hook.current_harness_pid(None, 50, proc) == 40
    assert hook.current_harness_pid(999, 50, proc) == 40  # a resumed session runs under a new process


def test_harness_pid_is_the_nearest_claude_or_codex_else_node_running_one(tmp_path):
    proc = tmp_path / 'proc'
    _proc(proc, 50, 'sh', 40)
    _proc(proc, 40, 'node', 30, ['node', '/usr/lib/node_modules/@openai/codex/bin/codex.js'])
    _proc(proc, 30, 'codex', 1)
    _proc(proc, 1, 'systemd', 0)
    assert hook.find_harness_pid(50, proc) == 30
    other = tmp_path / 'other'
    _proc(other, 50, 'sh', 40)
    _proc(other, 40, 'node', 1, ['node', '/opt/claude-code/cli.js'])
    _proc(other, 1, 'systemd', 0)
    assert hook.find_harness_pid(50, other) == 40
    none = tmp_path / 'none'
    _proc(none, 50, 'sh', 40)
    _proc(none, 40, 'node', 1, ['node', 'server.js'])
    _proc(none, 1, 'systemd', 0)
    assert hook.find_harness_pid(50, none) is None


def _under(monkeypatch, live):
    """Run the hook under a chosen harness process: returns a setter. `live` is the set of
    harness pids that still exist; looking one of them up from itself finds it."""
    current = {'pid': None}

    def find(start, proc='/proc'):
        if start == os.getppid():
            return current['pid']
        return start if start in live else None
    monkeypatch.setattr(hook, 'find_harness_pid', find)
    return lambda pid: current.update(pid=pid)


def _end(d):
    d('SessionEnd', (claude_bare if d.harness == 'claude-code' else codex_bare)('SessionEnd'))


@pytest.mark.parametrize('harness', ['claude-code', 'codex'])
def test_session_end_from_another_process_keeps_a_root_whose_prompter_is_live(tmp_path, monkeypatch, harness):
    d = Driver(tmp_path, harness)
    under = _under(monkeypatch, {7001, 7002})
    under(7001)
    d.prompt('work')
    under(7002)
    d.prompt('work in the second window')
    under(7001)
    d.prompt('approve')  # the last prompter holds the root
    before = d.state()
    under(7002)
    _end(d)
    assert d.state() == before
    under(7001)
    assert not denied(d.bash('ls'))
    _end(d)  # its own end still ends the root
    assert denied(d.bash('ls'))


@pytest.mark.parametrize('ending', [7001, None])
def test_session_end_ends_the_root_when_no_other_live_prompter_is_known(tmp_path, monkeypatch, ending):
    d = Driver(tmp_path, 'claude-code')
    under = _under(monkeypatch, {7001})
    under(7001)
    d.prompt('work')
    under(ending)
    _end(d)
    assert d.state() is None


def test_session_end_from_a_resumed_process_ends_a_root_whose_prompter_died(tmp_path, monkeypatch):
    d = Driver(tmp_path, 'claude-code')
    live = {7001, 7002}
    under = _under(monkeypatch, live)
    under(7001)
    d.prompt('work')
    live.remove(7001)
    under(7002)
    _end(d)
    assert d.state() is None


def test_session_end_from_another_process_keeps_a_pause(tmp_path, monkeypatch):
    d = Driver(tmp_path, 'claude-code')
    under = _under(monkeypatch, {7001, 7002})
    under(7001)
    d.pause_on_calls()
    under(7002)
    _end(d)
    assert d.state().paused == 'calls'


@pytest.mark.parametrize('harness', ['claude-code', 'codex'])
def test_an_ended_root_allows_bookkeeping_and_nothing_else(tmp_path, harness):
    d = Driver(tmp_path, harness)
    d.prompt('work')
    _end(d)
    for cmd in ("tasks feedback --project hq 'blocked wrongly' --category friction",
                "tasks note hq-000001 'state'", 'hq pause status'):
        assert d.bash(cmd) is None, cmd
    for cmd in ('ls', 'cat /etc/hostname', 'tasks start hq-000001', f'kill {os.getpid()}',
                "tasks feedback --project hq 'x'; touch y"):
        out = d.bash(cmd)
        assert denied(out), cmd
        assert 'tasks feedback' in reason(out)
    out = d.bash(f"tasks note hq-000001 'see {d.limits}'")
    assert denied(out) and 'protected path' in reason(out)
    assert d.state() is None


def test_entry_deeply_nested_payload_is_refused_on_pretooluse_and_dropped_elsewhere(tmp_path):
    deep = b'{"session_id": "s", "tool_input": ' + b'[' * 200000 + b']' * 200000 + b'}'
    r = run_entry(tmp_path, 'PreToolUse', deep)
    assert r.returncode == 0 and denied(json.loads(r.stdout))
    r = run_entry(tmp_path, 'PostToolUse', deep)
    assert r.returncode == 0 and r.stdout == b''


def test_an_unreadable_record_is_raised_after_the_counters_are_written(tmp_path):
    d = Driver(tmp_path, 'codex')
    d.prompt('fan out')
    pre = codex_spawn('w0', d.call_id())
    d('PreToolUse', pre)
    with pytest.raises(ValueError, match='spawn_agent response has no task_name'):
        d('PostToolUse', post(pre, 'spawn failed: too many agents'))
    st = d.state()
    assert st.turn.in_flight == {} and 'w0' in st.worker_names


# --- round 2: structure bound, record copies ------------------------------------------

def _many_nodes(element: bytes, size=33_000_000) -> bytes:
    pre = json.dumps(claude_pre('Write', {'file_path': '/srv/x', 'content': None}, 'c1'))
    head, tail = pre.split('null', 1)
    count = (size - len(pre)) // (len(element) + 1)
    return head.encode() + b'[' + (element + b',') * count + element + b']' + tail.encode()


@pytest.mark.parametrize('element', [b'0', b'[]', b'{}'])
def test_entry_refuses_a_33_mb_payload_of_many_nodes_well_inside_the_hook_timeout(tmp_path, element):
    run_entry(tmp_path, 'UserPromptSubmit', claude_prompt('work'))
    raw = _many_nodes(element)
    assert len(raw) < hook.MAX_PAYLOAD_BYTES
    start = time.monotonic()
    r = run_entry(tmp_path, 'PreToolUse', raw)
    assert time.monotonic() - start < 2.5  # the hook's timeout is 5 s
    out = json.loads(r.stdout)
    assert denied(out) and 'JSON nodes' in reason(out)


def test_entry_allows_a_large_write_whose_commas_are_inside_its_string(tmp_path):
    run_entry(tmp_path, 'UserPromptSubmit', claude_prompt('write the table'))
    rows = 'id,name,"quoted, value",3\n' * 800_000  # about 3.2M commas, all inside one string
    r = run_entry(tmp_path, 'PreToolUse', claude_pre('Write', {'file_path': '/srv/t.csv', 'content': rows}, 'c1'))
    assert r.returncode == 0 and r.stdout == b'', r.stdout[:300]


@pytest.mark.parametrize('paused', [False, True])
def test_a_tool_input_over_the_node_budget_is_refused_paused_or_not(tmp_path, notices, paused):
    from turn_pause import protect
    d = Driver(tmp_path, 'claude-code')
    if paused:
        d.pause_on_calls()
    else:
        d.prompt('work')
    out, _ = d.pre('Write', {'file_path': '/srv/x', 'content': [0] * (protect.MAX_NODES + 1)})
    assert denied(out) and 'JSON nodes' in reason(out)


def test_frozen_records_copy_deepcopy_and_pickle(tmp_path):
    import pickle
    from turn_pause.limits import Limits
    from turn_pause.prompt import Budget
    values = [Event(T0, 'a1', 'tool_start', call_id='c1', tool='Bash'), Limits(1, 2, 3, 4), Budget(60, None, 5, None),
              engine.Decision(False, {'x': [1]}, 'calls'), adapters.load_facts()]
    for value in values:
        for twin in (copy.copy(value), copy.deepcopy(value), pickle.loads(pickle.dumps(value))):
            assert twin == value and type(twin) is type(value)
    d = Driver(tmp_path, 'claude-code')
    d.prompt('work')
    d.bash('ls')
    st = d.state()
    for twin in (copy.deepcopy(st), pickle.loads(pickle.dumps(st))):
        assert twin == st


@pytest.mark.parametrize('path', ['harnesses/claude/settings.json', 'harnesses/codex/hooks.json',
                                  'harnesses/codex/work/hooks.json', 'harnesses/claude/work/settings.json'])
@pytest.mark.parametrize('shell', [False, True])
def test_relocated_wiring_is_protected(tmp_path, path, shell):
    d = Driver(tmp_path, 'claude-code')
    d.prompt('work')
    target = str(CHECKOUT / path)
    if shell:
        out = d.bash('touch ' + shlex.quote(target))
    else:
        out, _ = d.pre('Write', {'file_path': target, 'content': '{}'})
    assert denied(out)
    assert 'protected' in reason(out)


def _assert_hq_owner(text: str, expected_substring: str):
    assert expected_substring in text
    assert text.endswith(f'\n{OWNER_LINE}')
    body = text[:-len(OWNER_LINE) - 1]
    assert expected_substring in body
    assert 'owner: hq' not in body


@pytest.mark.parametrize('harness', ['claude-code', 'codex'])
@pytest.mark.parametrize('case', [
    'root-limit',
    'child-limit',
    'limits-changed',
    'paused-disallowed',
    'exhausted-grace',
    'protected-path',
    'node-budget',
    'ended-root',
    'malformed-event',
    'state-error',
])
def test_every_decide_denial_retains_its_cause_and_attributes_owner_to_hq(tmp_path, notices, harness, case):
    from turn_pause import protect
    d = Driver(tmp_path, harness)
    if case == 'root-limit':
        out = d.pause_on_calls(limit=1)
        _assert_hq_owner(reason(out), 'turn paused: calls over its limit')
        assert 'Start nothing new and stop the work you already started' in reason(out)
    elif case == 'child-limit':
        write_limits(d.limits, active_seconds=1)
        d.prompt('work')
        out = d.bash('touch x', agent='a620dc1cd95e3a1c5', dt=2)
        _assert_hq_owner(reason(out), "turn paused by your controller's limit")
        assert 'Do not write a pause report.' in reason(out)
    elif case == 'limits-changed':
        d.prompt('work')
        assert d.bash('ls') is None
        write_limits(d.limits, calls=5000)
        out = d.bash('ls')
        _assert_hq_owner(reason(out), 'turn paused: the turn limits file changed mid-turn')
        assert 'Start nothing new and stop the work you already started' in reason(out)
    elif case == 'paused-disallowed':
        d.pause_on_calls()
        out = d.bash('touch z')
        _assert_hq_owner(reason(out), 'This call:')
    elif case == 'exhausted-grace':
        d.pause_on_calls()
        for _ in range(25):
            assert not denied(d.bash('ls'))
        out = d.bash('ls')
        _assert_hq_owner(reason(out), 'the 25 allowlisted reads of grace are used up')
    elif case == 'protected-path':
        d.prompt('work')
        out = d.bash('touch ' + shlex.quote(str(d.limits)))
        _assert_hq_owner(reason(out), 'this call names a protected path')
    elif case == 'node-budget':
        d.prompt('work')
        out, _ = d.pre('Bash', {'command': 'ls', 'extra': [0] * (protect.MAX_NODES + 1)})
        _assert_hq_owner(reason(out), 'JSON nodes')
    elif case == 'ended-root':
        d.prompt('work')
        end = claude_bare('SessionEnd') if harness == 'claude-code' else codex_bare('SessionEnd')
        d('SessionEnd', end)
        out = d.bash('ls')
        _assert_hq_owner(reason(out), 'root session ended; a genuine root prompt is required to resume.')
    elif case == 'malformed-event':
        out = hook.decide(harness, 'PreToolUse', {'session_id': 123}, T0, d.store, d.limits, d.env)
        _assert_hq_owner(reason(out), 'turn-pause could not judge this call, so it is refused:')
    elif case == 'state-error':
        d.prompt('work')
        root = CLAUDE_ROOT if harness == 'claude-code' else CODEX_ROOT
        (state_dir(d.env) / f'{harness}-{root}.json').write_text('{not json')
        out = d.bash('ls')
        _assert_hq_owner(reason(out), 'turn-pause could not judge this call, so it is refused:')


@pytest.mark.parametrize('harness', ['claude-code', 'codex'])
@pytest.mark.parametrize('case', ['bad-json', 'oversized', 'many-nodes', 'import-error'])
def test_entry_fail_closed_denials_retain_cause_and_attribute_owner_to_hq(tmp_path, harness, case):
    if case == 'bad-json':
        r = run_entry(tmp_path, 'PreToolUse', b'{not json', harness=harness)
        expected = 'turn-pause could not judge this call, so it is refused: JSONDecodeError:'
    elif case == 'oversized':
        payload = (claude_pre('Write', {'file_path': '/srv/x', 'content': 'a' * (hook.MAX_PAYLOAD_BYTES + 1)}, 'c1')
                   if harness == 'claude-code'
                   else codex_pre('Bash', {'command': 'a' * (hook.MAX_PAYLOAD_BYTES + 1)}, 'c1'))
        r = run_entry(tmp_path, 'PreToolUse', payload, harness=harness)
        expected = f'over the {hook.MAX_PAYLOAD_BYTES} byte cap'
    elif case == 'many-nodes':
        r = run_entry(tmp_path, 'PreToolUse', _many_nodes(b'0'), harness=harness)
        expected = 'JSON nodes'
    elif case == 'import-error':
        broken = tmp_path / 'broken-entry'
        broken.mkdir()
        entry_copy = broken / 'turn-pause'
        shutil.copy2(ENTRY, entry_copy)
        (broken / 'turn_pause').mkdir()
        (broken / 'turn_pause' / 'hook.py').write_text('raise RuntimeError("boom")\n')
        r = subprocess.run([str(entry_copy), '--harness', harness, 'PreToolUse'],
                           input=b'{}', env=make_env(tmp_path), capture_output=True, timeout=20)
        expected = 'turn-pause cannot load, so this call is refused: RuntimeError'
    assert r.returncode == 0
    out = json.loads(r.stdout)
    assert denied(out)
    _assert_hq_owner(reason(out), expected)
    assert getattr(hook, 'OWNER_LINE', None) == OWNER_LINE


# --- spend episodes and host latch ----------------------------------------------------

def _spend_entry(
    harness: str,
    root_session: str,
    *,
    episode: str | None = None,
    value: int | float = 500_000_000,
    threshold: int | float = 350_000_000.0,
    ratio: int | float = 1.43,
    window_hours: int = 72,
    now_s: float = T0,
    measured_at: int | None = None,
    complete: bool = True,
    root_resolved: bool = True,
    credits_drawn_24h: int | float | None = 0.0,
    root: str | None = None,
    **overrides,
) -> dict:
    ts_ms = int(now_s * 1000) if measured_at is None else measured_at
    entry = {
        'root': f'{harness}:{root_session}' if root is None else root,
        'harness': harness,
        'root_session': root_session,
        'root_resolved': root_resolved,
        'episode': f'{harness}:{root_session}@1793539000000' if episode is None else episode,
        'metric': 'tokens',
        'window_hours': window_hours,
        'info_window_hours': 24,
        'value': value,
        'threshold': threshold,
        'ratio': ratio,
        'value_info': 100_000_000,
        'first_crossed_at': ts_ms - 1000,
        'measured_at': ts_ms,
        'observed_at': ts_ms,
        'complete': complete,
        'children': 1,
        'last_context_tokens': 50_000,
        'responses_last_hour': 12,
        'codex_home': '.codex' if harness == 'codex' else None,
        'credits_drawn_24h': credits_drawn_24h,
    }
    entry.update(overrides)
    return entry


def _write_spend_signal(
    env: dict[str, str],
    trees: list[dict],
    *,
    now_s: float = T0,
    generated_at: int | None = None,
    stale_after_ms: int = 600_000,
    status: str = 'ok',
    schema: object = 1,
) -> Path:
    gen_ms = int(now_s * 1000) if generated_at is None else generated_at
    obs_dir = Path(env['XDG_STATE_HOME']) / 'obs'
    obs_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        'schema': schema,
        'generated_at': gen_ms,
        'status': status,
        'stale_after_ms': stale_after_ms,
        'baseline': {
            'id': 'baseline-1',
            'computed_at': gen_ms,
            'harnesses': {
                'claude-code': {'state': 'ok', 'threshold': 250_000_000.0, 'trees': 40},
                'codex': {'state': 'ok', 'threshold': 350_000_000.0, 'trees': 40},
            },
        },
        'credits': {},
        'coverage': {
            'files_seen': 10,
            'files_unfinished': 0,
            'files_starved': [],
            'files_malformed': [],
            'files_unparsed': [],
            'trees_unfinished': [],
        },
        'trees': trees,
    }
    dest = obs_dir / 'spend-signals.json'
    tmp = obs_dir / f'.spend-signals.json.{os.urandom(6).hex()}.tmp'
    tmp.write_text(json.dumps(payload), encoding='utf-8')
    os.replace(tmp, dest)
    return dest


@pytest.fixture
def desktop_alerts(monkeypatch):
    sent = []
    monkeypatch.setattr(
        hook.notify,
        'desktop',
        lambda title, body, *, env: sent.append((title, body, dict(env))) or None,
    )
    return sent


class TestSpendHook:
    def test_spend_measurement_and_texts_contract(self):
        from turn_pause.spend import Entry

        base = dict(
            episode='ep-1',
            value=750_000_000,
            threshold=350_000_000.0,
            ratio=2.1428,
            window_hours=72,
            measured_at=int(T0 * 1000),
            complete=True,
        )
        e_none = Entry(**base, credits_drawn_24h=None)
        e_zero = Entry(**base, credits_drawn_24h=0.0)
        e_pos = Entry(**base, credits_drawn_24h=12.5)
        assert hook.SPEND == 'spend'
        assert hook.spend_measurement(e_none, 'claude-code') == (
            'obs measured 750.0M tokens in 72 h against a threshold of 350.0M '
            '(ratio 2.14; episode ep-1)'
        )
        assert hook.spend_measurement(e_zero, 'codex') == (
            'obs measured 750.0M tokens in 72 h against a threshold of 350.0M '
            '(ratio 2.14; episode ep-1)'
        )
        assert hook.spend_measurement(e_pos, 'codex') == (
            'obs measured 750.0M tokens in 72 h against a threshold of 350.0M '
            '(ratio 2.14; episode ep-1; credits drawn in 24 h: 12.5)'
        )
        root_text = hook.SPEND_ROOT_TEXT.format(measurement=hook.spend_measurement(e_pos, 'codex'))
        assert root_text.startswith(
            "turn paused: spend. This agent tree's token spend is far outside its harness's "
            'normal range: obs measured 750.0M tokens in 72 h against a threshold of 350.0M '
            '(ratio 2.14; episode ep-1; credits drawn in 24 h: 12.5). Start nothing new and stop'
        )
        assert '..' not in root_text
        assert 'do not claim it is paused. Then record the signal (value, threshold, episode)' in root_text
        assert root_text.endswith(
            'Only bookkeeping, plain reads and stopping your own work are allowed now; '
            'hq pause status shows the signal.'
        )
        inject_text = hook.SPEND_INJECT_TEXT.format(measurement=hook.spend_measurement(e_zero, 'codex'))
        assert inject_text == (
            "turn-pause: spend signal. This agent tree's token spend went far outside its "
            "harness's normal range while it was idle: obs measured 750.0M tokens in 72 h "
            'against a threshold of 350.0M (ratio 2.14; episode ep-1). Report the signal to the '
            "user first, then investigate its cause in this turn (obs's growth report on the "
            "tree, the polling pattern behind it) and record it on the task, before any of the "
            "original task's work resumes. Do not park or end the turn for this. The original "
            'work resumes only with a fix or a mitigation that removes the cause, or on the '
            "user's explicit instruction."
        )

    @pytest.mark.parametrize('harness', ['claude-code', 'codex'])
    @pytest.mark.parametrize('credits,status', [(0.0, 'ok'), (None, 'partial'), (12.5, 'ok')])
    def test_spend_pauses_root_call(self, tmp_path, notices, desktop_alerts, harness, credits, status):
        d = Driver(tmp_path, harness)
        d.prompt('work')
        _write_spend_signal(
            d.env,
            [_spend_entry(harness, d.root, episode='ep-root', value=500_000_000,
                          threshold=350_000_000.0, ratio=1.43, credits_drawn_24h=credits,
                          now_s=d.t)],
            now_s=d.t,
            status=status,
        )
        out = d.bash('ls')
        assert denied(out)
        text = reason(out)
        assert text.startswith('turn paused: spend.')
        expected_credits = '; credits drawn in 24 h: 12.5' if credits == 12.5 else ''
        expected_meas = (
            'obs measured 500.0M tokens in 72 h against a threshold of 350.0M '
            f'(ratio 1.43; episode ep-root{expected_credits})'
        )
        assert expected_meas in text
        if credits in (None, 0.0):
            assert 'credits drawn' not in text
        _assert_hq_owner(text, 'hq pause status shows the signal.')
        assert '..' not in text

        record = d.store.read_record(harness, d.root)
        pauses = [e for e in record.events if e['kind'] == 'enforced_pause']
        assert len(pauses) == 1 and pauses[0]['reason'] == 'spend'
        assert pauses[0]['snapshot']['paused'] == 'spend'
        assert record.spend is not None
        assert record.spend.delivered_value == 500_000_000
        assert record.spend.acked_value is None

        assert len(notices) == 1
        title, body, _ = notices[0]
        assert title == 'turn paused (spend)'
        assert body == (
            f'{harness} session {d.root} in {d.state().cwd}: {expected_meas}. '
            'Reply in the session to resume.'
        )
        assert desktop_alerts == []

    @pytest.mark.parametrize('harness', ['claude-code', 'codex'])
    def test_spend_child_call_pauses_without_delivery(self, tmp_path, notices, desktop_alerts, harness):
        d = Driver(tmp_path, harness)
        d.prompt('work')
        _write_spend_signal(
            d.env,
            [_spend_entry(harness, d.root, episode='ep-child', value=500_000_000, now_s=d.t)],
            now_s=d.t,
        )
        out = d.bash('touch x', agent='worker-1')
        assert denied(out)
        assert reason(out) == CHILD_TEXT.format(limit='spend') + f'\n{OWNER_LINE}'
        assert d.state().paused == 'spend'
        record = d.store.read_record(harness, d.root)
        assert record.spend is not None
        assert record.spend.episode == 'ep-child'
        assert record.spend.seen_value == 500_000_000
        assert record.spend.delivered_value is None
        assert record.spend.acked_value is None
        assert len(notices) == 1 and notices[0][0] == 'turn paused (spend)'

    @pytest.mark.parametrize('harness', ['claude-code', 'codex'])
    def test_child_only_pause_injects_at_prompt(self, tmp_path, notices, desktop_alerts, harness):
        d = Driver(tmp_path, harness)
        d.prompt('work')
        _write_spend_signal(
            d.env,
            [_spend_entry(harness, d.root, episode='ep-child', value=500_000_000, now_s=d.t)],
            now_s=d.t,
        )
        assert denied(d.bash('touch x', agent='worker-1'))
        assert d.store.read_record(harness, d.root).spend.delivered_value is None

        out = d.prompt('what happened?')
        ctx = context(out)
        assert ctx is not None
        assert ctx.startswith("turn-pause: spend signal. This agent tree's token spend went far outside")
        assert 'obs measured 500.0M tokens in 72 h against a threshold of 350.0M (ratio 1.43; episode ep-child)' in ctx
        record = d.store.read_record(harness, d.root)
        assert record.spend.delivered_value == 500_000_000
        assert record.spend.acked_value == 500_000_000
        assert record.state.paused is None
        assert record.state.spend_snapshot is None
        warnings = [e for e in record.events if e['kind'] == 'warning']
        assert len(warnings) == 1 and warnings[0]['reason'] == 'spend' and warnings[0]['turn'] == 2

    @pytest.mark.parametrize('harness', ['claude-code', 'codex'])
    def test_later_root_refusal_delivers_from_snapshot(self, tmp_path, notices, desktop_alerts, harness):
        d = Driver(tmp_path, harness)
        d.prompt('work')
        _write_spend_signal(
            d.env,
            [_spend_entry(harness, d.root, episode='ep-snap', value=500_000_000, now_s=d.t)],
            now_s=d.t,
        )
        assert denied(d.bash('touch x', agent='worker-1'))
        assert d.store.read_record(harness, d.root).spend.delivered_value is None

        # Episode closes in obs before the root's next call.
        _write_spend_signal(d.env, [], now_s=d.t + 1)
        # Allowlisted bookkeeping does not deliver.
        assert d.bash('tasks note hq-123456 paused') is None
        assert d.store.read_record(harness, d.root).spend.delivered_value is None

        out = d.bash('touch y')
        assert denied(out)
        text = reason(out)
        assert text.startswith('turn paused: spend.')
        assert '500.0M tokens in 72 h' in text
        assert 'episode ep-snap' in text
        assert 'This call:' in text
        record = d.store.read_record(harness, d.root)
        assert record.spend.delivered_value == 500_000_000
        assert record.spend.acked_value is None
        assert len(notices) == 1

    @pytest.mark.parametrize('harness', ['claude-code', 'codex'])
    @pytest.mark.parametrize(
        'case',
        ['absent', 'unreadable', 'wrong_schema', 'bool_value', 'stale_file', 'stale_entry', 'root_resolved_false'],
    )
    def test_no_spend_pause_when(self, tmp_path, notices, desktop_alerts, harness, case):
        from turn_pause import spend

        d = Driver(tmp_path, harness)
        d.prompt('work')
        now_ms = int(d.t * 1000)
        if case == 'unreadable':
            obs_dir = Path(d.env['XDG_STATE_HOME']) / 'obs'
            obs_dir.mkdir(parents=True, exist_ok=True)
            (obs_dir / 'spend-signals.json').write_text('{not valid json')
        elif case == 'wrong_schema':
            _write_spend_signal(d.env, [_spend_entry(harness, d.root, now_s=d.t)], now_s=d.t, schema=2)
        elif case == 'bool_value':
            _write_spend_signal(
                d.env,
                [_spend_entry(harness, d.root, value=True, now_s=d.t)],
                now_s=d.t,
            )
        elif case == 'stale_file':
            _write_spend_signal(
                d.env,
                [_spend_entry(harness, d.root, measured_at=now_ms - 600_001)],
                generated_at=now_ms - 600_001,
                stale_after_ms=600_000,
            )
        elif case == 'stale_entry':
            _write_spend_signal(
                d.env,
                [_spend_entry(harness, d.root, measured_at=now_ms - 600_001)],
                generated_at=now_ms,
                stale_after_ms=600_000,
            )
        elif case == 'root_resolved_false':
            _write_spend_signal(
                d.env,
                [_spend_entry(harness, d.root, root_resolved=False, now_s=d.t)],
                now_s=d.t,
            )

        assert d.bash('ls') is None
        st = d.state()
        assert st.paused is None
        assert st.spend_cache is not None
        expected_state = {
            'absent': 'absent',
            'unreadable': 'unreadable',
            'wrong_schema': 'unreadable',
            'bool_value': 'unreadable',
            'stale_file': 'stale',
            'stale_entry': 'fresh',
            'root_resolved_false': 'fresh',
        }[case]
        assert spend.state_of(st.spend_cache, int(d.t * 1000), False) == expected_state
        assert d.store.read_record(harness, d.root).spend is None
        assert notices == []

    @pytest.mark.parametrize('harness', ['claude-code', 'codex'])
    def test_counter_pause_not_switched(self, tmp_path, notices, desktop_alerts, harness):
        d = Driver(tmp_path, harness)
        write_limits(d.limits, calls=1)
        d.prompt('work')
        assert not denied(d.bash('ls'))
        _write_spend_signal(
            d.env,
            [_spend_entry(harness, d.root, episode='ep-counter', value=500_000_000, now_s=d.t)],
            now_s=d.t,
        )
        out = d.bash('ls')
        assert denied(out)
        assert d.state().paused == 'calls'
        assert 'calls over its limit' in reason(out)
        assert denied(d.bash('touch x'))
        assert d.state().paused == 'calls'
        assert d.store.read_record(harness, d.root).spend.delivered_value is None

        prompt_out = d.prompt('continue')
        assert 'turn-pause: spend signal.' in (context(prompt_out) or '')
        assert 'episode ep-counter' in context(prompt_out)
        rec = d.store.read_record(harness, d.root)
        assert rec.spend.delivered_value == 500_000_000
        assert rec.spend.acked_value == 500_000_000

    @pytest.mark.parametrize('harness', ['claude-code', 'codex'])
    def test_ack_at_prompt_then_quiet(self, tmp_path, notices, desktop_alerts, harness):
        d = Driver(tmp_path, harness)
        d.prompt('work')
        _write_spend_signal(
            d.env,
            [_spend_entry(harness, d.root, episode='ep-ack', value=500_000_000, now_s=d.t)],
            now_s=d.t,
        )
        assert denied(d.bash('ls'))
        assert d.store.read_record(harness, d.root).spend.acked_value is None

        assert d.prompt('investigate') is None
        rec = d.store.read_record(harness, d.root)
        assert rec.spend.acked_value == 500_000_000

        _write_spend_signal(
            d.env,
            [_spend_entry(harness, d.root, episode='ep-ack', value=999_000_000, now_s=d.t)],
            now_s=d.t,
        )
        assert d.bash('ls') is None
        assert d.state().paused is None

        _write_spend_signal(
            d.env,
            [_spend_entry(harness, d.root, episode='ep-ack', value=1_000_000_000, now_s=d.t)],
            now_s=d.t,
        )
        out = d.bash('ls')
        assert denied(out)
        assert d.state().paused == 'spend'
        assert '1000.0M tokens' in reason(out)

    @pytest.mark.parametrize('harness', ['claude-code', 'codex'])
    def test_root_repause_acked_not_injected(self, tmp_path, notices, desktop_alerts, harness):
        d = Driver(tmp_path, harness)
        d.prompt('work')
        _write_spend_signal(
            d.env,
            [_spend_entry(harness, d.root, episode='ep-re', value=500_000_000, now_s=d.t)],
            now_s=d.t,
        )
        assert denied(d.bash('ls'))
        assert d.prompt('ack first') is None

        _write_spend_signal(
            d.env,
            [_spend_entry(harness, d.root, episode='ep-re', value=1_000_000_000, now_s=d.t)],
            now_s=d.t,
        )
        assert denied(d.bash('ls'))
        rec = d.store.read_record(harness, d.root)
        assert rec.spend.delivered_value == 1_000_000_000
        assert rec.spend.acked_value is None

        assert d.prompt('ack second') is None
        rec = d.store.read_record(harness, d.root)
        assert rec.spend.acked_value == 1_000_000_000

    @pytest.mark.parametrize('harness', ['claude-code', 'codex'])
    def test_child_repause_injected(self, tmp_path, notices, desktop_alerts, harness):
        d = Driver(tmp_path, harness)
        d.prompt('work')
        _write_spend_signal(
            d.env,
            [_spend_entry(harness, d.root, episode='ep-cre', value=500_000_000, now_s=d.t)],
            now_s=d.t,
        )
        assert denied(d.bash('ls'))
        assert d.prompt('ack first') is None

        _write_spend_signal(
            d.env,
            [_spend_entry(harness, d.root, episode='ep-cre', value=1_000_000_000, now_s=d.t)],
            now_s=d.t,
        )
        assert denied(d.bash('touch x', agent='worker-1'))
        rec = d.store.read_record(harness, d.root)
        assert rec.spend.delivered_value == 500_000_000
        assert rec.spend.acked_value == 500_000_000

        out = d.prompt('next turn')
        assert 'turn-pause: spend signal.' in (context(out) or '')
        assert '1000.0M tokens' in context(out)
        rec = d.store.read_record(harness, d.root)
        assert rec.spend.delivered_value == 1_000_000_000
        assert rec.spend.acked_value == 1_000_000_000

    @pytest.mark.parametrize('harness', ['claude-code', 'codex'])
    def test_replacement_episode_injected(self, tmp_path, notices, desktop_alerts, harness):
        d = Driver(tmp_path, harness)
        d.prompt('work')
        _write_spend_signal(
            d.env,
            [_spend_entry(harness, d.root, episode='ep-1', value=500_000_000, now_s=d.t)],
            now_s=d.t,
        )
        assert denied(d.bash('ls'))
        assert d.store.read_record(harness, d.root).spend.acked_value is None

        _write_spend_signal(
            d.env,
            [_spend_entry(harness, d.root, episode='ep-2', value=600_000_000, now_s=d.t)],
            now_s=d.t,
        )
        out = d.prompt('continue')
        assert 'turn-pause: spend signal.' in (context(out) or '')
        assert '600.0M tokens' in context(out)
        assert 'episode ep-2' in context(out)
        rec = d.store.read_record(harness, d.root)
        assert rec.spend.episode == 'ep-2'
        assert rec.spend.delivered_value == 600_000_000
        assert rec.spend.acked_value == 600_000_000

    @pytest.mark.parametrize('harness', ['claude-code', 'codex'])
    def test_injection_on_first_prompt(self, tmp_path, notices, desktop_alerts, harness):
        d = Driver(tmp_path, harness)
        assert d.store.read_record(harness, d.root) is None
        _write_spend_signal(
            d.env,
            [_spend_entry(harness, d.root, episode='ep-first', value=500_000_000, now_s=d.t)],
            now_s=d.t,
        )
        out = d.prompt('start the task')
        ctx = context(out)
        assert ctx is not None
        assert ctx.startswith('turn-pause: spend signal.')
        assert 'episode ep-first' in ctx
        rec = d.store.read_record(harness, d.root)
        assert rec.turn_serial == 1
        assert [(e['kind'], e['reason'], e['turn']) for e in rec.events] == [
            ('turn_start', 'genuine_user', 1),
            ('warning', 'spend', 1),
        ]
        assert rec.spend.delivered_value == 500_000_000
        assert rec.spend.acked_value == 500_000_000
        assert d.bash('ls') is None

    @pytest.mark.parametrize('harness', ['claude-code', 'codex'])
    def test_injection_joins_budget_note(self, tmp_path, notices, desktop_alerts, harness):
        from turn_pause.limits import duration, with_budget

        d = Driver(tmp_path, harness)
        _write_spend_signal(
            d.env,
            [_spend_entry(harness, d.root, episode='ep-budget', value=500_000_000, now_s=d.t)],
            now_s=d.t,
        )
        out = d.prompt('budget: 2h\nRun the migration.')
        scaled = with_budget(load(d.limits)[0], parse_budget('budget: 2h'))
        expected_budget = BUDGET_TEXT.format(
            a=duration(scaled.active_seconds),
            c=scaled.calls,
            s=scaled.spawns,
            k=scaled.compactions,
        )
        ctx = context(out)
        assert ctx is not None
        parts = ctx.split('\n')
        assert len(parts) == 2
        assert parts[0] == expected_budget
        assert parts[1].startswith('turn-pause: spend signal.')
        assert 'episode ep-budget' in parts[1]
        assert d.state().budget_note == expected_budget

    def test_non_genuine_prompts_leave_record(self, tmp_path, notices, desktop_alerts):
        from turn_pause.record import jencode_compact
        from turn_pause.spend import spend_record_to_dict

        d = Driver(tmp_path, 'claude-code')
        d.prompt('work')
        d('Stop', claude_stop([{'id': 'cron-1', 'prompt': 'scheduled poll'}]))
        _write_spend_signal(
            d.env,
            [_spend_entry('claude-code', d.root, episode='ep-1', value=500_000_000, now_s=d.t)],
            now_s=d.t,
        )
        assert denied(d.bash('ls'))

        rec_before = d.store.read_record('claude-code', d.root)
        assert rec_before.spend is not None and rec_before.spend.episode == 'ep-1'
        assert rec_before.spend.delivered_value == 500_000_000
        assert rec_before.spend.acked_value is None
        expected_fragment = f'"spend":{jencode_compact(spend_record_to_dict(rec_before.spend))}'.encode()
        record_file = state_dir(d.env) / f'claude-code-{d.root}.json'
        assert expected_fragment in record_file.read_bytes()

        _write_spend_signal(
            d.env,
            [_spend_entry('claude-code', d.root, episode='ep-2', value=600_000_000, now_s=d.t)],
            now_s=d.t,
        )

        worker_prompt = dict(claude_prompt('worker check'), agent_id='a620dc1cd95e3a1c5', agent_type='general-purpose')
        assert d('UserPromptSubmit', worker_prompt) is None
        assert d.store.read_record('claude-code', d.root).spend == rec_before.spend
        assert expected_fragment in record_file.read_bytes()

        assert d.prompt('<task-notification>\n<task-id>a1</task-id>\n</task-notification>') is None
        assert d.store.read_record('claude-code', d.root).spend == rec_before.spend
        assert expected_fragment in record_file.read_bytes()

        wake_out = d.prompt('scheduled poll')
        assert context(wake_out) == WAKE_TEXT
        assert d.store.read_record('claude-code', d.root).spend == rec_before.spend
        assert expected_fragment in record_file.read_bytes()

    @pytest.mark.parametrize('harness', ['claude-code', 'codex'])
    def test_protected_denial_while_spend_paused_does_not_deliver(self, tmp_path, notices, desktop_alerts, harness):
        d = Driver(tmp_path, harness)
        d.prompt('work')
        sig_path = _write_spend_signal(
            d.env,
            [_spend_entry(harness, d.root, episode='ep-prot', value=500_000_000, now_s=d.t)],
            now_s=d.t,
        )
        assert denied(d.bash('touch x', agent='worker-1'))
        assert d.state().paused == 'spend'
        assert d.store.read_record(harness, d.root).spend.delivered_value is None

        out, _ = d.pre('Edit', {'file_path': str(sig_path), 'old_string': '500000000', 'new_string': '0'})
        assert denied(out)
        assert 'protected path' in reason(out)
        assert d.store.read_record(harness, d.root).spend.delivered_value is None

    @pytest.mark.parametrize('harness', ['claude-code', 'codex'])
    def test_snapshot_updates_from_newer_same_episode_entry(self, tmp_path, notices, desktop_alerts, harness):
        d = Driver(tmp_path, harness)
        d.prompt('work')
        _write_spend_signal(
            d.env,
            [_spend_entry(harness, d.root, episode='ep-up', value=700_000_000, now_s=d.t)],
            now_s=d.t,
        )
        out1 = d.bash('ls')
        assert denied(out1)
        assert '700.0M tokens' in reason(out1)

        _write_spend_signal(
            d.env,
            [_spend_entry(harness, d.root, episode='ep-up', value=750_000_000, now_s=d.t + 1)],
            now_s=d.t + 1,
        )
        out2 = d.bash('touch z')
        assert denied(out2)
        assert '750.0M tokens' in reason(out2)
        assert d.store.read_record(harness, d.root).spend.delivered_value == 750_000_000

    @pytest.mark.parametrize('harness', ['claude-code', 'codex'])
    def test_ack_survives_session_end(self, tmp_path, notices, desktop_alerts, harness):
        d = Driver(tmp_path, harness)
        d.prompt('work')
        _write_spend_signal(
            d.env,
            [_spend_entry(harness, d.root, episode='ep-end', value=500_000_000, now_s=d.t)],
            now_s=d.t,
            stale_after_ms=600_000,
        )
        assert denied(d.bash('ls'))
        assert d.store.read_record(harness, d.root).spend.acked_value is None

        end_payload = claude_bare('SessionEnd') if harness == 'claude-code' else codex_bare('SessionEnd')
        assert d('SessionEnd', end_payload) is None
        assert d.state() is None

        # Advance 700 s so the signal file is stale when the session resumes.
        out = d.prompt('resume after break', dt=700)
        assert out is None
        rec = d.store.read_record(harness, d.root)
        assert rec.spend is not None
        assert rec.spend.delivered_value == 500_000_000
        assert rec.spend.acked_value == 500_000_000
        assert len(desktop_alerts) == 1

    @pytest.mark.parametrize('harness', ['claude-code', 'codex'])
    def test_concurrent_root_and_worker_one_pause(self, tmp_path, notices, desktop_alerts, harness):
        d = Driver(tmp_path, harness)
        d.prompt('work')
        _write_spend_signal(
            d.env,
            [_spend_entry(harness, d.root, episode='ep-conc', value=500_000_000, now_s=d.t)],
            now_s=d.t,
        )
        maker = claude_pre if harness == 'claude-code' else codex_pre
        root_payload = dict(maker('Bash', {'command': 'touch a'}, 'c-root'), session_id=d.root)
        worker_payload = dict(maker('Bash', {'command': 'touch b'}, 'c-worker', agent='worker-1'), session_id=d.root)

        barrier = threading.Barrier(2)
        results = {}
        errors = []

        def invoke(key, payload, ts):
            try:
                barrier.wait(5)
                results[key] = hook.decide(harness, 'PreToolUse', payload, ts, d.store, d.limits, d.env)
            except BaseException as exc:
                errors.append(exc)

        t_root = threading.Thread(target=invoke, args=('root', root_payload, d.t + 1))
        t_worker = threading.Thread(target=invoke, args=('worker', worker_payload, d.t + 1))
        t_root.start()
        t_worker.start()
        t_root.join(5)
        t_worker.join(5)
        assert not t_root.is_alive() and not t_worker.is_alive() and not errors
        assert denied(results['root']) and denied(results['worker'])

        rec = d.store.read_record(harness, d.root)
        pauses = [e for e in rec.events if e['kind'] == 'enforced_pause']
        assert len(pauses) == 1 and pauses[0]['reason'] == 'spend'
        assert len(notices) == 1
        assert rec.spend.delivered_value == 500_000_000

    @pytest.mark.parametrize('harness', ['claude-code', 'codex'])
    def test_spend_files_protected(self, tmp_path, notices, desktop_alerts, harness):
        from turn_pause.spend import PROTECTED_NAMES

        d = Driver(tmp_path, harness)
        d.prompt('work')
        sig_path = _write_spend_signal(d.env, [], now_s=d.t)
        obs_dir = sig_path.parent

        for name in PROTECTED_NAMES:
            target = obs_dir / name
            out, _ = d.pre('Edit', {'file_path': str(target), 'old_string': 'a', 'new_string': 'b'})
            assert denied(out), name
            assert 'protected path' in reason(out)

        assert not denied(d.bash('cat ' + shlex.quote(str(sig_path))))
        doc_edit, _ = d.pre(
            'Edit',
            {
                'file_path': '/srv/docs/obs.md',
                'old_string': 'old',
                'new_string': f'See ~/.local/state/obs/index.sqlite and {obs_dir}/index.sqlite',
            },
        )
        assert not denied(doc_edit)

    def test_staleness_alert_once_across_roots(self, tmp_path, notices, desktop_alerts):
        env = make_env(tmp_path)
        store = Store(state_dir(env))
        limits = tmp_path / 'limits.toml'
        limits.write_bytes(DEFAULTS_PATH.read_bytes())

        now_ms = int(T0 * 1000)
        _write_spend_signal(env, [], generated_at=now_ms - 700_000, stale_after_ms=600_000)

        # Root 1 (claude-code) and Root 2 (codex) share the same host state directory.
        assert hook.decide('claude-code', 'UserPromptSubmit', claude_prompt('work'), T0, store, limits, env) is None
        assert hook.decide('claude-code', 'PreToolUse', claude_pre('Bash', {'command': 'ls'}, 'c1'), T0 + 1, store, limits, env) is None
        assert hook.decide('codex', 'UserPromptSubmit', codex_prompt('work'), T0 + 2, store, limits, env) is None
        assert hook.decide('codex', 'PreToolUse', codex_pre('Bash', {'command': 'ls'}, 'c2'), T0 + 3, store, limits, env) is None

        # Even if the file is rewritten with another stale payload, the latch stays silent.
        _write_spend_signal(env, [], generated_at=now_ms - 650_000, stale_after_ms=600_000)
        assert hook.decide('claude-code', 'PreToolUse', claude_pre('Bash', {'command': 'ls'}, 'c3'), T0 + 4, store, limits, env) is None
        assert hook.decide('codex', 'PreToolUse', codex_pre('Bash', {'command': 'ls'}, 'c4'), T0 + 5, store, limits, env) is None

        assert len(desktop_alerts) == 1
        title, body, _ = desktop_alerts[0]
        assert title == 'turn-pause: spend protection off'
        assert 'is stale' in body
        assert notices == []

    def test_staleness_alert_records_error_and_guards_unresolvable_obs_dir(self, tmp_path, monkeypatch, notices):
        from turn_pause import spend

        calls = []
        monkeypatch.setattr(
            hook.notify,
            'desktop',
            lambda title, body, *, env: calls.append((title, body)) or 'notify-send: missing binary',
        )
        bad_env = {
            'PATH': '/usr/bin:/bin',
            'HOME': str(tmp_path / 'home'),
            'XDG_STATE_HOME': 'relative/state',
            'XDG_RUNTIME_DIR': str(tmp_path / 'run'),
        }
        (tmp_path / 'home').mkdir()
        (tmp_path / 'run').mkdir()
        store = Store(tmp_path / 'pause')
        limits = tmp_path / 'limits.toml'
        limits.write_bytes(DEFAULTS_PATH.read_bytes())

        assert hook.decide('claude-code', 'UserPromptSubmit', claude_prompt('work'), T0, store, limits, bad_env) is None
        assert hook.decide('claude-code', 'PreToolUse', claude_pre('Bash', {'command': 'ls'}, 'c1'), T0 + 1, store, limits, bad_env) is None
        assert len(calls) == 1
        assert calls[0][0] == 'turn-pause: spend protection off'
        assert calls[0][1].startswith('spend-signals.json is unreadable')
        latch = spend.read_latch(store.dir)
        assert latch.outage is not None
        assert latch.outage['outcome'] == 'error'
        assert latch.outage['error'] == 'notify-send: missing binary'

