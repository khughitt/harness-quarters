"""Committed hook images retain their approved runtime independently of the CLI pin."""
import json
import shlex
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
HOOK_VERSION = 'v0.1.1'  # Hook upgrades have a separate approval gate from the CLI pin.
FILES = ['claude/settings.json', 'codex/hooks.json', 'codex/work/hooks.json']


def parse_relay_command(command):
    argv = shlex.split(command)
    if len(argv) < 2 or not argv[1].endswith('/relay/bin/relay.js'):
        return None
    assert len(argv) == 10
    assert argv[0] == '/usr/bin/node'
    assert Path(argv[1]).is_absolute()
    assert argv[1].endswith(f'/.local/share/relay/{HOOK_VERSION}/node_modules/relay/bin/relay.js')
    assert argv[2:4] == ['hook', '--harness']
    assert argv[5] == '--outer-ms'
    assert argv[7] == '--subscribers'
    assert Path(argv[8]).is_absolute()
    assert argv[8].endswith('/.config/relay/subscribers.json')
    return argv[4], int(argv[6]), argv[9]


def hook_entries(file):
    hooks = json.loads((ROOT / file).read_text())['hooks']
    return [(event, group.get('matcher'), hook)
            for event, groups in hooks.items() for group in groups
            for hook in group['hooks']]


def relay_entries(file):
    return [(event, matcher, *parsed, hook['timeout'])
            for event, matcher, hook in hook_entries(file)
            if (parsed := parse_relay_command(hook['command'])) is not None]


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


@pytest.mark.parametrize('file', FILES[1:])
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


@pytest.mark.parametrize('file', FILES)
def test_no_familiar_hook_or_native_guard(file):
    for _, _, hook in hook_entries(file):
        assert 'familiar hook' not in hook['command']
        assert 'claude-pretooluse' not in hook['command']


@pytest.mark.parametrize('file', FILES)
def test_native_entries_kept_in_order(file):
    native = {}
    for event, _, hook in hook_entries(file):
        if parse_relay_command(hook['command']) is None:
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
