# Workflow Outcome Evaluation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans. Execution chosen at plan review round 1: inline in one session, then one independent review of the whole branch. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the `flow-defects-after-close` eval case and the `flow-outcome-verdict` tool that judges it from an obs outcomes report, and file the obs work that report needs.

**Architecture:** One stdlib-only Python script, `agents/bin/flow-outcome-verdict`, reads `obs --json outcomes report --since <from> --until <to> --cohort --units` JSON on stdin. It recounts obs's `skill:flow` × `m4_defective` comparison cells from the task rows and refuses on any disagreement. Then it applies the spec's §4 rule (validation gate, stratum entry, minimum arm size, an exact conditional test across strata) and prints the verdict, its counts and the §5 conditions. The case file in `agents/evals/cases/` names the subject (a `SKILL.md` blob and its whole-UTC-day cohort window) and records each run's verdict.

**Tech Stack:** Python 3 standard library (`fractions`, `math`, `statistics`, `collections`, `json`), pytest through `python3 -m pytest agents/bin`, the `tasks` CLI.

**Review:** plan round 1 (codex): revise, P1 1, P2 5, answered in this revision: duplicate strata, task rows and two-valued attributions are refused (Task 2); explicit nulls and wrong types fail closed with exit 2 (Task 2); plan round 2 (codex): revise, P2 1 — task rows' flow credit and counts are validated before the recount (Task 2); change requests, extensions, reopens and defective task ids are printed (Task 4); conditions describe only entering strata, provisional ones under the gate (Tasks 3–4); `observed` keeps choice and reason apart (Task 5); the live cross-check reads the filtered M4 rows and counts one-arm strata separately (Task 5).

**Spec:** `docs/specs/2026-10-01-workflow-outcome-eval-design.md` (approved 2026-10-01, revision 3.1). Read it before any task. Section references (§4 and so on) point into it.

## Global Constraints

- Standard library only; no statistics package (§4).
- The script follows the `agents/bin` pattern: an extensionless executable with a `#!/usr/bin/env python3` shebang and a module docstring that serves as its usage, tested by `agents/bin/test_flow_outcome_verdict.py`, which loads it with `importlib` the way `test_wake_judge.py` loads `wake-judge`.
- Fixture reports are built by the test module's builders (`unit`, `rows_for`, `make_report`) rather than stored as JSON under `agents/evals/fixtures/`: the Simpson's-paradox fixture alone is 220 task rows, and a builder states each fixture's counts where the test reads them. The spec's §8 piece 2 is updated to say so.
- Tests run with `python3 -m pytest agents/bin/test_flow_outcome_verdict.py -q` while working, and `just test` before each commit. tack's justfile has no `test-one` or `test-fast` yet.
- Exit codes: `0` when a verdict is printed (any choice, including `insufficient`); `2` when the report is malformed (a missing key, an explicit null or a wrong type where a value is required), holds duplicate strata or task rows, or its comparison rows and task rows disagree. The message goes to stderr, prefixed `flow-outcome-verdict: `.
- The first stdout line is exactly one of `no-regression-detected`, `regression`, `insufficient: unvalidated`, `insufficient: too few`.
- Constants from the spec, verbatim: factor `skill:flow`; measure `m4_defective`; gate measure key `m4`, gate value `E2`; minimum arm size 10 scored tasks; one-sided threshold p < 0.1; unassigned states `unknown`, `several`; excluded authorship states `incomplete`, `mixed`, `several`, `unknown`; stratum keys `project`, `size`, `complexity`, `process`, `artifact`.
- Task rows: `defects`, `changes`, `extensions` and `reopens` are non-negative integers (not booleans); `output_tokens` is a non-negative integer or `null`; `skill:flow` values are booleans, with `null` allowed only beside a known value in a non-attributed credit (outcome spec D4).
- **The report contract** (what the obs task in Task 1 delivers; the tool reads nothing else):
  - `unvalidated.measures`: an object. The key `m4` mapped to `"E2"` means the gate holds. A missing key means it is cleared. Any other value, `null` included, is malformed.
  - One comparison row per stratum for a factor and measure, and one task row per task. An attributed unit has exactly one value for a factor (outcome spec revision 13: one participant).
  - `comparisons[]`: `{factor, measure, stratum: {project, size, complexity, process, artifact}, units, unassigned, suppressed, suppressed_reason, cells: [{value, total, attributed, n, sum, mean}]}`. `n` counts attributed, measured units; `sum` is the exact sum of the measure over them (for `m4_defective`, the defective count).
  - `units[]` (present only with `--units`): `{task, first_start_ms, first_close_ms, stratum, factors: {<name>: {state, values}}, defects, changes, extensions, reopens, links: [{kind, evidence}], output_tokens}`. `kind` is `defect`, `change` or `extension`; `evidence` is `recorded` or `inferred`; `output_tokens` is an integer or `null`.
  - `limitations`: an object of measure → text (exists today).
- No machine-specific absolute paths in code, comments or docs.

## Review Focus

