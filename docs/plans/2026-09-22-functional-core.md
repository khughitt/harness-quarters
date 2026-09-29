# Functional core framing: gate-note grammar and typed verdict — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the gate-note convention a checked type: one grammar with a golden corpus, one parsing entry point in `flow-state` that classifies every note as gate, not-a-gate or malformed, a derivation that never lets a malformed gate expose an earlier one, and a verified-gate record that carries finding records and a reviewer field.

**Architecture:** `agents/bin/flow-state` gains `parse_note(text) -> ParsedNote` and the `Finding` / `Verdict` records; `gates()` and `verified_tree_of` are expressed through it, and a new `malformed()` feeds the derivation, which voids earlier gates naming the state a malformed note attempted and reports the inconsistency. The grammar lives in `agents/flow/gate-notes.md` beside its corpus `agents/flow/gate-notes.jsonl`; the corpus is the test fixture, and obs consumes the same file later (obs-8ad564, outside this plan). The flow skill and the flow spec's gate table are updated to the verified-note shape last.

**Tech Stack:** Python 3.11 stdlib (`re`, `json`, `dataclasses`), pytest via `uv run --with pytest pytest agents/bin/test_flow_state.py` (the file imports the script through `importlib`, as it does today). No new dependencies, no obs changes.

**Spec:** `docs/specs/2026-09-21-functional-core-design.md`, sections 3.5, 4.1, 4.2 and 6. The flow machine itself is `docs/specs/2026-09-15-flow-state-machine-design.md`.

## Global Constraints

- Work happens in the task worktree `.worktrees/functional-core` (branch `feat/functional-core`); every task runs under the flow skill as a child of ai-634de8 (`gate: implementing`, `gate: verified tree:<f>`, `retro:`, `tasks done` in the landing commit).
- Python 3.11 standard library only; the script stays a single executable file without a `.py` suffix.
- Existing tests in `agents/bin/test_flow_state.py` keep passing unchanged, except where a task says which assertion it revises and why.
- Spec 4.1: a `verified` note without a tree is a `gate` with the tree absent, never `malformed`; the derivation keeps reporting `verified gate without tree:<hash>` for it.
- Spec 4.2: field parsing applies only when a `verified` detail contains `review:`; a comma ends a finding, a semicolon ends a field, empty finding text is malformed, `important deferred` is malformed.
- Spec 4.2: the history is reduced in order; a malformed gate note cancels the tail gates naming its state, stops at a back edge, and is superseded by any later well-formed gate; a live one reports `<state> (inconsistent: malformed gate at note <i>: <why>)`, a superseded one is a JSON diagnostic only; with no effective gate left the record is `captured`, or `closed` when done.
- No path such as a home directory appears in code comments or docs.
- Conventional commits, no attribution lines.

---

### Task 1: `parse_note`, the grammar and the corpus

**Files:**
- Create: `agents/flow/gate-notes.md`
- Create: `agents/flow/gate-notes.jsonl`
- Modify: `agents/bin/flow-state` (module docstring; the block between `GATE_RE` and `# --- leaf derivation`)
- Test: `agents/bin/test_flow_state.py`

**Interfaces:**
- Consumes: nothing new. `GATE_STATES`, `GATE_RE`, `TREE_RE`, `Gate` exist.
- Produces, for Task 2 and Task 3:

```python
@dataclass(frozen=True)
class Finding:
    severity: str      # "important" | "minor"
    disposition: str   # "addressed" | "deferred"
    text: str          # non-empty, contains neither "," nor ";"

@dataclass(frozen=True)
class Verdict:
    checks: str
    findings: tuple[Finding, ...]   # empty tuple for "review: none"
    reviewer: str                   # label: "<harness>/<model>" | "human" | "none"
    session: str | None             # qualified id after "session:", or None

@dataclass(frozen=True)
class ParsedNote:
    kind: str                       # "gate" | "not-a-gate" | "malformed"
    state: str | None = None        # gate: one of GATE_STATES; malformed: the attempted state if it is a known one, else None
    detail: str = ""                # gate: text after the state, stripped (leading "—" kept, as Gate.detail keeps it today)
    tree: str | None = None         # gate: the 40-hex hash after "tree:", anywhere in the detail
    verdict: Verdict | None = None  # gate + verified + "review:" present
    why: str | None = None          # malformed: one short reason

def parse_note(text: str) -> ParsedNote: ...
def gates(record: dict) -> list[Gate]: ...          # unchanged signature; well-formed gates only, via parse_note
def malformed(record: dict) -> list[tuple[int, str | None, str]]: ...   # (note index, attempted state or None, why)
```

