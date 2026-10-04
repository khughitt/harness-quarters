# Flow State Machine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the task workflow's states and gates explicit and executable: a `flow-state` script that derives a task's state from its record and the covered tree, a short `flow` skill that walks the machine, and one real task closed under it.

**Architecture:** `flow-state` is one stdlib-only Python script under `agents/bin` with pure derivation functions (record in, state out) and a git fingerprint of the covered tree, wrapped by a small CLI that calls `tasks show`. The skill is a single `SKILL.md` carrying the spec's tables. No tracker changes: transitions are `gate:` notes on the task.

**Tech Stack:** Python 3.11 stdlib (`subprocess`, `json`, `re`, `tempfile`, `dataclasses`), git, `tasks` CLI, pytest for the tests (`uv run --with pytest pytest …`; pytest 9 is also installed system-wide).

**Spec:** `docs/specs/2026-09-15-flow-state-machine-design.md` — the plan argues from it; read §3 (the machine) before Task 1, §3.6 (covered tree) before Task 3.

## Global Constraints

- Harness-neutral: the skill names no Claude-only tool; the script uses no third-party package.
- The bookkeeping exclusions are fixed: `tasks`, `docs/specs`, `docs/plans` (spec §3.6).
- Gate note grammar: `gate: <state>` followed by free text; `verified` must carry `tree:<40 hex>`; a reopen carries the word `reopened` (spec §3.5, §3.6).
- Every derived inconsistency is reported, never resolved by guessing (spec §3.5).
- Paths in this document are relative to the main checkout; execution happens in `.worktrees/flow/`.
- The spec and this plan are excluded from git (`.git/info/exclude`); never stage them.
- Task records: `tasks start <step>` before a task, `tasks done <step>` in the commit that lands it; each step child already carries `gate: scoped — step of ai-f5da3a plan` and gets `gate: implementing`, `gate: verified tree:<f>`, and `retro:` notes as it runs (spec §3.3). This plan is the machine's first parent/child use; the `flow-state` script is allowed to be the thing that checks its own record from Task 4 on.

## File Structure

- Create `agents/bin/flow-state` — executable, `#!/usr/bin/env python3`. Sections: gate parsing, leaf derivation, parent derivation, worktree comparison, fingerprint, CLI. One file because every part is under 400 lines total and the derivation functions are what the tests import.
- Create `agents/bin/test_flow_state.py` — pytest; imports the script via `importlib` (the file has no `.py` suffix). Fixture records are dicts shaped like `tasks show` JSON (`show["task"]` with `notes: [{at, by, text}]`, `show["children"]: [{id, title, status}]`).
- Create `agents/skills/flow/SKILL.md` — the skill.
- Modify `agents/skills/README.md` — one bullet for `flow`.
- Symlink `~/.claude/skills/flow → ~/d/ai/agents/skills/flow` (outside the repo; Task 5).

---

### Task 1: Gate parsing and leaf derivation

**Files:**
- Create: `agents/bin/flow-state`
- Create: `agents/bin/test_flow_state.py`

**Interfaces:**
- Produces:
  ```python
  STATES = ("captured", "scoped", "designed", "planned", "implementing", "verified", "closed", "outside")
  GATE_STATES = ("scoped", "designed", "planned", "implementing", "verified")

  @dataclass(frozen=True)
  class Gate:
      state: str      # one of GATE_STATES
      detail: str     # text after the state word, stripped; "" if none
      at: str         # note timestamp
      index: int = -1 # position of the note in record["notes"]

  @dataclass(frozen=True)
  class Derivation:
      state: str                      # one of STATES
      inconsistent: str | None = None # reason, or None
      note: str | None = None         # e.g. "verified at tree:<f>, covered content changed"
      verified_tree: str | None = None

  def gates(record: dict) -> list[Gate]          # record = show["task"]; in note order
  def has_retro(record: dict) -> bool            # any note text starting "retro:"
  def retro_after(record: dict, gate: Gate) -> bool  # a retro: note positioned after gate.index
  def verified_tree_of(gate: Gate) -> str | None # "tree:<40 hex>" in detail
  def derive_leaf(record: dict) -> Derivation
  ```

- [ ] **Step 1: Write the failing tests**

`agents/bin/test_flow_state.py`:

```python
import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).with_name("flow-state")
spec = importlib.util.spec_from_loader("flow_state", loader=None)
flow_state = importlib.util.module_from_spec(spec)
sys.modules["flow_state"] = flow_state  # dataclass resolves postponed annotations through sys.modules
exec(compile(SCRIPT.read_text(), str(SCRIPT), "exec"), flow_state.__dict__)


def record(status="todo", process=None, spec_link=None, plan=None, notes=(), **extra):
    task = {
        "id": "ai-000001", "title": "T", "status": status, "priority": 2,
        "process": process, "spec": spec_link, "plan": plan, "step": None,
        "parent": None, "notes": [
            {"at": f"2026-09-15T00:00:{i:02d}Z", "by": "main", "text": text}
            for i, text in enumerate(notes)
        ],
    }
    task.update(extra)
    return task


def test_gates_parses_state_and_detail_in_order():
    r = record(notes=["plain note", "gate: scoped — adopted", "gate: implementing .worktrees/x"])
    g = flow_state.gates(r)
    assert [x.state for x in g] == ["scoped", "implementing"]
    assert g[0].detail == "— adopted"
    assert g[1].at == "2026-09-15T00:00:02Z"
    assert [x.index for x in g] == [1, 2]


def test_gates_ignores_unknown_state_words():
    r = record(notes=["gate: reviewed by someone"])
    assert flow_state.gates(r) == []


def test_verified_tree_of_extracts_hash():
    g = flow_state.Gate("verified", "tree:" + "a" * 40 + " — pytest ok", "t")
    assert flow_state.verified_tree_of(g) == "a" * 40
    assert flow_state.verified_tree_of(flow_state.Gate("verified", "no hash", "t")) is None


def test_has_retro():
    assert flow_state.has_retro(record(notes=["retro: short"]))
    assert not flow_state.has_retro(record(notes=["gate: scoped"]))


@pytest.mark.parametrize("status", ["todo", "doing", "done", "blocked"])
def test_leaf_outside_without_gates(status):
    d = flow_state.derive_leaf(record(status=status))
    assert d == flow_state.Derivation("outside")


def test_leaf_idea_without_gates_is_captured():
    assert flow_state.derive_leaf(record(status="idea")).state == "captured"


def test_leaf_idea_with_gates_is_inconsistent():
    d = flow_state.derive_leaf(record(status="idea", process="direct", notes=["gate: scoped"]))
    assert d.state == "scoped" and "idea" in d.inconsistent


@pytest.mark.parametrize("status", ["todo", "doing", "blocked"])
def test_leaf_scoped_allows_claim(status):
    d = flow_state.derive_leaf(record(status=status, process="direct", notes=["gate: scoped"]))
    assert d == flow_state.Derivation("scoped")


def test_leaf_scoped_requires_process():
    d = flow_state.derive_leaf(record(process=None, notes=["gate: scoped"]))
    assert d.state == "scoped" and "process" in d.inconsistent


def test_leaf_designed_requires_spec_link():
    ok = record(status="doing", process="planned", spec_link="docs/specs/x.md",
                notes=["gate: scoped", "gate: designed docs/specs/x.md"])
    assert flow_state.derive_leaf(ok) == flow_state.Derivation("designed")
    missing = record(process="planned", notes=["gate: scoped", "gate: designed"])
    assert "spec" in flow_state.derive_leaf(missing).inconsistent


def test_leaf_planned_gate_is_inconsistent():
    d = flow_state.derive_leaf(record(process="planned", plan="docs/plans/x.md",
                                      notes=["gate: scoped", "gate: designed x", "gate: planned x"]))
    assert d.state == "planned" and "children" in d.inconsistent


def test_leaf_implementing_requires_doing():
    seq = ["gate: scoped", "gate: implementing .worktrees/x"]
    assert flow_state.derive_leaf(record(status="doing", process="direct", notes=seq)) == flow_state.Derivation("implementing")
    d = flow_state.derive_leaf(record(status="todo", process="direct", notes=seq))
    assert d.state == "implementing" and "todo" in d.inconsistent


def test_leaf_verified_carries_tree_and_requires_doing():
    f = "b" * 40
    seq = ["gate: scoped", "gate: implementing x", f"gate: verified tree:{f} — pytest ok"]
    d = flow_state.derive_leaf(record(status="doing", process="direct", notes=seq))
    assert d == flow_state.Derivation("verified", verified_tree=f)
    no_tree = seq[:2] + ["gate: verified — pytest ok"]
    assert "tree" in flow_state.derive_leaf(record(status="doing", process="direct", notes=no_tree)).inconsistent


def test_leaf_closed_requires_verified_gate_and_retro():
    f = "c" * 40
    seq = ["gate: scoped", "gate: implementing x", f"gate: verified tree:{f}", "retro: fine"]
    d = flow_state.derive_leaf(record(status="done", process="direct", notes=seq))
    assert d == flow_state.Derivation("closed", verified_tree=f)
    no_retro = flow_state.derive_leaf(record(status="done", process="direct", notes=seq[:3]))
    assert no_retro.state == "closed" and "retro" in no_retro.inconsistent
    early = flow_state.derive_leaf(record(status="done", process="direct", notes=seq[:2]))
    assert early.state == "closed" and "implementing" in early.inconsistent
    no_tree = flow_state.derive_leaf(record(status="done", process="direct",
                                            notes=seq[:2] + ["gate: verified — ok", "retro: x"]))
    assert no_tree.state == "closed" and "tree" in no_tree.inconsistent
    retro_before = seq[:2] + ["retro: early", f"gate: verified tree:{f}"]
    stale = flow_state.derive_leaf(record(status="done", process="direct", notes=retro_before))
    assert stale.state == "closed" and "retro" in stale.inconsistent


def test_leaf_reclosed_after_reopen_needs_a_fresh_retro():
    f, g = "c" * 40, "9" * 40
    seq = ["gate: scoped", "gate: implementing x", f"gate: verified tree:{f}", "retro: first",
           f"gate: implementing — reopened: hook rewrote content, verified tree:{f}",
           f"gate: verified tree:{g}"]
    stale = flow_state.derive_leaf(record(status="done", process="direct", notes=seq))
    assert stale.state == "closed" and "retro" in stale.inconsistent
    fresh = flow_state.derive_leaf(record(status="done", process="direct", notes=seq + ["retro: second"]))
    assert fresh == flow_state.Derivation("closed", verified_tree=g)


def test_leaf_identical_verified_notes_in_one_second_still_need_a_fresh_retro():
    f = "c" * 40
    texts = ["gate: scoped", "gate: implementing x", f"gate: verified tree:{f}", "retro: first",
             f"gate: implementing — reopened: hook, verified tree:{f}", f"gate: verified tree:{f}"]
    r = record(status="done", process="direct", notes=texts)
    for n in r["notes"]:
        n["at"] = "2026-09-15T00:00:00Z"
    d = flow_state.derive_leaf(r)
    assert d.state == "closed" and "retro" in d.inconsistent


def test_leaf_invalidation_back_edge_returns_to_scoped():
    seq = ["gate: scoped", "gate: designed x", "gate: implementing x", "gate: scoped — invalidated: decision"]
    d = flow_state.derive_leaf(record(status="doing", process="planned", spec_link="x", notes=seq))
    assert d == flow_state.Derivation("scoped")


def test_leaf_reopened_after_close_is_implementing():
    f = "d" * 40
    seq = ["gate: scoped", "gate: implementing x", f"gate: verified tree:{f}", "retro: ok",
           f"gate: implementing — reopened: commit failed, verified tree:{f}"]
    d = flow_state.derive_leaf(record(status="doing", process="direct", notes=seq))
    assert d == flow_state.Derivation("implementing")


def test_leaf_park_resume_keeps_state():
    seq = ["gate: scoped", "gate: implementing x"]
    assert flow_state.derive_leaf(record(status="doing", process="direct", notes=seq)).state == "implementing"
    seq2 = ["gate: scoped"]
    assert flow_state.derive_leaf(record(status="doing", process="direct", notes=seq2)).state == "scoped"


@pytest.mark.parametrize("status", ["dropped", "shelved"])
def test_leaf_dropped_or_shelved_is_outside(status):
    d = flow_state.derive_leaf(record(status=status, process="direct", notes=["gate: scoped"]))
    assert d.state == "outside" and d.note == status
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd .worktrees/flow && uv run --with pytest pytest agents/bin/test_flow_state.py -q`
Expected: error — `agents/bin/flow-state` does not exist (FileNotFoundError at import).

- [ ] **Step 3: Write the script's parsing and leaf derivation**

`agents/bin/flow-state`:

```python
#!/usr/bin/env python3
"""Derive a task's flow state from its record and the covered tree.

flow-state <id> [--json] [--no-git]    state of one task
flow-state fingerprint [--index|--head] covered-tree hash of the current repo

The machine is docs/specs/2026-09-15-flow-state-machine-design.md; the gate
grammar is "gate: <state> <detail>" in task notes, "retro:" for the retro.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

STATES = ("captured", "scoped", "designed", "planned", "implementing", "verified", "closed", "outside")
GATE_STATES = ("scoped", "designed", "planned", "implementing", "verified")
EXCLUDED = ("tasks", "docs/specs", "docs/plans")

GATE_RE = re.compile(r"^gate:\s*(scoped|designed|planned|implementing|verified)\b\s*(.*)$", re.S)
TREE_RE = re.compile(r"tree:([0-9a-f]{40})")
TODO_LIKE = ("todo", "blocked")


@dataclass(frozen=True)
class Gate:
    state: str
    detail: str
    at: str
    index: int = -1


@dataclass(frozen=True)
class Derivation:
    state: str
    inconsistent: str | None = None
    note: str | None = None
    verified_tree: str | None = None


# --- gate parsing -----------------------------------------------------------

def gates(record: dict) -> list[Gate]:
    out = []
    for i, n in enumerate(record.get("notes") or []):
        m = GATE_RE.match(n["text"].strip())
        if m:
            out.append(Gate(m.group(1), m.group(2).strip(), n["at"], i))
    return out


def has_retro(record: dict) -> bool:
    return any(n["text"].strip().startswith("retro:") for n in record.get("notes") or [])


def retro_after(record: dict, gate: Gate) -> bool:
    """A retro: note positioned after the gate's note (by index, never by clock or text)."""
    notes = record.get("notes") or []
    return any(n["text"].strip().startswith("retro:") for n in notes[gate.index + 1:])


def verified_tree_of(gate: Gate) -> str | None:
    m = TREE_RE.search(gate.detail)
    return m.group(1) if m else None


# --- leaf derivation --------------------------------------------------------

def _closed(record: dict, last: Gate) -> Derivation:
    if last.state != "verified":
        return Derivation("closed", f"done with last gate {last.state}")
    tree = verified_tree_of(last)
    if tree is None:
        return Derivation("closed", "verified gate without tree:<hash>")
    if not retro_after(record, last):
        return Derivation("closed", "done without a retro: note after the verified gate", verified_tree=tree)
    return Derivation("closed", verified_tree=tree)


def derive_leaf(record: dict) -> Derivation:
    status = record["status"]
    gs = gates(record)
    if status in ("dropped", "shelved"):
        return Derivation("outside", note=status)
    if not gs:
        return Derivation("captured" if status == "idea" else "outside")
    last = gs[-1]
    if status == "idea":
        return Derivation(last.state, "status idea with gate notes")
    if status == "done":
        return _closed(record, last)
    claimed = status in TODO_LIKE or status == "doing"
    if last.state == "scoped":
        if not record.get("process"):
            return Derivation("scoped", "process unset")
        return Derivation("scoped") if claimed else Derivation("scoped", f"status {status}")
    if last.state == "designed":
        if not record.get("spec"):
            return Derivation("designed", "no spec link")
        return Derivation("designed") if claimed else Derivation("designed", f"status {status}")
    if last.state == "planned":
        return Derivation("planned", "planned gate without step children")
    if last.state == "implementing":
        return Derivation("implementing") if status == "doing" else Derivation("implementing", f"status {status}")
    tree = verified_tree_of(last)
    if tree is None:
        return Derivation("verified", "verified gate without tree:<hash>")
    return Derivation("verified", verified_tree=tree) if status == "doing" else Derivation("verified", f"status {status}", verified_tree=tree)


if __name__ == "__main__":
    sys.exit("cli not wired yet")
```

