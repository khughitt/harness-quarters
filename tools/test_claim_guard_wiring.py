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
              if h['command'] != COMMAND]
    assert len(others) == 2
    assert others[0] == '~/.local/bin/harness-state-refresh'
    assert parse_relay_command(others[1], HOOK_VERSIONS[f'codex/{file}']) == ('codex', 600000, 'Stop')
    manifest = tomllib.loads((ROOT / 'links.toml').read_text())
    assert manifest['harness'][home]['links']['hooks.json'] == f'codex/{file}'


def test_agy_home_guards_pretooluse_and_stop():
    hooks = json.loads((ROOT / 'agy' / 'hooks.json').read_text())['hq']
    pre_tool = [
        (group['matcher'], h['command'])
        for group in hooks['PreToolUse']
        for h in group['hooks']
        if h.get('type') == 'command'
    ]
    assert pre_tool == [('run_command', '~/d/hq/agy/hook PreToolUse ~/d/ops/hooks/relay-guard')]
    stop = [h['command'] for h in hooks['Stop'] if h.get('type') == 'command']
    assert stop == ['~/d/hq/agy/hook Stop', '~/.local/bin/harness-state-refresh']
    manifest = tomllib.loads((ROOT / 'links.toml').read_text())
    assert manifest['harness']['agy-config']['links']['hooks.json'] == 'agy/hooks.json'