`Gate` gains one optional field, `verdict: Verdict | None = None`, appended after `index` so positional construction in existing tests still works. `Derivation` and `TODO_LIKE` are not touched by this task.

- [ ] **Step 1: Write the grammar document**

Create `agents/flow/gate-notes.md`:

````markdown
# Gate notes: the grammar

A gate note is a task note whose text, after stripping surrounding whitespace,
begins with `gate:`. `agents/bin/flow-state` is the reference parser
(`parse_note`); `agents/flow/gate-notes.jsonl` is the corpus every parser of
these notes is tested against. The machine the states belong to is
`docs/specs/2026-09-15-flow-state-machine-design.md`.

## Kinds

`parse_note(text)` returns one of three kinds.

- `not-a-gate`: the stripped text does not begin with `gate:`. Prose that
  mentions "gate:" later in the sentence, and every `retro:` note, are this.
- `gate`: `gate:` followed by optional whitespace, one of `scoped`, `designed`,
  `planned`, `implementing`, `verified`, then optional detail. The detail is
  the remainder, stripped; a leading em dash is part of the detail.
- `malformed`: the stripped text begins with `gate:` and the rest is not a
  gate. The reasons are listed below. A malformed note is a failed attempt at
  the state it names: the derivation cancels the gates at the tail of the
  history that name that state, stops at a back edge, and forgets the attempt
  once a later well-formed gate supersedes it (functional core spec, 4.2).

## Tree

The first `tree:` token in the detail, wherever it appears, names the covered
tree; its value is the run of letters and digits after the colon. A `verified`
gate without one is still a gate: the derivation reports it as
`verified gate without tree:<hash>`. A first token whose value is not exactly
40 hex characters makes the note malformed; later tokens (a reopen note names
two trees) are free text.

## The verified verdict

When a `verified` detail contains `review:`, the detail after the tree token
and the leading dash is a list of fields separated by `;`, each `name: value`,
every name exactly once, in any order, no other names:

    checks: <free text without ";">
    review: none | <finding>, <finding>, ...
    reviewer: <label> [session:<qualified id>]

    finding := (important | minor) (addressed | deferred) <text>
    text    := one or more characters, none of them "," or ";"
    label   := human | none | <harness>/<model>
    session := <harness>:<native id>   harness is [a-z][a-z0-9-]*, the id is non-empty and has no whitespace

Whitespace separates a finding's three parts: `important addressedness …` has
no disposition and is malformed, and `important addressed` alone has empty
text.

A `verified` detail without `review:` is free text and carries no verdict.

## Malformed reasons

| Reason | Example |
| --- | --- |
| `unknown state <word>` | `gate: reviewed by someone` |
| `tree hash not 40 hex` | `gate: verified tree:abc` |
| `missing field <name>` | a verdict without `reviewer:` |
| `unknown field <name>` | `checks: a; b; review: none; reviewer: human` |
| `duplicate field <name>` | two `review:` fields |
| `finding without severity and disposition: <text>` | `review: minor addressed handle retries, timeouts` |
| `empty finding text` | `review: minor addressed ` |
| `important finding deferred` | `review: important deferred rename` |
| `reviewer field` | `reviewer: codex/gpt-5.6 extra words` |
| `session id` | `session:garbage`, `session:codex:` |
````

- [ ] **Step 2: Write the corpus**

Create `agents/flow/gate-notes.jsonl`. `H` below stands for forty `a` characters; write the literal hash in the file. One JSON object per line; keys absent from a case are not compared by the test, `kind` is always present.