Then: `chmod +x agents/bin/flow-state`.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd .worktrees/flow && uv run --with pytest pytest agents/bin/test_flow_state.py -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
cd .worktrees/flow
git add agents/bin/flow-state agents/bin/test_flow_state.py
git commit -m "feat(flow): parse gate notes and derive a leaf task's flow state"
```

---

### Task 2: Parent derivation and dispatch

**Files:**
- Modify: `agents/bin/flow-state` (after `derive_leaf`)
- Modify: `agents/bin/test_flow_state.py`

**Interfaces:**
- Consumes: `Gate`, `Derivation`, `gates`, `has_retro`, `verified_tree_of`, `derive_leaf`, `TODO_LIKE` from Task 1.
- Produces:
  ```python
  def derive_parent(record: dict, children: list[dict]) -> Derivation
  # children: each child's show["task"] (full record, notes included)
  def derive(show: dict, child_records: list[dict]) -> Derivation
  # show: full `tasks show` JSON; dispatches on show["children"]
  ```

- [ ] **Step 1: Write the failing tests**

Append to `agents/bin/test_flow_state.py`:

```python
def parent(status="todo", notes=(), **extra):
    return record(status=status, process="planned", spec_link="docs/specs/p.md",
                  plan="docs/plans/p.md", notes=notes, **extra)


PARENT_GATES = ["gate: scoped", "gate: designed p", "gate: planned p"]
CHILD_SCOPED = ["gate: scoped — step of ai-000001 plan"]
F = "e" * 40


def child(cid, status="todo", notes=CHILD_SCOPED):
    c = record(status=status, process="direct", notes=notes)
    c["id"] = cid
    c["parent"] = "ai-000001"
    return c


def show_of(task, children):
    return {"task": task, "children": [{"id": c["id"], "title": "c", "status": c["status"]} for c in children]}


def test_parent_planned_until_a_child_leaves_scoped():
    p = parent(notes=PARENT_GATES)
    kids = [child("ai-c1"), child("ai-c2")]
    assert flow_state.derive_parent(p, kids) == flow_state.Derivation("planned")


def test_parent_implementing_once_a_child_starts():
    p = parent(status="doing", notes=PARENT_GATES)
    kids = [child("ai-c1", "doing", CHILD_SCOPED + ["gate: implementing w"]), child("ai-c2")]
    assert flow_state.derive_parent(p, kids) == flow_state.Derivation("implementing")


def test_parent_stays_implementing_after_all_children_close():
    closed = CHILD_SCOPED + ["gate: implementing w", f"gate: verified tree:{F}", "retro: ok"]
    p = parent(notes=PARENT_GATES)
    kids = [child("ai-c1", "done", closed), child("ai-c2", "done", closed)]
    assert flow_state.derive_parent(p, kids) == flow_state.Derivation("implementing")


def test_parent_stays_implementing_when_a_child_invalidates_its_own_work():
    p = parent(notes=PARENT_GATES)
    kids = [child("ai-c1", "doing", CHILD_SCOPED + ["gate: implementing w", "gate: scoped — invalidated: own approach"])]
    assert flow_state.derive_parent(p, kids) == flow_state.Derivation("implementing")


def test_parent_child_without_gates_is_inconsistent():
    p = parent(notes=PARENT_GATES)
    d = flow_state.derive_parent(p, [child("ai-c1", notes=[])])
    assert d.state == "planned" and "ai-c1" in d.inconsistent


@pytest.mark.parametrize("status", ["todo", "doing"])
def test_parent_status_is_only_a_claim(status):
    p = parent(status=status, notes=PARENT_GATES)
    kids = [child("ai-c1", "doing", CHILD_SCOPED + ["gate: implementing w"])]
    assert flow_state.derive_parent(p, kids).inconsistent is None


def test_parent_verified_requires_every_child_closed():
    closed = CHILD_SCOPED + ["gate: implementing w", f"gate: verified tree:{F}", "retro: ok"]
    p = parent(status="doing", notes=PARENT_GATES + [f"gate: verified tree:{F} — full suite"])
    ok = flow_state.derive_parent(p, [child("ai-c1", "done", closed)])
    assert ok == flow_state.Derivation("verified", verified_tree=F)
    early = flow_state.derive_parent(p, [child("ai-c1", "doing", CHILD_SCOPED + ["gate: implementing w"])])
    assert early.state == "verified" and "ai-c1 is implementing" in early.inconsistent
    badly_closed = flow_state.derive_parent(p, [child("ai-c1", "done", closed[:-1])])
    assert badly_closed.state == "verified" and "ai-c1 closed (inconsistent" in badly_closed.inconsistent


def test_parent_planned_requires_plan_link():
    p = parent(notes=PARENT_GATES)
    p["plan"] = None
    d = flow_state.derive_parent(p, [child("ai-c1")])
    assert d.state == "planned" and "plan" in d.inconsistent


def test_parent_closed():
    closed = CHILD_SCOPED + ["gate: implementing w", f"gate: verified tree:{F}", "retro: ok"]
    p = parent(status="done", notes=PARENT_GATES + [f"gate: verified tree:{F}", "retro: parent"])
    assert flow_state.derive_parent(p, [child("ai-c1", "done", closed)]) == flow_state.Derivation("closed", verified_tree=F)


