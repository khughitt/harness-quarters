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


import json
import os
import stat
import subprocess


def test_first_lookup_decides_the_unit_and_records_the_task():
    root = pick("on")
    t = tree(rec(root, process="planned", notes=[(IN, "started")]))
    result = ta.lookup(TRIAL, t, root)
    assert result.line == f"{T}: flow on (unit {root})"
    assert result.writes == [(root, f"trial: {T} — enrolled — flow on"),
                             (root, f"arm: {T} — unit {root} — flow on")]


def test_lookup_on_a_child_uses_the_unit_arm_and_writes_once():
    root = pick("off")
    child = "tack-f00001"
    t = tree(rec(root, process="planned", notes=[(IN, "started"), (IN, f"trial: {T} — enrolled — flow off"),
                                                 (IN, f"arm: {T} — unit {root} — flow off")]),
             rec(child, parent=root, notes=[(LATER, "started")]))
    first = ta.lookup(TRIAL, t, child)
    assert first.line == f"{T}: flow off (unit {root})"
    assert first.writes == [(child, f"arm: {T} — unit {root} — flow off")]
    t.records[child]["notes"].append({"at": LATER, "by": "main", "text": first.writes[0][1]})
    assert ta.lookup(TRIAL, t, child).writes == []


def apply(t, writes):
    for target, text in writes:
        t.records[target]["notes"].append({"at": LATER, "by": "main", "text": text})


def child_first_then_root_moved():
    """A child's lookup decides the unit; then the root moves under an off parent before
    its own lookup. Returns the tree, the two roots, the child and both lookups."""
    root, child = pick("on"), "tack-f00001"
    off_root = pick("off")
    t = tree(rec(root, process="planned", notes=[(IN, "started")]),
             rec(child, parent=root, notes=[(IN, "started")]),
             rec(off_root, process="planned", notes=[(IN, "started"), (IN, f"trial: {T} — enrolled — flow off"),
                                                     (IN, f"arm: {T} — unit {off_root} — flow off")]))
    first = ta.lookup(TRIAL, t, child)
    apply(t, first.writes)
    t.records[root]["parent"] = off_root
    moved = ta.lookup(TRIAL, t, root)
    apply(t, moved.writes)
    return t, root, off_root, child, first, moved


def test_a_child_first_lookup_freezes_the_root_membership_too():
    t, root, off_root, child, first, moved = child_first_then_root_moved()
    assert first.writes == [(root, f"trial: {T} — enrolled — flow on"),
                            (root, f"arm: {T} — unit {root} — flow on"),
                            (child, f"arm: {T} — unit {root} — flow on")]
    assert moved.line == f"{T}: flow off (moved from unit {root} to unit {off_root})"
    assert moved.writes == [(root, f"arm: {T} — moved to unit {off_root} — flow off")]
    assert t.unit_of(root) == root and t.unit_of(child) == root


def test_lookup_on_a_child_started_after_enroll_ends_keeps_the_unit_arm():
    root = pick("on")
    child = "tack-f00001"
    t = tree(rec(root, process="planned", notes=[(IN, "started")]),
             rec(child, parent=root, notes=[("2026-12-20T00:00:00Z", "started")]))
    assert ta.lookup(TRIAL, t, child).line == f"{T}: flow on (unit {root})"


def test_lookup_records_not_enrolled_members_too():
    root = pick("on")
    child = "tack-f00001"
    t = tree(rec(root, process="planned", notes=[(BEFORE, "started")]),
             rec(child, parent=root, notes=[(IN, "started")]))
    result = ta.lookup(TRIAL, t, child)
    assert result.line == f"not enrolled: unit {root} first started 2026-10-01, outside enroll"
    assert result.writes == [
        (root, f"trial: {T} — not enrolled: unit {root} first started 2026-10-01, outside enroll"),
        (root, f"arm: {T} — unit {root} — not enrolled"),
        (child, f"arm: {T} — unit {root} — not enrolled")]


