"""Committed hook images retain their approved runtime independently of the CLI pin."""
from hashlib import sha256
import json
import shlex
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FILES = ['harnesses/claude/settings.json', 'harnesses/codex/hooks.json', 'harnesses/codex/work/hooks.json', 'harnesses/agy/hooks.json']
# Hook upgrades have a separate approval gate from the CLI pin, per harness. The v0.5.0
# cutover (hq-663049) moved every relayed harness together: schema-2 subscriber files are
# refused by v0.3.0 and schema-1 files by v0.5.0, so one host runs one subscriber schema.
HOOK_VERSIONS = {
    FILES[0]: 'v0.5.0',
    FILES[1]: 'v0.5.0',
    FILES[2]: 'v0.5.0',
    FILES[3]: 'v0.5.0',
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
    # The runtime and expanded subscriber bytes determine the deployed address.
    root = next(parent.parent for parent in Path(argv[1]).parents if parent.name == '.local')
    template = (ROOT / 'relay/subscribers.template.json').read_bytes()
    digest = sha256(template.replace(b'@HOME@', str(root).encode())).hexdigest()[:12]
    assert Path(argv[8]) == root / '.config/relay' / f'{version}-{digest}' / 'relay/subscribers.json'
    return argv[4], int(argv[6]), argv[9]


def hook_entries(file):
    doc = json.loads((ROOT / file).read_text())
    if file == 'harnesses/agy/hooks.json':
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


def expected_agy_bridge(event):
    # The checked-in homes can differ from the account running hosted tests.
    relay = next(hook for _, _, hook in hook_entries(FILES[1])
                 if parse_relay_command(hook['command'], 'v0.5.0'))
    runtime_root = Path(shlex.split(relay['command'])[1]).parents[4]
    if event == 'SessionStart':
        args = [event, '--runtime', str(runtime_root / 'v0.6.0/node_modules/relay'),
                '--delegate', 'lore hook profile-notice', '--delegate', 'mindful notice session-start']
    else:
        assert event == 'Stop'
        args = [event, '--runtime', str(runtime_root / 'v0.5.0/node_modules/relay'),
                '--guard', 'tasks hook claim-guard']
    return '~/d/hq/harnesses/agy/hook ' + shlex.join(args)


def test_claude_relay_events():
    assert relay_entries(FILES[0]) == [
        ('SessionStart', 'startup|resume', 'claude-code', 600000, 'SessionStart', 600),
        ('PostModelSwitch', None, 'claude-code', 60000, 'PostModelSwitch', 60),
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
            # relay's built-in provenance replaced ops claude-provenance on SessionStart
            # and PostModelSwitch; running both would export the stamps twice.
            'SessionStart': ['~/d/ops/hooks/claude-sessionstart',
                             '~/d/lore/hooks/claude-profile', '~/d/ops/hooks/capture-notice'],
            'Stop': ['~/d/ops/hooks/claim-guard --harness claude-code',
                     '~/.local/bin/harness-state-refresh'],
            # tt's native command counts test front-door use; ops owns it on PATH.
            'PostToolUse': ['tt-posttooluse'],
            'PostToolUseFailure': ['tt-posttooluse'],
        }
    elif file == FILES[3]:
        assert native == {
            'SessionStart': [expected_agy_bridge('SessionStart')],
            'PreToolUse': ['~/d/hq/harnesses/agy/hook PreToolUse'],
            'Stop': [expected_agy_bridge('Stop'), '~/.local/bin/harness-state-refresh'],
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


def test_agy_statusline():
    assert json.loads((ROOT / 'harnesses/agy/settings.json').read_text())['statusLine'] == {
        'type': 'command', 'command': '~/d/familiar/bin/familiar statusline',
        'enabled': True,
    }