- A report produced without `--units`: the tool must refuse with exit 2 and say to rerun with `--units`, not crash on a `KeyError` or treat the cohort as empty.
- A validation status other than `"E2"` for `m4`, an explicit `null` included (a later obs renames it, say `"E2v2"`): exit 2, never read as "gate cleared".
- A task row with `defects > 0` but no `defect` link: exit 2, because the coverage table could not say where the defect came from.
- A stratum field that is `null` (an unsized task): the stratum key and the printed table must handle it (printed as `-`), not crash.
- A task row whose `skill:flow` credit is malformed (`values: [1]`, `values: "x"`, an attributed credit with no value) or whose counts are negative: exit 2, so the headline and the tables never count different tasks.
- Strata with no defects in either arm: the exact test returns p = 1 and the Mantel–Haenszel ratio is undefined, printed as `-`, with no division error.

Each line has a test in the task that owns the code (Tasks 2–4).

---

### Task 1: File the obs work and the obs-abfcf9 note

No code. This task records the obs contract where obs will build it, so Task 5 can depend on it.

**Files:** none (task records in obs and tack, through the CLI).

**Interfaces:**
- Produces: an obs task id (call it `OBS_ID` below) that Task 5's step child depends on.

- [ ] **Step 1: File the obs task**

```bash
tasks add "Outcomes report for cohort evals: --until, --cohort, an M4 E2 gate, exact cell sums, --units task rows" \
  --project obs -p 2 --size m --complexity mid --process planned --tag outcomes \
  --source tack-026612 --agent claude-code/claude-opus-5-5 \
  -b "Consumer: tack-026612's flow-defects-after-close case (tack docs/specs/2026-10-01-workflow-outcome-eval-design.md §8 piece 1, approved). Add to obs outcomes report: (1) --until <when>, inclusive through the end of that UTC day, on the same task anchor as --since; (2) --cohort: task units enter only when their first start and first eligible close both fall within --since..--until, applied before cell aggregation and suppression and to --units; (3) m4 and m4_defective: \"E2\" in UNVALIDATED, cleared when a followup-rubric-v2 rejudge, hand-checked, gives defect precision with Wilson lower bound >= 0.7 (recorded concerns: notes do not bypass the gate until their recall is measured); the existing top-level unvalidated.measures stays the measure-level status; (4) a sum field on every comparison cell: the exact sum of the measure over the attributed, measured units counted in n; (5) --units: a top-level units array of the windowed task units, each {task, first_start_ms, first_close_ms, stratum, factors: {name: {state, values}} for harness, model, effort and skill:*, defects, changes, extensions, reopens, links: [{kind: defect|change|extension, evidence: recorded|inferred}], output_tokens (int or null)}. Tests: a task started the day before --since is excluded under --cohort; a stratum that passes retention over the close window and fails it over the cohort is suppressed under --cohort; under the gate, an empty cohort still reports unvalidated.measures.m4 = E2."
```

Record the printed id as `OBS_ID`.

- [ ] **Step 2: Note the schema inputs on obs-abfcf9**

```bash
tasks note obs-abfcf9 "input from tack-026612 (spec docs/specs/2026-10-01-workflow-outcome-eval-design.md §7): the verdict record needs an input of kind query (derived tables, not a session or fixture), a subject version that is a blob set plus a cohort window rather than a commit, and an insufficient answer carrying a reason"
```

- [ ] **Step 3: Note the filing on tack-026612 and commit**

```bash
tasks dep tack-fbb7a2 --on <OBS_ID>
tasks note tack-026612 "obs work filed as <OBS_ID>, and Task 5 (tack-fbb7a2) depends on it; obs-abfcf9 noted with the three schema inputs"
tasks check
git add tasks/tack-026612.md tasks/tack-fbb7a2.md
git commit -m "chore(tasks): file obs cohort-report work for tack-026612"
```

The obs record lands uncommitted in obs's registered checkout. Leave it for obs's owner to commit, as with feedback reports.

---

### Task 2: Read the report, gate it, and reconcile its two halves

**Files:**
- Create: `agents/bin/flow-outcome-verdict`
- Create: `agents/bin/test_flow_outcome_verdict.py`

**Interfaces:**
- Produces, in `flow-outcome-verdict`:
  - `class ReportError(Exception)`
  - `stratum_key(stratum: dict) -> tuple` (values in `STRATUM_KEYS` order; `None` allowed)
  - `recount(units: list[dict]) -> (cells, unassigned, members)`: `cells[key][value] -> {"n": int, "sum": int}`, `unassigned: Counter[key]`, `members: Counter[key]`
  - `reconcile(rows, cells, unassigned, members) -> None` (raises `ReportError`)
  - `gate_holds(report: dict) -> bool` (raises `ReportError` on any value but `"E2"`)
  - `read(report) -> (rows, units, cells)`: checks the report's shape, refuses duplicates, reconciles, and returns the `skill:flow` × `m4_defective` rows, the task rows and the recounted cells.
- The test module's builders (`S1`, `S2`, `unit`, `rows_for`, `make_report`) are reused by Tasks 3 and 4.

- [ ] **Step 1: Write the failing tests**

`agents/bin/test_flow_outcome_verdict.py`:

```python
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m pytest agents/bin/test_flow_outcome_verdict.py -q`
Expected: collection error, `FileNotFoundError` for `flow-outcome-verdict`.

