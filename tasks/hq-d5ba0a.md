---
id: hq-d5ba0a
title: Resolve tilde-layout findings before the stricter ops-check reaches hq
status: doing
priority: 2
size: m
complexity: mid
process: direct
owner: main
created: 2026-10-25T12:27:45Z
updated: 2026-10-25T15:07:27Z
started: 2026-10-25T15:07:14Z
depends: []
tags: [docs]
source: hq-c6a149
agent: claude-code
---

Why: ops-295f8d (in progress) makes ops-check flag home-relative aliases of registered checkouts, their parents and WORK_ROOT, such as ~/d/<project>, while leaving a bare ~ and generic conventions like ~/.config alone. hq now runs ops-check in pre-commit (hq-c6a149), so once that version is published into hq every commit, record commits included, refuses until the tree is clean. Sibling projects each got a task like this from ops-295f8d; hq had no checker then. Today 37 tracked files outside tasks/*.md carry ~/d forms, including the D5 placeholder ~/d/<project> that hq-c6a149 itself introduced [ref:adoption-spec], relay cutover tools and tests outside the D4 allowance (tools/relay-cutover, tools/relay-cutover-rehearse, tools/test_relay_cutover.py, tools/test_relay_wiring.py, tools/test_capture_notice_wiring.py, tools/test_claim_guard_wiring.py), plans and specs, and two attachment derivatives (hq-48c5c6 europa-policy-check-round2.out, hq-83c787 windows-refined.txt) whose raw bytes hq-c5fd83 retains.

Done: run the candidate checker from ops-295f8d over hq (or reproduce its rule) and classify each hit in context. Shared docs take repository-relative paths or project-role references (the hq main checkout), not ~ forms; host configuration by design (the D3 harness files, already allowed) stays; code and tests that build real paths derive them at runtime or move under a narrow allowance with a stated reason. Pick one replacement for the D5 checkout placeholder and apply it everywhere hq-c6a149 used ~/d/<project>, including re-deriving the two attachment derivatives through the same detach and attach fallback, with their mapping notes. Escalate to planned if a code path needs a design call. Verify: the candidate checker exits 0 on hq, just test passes, tasks check is clean, and the hq-c5fd83 retained records still match.

## References

- adoption-spec (context, kind=spec): docs/specs/2026-10-24-ops-check-adoption-design.md — D3 to D6 set the allowance and placeholder rules this revisits

## Notes

- 2026-10-25T12:28:00Z (main): concerns: hq-c6a149 change — the stricter ops-check from ops-295f8d will flag the ~/d/<project> placeholder hq-c6a149 adopted, and other ~/d forms already in the tree
- 2026-10-25T15:07:14Z (main): started
  provenance: {"harness_session":"codex:01a17398-cc3d-7af0-9262-eb2ff49f5236","harness_session_source":"CODEX_THREAD_ID"}
- 2026-10-25T15:07:27Z (main): trial: flow-trial-1 — enrolled — flow on
