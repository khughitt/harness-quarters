import importlib.util
import io
import json
import math
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).with_name("flow-outcome-verdict")
spec = importlib.util.spec_from_loader("flow_outcome_verdict", loader=None)
fv = importlib.util.module_from_spec(spec)
sys.modules["flow_outcome_verdict"] = fv
exec(compile(SCRIPT.read_text(), str(SCRIPT), "exec"), fv.__dict__)

S1 = {"project": "tack", "size": "s", "complexity": "mid", "process": "direct", "artifact": "task"}
S2 = {"project": "tack", "size": "m", "complexity": "mid", "process": "planned", "artifact": "task"}


def unit(task, stratum, flow, defects=0, *, state="attributed", harness="claude-code",
         model="claude-opus-5-5", links=None, tokens=100):
    """A task row as obs `--units` prints it. `flow` is the skill:flow value, or None for
    no value."""
    if links is None:
        links = [{"kind": "defect", "evidence": "inferred"}] * defects
    return {"task": task, "first_start_ms": 1, "first_close_ms": 2, "stratum": dict(stratum),
            "factors": {"skill:flow": {"state": state, "values": [] if flow is None else [flow]},
                        "harness": {"state": "attributed", "values": [harness]},
                        "model": {"state": "attributed", "values": [model]}},
            "defects": defects, "changes": 0, "extensions": 0, "reopens": 0,
            "links": links, "output_tokens": tokens}


def rows_for(units, suppressed=None):
    """Comparison rows built independently of the tool: one per stratum, cells per value.
    `suppressed` maps a stratum's size to its suppressed_reason."""
    suppressed = suppressed or {}
    by = {}
    for u in units:
        key = tuple(u["stratum"][k] for k in ("project", "size", "complexity", "process", "artifact"))
        row = by.setdefault(key, {"factor": "skill:flow", "measure": "m4_defective",
                                  "stratum": dict(u["stratum"]), "units": 0, "unassigned": 0,
                                  "cells": {}})
        row["units"] += 1
        credit = u["factors"]["skill:flow"]
        if credit["state"] in ("unknown", "several") or not credit["values"]:
            row["unassigned"] += 1
            continue
        for value in credit["values"]:
            cell = row["cells"].setdefault(value, {"value": value, "total": 0, "attributed": 0,
                                                   "n": 0, "sum": 0, "mean": None})
            cell["total"] += 1
            if credit["state"] == "attributed":
                cell["attributed"] += 1
                cell["n"] += 1
                cell["sum"] += int(u["defects"] > 0)
    out = []
    for key, row in by.items():
        reason = suppressed.get(key[1])
        out.append({**row, "cells": list(row["cells"].values()),
                    "suppressed": reason is not None, "suppressed_reason": reason})
    return out


def make_report(units, *, gate=False, suppressed=None, rows=None):
    return {"evidence": "inferred",
            "unvalidated": {"version": 1, "measures": {"m4": "E2"} if gate else {}},
            "comparisons": rows if rows is not None else rows_for(units, suppressed),
            "units": units,
            "limitations": {"m4": "no exposure: needs obs-db1316"}}


def test_read_accepts_a_consistent_report():
    units = [unit("t1", S1, True, 1), unit("t2", S1, False)]
    rows, got_units, cells = fv.read(make_report(units))
    assert len(rows) == 1 and got_units == units
    assert cells[fv.stratum_key(S1)][True] == {"n": 1, "sum": 1}


def test_read_refuses_a_report_without_units():
    report = make_report([unit("t1", S1, True)])
    del report["units"]
    with pytest.raises(fv.ReportError, match="--units"):
        fv.read(report)


@pytest.mark.parametrize("damage", [
    lambda r: None,
    lambda r: {**r, "units": None},
    lambda r: {**r, "comparisons": None},
    lambda r: {**r, "unvalidated": {"version": 1, "measures": None}},
    lambda r: {**r, "units": [None]},
])
def test_read_refuses_null_parts(damage):
    with pytest.raises(fv.ReportError):
        fv.read(damage(make_report([unit("t1", S1, True)])))


def test_read_refuses_a_cell_count_mismatch():
    units = [unit("t1", S1, True, 1), unit("t2", S1, False)]
    rows = rows_for(units)
    rows[0]["cells"][0]["sum"] = 0
    with pytest.raises(fv.ReportError, match="disagree"):
        fv.read(make_report(units, rows=rows))


