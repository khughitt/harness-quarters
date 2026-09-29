import importlib.util
import json
import os
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


CORPUS = Path(__file__).resolve().parents[1] / "flow" / "gate-notes.jsonl"


def corpus_cases():
    return [json.loads(line) for line in CORPUS.read_text().splitlines() if line.strip()]


@pytest.mark.parametrize("case", corpus_cases(), ids=lambda c: c["text"][:40])
def test_parse_note_matches_corpus(case):
    p = flow_state.parse_note(case["text"])
    assert p.kind == case["kind"]
    for key in ("state", "detail", "tree", "why"):
        if key in case:
            assert getattr(p, key) == case[key], key
    if "verdict" in case:
        if case["verdict"] is None:
            assert p.verdict is None
        else:
            v = case["verdict"]
            assert p.verdict is not None
            assert p.verdict.checks == v["checks"]
            assert [[f.severity, f.disposition, f.text] for f in p.verdict.findings] == v["findings"]
            assert p.verdict.reviewer == v["reviewer"]
            assert p.verdict.session == v["session"]


def test_corpus_covers_every_kind_and_every_malformed_reason():
    kinds = {c["kind"] for c in corpus_cases()}
    assert kinds == {"gate", "not-a-gate", "malformed"}
    reasons = {c["why"].split(" ")[0] for c in corpus_cases() if c["kind"] == "malformed"}
    assert reasons == {"unknown", "tree", "missing", "duplicate", "finding", "empty", "important", "reviewer", "session"}


def test_gates_are_the_gate_kind_notes_only():
    r = record(notes=["gate: scoped", "gate: closed", "retro: x", "gate: verified tree:abc"])
    assert [g.state for g in flow_state.gates(r)] == ["scoped"]


def test_malformed_lists_index_state_and_reason():
    r = record(notes=["gate: scoped", "gate: closed", "gate: verified tree:abc — x"])
    assert flow_state.malformed(r) == [(1, None, "unknown state closed"), (2, "verified", "tree hash not 40 hex")]


def test_gate_carries_verdict():
    text = ("gate: verified tree:" + "a" * 40 +
            " — checks: pytest; review: minor deferred rename; reviewer: human")
    g = flow_state.gates(record(notes=[text]))[0]
    assert g.verdict.findings[0].disposition == "deferred"
    assert flow_state.verified_tree_of(g) == "a" * 40


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
    assert d == flow_state.Derivation("verified", verified_tree=f, verdict="no verdict")
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


H = "a" * 40
GOOD = f"gate: verified tree:{H} — checks: pytest; review: minor addressed rename; reviewer: human"
BAD = f"gate: verified tree:{H} — checks: pytest; review: important deferred rename; reviewer: human"


def test_leaf_malformed_verified_after_valid_verified_falls_back_to_implementing():
    r = record(status="doing", process="direct", notes=["gate: scoped", "gate: implementing .worktrees/x", GOOD, BAD])
    d = flow_state.derive_leaf(r)
    assert d.state == "implementing"
    assert d.inconsistent == "malformed gate at note 3: important finding deferred"
    assert d.verified_tree is None


def test_leaf_malformed_verified_after_implementing_stays_implementing():
    r = record(status="doing", process="direct", notes=["gate: scoped", "gate: implementing .worktrees/x", BAD])
    d = flow_state.derive_leaf(r)
    assert d.state == "implementing"
    assert d.inconsistent == "malformed gate at note 2: important finding deferred"


def test_leaf_done_with_malformed_gate_is_closed_inconsistent():
    r = record(status="done", process="direct",
               notes=["gate: scoped", "gate: implementing .worktrees/x", GOOD, BAD, "retro: x"])
    d = flow_state.derive_leaf(r)
    assert d.state == "closed"
    assert d.inconsistent == "done with last gate implementing; malformed gate at note 3: important finding deferred"


def test_leaf_malformed_unknown_state_voids_nothing():
    r = record(status="doing", process="direct", notes=["gate: scoped", "gate: implementing .worktrees/x", GOOD, "gate: closed"])
    d = flow_state.derive_leaf(r)
    assert d.state == "verified" and d.verified_tree == H
    assert d.inconsistent == "malformed gate at note 3: unknown state closed"


def test_leaf_malformed_cancels_the_whole_tail_of_that_state():
    r = record(status="doing", process="direct",
               notes=["gate: scoped", "gate: implementing .worktrees/x", GOOD, GOOD, BAD])
    assert flow_state.derive_leaf(r).state == "implementing"


def test_leaf_later_valid_gate_supersedes_the_failed_attempt():
    r = record(status="doing", process="direct",
               notes=["gate: scoped", "gate: implementing .worktrees/x", GOOD, BAD, GOOD])
    d = flow_state.derive_leaf(r)
    assert d.state == "verified" and d.inconsistent is None and d.verified_tree == H
    assert d.malformed == ({"note": 3, "state": "verified", "why": "important finding deferred", "superseded": True},)