- [ ] **Step 3: Write the implementation**

`agents/bin/flow-outcome-verdict`:

```python
#!/usr/bin/env python3
"""Judge the flow-defects-after-close eval case from an obs outcomes report.

obs --json outcomes report --since <from> --until <to> --cohort --units | flow-outcome-verdict

Reads the report's JSON on stdin (spec docs/specs/2026-10-01-workflow-outcome-eval-design.md
§4-§5). The first line printed is the choice: no-regression-detected, regression, or
insufficient: <unvalidated|too few>. The second is the counts behind it; the rest are
the conditions. Exits 0 with a verdict; 2 when the report is malformed, holds duplicate
strata or tasks, or its comparison rows and task rows describe different units. It
filters nothing: the cohort is obs's.
"""
import collections
import json
import sys

FACTOR = "skill:flow"
MEASURE = "m4_defective"
GATE_MEASURE = "m4"
GATE = "E2"
UNASSIGNED = ("unknown", "several")
STRATUM_KEYS = ("project", "size", "complexity", "process", "artifact")


class ReportError(Exception):
    """The report cannot be read as this case's input."""


def _field(container, name, kind, where):
    if not isinstance(container, dict):
        raise ReportError(f"{where} is {type(container).__name__}, not an object")
    if name not in container:
        raise ReportError(f"{where} lacks {name!r}")
    value = container[name]
    if not isinstance(value, kind):
        raise ReportError(f"{where}.{name} is {type(value).__name__}, not {kind.__name__}")
    return value


def stratum_key(stratum):
    if not isinstance(stratum, dict):
        raise ReportError(f"stratum is {type(stratum).__name__}, not an object")
    try:
        return tuple(stratum[name] for name in STRATUM_KEYS)
    except KeyError as missing:
        raise ReportError(f"stratum lacks {missing}") from None


def _credit(unit):
    return unit["factors"].get(FACTOR, {"state": "unknown", "values": []})


def recount(units):
    """The skill:flow x m4_defective cells per stratum, built from task rows the way obs
    builds its comparison cells: unassigned states and empty values go to `unassigned`,
    and only attributed units are counted in `n` and `sum`. `read` has already checked
    that an attributed unit carries exactly one boolean value."""
    cells = collections.defaultdict(dict)
    unassigned = collections.Counter()
    members = collections.Counter()
    for unit in units:
        key = stratum_key(unit["stratum"])
        members[key] += 1
        credit = _credit(unit)
        values = [value for value in credit["values"] if value is not None]
        if credit["state"] in UNASSIGNED or not values:
            unassigned[key] += 1
            continue
        if credit["state"] != "attributed":
            continue
        cell = cells[key].setdefault(values[0], {"n": 0, "sum": 0})
        cell["n"] += 1
        cell["sum"] += int(unit["defects"] > 0)
    return cells, unassigned, members


def reconcile(rows, cells, unassigned, members):
    """Refuse unless the comparison rows and the task rows describe the same units, one
    row per stratum."""
    keys = collections.Counter(stratum_key(row["stratum"]) for row in rows)
    repeated = sorted((key for key, count in keys.items() if count > 1), key=repr)
    if repeated:
        raise ReportError(f"duplicate comparison rows for strata {repeated}")
    if set(keys) != set(members):
        raise ReportError(f"comparison rows and task rows disagree on strata: "
                          f"rows only {sorted(set(keys) - set(members), key=repr)}, "
                          f"units only {sorted(set(members) - set(keys), key=repr)}")
    for row in rows:
        key = stratum_key(row["stratum"])
        shown = {cell["value"]: {"n": cell["n"], "sum": cell["sum"]}
                 for cell in row["cells"] if cell["n"] > 0}
        if (row["units"], row["unassigned"], shown) != (members[key], unassigned[key], cells[key]):
            raise ReportError(f"comparison rows and task rows disagree in stratum {key}: "
                              f"row units={row['units']} unassigned={row['unassigned']} cells={shown}; "
                              f"recount units={members[key]} unassigned={unassigned[key]} cells={cells[key]}")


def gate_holds(report):
    """A missing m4 key clears the gate; "E2" holds it; any other value, null included,
    is malformed."""
    measures = _field(_field(report, "unvalidated", dict, "report"), "measures", dict,
                      "report.unvalidated")
    if GATE_MEASURE not in measures:
        return False
    if measures[GATE_MEASURE] != GATE:
        raise ReportError(f"invalid validation status for {GATE_MEASURE}: {measures[GATE_MEASURE]!r}")
    return True


def _count(unit, name, where, nullable=False):
    if name not in unit:
        raise ReportError(f"{where} lacks {name!r}")
    value = unit[name]
    if value is None and nullable:
        return
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ReportError(f"{where}: {name} is {value!r}, not a count")


def _check_unit(unit):
    """One task row's shape: the fields the recount and the tables read, with counts that
    are non-negative integers and a skill:flow credit whose values are booleans (or null,
    beside a known value, in an unknown credit). Attributed means one participant, so
    exactly one boolean value."""
    for name, kind in (("task", str), ("stratum", dict), ("factors", dict), ("links", list)):
        _field(unit, name, kind, "unit")
    where = f"task {unit['task']}"
    for name in ("defects", "changes", "extensions", "reopens"):
        _count(unit, name, where)
    _count(unit, "output_tokens", where, nullable=True)
    if FACTOR not in unit["factors"]:
        return
    credit = unit["factors"][FACTOR]
    state = _field(credit, "state", str, f"{where} {FACTOR}")
    values = _field(credit, "values", list, f"{where} {FACTOR}")
    if any(value is not None and not isinstance(value, bool) for value in values):
        raise ReportError(f"{where}: {FACTOR} values {values!r} are not booleans")
    if state == "attributed" and (len(values) != 1 or values[0] is None):
        raise ReportError(f"{where} is attributed with flow values {values!r}, not exactly one")


def read(report):
    if isinstance(report, dict) and "units" not in report:
        raise ReportError("report lacks 'units': run obs outcomes report with --units")
    units = _field(report, "units", list, "report")
    comparisons = _field(report, "comparisons", list, "report")
    _field(report, "limitations", dict, "report")
    gate_holds(report)
    for unit in units:
        _check_unit(unit)
    repeated = sorted(task for task, count in collections.Counter(u["task"] for u in units).items()
                      if count > 1)
    if repeated:
        raise ReportError(f"duplicate task rows: {repeated}")
    for unit in units:
        if unit["defects"] > 0 and not any(link["kind"] == "defect" for link in unit["links"]):
            raise ReportError(f"task {unit['task']} has {unit['defects']} defects and no defect link")
    for row in comparisons:
        _field(row, "factor", str, "comparison row")
    rows = [row for row in comparisons if row["factor"] == FACTOR and row.get("measure") == MEASURE]
    cells, unassigned, members = recount(units)
    reconcile(rows, cells, unassigned, members)
    return rows, units, cells


def main():
    try:
        read(json.load(sys.stdin))
    except (ReportError, KeyError, TypeError, ValueError) as error:
        print(f"flow-outcome-verdict: {type(error).__name__}: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

`main` catches `KeyError`, `TypeError` and `ValueError` (which includes `json.JSONDecodeError`) besides `ReportError`, so a field the explicit checks above do not cover still fails closed with exit 2 rather than a traceback.

Then `chmod +x agents/bin/flow-outcome-verdict`.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m pytest agents/bin/test_flow_outcome_verdict.py -q`
Expected: 33 passed.