def test_parent_reopened_carries_implementing_itself():
    closed = CHILD_SCOPED + ["gate: implementing w", f"gate: verified tree:{F}", "retro: ok"]
    p = parent(status="doing", notes=PARENT_GATES + [f"gate: verified tree:{F}", "retro: parent",
                                                    f"gate: implementing — reopened: commit failed, verified tree:{F}"])
    assert flow_state.derive_parent(p, [child("ai-c1", "done", closed)]) == flow_state.Derivation("implementing")


def test_parent_implementing_gate_without_reopen_is_inconsistent():
    p = parent(status="doing", notes=PARENT_GATES + ["gate: implementing w"])
    d = flow_state.derive_parent(p, [child("ai-c1")])
    assert d.state == "implementing" and "reopen" in d.inconsistent


def test_parent_invalidated_from_child_returns_to_scoped():
    p = parent(status="doing", notes=PARENT_GATES + ["gate: scoped — invalidated: child ai-c1 changed the plan"])
    assert flow_state.derive_parent(p, [child("ai-c1")]) == flow_state.Derivation("scoped")


def test_derive_dispatches_on_children():
    leaf = record(status="doing", process="direct", notes=["gate: scoped", "gate: implementing w"])
    assert flow_state.derive(show_of(leaf, []), []) == flow_state.Derivation("implementing")
    p = parent(notes=PARENT_GATES)
    kids = [child("ai-c1")]
    assert flow_state.derive(show_of(p, kids), kids) == flow_state.Derivation("planned")
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd .worktrees/flow && uv run --with pytest pytest agents/bin/test_flow_state.py -q -k parent`
Expected: FAIL — `AttributeError: module has no attribute 'derive_parent'`.

- [ ] **Step 3: Write parent derivation and dispatch**

Insert after `derive_leaf` in `agents/bin/flow-state`:

```python
# --- parent derivation ------------------------------------------------------

def _child_left_scoped(child: dict) -> bool:
    return any(g.state != "scoped" for g in gates(child))


def derive_parent(record: dict, children: list[dict]) -> Derivation:
    status = record["status"]
    gs = gates(record)
    if status in ("dropped", "shelved"):
        return Derivation("outside", note=status)
    if not gs:
        return Derivation("captured" if status == "idea" else "outside")
    last = gs[-1]
    if last.state in ("scoped", "designed"):
        return derive_leaf(record)
    claimed = status in TODO_LIKE or status == "doing"
    ungated = [c["id"] for c in children if not gates(c)]
    if last.state == "planned":
        state = "implementing" if any(_child_left_scoped(c) for c in children) else "planned"
        if not record.get("plan"):
            return Derivation(state, "no plan link")
        if ungated:
            return Derivation(state, f"child {', '.join(ungated)} has no gate notes")
        if status == "done":
            return Derivation("closed", "done with last gate planned")
        return Derivation(state) if claimed else Derivation(state, f"status {status}")
    if last.state == "implementing":
        if "reopened" not in last.detail:
            return Derivation("implementing", "parent implementing gate is not a reopen")
        return Derivation("implementing") if claimed else Derivation("implementing", f"status {status}")
    # verified
    tree = verified_tree_of(last)
    if tree is None:
        return Derivation("verified", "verified gate without tree:<hash>")
    problems = []
    for c in children:
        cd = derive_leaf(c)
        if cd.state != "closed":
            problems.append(f"child {c['id']} is {cd.state}")
        elif cd.inconsistent:
            problems.append(f"child {c['id']} closed (inconsistent: {cd.inconsistent})")
    if problems:
        state = "closed" if status == "done" else "verified"
        return Derivation(state, "; ".join(problems), verified_tree=tree)
    if status == "done":
        return _closed(record, last)
    return Derivation("verified", verified_tree=tree) if claimed else Derivation("verified", f"status {status}", verified_tree=tree)


def derive(show: dict, child_records: list[dict]) -> Derivation:
    if show.get("children"):
        return derive_parent(show["task"], child_records)
    return derive_leaf(show["task"])
```

Note on child closure: a child counts only when its own derivation is `closed` *with no inconsistency*; a child that closed without a retro or without a tree hash blocks the parent, and the parent's result names it. A child that is itself a parent is read through `derive_leaf` here (its grandchildren are not fetched), which is enough for the first pass: a nested parent's `closed` needs `status: done` plus a verified gate and a retro after it, and the tracker already refuses `done` while its own children are open.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd .worktrees/flow && uv run --with pytest pytest agents/bin/test_flow_state.py -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
cd .worktrees/flow
git add agents/bin/flow-state agents/bin/test_flow_state.py
git commit -m "feat(flow): derive a planned parent's state from its children"
```

---

### Task 3: Covered-tree fingerprint

**Files:**
- Modify: `agents/bin/flow-state` (after `derive`)
- Modify: `agents/bin/test_flow_state.py`

**Interfaces:**
- Consumes: `EXCLUDED` from Task 1.
- Produces:
  ```python
  class DirtySubmodule(Exception): ...   # .paths: list[str]
  def git(repo: Path, *args: str, env: dict | None = None) -> str   # stdout, stripped; raises CalledProcessError
  def dirty_submodules(repo: Path) -> list[str]
  def fingerprint(repo: Path, mode: str = "worktree") -> str        # mode in {"worktree", "index", "head"}
  def apply_worktree(d: Derivation, covered: str | None) -> Derivation
  ```

- [ ] **Step 1: Write the failing tests**

Append to `agents/bin/test_flow_state.py`:

```python
import subprocess


def sh(cwd, *args, **kw):
    return subprocess.run(args, cwd=cwd, check=True, text=True, capture_output=True, **kw).stdout.strip()


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "r"
    r.mkdir()
    sh(r, "git", "init", "-q")
    sh(r, "git", "config", "user.email", "t@example.com")
    sh(r, "git", "config", "user.name", "t")
    (r / "src.txt").write_text("one\n")
    (r / "tasks").mkdir()
    (r / "tasks" / "t.md").write_text("task\n")
    (r / ".gitignore").write_text("build/\n*.log\n")
    sh(r, "git", "add", "-A")
    sh(r, "git", "commit", "-q", "-m", "init")
    return r


def test_fingerprint_is_stable_and_ignores_bookkeeping(repo):
    f = flow_state.fingerprint(repo)
    assert len(f) == 40
    assert flow_state.fingerprint(repo) == f
    (repo / "tasks" / "t.md").write_text("changed\n")
    (repo / "docs" / "specs").mkdir(parents=True)
    (repo / "docs" / "specs" / "s.md").write_text("spec\n")
    assert flow_state.fingerprint(repo) == f


def test_fingerprint_sees_uncommitted_and_untracked_covered_changes(repo):
    f = flow_state.fingerprint(repo)
    (repo / "src.txt").write_text("two\n")
    g = flow_state.fingerprint(repo)
    assert g != f
    (repo / "new.txt").write_text("new\n")
    assert flow_state.fingerprint(repo) not in (f, g)


def test_fingerprint_covers_tracked_file_matching_ignore_rule(repo):
    (repo / "keep.log").write_text("a\n")
    sh(repo, "git", "add", "-f", "keep.log")
    sh(repo, "git", "commit", "-q", "-m", "tracked log")
    f = flow_state.fingerprint(repo)
    (repo / "keep.log").write_text("b\n")
    assert flow_state.fingerprint(repo) != f


def test_fingerprint_skips_untracked_ignored_file(repo):
    f = flow_state.fingerprint(repo)
    (repo / "junk.log").write_text("x\n")
    assert flow_state.fingerprint(repo) == f


def test_fingerprint_index_and_head_projections(repo):
    f = flow_state.fingerprint(repo)
    assert flow_state.fingerprint(repo, "index") == f
    assert flow_state.fingerprint(repo, "head") == f
    (repo / "src.txt").write_text("staged\n")
    sh(repo, "git", "add", "src.txt")
    (repo / "src.txt").write_text("worktree\n")
    w, i, h = (flow_state.fingerprint(repo, m) for m in ("worktree", "index", "head"))
    assert len({w, i, h}) == 3


def test_fingerprint_index_survives_half_staged_task_file(repo):
    (repo / "tasks" / "t.md").write_text("staged\n")
    sh(repo, "git", "add", "tasks/t.md")
    (repo / "tasks" / "t.md").write_text("disk\n")
    assert flow_state.fingerprint(repo, "index") == flow_state.fingerprint(repo, "head")


def test_fingerprint_leaves_real_index_untouched(repo):
    (repo / "src.txt").write_text("dirty\n")
    before = sh(repo, "git", "status", "--porcelain")
    flow_state.fingerprint(repo)
    assert sh(repo, "git", "status", "--porcelain") == before


def test_fingerprint_refuses_dirty_submodule(repo, tmp_path):
    sub = tmp_path / "sub"
    sub.mkdir()
    sh(sub, "git", "init", "-q")
    sh(sub, "git", "config", "user.email", "t@example.com")
    sh(sub, "git", "config", "user.name", "t")
    (sub / "s.txt").write_text("s\n")
    sh(sub, "git", "add", "-A")
    sh(sub, "git", "commit", "-q", "-m", "sub")
    sh(repo, "git", "-c", "protocol.file.allow=always", "submodule", "add", "-q", str(sub), "vendor/sub")
    sh(repo, "git", "commit", "-q", "-m", "add sub")
    f = flow_state.fingerprint(repo)
    (repo / "vendor" / "sub" / "s.txt").write_text("edited\n")
    with pytest.raises(flow_state.DirtySubmodule) as e:
        flow_state.fingerprint(repo)
    assert e.value.paths == ["vendor/sub"]
    sh(repo / "vendor" / "sub", "git", "commit", "-q", "-am", "moved")
    assert flow_state.fingerprint(repo) != f  # pointer moved, allowed


def test_apply_worktree_marks_stale_verification():
    d = flow_state.Derivation("verified", verified_tree="f" * 40)
    same = flow_state.apply_worktree(d, "f" * 40)
    assert same == d
    moved = flow_state.apply_worktree(d, "0" * 40)
    assert moved.state == "implementing" and "covered content changed" in moved.note
    assert flow_state.apply_worktree(d, None) == d
    closed = flow_state.Derivation("closed", verified_tree="f" * 40)
    assert flow_state.apply_worktree(closed, "0" * 40) == closed
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd .worktrees/flow && uv run --with pytest pytest agents/bin/test_flow_state.py -q -k "fingerprint or apply_worktree"`
Expected: FAIL — `AttributeError: … 'fingerprint'`.

- [ ] **Step 3: Write the fingerprint**

Insert after `derive` in `agents/bin/flow-state`:

```python
# --- covered tree -----------------------------------------------------------

class DirtySubmodule(Exception):
    def __init__(self, paths: list[str]):
        super().__init__("dirty submodule: " + ", ".join(paths))
        self.paths = paths


def git(repo: Path, *args: str, env: dict | None = None) -> str:
    return subprocess.run(["git", *args], cwd=repo, check=True, text=True,
                          capture_output=True, env=env).stdout.strip()


def dirty_submodules(repo: Path) -> list[str]:
    out = git(repo, "status", "--porcelain=2", "--ignore-submodules=none")
    dirty = []
    for line in out.splitlines():
        parts = line.split(" ")
        if parts[0] not in ("1", "2"):
            continue
        sub = parts[2]  # "N..." for a file, "S<c><m><u>" for a submodule
        if sub.startswith("S") and ("M" in sub[2:] or "U" in sub[2:]):
            dirty.append(parts[-1] if parts[0] == "1" else parts[-1].split("\t")[0])
    return dirty


def fingerprint(repo: Path, mode: str = "worktree") -> str:
    if mode not in ("worktree", "index", "head"):
        raise ValueError(mode)
    if mode != "head":
        dirty = dirty_submodules(repo)
        if dirty:
            raise DirtySubmodule(dirty)
    git_dir = Path(git(repo, "rev-parse", "--git-dir"))
    if not git_dir.is_absolute():
        git_dir = repo / git_dir
    with tempfile.TemporaryDirectory() as tmp:
        index = Path(tmp) / "index"
        env = {**os.environ, "GIT_INDEX_FILE": str(index)}
        if mode == "head":
            git(repo, "read-tree", "HEAD", env=env)
        else:
            shutil.copy(git_dir / "index", index)
            if mode == "worktree":
                git(repo, "add", "-A", env=env)
        git(repo, "rm", "-r", "-q", "-f", "--cached", "--ignore-unmatch", "--", *EXCLUDED, env=env)
        return git(repo, "write-tree", env=env)


def apply_worktree(d: Derivation, covered: str | None) -> Derivation:
    if d.state != "verified" or covered is None or d.verified_tree == covered:
        return d
    return Derivation("implementing", d.inconsistent,
                      f"verified at tree:{d.verified_tree}, covered content changed", d.verified_tree)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd .worktrees/flow && uv run --with pytest pytest agents/bin/test_flow_state.py -q`
Expected: all pass. Porcelain v2 lines read `1 <XY> <sub> <mH> <mI> <mW> <hH> <hI> <path>` (and `2 … <path>\t<origPath>`), so `<sub>` is `parts[2]`; if the submodule test fails, print `git status --porcelain=2 --ignore-submodules=none` in the fixture repo and compare against that layout before touching anything else.

- [ ] **Step 5: Commit**

```bash
cd .worktrees/flow
git add agents/bin/flow-state agents/bin/test_flow_state.py
git commit -m "feat(flow): fingerprint the covered tree in three projections"
```

---

### Task 4: CLI — `flow-state <id>` and `flow-state fingerprint`

**Files:**
- Modify: `agents/bin/flow-state` (replace the `__main__` stub)
- Modify: `agents/bin/test_flow_state.py`

**Interfaces:**
- Consumes: `derive`, `apply_worktree`, `fingerprint`, `DirtySubmodule`.
- Produces: the command-line contract.
  - `flow-state <id> [--json] [--no-git]` → stdout one line: `<state>`, `<state> (<note>)`, or `<state> (inconsistent: <why>)`; both note and inconsistency print as `<state> (<note>; inconsistent: <why>)`. `--json` prints `{"id","state","inconsistent","note","verified_tree","covered_tree"}`. Exit 0 whenever a state was derived (inconsistent included), 1 on a failure to derive (task not found, `tasks` error, dirty submodule while comparing).
  - `flow-state fingerprint [--index|--head]` → the 40-hex hash; exit 1 with `dirty submodule: <paths>` on stderr when refused.
  - `FLOW_STATE_TASKS` overrides the `tasks` executable (tests use it).

- [ ] **Step 1: Write the failing tests**

Append to `agents/bin/test_flow_state.py`:

```python
import json
import os


@pytest.fixture
def fake_tasks(tmp_path):
    """A stand-in `tasks` that serves show JSON from <dir>/<id>.json."""
    store = tmp_path / "store"
    store.mkdir()
    exe = tmp_path / "tasks"
    exe.write_text(
        "#!/usr/bin/env python3\n"
        "import json, sys, pathlib\n"
        f"store = pathlib.Path({str(store)!r})\n"
        "assert sys.argv[1] == 'show'\n"
        "p = store / (sys.argv[2] + '.json')\n"
        "if not p.exists():\n"
        "    print(json.dumps({'error': {'kind': 'task_not_found'}})); sys.exit(1)\n"
        "print(p.read_text())\n"
    )
    exe.chmod(0o755)

    def put(task, children=()):
        show = {"task": task, "children": [{"id": c["id"], "title": "c", "status": c["status"]} for c in children]}
        (store / f"{task['id']}.json").write_text(json.dumps(show))
        for c in children:
            (store / f"{c['id']}.json").write_text(json.dumps({"task": c, "children": []}))

    return exe, put


def run_cli(exe, *args, cwd=None):
    env = {**os.environ, "FLOW_STATE_TASKS": str(exe)}
    return subprocess.run([str(SCRIPT), *args], cwd=cwd, text=True, capture_output=True, env=env)


def test_cli_prints_leaf_state(fake_tasks, tmp_path):
    exe, put = fake_tasks
    put(record(status="doing", process="direct", notes=["gate: scoped", "gate: implementing w"]))
    r = run_cli(exe, "ai-000001", "--no-git", cwd=tmp_path)
    assert r.returncode == 0 and r.stdout.strip() == "implementing"


def test_cli_prints_inconsistency_and_json(fake_tasks, tmp_path):
    exe, put = fake_tasks
    put(record(status="todo", process="direct", notes=["gate: scoped", "gate: implementing w"]))
    r = run_cli(exe, "ai-000001", "--no-git", cwd=tmp_path)
    assert r.stdout.strip() == "implementing (inconsistent: status todo)"
    j = json.loads(run_cli(exe, "ai-000001", "--no-git", "--json", cwd=tmp_path).stdout)
    assert j["state"] == "implementing" and j["inconsistent"] == "status todo" and j["covered_tree"] is None


def test_cli_fetches_children_for_a_parent(fake_tasks, tmp_path):
    exe, put = fake_tasks
    p = parent(notes=PARENT_GATES)
    put(p, [child("ai-c1", "doing", CHILD_SCOPED + ["gate: implementing w"])])
    r = run_cli(exe, "ai-000001", "--no-git", cwd=tmp_path)
    assert r.stdout.strip() == "implementing"


def test_cli_unknown_task_exits_1(fake_tasks, tmp_path):
    exe, _ = fake_tasks
    r = run_cli(exe, "ai-nope", "--no-git", cwd=tmp_path)
    assert r.returncode == 1 and "ai-nope" in r.stderr


def test_cli_compares_verified_tree_inside_a_repo(fake_tasks, repo):
    exe, put = fake_tasks
    f = flow_state.fingerprint(repo)
    put(record(status="doing", process="direct",
               notes=["gate: scoped", "gate: implementing w", f"gate: verified tree:{f} — ok"]))
    assert run_cli(exe, "ai-000001", cwd=repo).stdout.strip() == "verified"
    (repo / "src.txt").write_text("more\n")
    out = run_cli(exe, "ai-000001", cwd=repo).stdout.strip()
    assert out.startswith("implementing (verified at tree:") and "covered content changed" in out
    j = json.loads(run_cli(exe, "ai-000001", "--json", cwd=repo).stdout)
    assert j["verified_tree"] == f and j["covered_tree"] == flow_state.fingerprint(repo)


def test_cli_outside_a_repo_skips_git(fake_tasks, tmp_path):
    exe, put = fake_tasks
    put(record(status="doing", process="direct",
               notes=["gate: scoped", "gate: implementing w", f"gate: verified tree:{'a' * 40}"]))
    assert run_cli(exe, "ai-000001", cwd=tmp_path).stdout.strip() == "verified"


def test_cli_fingerprint_subcommand(fake_tasks, repo):
    exe, _ = fake_tasks
    assert run_cli(exe, "fingerprint", cwd=repo).stdout.strip() == flow_state.fingerprint(repo)
    assert run_cli(exe, "fingerprint", "--index", cwd=repo).stdout.strip() == flow_state.fingerprint(repo, "index")
    assert run_cli(exe, "fingerprint", "--head", cwd=repo).stdout.strip() == flow_state.fingerprint(repo, "head")
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd .worktrees/flow && uv run --with pytest pytest agents/bin/test_flow_state.py -q -k cli`
Expected: FAIL — the stub exits with "cli not wired yet".

- [ ] **Step 3: Write the CLI**

Replace the `if __name__ == "__main__":` stub in `agents/bin/flow-state` with:

```python
# --- CLI --------------------------------------------------------------------

def tasks_show(task_id: str) -> dict:
    exe = os.environ.get("FLOW_STATE_TASKS", "tasks")
    r = subprocess.run([exe, "show", task_id], text=True, capture_output=True)
    if r.returncode != 0:
        detail = r.stdout.strip() or r.stderr.strip()
        raise SystemExit(f"flow-state: tasks show {task_id} failed: {detail}")
    return json.loads(r.stdout)


def repo_root(cwd: Path) -> Path | None:
    r = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=cwd, text=True, capture_output=True)
    return Path(r.stdout.strip()) if r.returncode == 0 else None


def state_of(task_id: str, use_git: bool) -> dict:
    show = tasks_show(task_id)
    children = [tasks_show(c["id"])["task"] for c in show.get("children") or []]
    d = derive(show, children)
    covered = None
    root = repo_root(Path.cwd()) if use_git else None
    if root is not None and d.state == "verified":
        try:
            covered = fingerprint(root)
        except DirtySubmodule as e:
            raise SystemExit(f"flow-state: {e}")
        d = apply_worktree(d, covered)
    return {"id": task_id, "state": d.state, "inconsistent": d.inconsistent,
            "note": d.note, "verified_tree": d.verified_tree, "covered_tree": covered}


def render(result: dict) -> str:
    extras = [x for x in (result["note"], f"inconsistent: {result['inconsistent']}" if result["inconsistent"] else None) if x]
    return result["state"] + (f" ({'; '.join(extras)})" if extras else "")


def main(argv: list[str]) -> int:
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__.strip())
        return 0
    if argv[0] == "fingerprint":
        mode = {"--index": "index", "--head": "head"}.get(argv[1] if len(argv) > 1 else "", "worktree")
        root = repo_root(Path.cwd())
        if root is None:
            print("flow-state: not inside a git repository", file=sys.stderr)
            return 1
        try:
            print(fingerprint(root, mode))
        except DirtySubmodule as e:
            print(f"flow-state: {e}", file=sys.stderr)
            return 1
        return 0
    task_id = argv[0]
    as_json = "--json" in argv
    use_git = "--no-git" not in argv
    try:
        result = state_of(task_id, use_git)
    except SystemExit as e:
        print(e, file=sys.stderr)
        return 1
    print(json.dumps(result) if as_json else render(result))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd .worktrees/flow && uv run --with pytest pytest agents/bin/test_flow_state.py -q`
Expected: all pass.

- [ ] **Step 5: Run it over every task in `ai` (spec §6.3)**

Run from the worktree. `tasks list` without `--project` reads the checkout you stand in, which is what `flow-state` reads too; `--project ai` would list the registered main checkout, which does not yet have this plan's step children:

```bash
cd .worktrees/flow
for id in $(tasks list --status idea --status todo --status doing --status blocked --status done --status dropped | python3 -c 'import json,sys; d=json.load(sys.stdin); print(" ".join(r["id"] for r in (d if isinstance(d,list) else d.get("tasks",[]))))'); do
  printf '%s  ' "$id"; agents/bin/flow-state "$id" || echo "ERROR"
done
```

Expected: no `ERROR`; completed and unassessed records print `outside`; ideas print `captured`; `ai-f5da3a` prints `implementing` (its children have left `scoped` by now) and its step children print their own states. Anything else is a bug in the derivation or a record that needs a note — fix the script, or report the record in the task note, before committing.

- [ ] **Step 6: Commit**

```bash
cd .worktrees/flow
git add agents/bin/flow-state agents/bin/test_flow_state.py
git commit -m "feat(flow): flow-state CLI over tasks show with covered-tree comparison"
```

---

### Task 5: The `flow` skill

**Files:**
- Create: `agents/skills/flow/SKILL.md`
- Modify: `agents/skills/README.md` (add one bullet after the `tasks, curate, scope, quick-add` bullet)
- Outside the repo: `ln -s ~/d/ai/agents/skills/flow ~/.claude/skills/flow`

**Interfaces:**
- Consumes: the `flow-state` CLI contract from Task 4.
- Produces: the skill text the trial (Task 6) follows.

- [ ] **Step 1: Write the skill**

`agents/skills/flow/SKILL.md`:

````markdown
---
name: flow
description: Use when a project's agent instructions name the flow skill for task work, or when asked to run a task under flow — walks one task through explicit states and gates recorded as notes on the task.
---

# flow

One task, a few states, a gate on every transition. Inside a state you choose
the method; at a gate you produce the artifact, run the check, get the judge's
verdict, and write the record. The record is a note on the task:

    tasks note <id> "gate: <state> — <evidence>"

`~/.agents/bin/flow-state <id>` tells you where a task is;
`~/.agents/bin/flow-state fingerprint` names the content you verified.
`~/.agents` links to the `ai` checkout's `agents/`; nothing puts the script on
PATH, so always call it by that path (or `agents/bin/flow-state` when standing
in `ai`).

## Rules

1. **Find the state.** `~/.agents/bin/flow-state <id>`. `outside` means the record predates
   the flow: confirm it is scoped (process set, a body that says outcome,
   approach, verification — scope it if not), then
   `tasks note <id> "gate: scoped — adopted"`.
2. **Work freely inside a state.** The state names the artifact you are
   producing; how you produce it is yours.
3. **Advance only through the gate.** Artifact, check, judge, record, in that
   order. Never write the record without the gate; never move on without the
   record.
4. **Take back edges out loud.** When work in a state shows an earlier gate no
   longer holds, write `gate: scoped — invalidated: <why>` and say so. Every
   later approval is gone; on the direct path also `tasks edit --process planned`.
5. **Retro before done.** Two or three lines, `tasks note <id> "retro: …"`, on
   which pattern helped or hurt on this task.

## States

| State | Meaning | Status allowed |
| --- | --- | --- |
| `captured` | unscoped idea | `idea` |
| `scoped` | p/size/complexity/process chosen, work understood | `todo`, `doing` |
| `designed` | spec exists and the human reviewed it | `todo`, `doing` |
| `planned` | plan reviewed, steps filed as children, none started | `todo`, `doing` |
| `implementing` | code changing in a task worktree | leaf `doing`; parent `todo`/`doing` |
| `verified` | checks ran against a named covered tree, fresh-context review done | leaf `doing`; parent `todo`/`doing` |
| `closed` | retro written, `tasks done` in the landing commit | `done` |

`doing` before `implementing` is a claim, nothing more. `blocked` counts as
`todo`. `park`/`start` keep the state.

## Gates

| From → To | Artifact | Check | Judge | Record |
| --- | --- | --- | --- | --- |
| captured → scoped | scope brief in the body | `tasks check` clean; p/size/complexity/process set | you | `tasks edit … --process`, `gate: scoped` |
| scoped → designed (planned) | design spec | file exists, no placeholders | **human** | `tasks edit --spec`, `gate: designed <path>` |
| designed → planned (planned) | plan with `### Task N:` headings, one child per heading filed scoped | `tasks check` clean | **human** | `tasks edit --plan`, children with `--step`, `gate: planned <path>` |
| scoped → implementing (direct) | task worktree | `git worktree list` | you | `tasks start`, `gate: implementing <worktree>` |
| implementing → verified | verification output, review findings and disposition | commands ran against covered tree `<f>`; tests exist before the code they cover | a reviewer without your context read the diff at `<f>`; then you | `gate: verified tree:<f> — <commands, review outcome>` |
| verified → closed | retro, the landing commit | `tasks check` clean; covered tree still `<f>` | you | `retro:`, `tasks done`, one commit (below) |

## Planned parent and children

The parent reaches `planned`; its children are filed there with `--parent`,
`--step`, `--complexity`, `--process` and a body that is their scope brief,
plus `gate: scoped — step of <parent> plan`. Each direct child runs
`implementing → verified → closed` in the parent's worktree. The parent is
`implementing` from the first child that starts until its own integration
verification (whole branch, full suite, one fresh review of the combined
diff), which needs every child closed. A child whose invalidation changes the
plan writes `gate: scoped — invalidated` on the parent too.

## Closing sequence

`<f>` is `~/.agents/bin/flow-state fingerprint` at the moment verification ran. It hashes
the working tree, uncommitted edits included, minus `tasks/`, `docs/specs/`,
`docs/plans/`; a dirty submodule makes it refuse until clean.

1. Verify; any fix moves `<f>`, so re-run until the checks pass on the tree you will land.
2. `tasks note <id> "gate: verified tree:<f> — …"`
3. `tasks note <id> "retro: …"`
4. Stage what will land; require `fingerprint --index` = `fingerprint` = `<f>` (both via `~/.agents/bin/flow-state`). A half-staged file fails here — fix it before anything is closed.
5. `tasks done <id> "…"`; stage the `tasks/` change.
6. One commit: code and every `tasks/` change from 2–5.
7. `~/.agents/bin/flow-state fingerprint --head` must equal `<f>`.