```json
{"text": "gate: scoped — adopted", "kind": "gate", "state": "scoped", "detail": "— adopted", "tree": null, "verdict": null}
{"text": "gate: scoped", "kind": "gate", "state": "scoped", "detail": "", "tree": null}
{"text": "gate: implementing .worktrees/x", "kind": "gate", "state": "implementing", "detail": ".worktrees/x", "tree": null}
{"text": "   gate: implementing .worktrees/x  ", "kind": "gate", "state": "implementing", "detail": ".worktrees/x"}
{"text": "gate: scoped — invalidated: the spec did not settle the store", "kind": "gate", "state": "scoped", "detail": "— invalidated: the spec did not settle the store"}
{"text": "gate: implementing — reopened: commit 0123abc landed tree:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb, verified tree:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", "kind": "gate", "state": "implementing", "tree": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"}
{"text": "gate: designed docs/specs/2026-09-21-functional-core-design.md — human review", "kind": "gate", "state": "designed", "tree": null}
{"text": "gate: planned docs/plans/2026-09-22-functional-core.md", "kind": "gate", "state": "planned"}
{"text": "gate: verified tree:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa — pytest: 49 passed; fresh-context review (sonnet) approved, 2 minors deferred", "kind": "gate", "state": "verified", "tree": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", "verdict": null}
{"text": "gate: verified — pytest ok; tree:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", "kind": "gate", "state": "verified", "tree": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", "verdict": null}
{"text": "gate: verified — checks ran, no hash recorded", "kind": "gate", "state": "verified", "tree": null, "verdict": null}
{"text": "gate: verified tree:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa — checks: pytest 61 passed; review: important addressed missing null check, minor deferred rename helper; reviewer: codex/gpt-5.6 session:codex:0192", "kind": "gate", "state": "verified", "tree": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", "verdict": {"checks": "pytest 61 passed", "findings": [["important", "addressed", "missing null check"], ["minor", "deferred", "rename helper"]], "reviewer": "codex/gpt-5.6", "session": "codex:0192"}}
{"text": "gate: verified tree:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa — review: none; reviewer: human; checks: just gate", "kind": "gate", "state": "verified", "verdict": {"checks": "just gate", "findings": [], "reviewer": "human", "session": null}}
{"text": "gate: verified tree:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa — checks: pytest; review: minor addressed one, minor addressed two; reviewer: claude-code/claude-sonnet-5", "kind": "gate", "state": "verified", "verdict": {"checks": "pytest", "findings": [["minor", "addressed", "one"], ["minor", "addressed", "two"]], "reviewer": "claude-code/claude-sonnet-5", "session": null}}
{"text": "gate: verified tree:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa — checks: pytest; review: none; reviewer: none", "kind": "gate", "state": "verified", "verdict": {"checks": "pytest", "findings": [], "reviewer": "none", "session": null}}
{"text": "gate: reviewed by someone", "kind": "malformed", "state": null, "why": "unknown state reviewed"}
{"text": "gate: closed", "kind": "malformed", "state": null, "why": "unknown state closed"}
{"text": "gate: verified tree:abc — x", "kind": "malformed", "state": "verified", "why": "tree hash not 40 hex"}
{"text": "gate: verified tree:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa — checks: pytest; review: important deferred rename; reviewer: human", "kind": "malformed", "state": "verified", "why": "important finding deferred"}
{"text": "gate: verified tree:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa — checks: pytest; review: minor addressed ; reviewer: human", "kind": "malformed", "state": "verified", "why": "empty finding text"}
{"text": "gate: verified tree:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa — checks: pytest; review: minor addressed handle retries, timeouts; reviewer: human", "kind": "malformed", "state": "verified", "why": "finding without severity and disposition: timeouts"}
{"text": "gate: verified tree:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa — checks: a; b; review: none; reviewer: human", "kind": "malformed", "state": "verified", "why": "unknown field b"}
{"text": "gate: verified tree:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa — review: none; reviewer: human", "kind": "malformed", "state": "verified", "why": "missing field checks"}
{"text": "gate: verified tree:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa — checks: x; review: none; review: none; reviewer: human", "kind": "malformed", "state": "verified", "why": "duplicate field review"}
{"text": "gate: verified tree:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa — checks: x; review: none; reviewer: codex/gpt-5.6 extra words", "kind": "malformed", "state": "verified", "why": "reviewer field"}
{"text": "gate: verified tree:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa — checks: x; review: important addressedness is unproven; reviewer: human", "kind": "malformed", "state": "verified", "why": "finding without severity and disposition: important addressedness is unproven"}
{"text": "gate: verified tree:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa — checks: x; review: important addressed; reviewer: human", "kind": "malformed", "state": "verified", "why": "empty finding text"}
{"text": "gate: verified tree:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa — checks: x; review: none; reviewer: codex/gpt-5.6 session:garbage", "kind": "malformed", "state": "verified", "why": "session id"}
{"text": "gate: verified tree:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa — checks: x; review: none; reviewer: codex/gpt-5.6 session:codex:", "kind": "malformed", "state": "verified", "why": "session id"}
{"text": "the gate: verified note was written yesterday", "kind": "not-a-gate"}
{"text": "retro: the gate helped; the fingerprint check caught a half-staged file", "kind": "not-a-gate"}
{"text": "parked (waiting on user): review the spec", "kind": "not-a-gate"}
```

