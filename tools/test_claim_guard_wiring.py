"""Both declared Codex homes retain root hooks and register the worker guard once."""
import json
import tomllib
from pathlib import Path

import pytest

from test_relay_wiring import HOOK_VERSIONS, parse_relay_command

ROOT = Path(__file__).resolve().parents[1]
COMMAND = '~/d/ops/hooks/claim-guard --harness codex'


@pytest.mark.parametrize('file,home', [('hooks.json', 'codex'),
                                     ('work/hooks.json', 'codex-work')])
def test_both_codex_homes_guard_root_and_worker(file, home):
    hooks = json.loads((ROOT / 'codex' / file).read_text())['hooks']
    for event in ('Stop', 'SubagentStop'):
        commands = [h['command'] for group in hooks.get(event, [])
                    for h in group['hooks'] if h['type'] == 'command']
        assert commands.count(COMMAND) == 1
    others = [h['command'] for group in hooks['Stop'] for h in group['hooks']
              if h['command'] != COMMAND
              and '/turn-pause ' not in h['command']]  # pinned by test_turn_pause_wiring.py
    assert len(others) == 2
    assert others[0] == '~/.local/bin/harness-state-refresh'
    assert parse_relay_command(others[1], HOOK_VERSIONS[f'codex/{file}']) == ('codex', 600000, 'Stop')
    manifest = tomllib.loads((ROOT / 'links.toml').read_text())
    assert manifest['harness'][home]['links']['hooks.json'] == f'codex/{file}'


def test_agy_home_guards_pretooluse_and_stop():
    hooks = json.loads((ROOT / 'agy' / 'hooks.json').read_text())['hq']
    pre_tool = [
        (group['matcher'], h['command'], h.get('timeout'))
        for group in hooks['PreToolUse']
        for h in group['hooks']
        if h.get('type') == 'command'
    ]
    assert len(pre_tool) == 2
    assert pre_tool[0] == ('run_command', '~/d/hq/agy/hook PreToolUse', None)
    assert pre_tool[1][0] == '*'
    assert pre_tool[1][2] == 60
    assert parse_relay_command(pre_tool[1][1], HOOK_VERSIONS['agy/hooks.json']) == ('agy', 60000, 'PreToolUse')

    stop = [(h['command'], h.get('timeout')) for h in hooks['Stop'] if h.get('type') == 'command']
    assert len(stop) == 3
    assert stop[:2] == [
        ('~/d/hq/agy/hook Stop', None),
        ('~/.local/bin/harness-state-refresh', None),
    ]
    assert stop[2][1] == 60
    assert parse_relay_command(stop[2][0], HOOK_VERSIONS['agy/hooks.json']) == ('agy', 60000, 'Stop')

    manifest = tomllib.loads((ROOT / 'links.toml').read_text())
    assert manifest['harness']['agy-config']['links']['hooks.json'] == 'agy/hooks.json'