def test_leaf_malformed_retry_does_not_undo_a_reopen():
    reopen = f"gate: implementing — reopened: commit 0123abc landed tree:{'b' * 40}, verified tree:{H}"
    r = record(status="doing", process="direct",
               notes=["gate: scoped", "gate: implementing .worktrees/x", GOOD, reopen, "gate: implementing tree:abc"])
    d = flow_state.derive_leaf(r)
    assert d.state == "implementing" and d.verified_tree is None
    assert d.inconsistent == "malformed gate at note 4: tree hash not 40 hex"


def test_leaf_back_edge_words_in_finding_text_are_not_a_back_edge():
    prose = f"gate: verified tree:{H} — checks: pytest; review: minor addressed reopened regression fixed, minor addressed invalidated cache entry; reviewer: human"
    r = record(status="doing", process="direct",
               notes=["gate: scoped", "gate: implementing .worktrees/x", prose, BAD])
    d = flow_state.derive_leaf(r)
    assert d.state == "implementing" and d.verified_tree is None
    assert flow_state.is_back_edge(flow_state.Gate("scoped", "— invalidated: the store", "t"))
    assert flow_state.is_back_edge(flow_state.Gate("implementing", "— reopened: commit x", "t"))
    assert not flow_state.is_back_edge(flow_state.Gate("verified", "— reopened: x", "t"))
    assert not flow_state.is_back_edge(flow_state.Gate("scoped", "— reopened: x", "t"))


def test_leaf_malformed_that_leaves_no_gates_is_captured():
    r = record(status="todo", process="direct", notes=["gate: scoped", "gate: scoped tree:abc"])
    d = flow_state.derive_leaf(r)
    assert d.state == "captured"
    assert d.inconsistent == "no well-formed gate; malformed gate at note 1: tree hash not 40 hex"


def test_leaf_done_with_only_a_malformed_gate_is_closed_inconsistent():
    r = record(status="done", process="direct", notes=["gate: verified tree:abc", "retro: x"])
    d = flow_state.derive_leaf(r)
    assert d.state == "closed"
    assert d.inconsistent == "no well-formed gate; malformed gate at note 0: tree hash not 40 hex"


def test_leaf_verified_without_tree_is_a_gate_with_an_inconsistency():
    r = record(status="doing", process="direct", notes=["gate: scoped", "gate: implementing .worktrees/x", "gate: verified — checks ran"])
    d = flow_state.derive_leaf(r)
    assert d.state == "verified"
    assert d.inconsistent == "verified gate without tree:<hash>"
    assert flow_state.malformed(r) == []


def test_leaf_verified_reports_verdict():
    r = record(status="doing", process="direct", notes=["gate: scoped", "gate: implementing .worktrees/x", GOOD])
    d = flow_state.derive_leaf(r)
    assert d.state == "verified" and d.verdict == "findings: 0/1/0, human"
    legacy = record(status="doing", process="direct",
                    notes=["gate: scoped", "gate: implementing .worktrees/x", f"gate: verified tree:{H} — pytest ok"])
    assert flow_state.derive_leaf(legacy).verdict == "no verdict"
    assert flow_state.derive_leaf(record(status="doing", process="direct", notes=["gate: scoped", "gate: implementing .worktrees/x"])).verdict is None


def test_parent_stays_planned_when_a_child_gate_was_cancelled():
    parent = record(status="doing", process="planned", plan="p", notes=["gate: scoped", "gate: planned p"])
    child = record(status="doing", process="direct", id="ai-000002", parent="ai-000001",
                   notes=["gate: scoped — step", "gate: implementing .worktrees/x", "gate: implementing tree:abc"])
    assert flow_state.derive_leaf(child).state == "scoped"
    assert flow_state.derive_parent(parent, [child]).state == "planned"


def test_parent_verified_sees_child_malformed_verification():
    parent = record(status="doing", process="planned", plan="p", notes=["gate: scoped", "gate: planned p", f"gate: verified tree:{H}"])
    child = record(status="doing", process="direct", id="ai-000002", parent="ai-000001",
                   notes=["gate: scoped — step", "gate: implementing .worktrees/x", GOOD, BAD])
    d = flow_state.derive_parent(parent, [child])
    assert d.state == "verified"
    assert d.inconsistent == "child ai-000002 is implementing"


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
    assert ok == flow_state.Derivation("verified", verified_tree=F, verdict="no verdict")
    early = flow_state.derive_parent(p, [child("ai-c1", "doing", CHILD_SCOPED + ["gate: implementing w"])])
    assert early.state == "verified" and "ai-c1 is implementing" in early.inconsistent
    badly_closed = flow_state.derive_parent(p, [child("ai-c1", "done", closed[:-1])])
    assert badly_closed.state == "verified" and "ai-c1 closed (inconsistent" in badly_closed.inconsistent


