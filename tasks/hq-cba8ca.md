---
id: hq-cba8ca
title: Read relay bootstrap probe evidence from ops private records
status: doing
priority: 0
size: s
complexity: mid
process: direct
owner: main
created: 2026-11-05T09:58:20Z
updated: 2026-11-05T11:24:58Z
started: 2026-11-05T11:24:36Z
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