Then add every distinct gate-note shape on record that the lines above do not already cover: run

```sh
tasks list --all-projects --json | jq -r '.tasks[].id' > /tmp/ids
tasks list --all-projects --status done --json | jq -r '.tasks[].id' >> /tmp/ids
for id in $(sort -u /tmp/ids); do tasks show "$id" --json | jq -r '.task.notes[]?.text | select(startswith("gate:"))'; done | sort -u
```

(the scratchpad directory is fine in place of `/tmp`), read the output, and append one corpus line per shape that differs from the cases above in structure (not merely in wording), each with the parse result you expect. Every appended line must be `gate` or `malformed`; if a `malformed` one appears on record, say so in the task note, because Task 2's sweep will change that record's reported state.

- [ ] **Step 3: Write the failing tests**

Append to `agents/bin/test_flow_state.py`, after `test_verified_tree_of_extracts_hash`:

```python
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
```

The file already imports `json` further down (inside the CLI section); move that `import json` and `import os` to the top imports so `corpus_cases()` can use `json` at collection time.

- [ ] **Step 4: Run the tests to verify they fail**

Run: `uv run --with pytest pytest agents/bin/test_flow_state.py -q`
Expected: the new tests error with `AttributeError: module 'flow_state' has no attribute 'parse_note'` (and `malformed`); every pre-existing test passes.

- [ ] **Step 5: Implement `parse_note`, `malformed`, and re-express `gates`**

In `agents/bin/flow-state`, make three replacements. Leave `TODO_LIKE`, `STATES`, `GATE_STATES`, `EXCLUDED` and the whole `Derivation` class exactly where and as they are.

First, replace the two lines `GATE_RE = ...` and `TREE_RE = ...` with:

```python
GATE_RE = re.compile(r"^gate:\s*(\S+)\s*(.*)$", re.S)
TREE_RE = re.compile(r"tree:([0-9a-f]{40})")
TREE_TOKEN_RE = re.compile(r"tree:([0-9A-Za-z]*)")
FINDING_RE = re.compile(r"^(important|minor)\s+(addressed|deferred)(?:\s+(.*))?$", re.S)
LABEL_RE = re.compile(r"^(human|none|[A-Za-z0-9._-]+/[A-Za-z0-9._\[\]-]+)$")
SESSION_RE = re.compile(r"^[a-z][a-z0-9-]*:\S+$")
VERDICT_FIELDS = ("checks", "review", "reviewer")
```

Second, replace the `Gate` class (and only it; `Derivation` follows it and stays) with:

```python


@dataclass(frozen=True)
class Finding:
    severity: str
    disposition: str
    text: str


@dataclass(frozen=True)
class Verdict:
    checks: str
    findings: tuple
    reviewer: str
    session: str | None


@dataclass(frozen=True)
class ParsedNote:
    kind: str
    state: str | None = None
    detail: str = ""
    tree: str | None = None
    verdict: Verdict | None = None
    why: str | None = None


@dataclass(frozen=True)
class Gate:
    state: str
    detail: str
    at: str
    index: int = -1
    verdict: Verdict | None = None
```

Third, replace the section from the comment line `# --- gate parsing` through the end of `verified_tree_of` with:

```python
class Malformed(Exception):
    pass


def _parse_findings(value: str) -> tuple:
    value = value.strip()
    if value == "none":
        return ()
    out = []
    for part in value.split(","):
        part = part.strip()
        m = FINDING_RE.match(part)
        if not m:
            raise Malformed(f"finding without severity and disposition: {part}")
        severity, disposition, text = m.group(1), m.group(2), (m.group(3) or "").strip()
        if not text:
            raise Malformed("empty finding text")
        if severity == "important" and disposition == "deferred":
            raise Malformed("important finding deferred")
        out.append(Finding(severity, disposition, text))
    return tuple(out)


def _parse_verdict(detail: str) -> Verdict:
    body = TREE_TOKEN_RE.sub("", detail, count=1).strip().lstrip("—-").strip()
    fields: dict[str, str] = {}
    for part in body.split(";"):
        name, sep, value = part.strip().partition(":")
        name = name.strip()
        if not sep or name not in VERDICT_FIELDS:
            raise Malformed(f"unknown field {name or part.strip()}")
        if name in fields:
            raise Malformed(f"duplicate field {name}")
        fields[name] = value.strip()
    for name in VERDICT_FIELDS:
        if name not in fields:
            raise Malformed(f"missing field {name}")
    words = fields["reviewer"].split()
    session = None
    if len(words) == 2 and words[1].startswith("session:"):
        session = words[1][len("session:"):]
        if not SESSION_RE.match(session):
            raise Malformed("session id")
    elif len(words) != 1:
        raise Malformed("reviewer field")
    if not LABEL_RE.match(words[0]):
        raise Malformed("reviewer field")
    return Verdict(fields["checks"], _parse_findings(fields["review"]), words[0], session)


def parse_note(text: str) -> ParsedNote:
    t = text.strip()
    if not t.startswith("gate:"):
        return ParsedNote("not-a-gate")
    m = GATE_RE.match(t)
    state = m.group(1) if m else ""
    if state not in GATE_STATES:
        return ParsedNote("malformed", None, why=f"unknown state {state}")
    detail = m.group(2).strip()
    tree = None
    token = TREE_TOKEN_RE.search(detail)
    if token:
        if not re.fullmatch(r"[0-9a-f]{40}", token.group(1)):
            return ParsedNote("malformed", state, detail, why="tree hash not 40 hex")
        tree = token.group(1)
    verdict = None
    if state == "verified" and "review:" in detail:
        try:
            verdict = _parse_verdict(detail)
        except Malformed as e:
            return ParsedNote("malformed", state, detail, tree, why=str(e))
    return ParsedNote("gate", state, detail, tree, verdict)


# --- gate parsing -----------------------------------------------------------

def gates(record: dict) -> list[Gate]:
    out = []
    for i, n in enumerate(record.get("notes") or []):
        p = parse_note(n["text"])
        if p.kind == "gate":
            out.append(Gate(p.state, p.detail, n["at"], i, p.verdict))
    return out


def malformed(record: dict) -> list[tuple[int, str | None, str]]:
    out = []
    for i, n in enumerate(record.get("notes") or []):
        p = parse_note(n["text"])
        if p.kind == "malformed":
            out.append((i, p.state, p.why))
    return out


def retro_after(record: dict, gate: Gate) -> bool:
    """A retro: note positioned after the gate's note (by index, never by clock or text)."""
    notes = record.get("notes") or []
    return any(n["text"].strip().startswith("retro:") for n in notes[gate.index + 1:])


def verified_tree_of(gate: Gate) -> str | None:
    m = TREE_RE.search(gate.detail)
    return m.group(1) if m else None
```

Note `GATE_RE` now captures any first word so the unknown-state reason can name it; the state check moved into `parse_note`. Update the module docstring's last sentence to: `the gate grammar is agents/flow/gate-notes.md, with its corpus beside it.` After the edit, `grep -n "class Derivation" agents/bin/flow-state` must still print one line.

- [ ] **Step 6: Run the tests to verify they pass**

Run: `uv run --with pytest pytest agents/bin/test_flow_state.py -q`
Expected: all pass, including `test_gates_ignores_unknown_state_words` (a malformed note is still not in `gates()`) and `test_gates_parses_state_and_detail_in_order` (detail keeps its leading dash).

- [ ] **Step 7: Commit**

```bash
git add agents/flow/gate-notes.md agents/flow/gate-notes.jsonl agents/bin/flow-state agents/bin/test_flow_state.py
git commit -m "feat(flow): parse_note classifies gate notes against one grammar and corpus"
```

---

### Task 2: The derivation reduces the history in order, and reports the verdict

**Files:**
- Modify: `agents/bin/flow-state` (`Derivation`, `derive_leaf`, `derive_parent`, `state_of`, `render`)
- Test: `agents/bin/test_flow_state.py`

**Interfaces:**
- Consumes from Task 1: `gates(record)`, `malformed(record)`, `Gate.verdict`, `Verdict`, `Finding`.
- Produces: `Derivation` gains two fields after `verified_tree`: `verdict: str | None = None` (a rendered summary, `no verdict` or `findings: <important addressed>/<minor addressed>/<minor deferred>, <label>`, present only when the derived state is `verified`) and `malformed: tuple = ()` (one dict per malformed note, `{"note", "state", "why", "superseded"}`). `state_of` returns both under `"verdict"` and `"malformed"`; `render` appends the verdict inside the parentheses and shows only live malformed notes, as the inconsistency. Helpers:

```python
BACK_EDGE_RE = re.compile(r"^[—-]+\s*(invalidated|reopened):")
def is_back_edge(gate: Gate) -> bool: ...   # scoped with a leading "— invalidated:", or implementing with a leading "— reopened:"
def reduce_history(record: dict) -> tuple[list[Gate], list[dict]]: ...   # effective gates in order, every malformed note with its superseded flag
def _with_malformed(d: Derivation, bad: list[dict]) -> Derivation: ...
```

- [ ] **Step 1: Write the failing tests**

Append to `agents/bin/test_flow_state.py`, after `test_leaf_dropped_or_shelved_is_outside`:

```python
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


def test_parent_verified_sees_child_malformed_verification():
    parent = record(status="doing", process="planned", plan="p", notes=["gate: scoped", "gate: planned p", f"gate: verified tree:{H}"])
    child = record(status="doing", process="direct", id="ai-000002", parent="ai-000001",
                   notes=["gate: scoped — step", "gate: implementing .worktrees/x", GOOD, BAD])
    d = flow_state.derive_parent(parent, [child])
    assert d.state == "verified"
    assert d.inconsistent == "child ai-000002 is implementing"
```

Also add to the CLI section, after `test_cli_prints_inconsistency_and_json`:

```python
def test_cli_renders_verdict(fake_tasks, tmp_path):
    exe, put = fake_tasks
    put(record(status="doing", process="direct", notes=["gate: scoped", "gate: implementing .worktrees/x", GOOD]))
    r = run_cli(exe, "ai-000001", "--no-git", cwd=tmp_path)
    assert r.stdout.strip() == "verified (findings: 0/1/0, human)"
    r = run_cli(exe, "ai-000001", "--no-git", "--json", cwd=tmp_path)
    assert json.loads(r.stdout)["verdict"] == "findings: 0/1/0, human"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run --with pytest pytest agents/bin/test_flow_state.py -q -k "malformed or verdict"`
Expected: the new tests fail. The fallback tests fail because the derivation reads the last well-formed gate (`verified`) and reports it; the verdict and supersession tests fail with `AttributeError: 'Derivation' object has no attribute 'verdict'` or `'malformed'`.

- [ ] **Step 3: Implement**

In `agents/bin/flow-state`:

Add `verdict: str | None = None` and then `malformed: tuple = ()` as the last two fields of `Derivation`.

Add before `# --- leaf derivation`:

```python
BACK_EDGE_RE = re.compile(r"^[—-]+\s*(invalidated|reopened):")


def is_back_edge(gate: Gate) -> bool:
    """A recorded back edge: the marker leads the detail and matches the state (spec 4.2)."""
    m = BACK_EDGE_RE.match(gate.detail)
    return bool(m) and (gate.state, m.group(1)) in (("scoped", "invalidated"), ("implementing", "reopened"))


def reduce_history(record: dict) -> tuple[list[Gate], list[dict]]:
    """Fold the notes in order (spec 4.2): a well-formed gate appends and supersedes every
    earlier malformed note; a malformed note naming a known state cancels the tail gates
    naming that state, stopping at a back edge; an unknown state cancels nothing."""
    eff: list[Gate] = []
    bad: list[dict] = []
    for i, n in enumerate(record.get("notes") or []):
        p = parse_note(n["text"])
        if p.kind == "gate":
            eff.append(Gate(p.state, p.detail, n["at"], i, p.verdict))
            for b in bad:
                b["superseded"] = True
        elif p.kind == "malformed":
            if p.state is not None:
                while eff and eff[-1].state == p.state and not is_back_edge(eff[-1]):
                    eff.pop()
            bad.append({"note": i, "state": p.state, "why": p.why, "superseded": False})
    return eff, bad


def _with_malformed(d: Derivation, bad: list[dict]) -> Derivation:
    if not bad:
        return d
    problems = [f"malformed gate at note {b['note']}: {b['why']}" for b in bad if not b["superseded"]]
    joined = "; ".join(([d.inconsistent] if d.inconsistent else []) + problems) or None
    return Derivation(d.state, joined, d.note, d.verified_tree, d.verdict, tuple(bad))


def _no_effective_gate(record: dict, d: Derivation) -> Derivation:
    """Only malformed gate notes: not `outside` (the flow touched it); captured, or closed when done."""
    if d.state != "outside" or d.note is not None:
        return d
    return Derivation("closed" if record["status"] == "done" else "captured", "no well-formed gate")


def _verdict_summary(gate: Gate) -> str:
    v = gate.verdict
    if v is None:
        return "no verdict"
    ia = sum(1 for f in v.findings if f.severity == "important" and f.disposition == "addressed")
    ma = sum(1 for f in v.findings if f.severity == "minor" and f.disposition == "addressed")
    md = sum(1 for f in v.findings if f.severity == "minor" and f.disposition == "deferred")
    return f"findings: {ia}/{ma}/{md}, {v.reviewer}"


def _with_verdict(d: Derivation, last: Gate) -> Derivation:
    if d.state != "verified" or last.state != "verified":
        return d
    return Derivation(d.state, d.inconsistent, d.note, d.verified_tree, _verdict_summary(last), d.malformed)
```

