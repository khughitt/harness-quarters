"""The limits file and how a budget directive scales it."""
import hashlib

import pytest

from turn_pause import limits
from turn_pause.limits import Limits
from turn_pause.prompt import Budget


def test_defaults_file(): assert limits.load()[0] == Limits(57600, 500, 60, 2)


def test_default_spawn_budgets_scale_and_named_agents_override():
    defaults = limits.load()[0]
    assert limits.with_budget(defaults, Budget(43200, None, None, None)).spawns == 45
    assert limits.with_budget(defaults, Budget(172800, None, None, None)).spawns == 180
    assert limits.with_budget(defaults, Budget(43200, None, 17, None)).spawns == 17

def test_load_returns_file_sha256():
    assert limits.load()[1] == hashlib.sha256(limits.DEFAULTS_PATH.read_bytes()).hexdigest()

def test_defaults_file_names_spec_and_approval():
    text = limits.DEFAULTS_PATH.read_text()
    assert '2026-11-01-turn-pause-design' in text and '2026-11-01' in text

def test_budget_scales_unnamed(): assert limits.with_budget(Limits(14400, 500, 30, 2), Budget(43200, None, None, None)) == Limits(43200, 1500, 90, 6)

def test_budget_named_overrides(): assert limits.with_budget(Limits(14400, 500, 30, 2), Budget(36000, 2000, 80, None)) == Limits(36000, 2000, 80, 5)

def test_scaling_rounds_up(): assert limits.with_budget(Limits(14400, 500, 30, 2), Budget(14401, None, None, None)) == Limits(14401, 501, 31, 3)


@pytest.mark.parametrize('field', ['active_seconds', 'calls', 'spawns', 'compactions'])
@pytest.mark.parametrize('value', [0, -1])
def test_load_refuses_a_non_positive_limit(tmp_path, field, value):
    values = {**dict(active_seconds=14400, calls=500, spawns=30, compactions=2), field: value}
    path = tmp_path / 'limits.toml'
    path.write_text(''.join(f'{k} = {v}\n' for k, v in values.items()))
    with pytest.raises(ValueError, match=field):
        limits.load(path)


@pytest.mark.parametrize('text, field', [
    ('active_seconds = \n', 'line 1'),
    ('active_seconds = 1\ncalls = 2\ncompactions = 1\n', 'spawns'),
])
def test_load_names_the_file_for_a_syntax_error_or_a_missing_key(tmp_path, text, field):
    path = tmp_path / 'limits.toml'
    path.write_text(text)
    with pytest.raises(ValueError) as error:
        limits.load(path)
    assert str(path) in str(error.value) and field in str(error.value)


@pytest.mark.parametrize('seconds, text', [(0, '0h00m'), (59.9, '0h00m'), (960, '0h16m'), (4320, '1h12m'),
                                           (57600, '16h00m'), (360000, '100h00m')])
def test_duration_names_its_units(seconds, text): assert limits.duration(seconds) == text
