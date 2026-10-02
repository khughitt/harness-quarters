import datetime as dt
import importlib.machinery
import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).with_name("trial-arm")
loader = importlib.machinery.SourceFileLoader("trial_arm", str(SCRIPT))
spec = importlib.util.spec_from_loader("trial_arm", loader)
ta = importlib.util.module_from_spec(spec)
sys.modules["trial_arm"] = ta
loader.exec_module(ta)

TRIAL_TEXT = """---
id: flow-trial-1
factor: flow
arms: ["on", "off"]
projects: [tack, obs]
enroll: 2026-10-05..2026-11-29
close_by: 2027-01-10
follow_up_to: 2027-02-09
read_on: 2027-02-16
source: [tack-7d9375]
---

Body.
"""
TRIAL = ta.parse_trial(TRIAL_TEXT, "fixture")
T = TRIAL.id
BEFORE = "2026-10-01T10:00:00Z"
IN = "2026-10-06T10:00:00Z"
LATER = "2026-12-01T10:00:00Z"


def rec(tid, *, parent=None, process="direct", status="doing", notes=()):
    task = {"id": tid, "title": tid, "status": status, "notes": [
        {"at": at, "by": "main", "text": text} for at, text in notes]}
    if process is not None:
        task["process"] = process
    if parent is not None:
        task["parent"] = parent
    return task


def tree(*records):
    return ta.Tree({r["id"]: r for r in records}, T)


def pick(arm, prefix="tack", skip=()):
    """The first id `<prefix>-a0000N` whose arm under the fixture trial is `arm`."""
    for n in range(1000):
        tid = f"{prefix}-a{n:05x}"
        if tid not in skip and ta.arm_of(T, tid) == arm:
            return tid
    raise AssertionError("no id found")


def test_parse_trial_reads_the_fields():
    assert TRIAL.projects == ("tack", "obs")
    assert TRIAL.enroll == (dt.date(2026, 10, 5), dt.date(2026, 11, 29))
    assert TRIAL.close_by == dt.date(2027, 1, 10)
    assert TRIAL.read_on == dt.date(2027, 2, 16)


@pytest.mark.parametrize("old,new", [
    ("follow_up_to: 2027-02-09", "follow_up_to: 2027-02-10"),
    ("read_on: 2027-02-16", "read_on: 2027-02-09"),
    ("enroll: 2026-10-05..2026-11-29", "enroll: 2026-10-05..2027-01-10"),
    ("enroll: 2026-10-05..2026-11-29", "enroll: 2026-10-05"),
])
def test_parse_trial_refuses_broken_date_chain(old, new):
    with pytest.raises(ta.TrialError):
        ta.parse_trial(TRIAL_TEXT.replace(old, new), "fixture")


def test_parse_trial_refuses_other_factors():
    with pytest.raises(ta.TrialError, match="factor"):
        ta.parse_trial(TRIAL_TEXT.replace("factor: flow", "factor: model"), "fixture")


def test_load_trials_refuses_overlap_on_a_project(tmp_path):
    (tmp_path / "a.md").write_text(TRIAL_TEXT)
    (tmp_path / "b.md").write_text(TRIAL_TEXT.replace("id: flow-trial-1", "id: flow-trial-2")
                                   .replace("projects: [tack, obs]", "projects: [obs]"))
    with pytest.raises(ta.TrialError, match="overlap"):
        ta.load_trials(tmp_path)


def test_trial_for_is_active_from_enroll_start_through_close_by(tmp_path):
    trials = [TRIAL]
    assert ta.trial_for(trials, "tack", dt.date(2026, 10, 4)) is None
    assert ta.trial_for(trials, "tack", dt.date(2026, 10, 5)) is TRIAL
    assert ta.trial_for(trials, "obs", dt.date(2027, 1, 10)) is TRIAL
    assert ta.trial_for(trials, "tack", dt.date(2027, 1, 11)) is None
    assert ta.trial_for(trials, "relay", dt.date(2026, 10, 6)) is None


def test_arm_of_is_the_sha256_low_bit_of_the_first_byte():
    import hashlib
    for root in ("tack-000001", "obs-abcdef", "tack-7d9375"):
        bit = hashlib.sha256(f"{T}:{root}".encode()).digest()[0] & 1
        assert ta.arm_of(T, root) == ("on" if bit else "off")
    assert {ta.arm_of(T, f"tack-{n:06x}") for n in range(20)} == {"on", "off"}


def test_lifecycle_reads_markers_in_order():
    task = rec("tack-000001", notes=[
        (IN, "started"), ("2026-10-10T00:00:00Z", "done"),
        ("2026-12-15T00:00:00Z", "resumed"), ("2027-01-05T00:00:00Z", "done")])
    assert ta.first_start(task).date() == dt.date(2026, 10, 6)
    assert ta.first_done(task).date() == dt.date(2026, 10, 10)
    assert ta.state_on(task, dt.date(2026, 12, 20)) == "open"
    assert ta.state_on(task, dt.date(2027, 1, 10)) == "done"
    assert ta.reopened(task, dt.date(2027, 1, 10)) is True
    assert ta.reopened(task, dt.date(2026, 12, 1)) is False