Rename the existing `derive_leaf` to `_derive_leaf(record, gs)` and delete its `gs = gates(record)` line; likewise `derive_parent` to `_derive_parent(record, children, gs)`. Then add:

```python
def derive_leaf(record: dict) -> Derivation:
    gs, bad = reduce_history(record)
    d = _derive_leaf(record, gs)
    d = _with_verdict(d, gs[-1]) if gs else (_no_effective_gate(record, d) if bad else d)
    return _with_malformed(d, bad)


def derive_parent(record: dict, children: list[dict]) -> Derivation:
    gs, bad = reduce_history(record)
    d = _derive_parent(record, children, gs)
    d = _with_verdict(d, gs[-1]) if gs else (_no_effective_gate(record, d) if bad else d)
    return _with_malformed(d, bad)
```

In `_derive_parent`, the existing `if "reopened" not in last.detail:` becomes `if not is_back_edge(last):`, the same anchored test; the Task 2 sweep confirms no record on the host changes state because of it.

`_derive_leaf` keeps its `dropped`/`shelved` check first, so a shelved record with a malformed note stays `outside (shelved)` with the inconsistency appended; `_no_effective_gate` leaves that case alone because `note` is set.

In `_derive_parent`, the early return for a parent whose last gate is `scoped` or `designed` changes from `derive_leaf(record)` to `_derive_leaf(record, gs)`, so the wrapper reports a malformed note once rather than twice. The `derive_leaf(c)` calls over children stay: a child is derived through the public function, so its malformed note is reported as that child's inconsistency and state, which the parent test asserts as `child ai-000002 is implementing`.

In `apply_worktree`, the returned derivation becomes `Derivation("implementing", d.inconsistent, f"verified at tree:{d.verified_tree}, covered content changed", d.verified_tree, None, d.malformed)`: the verdict is dropped on purpose, since the state is no longer `verified`, and the malformed diagnostics are carried.

In `state_of`, add `"verdict": d.verdict` and `"malformed": list(d.malformed)` to the returned dict. In `render`:

```python
def render(result: dict) -> str:
    extras = [x for x in (
        result["note"],
        result.get("verdict"),
        f"inconsistent: {result['inconsistent']}" if result["inconsistent"] else None,
    ) if x]
    return result["state"] + (f" ({'; '.join(extras)})" if extras else "")
```

- [ ] **Step 4: Run the whole suite**

Five existing assertions expect a `verified` derivation without the new field and must be updated, and only these five; each is an intentional change and the commit body names them:

- `test_leaf_verified_carries_tree_and_requires_doing`: `Derivation("verified", verified_tree=f)` becomes `Derivation("verified", verified_tree=f, verdict="no verdict")`.
- `test_parent_verified_requires_every_child_closed`: the `ok ==` line, same change with `F`.
- `test_parent_verified_ignores_dropped_children`: same change with `F`.
- `test_cli_compares_verified_tree_inside_a_repo`: the first assertion expects `"verified (no verdict)"`.
- `test_cli_outside_a_repo_skips_git`: expects `"verified (no verdict)"`.

Run: `uv run --with pytest pytest agents/bin/test_flow_state.py -q`
Expected: all pass. No other existing assertion changes; if one fails, the implementation is wrong, not the test.

- [ ] **Step 5: Sweep every gated record on the host and compare with main**

From the worktree, with `main` as the reference:

```sh
S=$(mktemp -d)
{ tasks list --all-projects --json | jq -r '.tasks[].id'; tasks list --all-projects --status done --json | jq -r '.tasks[].id'; } | sort -u > "$S/ids"
for id in $(cat "$S/ids"); do
  before=$(~/.agents/bin/flow-state "$id" --no-git 2>&1)
  after=$(agents/bin/flow-state "$id" --no-git 2>&1)
  [ "$before" = "$after" ] || echo "$id | $before | $after"
done | tee "$S/diff"
wc -l < "$S/diff"
```

