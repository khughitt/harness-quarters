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

@pytest.mark.parametrize('text', ['budget:', 'budget: 0h', 'budget: 2h, 5 widgets', 'budget: 2h, 5 calls, 6 calls', 'budget: 2h,',
                                  'budget: 2h, 0 agents', 'budget: 2h, 0 calls', 'budget: 2h, 0 compactions'])
def test_budget_malformed_cases(text): assert isinstance(prompt.parse_budget(text), Malformed)

def test_budget_oversized_duration_is_malformed():
    assert isinstance(prompt.parse_budget('budget: ' + '9' * 400 + 'h'), Malformed)
    assert isinstance(prompt.parse_budget('budget: 1.' + '9' * 400 + 'h'), Malformed)

def test_budget_oversized_count_is_malformed():
    assert isinstance(prompt.parse_budget('budget: 2h, ' + '9' * 5000 + ' calls'), Malformed)

def test_budget_unicode_digits_are_malformed():
    assert isinstance(prompt.parse_budget('budget: ٣h'), Malformed)
    assert isinstance(prompt.parse_budget('budget: 2h, ٣ calls'), Malformed)


X_DIGEST = '2d711642b726b04401627ca9fbac32f5c8530fb1903cc4db02258717921a4881'


def test_prompt_guards_empty_factory_does_not_share_containers():
    a, b = prompt.empty_guards(), prompt.empty_guards()
    a['cron'].append(X_DIGEST)
    a['wakeups'].append([X_DIGEST, 100, 200])
    assert b == {'cron': [], 'wakeups': []}


def test_capture_guards_normalizes_without_mutating_state():
    from turn_pause.state import RootState, Wakeup, state_dict
    import copy
    state = RootState('codex', 'r1', None)
    state.cron_jobs = {'one': ' x ', 'two': 'x'}
    state.wakeups = [Wakeup(' x ', 100, 200), Wakeup('x', 100, 200)]
    before = copy.deepcopy(state_dict(state))
    assert prompt.capture_guards(state) == {'cron': [X_DIGEST], 'wakeups': [[X_DIGEST, 100, 200]]}
    assert state_dict(state) == before


@pytest.mark.parametrize('now,want,remaining', [(99, 'turn', 1), (100, 'wake', 0),
                                               (200, 'wake', 0), (201, 'turn', 0)])
def test_guarded_prompt_kind_windows_and_precedence(now, want, remaining):
    guards = {'cron': [], 'wakeups': [[X_DIGEST, 100, 200]]}
    assert prompt.guarded_prompt_kind(guards, ' x ', now) == want
    assert len(guards['wakeups']) == remaining


def test_guarded_prompt_matches_wake_before_persistent_cron():
    guards = {'cron': [X_DIGEST], 'wakeups': [[X_DIGEST, 100, 200]]}
    assert prompt.guarded_prompt_kind(guards, 'x', 100) == 'wake'
    assert guards == {'cron': [X_DIGEST], 'wakeups': []}
    assert prompt.guarded_prompt_kind(guards, 'x', 101) == 'wake'
    assert guards == {'cron': [X_DIGEST], 'wakeups': []}
    assert prompt.guarded_prompt_kind(guards, 'different', 101) == 'turn'


def test_guarded_prompt_uses_utf8_and_only_strip_normalization():
    from hashlib import sha256
    digest = sha256('é'.encode('utf-8')).hexdigest()
    guards = {'cron': [digest], 'wakeups': []}
    assert prompt.guarded_prompt_kind(guards, '\u2003é\n', 1) == 'wake'
    assert prompt.guarded_prompt_kind(guards, 'É', 1) == 'turn'
    assert prompt.guarded_prompt_kind(guards, 'e\u0301', 1) == 'turn'
