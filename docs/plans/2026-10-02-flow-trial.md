# Randomized Flow Trial Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Assign flow on or off at random to work items in tack and obs, record the
assignment on the tasks, and judge the trial's effect on clean delivery with one
pre-registered read.

**Architecture:** Two Python tools in `agents/bin`. `trial-arm` does the record side.
It answers a session's lookup after `tasks start` and writes the frozen decision and
membership notes. It lists units and compliance (`status`) and writes the JSON census
(`census`). Its logic is pure functions over task records fetched from the `tasks` CLI.
`trial-verdict` does the analysis side. It reads the census and obs's outcomes report
and applies the spec's §6 rule. A trial file and a case file under `agents/evals/`,
plus one global rule in `AGENTS.md`, put the tools in front of every session.

**Tech Stack:** Python 3.11+ (stdlib plus PyYAML, already on the host's `python3`),
pytest, the `tasks` CLI (JSON output).

**Spec:** `docs/specs/2026-10-02-flow-trial-design.md` (approved at revision 4; 4.1
moved the session rule into the global instructions). Read it before any task. The
section numbers below refer to it.

## Global Constraints

- Trial file: `agents/evals/trials/flow-trial-1.md` with `id: flow-trial-1`,
  `factor: flow`, `arms: ["on", "off"]`, `projects: [tack, obs]`,
  `enroll: 2026-10-05..2026-11-29`, `close_by: 2027-01-10`,
  `follow_up_to: 2027-02-09`, `read_on: 2027-02-16`, `source: [tack-7d9375]`.
- Arm: `"on" if sha256("<trial id>:<unit root id>").digest()[0] & 1 else "off"`.
- Note texts, exactly:
  - `trial: <trial> — enrolled — flow on|off`
  - `trial: <trial> — not enrolled: <reason>`
  - `arm: <trial> — unit <root> — flow on|off|not enrolled`
  - `arm: <trial> — moved to unit <root> — flow on|off`
  - `arm: <trial> — override: <why>`
- Lookup lines, exactly:
  - `<trial>: flow on|off (unit <root>)`
  - `not enrolled: <reason>`, where the reason is `no trial for <prefix>`,
    `unit <root> first started <YYYY-MM-DD>, outside enroll`, or `not started`
  - `<trial>: flow on|off (moved from unit <a> to unit <b>)`, where `<a>` is the task's
    analysis unit and `<b>` its physical root (the top of its current parent chain)
- Treated: a `gate:` note for a state in `designed`, `planned`, `implementing` or
  `verified` on any member. `gate: scoped` never counts.
- Verdict choices: `flow-better`, `no-difference-detected`, `flow-worse`,
  `insufficient: <before read date|unvalidated|missing defect data|too few|compliance>`.
  Thresholds: α = 0.1, two-sided Fisher; 100 enrolled units per arm; 30 assessable
  units per arm; compliance 0.8; missing defect data 5% of delivered units; 90%
  Newcombe interval.
- Exit codes: `trial-arm` exits 0 with an answer, 1 when the task is missing, and 2
  when trials overlap, a note contradicts the function, or `tasks` fails.
  `trial-verdict` exits 0 with a verdict and 2 on malformed or disagreeing inputs.
- No machine-specific absolute paths in code or docs. Paths are resolved from
  `__file__`.
- Tests: `python3 -m pytest agents/bin/<file> -q` for the focused run (tack has no
  `test-one` or `test-fast` recipe), then `just test` before each commit.

## Review Focus

1. **A lookup run from a task worktree, where the record is newer than the main
   checkout's.** The lookup must read the local checkout when its prefix matches. A
   child filed in the worktree must be visible (Task 2,
   `test_records_reads_the_local_checkout_for_its_own_prefix`).
2. **Two sessions looking up tasks of one fresh unit at nearly the same time.** Both
   may write a decision note. They agree, because the decision is a function of the
   same records, and the census must accept two identical decision notes and refuse
   two that differ (Task 1,
   `test_decision_of_accepts_repeats_and_refuses_disagreement`).
3. **A trial file edited after opening with dates that no longer chain** (e.g.
   `follow_up_to` ≠ `close_by` + 30 after a halt that moved only one date). It must
   refuse to load, never run with inconsistent windows (Task 1,
   `test_parse_trial_refuses_broken_date_chain`).
4. **An id with a trailing period, as copied from prose** (`tack-1234ab.`). It must
   resolve like the tasks CLI does (Task 2,
   `test_main_strips_trailing_periods`).
5. **An obs report whose units lack `first_close_ms` or carry it as null for a task
   the census says is done.** The verdict must exit 2 with the task named, not crash
   or count it clean (Task 4, `test_null_close_in_obs_row_is_refused`).

---

### Task 1: trial-arm foundations: trial files, the arm, lifecycle and the unit tree

**Files:**
- Create: `agents/bin/trial-arm`
- Test: `agents/bin/test_trial_arm.py`

**Interfaces:**
- Produces, in `agents/bin/trial-arm` (tests load it as module `trial_arm`):
  - `class TrialError(Exception)` (exit 2), `class MissingTask(Exception)` (exit 1)
  - `@dataclass(frozen=True) class Trial(id: str, factor: str, projects: tuple[str, ...], enroll: tuple[date, date], close_by: date, follow_up_to: date, read_on: date)`
    with `active_on(day: date) -> bool`
  - `parse_trial(text: str, where: str) -> Trial`;
    `load_trials(directory: Path) -> list[Trial]`;
    `trial_for(trials, prefix: str, day: date) -> Trial | None`;
    `find_trial(trials, trial_id: str) -> Trial`
  - `arm_of(trial_id: str, root: str) -> str` (`"on"` or `"off"`)
  - `first_start(task) -> datetime | None`, `first_done(task) -> datetime | None`,
    `state_on(task, day: date) -> str` (`done|dropped|shelved|open`),
    `reopened(task, day: date) -> bool`, `gates_past_scoped(task) -> list[str]`,
    `gated(task) -> bool`. `gates_past_scoped`, `overridden` and `moves_of` take an
    optional `until: date`; with it, only notes on or before that UTC day count
  - `@dataclass(frozen=True) class Decision(enrolled: bool, arm: str | None, reason: str | None, recorded: bool)`
  - `member_of(task, trial_id) -> tuple[str, str | None] | None` (unit, arm or None
    for not enrolled); `decision_of(task, trial_id) -> Decision | None`;
    `moves_of(task, trial_id) -> list[tuple[str, str]]`;
    `overridden(task, trial_id) -> bool`
  - `class Tree(records: dict[str, dict], trial_id: str)` with `task(id)`,
    `parent(id)`, `computed_root(id)`, `resolved_unit(id)`, `unit_of(id)`,
    `members(root) -> list[str]`
  - `decide(trial, tree, root) -> Decision | None`

- [ ] **Step 1: Write the failing tests**

`agents/bin/test_trial_arm.py`:

```python
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m pytest agents/bin/test_trial_arm.py -q`
Expected: collection error, `FileNotFoundError` for `trial-arm`.

- [ ] **Step 3: Write the foundations**

`agents/bin/trial-arm`:

```python
#!/usr/bin/env python3
"""Randomized trial arms (docs/specs/2026-10-02-flow-trial-design.md).

trial-arm <task-id>             the arm to follow after `tasks start`; writes the trial's notes once
trial-arm status <trial-id>     enrolled units with treatment and compliance so far
trial-arm census <trial-id>     the JSON census trial-verdict reads

Trials are agents/evals/trials/*.md. Exits 0 with an answer, 1 when the task is missing,
2 when trial files overlap on a project, a recorded note contradicts the function, or
the tasks CLI fails.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

import yaml

TRIALS = Path(__file__).resolve().parent.parent / "evals" / "trials"
TREATED = ("designed", "planned", "implementing", "verified")
FOLLOW_UP_DAYS = 30
FIELDS = ("id", "factor", "arms", "projects", "enroll", "close_by", "follow_up_to", "read_on")
GATE_RE = re.compile(r"^gate:\s*([A-Za-z]+)")
DECISION_RE = re.compile(r"^trial: (?P<trial>\S+) — (?:enrolled — flow (?P<arm>on|off)|not enrolled: (?P<reason>.+))$")
MEMBER_RE = re.compile(r"^arm: (?P<trial>\S+) — unit (?P<unit>\S+) — (?:flow (?P<arm>on|off)|not enrolled)$")
MOVE_RE = re.compile(r"^arm: (?P<trial>\S+) — moved to unit (?P<unit>\S+) — flow (?P<arm>on|off)$")
OVERRIDE_RE = re.compile(r"^arm: (?P<trial>\S+) — override: .+$")


class TrialError(Exception):
    """Trial files, recorded notes or the tasks CLI contradict the run (exit 2)."""


class MissingTask(Exception):
    """The task is not in its project's records (exit 1)."""


@dataclass(frozen=True)
class Trial:
    id: str
    factor: str
    projects: tuple
    enroll: tuple
    close_by: dt.date
    follow_up_to: dt.date
    read_on: dt.date

    def active_on(self, day):
        return self.enroll[0] <= day <= self.close_by


@dataclass(frozen=True)
class Decision:
    enrolled: bool
    arm: str | None
    reason: str | None
    recorded: bool


def _day(value, where):
    if isinstance(value, dt.date):
        return value
    try:
        return dt.date.fromisoformat(str(value))
    except ValueError:
        raise TrialError(f"{where} is {value!r}, not a YYYY-MM-DD date") from None


def parse_trial(text, where):
    parts = text.split("---\n")
    if len(parts) < 3 or parts[0] != "":
        raise TrialError(f"{where} has no frontmatter")
    meta = yaml.safe_load(parts[1])
    missing = [name for name in FIELDS if name not in meta]
    if missing:
        raise TrialError(f"{where} lacks {missing}")
    if meta["factor"] != "flow" or list(meta["arms"]) != ["on", "off"]:
        raise TrialError(f"{where}: only factor flow with arms [on, off] is supported")
    start, sep, end = str(meta["enroll"]).partition("..")
    if not sep:
        raise TrialError(f"{where}: enroll is {meta['enroll']!r}, not <from>..<to>")
    trial = Trial(id=str(meta["id"]), factor="flow", projects=tuple(meta["projects"]),
                  enroll=(_day(start, f"{where} enroll"), _day(end, f"{where} enroll")),
                  close_by=_day(meta["close_by"], f"{where} close_by"),
                  follow_up_to=_day(meta["follow_up_to"], f"{where} follow_up_to"),
                  read_on=_day(meta["read_on"], f"{where} read_on"))
    if not trial.enroll[0] <= trial.enroll[1] < trial.close_by:
        raise TrialError(f"{where}: enroll must end before close_by")
    if trial.follow_up_to != trial.close_by + dt.timedelta(days=FOLLOW_UP_DAYS):
        raise TrialError(f"{where}: follow_up_to must be close_by plus {FOLLOW_UP_DAYS} days")
    if trial.read_on <= trial.follow_up_to:
        raise TrialError(f"{where}: read_on must be after follow_up_to")
    return trial


def load_trials(directory=TRIALS):
    trials = [parse_trial(path.read_text(), str(path.name)) for path in sorted(directory.glob("*.md"))]
    ids = [trial.id for trial in trials]
    if len(set(ids)) != len(ids):
        raise TrialError(f"duplicate trial ids in {directory.name}: {sorted(ids)}")
    for i, a in enumerate(trials):
        for b in trials[i + 1:]:
            shared = set(a.projects) & set(b.projects)
            if shared and a.enroll[0] <= b.close_by and b.enroll[0] <= a.close_by:
                raise TrialError(f"trials {a.id} and {b.id} overlap on {sorted(shared)}")
    return trials


def trial_for(trials, prefix, day):
    found = [trial for trial in trials if prefix in trial.projects and trial.active_on(day)]
    return found[0] if found else None


def find_trial(trials, trial_id):
    for trial in trials:
        if trial.id == trial_id:
            return trial
    raise TrialError(f"no trial {trial_id}")


def arm_of(trial_id, root):
    return "on" if hashlib.sha256(f"{trial_id}:{root}".encode()).digest()[0] & 1 else "off"


def _at(note):
    return dt.datetime.fromisoformat(note["at"].replace("Z", "+00:00"))


def _kind(text):
    if text == "started":
        return "start"
    if text == "resumed":
        return "resume"
    if text in ("done", "dropped"):
        return text
    if text == "shelved" or text.startswith("shelved:"):
        return "shelved"
    return None


def events(task):
    return [(_at(note), kind) for note in task.get("notes", []) if (kind := _kind(note["text"]))]


def first_start(task):
    return next((at for at, kind in events(task) if kind == "start"), None)


def first_done(task):
    return next((at for at, kind in events(task) if kind == "done"), None)


def state_on(task, day):
    state = "open"
    for at, kind in events(task):
        if at.date() > day:
            break
        state = kind if kind in ("done", "dropped", "shelved") else "open"
    return state


def reopened(task, day):
    done = first_done(task)
    return done is not None and any(
        kind in ("start", "resume") and at > done and at.date() <= day for at, kind in events(task))


def _gate_states(task):
    return [m.group(1) for note in task.get("notes", []) if (m := GATE_RE.match(note["text"]))]


def _notes(task, until=None):
    return [note for note in task.get("notes", []) if until is None or _at(note).date() <= until]


def gates_past_scoped(task, until=None):
    return [m.group(1) for note in _notes(task, until)
            if (m := GATE_RE.match(note["text"])) and m.group(1) in TREATED]


def gated(task):
    return bool(_gate_states(task))


def _matches(task, regex, trial_id, until=None):
    return [m for note in _notes(task, until)
            if (m := regex.match(note["text"])) and m["trial"] == trial_id]


def member_of(task, trial_id):
    found = _matches(task, MEMBER_RE, trial_id)
    return (found[0]["unit"], found[0]["arm"]) if found else None


def decision_of(task, trial_id):
    found = {(m["arm"], m["reason"]) for m in _matches(task, DECISION_RE, trial_id)}
    if len(found) > 1:
        raise TrialError(f"task {task['id']} carries conflicting {trial_id} decision notes: {sorted(found, key=repr)}")
    if not found:
        return None
    arm, reason = found.pop()
    return Decision(arm is not None, arm, reason, True)


def moves_of(task, trial_id, until=None):
    return [(m["unit"], m["arm"]) for m in _matches(task, MOVE_RE, trial_id, until)]


def overridden(task, trial_id, until=None):
    return bool(_matches(task, OVERRIDE_RE, trial_id, until))


def _prefix(task_id):
    return task_id.partition("-")[0]


class Tree:
    """One trial's view of task records: parents within a project, units, members."""

    def __init__(self, records, trial_id):
        self.records = records
        self.trial_id = trial_id

    def task(self, task_id):
        if task_id not in self.records:
            raise MissingTask(task_id)
        return self.records[task_id]

    def parent(self, task_id):
        parent = self.task(task_id).get("parent")
        if parent in self.records and _prefix(parent) == _prefix(task_id):
            return parent
        return None

    def computed_root(self, task_id):
        unit = task_id
        while (parent := self.parent(unit)) is not None and self.records[parent].get("process"):
            unit = parent
        return unit

    def resolved_unit(self, task_id):
        root = self.computed_root(task_id)
        recorded = member_of(self.records[root], self.trial_id)
        return recorded[0] if recorded else root

    def unit_of(self, task_id):
        recorded = member_of(self.task(task_id), self.trial_id)
        return recorded[0] if recorded else self.resolved_unit(task_id)

    def members(self, root):
        return sorted(task_id for task_id in self.records if self.unit_of(task_id) == root)


def decide(trial, tree, root):
    """The unit's frozen decision when its root records one; otherwise a fresh one from
    the tree, or None while no member has started."""
    recorded = decision_of(tree.task(root), trial.id)
    if recorded is not None:
        return recorded
    starts = [at for task_id in tree.members(root) if (at := first_start(tree.records[task_id]))]
    if not starts:
        return None
    earliest = min(starts).date()
    if trial.enroll[0] <= earliest <= trial.enroll[1]:
        return Decision(True, arm_of(trial.id, root), None, False)
    return Decision(False, None, f"unit {root} first started {earliest}, outside enroll", False)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `chmod +x agents/bin/trial-arm && python3 -m pytest agents/bin/test_trial_arm.py -q`
Expected: all pass.

- [ ] **Step 5: Run the suite and commit**

```bash
just test
git add agents/bin/trial-arm agents/bin/test_trial_arm.py
git commit -m "feat(trial-arm): trial files, arm function, lifecycle and units"
```

### Task 2: trial-arm lookup, the tasks client and the CLI

**Files:**
- Modify: `agents/bin/trial-arm` (append after `decide`)
- Test: `agents/bin/test_trial_arm.py` (append)

**Interfaces:**
- Consumes: everything Task 1 produces.
- Produces:
  - `check(trial, tree) -> None`: raises `TrialError` when a recorded arm, decision or
    membership contradicts the function or the unit's decision
  - `@dataclass class Lookup(line: str, writes: list[tuple[str, str]])`
  - `lookup(trial, tree, task_id) -> Lookup` (pure; the writes are `(task_id, note text)`).
    Two roots are kept apart: the **analysis unit** (`tree.unit_of`, frozen by notes) decides
    enrollment and arm, and the **physical root** (`tree.computed_root`, the tree as it
    stands) decides how the work runs when the two belong to different units.
  - `decision_text(trial, d)`, `member_text(trial, unit, d)`, `move_text(trial, unit, arm) -> str`
  - `class Tasks(exe: str | None = None)` with `records(prefix) -> dict[str, dict]` and
    `note(task_id, text)`. The executable is `TRIAL_ARM_TASKS` when set, else `tasks`.
    Every call passes `--json`, so a `TASKS_FORMAT=pretty` environment cannot break it
  - `local_prefix(cwd=None) -> str | None`
  - `main(argv=None, tasks=None, trials_dir=TRIALS, today=None) -> int`
    (`status` and `census` are added in Task 3)

- [ ] **Step 1: Write the failing tests**

Append to `agents/bin/test_trial_arm.py`:

```python
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m pytest agents/bin/test_trial_arm.py -q`
Expected: the new tests fail with `AttributeError: module 'trial_arm' has no attribute 'lookup'` (and `check`, `Tasks`, `main`, `local_prefix`).

- [ ] **Step 3: Write the lookup, the client and the CLI**

Add `import json`, `import os`, `import subprocess`, `import sys` and `import tomllib`
to the imports of `agents/bin/trial-arm`. Add the constant
`STATUSES = ("idea", "todo", "doing", "blocked", "shelved", "done", "dropped")` below
`TREATED`, and append:

```python
def decision_text(trial, d):
    if d.enrolled:
        return f"trial: {trial.id} — enrolled — flow {d.arm}"
    return f"trial: {trial.id} — not enrolled: {d.reason}"


def member_text(trial, unit, d):
    return f"arm: {trial.id} — unit {unit} — " + (f"flow {d.arm}" if d.enrolled else "not enrolled")


def move_text(trial, unit, arm):
    return f"arm: {trial.id} — moved to unit {unit} — flow {arm}"


def check(trial, tree):
    """Refuse records whose trial notes contradict the arm function or their unit's decision."""
    for task_id, task in tree.records.items():
        decision = decision_of(task, trial.id)
        if decision is not None and decision.enrolled and decision.arm != arm_of(trial.id, task_id):
            raise TrialError(f"{task_id}: decision flow {decision.arm} contradicts the arm function "
                             f"(flow {arm_of(trial.id, task_id)})")
        member = member_of(task, trial.id)
        if member is None:
            continue
        unit, arm = member
        if arm is not None and arm != arm_of(trial.id, unit):
            raise TrialError(f"{task_id}: recorded flow {arm} for unit {unit} contradicts the arm function")
        unit_decision = decision_of(tree.records[unit], trial.id) if unit in tree.records else None
        if unit_decision is not None and unit_decision.arm != arm:
            raise TrialError(f"{task_id}: recorded arm {arm} contradicts unit {unit}'s decision {unit_decision.arm}")


@dataclass
class Lookup:
    line: str
    writes: list


def _answer(trial, unit, d):
    return f"{trial.id}: flow {d.arm} (unit {unit})" if d.enrolled else f"not enrolled: {d.reason}"


def _freeze(trial, tree, unit, d, task_id, writes):
    """Record a fresh decision on the unit's root together with the root's own membership,
    so a root moved before its own lookup still belongs to the unit it decided."""
    if d.recorded:
        return
    writes.append((unit, decision_text(trial, d)))
    if unit != task_id and member_of(tree.task(unit), trial.id) is None:
        writes.append((unit, member_text(trial, unit, d)))


def lookup(trial, tree, task_id):
    """What the session follows after `tasks start`, and the notes to write (§4).

    The analysis unit (frozen by the task's `arm:` note, else resolved from the tree)
    decides enrollment and arm. The physical root (the top of the task's current parent
    chain) decides execution when it belongs to another unit: that unit's arm when it is
    enrolled, otherwise the root's actual workflow (flow when it carries any gate)."""
    task = tree.task(task_id)
    check(trial, tree)
    writes = []
    member = member_of(task, trial.id)
    unit = member[0] if member else tree.resolved_unit(task_id)
    d = decide(trial, tree, unit)
    if d is None:
        return Lookup("not enrolled: not started", [])
    _freeze(trial, tree, unit, d, task_id, writes)
    if member is None:
        writes.append((task_id, member_text(trial, unit, d)))
    root = tree.computed_root(task_id)
    root_unit = tree.unit_of(root)
    if root_unit == unit:
        return Lookup(_answer(trial, unit, d), writes)
    rd = decide(trial, tree, root_unit)
    if rd is not None:
        _freeze(trial, tree, root_unit, rd, task_id, writes)
    if rd is not None and rd.enrolled:
        arm = rd.arm
    elif d.enrolled:
        arm = "on" if gated(tree.task(root)) else "off"
    else:
        return Lookup(_answer(trial, unit, d), writes)
    if (root, arm) not in moves_of(task, trial.id):
        writes.append((task_id, move_text(trial, root, arm)))
    return Lookup(f"{trial.id}: flow {arm} (moved from unit {unit} to unit {root})", writes)


def local_prefix(cwd=None):
    """The tasks prefix of the checkout containing `cwd`, or None outside one."""
    top = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=cwd, text=True, capture_output=True)
    if top.returncode != 0:
        return None
    config = Path(top.stdout.strip()) / "tasks" / ".config.toml"
    if not config.exists():
        return None
    return tomllib.loads(config.read_text()).get("prefix")


