"""Each harness home wires the turn-pause hook exactly once per supported event."""
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
COMMON = ('UserPromptSubmit', 'PreToolUse', 'PostToolUse', 'Stop', 'SubagentStop',
          'SessionEnd', 'SubagentStart')
# Claude Code adds PostToolUseFailure and the compaction pair (hook-compact-event probed);
# Codex has no failure event and its compaction hooks are unprobed (unknown).
EVENTS = {
    'claude-code': COMMON + ('PostToolUseFailure', 'PreCompact', 'PostCompact'),
    'codex': COMMON,
}
ABSENT_CODEX = ('PostToolUseFailure', 'PreCompact', 'PostCompact')
ALL_TOOLS = ('PreToolUse', 'PostToolUse', 'PostToolUseFailure')
# Codex clamps a SessionEnd hook's timeout to 3 s (the relay-cutover plan's Codex
# SessionEnd row); every other turn-pause entry declares 5 s.
TIMEOUTS = {('codex', 'SessionEnd'): 3}
DEFAULT_TIMEOUT = 5
CASES = [('claude/settings.json', 'claude-code'), ('codex/hooks.json', 'codex'),
         ('codex/work/hooks.json', 'codex')]


def entries(file, event):
    hooks = json.loads((ROOT / file).read_text())['hooks']
    return [(group, h) for group in hooks.get(event, []) for h in group['hooks']
            if h.get('type') == 'command' and '/turn-pause ' in h['command']]


@pytest.mark.parametrize('file,harness', CASES)
def test_one_entry_per_supported_event(file, harness):
    for event in EVENTS[harness]:
        found = entries(file, event)
        assert len(found) == 1, (file, event, len(found))
        group, hook = found[0]
        command = hook['command']
        assert command.startswith('~/'), command  # home-relative, as the claim-guard entries
        assert command.endswith(f'/hq/tools/turn-pause --harness {harness} {event}'), command
        assert hook['timeout'] == TIMEOUTS.get((harness, event), DEFAULT_TIMEOUT), (file, event)
        if event in ALL_TOOLS:
            assert group.get('matcher') in ('*', '', None) and group.get('matcher') != 'Bash'


@pytest.mark.parametrize('file,harness', CASES)
def test_no_entry_for_unsupported_events(file, harness):
    hooks = json.loads((ROOT / file).read_text())['hooks']
    for event in hooks:
        if event not in EVENTS[harness]:
            assert not entries(file, event), (file, event)
    if harness == 'codex':
        for event in ABSENT_CODEX:
            assert not entries(file, event)