- [ ] **Step 5: Commit**

```bash
just test
git add agents/bin/flow-outcome-verdict agents/bin/test_flow_outcome_verdict.py
git commit -m "feat(evals): flow-outcome-verdict reads and reconciles an outcomes report"
```

---

### Task 3: The verdict rule and the exact stratified test

**Files:**
- Modify: `agents/bin/flow-outcome-verdict` (add the statistics and `verdict`)
- Modify: `agents/bin/test_flow_outcome_verdict.py`

**Interfaces:**
- Consumes: `read`, `gate_holds`, `stratum_key`, `ReportError` (Task 2); the test builders.
- Produces:
  - `exact_p(tables: list[tuple[int, int, int, int]]) -> float`: each table is `(flow_defective, flow_n, other_defective, other_n)`.
  - `mh_odds_ratio(tables) -> float` (`math.inf` or `math.nan` when the denominator is 0)
  - `verdict(report: dict) -> dict` with keys `choice` (`"no-regression-detected"`, `"regression"`, `"insufficient"`), `reason` (`"unvalidated"`, `"too few"` or `None`), `provisional` (bool: the gate holds, so `entered` is what would enter once it clears), `entered` (list of `(key, table)`), `skipped` (`Counter` of reason → strata), `strata_total`, `flow` (`(defective, n)`), `other` (`(defective, n)`), `p`, `odds_ratio` (floats, or `None` when not computed), `units`.

**Entering under the gate.** While the gate holds, obs suppresses M4 rows as `unvalidated:E2` unless coverage suppressed them first (`unassigned`, `low_retention` take precedence). A row whose reason is `unvalidated:E2` is therefore one that would be shown once the gate clears, and it enters the provisional tables. A coverage-suppressed row never enters, gate or not.

- [ ] **Step 1: Write the failing tests**

Append to `agents/bin/test_flow_outcome_verdict.py`:

```python
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m pytest agents/bin/test_flow_outcome_verdict.py -q`
Expected: the 10 new tests fail with `AttributeError: ... 'exact_p'` / `'verdict'`; the 33 Task 2 tests pass.

- [ ] **Step 3: Write the implementation**

In `agents/bin/flow-outcome-verdict`, add `import math` and `from fractions import Fraction` to the imports, add these constants beside the others:

```python
MIN_ARM = 10
ALPHA = 0.1
```

and add after `read`:

```python
def _hypergeometric(flow_n, other_n, defective):
    """The flow arm's defective count given the stratum's margins, exactly."""
    whole = math.comb(flow_n + other_n, defective)
    return {x: Fraction(math.comb(flow_n, x) * math.comb(other_n, defective - x), whole)
            for x in range(max(0, defective - other_n), min(flow_n, defective) + 1)}


def exact_p(tables):
    """One-sided p of the exact conditional test of a common odds ratio of 1 (spec §4):
    the sum over strata of the flow arm's defective count, against the convolution of
    the per-stratum hypergeometrics. Each table is (flow_defective, flow_n,
    other_defective, other_n)."""
    null = {0: Fraction(1)}
    observed = 0
    for flow_d, flow_n, other_d, other_n in tables:
        observed += flow_d
        step = _hypergeometric(flow_n, other_n, flow_d + other_d)
        nxt = collections.defaultdict(Fraction)
        for total, p in null.items():
            for x, q in step.items():
                nxt[total + x] += p * q
        null = nxt
    return float(sum(p for total, p in null.items() if total >= observed))


def mh_odds_ratio(tables):
    """The Mantel-Haenszel common odds ratio, flow against no flow."""
    num = sum(Fraction(fd * (on - od), fn + on) for fd, fn, od, on in tables)
    den = sum(Fraction((fn - fd) * od, fn + on) for fd, fn, od, on in tables)
    if den == 0:
        return math.inf if num > 0 else math.nan
    return float(num / den)


def verdict(report):
    """The §4 rule. The gate is read first and from the measure-level status, so neither an
    empty cohort nor a coverage suppression can hide it. Under the gate, the strata that
    would enter once it clears (suppressed only as unvalidated:E2) are kept as provisional."""
    rows, units, cells = read(report)
    gated = gate_holds(report)
    entered, skipped = [], collections.Counter()
    for row in rows:
        key = stratum_key(row["stratum"])
        reason = row["suppressed_reason"] if row["suppressed"] else None
        if reason is not None and not (gated and reason == f"unvalidated:{GATE}"):
            skipped[reason] += 1
            continue
        flow, other = cells[key].get(True), cells[key].get(False)
        if flow is None or other is None:   # recount creates a cell only with n >= 1
            skipped["one arm"] += 1
            continue
        entered.append((key, (flow["sum"], flow["n"], other["sum"], other["n"])))
    tables = [table for _, table in entered]
    result = {"entered": entered, "skipped": skipped, "strata_total": len(rows), "provisional": gated,
              "flow": (sum(t[0] for t in tables), sum(t[1] for t in tables)),
              "other": (sum(t[2] for t in tables), sum(t[3] for t in tables)),
              "p": None, "odds_ratio": None, "units": units}
    if gated:
        return {**result, "choice": "insufficient", "reason": "unvalidated"}
    if result["flow"][1] < MIN_ARM or result["other"][1] < MIN_ARM:
        return {**result, "choice": "insufficient", "reason": "too few"}
    p = exact_p(tables)
    return {**result, "p": p, "odds_ratio": mh_odds_ratio(tables),
            "choice": "regression" if p < ALPHA else "no-regression-detected", "reason": None}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m pytest agents/bin/test_flow_outcome_verdict.py -q`
Expected: 43 passed.

- [ ] **Step 5: Commit**

```bash
just test
git add agents/bin/flow-outcome-verdict agents/bin/test_flow_outcome_verdict.py
git commit -m "feat(evals): exact stratified verdict rule for flow-outcome-verdict"
```

---

### Task 4: Conditions and the printed verdict

**Files:**
- Modify: `agents/bin/flow-outcome-verdict` (add `conditions`, `render`; rewrite `main`)
- Modify: `agents/bin/test_flow_outcome_verdict.py`

**Interfaces:**
- Consumes: `verdict` (Task 3), its result keys.
- Produces:
  - `conditions(result: dict, report: dict) -> list[str]`: the §5 lines, over the **scored cohort** only: the units of the entering strata (provisional ones under the gate) whose flow value is attributed. Never a unit from a stratum that did not enter.
  - `render(result: dict, report: dict) -> str`: the full stdout text. Line 1 is the choice (`insufficient: <reason>` when insufficient). Line 2 is `flow <d>/<n>, no flow <d>/<n>, strata <entered>/<total>, p <p>, OR <or>`, with `-` for a value not computed and both numbers printed to three significant figures. Under the gate, line 3 is `provisional: M4 is unvalidated:E2; the counts and tables are the strata that would enter once it clears`.
  - `main()` returns `0` after printing `render(...)`, and `2` on `ReportError`, `KeyError`, `TypeError` or `ValueError`.

- [ ] **Step 1: Write the failing tests**

Append to `agents/bin/test_flow_outcome_verdict.py`:

```python
def run_main(report, monkeypatch, capsys):
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(report)))
    code = fv.main()
    out, err = capsys.readouterr()
    return code, out, err


def test_main_prints_choice_then_counts(monkeypatch, capsys):
    units = arm(S1, "a", True, 8, 12) + arm(S1, "b", False, 1, 12)
    code, out, _ = run_main(make_report(units), monkeypatch, capsys)
    lines = out.splitlines()
    assert code == 0 and lines[0] == "regression"
    assert lines[1].startswith("flow 8/12, no flow 1/12, strata 1/1, p ")
    assert not lines[2].startswith("provisional")


def test_main_under_the_gate_with_an_empty_cohort(monkeypatch, capsys):
    code, out, _ = run_main(make_report([], gate=True), monkeypatch, capsys)
    assert code == 0
    assert out.splitlines()[:3] == [
        "insufficient: unvalidated",
        "flow 0/0, no flow 0/0, strata 0/0, p -, OR -",
        "provisional: M4 is unvalidated:E2; the counts and tables are the strata that would enter once it clears"]


@pytest.mark.parametrize("text", ["null", "{}", "not json", '{"units": null}'])
def test_main_exits_2_on_a_malformed_report(text, monkeypatch, capsys):
    monkeypatch.setattr(sys, "stdin", io.StringIO(text))
    assert fv.main() == 2
    out, err = capsys.readouterr()
    assert out == "" and err.startswith("flow-outcome-verdict: ")


def test_conditions_cover_strata_joint_mix_outcomes_coverage_cost_and_limitations():
    units = arm(S1, "a", True, 1, 10) + arm(S1, "b", False, 0, 10)
    units[0]["links"] = [{"kind": "defect", "evidence": "recorded"}]
    units[0]["changes"] = 1
    units[1]["factors"]["model"]["values"] = ["gpt-5.6"]
    units[2]["output_tokens"] = None
    units[3]["extensions"] = 2
    units[10]["reopens"] = 1
    units.append(unit("u", S1, None, state="incomplete"))
    report = make_report(units)
    text = "\n".join(fv.conditions(fv.verdict(report), report))
    assert "tack s mid direct task: flow 1/10, no flow 0/10" in text
    assert "flow true, claude-code, claude-opus-5-5: 9" in text
    assert "flow true, claude-code, gpt-5.6: 1" in text
    assert "flow true: changes 1, extensions 2, reopened 0 of 10" in text
    assert "flow false: changes 0, extensions 0, reopened 1 of 10" in text
    assert "defective tasks, flow true: a0" in text
    assert "defective tasks, flow false: none" in text
    assert "flow true, recorded: 1" in text
    assert "flow false, no link: 10" in text
    assert "excluded authorship: incomplete 1" in text
    assert "flow true: median 100, total 900, missing 1" in text
    assert "no exposure: needs obs-db1316" in text
    assert "pre-start" in text and "uncommitted" in text


def test_conditions_leave_out_strata_that_did_not_enter():
    units = arm(S1, "a", True, 1, 12) + arm(S1, "b", False, 1, 12) \
        + arm(S2, "c", True, 3, 12) + arm(S2, "d", False, 1, 12)
    report = make_report(units, gate=True, suppressed={"s": "unvalidated:E2", "m": "low_retention"})
    text = "\n".join(fv.conditions(fv.verdict(report), report))
    assert "tack s mid direct task: flow 1/12, no flow 1/12" in text
    assert "not entered, low_retention: 1" in text
    assert "c0" not in text and "flow true, claude-code, claude-opus-5-5: 12" in text


def test_null_stratum_field_prints_as_dash():
    unsized = {**S1, "size": None}
    units = arm(unsized, "a", True, 0, 10) + arm(unsized, "b", False, 0, 10)
    report = make_report(units)
    assert "tack - mid direct task: flow 0/10, no flow 0/10" in fv.render(fv.verdict(report), report)
```

In the first conditions test, the `incomplete` unit sits in `S1`, which enters, so it is counted under excluded authorship there. Its empty value list makes it unassigned in both obs's row and the recount.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m pytest agents/bin/test_flow_outcome_verdict.py -q`
Expected: the new tests fail (`main` prints nothing; `conditions` and `render` are missing), except the four `test_main_exits_2_on_a_malformed_report` cases, which Task 2's `main` already passes; the 43 earlier tests pass.

- [ ] **Step 3: Write the implementation**

In `agents/bin/flow-outcome-verdict`, add `import statistics` to the imports, add beside the constants:

```python
EXCLUDED = ("incomplete", "mixed", "several", "unknown")
LIMITATIONS = (
    "cohort, not execution: pre-start skill loads count (obs credits a skill invoked at or "
    "before the task's end)",
    "cohort, not execution: a session keeps skill content it loaded earlier across later "
    "turns and resumptions",
    "cohort, not execution: harness homes load the skill from the main checkout's working "
    "tree, so uncommitted edits can run",
    "historical association: flow was chosen, not assigned; a verdict does not establish cause",
)
PROVISIONAL = (f"provisional: M4 is unvalidated:{GATE}; the counts and tables are the strata "
               f"that would enter once it clears")
```

add after `verdict`:

```python
def _name(value):
    return "-" if value is None else str(value)


def _arm(unit):
    credit = _credit(unit)
    return credit["values"][0] if credit["state"] == "attributed" and credit["values"] else None


def _attributed(unit, factor):
    credit = unit["factors"].get(factor, {"state": "unknown", "values": []})
    if credit["state"] != "attributed":
        return credit["state"]
    return "/".join(str(value) for value in credit["values"])


def _evidence(unit):
    kinds = {link["evidence"] for link in unit["links"] if link["kind"] == "defect"}
    return "recorded" if "recorded" in kinds else "inferred" if kinds else "no link"


def _flow(value):
    return f"flow {str(value).lower()}"


def conditions(result, report):
    """§5's tables over the scored cohort: the units of the entering strata (provisional
    ones under the gate). A stratum that did not enter is counted by reason, never
    described."""
    entered = {key for key, _ in result["entered"]}
    members = [unit for unit in result["units"] if stratum_key(unit["stratum"]) in entered]
    scored = [unit for unit in members if _arm(unit) is not None]
    arms = {flow: [unit for unit in scored if _arm(unit) is flow] for flow in (True, False)}
    lines = ["strata:"]
    for key, (fd, fn, od, on) in result["entered"]:
        lines.append(f"  {' '.join(_name(part) for part in key)}: flow {fd}/{fn}, no flow {od}/{on}")
    lines += [f"  not entered, {reason}: {count}" for reason, count in sorted(result["skipped"].items())]
    lines.append("flow x harness x model:")
    joint = collections.Counter((_arm(unit), _attributed(unit, "harness"), _attributed(unit, "model"))
                                for unit in scored)
    lines += [f"  {_flow(flow)}, {harness}, {model}: {count}"
              for (flow, harness, model), count in sorted(joint.items(), key=repr)]
    lines.append("after close (shown, not scored):")
    for flow, group in arms.items():
        lines.append(f"  {_flow(flow)}: changes {sum(u['changes'] for u in group)}, "
                     f"extensions {sum(u['extensions'] for u in group)}, "
                     f"reopened {sum(u['reopens'] > 0 for u in group)} of {len(group)}")
    for flow, group in arms.items():
        defective = sorted(unit["task"] for unit in group if unit["defects"] > 0)
        lines.append(f"  defective tasks, {_flow(flow)}: {' '.join(defective) or 'none'}")
    lines.append("coverage:")
    evidence = collections.Counter((_arm(unit), _evidence(unit)) for unit in scored)
    lines += [f"  {_flow(flow)}, {kind}: {count}"
              for (flow, kind), count in sorted(evidence.items(), key=repr)]
    excluded = collections.Counter(_credit(unit)["state"] for unit in members
                                   if _credit(unit)["state"] in EXCLUDED)
    lines.append("  excluded authorship: "
                 + (" ".join(f"{state} {count}" for state, count in sorted(excluded.items())) or "none"))
    lines.append("cost (output_tokens):")
    for flow, group in arms.items():
        known = [unit["output_tokens"] for unit in group if unit["output_tokens"] is not None]
        median = _name(statistics.median(known) if known else None)
        lines.append(f"  {_flow(flow)}: median {median}, total {sum(known)}, "
                     f"missing {len(group) - len(known)}")
    lines.append("limitations:")
    lines += [f"  {text}" for text in (*report["limitations"].values(), *LIMITATIONS)]
    return lines


def _number(value):
    return "-" if value is None or (isinstance(value, float) and math.isnan(value)) else f"{value:.3g}"


def render(result, report):
    head = result["choice"] if result["reason"] is None else f"{result['choice']}: {result['reason']}"
    (fd, fn), (od, on) = result["flow"], result["other"]
    counts = (f"flow {fd}/{fn}, no flow {od}/{on}, strata {len(result['entered'])}/{result['strata_total']}, "
              f"p {_number(result['p'])}, OR {_number(result['odds_ratio'])}")
    lines = [head, counts, *([PROVISIONAL] if result["provisional"] else []), *conditions(result, report)]
    return "\n".join(lines) + "\n"
```

and replace `main` with:

```python
def main():
    try:
        report = json.load(sys.stdin)
        text = render(verdict(report), report)
    except (ReportError, KeyError, TypeError, ValueError) as error:
        print(f"flow-outcome-verdict: {type(error).__name__}: {error}", file=sys.stderr)
        return 2
    sys.stdout.write(text)
    return 0
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m pytest agents/bin/test_flow_outcome_verdict.py -q`
Expected: 52 passed.

- [ ] **Step 5: Commit**

```bash
just test
git add agents/bin/flow-outcome-verdict agents/bin/test_flow_outcome_verdict.py
git commit -m "feat(evals): print flow-outcome-verdict conditions and counts"
```

---

### Task 5: The case file and its first live run

Blocked on `OBS_ID` (Task 1 wires the dependency): the live run needs `--until`, `--cohort`, `--units` and the cell `sum`. Steps 1 and 2 can be written before it lands; steps 3 to 5 wait.

**Files:**
- Create: `agents/evals/cases/flow-defects-after-close.md`

**Interfaces:**
- Consumes: `agents/bin/flow-outcome-verdict` (Tasks 2–4), the obs report contract (Global Constraints).

- [ ] **Step 1: Find the current blob and its window**

```bash
git log --format='%H %cI' -- agents/skills/flow/SKILL.md | head -3
git rev-parse HEAD:agents/skills/flow/SKILL.md
```

As of this plan the current blob is `9d90fb017099eb006f1e7d012f9aea5db944950a`, committed by `ba4395b` at 2026-09-29T20:15:27Z. The first whole UTC day at or after that is 2026-09-30, so the window is `2026-09-30..<run date>`. If a later commit has changed `SKILL.md` by the time this runs, use the blob and window that `git log` shows for the latest commit instead (§3, window boundaries). Earlier blobs (before 2026-09-29) live in the private archive and are out of this run's scope.

- [ ] **Step 2: Write the case file**