def test_parent_verified_ignores_dropped_children():
    closed = CHILD_SCOPED + ["gate: implementing w", f"gate: verified tree:{F}", "retro: ok"]
    p = parent(status="doing", notes=PARENT_GATES + [f"gate: verified tree:{F} — full suite"])
    kids = [child("ai-c1", "done", closed), child("ai-c2", "dropped", CHILD_SCOPED)]
    assert flow_state.derive_parent(p, kids) == flow_state.Derivation("verified", verified_tree=F, verdict="no verdict")


def test_parent_verified_blocks_on_shelved_child():
    closed = CHILD_SCOPED + ["gate: implementing w", f"gate: verified tree:{F}", "retro: ok"]
    p = parent(status="doing", notes=PARENT_GATES + [f"gate: verified tree:{F} — full suite"])
    kids = [child("ai-c1", "done", closed), child("ai-c2", "shelved", CHILD_SCOPED)]
    d = flow_state.derive_parent(p, kids)
    assert d.state == "verified" and "ai-c2 is shelved" in d.inconsistent


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


def test_parent_done_with_reopen_gate_is_closed_inconsistent():
    closed = CHILD_SCOPED + ["gate: implementing w", f"gate: verified tree:{F}", "retro: ok"]
    p = parent(status="done", notes=PARENT_GATES + [f"gate: verified tree:{F}", "retro: parent",
                                                    f"gate: implementing — reopened: commit failed, verified tree:{F}"])
    d = flow_state.derive_parent(p, [child("ai-c1", "done", closed)])
    assert d.state == "closed" and "implementing" in d.inconsistent


def test_parent_invalidated_from_child_returns_to_scoped():
    p = parent(status="doing", notes=PARENT_GATES + ["gate: scoped — invalidated: child ai-c1 changed the plan"])
    assert flow_state.derive_parent(p, [child("ai-c1")]) == flow_state.Derivation("scoped")


def test_derive_dispatches_on_children():
    leaf = record(status="doing", process="direct", notes=["gate: scoped", "gate: implementing w"])
    assert flow_state.derive(show_of(leaf, []), []) == flow_state.Derivation("implementing")
    p = parent(notes=PARENT_GATES)
    kids = [child("ai-c1")]
    assert flow_state.derive(show_of(p, kids), kids) == flow_state.Derivation("planned")


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


def test_cli_renders_verdict(fake_tasks, tmp_path):
    exe, put = fake_tasks
    put(record(status="doing", process="direct", notes=["gate: scoped", "gate: implementing .worktrees/x", GOOD]))
    r = run_cli(exe, "ai-000001", "--no-git", cwd=tmp_path)
    assert r.stdout.strip() == "verified (findings: 0/1/0, human)"
    r = run_cli(exe, "ai-000001", "--no-git", "--json", cwd=tmp_path)
    assert json.loads(r.stdout)["verdict"] == "findings: 0/1/0, human"


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
    assert run_cli(exe, "ai-000001", cwd=repo).stdout.strip() == "verified (no verdict)"
    (repo / "src.txt").write_text("more\n")
    out = run_cli(exe, "ai-000001", cwd=repo).stdout.strip()
    assert out.startswith("implementing (verified at tree:") and "covered content changed" in out
    j = json.loads(run_cli(exe, "ai-000001", "--json", cwd=repo).stdout)
    assert j["verified_tree"] == f and j["covered_tree"] == flow_state.fingerprint(repo)


def test_cli_outside_a_repo_skips_git(fake_tasks, tmp_path):
    exe, put = fake_tasks
    put(record(status="doing", process="direct",
               notes=["gate: scoped", "gate: implementing w", f"gate: verified tree:{'a' * 40}"]))
    assert run_cli(exe, "ai-000001", cwd=tmp_path).stdout.strip() == "verified (no verdict)"


def test_cli_fingerprint_subcommand(fake_tasks, repo):
    exe, _ = fake_tasks
    assert run_cli(exe, "fingerprint", cwd=repo).stdout.strip() == flow_state.fingerprint(repo)
    assert run_cli(exe, "fingerprint", "--index", cwd=repo).stdout.strip() == flow_state.fingerprint(repo, "index")
    assert run_cli(exe, "fingerprint", "--head", cwd=repo).stdout.strip() == flow_state.fingerprint(repo, "head")


def test_cli_fingerprint_rejects_unknown_flag(fake_tasks, repo):
    exe, _ = fake_tasks
    r = run_cli(exe, "fingerprint", "--bogus", cwd=repo)
    assert r.returncode == 2 and "usage" in r.stderr
    r = run_cli(exe, "fingerprint", "--index", "extra", cwd=repo)
    assert r.returncode == 2


def test_cli_accepts_flags_before_id(fake_tasks, tmp_path):
    exe, put = fake_tasks
    put(record(status="doing", process="direct", notes=["gate: scoped", "gate: implementing w"]))
    before = run_cli(exe, "--json", "--no-git", "ai-000001", cwd=tmp_path)
    after = run_cli(exe, "ai-000001", "--json", "--no-git", cwd=tmp_path)
    assert before.returncode == 0 and before.stdout == after.stdout