class Tasks:
    """The tasks CLI. A project read from inside its own checkout (a task worktree
    included) reads that checkout, whose records may be newer than the main one's."""

    def __init__(self, exe=None):
        self.exe = exe or os.environ.get("TRIAL_ARM_TASKS", "tasks")

    def _run(self, *args):
        r = subprocess.run([self.exe, *args], text=True, capture_output=True)
        if r.returncode != 0:
            raise TrialError(f"tasks {' '.join(args[:2])} failed: {(r.stderr or r.stdout).strip()}")
        return r.stdout

    def records(self, prefix):
        scope = [] if local_prefix() == prefix else ["--project", prefix]
        statuses = [arg for status in STATUSES for arg in ("--status", status)]
        listed = json.loads(self._run("list", "--json", *scope, *statuses))["tasks"]
        return {row["id"]: json.loads(self._run("show", "--json", row["id"]))["task"] for row in listed}

    def note(self, task_id, text):
        self._run("note", "--json", task_id, text)


def main(argv=None, tasks=None, trials_dir=TRIALS, today=None):
    argv = sys.argv[1:] if argv is None else argv
    tasks = tasks or Tasks()
    today = today or dt.datetime.now(dt.timezone.utc).date()
    try:
        trials = load_trials(trials_dir)
        if len(argv) == 1 and not argv[0].startswith("-") and argv[0] not in ("status", "census"):
            task_id = argv[0].rstrip(".")
            trial = trial_for(trials, _prefix(task_id), today)
            if trial is None:
                print(f"not enrolled: no trial for {_prefix(task_id)}")
                return 0
            result = lookup(trial, Tree(tasks.records(_prefix(task_id)), trial.id), task_id)
            for target, text in result.writes:
                tasks.note(target, text)
            print(result.line)
            return 0
        print(__doc__.strip(), file=sys.stderr)
        return 2
    except MissingTask as missing:
        print(f"trial-arm: no task {missing}", file=sys.stderr)
        return 1
    except TrialError as error:
        print(f"trial-arm: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m pytest agents/bin/test_trial_arm.py -q`
Expected: all pass.

- [ ] **Step 5: Run the suite and commit**

```bash
just test
git add agents/bin/trial-arm agents/bin/test_trial_arm.py
git commit -m "feat(trial-arm): lookup with frozen decisions, membership and moves"
```

### Task 3: trial-arm census and status

**Files:**
- Modify: `agents/bin/trial-arm` (append before `main`; extend `main`)
- Test: `agents/bin/test_trial_arm.py` (append)

**Interfaces:**
- Consumes: Tasks 1 and 2.
- Produces:
  - `census(trial, tree, as_of: date) -> dict`, the JSON object
    `{"trial", "as_of", "close_by", "units": [Unit], "decided_late": {"on": int, "off": int}, "conflicts": [{"task", "recorded", "computed"}]}`,
    where each `Unit` is
    `{"root", "arm", "decision": "recorded"|"decided late", "enrolled_at", "first_done", "state", "reopened", "stratum": {"project", "size", "complexity", "process"}, "treated", "compliant": bool|None, "members": [{"task", "first_start", "first_done", "gates", "override", "moves": [{"unit", "arm"}]}]}`
    and timestamps are `YYYY-MM-DDTHH:MM:SSZ` or null
  - `compliance(units) -> {"on"|"off": {"enrolled", "assessable", "compliant", "rate"}}`
  - `status_lines(trial, report: dict) -> list[str]`
  - `main` gains `status <trial-id>` (as of `min(today, close_by)`) and
    `census <trial-id>` (as of `close_by`; JSON on stdout). Both read every project in
    the trial.

- [ ] **Step 1: Write the failing tests**

Append to `agents/bin/test_trial_arm.py`:

```python
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
```

The fake `tasks` lists every stored task for both projects, so the census must keep
only units whose root's prefix is in the trial. Both roots here are in it.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m pytest agents/bin/test_trial_arm.py -q`
Expected: the new tests fail with `AttributeError` for `census`, `compliance` and `status_lines`.

- [ ] **Step 3: Write the census and status**

Append before `main` in `agents/bin/trial-arm`:

```python
HALT_ASSESSABLE = 15
HALT_RATE = 0.8


def _iso(at):
    return None if at is None else at.strftime("%Y-%m-%dT%H:%M:%SZ")


def _unit(trial, tree, root, d, as_of):
    root_task = tree.records[root]
    members = []
    for task_id in tree.members(root):
        task = tree.records[task_id]
        members.append({"task": task_id, "first_start": _iso(first_start(task)),
                        "first_done": _iso(first_done(task)), "gates": gates_past_scoped(task, as_of),
                        "override": overridden(task, trial.id, as_of),
                        "moves": [{"unit": unit, "arm": arm} for unit, arm in moves_of(task, trial.id, as_of)]})
    starts = [first_start(tree.records[m["task"]]) for m in members if m["first_start"]]
    done = first_done(root_task)
    treated = any(m["gates"] for m in members)
    compliant = None
    if done is not None and done.date() <= as_of:
        compliant = (treated == (d.arm == "on")
                     and not any(m["override"] for m in members)
                     and all(move["arm"] == d.arm for m in members for move in m["moves"]))
    return {"root": root, "arm": d.arm, "decision": "recorded" if d.recorded else "decided late",
            "enrolled_at": _iso(min(starts)), "first_done": _iso(done),
            "state": state_on(root_task, as_of), "reopened": reopened(root_task, as_of),
            "stratum": {"project": _prefix(root), "size": root_task.get("size"),
                        "complexity": root_task.get("complexity"), "process": root_task.get("process")},
            "treated": treated, "compliant": compliant, "members": members}


def census(trial, tree, as_of):
    """Every enrolled unit as of `as_of` (§6 input 1)."""
    check(trial, tree)
    units, late = [], {"on": 0, "off": 0}
    roots = sorted({tree.unit_of(task_id) for task_id in tree.records if _prefix(task_id) in trial.projects})
    for root in roots:
        if root not in tree.records:
            continue
        d = decide(trial, tree, root)
        if d is None or not d.enrolled:
            continue
        if not d.recorded:
            late[d.arm] += 1
        units.append(_unit(trial, tree, root, d, as_of))
    conflicts = [{"task": task_id, "recorded": tree.unit_of(task_id), "computed": tree.resolved_unit(task_id)}
                 for task_id in sorted(tree.records)
                 if member_of(tree.records[task_id], trial.id) and tree.unit_of(task_id) != tree.resolved_unit(task_id)]
    return {"trial": trial.id, "as_of": as_of.isoformat(), "close_by": trial.close_by.isoformat(),
            "units": units, "decided_late": late, "conflicts": conflicts}


def compliance(units):
    summary = {}
    for arm in ("on", "off"):
        assessed = [u for u in units if u["arm"] == arm and u["compliant"] is not None]
        complied = sum(u["compliant"] for u in assessed)
        summary[arm] = {"enrolled": sum(u["arm"] == arm for u in units), "assessable": len(assessed),
                        "compliant": complied, "rate": complied / len(assessed) if assessed else None}
    return summary


def status_lines(trial, report):
    summary = compliance(report["units"])
    lines = [f"{trial.id} as of {report['as_of']}: " + "; ".join(
        f"{arm} {s['enrolled']} enrolled, {s['assessable']} assessable, {s['compliant']} compliant"
        + (f" ({s['rate']:.2f})" if s["rate"] is not None else "") for arm, s in summary.items())]
    for u in report["units"]:
        verdict = "unassessable" if u["compliant"] is None else ("compliant" if u["compliant"] else "non-compliant")
        lines.append(f"{u['root']} flow {u['arm']} {u['state']} {'treated' if u['treated'] else 'untreated'} {verdict}")
    for arm, s in summary.items():
        if all(x["assessable"] >= HALT_ASSESSABLE for x in summary.values()) and s["rate"] < HALT_RATE:
            lines.append(f"halt: compliance below {HALT_RATE} in {arm} (spec §7)")
    return lines


def _trial_tree(tasks, trial):
    records = {}
    for project in trial.projects:
        records.update(tasks.records(project))
    return Tree(records, trial.id)
```

In `main`, before the usage fallback, add:

```python
        if len(argv) == 2 and argv[0] in ("status", "census"):
            trial = find_trial(trials, argv[1])
            tree = _trial_tree(tasks, trial)
            if argv[0] == "census":
                print(json.dumps(census(trial, tree, trial.close_by), indent=2))
            else:
                print("\n".join(status_lines(trial, census(trial, tree, min(today, trial.close_by)))))
            return 0
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m pytest agents/bin/test_trial_arm.py -q`
Expected: all pass.

- [ ] **Step 5: Run the suite and commit**

```bash
just test
git add agents/bin/trial-arm agents/bin/test_trial_arm.py
git commit -m "feat(trial-arm): census and status with unit compliance"
```

### Task 4: trial-verdict

**Files:**
- Create: `agents/bin/trial-verdict`
- Test: `agents/bin/test_trial_verdict.py`

**Interfaces:**
- Consumes: `trial_arm.parse_trial`, `trial_arm.arm_of`, `trial_arm.TrialError` (loaded
  from the sibling `trial-arm` file), and the census shape from Task 3. From obs-0491f1's
  `--units` rows it reads `task`, `first_start_ms`, `first_close_ms`, `defects`,
  `changes`, `extensions`, `reopens` and `output_tokens`, and from the report
  `unvalidated.measures.m4`.
- Produces: `fisher_two_sided(a, b, c, d) -> float`, `wilson(x, n, z) -> (lo, hi)`,
  `newcombe(x1, n1, x2, n2, z) -> (diff, lo, hi)`,
  `read_inputs(trial, census, report) -> dict[str, dict]` (validates both inputs and
  their agreement, returns the obs rows by task), `judge(trial, census, report) -> list[str]`,
  `main(argv=None, stdin=None, stdout=None) -> int`. `--validate` checks the inputs and
  prints one line naming only how many census units and matching obs rows were read, so
  the live pipeline can be checked before `read_on` without showing any outcome.

- [ ] **Step 1: Write the failing tests**

`agents/bin/test_trial_verdict.py`:

```python
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m pytest agents/bin/test_trial_verdict.py -q`
Expected: collection error, `FileNotFoundError` for `trial-verdict`.

- [ ] **Step 3: Write the verdict tool**

`agents/bin/trial-verdict`:

```python
#!/usr/bin/env python3
"""Judge a randomized flow trial from its census and an obs outcomes report.

trial-arm census <trial-id> > census.json
obs --json outcomes report --since <enroll start> --until <close_by> --cohort --units \\
  | trial-verdict <trial file> --census census.json [--as-of YYYY-MM-DD]

Spec docs/specs/2026-10-02-flow-trial-design.md §6. The first line is the choice:
flow-better, no-difference-detected, flow-worse, or insufficient: <reason>. Exits 0 with
a verdict, 2 when the inputs are malformed or disagree.
"""

import argparse
import datetime as dt
import importlib.machinery
import importlib.util
import json
import math
import statistics
import sys
from fractions import Fraction
from pathlib import Path


def _load_trial_arm():
    path = Path(__file__).resolve().with_name("trial-arm")
    loader = importlib.machinery.SourceFileLoader("trial_arm", str(path))
    module = importlib.util.module_from_spec(importlib.util.spec_from_loader("trial_arm", loader))
    sys.modules["trial_arm"] = module
    loader.exec_module(module)
    return module


ta = _load_trial_arm()

ALPHA = 0.1
MIN_ARM = 100
MIN_ASSESSABLE = 30
MIN_COMPLIANCE = 0.8
MAX_UNKNOWN = 0.05
Z90 = 1.6448536269514722
LIMITS = (
    "limit: a unit that flow's gates stop on purpose counts against flow",
    "limit: defects are watched only after first closes; work reopened and closed again "
    "has its later episode unobserved (reopens per arm are shown)",
)


class InputError(Exception):
    """The census and the report cannot be read together (exit 2)."""


def _field(container, name, kind, where):
    if not isinstance(container, dict) or name not in container:
        raise InputError(f"{where} lacks {name!r}")
    value = container[name]
    if not isinstance(value, kind) or isinstance(value, bool) and kind is int:
        raise InputError(f"{where}.{name} is {value!r}, not {kind.__name__}")
    return value


def _day_ms(ms):
    return dt.datetime.fromtimestamp(ms / 1000, dt.timezone.utc).date()


def _day_iso(text):
    return None if text is None else dt.date.fromisoformat(text[:10])


def fisher_two_sided(a, b, c, d):
    r1, r2, c1 = a + b, c + d, a + c
    total = math.comb(r1 + r2, c1)

    def p(x):
        return Fraction(math.comb(r1, x) * math.comb(r2, c1 - x), total)

    observed = p(a)
    return float(sum(p(x) for x in range(max(0, c1 - r2), min(c1, r1) + 1) if p(x) <= observed))


def wilson(x, n, z=Z90):
    if n == 0:
        return 0.0, 1.0
    phat = x / n
    denom = 1 + z * z / n
    centre = (phat + z * z / (2 * n)) / denom
    half = z * math.sqrt(phat * (1 - phat) / n + z * z / (4 * n * n)) / denom
    return centre - half, centre + half


def newcombe(x1, n1, x2, n2, z=Z90):
    p1, p2 = x1 / n1, x2 / n2
    l1, u1 = wilson(x1, n1, z)
    l2, u2 = wilson(x2, n2, z)
    d = p1 - p2
    return d, d - math.sqrt((p1 - l1) ** 2 + (u2 - p2) ** 2), d + math.sqrt((u1 - p1) ** 2 + (p2 - l2) ** 2)


COUNTS = ("defects", "changes", "extensions", "reopens")
STATES = ("done", "dropped", "shelved", "open")
GATE_STATUSES = ("E2",)


def _count(value, where):
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise InputError(f"{where} is {value!r}, not a count")
    return value


def _timestamp(value, where):
    if value is None:
        return None
    if not isinstance(value, str):
        raise InputError(f"{where} is {value!r}, not a timestamp")
    try:
        dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise InputError(f"{where} is {value!r}, not a timestamp") from None
    return value


def _rows(report):
    rows = {}
    for row in _field(report, "units", list, "report"):
        task = _field(row, "task", str, "obs row")
        if task in rows:
            raise InputError(f"duplicate obs row for {task}")
        for name in ("first_start_ms", "first_close_ms", *COUNTS):
            _count(_field(row, name, int, f"obs row {task}"), f"obs row {task}.{name}")
        if "output_tokens" not in row:
            raise InputError(f"obs row {task} lacks 'output_tokens'")
        if row["output_tokens"] is not None:
            _count(row["output_tokens"], f"obs row {task}.output_tokens")
        rows[task] = row
    return rows


def _gate_holds(report):
    """A missing m4 key clears the gate; "E2" holds it; anything else is malformed."""
    measures = _field(_field(report, "unvalidated", dict, "report"), "measures", dict, "report.unvalidated")
    if "m4" not in measures:
        return False
    if measures["m4"] not in GATE_STATUSES:
        raise InputError(f"invalid validation status for m4: {measures['m4']!r}")
    return True


def _census_shape(census):
    _field(census, "trial", str, "census")
    _field(census, "as_of", str, "census")
    late = _field(census, "decided_late", dict, "census")
    if set(late) != {"on", "off"}:
        raise InputError(f"census.decided_late has keys {sorted(late)}, not on and off")
    for arm in ("on", "off"):
        _count(late[arm], f"census.decided_late.{arm}")
    _field(census, "conflicts", list, "census")
    for u in _field(census, "units", list, "census"):
        root = _field(u, "root", str, "census unit")
        where = f"census unit {root}"
        if _field(u, "arm", str, where) not in ("on", "off"):
            raise InputError(f"{where}.arm is {u['arm']!r}")
        if _field(u, "decision", str, where) not in ("recorded", "decided late"):
            raise InputError(f"{where}.decision is {u['decision']!r}")
        if _field(u, "state", str, where) not in STATES:
            raise InputError(f"{where}.state is {u['state']!r}")
        for name in ("enrolled_at", "first_done"):
            if name not in u:
                raise InputError(f"{where} lacks {name!r}")
            _timestamp(u[name], f"{where}.{name}")
        _field(u, "reopened", bool, where)
        _field(u, "treated", bool, where)
        if "compliant" not in u or not (u["compliant"] is None or isinstance(u["compliant"], bool)):
            raise InputError(f"{where}.compliant is {u.get('compliant')!r}, not true, false or null")
        stratum = _field(u, "stratum", dict, where)
        for name in ("project", "size", "complexity", "process"):
            if name not in stratum:
                raise InputError(f"{where}.stratum lacks {name!r}")
        members = _field(u, "members", list, where)
        if not members:
            raise InputError(f"{where} has no members")
        for m in members:
            task = _field(m, "task", str, f"{where} member")
            for name in ("first_start", "first_done"):
                if name not in m:
                    raise InputError(f"{where} member {task} lacks {name!r}")
                _timestamp(m[name], f"{where} member {task}.{name}")
            _field(m, "gates", list, f"{where} member {task}")
            _field(m, "override", bool, f"{where} member {task}")
            _field(m, "moves", list, f"{where} member {task}")


def read_inputs(trial, census, report):
    """Validate both inputs and their agreement; return the obs rows by task."""
    _census_shape(census)
    rows = _rows(report)
    _gate_holds(report)
    if census["trial"] != trial.id:
        raise InputError(f"census is for {census['trial']!r}, not {trial.id}")
    if census["as_of"] != trial.close_by.isoformat():
        raise InputError(f"census is as of {census['as_of']!r}, not close_by {trial.close_by}")
    seen = set()
    for u in census["units"]:
        if u["arm"] != ta.arm_of(trial.id, u["root"]):
            raise InputError(f"unit {u['root']} has arm {u['arm']}; the function gives {ta.arm_of(trial.id, u['root'])}")
        for m in u["members"]:
            if m["task"] in seen:
                raise InputError(f"task {m['task']} is in two census units")
            seen.add(m["task"])
            row = rows.get(m["task"])
            if row is None:
                continue
            if (_day_ms(row["first_start_ms"]), _day_ms(row["first_close_ms"])) != \
                    (_day_iso(m["first_start"]), _day_iso(m["first_done"])):
                raise InputError(f"task {m['task']}: census and obs disagree on its first start or first close")
    return rows


def _defect_state(trial, u, rows):
    present = [rows[m["task"]] for m in u["members"] if m["task"] in rows]
    if any(row["defects"] > 0 for row in present):
        return "defective"
    if any(m["first_done"] and _day_iso(m["first_done"]) <= trial.close_by and m["task"] not in rows
           for m in u["members"]):
        return "unknown"
    return "clean"


def _ratio(a, b):
    return f"{a}/{b}"


def judge(trial, census, report):
    rows = read_inputs(trial, census, report)
    gated = _gate_holds(report)
    by_arm = {"on": [], "off": []}
    for u in census["units"]:
        delivered = u["first_done"] is not None and _day_iso(u["first_done"]) <= trial.close_by
        state = _defect_state(trial, u, rows) if delivered else None
        member_rows = [rows[m["task"]] for m in u["members"] if m["task"] in rows]
        by_arm[u["arm"]].append({"unit": u, "delivered": delivered, "state": state, "rows": member_rows})
    count = {arm: {
        "enrolled": len(items),
        "delivered": sum(i["delivered"] for i in items),
        "clean": sum(i["state"] in ("clean", "unknown") for i in items),
        "strict": sum(i["state"] == "clean" for i in items),
        "unknown": sum(i["state"] == "unknown" for i in items),
        "defective": sum(i["state"] == "defective" for i in items),
    } for arm, items in by_arm.items()}
    on, off = count["on"], count["off"]
    comp = ta.compliance(census["units"])

    def test(key):
        if on["enrolled"] == 0 or off["enrolled"] == 0:
            return None, None
        p = fisher_two_sided(on[key], on["enrolled"] - on[key], off[key], off["enrolled"] - off[key])
        return p, newcombe(on[key], on["enrolled"], off[key], off["enrolled"])

    p, interval = test("clean")
    delivered_total = on["delivered"] + off["delivered"]
    unknown_share = (on["unknown"] + off["unknown"]) / delivered_total if delivered_total else 0.0
    if gated:
        choice = "insufficient: unvalidated"
    elif unknown_share > MAX_UNKNOWN:
        choice = "insufficient: missing defect data"
    elif on["enrolled"] < MIN_ARM or off["enrolled"] < MIN_ARM:
        choice = "insufficient: too few"
    elif any(s["assessable"] < MIN_ASSESSABLE or s["rate"] < MIN_COMPLIANCE for s in comp.values()):
        choice = "insufficient: compliance"
    elif p < ALPHA:
        choice = "flow-better" if on["clean"] / on["enrolled"] > off["clean"] / off["enrolled"] else "flow-worse"
    else:
        choice = "no-difference-detected"

    def counts(key, label):
        p_value, ci = test(key)
        if p_value is None:
            return f"{label}on {_ratio(on[key], on['enrolled'])}, off {_ratio(off[key], off['enrolled'])}, p n/a"
        d, lo, hi = ci
        return (f"{label}on {_ratio(on[key], on['enrolled'])}, off {_ratio(off[key], off['enrolled'])}, "
                f"p {p_value:.4f}, risk difference {d:+.3f} [{lo:+.3f}, {hi:+.3f}] (90% Newcombe)")

    def per_arm(fn):
        return ", ".join(f"{arm} {fn(arm, items)}" for arm, items in by_arm.items())

    def state_count(state):
        return per_arm(lambda arm, items: sum(i["unit"]["state"] == state for i in items))

    def conditional(name):
        return per_arm(lambda arm, items: sum(r[name] for i in items if i["delivered"] for r in i["rows"]))

    def tokens(arm, items):
        sums = [sum(r["output_tokens"] for r in i["rows"] if r.get("output_tokens") is not None)
                for i in items if i["delivered"]]
        return statistics.median(sums) if sums else "n/a"

    strata = {}
    for arm, items in by_arm.items():
        for i in items:
            s = i["unit"]["stratum"]
            key = f"{s['project']}/{s['size']}/{s['complexity']}/{s['process']}"
            strata.setdefault(key, {"on": 0, "off": 0})[arm] += 1
    moves = per_arm(lambda arm, items: sum(len(m["moves"]) for i in items for m in i["unit"]["members"]))
    return [
        choice,
        counts("clean", ""),
        counts("strict", "sensitivity (unknown defect state counted defective): "),
        "compliance: " + "; ".join(
            f"{arm} {s['compliant']}/{s['assessable']} assessable"
            + (f" ({s['rate']:.2f})" if s["rate"] is not None else "")
            + f", unassessable {s['enrolled'] - s['assessable']}" for arm, s in comp.items()),
        f"delivered: {per_arm(lambda arm, items: _ratio(count[arm]['delivered'], count[arm]['enrolled']))}; "
        f"delivered with a defect: {per_arm(lambda arm, items: count[arm]['defective'])}; "
        f"dropped: {state_count('dropped')}; shelved: {state_count('shelved')}; "
        f"open on {trial.close_by}: {state_count('open')}; "
        f"reopened after delivery: {per_arm(lambda arm, items: sum(i['unit']['reopened'] for i in items))}",
        "conditional on delivery (not causal): "
        f"defect rate {per_arm(lambda arm, items: _ratio(count[arm]['defective'], count[arm]['delivered']))}; "
        f"change requests {conditional('changes')}; extensions {conditional('extensions')}; "
        f"reopens {conditional('reopens')}",
        f"median output_tokens per delivered unit: {per_arm(tokens)}",
        "strata (project/size/complexity/process): "
        + "; ".join(f"{k} on {v['on']} off {v['off']}" for k, v in sorted(strata.items())),
        f"decided late: {', '.join(f'{a} {n}' for a, n in census['decided_late'].items())}; "
        f"moves: {moves}; membership conflicts: {len(census['conflicts'])}",
        *LIMITS,
    ]


def main(argv=None, stdin=None, stdout=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("trial")
    parser.add_argument("--census", required=True)
    parser.add_argument("--as-of", type=dt.date.fromisoformat)
    parser.add_argument("--validate", action="store_true",
                        help="check both inputs and print only what was read; compute no outcome")
    args = parser.parse_args(argv)
    stdin, out = stdin or sys.stdin, stdout or sys.stdout
    try:
        trial = ta.parse_trial(Path(args.trial).read_text(), args.trial)
        if args.validate:
            census = json.loads(Path(args.census).read_text())
            rows = read_inputs(trial, census, json.load(stdin))
            members = {m["task"] for u in census["units"] for m in u["members"]}
            print(f"inputs valid: {len(census['units'])} census units, "
                  f"{len(members & set(rows))} obs rows for their members", file=out)
            return 0
        as_of = args.as_of or dt.datetime.now(dt.timezone.utc).date()
        if as_of < trial.read_on:
            print("insufficient: before read date", file=out)
            print(f"read on {trial.read_on}; nothing computed", file=out)
            return 0
        census = json.loads(Path(args.census).read_text())
        lines = judge(trial, census, json.load(stdin))
    except (InputError, ta.TrialError, json.JSONDecodeError) as error:
        print(f"trial-verdict: {error}", file=sys.stderr)
        return 2
    print("\n".join(lines), file=out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `chmod +x agents/bin/trial-verdict && python3 -m pytest agents/bin/test_trial_verdict.py -q`
Expected: all pass. If `test_newcombe_matches_the_published_example` is off in the
fourth decimal, check the Wilson formula against Newcombe (1998), method 10, before
touching the test. The published interval is (0.0524, 0.3339).

- [ ] **Step 5: Run the suite and commit**

```bash
just test
git add agents/bin/trial-verdict agents/bin/test_trial_verdict.py
git commit -m "feat(trial-verdict): intention-to-treat verdict over the census and obs units"
```

### Task 5: the trial file, the case file and the global rule

**Files:**
- Create: `agents/evals/trials/flow-trial-1.md`
- Create: `agents/evals/cases/flow-trial-1-delivery.md`
- Modify: `AGENTS.md` (a new `## Trials` section between "Task notes for outcome measures" and "Feedback")
- Modify: `agents/bin/test_trial_arm.py` (one test that loads the real trial file)

**Interfaces:**
- Consumes: `trial-arm` (Tasks 1 to 3), `trial-verdict` (Task 4).
- Produces: the live trial, read by `~/.agents/bin/trial-arm` from the main checkout
  once merged. It must be merged before 2026-10-05, when enrollment opens.

- [ ] **Step 1: Write the failing test**

Append to `agents/bin/test_trial_arm.py`:

```python
def test_the_shipped_trial_file_loads_with_the_spec_dates():
    [trial] = [t for t in ta.load_trials(ta.TRIALS) if t.id == "flow-trial-1"]
    assert trial.projects == ("tack", "obs")
    assert trial.enroll == (dt.date(2026, 10, 5), dt.date(2026, 11, 29))
    assert (trial.close_by, trial.follow_up_to, trial.read_on) == (
        dt.date(2027, 1, 10), dt.date(2027, 2, 9), dt.date(2027, 2, 16))
```

Run: `python3 -m pytest agents/bin/test_trial_arm.py -q -k shipped`
Expected: FAIL (`ValueError: not enough values to unpack`), since no trial file exists yet.

- [ ] **Step 2: Write the trial file**

`agents/evals/trials/flow-trial-1.md`:

```markdown
---
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

Flow on or off, assigned at random to work items in tack and obs. The design is
docs/specs/2026-10-02-flow-trial-design.md; this file is frozen from 2026-10-05.

- Unit: a task's work item, found by climbing its parents while the parent has
  `process` set (§4). One arm per unit, `sha256("flow-trial-1:<root>")[0] & 1`.
- Sessions run `~/.agents/bin/trial-arm <id>` after `tasks start` and follow it (the
  global rule in AGENTS.md, "Trials").
- Watch compliance with `trial-arm status flow-trial-1`. Halt when compliance falls below
  0.8 in either arm once each arm has 15 assessable units (§7).
- Material changes to flow that halt the trial: a gate added, removed or renamed, or a
  change to who judges a gate. Wording edits do not.

## Stop events

<none: a halt writes a dated line here and moves enroll's end, close_by, follow_up_to
and read_on by the same offset>
```

- [ ] **Step 3: Write the case file**

`agents/evals/cases/flow-trial-1-delivery.md`:

```markdown
---
id: flow-trial-1-delivery
title: Effect of flow on clean delivery of work items, by randomized arm
subject:
  kind: flow
  name: flow skill (agents/skills/flow/SKILL.md), trial flow-trial-1
  version: [trial flow-trial-1, enroll 2026-10-05..2026-11-29]
inputs:
  - kind: query
    ref: agents/bin/trial-arm census flow-trial-1
  - kind: query
    ref: obs --json outcomes report --since 2026-10-05 --until 2027-01-10 --cohort --units
expected:
  type: choice
  claim: the intention-to-treat comparison of delivered clean, flow on against flow off, over every enrolled unit, read by the rule in docs/specs/2026-10-02-flow-trial-design.md §6
  choices: [flow-better, no-difference-detected, flow-worse, insufficient]
  value: no-difference-detected
observed:
  value: <choice: the first line of the run up to any colon>
  reason: <the text after "insufficient: ", or null>
  at: trial flow-trial-1, enroll 2026-10-05..2026-11-29
judge:
  kind: check
  command: agents/bin/trial-arm census flow-trial-1 > <tmp> && obs --json outcomes report --since 2026-10-05 --until 2027-01-10 --cohort --units | agents/bin/trial-verdict agents/evals/trials/flow-trial-1.md --census <tmp>
  cwd: tack checkout
  pass: prints no-difference-detected
source: [tack-7d9375, obs-00809f]
evidence: inferred
---

The randomized counterpart of flow-defects-after-close. Work items in tack and obs
whose earliest start falls between 2026-10-05 and 2026-11-29 were assigned flow on or
off by a hash of their root id. The case compares, over every enrolled unit, the share
delivered clean: the root first closed `done` by 2027-01-10, and no member drew a
defect in the 30 days after its own first close. `expected` is the null hypothesis,
stated before any data. Either direction is a finding.

The rule is read once, on or after 2027-02-16. Earlier runs print
`insufficient: before read date` and compute nothing. Two limits travel with every
verdict: a unit that flow's gates stop on purpose counts against flow, and defects are
watched only after first closes.

## Verdicts

<one entry per run, newest last: `<run date> <choice>[: <reason>] — <counts line>`, then the tool's remaining lines indented>
```

- [ ] **Step 4: Add the global rule**

In `AGENTS.md`, insert this section immediately before `## Feedback`:

```markdown
## Trials

After `tasks start`, run `~/.agents/bin/trial-arm <id>` and follow what it prints.
`flow on` runs the task under the flow skill; `flow off` runs it without flow,
whatever else would choose it; `not enrolled` changes nothing. Every task in a unit
has the unit's arm, and the task's `process` is unchanged in both arms. Only the user
overrides an arm: record it with `tasks note <id> "arm: <trial> — override: <why>"`.
```

- [ ] **Step 5: Run the tests and the live checks**

Run: `just test`
Expected: all pass, including `test_the_shipped_trial_file_loads_with_the_spec_dates`.

Run, from the worktree:
`agents/bin/trial-arm tack-7d9375`
Expected before 2026-10-05: `not enrolled: no trial for tack`, with no note written
(`tasks show tack-7d9375 | jq -r '.task.notes[-1].text'` is unchanged). From
2026-10-05 on: `not enrolled: unit tack-7d9375 first started 2026-10-02, outside
enroll`, with one `trial:` note and one `arm:` note written.

Run: `agents/bin/trial-arm census flow-trial-1 | jq '.units | length'`
Expected: `0` before enrollment opens. Exit 0, and the run reads tack and obs without
error.

Run: `agents/bin/trial-arm census flow-trial-1 > "$TMPDIR/census.json" && echo '{}' | agents/bin/trial-verdict agents/evals/trials/flow-trial-1.md --census "$TMPDIR/census.json"`
(with `TMPDIR` set to the session scratchpad)
Expected: `insufficient: before read date` and `read on 2027-02-16; nothing computed`.

- [ ] **Step 6: Commit**

```bash
git add agents/evals/trials/flow-trial-1.md agents/evals/cases/flow-trial-1-delivery.md AGENTS.md agents/bin/test_trial_arm.py
git commit -m "feat(evals): open flow-trial-1 with its case and the global trial rule"
```

### Task 6: the case's first live run against obs

Blocked on obs-0491f1 (`--until`, `--cohort`, `--units`). File it with
`tasks dep <this step> --on obs-0491f1`.

**Files:**
- Modify: `agents/evals/cases/flow-trial-1-delivery.md` (`observed` and `## Verdicts`)

**Interfaces:**
- Consumes: the case's judge command, verbatim.

- [ ] **Step 1: Run the judge command from the main checkout**

```bash
agents/bin/trial-arm census flow-trial-1 > "$TMPDIR/census.json" \
  && obs --json outcomes report --since 2026-10-05 --until 2027-01-10 --cohort --units \
  | agents/bin/trial-verdict agents/evals/trials/flow-trial-1.md --census "$TMPDIR/census.json"
```

Expected: exit 0, first line `insufficient: before read date`. Any other exit is a
pipeline defect: fix it before recording.

- [ ] **Step 2: Validate the live inputs without computing any outcome**

```bash
obs --json outcomes report --since 2026-10-05 --until 2027-01-10 --cohort --units \
  | agents/bin/trial-verdict agents/evals/trials/flow-trial-1.md --census "$TMPDIR/census.json" --validate
```

Expected: exit 0 and one line, `inputs valid: <n> census units, <m> obs rows for their
members`. This checks that the live census and the obs report parse and agree, with
no outcome, arm comparison or statistic printed. Never run the verdict with an
`--as-of` at or after `read_on` before that date: the full rule is exercised by Task 4's
fixtures, and the trial's one read is the run on or after 2027-02-16.

- [ ] **Step 3: Record and commit**

Set `observed.value: insufficient` and `observed.reason: before read date`, and append
under `## Verdicts`:
`<run date> insufficient: before read date — pipeline check; --validate printed <its line>`.

```bash
git add agents/evals/cases/flow-trial-1-delivery.md
git commit -m "docs(evals): first live run of flow-trial-1-delivery"
```
