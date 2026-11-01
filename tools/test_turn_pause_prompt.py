"""Prompt rules: the genuine-prompt test, typed text and the budget directive."""
import pytest

from turn_pause import prompt
from turn_pause.prompt import Budget, Malformed


@pytest.mark.parametrize('text,expected', [
    ('fix the bug', True), ('<task-notification>done</task-notification>', False),
    ('<system-reminder>x</system-reminder>', False), ('<pasted_content id="1">x</pasted_content id="1"> look', True),
    ('   ', False), ('', False),
])
def test_is_genuine_claude(text, expected): assert prompt.is_genuine(text, 'claude-code') is expected

def test_is_genuine_codex_agents_injection(): assert not prompt.is_genuine('# AGENTS.md instructions', 'codex')

def test_codex_agents_header_is_genuine_for_claude(): assert prompt.is_genuine('# AGENTS.md notes', 'claude-code')

def test_typed_text_removes_pasted_blocks():
    assert prompt.typed_text('a <pasted_content id="1">x\ny</pasted_content id="1"> b').split() == ['a', 'b']

def test_budget_first_line(): assert prompt.parse_budget('budget: 12h\nrun the sweep') == Budget(43200, None, None, None)
def test_budget_named_counts(): assert prompt.parse_budget('budget: 10h, 2000 calls, 80 agents') == Budget(36000, 2000, 80, None)
def test_budget_compactions(): assert prompt.parse_budget('budget: 2h, 4 compactions') == Budget(7200, None, None, 4)
def test_budget_key_case_insensitive(): assert prompt.parse_budget('Budget: 1h') == Budget(3600, None, None, None)
def test_budget_minutes_and_fraction(): assert prompt.parse_budget('budget: 90m').seconds == 5400 and prompt.parse_budget('budget: 1.5h').seconds == 5400

@pytest.mark.parametrize('text', [
    'please review\nbudget: 100h', '```\nbudget: 100h\n```', '> budget: 100h',
    '<pasted_content id="1">budget: 100h</pasted_content id="1">',
    '', 'run it',
])
def test_budget_examples_are_silent(text): assert prompt.parse_budget(text) is None

def test_budget_after_pasted_block_is_first_typed_line():
    text = '<pasted_content id="1">spec</pasted_content id="1">\nbudget: 3h'
    assert prompt.parse_budget(text) == Budget(10800, None, None, None)

def test_second_budget_line_ignored(): assert prompt.parse_budget('budget: 2h\nbudget: 100h') == Budget(7200, None, None, None)
def test_budget_malformed(): assert isinstance(prompt.parse_budget('budget: 12 hours please'), Malformed)

@pytest.mark.parametrize('text', ['budget:', 'budget: 0h', 'budget: 2h, 5 widgets', 'budget: 2h, 5 calls, 6 calls', 'budget: 2h,'])
def test_budget_malformed_cases(text): assert isinstance(prompt.parse_budget(text), Malformed)
