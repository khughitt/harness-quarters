"""The limits file and how a budget directive scales it."""
import hashlib

from turn_pause import limits
from turn_pause.limits import Limits
from turn_pause.prompt import Budget


def test_defaults_file(): assert limits.load()[0] == Limits(14400, 500, 30, 2)

def test_load_returns_file_sha256():
    assert limits.load()[1] == hashlib.sha256(limits.DEFAULTS_PATH.read_bytes()).hexdigest()

def test_defaults_file_names_spec_and_approval():
    text = limits.DEFAULTS_PATH.read_text()
    assert '2026-11-01-turn-pause-design' in text and '2026-11-01' in text

def test_budget_scales_unnamed(): assert limits.with_budget(Limits(14400, 500, 30, 2), Budget(43200, None, None, None)) == Limits(43200, 1500, 90, 6)

def test_budget_named_overrides(): assert limits.with_budget(Limits(14400, 500, 30, 2), Budget(36000, 2000, 80, None)) == Limits(36000, 2000, 80, 5)

def test_scaling_rounds_up(): assert limits.with_budget(Limits(14400, 500, 30, 2), Budget(14401, None, None, None)) == Limits(14401, 501, 31, 3)