`agents/evals/cases/flow-defects-after-close.md` (Step 5 fills in `<run date>`, the choice and the reason). `observed` keeps the choice and its reason in separate fields, so `observed.value` is always one of `expected.choices`:

````markdown
---
id: flow-defects-after-close
title: No defect regression among tasks the flow skill carried while one version was current
subject:
  kind: flow
  name: flow skill (agents/skills/flow/SKILL.md)
  version: [blob:9d90fb017099eb006f1e7d012f9aea5db944950a, cohort 2026-09-30..<run date>]
inputs:
  - kind: query
    ref: obs --json outcomes report --since 2026-09-30 --until <run date> --cohort --units
    window: 2026-09-30..<run date>
expected:
  type: choice
  claim: the stratified M4 comparison of skill:flow true against false, read by the rule in docs/specs/2026-10-01-workflow-outcome-eval-design.md §4
  choices: [no-regression-detected, regression, insufficient]
  value: no-regression-detected
observed:
  value: <choice: the first line of the run up to any colon>
  reason: <the text after "insufficient: ", or null>
  at: blob:9d90fb017099eb006f1e7d012f9aea5db944950a, cohort 2026-09-30..<run date>
judge:
  kind: check
  command: obs --json outcomes report --since 2026-09-30 --until <run date> --cohort --units | agents/bin/flow-outcome-verdict
  cwd: tack checkout
  pass: prints no-regression-detected
source: [tack-026612, obs-00809f]
evidence: inferred
---

The first case judged from obs's derived tables rather than a session. It looks
for a defect regression after close (M4) among tasks that the flow skill carried
and that both started and closed while one `SKILL.md` blob was committed, against
comparable tasks closed without flow, stratum by stratum. Cost, change requests,
extensions and reopens are printed beside the verdict and never enter it; so are
the defective tasks' ids, for inspecting an alarm.

A verdict is about a cohort, not an execution: loads before a task's first start
count, a session keeps content it loaded earlier, and the harness homes load the
skill from the main checkout's working tree, uncommitted edits included. The
comparison is historical: flow was chosen for work its owner judged to need gates,
so `no-regression-detected` says only that this cohort gave no evidence of more
defects with flow (p < 0.1, one-sided, exact within strata), and `regression`
does not establish cause. Randomized arms (tack-7d9375) are the stronger evidence.

Until obs validates its defect links (E2, Wilson lower bound ≥ 0.7 on defect
precision), every run returns `insufficient: unvalidated`, with provisional
tables. That run checks the pipeline, not flow.

The window starts at the first whole UTC day after `ba4395b` committed this blob
(2026-09-29T20:15:27Z); the partial day 2026-09-29 is cut.

## Verdicts

<one entry per run, newest last: the §7 line, then the tool's remaining lines indented>
````

- [ ] **Step 3: Run the case live** (after `OBS_ID` is done)

```bash
obs --json outcomes report --since 2026-09-30 --until "$(date -u +%F)" --cohort --units > "$TMPDIR/flow-report.json"
agents/bin/flow-outcome-verdict < "$TMPDIR/flow-report.json" > "$TMPDIR/flow-verdict.txt"; echo "exit $?"
cat "$TMPDIR/flow-verdict.txt"
```

Expected while the E2 gate holds: exit 0, first line `insufficient: unvalidated`, third line the provisional note. An exit 2 is the tool refusing live data (a reconciliation mismatch, a duplicate, a malformed field). Stop and report it on `OBS_ID` with the printed message; do not edit the tool to pass.

- [ ] **Step 4: Cross-check the strata against the filtered M4 rows**

Count the `skill:flow` × `m4_defective` rows in the same JSON by suppression reason, independently of the tool:

```bash
python3 - "$TMPDIR/flow-report.json" <<'EOF'
import collections, json, sys
rows = [r for r in json.load(open(sys.argv[1]))["comparisons"]
        if r["factor"] == "skill:flow" and r["measure"] == "m4_defective"]
reasons = collections.Counter(r["suppressed_reason"] if r["suppressed"] else "shown" for r in rows)
print("rows", len(rows), dict(sorted(reasons.items())))
EOF
```

Check against the tool's output:
- `rows` equals the total in the tool's `strata <entered>/<total>`.
- The tool's `entered` plus its `not entered, one arm` count equals `shown` plus `unvalidated:E2` while the gate holds, and `shown` alone once it clears. A one-arm stratum is shown by obs but cannot enter the test, which is why it is counted separately.
- Each other reason (`unassigned`, `low_retention`) equals the tool's `not entered, <reason>` count.

Record any difference on `OBS_ID`.

- [ ] **Step 5: Record the verdict and commit**

Fill in `<run date>` (the `--until` date), `observed.value` (the choice alone: `insufficient`, `regression` or `no-regression-detected`) and `observed.reason` (`unvalidated`, `too few`, or `null`). Replace the Verdicts placeholder with:

```
<run date> blob:9d90fb0 cohort 2026-09-30..<run date> <first line> — <second line>
    <the tool's remaining lines, indented four spaces>
```

```bash
just test
git add agents/evals/cases/flow-defects-after-close.md
git commit -m "feat(evals): flow-defects-after-close case and its first run"
```
