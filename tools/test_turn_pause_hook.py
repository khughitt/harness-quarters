"""The turn-pause hook: payloads in, decisions out (spec: The unit, Counters, Warning,
pause, notification, Resuming and granting more, State and integrity).

Payloads are the recorded hook fixtures under tools/fixtures/turn-pause/hooks/ with the
fields a case needs replaced. Shapes no fixture holds (Claude Code PreCompact,
PostCompact, the compaction summarizer's SubagentStop, Codex prompts and stops) are
built from the raw probe logs' keys and say so where they are built."""
import copy
import json
import os
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
    'turn paused: {limit} over its limit (active {a} of {A}, calls {c}/{C}, spawns {s}/{S}, '
    'compactions {k}/{K}). Start nothing new and stop the work you already started: interrupt '
    'your subagents and the sessions you launched, stop your background calls and processes, '
    'and set any active goal of yours to paused. Then write the pause report the turn-pause '
    'rule describes, park your task --waiting-on user --reason decision, and end your turn. If '
    'another agent launched this session, park any claim --waiting-on agent for that agent and '
    'return a short status (done, left, running) instead of a pause report. Only bookkeeping, '
    'plain reads and stopping your own work are allowed now; hq pause status shows the counts.')
CHILD_TEXT = (
    "turn paused by your controller's limit ({limit}). Start nothing new and stop the work you "
    'already started (your background calls and processes), park any claim --waiting-on agent '
    'for your controller, and return a short status (done, left, running). Do not write a '
    'pause report.')
LIMITS_CHANGED_TEXT = (
    'turn paused: the turn limits file changed mid-turn (active {a} of {A}, calls {c}/{C}, spawns {s}/{S}, '
    'compactions {k}/{K}). ' + ROOT_TEXT[ROOT_TEXT.index('Start nothing new'):])
WARNING_TEXT = 'turn-pause: {limit} at {n}% ({used} of {value}). Finish a coherent step and prepare your report.'
BUDGET_TEXT = 'turn-pause: budget for this turn: active {a}, {c} calls, {s} spawns, {k} compactions.'
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

def test_501st_root_call_is_denied_with_the_root_text_after_one_warning(tmp_path, notices):
    d = Driver(tmp_path, 'claude-code')
    d.prompt('a long job')
    for i in range(1, 501):
        out = d.bash('ls')
        assert not denied(out), i
        expected = WARNING_TEXT.format(limit='calls', n=75, used=375, value=500) if i == 375 else None
        assert context(out) == expected, i
    out = d.bash('ls')
    assert denied(out)
    assert reason(out) == ROOT_TEXT.format(limit='calls', a='0:08', A='4:00', c=501, C=500,
                                           s=0, S=30, k=0, K=2)
    assert 'stop the work you already started: interrupt your subagents and the sessions you launched' in reason(out)
    assert 'If another agent launched this session, park any claim --waiting-on agent' in reason(out)
    assert d.state().paused == 'calls' and len(notices) == 1


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


def test_continue_ends_the_pause_resets_counters_and_sets_no_budget(tmp_path, notices):
    d = Driver(tmp_path, 'claude-code')
    d.pause_on_calls()
    assert d.prompt('continue') is None
    st = d.state()
    assert st.paused is None and st.turn.calls == 0 and st.grace_used == {}
    assert st.turn.limits == load(d.limits)[0]
    assert st.budget_note is None and st.notified is False


def test_budget_directive_confirms_and_raises_limits(tmp_path):
    d = Driver(tmp_path, 'claude-code')
    out = d.prompt('budget: 12h\nRun the whole migration.')
    assert context(out) == BUDGET_TEXT.format(a='12:00', c=1500, s=90, k=6)
    assert d.state().turn.limits == Limits(43200, 1500, 90, 6)


def test_malformed_budget_adds_its_context_once(tmp_path):
    d = Driver(tmp_path, 'claude-code')
    text = 'budget: soon\nRun the whole migration.'
    bad = parse_budget(text)
    assert isinstance(bad, Malformed)
    assert context(d.prompt(text)) == MALFORMED_TEXT.format(reason=bad.reason)
    assert d.state().turn.limits == load(d.limits)[0]
    assert d.bash('ls') is None


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
    assert reason(out) == LIMITS_CHANGED_TEXT.format(a='0:00', A='4:00', c=2, C=500, s=0, S=30, k=0, K=2)
    assert reason(out).startswith('turn paused: the turn limits file changed mid-turn (active 0:00 of 4:00, '
                                  'calls 2/500, spawns 0/30, compactions 0/2). Start nothing new and stop')
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
            'wiring': CHECKOUT / 'codex' / 'hooks.json',
            'home-link': Path(d.env['HOME']) / '.claude' / 'settings.json',
            'facts': Path(adapters.SNAPSHOT)}[target]
    out, _ = d.pre('Edit', {'file_path': str(path), 'old_string': '500', 'new_string': '5000'})
    assert denied(out)
    assert 'protected' in reason(out)
    assert d.state().paused is None


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

def test_codex_31_spawns_count_31_calls_and_spawns_then_the_tree_pauses(tmp_path, notices):
    d = Driver(tmp_path, 'codex')
    d.prompt('fan out')
    for i in range(31):
        assert not denied(d('PreToolUse', codex_spawn(f'w{i}', d.call_id()))), i
        d('SubagentStart', codex_subagent_start(f'01a19708-0000-0000-0000-{i:012d}'))
    st = d.state()
    assert st.turn.calls == 31 and st.turn.spawns == 31
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


HEAVY = ('dataclasses', 'typing', 'tempfile', 'pathlib', 'hashlib', 'shlex', 'string', 'turn_pause.allowlist')


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
def test_entry_refuses_a_33_mb_payload_of_many_nodes_well_under_a_second(tmp_path, element):
    run_entry(tmp_path, 'UserPromptSubmit', claude_prompt('work'))
    raw = _many_nodes(element)
    assert len(raw) < hook.MAX_PAYLOAD_BYTES
    start = time.monotonic()
    r = run_entry(tmp_path, 'PreToolUse', raw)
    assert time.monotonic() - start < 1.0
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
