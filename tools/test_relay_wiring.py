"""Committed hook images retain their approved runtime independently of the CLI pin."""
import json
import shlex
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FILES = ['claude/settings.json', 'codex/hooks.json', 'codex/work/hooks.json', 'agy/hooks.json']
# Hook upgrades have a separate approval gate from the CLI pin, per harness; routing agy
# through relay v0.3.0 moves every relayed harness to v0.3.0 so snapshots and subscribers
# naming agy are accepted across Claude Code, Codex, and agy.
HOOK_VERSIONS = {
    FILES[0]: 'v0.3.0',
    FILES[1]: 'v0.3.0',
    FILES[2]: 'v0.3.0',
    FILES[3]: 'v0.3.0',
}


def parse_relay_command(command, version):
    argv = shlex.split(command)
    if len(argv) < 2 or not argv[1].endswith('/relay/bin/relay.js'):
        return None
    assert len(argv) == 10
    assert argv[0] == '/usr/bin/node'
    assert Path(argv[1]).is_absolute()
    assert argv[1].endswith(f'/.local/share/relay/{version}/node_modules/relay/bin/relay.js')
    assert argv[2:4] == ['hook', '--harness']
    assert argv[5] == '--outer-ms'
    assert argv[7] == '--subscribers'
    assert Path(argv[8]).is_absolute()
    assert argv[8].endswith('/.config/relay/subscribers.json')
    return argv[4], int(argv[6]), argv[9]


def hook_entries(file):
    doc = json.loads((ROOT / file).read_text())
    if file == 'agy/hooks.json':
        hq = doc['hq']
        entries = []
        for event, items in hq.items():
            if event == 'enabled':
                continue
            if event in ('PreToolUse', 'PostToolUse'):
                for group in items:
                    for hook in group['hooks']:
                        entries.append((event, group.get('matcher'), hook))
            else:
                for hook in items:
                    entries.append((event, None, hook))
        return entries
    hooks = doc['hooks']
    return [(event, group.get('matcher'), hook)
            for event, groups in hooks.items() for group in groups
            for hook in group['hooks']]


def relay_entries(file):
    entries = []
    for event, matcher, hook in hook_entries(file):
        parsed = parse_relay_command(hook['command'], HOOK_VERSIONS[file])
        if parsed is not None:
            assert hook['timeout'] * 1000 == parsed[1]
            entries.append((event, matcher, *parsed, hook['timeout']))
    return entries


def test_claude_relay_events():
    assert relay_entries(FILES[0]) == [
        ('SessionStart', 'startup|resume', 'claude-code', 600000, 'SessionStart', 600),
        ('UserPromptSubmit', None, 'claude-code', 600000, 'UserPromptSubmit', 600),
        ('PreToolUse', '*', 'claude-code', 600000, 'PreToolUse', 600),
        ('Notification', 'idle_prompt', 'claude-code', 600000, 'Notification:idle_prompt', 600),
        ('Notification', 'permission_prompt', 'claude-code', 600000, 'Notification:permission_prompt', 600),
        ('Stop', None, 'claude-code', 600000, 'Stop', 600),
        ('StopFailure', None, 'claude-code', 600000, 'StopFailure', 600),
        ('SessionEnd', None, 'claude-code', 60000, 'SessionEnd', 60),
    ]


@pytest.mark.parametrize('file', FILES[1:3])
def test_codex_relay_events(file):
    assert sorted(relay_entries(file)) == sorted([
        ('SessionStart', None, 'codex', 600000, 'SessionStart', 600),
        ('SubagentStart', None, 'codex', 600000, 'SubagentStart', 600),
        ('UserPromptSubmit', None, 'codex', 600000, 'UserPromptSubmit', 600),
        ('PreToolUse', '*', 'codex', 600000, 'PreToolUse', 600),
        ('PermissionRequest', None, 'codex', 600000, 'PermissionRequest', 600),
        ('Stop', None, 'codex', 600000, 'Stop', 600),
        ('SubagentStop', None, 'codex', 600000, 'SubagentStop', 600),
        ('SessionEnd', None, 'codex', 3000, 'SessionEnd', 3),
    ])


def test_agy_relay_events():
    assert relay_entries(FILES[3]) == [
        ('SessionStart', None, 'agy', 60000, 'SessionStart', 60),
        ('PreToolUse', '*', 'agy', 60000, 'PreToolUse', 60),
        ('Stop', None, 'agy', 60000, 'Stop', 60),
    ]


@pytest.mark.parametrize('file', FILES)
def test_no_familiar_hook_or_native_guard(file):
    for _, _, hook in hook_entries(file):
        assert 'familiar hook' not in hook['command']
        assert 'claude-pretooluse' not in hook['command']
        assert 'relay-guard' not in hook['command']


@pytest.mark.parametrize('file', FILES)
def test_native_entries_kept_in_order(file):
    native = {}
    for event, _, hook in hook_entries(file):
        if '/turn-pause ' in hook['command']:
            continue  # pinned by test_turn_pause_wiring.py
        if parse_relay_command(hook['command'], HOOK_VERSIONS[file]) is None:
            native.setdefault(event, []).append(hook['command'])
    if file == FILES[0]:
        assert native == {
            'SessionStart': ['~/d/ops/hooks/claude-sessionstart',
                             '~/d/ops/hooks/claude-provenance',
                             '~/d/lore/hooks/claude-profile', '~/d/ops/hooks/capture-notice'],
            'PostModelSwitch': ['~/d/ops/hooks/claude-provenance'],
            'Stop': ['~/d/ops/hooks/claim-guard --harness claude-code',
                     '~/.local/bin/harness-state-refresh'],
            'PostToolUse': ['~/d/ops/hooks/claude-posttooluse'],
            'PostToolUseFailure': ['~/d/ops/hooks/claude-posttooluse'],
        }
    elif file == FILES[3]:
        assert native == {
            'SessionStart': ['~/d/hq/agy/hook SessionStart ~/d/lore/hooks/claude-profile ~/d/ops/hooks/capture-notice'],
            'PreToolUse': ['~/d/hq/agy/hook PreToolUse'],
            'Stop': ['~/d/hq/agy/hook Stop', '~/.local/bin/harness-state-refresh'],
        }
    else:
        session_start = ['~/d/lore/hooks/claude-profile']
        if file == FILES[1]:
            session_start.append('~/d/ops/hooks/capture-notice')
        assert native == {
            'SessionStart': session_start,
            'Stop': ['~/d/ops/hooks/claim-guard --harness codex',
                     '~/.local/bin/harness-state-refresh'],
            'SubagentStop': ['~/d/ops/hooks/claim-guard --harness codex'],
        }


def test_statusline_unchanged():
    assert json.loads((ROOT / FILES[0]).read_text())['statusLine'] == {
        'type': 'command', 'command': '~/d/familiar/bin/familiar statusline',
        'refreshInterval': 2,
    }