def test_a_child_detached_from_an_excluded_unit_stays_out_with_its_children():
    root, child, grandchild = pick("on"), "tack-f00001", "tack-f00002"
    t = tree(rec(root, process="planned", notes=[(BEFORE, "started"),
                                                 (BEFORE, f"trial: {T} — not enrolled: unit {root} first started 2026-10-01, outside enroll")]),
             rec(child, process="planned", notes=[(IN, "started"), (IN, f"arm: {T} — unit {root} — not enrolled")]),
             rec(grandchild, parent=child, notes=[(LATER, "started")]))
    assert ta.lookup(TRIAL, t, child).line.startswith("not enrolled: unit")
    result = ta.lookup(TRIAL, t, grandchild)
    assert result.line.startswith("not enrolled: unit")
    assert result.writes == [(grandchild, f"arm: {T} — unit {root} — not enrolled")]


def test_a_task_moved_from_an_on_unit_under_an_off_parent_follows_the_destination():
    on_root = pick("on")
    off_root = pick("off")
    task = "tack-f00001"
    t = tree(rec(on_root, process="planned", notes=[(IN, "started"), (IN, f"trial: {T} — enrolled — flow on")]),
             rec(off_root, process="planned", notes=[(IN, "started"), (IN, f"trial: {T} — enrolled — flow off")]),
             rec(task, parent=off_root, notes=[(IN, "started"), (IN, f"arm: {T} — unit {on_root} — flow on")]))
    result = ta.lookup(TRIAL, t, task)
    assert result.line == f"{T}: flow off (moved from unit {on_root} to unit {off_root})"
    assert result.writes == [(task, f"arm: {T} — moved to unit {off_root} — flow off")]
    t.records[task]["notes"].append({"at": LATER, "by": "main", "text": result.writes[0][1]})
    assert ta.lookup(TRIAL, t, task).writes == []
    assert t.unit_of(task) == on_root


def test_a_move_under_a_not_enrolled_parent_follows_its_actual_workflow():
    on_root = pick("off")
    outside = pick("on", skip=(on_root,))
    task = "tack-f00001"
    base = [rec(on_root, process="planned", notes=[(IN, "started"), (IN, f"trial: {T} — enrolled — flow off")]),
            rec(task, parent=outside, notes=[(IN, "started"), (IN, f"arm: {T} — unit {on_root} — flow off")])]
    flowing = tree(*base, rec(outside, process="planned", notes=[
        (BEFORE, "started"), (BEFORE, "gate: scoped — adopted"),
        (BEFORE, f"trial: {T} — not enrolled: unit {outside} first started 2026-10-01, outside enroll")]))
    assert ta.lookup(TRIAL, flowing, task).line == f"{T}: flow on (moved from unit {on_root} to unit {outside})"
    plain = tree(*base, rec(outside, process="planned", notes=[
        (BEFORE, "started"),
        (BEFORE, f"trial: {T} — not enrolled: unit {outside} first started 2026-10-01, outside enroll")]))
    assert ta.lookup(TRIAL, plain, task).line == f"{T}: flow off (moved from unit {on_root} to unit {outside})"


def test_a_move_under_a_detached_parent_follows_the_parent_not_its_excluded_origin():
    """The physical root decides execution: a parent detached from an excluded unit that
    runs flow carries its children under flow, even though its analysis unit has no gates."""
    a = pick("off")
    origin = pick("on", skip=(a,))
    parent, task = "tack-e00001", "tack-f00001"
    t = tree(rec(a, process="planned", notes=[(IN, "started"), (IN, f"trial: {T} — enrolled — flow off")]),
             rec(origin, process="planned", notes=[
                 (BEFORE, "started"),
                 (BEFORE, f"trial: {T} — not enrolled: unit {origin} first started 2026-10-01, outside enroll")]),
             rec(parent, process="planned", notes=[
                 (IN, "started"), (IN, f"arm: {T} — unit {origin} — not enrolled"),
                 (IN, "gate: implementing .worktrees/p")]),
             rec(task, parent=parent, notes=[(IN, "started"), (IN, f"arm: {T} — unit {a} — flow off")]))
    result = ta.lookup(TRIAL, t, task)
    assert result.line == f"{T}: flow on (moved from unit {a} to unit {parent})"
    assert result.writes == [(task, f"arm: {T} — moved to unit {parent} — flow on")]
    assert t.unit_of(task) == a


