---
id: gate-note-short-tree-rejected
title: A verified gate naming a commit instead of the covered-tree fingerprint is malformed
subject:
  kind: parser
  name: flow-state parse_note and the gate-note grammar (agents/flow/gate-notes.md)
  version: [ai@62e4a54 agents/bin/flow-state, ai@62e4a54 agents/flow/gate-notes.md]
inputs:
  - kind: note
    ref: obs-03e018, 2026-09-18T12:51:18Z
    value: "gate: verified tree:f5eaf94 — just gate (58 tests); independent review clean after two fix rounds"
expected:
  type: choice
  claim: the kind and reason parse_note returns
  choices: [gate, not-a-gate, malformed]
  value: malformed
  reason: tree hash not 40 hex
observed:
  value: malformed
  at: the subject version above
judge:
  kind: check
  command: >-
    python3 -c 'import importlib.util as u, sys; s = u.spec_from_loader("fs", loader=None);
    m = u.module_from_spec(s); sys.modules["fs"] = m; p = "agents/bin/flow-state";
    exec(compile(open(p).read(), p, "exec"), m.__dict__);
    r = m.parse_note(sys.argv[1]); print(r.kind, r.why)'
    'gate: verified tree:f5eaf94 — just gate (58 tests); independent review clean after two fix rounds'
  cwd: ai checkout
  pass: prints "malformed tree hash not 40 hex"
source: [ai-634de8, ai-f6a3a1]
evidence: observed
---

The functional-core spec (ai-634de8, section 4.1) requires the corpus to reject
this note. It is the one malformed note the on-record sweep found: obs-03e018's
verified gate named commit `f5eaf94` instead of the content fingerprint, and a
reopen note followed it about 50 seconds later. The note is line 33 of
`agents/flow/gate-notes.jsonl`; this case restates it with a subject version
and a judge, the two things a corpus line does not carry.
