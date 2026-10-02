import datetime as dt
import importlib.machinery
import importlib.util
import io
import json
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).with_name("trial-verdict")
loader = importlib.machinery.SourceFileLoader("trial_verdict", str(SCRIPT))
spec = importlib.util.spec_from_loader("trial_verdict", loader)
tv = importlib.util.module_from_spec(spec)
sys.modules["trial_verdict"] = tv
loader.exec_module(tv)
ta = tv.ta

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
"""
TRIAL = ta.parse_trial(TRIAL_TEXT, "fixture")
START = "2026-10-06T10:00:00Z"
DONE = "2026-11-01T10:00:00Z"
MS = {START: 1791280800000, DONE: 1793527200000}


def ids(arm, count, offset=0):
    found, n = [], offset
    while len(found) < count:
        tid = f"tack-{n:06x}"
        if ta.arm_of(TRIAL.id, tid) == arm:
            found.append(tid)
        n += 1
    return found


def unit(root, *, delivered=True, defects=0, missing=False, compliant=True, state=None, children=()):
    """A census unit and its obs rows. `children` are (task, defects, missing) triples."""
    members, rows = [], []
    for task, task_defects, task_missing in [(root, defects, missing), *children]:
        done = DONE if delivered else None
        members.append({"task": task, "first_start": START, "first_done": done, "gates": [],
                        "override": False, "moves": []})
        if done and not task_missing:
            rows.append({"task": task, "first_start_ms": MS[START], "first_close_ms": MS[DONE],
                         "defects": task_defects, "changes": 0, "extensions": 0, "reopens": 0,
                         "output_tokens": 1000})
    census_unit = {"root": root, "arm": ta.arm_of(TRIAL.id, root), "decision": "recorded",
                   "enrolled_at": START, "first_done": DONE if delivered else None,
                   "state": state or ("done" if delivered else "open"), "reopened": False,
                   "stratum": {"project": "tack", "size": "s", "complexity": "low", "process": "direct"},
                   "treated": ta.arm_of(TRIAL.id, root) == "on",
                   "compliant": (compliant if delivered else None), "members": members}
    return census_unit, rows


def build(units, m4=None):
    census = {"trial": TRIAL.id, "as_of": "2027-01-10", "close_by": "2027-01-10",
              "units": [u for u, _ in units], "decided_late": {"on": 0, "off": 0}, "conflicts": []}
    report = {"units": [r for _, rows in units for r in rows],
              "unvalidated": {"measures": {} if m4 is None else {"m4": m4}}}
    return census, report


def arms(on_clean, on_n, off_clean, off_n, **kw):
    on, off = ids("on", on_n), ids("off", off_n, offset=10_000)
    return ([unit(r, defects=0 if i < on_clean else 1, **kw) for i, r in enumerate(on)]
            + [unit(r, defects=0 if i < off_clean else 1, **kw) for i, r in enumerate(off)])


def run(tmp_path, census, report, as_of="2027-02-16"):
    trial = tmp_path / "trial.md"
    trial.write_text(TRIAL_TEXT)
    path = tmp_path / "census.json"
    path.write_text(json.dumps(census))
    out = io.StringIO()
    code = tv.main([str(trial), "--census", str(path), "--as-of", as_of],
                   stdin=io.StringIO(json.dumps(report)), stdout=out)
    return code, out.getvalue().splitlines()


def test_fisher_two_sided_matches_the_tea_tasting_value():
    assert tv.fisher_two_sided(3, 1, 1, 3) == pytest.approx(0.4857142857)


def test_newcombe_matches_the_published_example():
    d, lo, hi = tv.newcombe(56, 70, 48, 80, z=1.959963984540054)
    assert (round(d, 4), round(lo, 4), round(hi, 4)) == (0.2, 0.0524, 0.3339)


def test_before_the_read_date_nothing_is_read(tmp_path):
    class Exploding(io.StringIO):
        def read(self, *a):
            raise AssertionError("stdin read")
    trial = tmp_path / "trial.md"
    trial.write_text(TRIAL_TEXT)
    out = io.StringIO()
    code = tv.main([str(trial), "--census", str(tmp_path / "absent.json"), "--as-of", "2027-02-15"],
                   stdin=Exploding(), stdout=out)
    assert code == 0 and out.getvalue().splitlines()[0] == "insufficient: before read date"


def test_unvalidated_gate(tmp_path):
    census, report = build(arms(100, 100, 100, 100), m4="E2")
    assert run(tmp_path, census, report)[1][0] == "insufficient: unvalidated"


def test_too_few(tmp_path):
    census, report = build(arms(99, 99, 100, 100))
    assert run(tmp_path, census, report)[1][0] == "insufficient: too few"


def test_low_compliance(tmp_path):
    units = arms(100, 100, 100, 100)
    for census_unit, _ in units[:25]:
        census_unit["compliant"] = False
    census, report = build(units)
    assert run(tmp_path, census, report)[1][0] == "insufficient: compliance"


def test_too_few_assessable_is_compliance(tmp_path):
    on = [unit(r, delivered=False) for r in ids("on", 100)]
    off = [unit(r) for r in ids("off", 100, offset=10_000)]
    census, report = build(on + off)
    assert run(tmp_path, census, report)[1][0] == "insufficient: compliance"


def test_flow_better_and_worse_and_no_difference(tmp_path):
    better = build(arms(90, 100, 70, 100))
    worse = build(arms(70, 100, 90, 100))
    same = build(arms(80, 100, 79, 100))
    assert run(tmp_path, *better)[1][0] == "flow-better"
    assert run(tmp_path, *worse)[1][0] == "flow-worse"
    code, lines = run(tmp_path, *same)
    assert (code, lines[0]) == (0, "no-difference-detected")
    assert lines[1].startswith("on 80/100, off 79/100, p ")


def test_missing_defect_data_bound(tmp_path):
    units = arms(100, 100, 100, 100)
    for census_unit, rows in units[:10]:
        rows.clear()
    census, report = build(units)
    code, lines = run(tmp_path, census, report)
    assert lines[0] != "insufficient: missing defect data"
    assert any(line.startswith("sensitivity") for line in lines)
    units = arms(100, 100, 100, 100)
    for census_unit, rows in units[:11]:
        rows.clear()
    assert run(tmp_path, *build(units))[1][0] == "insufficient: missing defect data"


def test_a_dropped_unit_without_rows_is_not_delivered_not_missing(tmp_path):
    units = arms(100, 100, 100, 100)
    root = ids("on", 1, offset=50_000)[0]
    units.append(unit(root, delivered=False, state="dropped"))
    code, lines = run(tmp_path, *build(units))
    assert lines[1].startswith("on 100/101,")


def test_a_child_defect_makes_the_unit_unclean(tmp_path):
    units = arms(100, 100, 100, 100)
    root = ids("on", 1, offset=50_000)[0]
    units.append(unit(root, children=[("tack-ffff01", 1, False)]))
    assert run(tmp_path, *build(units))[1][1].startswith("on 100/101,")


def test_a_known_defect_wins_over_a_missing_member(tmp_path):
    units = arms(100, 100, 100, 100)
    root = ids("on", 1, offset=50_000)[0]
    units.append(unit(root, defects=1, children=[("tack-ffff01", 0, True)]))
    lines = run(tmp_path, *build(units))[1]
    assert lines[1].startswith("on 100/101,")
    assert [line for line in lines if line.startswith("sensitivity")][0].startswith(
        "sensitivity (unknown defect state counted defective): on 100/101,")


def test_rows_for_tasks_outside_the_census_are_ignored(tmp_path):
    census, report = build(arms(80, 100, 79, 100))
    report["units"].append({"task": "relay-000001", "first_start_ms": 1, "first_close_ms": 2, "defects": 3,
                            "changes": 0, "extensions": 0, "reopens": 0, "output_tokens": None})
    assert run(tmp_path, census, report)[0] == 0


@pytest.mark.parametrize("damage", ["arm", "start", "duplicate", "trial"])
def test_disagreeing_inputs_exit_2(tmp_path, damage):
    census, report = build(arms(80, 100, 79, 100))
    if damage == "arm":
        census["units"][0]["arm"] = "off" if census["units"][0]["arm"] == "on" else "on"
    elif damage == "start":
        report["units"][0]["first_start_ms"] -= 3 * 86_400_000
    elif damage == "duplicate":
        report["units"].append(dict(report["units"][0]))
    else:
        census["trial"] = "other"
    assert run(tmp_path, census, report)[0] == 2


@pytest.mark.parametrize("damage", ["negative defects", "null gate", "bad gate", "no state", "compliant text",
                                    "negative tokens", "no members", "bad timestamp"])
def test_malformed_inputs_exit_2(tmp_path, damage):
    census, report = build(arms(80, 100, 79, 100))
    first = census["units"][0]
    if damage == "negative defects":
        report["units"][0]["defects"] = -1
    elif damage == "null gate":
        report["unvalidated"]["measures"]["m4"] = None
    elif damage == "bad gate":
        report["unvalidated"]["measures"]["m4"] = "E3"
    elif damage == "no state":
        del first["state"]
    elif damage == "compliant text":
        first["compliant"] = "yes"
    elif damage == "negative tokens":
        report["units"][0]["output_tokens"] = -5
    elif damage == "no members":
        first["members"] = []
    else:
        first["members"][0]["first_start"] = "yesterday"
    assert run(tmp_path, census, report)[0] == 2


def test_validate_reads_live_inputs_without_any_outcome(tmp_path):
    census, report = build(arms(80, 100, 79, 100))
    trial = tmp_path / "trial.md"
    trial.write_text(TRIAL_TEXT)
    path = tmp_path / "census.json"
    path.write_text(json.dumps(census))
    out = io.StringIO()
    code = tv.main([str(trial), "--census", str(path), "--validate"],
                   stdin=io.StringIO(json.dumps(report)), stdout=out)
    assert (code, out.getvalue().splitlines()) == (0, ["inputs valid: 200 census units, 200 obs rows for their members"])
    report["units"][0]["defects"] = -1
    out = io.StringIO()
    assert tv.main([str(trial), "--census", str(path), "--validate"],
                   stdin=io.StringIO(json.dumps(report)), stdout=out) == 2


def test_null_close_in_obs_row_is_refused(tmp_path, capsys):
    census, report = build(arms(80, 100, 79, 100))
    report["units"][0]["first_close_ms"] = None
    code, _ = run(tmp_path, census, report)
    assert code == 2
    assert report["units"][0]["task"] in capsys.readouterr().err