def test_a_new_child_of_a_detached_flow_parent_is_not_enrolled_and_writes_no_move():
    origin = pick("on")
    parent, child = "tack-e00001", "tack-f00002"
    t = tree(rec(origin, process="planned", notes=[
                 (BEFORE, "started"),
                 (BEFORE, f"trial: {T} — not enrolled: unit {origin} first started 2026-10-01, outside enroll")]),
             rec(parent, process="planned", notes=[(IN, "started"), (IN, f"arm: {T} — unit {origin} — not enrolled"),
                                                   (IN, "gate: implementing .worktrees/p")]),
             rec(child, parent=parent, notes=[(LATER, "started")]))
    result = ta.lookup(TRIAL, t, child)
    assert result.line.startswith("not enrolled: unit")
    assert result.writes == [(child, f"arm: {T} — unit {origin} — not enrolled")]


def test_a_task_with_an_earlier_start_moved_under_an_enrolled_root_leaves_it_enrolled():
    root = pick("on")
    t = tree(rec(root, process="planned", notes=[(IN, "started"), (IN, f"trial: {T} — enrolled — flow on")]),
             rec("tack-f00001", parent=root, notes=[(BEFORE, "started")]))
    assert ta.lookup(TRIAL, t, "tack-f00001").line == f"{T}: flow on (unit {root})"


def test_check_refuses_a_recorded_arm_that_contradicts_the_function():
    root = pick("on")
    t = tree(rec(root, notes=[(IN, "started"), (IN, f"arm: {T} — unit {root} — flow off")]))
    with pytest.raises(ta.TrialError, match="contradicts"):
        ta.lookup(TRIAL, t, root)


def test_check_refuses_a_decision_that_contradicts_the_function():
    root = pick("on")
    t = tree(rec(root, notes=[(IN, "started"), (IN, f"trial: {T} — enrolled — flow off")]))
    with pytest.raises(ta.TrialError, match="contradicts"):
        ta.check(TRIAL, t)


def test_lookup_on_a_missing_task_raises():
    with pytest.raises(ta.MissingTask):
        ta.lookup(TRIAL, tree(), "tack-ffffff")


FAKE_TASKS = """#!/usr/bin/env python3
import json, os, sys
store = os.environ["FAKE_TASKS_STORE"]
data = json.load(open(store))
cmd, args = sys.argv[1], [a for a in sys.argv[2:] if a != "--json"]
with open(os.environ["FAKE_TASKS_LOG"], "a") as log:
    log.write(json.dumps(sys.argv[1:]) + "\\n")
if os.environ.get("TASKS_FORMAT") == "pretty" and "--json" not in sys.argv:
    print("---\\nid: pretty output, not JSON")
elif cmd == "list":
    print(json.dumps({"tasks": [{"id": i} for i in data]}))
elif cmd == "show":
    print(json.dumps({"task": data[args[0]]}))
elif cmd == "note":
    data[args[0]]["notes"].append({"at": "2026-10-06T12:00:00Z", "by": "main", "text": args[1]})
    json.dump(data, open(store, "w"))
    print(json.dumps({"ok": True}))
"""


@pytest.fixture
def fake_tasks(tmp_path, monkeypatch):
    exe = tmp_path / "tasks"
    exe.write_text(FAKE_TASKS)
    exe.chmod(exe.stat().st_mode | stat.S_IEXEC)
    store, log = tmp_path / "store.json", tmp_path / "log.jsonl"
    log.write_text("")
    monkeypatch.setenv("FAKE_TASKS_STORE", str(store))
    monkeypatch.setenv("FAKE_TASKS_LOG", str(log))
    monkeypatch.chdir(tmp_path)

    def load(*records):
        store.write_text(json.dumps({r["id"]: r for r in records}))
        return ta.Tasks(str(exe))
    load.store, load.log = store, log
    return load


def trials_dir(tmp_path):
    d = tmp_path / "trials"
    d.mkdir(exist_ok=True)
    (d / "flow-trial-1.md").write_text(TRIAL_TEXT)
    return d


