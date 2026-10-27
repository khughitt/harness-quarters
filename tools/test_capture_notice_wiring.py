"""The personal Claude Code and Codex homes run ops's capture notice at session start."""
import json
from pathlib import Path

from test_relay_wiring import HOOK_VERSIONS, parse_relay_command

ROOT = Path(__file__).resolve().parents[1]
COMMAND = '~/d/ops/hooks/capture-notice'


def session_start(path):
    groups = json.loads(path.read_text())['hooks']['SessionStart']
    return [h['command'] for group in groups for h in group['hooks']
            if h['type'] == 'command']


def test_claude_registers_capture_notice_once():
    assert session_start(ROOT / 'claude' / 'settings.json').count(COMMAND) == 1


def test_codex_appends_capture_notice_after_trusted_entries():
    # The cutover re-trusts every shifted index; new entries still go last.
    commands = session_start(ROOT / 'codex' / 'hooks.json')
    assert len(commands) == 3
    assert commands[:2] == ['~/d/lore/hooks/claude-profile', COMMAND]
    assert parse_relay_command(commands[2], HOOK_VERSIONS['codex/hooks.json']) == ('codex', 600000, 'SessionStart')


def test_codex_work_home_has_no_capture_notice():
    hooks = json.loads((ROOT / 'codex' / 'work' / 'hooks.json').read_text())['hooks']
    commands = [h['command'] for groups in hooks.values() for group in groups
                for h in group['hooks'] if h['type'] == 'command']
    assert COMMAND not in commands
