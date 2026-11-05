---
id: hq-cba8ca
title: Read relay bootstrap probe evidence from ops private records
status: done
priority: 0
size: s
complexity: mid
process: direct
owner: main
created: 2026-11-05T09:58:20Z
updated: 2026-11-05T12:14:13Z
started: 2026-11-05T11:24:36Z
completed: 2026-11-05T12:13:52Z
closed: 2026-11-05T12:13:52Z
depends: [ops-b4b162]
tags: []
source: ops-7f0b75
agent: codex
origin: agent
---

Prerequisite for ops-7f0b75 removing the two historical probe evidence JSON files from ops code. The approved ops design is records commit 59aa5066d37c9c2555f3084d464af21b056d2e79, ops/docs/specs/2026-11-05-public-docs-curation-design.md; its exact Git-pinned bytes govern. This is a bounded consumer correction, separate from hq-4e0064 and the deferred full records migration. Do not change the measured environment or activate a live harness cutover.

After the docs-only archive supplies exact private files and hashes, replace the code-root evidence assumption in tools/relay_cutover_bootstrap/inventory.py and targets.py with explicit ops records resolution through tasks where for the ops code checkout on the executing host. Reuse hosts._run_child for a bounded read-only resolver call, require success and a valid records path, and use the same resolved evidence path for inventory, identities and --evidence. Preserve reviewed-manifest digest binding, version/shape validation, missing/mismatch refusal and child ownership; no fallback to code paths or arbitrary sibling guesses. No new CLI option or live activation. Update tools/test_relay_cutover_bootstrap.py, tools/test_relay_cutover_transport.py and docs/runbooks/relay-runtime.md as affected; keep fixtures synthetic and subprocess environments built key by key.

Done: focused RED-to-GREEN proves private-records evidence works with the old ops code paths absent; missing resolver/invalid response/missing evidence/digest mismatch fail before writes; installer arguments and inventory use the same reviewed bytes. Run the hq test front door under its own .tt.toml, mandatory hygiene and independent review. Publish exact code revision, command/test counts and archived evidence identities back to ops-7f0b75 before its deletion commit. Observe hq owner claims and all integration/live gates; no hq migration, host update or trial-environment change is authorized by this task.

## Notes

- 2026-11-05T09:58:20Z (add): created
  provenance: {"harness_session":"codex:01a1ab05-ce9a-72d1-890e-c01268ef1193","harness_session_source":"CODEX_THREAD_ID","origin":"agent"}
- 2026-11-05T10:56:11Z (main): Verified private evidence is now available: records archive A a83536d369734fcf0cb2ad6b8c876e8f7d5dadb3 (export tip 237520159d6201b4b14f2aed0d2a4cba64852c34), paths relative to ops records directory: docs/runbooks/relay-guard-evidence-claude-code.json SHA-256 8e124ab9c6504744d4ed17ca8d0619a9f553486573dacce2d648457c83bb5b84; docs/runbooks/relay-guard-evidence-codex.json SHA-256 bc2c280243f4562d93ffc2b43bbb01cca3832b278af376489f6e7e3a327fd04a. All historical/current archive bytes verified, and records-migrate find_import tuple unchanged. Ops code files still exist and must stay until this task supplies accepted integrated consumer proof. Resolve the executing host records location explicitly; no source-copy fallback and no live cutover/host installation. Archive step ops-b4b162 is closing after receipt verification.
- 2026-11-05T11:24:36Z (main): started
  provenance: {"harness_session":"codex:01a1ab05-ce9a-72d1-890e-c01268ef1193","harness_session_source":"CODEX_THREAD_ID"}