def test_main_lookup_writes_the_notes_through_tasks(fake_tasks, tmp_path, capsys):
    root = pick("on")
    tasks = fake_tasks(rec(root, process="planned", notes=[(IN, "started")]))
    code = ta.main([root], tasks=tasks, trials_dir=trials_dir(tmp_path), today=dt.date(2026, 10, 6))
    assert code == 0
    assert capsys.readouterr().out.strip() == f"{T}: flow on (unit {root})"
    notes = [n["text"] for n in json.loads(fake_tasks.store.read_text())[root]["notes"]]
    assert notes[-2:] == [f"trial: {T} — enrolled — flow on", f"arm: {T} — unit {root} — flow on"]


def test_main_outside_any_trial_touches_nothing(fake_tasks, tmp_path, capsys):
    tasks = fake_tasks()
    code = ta.main(["relay-000001"], tasks=tasks, trials_dir=trials_dir(tmp_path), today=dt.date(2026, 10, 6))
    assert (code, capsys.readouterr().out.strip()) == (0, "not enrolled: no trial for relay")
    assert fake_tasks.log.read_text() == ""


def test_main_strips_trailing_periods(fake_tasks, tmp_path, capsys):
    root = pick("off")
    tasks = fake_tasks(rec(root, notes=[(IN, "started")]))
    assert ta.main([root + ".."], tasks=tasks, trials_dir=trials_dir(tmp_path), today=dt.date(2026, 10, 6)) == 0
    assert capsys.readouterr().out.strip() == f"{T}: flow off (unit {root})"


def test_main_exit_codes(fake_tasks, tmp_path, capsys):
    tasks = fake_tasks()
    assert ta.main(["tack-ffffff"], tasks=tasks, trials_dir=trials_dir(tmp_path), today=dt.date(2026, 10, 6)) == 1
    d = trials_dir(tmp_path)
    (d / "b.md").write_text(TRIAL_TEXT.replace("id: flow-trial-1", "id: flow-trial-2"))
    assert ta.main(["tack-ffffff"], tasks=tasks, trials_dir=d, today=dt.date(2026, 10, 6)) == 2