def test_state_on_counts_a_close_on_the_day_and_not_the_day_after():
    task = rec("tack-000001", notes=[(IN, "started"), ("2027-01-11T00:30:00Z", "done")])
    assert ta.state_on(task, dt.date(2027, 1, 10)) == "open"
    assert ta.state_on(task, dt.date(2027, 1, 11)) == "done"
    shelved = rec("tack-000002", notes=[(IN, "started"), (LATER, "shelved: later")])
    assert ta.state_on(shelved, dt.date(2027, 1, 10)) == "shelved"


def test_gates_past_scoped_ignores_scoped():
    task = rec("tack-000001", notes=[(IN, "gate: scoped — step of tack-0 plan"),
                                     (IN, "gate: implementing .worktrees/x")])
    assert ta.gates_past_scoped(task) == ["implementing"]
    assert ta.gated(rec("tack-000002", notes=[(IN, "gate: scoped — adopted")])) is True
    assert ta.gates_past_scoped(rec("tack-000003", notes=[(IN, "gate: scoped — adopted")])) == []


def test_units_climb_through_parents_with_process_only():
    goal = rec("tack-100000", process=None)
    plan = rec("tack-200000", parent="tack-100000", process="planned")
    step = rec("tack-300000", parent="tack-200000", process="direct")
    loose = rec("tack-400000", parent="tack-100000")
    t = tree(goal, plan, step, loose)
    assert t.computed_root("tack-300000") == "tack-200000"
    assert t.computed_root("tack-400000") == "tack-400000"
    assert t.computed_root("tack-200000") == "tack-200000"
    assert t.members("tack-200000") == ["tack-200000", "tack-300000"]


def test_the_climb_never_crosses_projects():
    parent = rec("obs-200000", process="planned")
    child = rec("tack-300000", parent="obs-200000")
    assert tree(parent, child).computed_root("tack-300000") == "tack-300000"


def test_resolved_unit_follows_a_root_recorded_elsewhere():
    origin = rec("tack-100000", process="planned")
    detached = rec("tack-200000", process="planned",
                   notes=[(IN, f"arm: {T} — unit tack-100000 — not enrolled")])
    child = rec("tack-300000", parent="tack-200000")
    t = tree(origin, detached, child)
    assert t.resolved_unit("tack-300000") == "tack-100000"
    assert t.unit_of("tack-200000") == "tack-100000"


def test_decide_enrolls_by_the_earliest_start_in_the_unit():
    root = pick("on")
    t = tree(rec(root, process="planned", notes=[(IN, "started")]),
             rec("tack-f00001", parent=root, notes=[(LATER, "started")]))
    assert ta.decide(TRIAL, t, root) == ta.Decision(True, "on", None, False)


def test_decide_excludes_a_unit_with_a_pre_window_start():
    root = pick("on")
    t = tree(rec(root, process="planned", notes=[(BEFORE, "started")]),
             rec("tack-f00001", parent=root, notes=[(IN, "started")]))
    d = ta.decide(TRIAL, t, root)
    assert d == ta.Decision(False, None, f"unit {root} first started 2026-10-01, outside enroll", False)


def test_decide_returns_none_before_any_start():
    root = pick("off")
    assert ta.decide(TRIAL, tree(rec(root)), root) is None


def test_decide_reads_a_recorded_decision_and_never_re_decides():
    root = pick("on")
    t = tree(rec(root, process="planned", notes=[(IN, "started"), (IN, f"trial: {T} — enrolled — flow on")]),
             rec("tack-f00001", parent=root, notes=[(BEFORE, "started")]))
    assert ta.decide(TRIAL, t, root) == ta.Decision(True, "on", None, True)


def test_decision_of_accepts_repeats_and_refuses_disagreement():
    root = pick("on")
    same = rec(root, notes=[(IN, f"trial: {T} — enrolled — flow on"), (IN, f"trial: {T} — enrolled — flow on")])
    assert ta.decision_of(same, T) == ta.Decision(True, "on", None, True)
    differ = rec(root, notes=[(IN, f"trial: {T} — enrolled — flow on"),
                              (IN, f"trial: {T} — not enrolled: not started")])
    with pytest.raises(ta.TrialError, match="decision"):
        ta.decision_of(differ, T)


def test_trial_notes_parse():
    task = rec("tack-000001", notes=[
        (IN, f"arm: {T} — unit tack-100000 — flow on"),
        (IN, f"arm: {T} — moved to unit tack-200000 — flow off"),
        (IN, f"arm: {T} — override: user asked for flow"),
        (IN, "arm: other-trial — unit tack-9 — flow off")])
    assert ta.member_of(task, T) == ("tack-100000", "on")
    assert ta.moves_of(task, T) == [("tack-200000", "off")]
    assert ta.overridden(task, T) is True
    assert ta.member_of(rec("tack-000002", notes=[(IN, f"arm: {T} — unit tack-1 — not enrolled")]), T) == ("tack-1", None)