`~/.agents/bin/flow-state` resolves to the main checkout's script and `agents/bin/flow-state` to this worktree's. Expected: the only differences are open `verified` records rendering as `verified (no verdict)`, and any record whose gate note Task 1's corpus step reported as malformed on record (a live one adds an inconsistency; a superseded one changes nothing in the rendering). Any other difference is a regression to fix before the gate. Paste the count and the differing lines into the task note.

- [ ] **Step 6: Commit**

```bash
git add agents/bin/flow-state agents/bin/test_flow_state.py
git commit -m "feat(flow): a malformed gate voids the state it attempted; verified reports its verdict"
```

---

### Task 3: The verified-note shape in the skill and the flow spec

**Files:**
- Modify: `agents/skills/flow/SKILL.md` (the `implementing → verified` row of the Gates table; step 2 of the closing sequence)
- Modify: `docs/specs/2026-09-15-flow-state-machine-design.md` (section 3.2 row `implementing → verified`; section 3.5 gains one sentence naming the grammar)
- Modify: `docs/specs/2026-09-21-functional-core-design.md` (status line only)

**Interfaces:**
- Consumes from Task 1: the grammar in `agents/flow/gate-notes.md`.
- Produces: nothing for code. The goal's own closing (ai-634de8) writes the first `verified` note in this shape.

- [ ] **Step 1: Update the skill's gate row**

In `agents/skills/flow/SKILL.md`, replace the `implementing → verified` row with:

```markdown
| implementing → verified | verification output; each review finding with severity and disposition | commands ran against covered tree `<f>`; tests exist before the code they cover; the note parses (`agents/flow/gate-notes.md`) | a reviewer without your context, dispatched by you, read the diff at `<f>`; then you | `gate: verified tree:<f> — checks: <commands and result>; review: none \| <severity> <disposition> <text>, …; reviewer: <harness/model \| human \| none> [session:<harness:id>]` |
```

and add after the table:

```markdown
A finding is `important` or `minor`, `addressed` or `deferred`; its text has no
comma or semicolon. `important deferred` is not a verdict: address it or do not
write the gate. The reviewer label says what kind of reviewer was used and
nothing more; add `session:<harness:id>` when the reviewer ran in its own
session (a Codex thread, a cross-harness review). A Claude Code subagent shares
your session id, so it gets the label only. `none` means no independent
review happened; the skill does not close on it.
```

Replace closing-sequence step 2 with:

```markdown
2. `tasks note <id> "gate: verified tree:<f> — checks: …; review: …; reviewer: …"` (the shape above; `~/.agents/bin/flow-state <id>` must then print `verified (findings: …)`, not `inconsistent`)
```

- [ ] **Step 2: Update the flow spec**

In `docs/specs/2026-09-15-flow-state-machine-design.md` section 3.2, replace the `implementing → verified` row's Record cell with the same shape as the skill row, and append to section 3.5, after "the sequence of `gate:` notes is the task's transition log.":

```markdown
The grammar of those notes is `agents/flow/gate-notes.md`, with the corpus
every parser is tested against beside it; a malformed note voids the state it
attempted (functional core spec, 2026-09-21, section 4.2).
```

In `docs/specs/2026-09-21-functional-core-design.md`, change the status line to `Status: implemented (ai-634de8); steps 4.1 and 4.2 landed on <date>.` with the actual date.

- [ ] **Step 3: Check the documents**

Run: `tasks check` (headings unchanged, so it prints nothing) and `grep -n "review outcome" agents/skills/flow/SKILL.md docs/specs/2026-09-15-flow-state-machine-design.md`.
Expected: `tasks check` prints nothing; the grep prints nothing, since the old free-text form is gone from both tables.

- [ ] **Step 4: Commit**

```bash
git add agents/skills/flow/SKILL.md docs/specs/2026-09-15-flow-state-machine-design.md docs/specs/2026-09-21-functional-core-design.md
git commit -m "docs(flow): the verified gate record carries finding records and a reviewer field"
```

---

## Verification of the whole (the parent's gate)

- `uv run --with pytest pytest agents/bin/test_flow_state.py -q` on the merged branch: all pass.
- The Task 2 sweep, rerun on the final tree, shows the same differences it showed then.
- One fresh-context review of the combined diff against spec sections 4.1 and 4.2, recorded as the parent's `gate: verified` note in the new shape, which `flow-state ai-634de8` must render as `verified (findings: …)`.