def test_the_client_forces_json_when_pretty_output_is_configured(fake_tasks, tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("TASKS_FORMAT", "pretty")
    root = pick("on")
    tasks = fake_tasks(rec(root, process="planned", notes=[(IN, "started")]))
    assert ta.main([root], tasks=tasks, trials_dir=trials_dir(tmp_path), today=dt.date(2026, 10, 6)) == 0
    assert capsys.readouterr().out.strip() == f"{T}: flow on (unit {root})"


def test_records_reads_the_local_checkout_for_its_own_prefix(fake_tasks, tmp_path, monkeypatch):
    tasks = fake_tasks(rec("tack-000001"))
    monkeypatch.setattr(ta, "local_prefix", lambda cwd=None: "tack")
    tasks.records("tack")
    tasks.records("obs")
    calls = [json.loads(line) for line in fake_tasks.log.read_text().splitlines() if line.startswith('["list"')]
    assert all("--json" in call for call in calls)
    assert "--project" not in calls[0]
    assert calls[1][calls[1].index("--project") + 1] == "obs"


def test_local_prefix_reads_the_checkout_config(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / "tasks").mkdir()
    (tmp_path / "tasks" / ".config.toml").write_text('prefix = "obs"\n')
    assert ta.local_prefix(tmp_path) == "obs"
    bare = tmp_path / "bare"
    subprocess.run(["git", "init", "-q", str(bare)], check=True)
    assert ta.local_prefix(bare) is None


def enrolled(root, arm, *extra_notes, process="planned"):
    return rec(root, process=process, notes=[(IN, "started"), (IN, f"trial: {T} — enrolled — flow {arm}"),
                                             (IN, f"arm: {T} — unit {root} — flow {arm}"), *extra_notes])


def test_census_lists_enrolled_units_with_members_and_state():
    root = pick("on")
    t = tree(enrolled(root, "on", (IN, "gate: implementing .worktrees/x"), ("2026-11-01T00:00:00Z", "done")),
             rec("tack-f00001", parent=root, notes=[(IN, "started"), (IN, "gate: scoped — step"),
                                                    ("2026-10-20T00:00:00Z", "done")]))
    out = ta.census(TRIAL, t, TRIAL.close_by)
    [unit] = out["units"]
    assert unit["root"] == root and unit["arm"] == "on" and unit["decision"] == "recorded"
    assert unit["state"] == "done" and unit["first_done"] == "2026-11-01T00:00:00Z"
    assert [m["task"] for m in unit["members"]] == [root, "tack-f00001"]
    assert unit["treated"] is True and unit["compliant"] is True
    assert unit["stratum"]["project"] == "tack"
    assert out["decided_late"] == {"on": 0, "off": 0}


def test_scoped_gates_alone_leave_a_unit_untreated():
    root = pick("on")
    t = tree(enrolled(root, "on", (IN, "gate: scoped — adopted"), (LATER, "done")))
    [unit] = ta.census(TRIAL, t, TRIAL.close_by)["units"]
    assert (unit["treated"], unit["compliant"]) == (False, False)


def test_dropped_and_open_units_are_unassessable():
    a, b = pick("off"), pick("off", skip=(pick("off"),))
    t = tree(enrolled(a, "off", (LATER, "dropped"), process="direct"),
             enrolled(b, "off", process="direct"))
    units = {u["root"]: u for u in ta.census(TRIAL, t, TRIAL.close_by)["units"]}
    assert (units[a]["state"], units[a]["compliant"]) == ("dropped", None)
    assert (units[b]["state"], units[b]["compliant"]) == ("open", None)


def test_a_unit_with_no_lookups_is_decided_late():
    root = pick("off")
    t = tree(rec(root, notes=[(IN, "started"), (LATER, "done")]))
    out = ta.census(TRIAL, t, TRIAL.close_by)
    assert out["units"][0]["decision"] == "decided late"
    assert out["decided_late"] == {"on": 0, "off": 1}


def test_not_enrolled_units_are_left_out():
    root = pick("on")
    t = tree(rec(root, notes=[(BEFORE, "started")]))
    assert ta.census(TRIAL, t, TRIAL.close_by)["units"] == []


def test_a_moved_task_stays_in_its_recorded_unit_and_breaks_compliance():
    on_root, off_root, task = pick("on"), pick("off"), "tack-f00001"
    t = tree(enrolled(on_root, "on", (IN, "gate: implementing x"), (LATER, "done")),
             enrolled(off_root, "off", (LATER, "done")),
             rec(task, parent=off_root, notes=[(IN, "started"), (IN, f"arm: {T} — unit {on_root} — flow on"),
                                               (IN, f"arm: {T} — moved to unit {off_root} — flow off")]))
    out = ta.census(TRIAL, t, TRIAL.close_by)
    units = {u["root"]: u for u in out["units"]}
    assert task in [m["task"] for m in units[on_root]["members"]]
    assert task not in [m["task"] for m in units[off_root]["members"]]
    assert units[on_root]["compliant"] is False
    assert out["conflicts"] == [{"task": task, "recorded": on_root, "computed": off_root}]


def test_an_override_breaks_compliance():
    root = pick("off")
    t = tree(enrolled(root, "off", (IN, f"arm: {T} — override: user asked to stop"),
                      (LATER, "done"), process="direct"))
    [unit] = ta.census(TRIAL, t, TRIAL.close_by)["units"]
    assert (unit["treated"], unit["compliant"]) == (False, False)


def test_census_state_reads_close_by_and_keeps_the_first_done_date():
    root = pick("off")
    t = tree(enrolled(root, "off", ("2026-10-10T00:00:00Z", "done"), ("2026-12-15T00:00:00Z", "resumed"),
                      ("2027-01-11T00:00:00Z", "done"), process="direct"))
    [unit] = ta.census(TRIAL, t, TRIAL.close_by)["units"]
    assert unit["first_done"] == "2026-10-10T00:00:00Z"
    assert unit["state"] == "open" and unit["reopened"] is True


def test_a_root_moved_after_a_child_first_lookup_stays_in_its_unit_in_the_census():
    t, root, off_root, child, _, _ = child_first_then_root_moved()
    t.records[root]["notes"].append({"at": LATER, "by": "main", "text": "done"})
    units = {u["root"]: u for u in ta.census(TRIAL, t, TRIAL.close_by)["units"]}
    assert [m["task"] for m in units[root]["members"]] == [root, child]
    assert units[root]["members"][0]["moves"] == [{"unit": off_root, "arm": "off"}]
    assert units[root]["compliant"] is False
    assert root not in [m["task"] for m in units[off_root]["members"]]


def test_evidence_after_the_cutoff_leaves_the_census_unchanged():
    root = pick("on")
    before = tree(enrolled(root, "on", (LATER, "done")))
    after = tree(enrolled(root, "on", (LATER, "done"), ("2027-01-20T00:00:00Z", "gate: implementing late"),
                          ("2027-01-21T00:00:00Z", f"arm: {T} — override: late"),
                          ("2027-01-22T00:00:00Z", f"arm: {T} — moved to unit tack-ffffff — flow off")))
    assert ta.census(TRIAL, after, TRIAL.close_by) == ta.census(TRIAL, before, TRIAL.close_by)
    [unit] = ta.census(TRIAL, after, TRIAL.close_by)["units"]
    assert (unit["treated"], unit["compliant"]) == (False, False)


def test_compliance_and_status_lines_flag_a_halt():
    units = [{"root": f"tack-{i}", "arm": "on", "state": "done", "treated": i >= 4, "compliant": i >= 4}
             for i in range(16)] + \
            [{"root": f"obs-{i}", "arm": "off", "state": "done", "treated": False, "compliant": True}
             for i in range(15)]
    summary = ta.compliance(units)
    assert summary["on"] == {"enrolled": 16, "assessable": 16, "compliant": 12, "rate": 0.75}
    lines = ta.status_lines(TRIAL, {"as_of": "2026-11-20", "units": units})
    assert any(line.startswith("halt: compliance below 0.8 in on") for line in lines)


def test_main_census_reads_every_trial_project(fake_tasks, tmp_path, capsys):
    tack_root, obs_root = pick("on"), pick("off", prefix="obs")
    tasks = fake_tasks(enrolled(tack_root, "on", (LATER, "done")),
                       enrolled(obs_root, "off", (LATER, "done"), process="direct"))
    assert ta.main(["census", T], tasks=tasks, trials_dir=trials_dir(tmp_path), today=dt.date(2027, 2, 20)) == 0
    out = json.loads(capsys.readouterr().out)
    assert sorted(u["root"] for u in out["units"]) == sorted([tack_root, obs_root])
    assert out["as_of"] == "2027-01-10"


def test_the_shipped_trial_file_loads_with_the_spec_dates():
    [trial] = [t for t in ta.load_trials(ta.TRIALS) if t.id == "flow-trial-1"]
    assert trial.projects == ("tack", "obs")
    assert trial.enroll == (dt.date(2026, 10, 5), dt.date(2026, 11, 29))
    assert (trial.close_by, trial.follow_up_to, trial.read_on) == (
        dt.date(2027, 1, 10), dt.date(2027, 2, 9), dt.date(2027, 2, 16))


# --- final review fixes (F1-F11) ---

def test_the_shipped_trial_file_parses_without_yaml():
    assert [t.id for t in ta.load_trials(ta.TRIALS)] == ["flow-trial-1"]
    assert "import yaml" not in SCRIPT.read_text()


def test_unquoted_arms_are_strings_not_booleans():
    trial = ta.parse_trial(TRIAL_TEXT.replace('arms: ["on", "off"]', "arms: [on, off]"), "fixture")
    assert trial.factor == "flow"
    assert ta.parse_frontmatter("a: [on, 'off', \"x\"]\nb: 'q'\n\nc: plain\n", "f") == {
        "a": ["on", "off", "x"], "b": "q", "c": "plain"}


@pytest.mark.parametrize("front", ["id flow-trial-1", "a: [on, off", "a:\n  b: 1", "  a: 1", "a: 1\njunk"])
def test_malformed_frontmatter_raises_trial_error(front):
    with pytest.raises(ta.TrialError, match="fixture"):
        ta.parse_trial(f"---\n{front}\n---\n", "fixture")


def test_the_script_runs_where_yaml_cannot_be_imported(tmp_path):
    code = ("import sys, runpy; sys.modules['yaml'] = None; sys.argv = ['trial-arm', 'relay-000001']; "
            f"runpy.run_path({str(SCRIPT)!r}, run_name='__main__')")
    r = subprocess.run([sys.executable, "-c", code], text=True, capture_output=True)
    assert (r.returncode, r.stdout.strip()) == (0, "not enrolled: no trial for relay"), r.stderr


def write_exe(tmp_path, body):
    exe = tmp_path / "badtasks"
    exe.write_text("#!/bin/sh\n" + body)
    exe.chmod(exe.stat().st_mode | stat.S_IEXEC)
    return str(exe)


def test_main_exits_2_when_tasks_prints_non_json(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    tasks = ta.Tasks(write_exe(tmp_path, "echo not json\n"))
    assert ta.main(["tack-ffffff"], tasks=tasks, trials_dir=trials_dir(tmp_path), today=dt.date(2026, 10, 6)) == 2
    assert "tasks list" in capsys.readouterr().err


def test_main_exits_2_when_tasks_json_lacks_fields(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    tasks = ta.Tasks(write_exe(tmp_path, "echo '{}'\n"))
    assert ta.main(["tack-ffffff"], tasks=tasks, trials_dir=trials_dir(tmp_path), today=dt.date(2026, 10, 6)) == 2


def test_main_exits_2_when_tasks_is_missing(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    tasks = ta.Tasks(str(tmp_path / "nonexistent"))
    assert ta.main(["tack-ffffff"], tasks=tasks, trials_dir=trials_dir(tmp_path), today=dt.date(2026, 10, 6)) == 2
    assert "nonexistent" in capsys.readouterr().err


def test_local_prefix_exits_2_when_git_is_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("PATH", str(tmp_path))
    with pytest.raises(ta.TrialError, match="git"):
        ta.local_prefix(str(tmp_path))


def test_a_parent_cycle_is_refused_by_lookup_and_census():
    a, b = "tack-aaaaa1", "tack-aaaaa2"
    t = tree(rec(a, parent=b, notes=[(IN, "started")]), rec(b, parent=a, notes=[(IN, "started")]))
    with pytest.raises(ta.TrialError, match="cycle"):
        ta.lookup(TRIAL, t, a)
    with pytest.raises(ta.TrialError, match="cycle"):
        ta.census(TRIAL, t, dt.date(2026, 12, 1))


def test_load_trials_refuses_a_missing_directory_but_not_an_empty_one(tmp_path):
    assert ta.load_trials(tmp_path) == []
    with pytest.raises(ta.TrialError, match="missing"):
        ta.load_trials(tmp_path / "missing")


def test_a_prose_gate_note_does_not_gate_a_task():
    prose = rec("tack-aaaaa1", notes=[(IN, "gate: and more")])
    real = rec("tack-aaaaa2", notes=[(IN, "gate: planned")])
    assert not ta.gated(prose) and ta.gated(real)
    assert ta.gates_past_scoped(prose) == [] and ta.gates_past_scoped(real) == ["planned"]


def test_closed_counts_as_treated():
    assert "closed" in ta.TREATED


def test_lifecycle_reads_notes_in_time_order():
    task = rec("tack-aaaaa1", notes=[(LATER, "done"), (IN, "started")])
    assert ta.first_start(task) == dt.datetime(2026, 10, 6, 10, tzinfo=dt.timezone.utc)
    assert ta.state_on(task, dt.date(2026, 10, 7)) == "open"
    assert ta.state_on(task, dt.date(2026, 12, 2)) == "done"
    assert ta.first_done(task) is not None


def test_override_notes_accept_hand_written_separators():
    for sep in ("—", "–", "--", "-"):
        task = rec("tack-aaaaa1", notes=[(IN, f"arm: {T} {sep} override: user said so")])
        assert ta.overridden(task, T), sep


def test_census_refuses_a_unit_whose_root_has_no_record():
    ghost = "tack-zzzzzz"
    arm = ta.arm_of(T, ghost)
    child = rec("tack-aaaaa1", notes=[(IN, "started"), (IN, f"arm: {T} — unit {ghost} — flow {arm}")])
    with pytest.raises(ta.TrialError, match=ghost):
        ta.census(TRIAL, tree(child), dt.date(2026, 12, 1))