def test_read_refuses_a_stratum_with_units_but_no_row():
    units = [unit("t1", S1, True), unit("t2", S2, False)]
    rows = [row for row in rows_for(units) if row["stratum"]["size"] == "s"]
    with pytest.raises(fv.ReportError, match="disagree"):
        fv.read(make_report(units, rows=rows))


def test_read_refuses_duplicate_comparison_rows():
    # Review round 1 on the plan: a repeated row moved p from 0.1053 to 0.0111.
    units = [unit("t1", S1, True, 1), unit("t2", S1, False)]
    rows = rows_for(units)
    with pytest.raises(fv.ReportError, match="duplicate"):
        fv.read(make_report(units, rows=rows + [dict(rows[0])]))


def test_read_refuses_duplicate_task_rows():
    units = [unit("t1", S1, True, 1), unit("t1", S1, True, 1), unit("t2", S1, False)]
    with pytest.raises(fv.ReportError, match="duplicate task rows: \\['t1'\\]"):
        fv.read(make_report(units))


def test_read_refuses_an_attributed_unit_with_two_flow_values():
    # Revision 13 of the outcome spec: attributed means one participant, one value.
    both = unit("t1", S1, True)
    both["factors"]["skill:flow"]["values"] = [True, False]
    with pytest.raises(fv.ReportError, match="t1"):
        fv.read(make_report([both, unit("t2", S1, False)]))


def test_unassigned_and_non_attributed_units_reconcile():
    units = [unit("t1", S1, True), unit("t2", S1, None, state="unknown"),
             unit("t3", S1, False, state="mixed")]
    rows, _, cells = fv.read(make_report(units))
    assert rows[0]["unassigned"] == 1
    assert False not in cells[fv.stratum_key(S1)]   # mixed is assigned but not attributed


def test_null_stratum_field_is_a_valid_key():
    unsized = {**S1, "size": None}
    rows, _, cells = fv.read(make_report([unit("t1", unsized, True)]))
    assert fv.stratum_key(unsized) in cells


def test_gate_holds_and_clears():
    assert fv.gate_holds(make_report([], gate=True)) is True
    assert fv.gate_holds(make_report([], gate=False)) is False


@pytest.mark.parametrize("status", ["E2v2", None, ""])
def test_gate_refuses_any_other_status(status):
    report = make_report([])
    report["unvalidated"]["measures"]["m4"] = status
    with pytest.raises(fv.ReportError, match="validation status"):
        fv.gate_holds(report)


@pytest.mark.parametrize("credit", [
    None,
    {"state": None, "values": [True]},
    {"state": "attributed", "values": "x"},
    {"state": "attributed", "values": [1]},
    {"state": "attributed", "values": []},
    {"state": "attributed", "values": [None]},
    {"state": "unknown", "values": ["yes"]},
    {"state": "unknown", "values": [None]},
])
def test_read_refuses_a_malformed_flow_credit(credit):
    # Plan review round 2: [1] counted as flow true in the headline and vanished from
    # the tables; an attributed credit with no value passed as unassigned.
    units = [unit("t1", S1, True), unit("t2", S1, False)]
    rows = rows_for(units)   # built before the damage, from well-formed rows
    units[0]["factors"]["skill:flow"] = credit
    with pytest.raises(fv.ReportError, match="t1"):
        fv.read(make_report(units, rows=rows))


@pytest.mark.parametrize("name, value", [
    ("defects", -1), ("changes", -1), ("extensions", True), ("reopens", None),
    ("output_tokens", -5), ("output_tokens", "x"),
])
def test_read_refuses_a_bad_count(name, value):
    units = [unit("t1", S1, True)]
    rows = rows_for(units)
    units[0][name] = value
    with pytest.raises(fv.ReportError, match="t1"):
        fv.read(make_report(units, rows=rows))


def test_read_accepts_an_unknown_credit_carrying_a_known_value():
    # D4 of the outcome spec: unknown can carry a known value beside an unrecorded one.
    partial = unit("t1", S1, None, state="unknown")
    partial["factors"]["skill:flow"]["values"] = [True, None]
    rows, _, _ = fv.read(make_report([partial]))
    assert rows[0]["unassigned"] == 1


def test_defects_without_a_defect_link_are_refused():
    units = [unit("t1", S1, True, 1, links=[])]
    with pytest.raises(fv.ReportError, match="t1"):
        fv.read(make_report(units))


def arm(stratum, prefix, flow, defective, n):
    return [unit(f"{prefix}{i}", stratum, flow, int(i < defective)) for i in range(n)]