If 7 fails, or the commit itself fails for a reason that needs a covered
change: `tasks edit <id> --status todo`, `tasks start <id>`,
`tasks note <id> "gate: implementing — reopened: <what happened>, verified tree:<f>"`,
and start again at 1. A commit that failed for a reason outside the covered
tree (signing, a hook's own dependency) is fixed and retried at 6 with no
record change.

## Opting in

One line in a project's `AGENTS.md`:

> This project uses the `flow` skill for task work. Superpowers process skills
> (brainstorming, writing-plans, executing-plans) do not trigger here; their
> implementation skills may be used inside a state when they fit.

The reference machine is `docs/specs/2026-09-15-flow-state-machine-design.md`
in the `ai` checkout.
````

- [ ] **Step 2: Add the README bullet and the harness link**

In `agents/skills/README.md`, after the `tasks, curate, scope, quick-add` bullet:

```markdown
- `flow/` — the explicit task state machine (states, gates, `gate:` notes) and
  its walker; `agents/bin/flow-state` derives a task's state. Linked from
  `~/.claude/skills/flow` like the others.
```

Then: `ln -s ~/d/ai/agents/skills/flow ~/.claude/skills/flow` (the worktree path is not the link target; the link points at the main checkout, which sees the skill after merge — for the trial before merge, point it at the worktree temporarily: `ln -sfn "$(pwd)/agents/skills/flow" ~/.claude/skills/flow` from `.worktrees/flow`, and repoint after merge).

- [ ] **Step 3: Check the skill loads**

Run: `ls -la ~/.claude/skills/flow/SKILL.md && head -4 ~/.claude/skills/flow/SKILL.md`
Expected: the symlink resolves and the frontmatter's `name: flow` prints. In a fresh Claude Code session, `/flow` appears in the skill list.

- [ ] **Step 4: Commit**

```bash
cd .worktrees/flow
git add agents/skills/flow/SKILL.md agents/skills/README.md
git commit -m "feat(flow): the flow skill, a walker for the explicit task state machine"
```

---

### Task 6: Trial — close one real direct task under the skill

**Files:**
- None in this repo beyond what `ai-c6086b` itself changes (a pre-commit guard for the generated projects block, xs, low, direct).
- Modify: task record `ai-c6086b` (via `tasks` only), and a result note on `ai-f5da3a`.

**Interfaces:**
- Consumes: the `flow` skill (Task 5) and `flow-state` (Task 4).
- Produces: a task record whose gate log is complete, the evidence for spec §6.2.

This task is run in Claude Code with superpowers still installed, in this worktree (`ai-c6086b` is an `ai` task; do not create a second worktree). The trial is the skill's procedure; the steps below are what must be observed, not a substitute for reading the skill. Until `flow` merges, `~/.agents/bin/flow-state` does not exist (it resolves into `main`), so the trial calls `agents/bin/flow-state` from the worktree root; that is the one place the trial departs from the skill text.

- [ ] **Step 1: Adopt and start**

```bash
cd .worktrees/flow
agents/bin/flow-state ai-c6086b        # expected: outside
tasks show ai-c6086b --pretty          # confirm process direct and a scope brief; scope it if not
tasks note ai-c6086b "gate: scoped — adopted"
tasks start ai-c6086b
tasks note ai-c6086b "gate: implementing .worktrees/flow"
agents/bin/flow-state ai-c6086b        # expected: implementing
```

- [ ] **Step 2: Implement `ai-c6086b` as scoped**

Read its body and do the work with tests first (TDD applies inside the state; the skill does not restate it). Commit as you go — commits during `implementing` are normal.

- [ ] **Step 3: Verify and record**

Run the task's own verification commands (from its body) and a fresh-context review of the diff (a subagent, or Codex, given only the diff and the task body). Address findings. Then:

```bash
F=$(agents/bin/flow-state fingerprint)
tasks note ai-c6086b "gate: verified tree:$F — <commands run and their result>; review: <n findings, all addressed>"
agents/bin/flow-state ai-c6086b        # expected: verified
tasks note ai-c6086b "retro: <2–3 lines: what helped, what hurt>"
```

- [ ] **Step 4: Close by the sequence**

Write the sequence as a script so a failed check stops it (`set -eu`) and a failed or empty fingerprint never compares equal to anything. Save it in the scratchpad (not the repo), then run it from the worktree root with `F` exported from step 3.

```bash
cat > "$SCRATCH/close-ai-c6086b.sh" <<'EOF'
#!/usr/bin/env bash
# Spec §3.6 closing sequence for ai-c6086b. Run from the worktree root.
# Required: F (fingerprint verification ran against), DONE_MSG, COMMIT_MSG.
# RETRY=1 re-enters at the commit after a failure that needed no covered change.
set -eu
: "${F:?F must be the fingerprint verification ran against}"
: "${DONE_MSG:?DONE_MSG must say what landed}"
: "${COMMIT_MSG:?COMMIT_MSG must be the conventional message}"
FS=agents/bin/flow-state
ID=ai-c6086b

fp() {  # fp [--index|--head] -> hash on stdout; exits non-zero on failure or empty output
  local out
  out=$("$FS" fingerprint "$@") || { echo "fingerprint $* failed" >&2; return 1; }
  [ -n "$out" ] || { echo "fingerprint $* printed nothing" >&2; return 1; }
  printf '%s\n' "$out"
}

reopen_cmd() {  # reopen_cmd <why>
  echo "  tasks edit $ID --status todo && tasks start $ID && tasks note $ID \"gate: implementing — reopened: $1, verified tree:$F\""
}

land() {  # commit, then the head check; every exit from here is checked
  if ! git commit -m "$COMMIT_MSG"; then
    echo "commit FAILED. If the cause needs no covered change (signing, a hook's own dependency), fix it and rerun:"
    echo "  RETRY=1 F=$F DONE_MSG=... COMMIT_MSG=... $0"
    echo "Otherwise reopen:"
    reopen_cmd "commit failed: <reason>"
    exit 1
  fi
  local head
  head=$(fp --head)
  if [ "$head" != "$F" ]; then
    echo "head check FAILED (head=$head verified=$F). Reopen:"
    reopen_cmd "commit $(git rev-parse --short HEAD) landed tree:$head"
    exit 1
  fi
  echo "landed ok"
  "$FS" "$ID"   # expected: closed
}

if [ "${RETRY:-0}" = 1 ]; then
  land
  exit 0
fi

git add -A -- . ':!docs/specs' ':!docs/plans'
idx=$(fp --index); wt=$(fp)
if [ "$idx" != "$F" ] || [ "$wt" != "$F" ]; then
  echo "preflight FAILED (index=$idx worktree=$wt verified=$F)."
  echo "Stage or revert the rest and rerun; if the working tree changed, state is implementing — restart at step 3."
  exit 1
fi
echo "preflight ok"

tasks done "$ID" "$DONE_MSG"
git add tasks/
land
EOF
chmod +x "$SCRATCH/close-ai-c6086b.sh"
cd .worktrees/flow && F="$F" DONE_MSG="<what landed>" COMMIT_MSG="<conventional message for the guard>" "$SCRATCH/close-ai-c6086b.sh"
```

`SCRATCH` is the session's scratchpad directory. The script validates its inputs before touching the record, exits non-zero at the first failed check with the recovery command for that point, and a retry (`RETRY=1`) goes through the same commit-then-head-check path, so a retried commit that lands unexpected content is caught the same way. Never hand-edit the record to get past a failed check.

- [ ] **Step 5: Record the outcome on the parent**

```bash
tasks note ai-f5da3a "Trial: ai-c6086b closed under flow. flow-state read outside → implementing → verified → closed with no inconsistency; closing sequence preflight and head check both passed first time (or: what happened). Session log kept for ai-9dfba9."
```

Also run the §6.3 sweep from Task 4 step 5 once more; every `ai` record must derive without error.

- [ ] **Step 6: Commit the note**

```bash
cd .worktrees/flow
git add tasks/ai-f5da3a.md
git commit -m "chore(tasks): record the flow trial outcome"
```

---

## After the plan

Parent closure (`ai-f5da3a`) is not a task in this plan; it is the parent's own gate. When Task 6 is done: full test run, one fresh review of the whole branch, `gate: verified tree:<f>` on `ai-f5da3a`, its `retro:`, `tasks done`, and the finishing-a-development-branch decision (merge `flow` into `main`). Copy the excluded spec and plan back to the main checkout before removing the worktree; they are already there, so confirm they match.