- 2026-11-05T11:24:58Z (main): trial: flow-trial-1 — enrolled — flow off
- 2026-11-05T11:25:00Z (main): arm: flow-trial-1 — unit tack-cba8ca — flow off
- 2026-11-05T11:26:00Z (fix/hq-cba8ca-records-evidence): Execution begins under approved ops inline plan Task 4, flow-trial-1 arm flow off. Created and locked .worktrees/hq-cba8ca on fix/hq-cba8ca-records-evidence at 1d0752c0; physical host-local storage on titan. just setup completed before tests/edits. This task owns that worktree through review/integration/disposal. Parent ops-7f0b75 owns shared execution workspace /mnt/ssd3/work/ops/ops-7f0b75/plans/public-docs-curation, where narrow test/review evidence for its deletion gate will be kept; no duplicate child workspace. Main preexisting agy/settings.json change is untouched; no host links or runtime are changed. Relevant focused baseline follows; broad baseline omitted under validated policy-off.
- 2026-11-05T11:32:50Z (fix/hq-cba8ca-records-evidence): Relevant baseline: 50 passed, 343 deselected in 99.40s via just test-one tools/test_relay_cutover_bootstrap.py tools/test_relay_cutover_transport.py -k inventory-or-manifest-or-dry_copy (actual quoted expression in parent hq-baseline.log). Broad baseline deliberately omitted by validated policy-off. Private-path RED: 6 failed before implementation; initial GREEN 6 passed. Caller scan additionally found tools/relay-cutover evidence() reads a computed old path; bootstrap inventory invokes it, so it is included with its own tests as a necessary consumer correction. Shared reply/path validation will preserve the standalone bounded runner and bootstrap owned-child route; no new option, live bootstrap, host pointer or activation. Parent ledger records Why/Cost and revision references.
- 2026-11-05T12:03:18Z (fix/hq-cba8ca-records-evidence): Implementation committed c9e54187131c1e8eef8822e106a03c084718c428; main refreshed by merge b1c66416b4f7d6e134b68a9b942d32d06f4302c7 (only three task records, no code change). Final focused scope: just test-one tools/test_relay_cutover.py tools/test_relay_cutover_transport.py tools/test_relay_cutover_bootstrap.py -n auto -k "not test_signal_while_recording_start_cancels" -x -> 461 passed in 243.76s, plus protected serial named signal case -> 1 passed in 0.19s. Mandatory hygiene passed; normal commit/merge hooks passed. Broad project suite deliberately omitted under policy-off; no remote evidence. Actual-host read-only tasks where plus pure validator resolved private ops records and confirmed both archived JSON SHA-256 values (hq-actual-records-proof.json). No live bootstrap, harness invocation, pointer/service change, install or push. Parent W logs retain RED/GREEN, interrupted/failed attempts and corrections; parent ledger records the standalone preflight and pure controller fingerprint rulings. Independent review follows before local hq merge.
- 2026-11-05T12:11:41Z (fix/hq-cba8ca-records-evidence): review: impl round 1 — verdict: accept; findings: Minor 1; reviewer: codex/gpt-6-astra
- 2026-11-05T12:12:25Z (fix/hq-cba8ca-records-evidence): Independent review accepted with no Critical/Important findings. Report /mnt/ssd3/work/ops/ops-7f0b75/plans/public-docs-curation/hq-cba8ca-round-1-report.md (8772 bytes), frozen 10cd3b13..8d2698bc. Minor M1 deferred in parent ops-7f0b75 ledger: bootstrap caches its own records lookup but nested standalone preflight resolves independently; runbook wording/test scope overstate one lookup. Parent owns disposition; no new runtime mechanism justified. All live deployment/adoption judgments remain outside this review.
- 2026-11-05T12:13:04Z (fix/hq-cba8ca-records-evidence): Accepted H integrated by local merge f08b92d429dd5afe2b9d7a9465f4d64ad1bff5fe on main; reviewed 8d2698bc is ancestor and tools/docs byte-identical. Disposing own clean locked worktree: .pytest_cache/ and tools/relay_cutover_bootstrap/__pycache__/ are regenerable test caches and may be discarded. No submodules or local .superpowers/sdd workspace; parent external workspace/ledger remains owned by open ops-7f0b75. Host-pointer inspection of ~/bin, ~/.local/bin, user units and known harness config includes found no reference into worktree. Session host-load: nothing left running. No push or live activation; main preexisting agy/settings.json change untouched.
- 2026-11-05T12:13:16Z (main): resumed
  provenance: {"harness_session":"codex:01a1ab05-ce9a-72d1-890e-c01268ef1193","harness_session_source":"CODEX_THREAD_ID"}
- 2026-11-05T12:13:50Z (main): retained: {"version":1,"host":"titan","kind":"worktree","path":".worktrees/hq-cba8ca","state":"released","verification":"verified","purpose":"Accepted branch merged into main with exact reviewed tools/docs; tt-report harvested timings, regenerable pytest/bytecode caches discarded, pointer/workspace checks passed; worktree removed and merged branch deleted","next_owner":"none","cleanup_trigger":"none"}
- 2026-11-05T12:13:52Z (main): done
  provenance: {"harness_session":"codex:01a1ab05-ce9a-72d1-890e-c01268ef1193","harness_session_source":"CODEX_THREAD_ID"}
- 2026-11-05T12:13:52Z (main): Accepted private-records correction integrated at f08b92d429dd5afe2b9d7a9465f4d64ad1bff5fe; subsequent note-only merge 58evidence is recorded in main ancestry (use Git for exact tip). Focused scope 461+1 affected tests passed; mandatory hygiene passed; broad suite deliberately omitted under policy-off; no remote evidence or live activation. Parent ops-7f0b75 owns logs/review/ledger, including deferred Minor M1; no other retained child items remain. Own worktree and merged branch removed after clean/cache/pointer/tt-report checks; no process survives, nothing pushed; unrelated agy/settings.json preserved.
  provenance: {"harness_session":"codex:01a1ab05-ce9a-72d1-890e-c01268ef1193","harness_session_source":"CODEX_THREAD_ID"}
- 2026-11-05T12:14:13Z (main): Correction to done-note wording: the note-only integration merge is b35319431dd12a4511f2c571df199388873e6a13; the text 58evidence was a transcription error, not a Git identifier. Accepted code integration H remains f08b92d429dd5afe2b9d7a9465f4d64ad1bff5fe. Main ancestry preserves the complete task/review record.
