"""Both declared Codex homes retain root hooks and register the worker guard once."""
import json
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
COMMAND = '~/d/ops/hooks/claim-guard --harness codex'


@pytest.mark.parametrize('file,home', [('hooks.json', 'codex'),
                                     ('hooks.work.json', 'codex-work')])
def test_both_codex_homes_guard_root_and_worker(file, home):
    hooks = json.loads((ROOT / 'codex' / file).read_text())['hooks']
    for event in ('Stop', 'SubagentStop'):
        commands = [h['command'] for group in hooks.get(event, [])
                    for h in group['hooks'] if h['type'] == 'command']
        assert commands.count(COMMAND) == 1
    others = [h['command'] for group in hooks['Stop'] for h in group['hooks']
              if h['command'] != COMMAND]
    assert others == ['~/d/familiar/bin/familiar hook --agent codex Stop',
                      '~/.local/bin/harness-state-refresh']
    manifest = tomllib.loads((ROOT / 'links.toml').read_text())
    assert manifest['harness'][home]['links']['hooks.json'] == f'codex/{file}'
