"""The personal Claude Code, Codex and agy homes register the capture notice once."""
import json
from pathlib import Path

from test_relay_wiring import HOOK_VERSIONS, expected_agy_bridge, parse_relay_command

ROOT = Path(__file__).resolve().parents[1]
COMMAND = '~/d/ops/hooks/capture-notice'


def session_start(path):
    groups = json.loads(path.read_text())['hooks']['SessionStart']
    return [h['command'] for group in groups for h in group['hooks']
            if h['type'] == 'command']


def test_claude_runs_capture_notice_through_relay_once():
    # hq-8185d3 moved the notice into the donor-2 relay composition.
    commands = session_start(ROOT / 'harnesses/claude' / 'settings.json')
    assert [parse_relay_command(c, HOOK_VERSIONS['harnesses/claude/settings.json']) for c in commands] == [
        ('claude-code', 600000, 'SessionStart', 'donor-2')]
    subscribers = json.loads((ROOT / 'relay/subscribers.donor-2.template.json').read_text())['subscribers']
    assert [s['argv'] for s in subscribers].count(['mindful', 'notice', 'session-start']) == 1


def test_codex_appends_capture_notice_after_trusted_entries():
    # The cutover re-trusts every shifted index; new entries still go last.
    commands = session_start(ROOT / 'harnesses/codex' / 'hooks.json')
    assert len(commands) == 3
    assert commands[:2] == ['~/d/lore/hooks/claude-profile', COMMAND]
    assert parse_relay_command(commands[2], HOOK_VERSIONS['harnesses/codex/hooks.json']) == ('codex', 600000, 'SessionStart', 'shared')


def test_codex_work_home_has_no_capture_notice():
    hooks = json.loads((ROOT / 'harnesses/codex' / 'work' / 'hooks.json').read_text())['hooks']
    commands = [h['command'] for groups in hooks.values() for group in groups
                for h in group['hooks'] if h['type'] == 'command']
    assert COMMAND not in commands


def test_agy_registers_profile_and_capture_notice_once():
    hooks = json.loads((ROOT / 'harnesses/agy' / 'hooks.json').read_text())['hq']
    commands = [h['command'] for h in hooks['SessionStart'] if h.get('type') == 'command']
    assert len(commands) == 2
    assert commands[0] == expected_agy_bridge('SessionStart')
    assert parse_relay_command(commands[1], HOOK_VERSIONS['harnesses/agy/hooks.json']) == ('agy', 60000, 'SessionStart', 'shared')