def test_exact_p_single_stratum_matches_fisher():
    # Spec review round 1's example: 2/5 flow defective against 0/5 is p = 10/45.
    assert fv.exact_p([(2, 5, 0, 5)]) == pytest.approx(10 / 45)


def test_exact_p_no_defects_is_one_and_odds_ratio_undefined():
    assert fv.exact_p([(0, 10, 0, 10)]) == 1.0
    assert math.isnan(fv.mh_odds_ratio([(0, 10, 0, 10)]))


def test_simpsons_paradox_is_not_a_regression():
    # Flow is better in each stratum (80/100 vs 9/10; 1/10 vs 20/100) and worse pooled
    # (81/110 vs 29/110). Within strata it must not be called a regression.
    tables = [(80, 100, 9, 10), (1, 10, 20, 100)]
    assert fv.exact_p([(81, 110, 29, 110)]) < 0.1   # what pooling would have said
    assert fv.exact_p(tables) >= 0.1
    assert fv.mh_odds_ratio(tables) < 1
    units = arm(S1, "a", True, 80, 100) + arm(S1, "b", False, 9, 10) \
        + arm(S2, "c", True, 1, 10) + arm(S2, "d", False, 20, 100)
    result = fv.verdict(make_report(units))
    assert result["choice"] == "no-regression-detected"


def test_regression():
    units = arm(S1, "a", True, 8, 12) + arm(S1, "b", False, 1, 12)
    result = fv.verdict(make_report(units))
    assert (result["choice"], result["reason"], result["provisional"]) == ("regression", None, False)
    assert result["p"] < 0.1 and result["flow"] == (8, 12) and result["other"] == (1, 12)
    assert result["validation"] == "cleared"


def test_no_regression_detected():
    units = arm(S1, "a", True, 2, 12) + arm(S1, "b", False, 2, 12)
    assert fv.verdict(make_report(units))["choice"] == "no-regression-detected"


def test_gate_wins_over_counts():
    units = arm(S1, "a", True, 8, 12) + arm(S1, "b", False, 1, 12)
    result = fv.verdict(make_report(units, gate=True, suppressed={"s": "unvalidated:E2"}))
    assert (result["choice"], result["reason"]) == ("insufficient", "unvalidated")
    assert result["p"] is None


def test_empty_cohort_under_the_gate_is_unvalidated_not_too_few():
    result = fv.verdict(make_report([], gate=True))
    assert (result["choice"], result["reason"]) == ("insufficient", "unvalidated")
    assert result["validation"] == "unvalidated:E2"
    assert result["entered"] == []
    assert result["strata_total"] == 0


def test_coverage_suppression_does_not_mask_the_gate():
    # The only stratum is coverage-suppressed, so no row carries unvalidated:E2;
    # the gate still comes from the measure-level status.
    units = arm(S1, "a", True, 8, 12) + arm(S1, "b", False, 1, 12)
    result = fv.verdict(make_report(units, gate=True, suppressed={"s": "unassigned"}))
    assert (result["choice"], result["reason"], result["validation"]) == \
        ("insufficient", "unvalidated", "unvalidated:E2")
    assert result["entered"] == [] and result["skipped"] == {"unassigned": 1}


def test_provisional_strata_exclude_coverage_suppression():
    units = arm(S1, "a", True, 1, 12) + arm(S1, "b", False, 1, 12) \
        + arm(S2, "c", True, 1, 12) + arm(S2, "d", False, 1, 12)
    result = fv.verdict(make_report(units, gate=True,
                                    suppressed={"s": "unvalidated:E2", "m": "low_retention"}))
    assert result["provisional"] is True
    assert [key for key, _ in result["entered"]] == [fv.stratum_key(S1)]
    assert result["skipped"] == {"low_retention": 1}


def test_too_few():
    units = arm(S1, "a", True, 8, 9) + arm(S1, "b", False, 1, 12)
    assert fv.verdict(make_report(units))["reason"] == "too few"


def test_suppressed_and_one_arm_strata_do_not_enter():
    units = arm(S1, "a", True, 1, 12) + arm(S1, "b", False, 1, 12) + arm(S2, "c", True, 5, 6)
    result = fv.verdict(make_report(units, suppressed={"m": "low_retention"}))
    assert [key for key, _ in result["entered"]] == [fv.stratum_key(S1)]
    assert result["skipped"] == {"low_retention": 1}
    assert fv.verdict(make_report(units))["skipped"] == {"one arm": 1}
