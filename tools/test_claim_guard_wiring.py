"""Both declared Codex homes retain root hooks and register the worker guard once."""
import json
import tomllib
from pathlib import Path

import pytest

from test_relay_wiring import parse_relay_command

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
    assert parse_relay_command(others[1]) == ('codex', 600000, 'Stop')
    manifest = tomllib.loads((ROOT / 'links.toml').read_text())
    assert manifest['harness'][home]['links']['hooks.json'] == f'codex/{file}'
